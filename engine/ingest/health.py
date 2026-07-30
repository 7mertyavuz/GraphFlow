"""Veri sağlığı invariant'ları — F3.5.

F3'te yakalanan hata (arşivin mikrosaniye damgaya geçmesi) **sıfır hata
mesajıyla** 19 aylık veriyi yok etti. İndirme başarıyla bitti, dosyalar
yazıldı, testler geçti — yalnızca veri yoktu.

Bu sınıf hatanın bir daha sessiz kalmaması için kalıcı bir invariant:

    max(open_time) bugünden ``MAX_STALENESS_BARS`` bardan fazla geride olamaz.

Eşik bar cinsindendir, çünkü tazelik zaman diliminin kendi ölçeğine bağlıdır:
1d için 3 bar = 3 gün, 4h için 3 bar = 12 saat.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from engine.config import MAX_STALENESS_BARS, TIMEFRAME_MS
from engine.ingest.store import available_symbols, last_open_time


@dataclass(frozen=True)
class FreshnessReport:
    timeframe: str
    symbols: int
    newest_open_time: int | None
    stale_bars: float
    limit_bars: int

    @property
    def ok(self) -> bool:
        return self.newest_open_time is not None and self.stale_bars <= self.limit_bars

    def __str__(self) -> str:  # pragma: no cover - log biçimi
        if self.newest_open_time is None:
            return f"{self.timeframe}: veri yok"
        durum = "TAZE" if self.ok else "BAYAT"
        return (
            f"{self.timeframe}: {self.symbols} sembol, en yeni bar "
            f"{self.stale_bars:.1f} bar geride (sınır {self.limit_bars}) -> {durum}"
        )


def freshness(
    timeframe: str,
    symbols: Sequence[str] | None = None,
    root: Path | None = None,
    now_ms: int | None = None,
    limit_bars: int | None = None,
) -> FreshnessReport:
    """Depodaki en yeni barın kaç bar geride kaldığını ölçer.

    "En yeni" ölçütü **tüm evrenin maksimumu**dur: tek tek semboller delist
    edilmiş olabilir (K-13 gereği veri setinde kalırlar), ama evrenin tamamı
    birden geri kalıyorsa ingest bozulmuş demektir.
    """
    step = TIMEFRAME_MS[timeframe]
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    limit = limit_bars if limit_bars is not None else MAX_STALENESS_BARS[timeframe]

    names = list(symbols) if symbols is not None else available_symbols(timeframe, root)
    newest: int | None = None
    for symbol in names:
        value = last_open_time(symbol, timeframe, root)
        if value is not None and (newest is None or value > newest):
            newest = value

    stale = float("inf") if newest is None else (now_ms - newest) / step
    return FreshnessReport(timeframe, len(names), newest, stale, limit)


def check_freshness(
    timeframe: str,
    symbols: Sequence[str] | None = None,
    root: Path | None = None,
    now_ms: int | None = None,
    limit_bars: int | None = None,
) -> FreshnessReport:
    """``freshness`` ile aynı, ama ihlal hâlinde istisna fırlatır."""
    report = freshness(timeframe, symbols, root, now_ms, limit_bars)
    if not report.ok:
        raise StaleDataError(str(report))
    return report


class StaleDataError(RuntimeError):
    """Veri bayat — ingest sessizce bozulmuş olabilir."""
