"""``/api/health`` — deponun ve matrislerin durumu.

Tazelik burada **veriden** okunur, bir durum dosyasının "başarıyla bitti"
kaydından değil: F3'te indirme başarıyla bitip dosyalar yazılırken 19 aylık
veri sessizce yok olmuştu. Ölçüt her zaman depodaki en yeni bardır.
"""

from __future__ import annotations

from fastapi import APIRouter

from engine.api import freshness
from engine.api.schemas import HealthResponse
from engine.config import MATRIX_DIR, WINDOW_LENGTHS

router = APIRouter()


def _matrix_ready() -> bool:
    """En az bir (timeframe, length) matrisi diskte mi?"""
    if not MATRIX_DIR.exists():
        return False
    return any((MATRIX_DIR / f"{tf}_{length}").exists() for tf in ("4h", "1d") for length in WINDOW_LENGTHS)


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    timeframes = freshness.snapshot()
    newest = [tf["newest_open_time"] for tf in timeframes.values() if tf["newest_open_time"]]
    stale = any(not tf["ok"] for tf in timeframes.values()) or not timeframes

    return HealthResponse(
        status="ok",
        timeframes=timeframes,
        stale_warning=stale,
        data_as_of=max(newest) if newest else 0,
        matrix_ready=_matrix_ready(),
    )
