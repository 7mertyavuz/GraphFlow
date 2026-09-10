"""Oturum sayacı — çoklu karşılaştırma muhasebesi (K-12).

Kullanıcı arka arkaya 20 şekil denerse %95 güvenle ~1 tanesinin şans eseri
"anlamlı" çıkması beklenir. Sayaç bunu görünür kılar: α, denenen şekil
sayısına bölünerek (Bonferroni) raporlanır.

**Yalnızca yeni arama sayılır.** Sayfalama ve istatistik çağrıları sayacı
artırmaz; "Daha fazla" tuşuna basmak yeni bir hipotez testi değildir.

**Ve yalnızca AYRI hipotez sayılır.** Aynı şekli aynı parametrelerle yeniden
sormak (kullanıcı tekrar tıkladı, Radar kendini yeniledi) yeni bir test
değildir. Sayaç isteği değil hipotezi sayar: aksi hâlde açık bırakılmış bir
Radar sekmesi, kullanıcı hiçbir şey denemeden α'yı zamanla küçültürdü ve
uyarı anlamsızlaşırdı.
"""

from __future__ import annotations

import uuid
from typing import Final

from fastapi import Header

from engine.api.cache import get_cache
from engine.api.schemas import SessionInfo

SESSION_TTL: Final[int] = 3600
BASE_ALPHA: Final[float] = 0.05

#: Bu sayıdan itibaren çoklu karşılaştırma uyarısı gösterilir.
WARN_AFTER_QUERIES: Final[int] = 2


async def get_session_id(x_session_id: str | None = Header(default=None)) -> str:
    if x_session_id is not None:
        return x_session_id
    return str(uuid.uuid4())


def _key(session_id: str) -> str:
    return f"session:{session_id}:queries"


def _envelope(queries: int) -> SessionInfo:
    queries = max(1, queries)
    return SessionInfo(
        session_queries=queries,
        multiple_comparison_warning=queries >= WARN_AFTER_QUERIES,
        adjusted_alpha=BASE_ALPHA / queries,
        warning_text=get_warning_text(queries),
    )


def _seen_key(session_id: str, fingerprint: str) -> str:
    return f"session:{session_id}:seen:{fingerprint}"


async def track_session(session_id: str, fingerprint: str | None = None) -> SessionInfo:
    """Yeni bir **hipotezi** sayar ve güncel zarfı döner.

    ``fingerprint`` verilirse aynı parmak izi ikinci kez geldiğinde sayaç
    artmaz — Bonferroni ailesi denenen ayrı şekil sayısıdır, gönderilen
    istek sayısı değil.
    """
    cache = get_cache()
    if fingerprint is not None:
        seen = _seen_key(session_id, fingerprint)
        if await cache.get(seen):
            return await read_session(session_id)
        await cache.set(seen, b"1", SESSION_TTL)

    # incr ilk çağrıda 1 döner ve TTL penceresini başlatır
    queries = await cache.incr(_key(session_id), SESSION_TTL)
    return _envelope(queries)


async def read_session(session_id: str) -> SessionInfo:
    """Sayacı **artırmadan** okur (sayfalama, istatistik)."""
    cache = get_cache()
    return _envelope(await cache.count(_key(session_id)))


def get_warning_text(queries: int) -> str | None:
    if queries < WARN_AFTER_QUERIES:
        return None
    return (
        f"Bu oturumda {queries} farklı şekil denendi. Bonferroni düzeltilmiş "
        f"anlamlılık eşiği α = {BASE_ALPHA / queries:.4f}; bu eşiği geçmeyen "
        "bulgular şans eseri ortaya çıkmış olabilir."
    )
