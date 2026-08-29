"""Eşleşmelerin bar bazında ince ayarı — stride 3'ün bedelini geri alır.

Matris ``STRIDE = 3`` ile kurulur (K-01): 12M pencerelik hedefte stride 1
belleği üçe katlar. Bunun bir bedeli vardır ve ``tools/verify_stage1`` onu
**ölçtü**: kaba kuvvet (stride 1) ile matrisin bulduğu en iyi pencere
arasında kosinüs farkı ortalama **+0,021**, %95 **+0,074**, en kötü
**+0,096**.

Gerçek aramalarda ilk sonuçlar r ≈ 0,93 bandında geliyor; yani 1–2 bar ötede
duran r ≈ 0,99'luk bir pencere kullanıcıya hiç gösterilmemiş olabiliyor.
Kullanıcının *"çizdiğime tam benzemiyor"* dediği şey büyük ölçüde budur:
motor doğru formasyonu buluyor ama **yanlış hizada** gösteriyor.

Çözüm STRIDE'ı değiştirmek değil — o karar gerekçesiyle alınmış ve tüm
matris/eşik kalibrasyonu ona bağlı. Bunun yerine yalnızca **gösterilecek**
eşleşmeler, ±(STRIDE−1) bar penceresinde yeniden taranır ve en iyi hizaya
oturtulur. Kapsanan offset kümesi stride ızgarasındaki boşluğun tamamıdır,
yani kaçırılan hizalama kalmaz.

**Aynı invariant'lar burada da geçerlidir.** Kaydırılan pencere zaman
sürekliliğini (boşluksuz bar) veya fiyat sürekliliğini (redenominasyon)
ihlal ediyorsa o offset elenir — aksi hâlde ince ayar, matrisin bilerek
dışarıda bıraktığı pencereleri arka kapıdan içeri alırdı.
"""

from __future__ import annotations

import numpy as np

from engine.config import (
    ATR_PERIOD,
    N_POINTS,
    PRICE_CONTINUITY_MAX_RATIO,
    SAKOE_CHIBA_RADIUS,
    STAGE2_METRIC,
    STRIDE,
    TIMEFRAME_MS,
)
from engine.normalize.amplitude import amplitude_batch
from engine.normalize.atr import wilder_atr
from engine.normalize.pipeline import normalize_batch
from engine.search.ddtw import stage2_scores


class _AtrCache:
    """Sembol başına Wilder ATR — kaydırılan pencerenin ATR'si de kayar.

    Eski ATR'yi taşımak sessiz bir hata olurdu: bariyerler (K-16) formasyonun
    bittiği barın ATR'sinden türetilir, pencere kayarsa o bar da değişir.
    """

    def __init__(self, store) -> None:
        self._store = store
        self._cache: dict[int, np.ndarray] = {}

    def of(self, symbol_id: int) -> np.ndarray:
        sid = int(symbol_id)
        hit = self._cache.get(sid)
        if hit is None:
            off, n = self._store.offset[sid], self._store.n_bars[sid]
            hit = wilder_atr(
                self._store.high[off : off + n],
                self._store.low[off : off + n],
                self._store.close[off : off + n],
                ATR_PERIOD,
            )
            self._cache[sid] = hit
        return hit


def _candidate_starts(start: int, length: int, n_bars: int, radius: int) -> np.ndarray:
    lo = max(0, start - radius)
    hi = min(n_bars - length, start + radius)
    if hi < lo:
        return np.empty(0, dtype=np.int64)
    return np.arange(lo, hi + 1, dtype=np.int64)


def refine_matches(
    matches,
    store,
    query: np.ndarray,
    timeframe: str,
    null_dist: dict[int, np.ndarray] | None = None,
    radius: int = STRIDE - 1,
    metric: str = STAGE2_METRIC,
    sakoe_radius: int = SAKOE_CHIBA_RADIUS,
):
    """Eşleşmeleri en iyi bar hizasına oturtur; yüzdeliğe göre yeniden sıralar.

    ``null_dist`` verilirse yüzdelik dilim yeniden hesaplanır (sıralama buna
    göredir, K-14/F3.5). Verilmezse mesafeler güncellenir ama sıralama
    korunur — yanlış bir yüzdelik yazmaktansa eskisini taşımak yeğdir.
    """
    if not matches:
        return list(matches)

    q = np.asarray(query, dtype=np.float64)
    atr_cache = _AtrCache(store)
    step_ms = TIMEFRAME_MS.get(timeframe, TIMEFRAME_MS["4h"])
    out = []

    for m in matches:
        sid = int(m.symbol_id)
        if not store.has(sid):
            out.append(m)
            continue

        off, n_bars = store.offset[sid], store.n_bars[sid]
        length = int(m.window_length)
        starts = _candidate_starts(int(m.start_idx), length, n_bars, radius)
        if starts.size == 0:
            out.append(m)
            continue

        idx = off + starts[:, None] + np.arange(length, dtype=np.int64)[None, :]
        raw = store.close[idx]
        times = store.open_time[idx]

        vectors, valid = normalize_batch(raw, N_POINTS)

        # Zaman sürekliliği: pencere gerçekten `length` bar mı kapsıyor?
        valid &= (times[:, -1] - times[:, 0]) == (length - 1) * step_ms

        # Fiyat sürekliliği: pencere içinde redenominasyon sıçraması olmamalı.
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = np.maximum(raw[:, 1:] / raw[:, :-1], raw[:, :-1] / raw[:, 1:])
        valid &= ~(~np.isfinite(ratio) | (ratio > PRICE_CONTINUITY_MAX_RATIO)).any(axis=1)

        if not valid.any():
            out.append(m)
            continue

        keep = np.flatnonzero(valid)
        distances = stage2_scores(q, vectors[keep], sakoe_radius, metric)
        best = int(keep[int(np.argmin(distances))])
        best_distance = float(distances[int(np.argmin(distances))])

        # İnce ayar yalnızca İYİLEŞTİRİR: mevcut hizayı da aday kümesine
        # aldık, dolayısıyla kötüleşme ancak sayısal gürültüyle olabilir.
        if best_distance >= float(m.distance):
            out.append(m)
            continue

        new_start = int(starts[best])
        new_end = new_start + length - 1
        atr = atr_cache.of(sid)
        vector = np.asarray(vectors[best], dtype=np.float64)

        percentile = m.percentile
        null = None if null_dist is None else null_dist.get(length)
        if null is not None and null.size:
            percentile = float(np.searchsorted(null, best_distance, side="left") / null.size)

        out.append(
            type(m)(
                symbol=m.symbol,
                symbol_id=m.symbol_id,
                timeframe=m.timeframe,
                window_length=length,
                start_idx=new_start,
                end_idx=new_end,
                end_time=int(store.open_time[off + new_end]),
                score=float(vector @ q / N_POINTS),
                distance=best_distance,
                amplitude=float(amplitude_batch(raw[best : best + 1])[0]),
                atr=float(np.nan_to_num(atr[new_end], nan=0.0)),
                percentile=percentile,
                row=m.row,
                dtw_path=None,  # hiza değişti: eski yol artık geçersiz
            )
        )

    if null_dist is not None:
        out.sort(key=lambda x: (x.percentile, x.distance))
    return out
