"""Gölge dağılım — zaman-eşleştirmeli kontrol grubu (K-12).

Kripto piyasasında long yönlü her test doğal bir bias taşır. Daha kötüsü: bir
formasyon tarihte 100 kez bulunduysa ve 60'ı Mart 2021'de kümelendiyse,
tüm-geçmiş baseline'ıyla kıyaslamak **sahte bir edge** üretir — ölçtüğünüz şey
formasyonun başarısı değil, piyasanın o dönemdeki başarısıdır.

Çözüm: her eşleşme için **aynı aydan**, **farklı sembollerden**, aynı likidite
filtresini geçen P rastgele pencere. Kontrol grubunun zaman dağılımı,
eşleşmelerin zaman dağılımını birebir taklit eder.

⚠️ **Gölgeye de ileri pencere ayrımı uygulanır.** Aynı sembolde çekilen gölge
pencerelerin ``T``-barlık ileri ufukları kesişirse null dağılımı kendi içinde
otokorelasyonlu olur → gölgenin varyansı olduğundan küçük ölçülür → edge'in
güven aralığı sahte biçimde daralır → **anlamsız bir farkı anlamlı ilan
edersin**. Tekilleştirme tek bir eşleşmenin P'lisi içinde değil, **ay havuzu
genelinde** yapılır: farklı eşleşmelerin gölgeleri de birbirini tekrar edebilir.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from engine.config import SHADOW_SAMPLES_PER_MATCH, TIME_BARRIER_RATIO
from engine.matrix.liquidity import month_key
from engine.outcome.triple_barrier import EVENT_DTYPE, time_barrier


@dataclass
class ShadowPool:
    """Bir (timeframe, pencere uzunluğu) matrisinden türetilmiş aday havuzu."""

    symbol_id: np.ndarray
    end_idx: np.ndarray
    end_time: np.ndarray
    atr: np.ndarray
    month: np.ndarray
    length: int
    by_month: dict[int, np.ndarray]

    @classmethod
    def from_meta(cls, meta: np.ndarray, length: int, require_liquid: bool = True) -> "ShadowPool":
        mask = np.asarray(meta["liquid"]) if require_liquid else np.ones(meta.size, dtype=bool)
        mask = mask & np.isfinite(np.asarray(meta["atr"])) & (np.asarray(meta["atr"]) > 0)
        rows = np.flatnonzero(mask)

        month = month_key(np.asarray(meta["end_time"])[rows])

        # Ay → havuz satırları (filtrelenmiş dizilere indeks)
        order = np.argsort(month, kind="stable")
        boundaries = np.flatnonzero(np.diff(month[order])) + 1
        by_month = {int(month[g[0]]): g for g in np.split(order, boundaries) if g.size}

        return cls(
            symbol_id=np.asarray(meta["symbol_id"])[rows],
            end_idx=np.asarray(meta["end_idx"])[rows],
            end_time=np.asarray(meta["end_time"])[rows],
            atr=np.asarray(meta["atr"])[rows].astype(np.float64),
            month=month,
            length=length,
            by_month=by_month,
        )


def sample_shadow(
    events: np.ndarray,
    pools: dict[int, ShadowPool],
    p: int = SHADOW_SAMPLES_PER_MATCH,
    rng: np.random.Generator | None = None,
    ratio: float = TIME_BARRIER_RATIO,
) -> tuple[np.ndarray, dict]:
    """Eşleşmelerin zaman dağılımını taklit eden kontrol olayları üretir.

    Döner: ``(gölge olayları, rapor)``. Rapor, havuz yetersizliğinden dolayı
    ``P < 20``'ye düşülen eşleşme sayısını taşır — sessizce eksiltilmez.
    """
    rng = rng if rng is not None else np.random.default_rng(20260731)
    picked: list[tuple[int, int, int, int, float, int]] = []

    used: set[tuple[int, int]] = set()  # (symbol_id, end_idx) — havuz geneli
    last_by_symbol: dict[int, list[int]] = {}  # ileri pencere ayrımı için
    short_pools = 0

    for event in events:
        length = int(event["length"])
        pool = pools.get(length)
        if pool is None:
            short_pools += 1
            continue

        horizon = time_barrier(length, ratio)
        month = int(month_key(np.array([event["end_time"]]))[0])
        candidates = pool.by_month.get(month)
        if candidates is None or candidates.size == 0:
            short_pools += 1
            continue

        # Aynı sembol dışlanır: kontrol grubu "başka bir parite" olmalı.
        allowed = candidates[pool.symbol_id[candidates] != int(event["symbol_id"])]
        if allowed.size == 0:
            short_pools += 1
            continue

        rng.shuffle(allowed)
        taken = 0
        for row in allowed:
            if taken >= p:
                break
            sid = int(pool.symbol_id[row])
            end = int(pool.end_idx[row])
            if (sid, end) in used:
                continue
            # İleri pencere ayrımı — ay havuzu genelinde
            previous = last_by_symbol.setdefault(sid, [])
            if any(abs(end - q) < horizon for q in previous):
                continue

            used.add((sid, end))
            previous.append(end)
            picked.append((sid, end, length, int(pool.end_time[row]), float(pool.atr[row]), 0))
            taken += 1

        if taken < p:
            short_pools += 1

    out = np.empty(len(picked), dtype=EVENT_DTYPE)
    for i, (sid, end, length, end_time, atr, _) in enumerate(picked):
        out[i] = (sid, end, length, atr, end_time)

    report = {
        "requested_per_match": p,
        "matches": int(events.size),
        "shadow_events": int(out.size),
        "matches_with_short_pool": int(short_pools),
        "achieved_per_match": float(out.size / events.size) if events.size else 0.0,
    }
    return out, report
