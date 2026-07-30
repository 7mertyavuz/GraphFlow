"""Aşama 1 — Kosinüs benzerliği ile kaba eleme (docs/01-mimari.md §5.1, K-03).

    scores = (V @ q) / 32

``V`` satırları ve ``q`` z-score'lu olduğu için ``‖v‖ = ‖q‖ = √32``; bu işlem
**Pearson korelasyonuna matematiksel olarak eşittir**. İstenen davranış budur —
şekil korelasyonu ölçüyoruz.

Uygulama notları:

* ``V`` bir ``np.memmap``'tir; skorlama ``STAGE1_CHUNK_ROWS``'luk parçalar
  hâlinde yapılır ki geçici diziler RAM'i şişirmesin.
* **Sorgu vektörü float32'ye çevrilir.** float64 bir ``q``, NumPy'ı tüm
  float32 matrisi float64'e yükseltmeye zorlar (4x bellek, 2x süre).
* Filtreler (likidite, genlik) **çarpımdan önce** maskelenir. Maske çok
  seyrekse (Radar modu) tüm matris çarpılmaz, yalnızca ilgili satırlar
  toplanır — performans bütçesindeki < 10 ms bu sayede tutar.
"""

from __future__ import annotations

import numpy as np

from engine.config import N_POINTS, STAGE1_CHUNK_ROWS, STAGE1_SPARSE_MASK_RATIO, STAGE1_TOPK

NEG_INF = np.float32(-np.inf)


def prepare_query(query: np.ndarray) -> np.ndarray:
    """Sorguyu bitişik float32'ye çevirir (dtype yükseltmesini önler)."""
    q = np.ascontiguousarray(np.asarray(query, dtype=np.float32))
    if q.shape != (N_POINTS,):
        raise ValueError(f"sorgu vektörü ({N_POINTS},) olmalı, gelen {q.shape}")
    return q


def cosine_scores(
    vectors: np.ndarray,
    query: np.ndarray,
    mask: np.ndarray | None = None,
    chunk: int = STAGE1_CHUNK_ROWS,
) -> np.ndarray:
    """(K,) skor dizisi. Maskelenen satırlar ``-inf`` alır."""
    q = prepare_query(query)
    k = vectors.shape[0]
    scores = np.empty(k, dtype=np.float32)
    if k == 0:
        return scores

    for a in range(0, k, chunk):
        b = min(a + chunk, k)
        block = np.asarray(vectors[a:b])
        np.matmul(block, q, out=scores[a:b])

    scores /= np.float32(N_POINTS)
    if mask is not None:
        scores[~mask] = NEG_INF
    return scores


def _sparse_scores(vectors: np.ndarray, query: np.ndarray, rows: np.ndarray) -> np.ndarray:
    q = prepare_query(query)
    block = np.asarray(vectors[rows])
    return (block @ q) / np.float32(N_POINTS)


def top_k(
    vectors: np.ndarray,
    query: np.ndarray,
    k: int = STAGE1_TOPK,
    mask: np.ndarray | None = None,
    chunk: int = STAGE1_CHUNK_ROWS,
    sparse_ratio: float = STAGE1_SPARSE_MASK_RATIO,
) -> tuple[np.ndarray, np.ndarray]:
    """En yüksek skorlu k adayı döndürür: ``(indeksler, skorlar)``, skora göre azalan.

    ``np.argpartition`` kullanılır: tam sıralama O(K log K) yerine O(K).
    """
    n_rows = vectors.shape[0]
    if n_rows == 0 or k <= 0:
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.float32)

    if mask is not None:
        n_active = int(mask.sum())
        if n_active == 0:
            return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.float32)

        # Seyrek maske (ör. Radar): tüm matrisi çarpmak yerine satırları topla.
        if n_active <= max(1, int(n_rows * sparse_ratio)):
            rows = np.flatnonzero(mask)
            sub = _sparse_scores(vectors, query, rows)
            take = min(k, sub.size)
            part = np.argpartition(-sub, take - 1)[:take]
            order = part[np.argsort(-sub[part], kind="stable")]
            return rows[order], sub[order]

    scores = cosine_scores(vectors, query, mask=mask, chunk=chunk)
    limit = int(mask.sum()) if mask is not None else n_rows
    take = min(k, limit)
    if take <= 0:
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.float32)

    part = np.argpartition(-scores, take - 1)[:take]
    order = part[np.argsort(-scores[part], kind="stable")]
    return order.astype(np.int64), scores[order]
