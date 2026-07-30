"""Artımlı matris güncellemesi — docs/01-mimari.md §4.4.

Cron her çalıştığında **yalnızca yeni kapanan mumların** ürettiği pencereler
matrisin sonuna eklenir. 1,5 GB'lık matrisi 5 dakikada bir yeniden inşa etmek
gereksizdir; performans bütçesi bu iş için < 30 sn öngörür (§15).

Devam noktası matrisin kendisinden okunur: bir sembolün ``meta``'daki en
büyük ``end_idx``'i, o sembol için son üretilmiş pencerenin bitişidir.
Pencere ızgarası daima 0'dan hizalandığı (``window_starts``) için yeni
pencereler eskileriyle örtüşmez ve tekrar üretilmez.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

import numpy as np

from engine.config import META_DTYPE, N_POINTS, STRIDE, TIMEFRAMES, WINDOW_LENGTHS
from engine.ingest.store import available_symbols, read_klines
from engine.ingest.symbol_universe import load_universe, symbol_id_map
from engine.matrix.build import META_FILE, VECTORS_FILE, build_symbol_rows, matrix_dir
from engine.matrix.liquidity import LiquidityMask
from engine.matrix.npy_store import append_rows, load_matrix

log = logging.getLogger(__name__)


def last_end_idx(meta: np.ndarray) -> dict[int, int]:
    """symbol_id → matriste kayıtlı en büyük end_idx."""
    if meta.size == 0:
        return {}
    sid = np.asarray(meta["symbol_id"])
    end = np.asarray(meta["end_idx"])
    out: dict[int, int] = {}
    for s in np.unique(sid):
        out[int(s)] = int(end[sid == s].max())
    return out


def update_matrix(
    timeframe: str,
    length: int,
    symbols: Sequence[str] | None = None,
    ids: dict[str, int] | None = None,
    liquidity: LiquidityMask | None = None,
    klines_root: Path | None = None,
    out_root: Path | None = None,
    stride: int = STRIDE,
) -> int:
    """Tek matrise yeni pencereleri ekler; eklenen satır sayısını döner."""
    out_dir = matrix_dir(timeframe, length, out_root)
    vec_path = out_dir / VECTORS_FILE
    meta_path = out_dir / META_FILE
    if not vec_path.exists() or not meta_path.exists():
        raise FileNotFoundError(f"{out_dir} yok — önce engine.matrix.build çalıştırın")

    meta = load_matrix(meta_path)
    frontier = last_end_idx(meta)
    del meta

    if ids is None:
        ids = symbol_id_map(load_universe())
    if symbols is None:
        symbols = available_symbols(timeframe, klines_root)

    added = 0
    for symbol in symbols:
        symbol_id = ids.get(symbol)
        if symbol_id is None:
            continue
        df = read_klines(symbol, timeframe, klines_root)
        if len(df) < length:
            continue

        known_end = frontier.get(symbol_id, -1)
        if known_end >= len(df) - 1:
            continue  # yeni kapanmış bar yok

        for vectors, new_meta in build_symbol_rows(
            df, symbol, symbol_id, length, timeframe, liquidity, stride, from_bar=known_end + 1
        ):
            # Güvenlik ağı: ızgara kayması olursa bile eski pencereyi tekrar yazma.
            fresh = new_meta["end_idx"] > known_end
            if not fresh.any():
                continue
            append_rows(vec_path, np.ascontiguousarray(vectors[fresh], dtype=np.float32))
            append_rows(meta_path, np.ascontiguousarray(new_meta[fresh], dtype=META_DTYPE))
            added += int(fresh.sum())

    if added:
        log.info("%s_%d: +%d pencere", timeframe, length, added)
    return added


def update_all(
    timeframes: Sequence[str] = TIMEFRAMES,
    lengths: Sequence[int] = WINDOW_LENGTHS,
    symbols: Sequence[str] | None = None,
    klines_root: Path | None = None,
    out_root: Path | None = None,
    liquidity: LiquidityMask | None = None,
    stride: int = STRIDE,
) -> dict[str, int]:
    ids = symbol_id_map(load_universe())
    return {
        f"{tf}_{length}": update_matrix(
            tf,
            length,
            symbols=symbols,
            ids=ids or None,
            liquidity=liquidity,
            klines_root=klines_root,
            out_root=out_root,
            stride=stride,
        )
        for tf in timeframes
        for length in lengths
    }


def matrix_shape(timeframe: str, length: int, out_root: Path | None = None) -> tuple[int, int]:
    v = load_matrix(matrix_dir(timeframe, length, out_root) / VECTORS_FILE)
    shape = (int(v.shape[0]), int(v.shape[1]) if v.ndim > 1 else N_POINTS)
    del v
    return shape
