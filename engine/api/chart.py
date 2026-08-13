"""Eşleşme karosunun grafiği — mumlar + blueprint katmanları.

Geometri **sunucuda** kurulur. Sebebi tek bir cümlede: normalizasyon log
uzayında yapılır (K-02), dolayısıyla z-score'lu sorguyu fiyat eksenine geri
taşımanın doğru yolu ``exp(mu + sigma·z)``'dir. Bunu istemcide yeniden
uydurmak, arayüzde motorun ölçtüğünden farklı bir şekil çizmek demektir —
göz testi ile ürünün ayrışması tam olarak buradan başlar.

İndeks sözleşmesi: ``Match.start_idx``/``end_idx`` **sembol-yerel** bar
indeksleridir; ``BarStore`` ise tüm sembolleri uç uca eklenmiş tek dizide
tutar. Dönüşüm ``offset[sembol] + yerel`` ile yapılır; unutulursa grafik
başka bir sembolün barlarını çizer.
"""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np

from engine.api.schemas import Candle, ChartResponse, OverlayPoint
from engine.config import CHART_CONTEXT_RATIO, N_POINTS
from engine.normalize.pipeline import resample_to
from engine.outcome.bars import BarStore
from engine.search.blueprint import blueprint_layers


def _finite(value: float) -> float | None:
    return float(value) if math.isfinite(value) else None


def _price_mapper(closes: np.ndarray):
    """Z-score uzayındaki bir eğriyi pencerenin fiyat ölçeğine taşır.

    Normalizasyonun (log → resample → z-score) tersi; blueprint tam olarak
    motorun kıyasladığı şeklin fiyat eksenindeki karşılığıdır.
    """
    positive = closes[closes > 0]
    if positive.size < 2:
        return None

    x = np.log(positive.astype(np.float64))
    x32 = resample_to(x, N_POINTS)
    mu, sigma = float(x32.mean()), float(x32.std())
    if not math.isfinite(mu) or sigma <= 0.0:
        return None

    def to_price(z: np.ndarray) -> np.ndarray:
        return np.exp(mu + sigma * np.asarray(z, dtype=np.float64))

    return to_price


def _overlay(values: np.ndarray, times: np.ndarray) -> list[OverlayPoint]:
    """32 noktalık eğriyi pencere barlarının zaman eksenine oturtur.

    Pencere 32 bardan kısaysa (ör. 24 barlık pencere) eğri **bar sayısına
    indirgenir**: aksi hâlde iki nokta aynı bara düşer ve grafik kütüphanesi
    "zamanlar artan olmalı" diyerek seriyi tümden reddeder — katman sessizce
    kaybolur.
    """
    values = np.asarray(values, dtype=np.float64)
    if values.size < 2 or times.size == 0:
        return []

    if times.size < values.size:
        src = np.linspace(0.0, 1.0, values.size)
        dst = np.linspace(0.0, 1.0, int(times.size))
        values = np.interp(dst, src, values)

    positions = np.linspace(0, times.size - 1, values.size)
    return [
        OverlayPoint(time=int(times[int(round(p))] // 1000), value=float(v))
        for p, v in zip(positions, values)
        if math.isfinite(float(v))
    ]


def build_chart(
    store: BarStore,
    symbol: str,
    symbol_id: int,
    timeframe: str,
    start_idx: int,
    end_idx: int,
    query: np.ndarray | None = None,
    candidate: np.ndarray | None = None,
    warp_path: Sequence[Sequence[int]] | None = None,
) -> ChartResponse:
    """Bağlam barlarıyla birlikte tek eşleşmenin grafik yükü."""
    empty = ChartResponse(
        symbol=symbol,
        timeframe=timeframe,
        ohlcv=[],
        highlight_start=0,
        highlight_end=0,
        blueprint_overlay=[],
        warped_overlay=[],
        warp_amount=None,
    )
    if not store.has(symbol_id):
        return empty

    off = store.offset[int(symbol_id)]
    n_bars = store.n_bars[int(symbol_id)]

    start = max(0, min(int(start_idx), n_bars - 1))
    end = max(start, min(int(end_idx), n_bars - 1))

    # Bağlam: formasyon nereden geldi, sonrasında ne oldu. Pencere uzunluğuyla
    # orantılıdır — 24 barlık bayrağa 100 bar bağlam eklemek formasyonu
    # görünmez yapar.
    pad = int(round(CHART_CONTEXT_RATIO * (end - start + 1)))
    lo = max(0, start - pad)
    hi = min(n_bars - 1, end + pad)

    times = store.open_time[off + lo : off + hi + 1]
    opens = store.open[off + lo : off + hi + 1]
    highs = store.high[off + lo : off + hi + 1]
    lows = store.low[off + lo : off + hi + 1]
    closes = store.close[off + lo : off + hi + 1]

    if closes.size == 0:
        return empty

    # Filtreleme yapılmaz: bir barı atlamak highlight indekslerini kaydırır.
    candles = [
        Candle(
            time=int(t // 1000),  # lightweight-charts saniye bekler
            open=float(o),
            high=float(h),
            low=float(low),
            close=float(c),
        )
        for t, o, h, low, c in zip(times, opens, highs, lows, closes)
    ]

    highlight_start = start - lo
    highlight_end = end - lo

    blueprint: list[OverlayPoint] = []
    warped: list[OverlayPoint] = []
    amount: float | None = None

    if query is not None and len(query) == N_POINTS:
        window_closes = store.close[off + start : off + end + 1]
        window_times = store.open_time[off + start : off + end + 1]
        to_price = _price_mapper(window_closes)
        if to_price is not None:
            q = np.asarray(query, dtype=np.float64)
            path = np.asarray(warp_path, dtype=np.int64).reshape(-1, 2) if warp_path else None
            if path is not None and path.size:
                canonical, warp_curve, amount_raw = blueprint_layers(q, candidate, path=path)
                amount = _finite(amount_raw)
                warped = _overlay(to_price(warp_curve), window_times)
            else:
                canonical = q
            blueprint = _overlay(to_price(canonical), window_times)

    return ChartResponse(
        symbol=symbol,
        timeframe=timeframe,
        ohlcv=candles,
        highlight_start=highlight_start,
        highlight_end=highlight_end,
        blueprint_overlay=blueprint,
        warped_overlay=warped,
        warp_amount=amount,
    )
