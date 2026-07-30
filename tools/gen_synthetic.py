"""Sentetik OHLCV üreteci — ground truth'lu doğrulama verisi.

Binance indirmesinin bitmesini beklemeye gerek yok: geometrik brownian
hareket (GBM) tabanlı bir fiyat serisine, bilinen formasyonlar **rastgele
ölçek, uzunluk ve gürültüyle** enjekte edilir. Nerede hangi formasyonun
olduğunu bildiğimiz için bu, gerçek veriden **daha güçlü** bir doğrulamadır:
motorun bulduğu sonuçlar objektif olarak doğru/yanlış diye işaretlenebilir.

Enjeksiyon log-fiyat uzayında yapılır ve serinin geri kalanı kaydırılarak
süreklilik korunur — enjeksiyon sınırında yapay sıçrama oluşmaz.

CLI::

    python -m tools.gen_synthetic --out data/synthetic --symbols 20
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import pandas as pd

from engine.config import HISTORY_START_MS, TIMEFRAME_MS
from engine.ingest.store import write_atomic
from tools.shapes import shape


@dataclass(frozen=True)
class Injection:
    """Ground truth kaydı: hangi formasyon, hangi bar aralığında."""

    symbol: str
    pattern: str
    start: int
    end: int  # dahil
    length: int
    amplitude_log: float
    noise: float


def gbm_log_prices(n: int, rng: np.random.Generator, sigma: float = 0.02, drift: float = 0.0) -> np.ndarray:
    """Driftsiz(e yakın) geometrik brownian hareketin log fiyat yolu."""
    steps = rng.normal(loc=drift, scale=sigma, size=n)
    steps[0] = 0.0
    return np.cumsum(steps)


def inject(
    log_price: np.ndarray,
    start: int,
    pattern: str,
    length: int,
    amplitude_log: float,
    noise: float,
    rng: np.random.Generator,
) -> None:
    """``log_price`` üzerine formasyonu yerinde (in-place) yazar.

    Segment, başlangıç seviyesine sabitlenir; segment sonrası tüm seri
    oluşan farkla kaydırılır → süreklilik korunur.
    """
    end = start + length
    form = shape(pattern, length) * amplitude_log
    form = form - form[0]
    if noise > 0:
        form = form + rng.normal(0.0, noise * amplitude_log, size=length)
        form = form - form[0]

    old_tail_delta = log_price[end - 1] - log_price[start]
    log_price[start:end] = log_price[start] + form
    log_price[end:] += (log_price[end - 1] - log_price[start]) - old_tail_delta


def ohlcv_from_log_prices(
    log_price: np.ndarray,
    rng: np.random.Generator,
    timeframe: str = "4h",
    start_ms: int = HISTORY_START_MS,
    base_price: float = 100.0,
    base_volume: float = 1_000_000.0,
) -> pd.DataFrame:
    """Log fiyat yolundan tutarlı OHLCV üretir (high >= max(o,c) vb.)."""
    n = log_price.size
    close = base_price * np.exp(log_price)

    open_ = np.empty(n)
    open_[0] = close[0]
    open_[1:] = close[:-1]

    wick = np.abs(rng.normal(0.0, 0.004, size=(2, n)))
    high = np.maximum(open_, close) * (1.0 + wick[0])
    low = np.minimum(open_, close) * (1.0 - wick[1])

    volume = base_volume * np.exp(rng.normal(0.0, 0.35, size=n))
    step = TIMEFRAME_MS[timeframe]
    open_time = start_ms + np.arange(n, dtype=np.int64) * step

    return pd.DataFrame(
        {
            "open_time": open_time,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "quote_volume": volume * close,
            "trades": np.maximum(1, (volume / 10.0).astype(np.int32)),
        }
    )


def make_symbol(
    symbol: str,
    rng: np.random.Generator,
    n_bars: int = 2_000,
    patterns: tuple[str, ...] = ("head_and_shoulders", "cup_and_handle", "bull_flag"),
    n_injections: int = 6,
    length_range: tuple[int, int] = (24, 100),
    amplitude_range: tuple[float, float] = (0.10, 0.45),
    noise_range: tuple[float, float] = (0.02, 0.12),
    gbm_sigma: float = 0.02,
    timeframe: str = "4h",
    base_price: float | None = None,
) -> tuple[pd.DataFrame, list[Injection]]:
    """Tek bir sentetik parite: GBM + rastgele yerleştirilmiş formasyonlar."""
    log_price = gbm_log_prices(n_bars, rng, sigma=gbm_sigma)

    # Enjeksiyonlar çakışmasın: aralarında en az bir pencere boşluk bırak.
    injections: list[Injection] = []
    occupied: list[tuple[int, int]] = []
    attempts = 0
    while len(injections) < n_injections and attempts < n_injections * 50:
        attempts += 1
        length = int(rng.integers(length_range[0], length_range[1] + 1))
        start = int(rng.integers(50, max(51, n_bars - length - 50)))
        end = start + length - 1
        if any(not (end + 20 < s or start - 20 > e) for s, e in occupied):
            continue

        pattern = str(rng.choice(patterns))
        amplitude = float(rng.uniform(*amplitude_range))
        noise = float(rng.uniform(*noise_range))
        inject(log_price, start, pattern, length, amplitude, noise, rng)

        occupied.append((start, end))
        injections.append(
            Injection(symbol, pattern, start, end, length, amplitude, noise)
        )

    price = base_price if base_price is not None else float(np.exp(rng.uniform(-6.0, 11.0)))
    df = ohlcv_from_log_prices(log_price, rng, timeframe=timeframe, base_price=price)
    return df, sorted(injections, key=lambda i: i.start)


def generate_dataset(
    out_root: Path,
    n_symbols: int = 20,
    n_bars: int = 2_000,
    timeframe: str = "4h",
    seed: int = 7,
    **symbol_kwargs,
) -> list[Injection]:
    """Parquet deposu + ``ground_truth.json`` üretir."""
    rng = np.random.default_rng(seed)
    out_root = Path(out_root)
    truth: list[Injection] = []

    for i in range(n_symbols):
        symbol = f"SYN{i:03d}USDT"
        df, injections = make_symbol(symbol, rng, n_bars=n_bars, timeframe=timeframe, **symbol_kwargs)
        write_atomic(df, out_root / timeframe / f"{symbol}.parquet")
        truth.extend(injections)

    (out_root / "ground_truth.json").write_text(
        json.dumps([asdict(i) for i in truth], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return truth


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI
    p = argparse.ArgumentParser(prog="python -m tools.gen_synthetic")
    p.add_argument("--out", default="data/synthetic")
    p.add_argument("--symbols", type=int, default=20)
    p.add_argument("--bars", type=int, default=2_000)
    p.add_argument("--timeframe", default="4h")
    p.add_argument("--seed", type=int, default=7)
    args = p.parse_args(argv)

    truth = generate_dataset(
        Path(args.out),
        n_symbols=args.symbols,
        n_bars=args.bars,
        timeframe=args.timeframe,
        seed=args.seed,
    )
    print(f"{args.symbols} sembol, {len(truth)} enjekte formasyon → {args.out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
