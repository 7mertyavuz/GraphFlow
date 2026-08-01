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

F4.6 EKLEMESİ: Ön-getiri eşleştirmeli gölge
---------------------------------------------
Yükselen takozun short'ta +0,331R edge'i şekilden mi yoksa momentum tersine
dönüşünden (vekil) mi kaynaklanıyor? Bunu ayırmak için gölge havuzuna "benzer
ön-getiri" kısıtı eklenir. Fallback zinciri (gölge tüketimi riski):
  1) Bandı genişlet (±0.25σ → ±0.50σ)
  2) Hâlâ yoksa ay kısıtını ±1 ay esnet
  3) Hâlâ yoksa uyarı ver
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from engine.config import (
    RETURN_MATCH_BAND_FALLBACK,
    RETURN_MATCH_BAND_SIGMA,
    RETURN_MATCH_MONTH_EXPAND,
    SHADOW_SAMPLES_PER_MATCH,
    TIME_BARRIER_RATIO,
)
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
    #: F4.6: pencere ön-getirisi (log return), vekil testi için.
    log_return: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.float64))
    #: F4.6: evren geneli ön-getiri standart sapması (σ).
    return_sigma: float = 1.0

    @classmethod
    def from_meta(
        cls,
        meta: np.ndarray,
        length: int,
        require_liquid: bool = True,
        klines_close: np.ndarray | None = None,
        klines_offsets: dict[int, int] | None = None,
    ) -> "ShadowPool":
        """Meta dizisinden gölge havuzu oluşturur.

        ``klines_close`` ve ``klines_offsets`` verilirse her pencere için
        ön-getiri (log return) hesaplanır — F4.6 vekil testi için gereklidir.
        """
        mask = np.asarray(meta["liquid"]) if require_liquid else np.ones(meta.size, dtype=bool)
        mask = mask & np.isfinite(np.asarray(meta["atr"])) & (np.asarray(meta["atr"]) > 0)
        rows = np.flatnonzero(mask)

        month = month_key(np.asarray(meta["end_time"])[rows])

        # Ay → havuz satırları (filtrelenmiş dizilere indeks)
        order = np.argsort(month, kind="stable")
        boundaries = np.flatnonzero(np.diff(month[order])) + 1
        by_month = {int(month[g[0]]): g for g in np.split(order, boundaries) if g.size}

        # F4.6: ön-getiri hesaplama
        log_return = np.zeros(rows.size, dtype=np.float64)
        return_sigma = 1.0
        if klines_close is not None and klines_offsets is not None:
            start_indices = np.asarray(meta["start_idx"])[rows]
            end_indices = np.asarray(meta["end_idx"])[rows]
            symbol_ids = np.asarray(meta["symbol_id"])[rows]
            for i in range(rows.size):
                sid = int(symbol_ids[i])
                if sid not in klines_offsets:
                    continue
                offset = klines_offsets[sid]
                s_idx = int(start_indices[i]) + offset
                e_idx = int(end_indices[i]) + offset
                if 0 <= s_idx < klines_close.size and 0 <= e_idx < klines_close.size:
                    c_start = klines_close[s_idx]
                    c_end = klines_close[e_idx]
                    if c_start > 0 and c_end > 0:
                        log_return[i] = float(np.log(c_end / c_start))
            sigma = float(np.std(log_return[np.isfinite(log_return)]))
            return_sigma = sigma if sigma > 1e-12 else 1.0

        return cls(
            symbol_id=np.asarray(meta["symbol_id"])[rows],
            end_idx=np.asarray(meta["end_idx"])[rows],
            end_time=np.asarray(meta["end_time"])[rows],
            atr=np.asarray(meta["atr"])[rows].astype(np.float64),
            month=month,
            length=length,
            by_month=by_month,
            log_return=log_return,
            return_sigma=return_sigma,
        )


def _adjacent_months(month: int, expand: int) -> list[int]:
    """Bir ay anahtarının ±expand komşularını döndürür.

    ``month_key`` çıktısı milisaniye cinsi ayın ilk gününe yuvarlanmış
    zaman damgasıdır. Ay aritmetiği için datetime64 kullanılır.
    """
    base = np.array([month], dtype="int64").astype("datetime64[ms]")
    result = []
    for delta in range(-expand, expand + 1):
        if delta == 0:
            continue
        shifted = (base.astype("datetime64[M]") + np.timedelta64(delta, "M")).astype("datetime64[ms]").astype("int64")
        result.append(int(shifted[0]))
    return result


