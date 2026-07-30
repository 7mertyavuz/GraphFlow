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

from engine.config import SAKOE_CHIBA_RADIUS, STAGE2_METRIC


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
    # Hücre başına yalnızca bir argmin + iki fancy-index; ``take_along_axis``
    # bu iç döngüde çağrı başına ağır kaldığı için kullanılmaz.
    options = np.empty((3, n), dtype=np.float64)
    lengths = np.empty((3, n), dtype=np.int32)
    cols = np.arange(n)

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
            # inf + sonlu = inf olduğu için ulaşılamaz hücreler kendiliğinden
            # inf kalır; yol uzunluğu yalnızca sonda temizlenir.
            cur[:, k] = options[best, cols] + (q[i] - C[:, j]) ** 2
            cur_len[:, k] = lengths[best, cols] + 1

    # Bitiş hücresi: i = j = m-1 → k = r
    distance = cur[:, r].copy()
    path_length = np.where(np.isfinite(distance), cur_len[:, r], 0).astype(np.float64)
    return distance, path_length


def warping_path(
    query: np.ndarray,
    candidate: np.ndarray,
    radius: int = SAKOE_CHIBA_RADIUS,
    use_derivative: bool = True,
) -> np.ndarray:
    """Tek bir aday için hizalama yolu: ``(k, 2)`` — (sorgu_i, aday_j) çiftleri.

    Toplu skorlama yolu (``banded_dtw_batch``) yalnızca mesafe ve yol uzunluğu
    taşır; görselleştirme için yolun kendisi gerekir. Bu fonksiyon **tek aday**
    içindir (göz testi karosu başına bir kez) — sıcak yolda kullanılmaz.
    """
    q = derivative(query) if use_derivative else np.asarray(query, dtype=np.float64)
    c = derivative(candidate) if use_derivative else np.asarray(candidate, dtype=np.float64)
    m = q.size
    r = int(min(max(1, radius), m - 1))

    inf = np.inf
    cost = np.full((m, m), inf)
    back = np.zeros((m, m, 2), dtype=np.int32)

    for i in range(m):
        for j in range(max(0, i - r), min(m, i + r + 1)):
            d = (q[i] - c[j]) ** 2
            if i == 0 and j == 0:
                cost[i, j] = d
                continue
            options = []
            if i > 0 and abs(i - 1 - j) <= r:
                options.append((cost[i - 1, j], i - 1, j))
            if j > 0 and abs(i - j + 1) <= r:
                options.append((cost[i, j - 1], i, j - 1))
            if i > 0 and j > 0:
                options.append((cost[i - 1, j - 1], i - 1, j - 1))
            if not options:
                continue
            best, bi, bj = min(options, key=lambda t: t[0])
            if np.isfinite(best):
                cost[i, j] = best + d
                back[i, j] = (bi, bj)

    path = [(m - 1, m - 1)]
    i, j = m - 1, m - 1
    while (i, j) != (0, 0):
        i, j = int(back[i, j, 0]), int(back[i, j, 1])
        path.append((i, j))
    return np.array(path[::-1], dtype=np.int32)


def warp_amount(path: np.ndarray) -> float:
    """Hizalama yolunun köşegenden ortalama sapması (bar cinsinden).

    Büyük değer = eşleşme ağır zaman bükmesiyle kurulmuş → şüpheli.
    **Yalnızca ölçülür, filtreye çevrilmez** (F3.5, Adım 6: kanıt biriksin).
    """
    if path.size == 0:
        return 0.0
    return float(np.mean(np.abs(path[:, 0].astype(np.int64) - path[:, 1].astype(np.int64))))


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
    """Ham DTW — kıyas metriği (K-11 yeniden açıldı; F3'te karara bağlanacak)."""
    return normalized_scores(query, candidates, radius, use_derivative=False)


def stage2_scores(
    query: np.ndarray,
    candidates: np.ndarray,
    radius: int = SAKOE_CHIBA_RADIUS,
    metric: str = STAGE2_METRIC,
) -> np.ndarray:
    """Aşama 2 metrik seçici — F3 kalibrasyonunun anahtarı (K-11).

    Varsayılan ``"ddtw"``. ``"hybrid"`` bilinçli olarak uygulanmadı: hesaplama
    maliyeti sıfıra yakın olsa da, harmanlama ancak ROC kanıtı geldikten sonra
    eklenecek.
    """
    if metric == "ddtw":
        return ddtw_scores(query, candidates, radius)
    if metric == "dtw":
        return dtw_scores(query, candidates, radius)
    if metric == "hybrid":
        # İki normalize mesafenin ortalaması. UYARI: ham DTW mesafeleri
        # DDTW'ninkinden ~4x büyük olduğu için düz ortalama pratikte ham DTW
        # ağırlıklıdır; bu, F3 raporunda açıkça belirtilir.
        return 0.5 * (
            ddtw_scores(query, candidates, radius) + dtw_scores(query, candidates, radius)
        )
    raise ValueError(f"bilinmeyen Aşama 2 metriği: {metric}")
