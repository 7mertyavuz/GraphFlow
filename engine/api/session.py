from __future__ import annotations

import uuid
from typing import Final

from fastapi import Header, Request
from engine.api.cache import get_cache
from engine.api.schemas import SessionInfo

SESSION_TTL: Final[int] = 3600
BASE_ALPHA: Final[float] = 0.05


async def get_session_id(x_session_id: str | None = Header(default=None)) -> str:
    if x_session_id is not None:
        return x_session_id
    return str(uuid.uuid4())


async def track_session(session_id: str) -> SessionInfo:
    cache = get_cache()
    key = f"session:{session_id}:queries"
    
    # incr will initialize to 1 if it doesn't exist
    queries = await cache.incr(key)
    
    adjusted_alpha = BASE_ALPHA / max(1, queries)
    warning = queries > 1
    
    return SessionInfo(
        session_queries=queries,
        multiple_comparison_warning=warning,
        adjusted_alpha=adjusted_alpha
    )

def get_warning_text(queries: int) -> str | None:
    if queries <= 1:
        return None
    return f"Bu oturumda {queries} farklı şekil denediniz; şans eseri 'anlamlı' sonuç görme olasılığınız arttı."
