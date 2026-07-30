"""Wilder ATR(14) — K-16.4, docs/01-mimari.md §8.1.

**Lookahead yasağı bu modülün tek gerekçesidir.** ATR, bariyerleri belirler;
formasyon tamamlandığı anda (``t0``) bilinebilir olmalıdır. ``t0``'dan sonraki
tek bir barın ATR'ye sızması tüm istatistik katmanını geçersiz kılar.

Wilder yumuşatması özyinelemelidir ve doğası gereği yalnızca geçmişe bakar:

    TR[0]   = high[0] - low[0]
    TR[i]   = max(high[i]-low[i], |high[i]-close[i-1]|, |low[i]-close[i-1]|)
    ATR[p-1] = mean(TR[0:p])
    ATR[i]   = (ATR[i-1] * (p-1) + TR[i]) / p

Bu özelliğin birim testi ``tests/test_normalize.py`` içindedir: dizinin
tamamından hesaplanan ``ATR[t0]``, yalnızca ``[0..t0]`` barlarından
hesaplanan ATR'nin son değerine **birebir eşit** olmalıdır.
"""

from __future__ import annotations

import numpy as np

from engine.config import ATR_PERIOD


def true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    h = np.asarray(high, dtype=np.float64)
    l = np.asarray(low, dtype=np.float64)
    c = np.asarray(close, dtype=np.float64)
    if not (h.shape == l.shape == c.shape):
        raise ValueError("high/low/close aynı uzunlukta olmalı")

    tr = np.empty_like(h)
    tr[0] = h[0] - l[0]
    if h.size > 1:
        prev_close = c[:-1]
        tr[1:] = np.maximum(
            h[1:] - l[1:],
            np.maximum(np.abs(h[1:] - prev_close), np.abs(l[1:] - prev_close)),
        )
    return tr


def wilder_atr(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = ATR_PERIOD,
) -> np.ndarray:
    """(n,) ATR dizisi. İlk ``period-1`` eleman NaN'dır (henüz tanımsız).

    ``atr[i]`` yalnızca ``0..i`` barlarını kullanır — lookahead yok.
    """
    tr = true_range(high, low, close)
    n = tr.size
    atr = np.full(n, np.nan, dtype=np.float64)
    if n < period:
        return atr

    atr[period - 1] = tr[:period].mean()
    alpha = (period - 1) / period
    for i in range(period, n):  # özyineleme — vektörize edilemez
        atr[i] = atr[i - 1] * alpha + tr[i] / period
    return atr


def atr_at(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    index: int,
    period: int = ATR_PERIOD,
) -> float:
    """``index`` barındaki ATR — açıkça yalnızca ``[0..index]`` dilimiyle.

    Lookahead'in imkânsız olduğu, okunduğunda görülebilen versiyon.
    """
    end = index + 1
    values = wilder_atr(high[:end], low[:end], close[:end], period)
    return float(values[-1])
