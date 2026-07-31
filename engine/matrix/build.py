"""Kayan pencere → vektör matrisi (docs/01-mimari.md §4).

Her (timeframe, window_length) çifti için ayrı bir dizin:

    data/matrix/{timeframe}_{length}/
        vectors.npy   # (K, 32) float32 — normalize şekil vektörleri
        meta.npy      # (K,)    META_DTYPE

2 zaman dilimi × 4 pencere uzunluğu = **8 matris** (K-14).

Bellek: pencereler ``MATRIX_CHUNK_WINDOWS``'luk parçalar hâlinde işlenir ve
doğrudan diske akıtılır; hiçbir noktada tüm pencereler RAM'de tutulmaz.
Asıl hız kazancı zaten dilden değil, bitişik matris düzeninden gelir (K-01).

Normalizasyon sırası ve düz pencere düşürme kuralı ``engine.normalize``
modülünden gelir — burada tekrar edilmez.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from engine.config import (
    ATR_PERIOD,
    KLINES_DIR,
    MATRIX_CHUNK_WINDOWS,
    MATRIX_DIR,
    META_DTYPE,
    PRICE_CONTINUITY_MAX_RATIO,
    TIMEFRAME_MS,
    N_POINTS,
    STRIDE,
    TIMEFRAMES,
    WINDOW_LENGTHS,
)
from engine.ingest.store import available_symbols, read_klines, write_json_atomic
from engine.ingest.symbol_universe import load_universe, symbol_id_map
from engine.matrix.liquidity import LiquidityMask, build_from_klines, month_key, save_table
from engine.matrix.npy_store import ChunkedNpyWriter
from engine.matrix.universe_filter import filter_universe
from engine.normalize.amplitude import amplitude_batch
from engine.normalize.atr import wilder_atr
from engine.normalize.pipeline import normalize_batch

log = logging.getLogger(__name__)

VECTORS_FILE = "vectors.npy"
META_FILE = "meta.npy"


def matrix_dir(timeframe: str, length: int, root: Path | None = None) -> Path:
    return Path(root or MATRIX_DIR) / f"{timeframe}_{length}"


@dataclass
class BuildStats:
    symbols: int = 0
    windows: int = 0
    dropped: int = 0

    def __str__(self) -> str:  # pragma: no cover - log biçimi
        return f"{self.symbols} sembol, {self.windows} pencere, {self.dropped} düştü (düz + boşluklu)"


def window_starts(n_bars: int, length: int, stride: int = STRIDE, from_bar: int = 0) -> np.ndarray:
    """``from_bar``'dan itibaren biten pencerelerin başlangıç indeksleri.

    Izgara daima 0'dan hizalanır; artımlı güncelleme aynı pencereleri yeniden
    üretmesin diye (aynı stride ızgarası).
    """
    if n_bars < length:
        return np.empty(0, dtype=np.int64)
    last_start = n_bars - length
    starts = np.arange(0, last_start + 1, stride, dtype=np.int64)
    if from_bar > 0:
        starts = starts[starts + length - 1 >= from_bar]
    return starts


def build_symbol_rows(
    df: pd.DataFrame,
    symbol: str,
    symbol_id: int,
    length: int,
    timeframe: str,
    liquidity: LiquidityMask | None,
    stride: int = STRIDE,
    from_bar: int = 0,
    chunk: int = MATRIX_CHUNK_WINDOWS,
) -> Iterable[tuple[np.ndarray, np.ndarray]]:
    """Bir sembolün pencerelerini chunk'lar hâlinde (vectors, meta) üretir.

    Generator'dır: çağıran her chunk'ı diske yazıp bırakır, RAM'de birikmez.
    """
    n = len(df)
    starts = window_starts(n, length, stride, from_bar)
    if starts.size == 0:
        return

    close = df["close"].to_numpy(dtype=np.float64)
    high = df["high"].to_numpy(dtype=np.float64)
    low = df["low"].to_numpy(dtype=np.float64)
    open_time = df["open_time"].to_numpy(dtype=np.int64)

    # ATR dizisi bir kez; atr[i] yalnızca 0..i barlarını kullanır (lookahead yok).
    atr = wilder_atr(high, low, close, ATR_PERIOD)
    months = month_key(open_time)
    expected_span = (length - 1) * TIMEFRAME_MS[timeframe]

    # Fiyat sürekliliği (F4): bar-bar oranı eşiği aşan yer bir fiyat hareketi
    # değil, redenominasyon / token swap / ticker yeniden kullanımıdır
    # (LUNAUSDT'de 177.400x). O noktayı içeren pencere geçersizdir.
    with np.errstate(divide="ignore", invalid="ignore"):
        step_ratio = np.maximum(close[1:] / close[:-1], close[:-1] / close[1:])
    jump = np.zeros(n, dtype=bool)
    jump[1:] = ~np.isfinite(step_ratio) | (step_ratio > PRICE_CONTINUITY_MAX_RATIO)
    jump_cum = np.concatenate([[0], np.cumsum(jump)])

    for c0 in range(0, starts.size, chunk):
        block = starts[c0 : c0 + chunk]
        ends = block + length - 1

        # (c, L) pencere matrisi — sadece bu chunk kopyalanır.
        idx = block[:, None] + np.arange(length, dtype=np.int64)[None, :]
        raw = close[idx]

        vectors, valid = normalize_batch(raw, N_POINTS)

        # Zaman sürekliliği invariant'ı (F3.5, Adım 3): boşluk içeren pencere
        # matrise girmez. Aksi hâlde "24 bar" sanılan bir pencere 40 takvim
        # günü kapsayabilir — şekil yapısal olarak bozulur.
        #
        # Boşluk ffill ile DOLDURULMAZ: uydurma bar True Range = 0 üretir,
        # ATR'yi yapay olarak düşürür (K-16 bariyerleri daralır → sahte TP/SL),
        # şekle düz plato ekler ve volume = 0 ile likidite sıralamasını (K-13)
        # bozar. Doğrusu düşürmektir; 1,9M pencerede birkaç bin kayıp önemsiz.
        span = open_time[ends] - open_time[block]
        valid &= span == expected_span
        # Pencere içinde fiyat sıçraması var mı? (kümülatif sayaç farkı)
        valid &= (jump_cum[ends + 1] - jump_cum[block + 1]) == 0
        if not valid.any():
            continue

        amps = amplitude_batch(raw)
        meta = np.empty(block.size, dtype=META_DTYPE)
        meta["symbol_id"] = symbol_id
        meta["start_idx"] = block
        meta["end_idx"] = ends
        meta["end_time"] = open_time[ends]
        meta["amplitude"] = amps
        meta["atr"] = np.nan_to_num(atr[ends], nan=0.0)
        if liquidity is None:
            meta["liquid"] = True
        else:
            meta["liquid"] = liquidity.lookup(symbol, months[ends])

        yield vectors[valid], meta[valid]


def build_matrix(
    timeframe: str,
    length: int,
    symbols: Sequence[str],
    ids: dict[str, int],
    liquidity: LiquidityMask | None = None,
    klines_root: Path | None = None,
    out_root: Path | None = None,
    stride: int = STRIDE,
    chunk: int = MATRIX_CHUNK_WINDOWS,
) -> BuildStats:
    """Tek bir (timeframe, length) matrisini sıfırdan inşa eder."""
    out_dir = matrix_dir(timeframe, length, out_root)
    out_dir.mkdir(parents=True, exist_ok=True)

    stats = BuildStats()
    vec_writer = ChunkedNpyWriter(out_dir / VECTORS_FILE, np.float32, (N_POINTS,))
    meta_writer = ChunkedNpyWriter(out_dir / META_FILE, META_DTYPE)

    try:
        for symbol in symbols:
            df = read_klines(symbol, timeframe, klines_root)
            if len(df) < length:
                continue
            stats.symbols += 1
            total_windows = window_starts(len(df), length, stride).size

            kept = 0
            for vectors, meta in build_symbol_rows(
                df, symbol, ids.get(symbol, -1), length, timeframe, liquidity, stride, chunk=chunk
            ):
                vec_writer.append(vectors)
                meta_writer.append(meta)
                kept += len(meta)

            stats.windows += kept
            stats.dropped += total_windows - kept
    except BaseException:
        vec_writer.abort()
        meta_writer.abort()
        raise

    vec_writer.close()
    meta_writer.close()
    log.info("matris %s_%d: %s", timeframe, length, stats)
    return stats


def build_all(
    timeframes: Sequence[str] = TIMEFRAMES,
    lengths: Sequence[int] = WINDOW_LENGTHS,
    symbols: Sequence[str] | None = None,
    klines_root: Path | None = None,
    out_root: Path | None = None,
    use_liquidity: bool = True,
    stride: int = STRIDE,
    exclude_pegged: bool = True,
) -> dict[str, BuildStats]:
    """8 matrisin tamamını inşa eder (2 timeframe × 4 uzunluk)."""
    universe = load_universe()
    ids = symbol_id_map(universe) if universe else {}

    results: dict[str, BuildStats] = {}
    for timeframe in timeframes:
        tf_symbols = list(symbols) if symbols else available_symbols(timeframe, klines_root)
        if not tf_symbols:
            log.warning("%s için Parquet verisi yok — atlanıyor", timeframe)
            continue

        # Sabitlenmiş pariteler matrise hiç girmez (F3.5): z-score onların
        # %2'lik dalgalanmasını kusursuz formasyona çevirip ilk sayfanın
        # tepesine yerleştiriyordu.
        if exclude_pegged:
            tf_symbols, pegged = filter_universe(tf_symbols, timeframe, klines_root)
            if pegged:
                log.info("%s: sabitlenmiş %d parite atlandı (%s...)", timeframe, len(pegged), ", ".join(pegged[:3]))

        # symbol_id evrende yoksa (ör. sadece test verisi) sıralı id ata.
        for s in tf_symbols:
            ids.setdefault(s, len(ids))

        mask: LiquidityMask | None = None
        if use_liquidity:
            table = build_from_klines(tf_symbols, timeframe, klines_root)
            save_table(table, Path(out_root or MATRIX_DIR) / f"liquidity_{timeframe}.parquet")
            mask = LiquidityMask(table)
            log.info("%s likidite: %d (sembol, ay) çifti likit", timeframe, len(mask))

        # SearchEngine'in symbol_id → sembol adı çözebilmesi için (matris
        # meta'sındaki id'ler bu haritaya referans verir).
        write_json_atomic(
            {s: int(ids[s]) for s in tf_symbols}, Path(out_root or MATRIX_DIR) / "symbols.json"
        )

        for length in lengths:
            results[f"{timeframe}_{length}"] = build_matrix(
                timeframe,
                length,
                tf_symbols,
                ids,
                liquidity=mask,
                klines_root=klines_root,
                out_root=out_root,
                stride=stride,
            )

    return results


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI
    import argparse

    p = argparse.ArgumentParser(prog="python -m engine.matrix.build")
    p.add_argument("--timeframes", nargs="+", default=list(TIMEFRAMES))
    p.add_argument("--lengths", nargs="+", type=int, default=list(WINDOW_LENGTHS))
    p.add_argument("--symbols", nargs="+", default=None)
    p.add_argument("--klines-root", default=str(KLINES_DIR))
    p.add_argument("--out-root", default=str(MATRIX_DIR))
    p.add_argument("--no-liquidity", action="store_true")
    p.add_argument("--keep-pegged", action="store_true", help="sabitlenmiş pariteleri de dahil et")
    p.add_argument("--log-level", default="INFO")
    args = p.parse_args(argv)

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    stats = build_all(
        timeframes=args.timeframes,
        lengths=args.lengths,
        symbols=args.symbols,
        klines_root=Path(args.klines_root),
        out_root=Path(args.out_root),
        use_liquidity=not args.no_liquidity,
        exclude_pegged=not args.keep_pegged,
    )
    for name, s in stats.items():
        print(f"{name}: {s}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
