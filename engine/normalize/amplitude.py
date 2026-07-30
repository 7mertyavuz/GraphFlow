"""Genlik (amplitude) meta-verisi — K-10.

Z-score hareketin **şiddetini** siler: %2'lik yatay bir testere hareketi ile
%40'lık bir mega ralli tamamen aynı vektörü üretir. Bu bilinçli bir kayıptır,
ama telafi edilmesi gerekir; aksi hâlde kullanıcı sonuçlara bakıp "bu
saçmalık" der.

Genlik **ham fiyatlardan, normalizasyondan ÖNCE** hesaplanır:

    genlik = (max(p) - min(p)) / min(p) * 100
"""

from __future__ import annotations

import numpy as np


def amplitude(prices: np.ndarray) -> float:
    """Tek pencerenin genlik yüzdesi. Geçersiz fiyatta NaN."""
    p = np.asarray(prices, dtype=np.float64)
    if p.size == 0 or not np.all(np.isfinite(p)):
        return float("nan")
    lo = p.min()
    if lo <= 0.0:
        return float("nan")
    return float((p.max() - lo) / lo * 100.0)


def amplitude_batch(windows: np.ndarray) -> np.ndarray:
    """(m, L) ham fiyat penceresi → (m,) genlik yüzdesi (float32)."""
    w = np.asarray(windows, dtype=np.float64)
    if w.ndim == 1:
        w = w[None, :]

    lo = w.min(axis=1)
    hi = w.max(axis=1)
    ok = np.isfinite(w).all(axis=1) & (lo > 0.0)

    out = np.full(w.shape[0], np.nan, dtype=np.float64)
    np.divide(hi - lo, lo, out=out, where=ok)
    out *= 100.0
    out[~ok] = np.nan
    return out.astype(np.float32)
