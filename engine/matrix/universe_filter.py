"""Sabitlenmiş (pegged) parite filtresi — F3.5, K-10'un ölçülmüş uzantısı.

F3 göz testinde ölçülen sorun: z-score, şeklin *kimliğini* fiyat seviyesinden
ve hareket büyüklüğünden ayırır (K-02). Bu, sabitlenmiş bir paritede kusursuz
ama **anlamsız** formasyonlar üretir — PAXUSDT'nin %4'lük dalgalanması, OBO
sorgusunda birinci sıraya yerleşiyordu.

Genlik filtresi (K-10) tek başına yeterli değil: eşiği, düşük oynaklıklı ama
meşru pariteleri de eleyecek kadar yükseltmek gerekirdi. Bu yüzden **yapısal**
bir filtre eklenir: fiyatı geçmişinin çoğunda ``1,0 ± PEG_TOLERANCE`` içinde
kalan parite evrenden düşer.

Kural yalnızca sabitlenmiş varlıkları yakalar, "ucuz" olanları değil: ölçüt
1,0 civarında **kalmak**, küçük olmak değil. Gerçek veride ayrım keskin çıktı —
oranı 0,96'nın üstünde 19 parite var, 0,30 ile 0,96 arasında hiç yok.

Yakalananlar arasında sarmalanmış varlıklar da vardır (``WBTCBTC``,
``RENBTCBTC``, ``BTCBBTC``): onlar da kendi dayanağına sabitlidir ve aynı
sorunu üretir.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

from engine.config import META_DIR, PEG_MIN_RATIO, PEG_TOLERANCE
from engine.ingest.store import read_json, read_klines, write_json_atomic

log = logging.getLogger(__name__)

PEGGED_FILE = "pegged_symbols.json"


def peg_ratio(close: np.ndarray, tolerance: float = PEG_TOLERANCE) -> float:
    """Fiyatın 1,0 ± tolerance bandında kaldığı bar oranı."""
    c = np.asarray(close, dtype=np.float64)
    if c.size == 0:
        return 0.0
    return float(np.mean(np.abs(c - 1.0) <= tolerance))


def is_pegged(
    close: np.ndarray,
    tolerance: float = PEG_TOLERANCE,
    min_ratio: float = PEG_MIN_RATIO,
    min_bars: int = 30,
) -> bool:
    c = np.asarray(close, dtype=np.float64)
    if c.size < min_bars:
        return False
    return peg_ratio(c, tolerance) >= min_ratio


def detect_pegged(
    symbols: Iterable[str],
    timeframe: str,
    root: Path | None = None,
    tolerance: float = PEG_TOLERANCE,
    min_ratio: float = PEG_MIN_RATIO,
) -> list[str]:
    """Sabitlenmiş pariteleri bulur (oranlarıyla loglar)."""
    found: list[str] = []
    for symbol in symbols:
        df = read_klines(symbol, timeframe, root, columns=["close"])
        if df.empty:
            continue
        close = df["close"].to_numpy()
        if is_pegged(close, tolerance, min_ratio):
            found.append(symbol)
            log.debug("sabitlenmiş: %s (oran %.3f)", symbol, peg_ratio(close, tolerance))
    return sorted(found)


def filter_universe(
    symbols: Sequence[str],
    timeframe: str,
    root: Path | None = None,
    save_to: Path | None = None,
) -> tuple[list[str], list[str]]:
    """(kalanlar, düşenler) döndürür ve düşenleri diske kaydeder."""
    pegged = detect_pegged(symbols, timeframe, root)
    kept = [s for s in symbols if s not in set(pegged)]

    if pegged:
        path = Path(save_to or (META_DIR / PEGGED_FILE))
        existing = read_json(path, default={}) or {}
        existing[timeframe] = pegged
        write_json_atomic(existing, path)
        log.info("%s: %d sabitlenmiş parite evrenden düştü", timeframe, len(pegged))

    return kept, pegged


def load_pegged(timeframe: str, path: Path | None = None) -> list[str]:
    data = read_json(Path(path or (META_DIR / PEGGED_FILE)), default={}) or {}
    return list(data.get(timeframe, []))
