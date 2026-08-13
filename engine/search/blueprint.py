"""Blueprint katmanları — "aradığın şey" ile "motorun hizaladığı şey" (F3.5).

Göz testinin (ve F6 arayüzündeki her karonun) iki katmanı vardır:

* **Kanonik** — sorgunun kendisi: *aradığın şey*
* **Bükülmüş** — DTW hizalama yoluyla eşleşmeye oturtulmuş sorgu:
  *motor bunu buna hizaladı*

İkisi ayrışıyorsa eşleşme ağır zaman bükmesiyle kurulmuştur; kullanıcı bunu
skora bakarak değil, **görerek** anlamalıdır. Bu yüzden katmanlar notebook'a
özel bir çizim yardımcısı değil, motorun parçasıdır: arayüz ile göz testi
aynı geometriyi gösterir.
"""

from __future__ import annotations

import numpy as np

from engine.config import SAKOE_CHIBA_RADIUS
from engine.search.ddtw import warp_amount, warping_path


def warped_query(query: np.ndarray, path: np.ndarray) -> np.ndarray:
    """Sorguyu hizalama yolu boyunca adayın zaman eksenine taşır.

    Yol **türev uzayında** kurulduğu için indeksler bir kayıktır
    (``D[i] ↔ x[i+1]``); uçlar sorgunun kendi uçlarıyla sabitlenir ve yolun
    atladığı noktalar doğrusal doldurulur.
    """
    q = np.asarray(query, dtype=np.float64)
    out = np.full(q.size, np.nan)

    for qi, cj in np.asarray(path, dtype=np.int64):
        if 0 <= cj + 1 < q.size and 0 <= qi + 1 < q.size:
            out[cj + 1] = q[qi + 1]
    out[0], out[-1] = q[0], q[-1]

    missing = np.isnan(out)
    if missing.all():
        return q.copy()
    if missing.any():
        idx = np.arange(q.size)
        out[missing] = np.interp(idx[missing], idx[~missing], out[~missing])
    return out


def blueprint_layers(
    query: np.ndarray,
    candidate: np.ndarray,
    radius: int = SAKOE_CHIBA_RADIUS,
    path: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, float]:
    """``(kanonik, bükülmüş, bükülme_miktarı)``.

    ``path`` verilirse yeniden hesaplanmaz — API'de yol zaten arama anında
    üretilip önbelleğe alınmıştır.
    """
    q = np.asarray(query, dtype=np.float64)
    if path is None:
        path = warping_path(q, np.asarray(candidate, dtype=np.float64), radius=radius)
    path = np.asarray(path, dtype=np.int64).reshape(-1, 2)
    if path.size == 0:
        return q, q.copy(), 0.0
    return q, warped_query(q, path), warp_amount(path)