def sample_shadow(
    events: np.ndarray,
    pools: dict[int, ShadowPool],
    p: int = SHADOW_SAMPLES_PER_MATCH,
    rng: np.random.Generator | None = None,
    ratio: float = TIME_BARRIER_RATIO,
    match_return: bool = False,
    return_band_sigma: float = RETURN_MATCH_BAND_SIGMA,
) -> tuple[np.ndarray, dict]:
    """Eşleşmelerin zaman dağılımını taklit eden kontrol olayları üretir.

    ``match_return=True`` ise F4.6 ön-getiri eşleştirmesi aktif edilir:
    gölge adayları, eşleşmenin ön-getirisi ±``return_band_sigma``×σ
    bandında olmalıdır. Çok katmanlı fallback zinciri:
      1) Band genişlet (→ ±RETURN_MATCH_BAND_FALLBACK×σ)
      2) Ay kısıtını ±RETURN_MATCH_MONTH_EXPAND esnet
      3) Yetersizse uyarı ver

    Döner: ``(gölge olayları, rapor)``. Rapor, havuz yetersizliğinden dolayı
    ``P < 20``'ye düşülen eşleşme sayısını taşır — sessizce eksiltilmez.
    """
    rng = rng if rng is not None else np.random.default_rng(20260731)
    picked: list[tuple[int, int, int, int, float, int]] = []

    used: set[tuple[int, int]] = set()  # (symbol_id, end_idx) — havuz geneli
    last_by_symbol: dict[int, list[int]] = {}  # ileri pencere ayrımı için
    short_pools = 0
    fallback_band_count = 0
    fallback_month_count = 0

    for event in events:
        length = int(event["length"])
        pool = pools.get(length)
        if pool is None:
            short_pools += 1
            continue

        horizon = time_barrier(length, ratio)
        month = int(month_key(np.array([event["end_time"]]))[0])
        event_sid = int(event["symbol_id"])

        # Eşleşmenin ön-getirisi (F4.6)
        event_return: float | None = None
        if match_return and pool.log_return.size > 0:
            # Eşleşmenin kendisinin ön-getirisini meta'dan al
            # Meta'da end_idx ve symbol_id ile eşleştir
            mask = (pool.symbol_id == event_sid) & (pool.end_idx == int(event["t0"]))
            if mask.any():
                event_return = float(pool.log_return[np.flatnonzero(mask)[0]])
            else:
                # Eşleşme havuzda yoksa (farklı filtre), kaba tahmin
                event_return = None

        taken = 0
        # Çok katmanlı fallback zinciri
        used_fallback_band = False
        used_fallback_month = False

        for attempt, (band_sigma, month_expand) in enumerate(_fallback_chain(return_band_sigma)):
            if taken >= p:
                break

            # Hangi aylardan aday çekilecek
            months_to_try = [month]
            if month_expand > 0:
                months_to_try.extend(_adjacent_months(month, month_expand))

            for m in months_to_try:
                if taken >= p:
                    break
                candidates = pool.by_month.get(m)
                if candidates is None or candidates.size == 0:
                    continue

                # Aynı sembol dışlanır: kontrol grubu "başka bir parite" olmalı.
                allowed = candidates[pool.symbol_id[candidates] != event_sid]
                if allowed.size == 0:
                    continue

                # F4.6: ön-getiri bandı filtresi
                if match_return and event_return is not None and pool.log_return.size > 0:
                    returns = pool.log_return[allowed]
                    band = band_sigma * pool.return_sigma
                    in_band = np.abs(returns - event_return) <= band
                    allowed = allowed[in_band]
                    if allowed.size == 0:
                        continue

                rng.shuffle(allowed)
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

            if attempt == 1 and taken > 0:
                used_fallback_band = True
            if attempt >= 2 and taken > 0:
                used_fallback_month = True

        if taken < p:
            short_pools += 1
        if used_fallback_band:
            fallback_band_count += 1
        if used_fallback_month:
            fallback_month_count += 1

    out = np.empty(len(picked), dtype=EVENT_DTYPE)
    for i, (sid, end, length, end_time, atr, _) in enumerate(picked):
        out[i] = (sid, end, length, atr, end_time)

    report = {
        "requested_per_match": p,
        "matches": int(events.size),
        "shadow_events": int(out.size),
        "matches_with_short_pool": int(short_pools),
        "achieved_per_match": float(out.size / events.size) if events.size else 0.0,
        "return_matched": match_return,
    }
    if match_return:
        report["return_band_sigma"] = return_band_sigma
        report["fallback_band_widened"] = fallback_band_count
        report["fallback_month_expanded"] = fallback_month_count

    return out, report


def _fallback_chain(
    initial_band: float,
) -> list[tuple[float, int]]:
    """Çok katmanlı fallback zinciri üretir.

    Döner: [(band_sigma, month_expand), ...] sıralı deneme listesi.
    Her adımda bir kısıt gevşetilir — ikisi aynı anda değil.
    """
    return [
        (initial_band, 0),                      # 1) Orijinal kısıtlar
        (RETURN_MATCH_BAND_FALLBACK, 0),         # 2) Band genişlet
        (RETURN_MATCH_BAND_FALLBACK, RETURN_MATCH_MONTH_EXPAND),  # 3) Ay da esnet
    ]
