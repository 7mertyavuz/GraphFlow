"""Hızlı başlangıç için sentetik demo korpusu üreticisi.

Yeni klonlayan bir kullanıcının 3 GB Binance verisi indirmeden tüm uygulamayı
(Radar, Backtest, üçlü bariyer istatistikleri ve grafik görünümü) ~5 saniyede
deneyebilmesi için 24 sembollük gerçekçi bir GBM + formasyon korpusu ve
8 arama matrisini üretir:

    python -m tools.generate_demo_corpus --out data/demo
    GRAPHFLOW_DATA_DIR=data/demo uvicorn engine.api.main:app --port 8000

Varsayılan ``data/`` dizininde gerçek korpus varsa üzerine yazmayı reddeder
(``--force`` ile geçersiz kılınabilir).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from engine.config import DATA_DIR, TIMEFRAMES
from engine.ingest.store import write_atomic
from engine.matrix.build import build_all
from engine.templates import load_all
from tools.gen_synthetic import make_symbol

DEMO_SYMBOLS: tuple[str, ...] = (
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "AVAXUSDT",
    "DOGEUSDT",
    "DOTUSDT",
    "LINKUSDT",
    "MATICUSDT",
    "LTCUSDT",
    "UNIUSDT",
    "ATOMUSDT",
    "NEARUSDT",
    "APTUSDT",
    "ARBUSDT",
    "OPUSDT",
    "INJUSDT",
    "SUIUSDT",
    "AAVEUSDT",
    "FILUSDT",
    "ETCUSDT",
    "RNDRUSDT",
)


def generate_demo_corpus(
    out_dir: Path,
    *,
    n_bars_1d: int = 900,
    n_bars_4h: int = 1200,
    seed: int = 2026,
    force: bool = False,
) -> dict[str, int]:
    """``out_dir`` altına ``klines/`` ve ``matrix/`` üretir."""
    out_dir = Path(out_dir)
    klines_root = out_dir / "klines"
    matrix_root = out_dir / "matrix"

    existing_parquets = list(klines_root.glob("*/*.parquet")) if klines_root.exists() else []
    if existing_parquets and not force:
        raise FileExistsError(
            f"{klines_root} zaten {len(existing_parquets)} Parquet dosyası içeriyor. "
            "Üzerine yazmak için --force kullanın veya --out data/demo verin."
        )

    rng = np.random.default_rng(seed)
    all_patterns = tuple(load_all().keys())

    for tf, n_bars in (("1d", n_bars_1d), ("4h", n_bars_4h)):
        for idx, sym in enumerate(DEMO_SYMBOLS):
            p1 = all_patterns[idx % len(all_patterns)]
            p2 = all_patterns[(idx + 5) % len(all_patterns)]
            df, _ = make_symbol(
                sym,
                rng,
                n_bars=n_bars,
                timeframe=tf,
                patterns=(p1, p2),
                n_injections=4,
                length_range=(32, 85),
                amplitude_range=(0.16, 0.38),
                noise_range=(0.015, 0.045),
            )
            write_atomic(df, klines_root / tf / f"{sym}.parquet")

    stats = build_all(
        timeframes=TIMEFRAMES,
        klines_root=klines_root,
        out_root=matrix_root,
        use_liquidity=False,
    )
    return {k: v.windows for k, v in stats.items()}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m tools.generate_demo_corpus")
    p.add_argument(
        "--out",
        default=str(DATA_DIR / "demo"),
        help="Hedef veri dizini (varsayılan: data/demo)",
    )
    p.add_argument("--force", action="store_true", help="Var olan dosyaların üzerine yaz")
    p.add_argument("--seed", type=int, default=2026)
    args = p.parse_args(argv)

    out_path = Path(args.out)
    counts = generate_demo_corpus(out_path, seed=args.seed, force=args.force)
    total_windows = sum(counts.values())
    print(f"Demo korpus hazır: {out_path} ({len(DEMO_SYMBOLS)} sembol, {total_windows:,} toplam pencere)")
    for k, w in counts.items():
        print(f"  {k}: {w:,} pencere")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
