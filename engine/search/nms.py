"""1D Non-Maximum Suppression — K-09, docs/01-mimari.md §5.2 / §5.4.

Stride 1–3 ile kayan pencerelerde komşu pencereler z-score sonrası birbirinin
%99 aynısıdır. Dedupe edilmezse:

* kullanıcı 12 kutuda **aynı grafiği** görür (planın en büyük gizli hatasıydı),
* Aşama 2'nin bütçesi ~50 farklı olayın 20'şer kopyasına harcanır.

Bu yüzden **iki geçiş** vardır ve ikisi de aynı fonksiyonu kullanır:

| Geçiş | IoU | max/sembol | Amaç |
|---|---|---|---|
| Pre-NMS  | 0,70 (gevşek) | — | DDTW'ye giden havuzu çeşitlendirmek |
| Post-NMS | 0,50 (katı)   | 3 | Kullanıcıya gidecek listeyi temizlemek |

Tek geçiş yeterli değildir: yalnız başta yapılırsa kaba (kosinüs) skorla
eleme yapılmış olur, yalnız sonda yapılırsa Aşama 2 bütçesi yanar.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np


def iou_1d(a_start: int, a_end: int, b_start: int, b_end: int) -> float:
    """docs/01-mimari.md §5.2'deki formül. Aynı sembol/timeframe varsayılır."""
    inter = min(a_end, b_end) - max(a_start, b_start)
    if inter <= 0:
        return 0.0
    union = (a_end - a_start) + (b_end - b_start) - inter
    return inter / union if union > 0 else 0.0


def nms_1d(
    candidates: np.ndarray,
    iou_threshold: float,
    max_per_symbol: int | None = None,
    score_field: str = "score",
    higher_is_better: bool = True,
) -> np.ndarray:
    """Örtüşen pencereleri tekilleştirir; **korunan adayların indekslerini** döner.

    ``candidates`` yapılandırılmış bir dizidir; en az ``symbol_id``,
    ``start_idx``, ``end_idx`` ve ``score_field`` alanlarını taşımalıdır.

    Pre ve post geçişleri aynı fonksiyondur — tek fark eşikler ve
    ``max_per_symbol``. Post-NMS DDTW **mesafesi** ile çağrıldığında
    ``higher_is_better=False`` verilir (küçük mesafe = iyi eşleşme).

    Dönen indeksler skora göre sıralıdır (en iyiden kötüye).
    """
    n = len(candidates)
    if n == 0:
        return np.empty(0, dtype=np.int64)

    scores = np.asarray(candidates[score_field], dtype=np.float64)
    order = np.argsort(-scores if higher_is_better else scores, kind="stable")

    symbol_id = np.asarray(candidates["symbol_id"])
    start = np.asarray(candidates["start_idx"])
    end = np.asarray(candidates["end_idx"])

    kept: list[int] = []
    kept_by_symbol: dict[int, list[int]] = defaultdict(list)

    for i in order:
        sid = int(symbol_id[i])
        bucket = kept_by_symbol[sid]

        if max_per_symbol is not None and len(bucket) >= max_per_symbol:
            continue
        # Karşılaştırma yalnızca aynı sembol içinde anlamlıdır.
        if any(iou_1d(start[i], end[i], start[j], end[j]) >= iou_threshold for j in bucket):
            continue

        bucket.append(int(i))
        kept.append(int(i))

    return np.asarray(kept, dtype=np.int64)
