"""Normalizasyon pipeline'ı — docs/01-mimari.md §3, K-02.

**Sıra önemlidir:**

1. ``x = log(p)``           — piyasada anlamlı olan yüzdesel değişimdir;
   log uzayında eşit dikey mesafe = eşit yüzdesel hareket
2. ``resample(x, 32)``      — farklı uzunluktaki pencereleri tek vektör
   uzayında kıyaslayabilmek için (``np.interp``, lineer)
3. ``z = (x - mu) / sigma`` — şeklin kimliğini fiyat seviyesinden ve hareket
   büyüklüğünden ayrıştırır; geriye saf geometrik form kalır

``sigma < FLAT_EPS`` (düz pencere) → pencere veri setinden **düşürülür**.

Sonuç vektörlerinin normu sabittir: ``‖z‖ = √32``. Aşama 1'deki
``(V @ q) / 32`` bu yüzden Pearson korelasyonuna eşittir (K-03).

Kullanıcı çizimi için ``normalize_drawing()``: y ekseni ters çevrilir
(kanvasta y aşağı doğru artar), **log adımı uygulanmaz** — çizim zaten
lineer/görsel uzaydadır ve z-score sonrası fark ortadan kalkar.
"""

from __future__ import annotations

import numpy as np

from engine.config import FLAT_EPS, N_POINTS


def resample_to(x: np.ndarray, n: int = N_POINTS) -> np.ndarray:
    """(L,) diziyi lineer interpolasyonla n noktaya indirger/yükseltir."""
    x = np.asarray(x, dtype=np.float64)
    if x.ndim != 1:
        raise ValueError("resample_to tek boyutlu dizi bekler")
    if x.size == n:
        return x.copy()
    if x.size < 2:
        return np.full(n, float(x[0]) if x.size else np.nan)
    src = np.linspace(0.0, 1.0, x.size)
    dst = np.linspace(0.0, 1.0, n)
    return np.interp(dst, src, x)


def _resample_batch(windows: np.ndarray, n: int = N_POINTS) -> np.ndarray:
    """(m, L) → (m, n). Kaynak ızgara tüm satırlarda aynı olduğu için
    interpolasyon ağırlıkları bir kez hesaplanır — döngü yok."""
    m, L = windows.shape
    if L == n:
        return windows.astype(np.float64, copy=True)
    if L < 2:
        return np.repeat(windows.astype(np.float64), n, axis=1)

    # dst noktalarının kaynak ızgaradaki kesirli konumu
    pos = np.linspace(0.0, 1.0, n) * (L - 1)
    i0 = np.floor(pos).astype(np.intp)
    np.clip(i0, 0, L - 2, out=i0)
    i1 = i0 + 1
    w = (pos - i0)[None, :]

    return windows[:, i0] * (1.0 - w) + windows[:, i1] * w


def zscore(x: np.ndarray) -> np.ndarray | None:
    """Popülasyon z-score'u (ddof=0). Düz pencerede None döner."""
    x = np.asarray(x, dtype=np.float64)
    sigma = x.std()
    if sigma < FLAT_EPS:
        return None
    return (x - x.mean()) / sigma


def normalize_window(prices: np.ndarray, n: int = N_POINTS) -> np.ndarray | None:
    """Ham kapanış fiyatları → (n,) normalize şekil vektörü.

    Düz pencere (sigma < FLAT_EPS) veya geçersiz fiyat varsa None.
    """
    p = np.asarray(prices, dtype=np.float64)
    if p.size == 0 or not np.all(np.isfinite(p)) or np.any(p <= 0.0):
        return None

    x = np.log(p)  # 1. log fiyat
    x32 = resample_to(x, n)  # 2. resample
    return zscore(x32)  # 3. z-score


def normalize_batch(
    windows: np.ndarray, n: int = N_POINTS, apply_log: bool = True
) -> tuple[np.ndarray, np.ndarray]:
    """Vektörize toplu normalizasyon.

    Girdi: (m, L) ham fiyat pencereleri (tüm satırlar aynı uzunlukta).
    Çıktı: ``(vectors (m, n) float32, valid (m,) bool)``.

    Geçersiz satırlar (düz pencere, fiyat <= 0, NaN) ``valid=False`` ile
    işaretlenir; vektör içerikleri o satırlarda tanımsızdır. Çağıran taraf
    maskeyle filtreler — böylece bellek tek seferde ayrılır ve döngü olmaz.
    """
    w = np.asarray(windows, dtype=np.float64)
    if w.ndim == 1:
        w = w[None, :]
    m = w.shape[0]

    valid = np.isfinite(w).all(axis=1)
    if apply_log:
        valid &= (w > 0.0).all(axis=1)
        x = np.log(np.where(valid[:, None], w, 1.0))
    else:
        x = np.where(valid[:, None], w, 0.0)

    x32 = _resample_batch(x, n)

    mu = x32.mean(axis=1, keepdims=True)
    sigma = x32.std(axis=1, keepdims=True)
    valid &= sigma[:, 0] >= FLAT_EPS

    safe_sigma = np.where(sigma < FLAT_EPS, 1.0, sigma)
    z = (x32 - mu) / safe_sigma

    out = np.ascontiguousarray(z, dtype=np.float32)
    assert out.shape == (m, n)
    return out, valid


def normalize_drawing(points, n: int = N_POINTS, invert_y: bool = True) -> np.ndarray | None:
    """Kanvas noktaları → (n,) normalize vektör.

    * ``points`` (k, 2) ise x sütunu örnekleme ızgarası olarak kullanılır
      (kullanıcı hızlı/yavaş çizdiğinde noktalar düzgün dağılmaz).
    * ``points`` (k,) ise noktalar eşit aralıklı varsayılır.
    * ``invert_y``: kanvasta y aşağı doğru arttığı için ters çevrilir.
    * **Log adımı uygulanmaz** (docs/01-mimari.md §3) — çizim lineer uzayda.
    """
    arr = np.asarray(points, dtype=np.float64)

    if arr.ndim == 2 and arr.shape[1] == 2:
        xs, ys = arr[:, 0], arr[:, 1]
        order = np.argsort(xs, kind="stable")
        xs, ys = xs[order], ys[order]
        if invert_y:
            ys = -ys
        span = xs[-1] - xs[0]
        if span <= 0:
            return None
        dst = np.linspace(xs[0], xs[-1], n)
        y32 = np.interp(dst, xs, ys)
    elif arr.ndim == 1:
        ys = -arr if invert_y else arr
        y32 = resample_to(ys, n)
    else:
        raise ValueError("normalize_drawing (k,) veya (k, 2) bekler")

    if not np.all(np.isfinite(y32)):
        return None
    return zscore(y32)
