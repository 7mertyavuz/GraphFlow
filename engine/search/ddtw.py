"""Aşama 2 — DDTW: türev DTW + Sakoe-Chiba bandı (K-11, docs §5.3).

**Neden ham DTW değil:** Klasik DTW'nin bilinen hastalığı *singularity*'dir —
tek bir nokta karşı serideki 15 noktaya hizalanabilir. Pratik sonucu, düz
yatay bir çizginin çanak formasyonuyla yüksek skorla eşleşmesidir. Bir şekil
arama motoru için bu ölümcüldür; Sakoe-Chiba bandı azaltır ama çözmez.

Çözüm, noktaların mutlak değerleri yerine **yerel eğimlerini** hizalamaktır
(Keogh & Pazzani):

    D[i] = ( (x[i] − x[i−1]) + (x[i+1] − x[i−1]) / 2 ) / 2,   1 ≤ i ≤ N−2

**Vektörizasyon:** Aday listesi üzerinde Python döngüsü yoktur. Dinamik
programlama tüm adaylar üzerinde aynı anda, ``(n_cand, band)`` şeklinde
yürütülür: dış döngüler yalnızca satır (30) ve band (2r+1 = 11) üzerindedir;
her adım tüm adayları kapsayan bir NumPy vektör işlemidir.

**Skor normalizasyonu (K-14):** ``normal_score = dtw_distance / path_length``.
Bu bölme olmadan farklı uzunluktaki pencerelerden gelen mesafeler
kıyaslanamaz ve 24 barlık pencereler 100 barlıkları sistematik olarak ezer.

``dtw_scores`` (ham DTW) yalnızca doğrulama ve kıyas içindir; üretim yolu
daima DDTW'dir.
"""

from __future__ import annotations

import numpy as np

from engine.config import SAKOE_CHIBA_RADIUS


def derivative(x: np.ndarray) -> np.ndarray:
    """Keogh-Pazzani türev tahmini. (N,) → (N-2,)."""
    x = np.asarray(x, dtype=np.float64)
    if x.ndim != 1:
        raise ValueError("derivative tek boyutlu dizi bekler")
    return derivative_batch(x[None, :])[0]


def derivative_batch(X: np.ndarray) -> np.ndarray:
    """(n, N) → (n, N-2). Tek noktalı farktan daha gürültü-dayanıklıdır."""
    X = np.asarray(X, dtype=np.float64)
    if X.ndim != 2:
        raise ValueError("derivative_batch iki boyutlu dizi bekler")
    if X.shape[1] < 3:
        raise ValueError("türev için en az 3 nokta gerekir")

    left = X[:, 1:-1] - X[:, :-2]  # x[i] - x[i-1]
    span = (X[:, 2:] - X[:, :-2]) / 2.0  # (x[i+1] - x[i-1]) / 2
    return (left + span) / 2.0


def banded_dtw_batch(
    query: np.ndarray,
    candidates: np.ndarray,
    radius: int = SAKOE_CHIBA_RADIUS,
) -> tuple[np.ndarray, np.ndarray]:
    """Tüm adaylara karşı banded DTW — tek Python döngüsü satır/band üzerinde.

    Girdi: ``query (m,)``, ``candidates (n, m)``. Mesafe metriği kare Öklid.
    Çıktı: ``(distance (n,), path_length (n,))``.
    """
    q = np.asarray(query, dtype=np.float64)
    C = np.asarray(candidates, dtype=np.float64)
    if C.ndim == 1:
        C = C[None, :]
    m = q.size
    if C.shape[1] != m:
        raise ValueError(f"aday uzunluğu {C.shape[1]}, sorgu {m}")

    n = C.shape[0]
    r = int(min(max(1, radius), m - 1))
    width = 2 * r + 1

    inf = np.inf
    # Son sütun sentinel: band dışına taşan prev[k+1] okumaları için.
    cur = np.full((n, width + 1), inf)
    cur_len = np.zeros((n, width + 1), dtype=np.int32)
    prev = np.full((n, width + 1), inf)
    prev_len = np.zeros((n, width + 1), dtype=np.int32)

    # --- i = 0 satırı: yalnızca soldan gelinebilir -------------------------
    for k in range(width):
        j = k - r
        if j < 0 or j >= m:
            continue
        cost = (q[0] - C[:, j]) ** 2
        if j == 0:
            cur[:, k] = cost
            cur_len[:, k] = 1
        else:
            cur[:, k] = cur[:, k - 1] + cost
            cur_len[:, k] = cur_len[:, k - 1] + 1

    # --- i >= 1 ------------------------------------------------------------
    options = np.empty((3, n), dtype=np.float64)
    lengths = np.empty((3, n), dtype=np.int32)

    for i in range(1, m):
        prev, cur = cur, prev
        prev_len, cur_len = cur_len, prev_len
        cur.fill(inf)
        cur_len.fill(0)

        for k in range(width):
            j = i - r + k
            if j < 0 or j >= m:
                continue

            options[0] = prev[:, k + 1]  # D[i-1, j]
            options[1] = prev[:, k]  # D[i-1, j-1]
            options[2] = cur[:, k - 1] if k > 0 else inf  # D[i, j-1]
            lengths[0] = prev_len[:, k + 1]
            lengths[1] = prev_len[:, k]
            lengths[2] = cur_len[:, k - 1] if k > 0 else 0

            best = np.argmin(options, axis=0)
            base = np.take_along_axis(options, best[None, :], axis=0)[0]
            base_len = np.take_along_axis(lengths, best[None, :], axis=0)[0]

            reachable = np.isfinite(base)
            cost = (q[i] - C[:, j]) ** 2
            cur[:, k] = np.where(reachable, base + cost, inf)
            cur_len[:, k] = np.where(reachable, base_len + 1, 0)

    # Bitiş hücresi: i = j = m-1 → k = r
    distance = cur[:, r].copy()
    path_length = cur_len[:, r].astype(np.float64)
    return distance, path_length


def normalized_scores(
    query: np.ndarray,
    candidates: np.ndarray,
    radius: int = SAKOE_CHIBA_RADIUS,
    use_derivative: bool = True,
) -> np.ndarray:
    """``dtw_distance / path_length`` (K-14). Küçük = benzer."""
    if use_derivative:
        q = derivative(query)
        C = derivative_batch(np.atleast_2d(candidates))
    else:
        q = np.asarray(query, dtype=np.float64)
        C = np.atleast_2d(np.asarray(candidates, dtype=np.float64))

    distance, path_length = banded_dtw_batch(q, C, radius)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(path_length > 0, distance / path_length, np.inf)


def ddtw_scores(query: np.ndarray, candidates: np.ndarray, radius: int = SAKOE_CHIBA_RADIUS) -> np.ndarray:
    """Üretim yolu: türev DTW, yol uzunluğuna normalize (K-11 + K-14)."""
    return normalized_scores(query, candidates, radius, use_derivative=True)


def dtw_scores(query: np.ndarray, candidates: np.ndarray, radius: int = SAKOE_CHIBA_RADIUS) -> np.ndarray:
    """Ham DTW — **yalnızca doğrulama/kıyas için** (K-11'in kanıtı)."""
    return normalized_scores(query, candidates, radius, use_derivative=False)
