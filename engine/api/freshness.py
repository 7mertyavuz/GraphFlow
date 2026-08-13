"""Veri tazeliği — API tarafı önbelleği.

``engine.ingest.health.freshness`` her sembolün parquet ayak izini okur; bu
arama başına yapılacak bir iş değildir. Rapor ``FRESHNESS_TTL_SECONDS``
boyunca süreç içinde tutulur.

Tazelik **sessizce yutulmaz**: bayat veriyle dönen bir Radar sonucu,
kullanıcının "şu an oluşan formasyon" sandığı ama üç gün önce kapanmış bir
pencereyi göstermek demektir.
"""

from __future__ import annotations

import time
from typing import Final

from engine.config import FRESHNESS_TTL_SECONDS, TIMEFRAMES
from engine.ingest.health import FreshnessReport, freshness

_cache: dict[str, tuple[float, FreshnessReport]] = {}

UNKNOWN: Final[int] = 0


def report(timeframe: str) -> FreshnessReport:
    now = time.monotonic()
    hit = _cache.get(timeframe)
    if hit is not None and now - hit[0] < FRESHNESS_TTL_SECONDS:
        return hit[1]

    value = freshness(timeframe)
    _cache[timeframe] = (now, value)
    return value


def data_as_of(timeframe: str) -> int:
    """Deponun gördüğü en yeni barın açılış zamanı (ms); veri yoksa 0."""
    newest = report(timeframe).newest_open_time
    return int(newest) if newest is not None else UNKNOWN


def is_stale(timeframe: str) -> bool:
    return not report(timeframe).ok


def snapshot() -> dict[str, dict]:
    """Tüm zaman dilimleri için tazelik özeti (``/api/health``)."""
    out: dict[str, dict] = {}
    for tf in TIMEFRAMES:
        try:
            r = report(tf)
        except Exception:  # veri kökü yok / bozuk — sağlık ucu yine cevap verir
            out[tf] = {"symbols": 0, "newest_open_time": 0, "stale_bars": None, "ok": False}
            continue
        out[tf] = {
            "symbols": r.symbols,
            "newest_open_time": int(r.newest_open_time or 0),
            "stale_bars": None if r.stale_bars == float("inf") else round(r.stale_bars, 2),
            "limit_bars": r.limit_bars,
            "ok": r.ok,
        }
    return out


def clear() -> None:
    """Testler için önbelleği boşaltır."""
    _cache.clear()
