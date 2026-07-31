"""Düz (flat) bar deposu — vektörize outcome hesabının taşıyıcısı.

Her sembolün OHLC dizileri farklı uzunluktadır; bu "pürüzlü" (ragged) yapı
NumPy'da doğrudan matrisleştirilemez. Çözüm: tüm sembolleri **tek bir düz
dizide** birleştirip sembol başına ofset tutmak. Böylece

    global_indeks = ofset[sembol] + yerel_indeks

ile ~10.000 olayın ileri pencereleri tek bir fancy-index ile toplanır ve
triple-barrier'da hiç Python döngüsü kalmaz.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

from engine.config import PRICE_CONTINUITY_MAX_RATIO
from engine.ingest.store import read_klines


@dataclass
class BarStore:
    """Sembolleri uç uca eklenmiş OHLC dizileri + ofset tablosu."""

    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    open_time: np.ndarray
    offset: dict[int, int] = field(default_factory=dict)
    n_bars: dict[int, int] = field(default_factory=dict)
    symbols: dict[int, str] = field(default_factory=dict)
    #: Bar-bar fiyat sıçraması (redenominasyon / ticker yeniden kullanımı).
    #: İleri pencere burada kesilir; sıçramanın ötesi ölçülmez.
    jump: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=bool))

    def __post_init__(self) -> None:
        if self.jump.size == self.close.size:
            return
        jump = np.zeros(self.close.size, dtype=bool)
        for sid, off in self.offset.items():
            n = self.n_bars[sid]
            c = self.close[off : off + n]
            if n < 2:
                continue
            with np.errstate(divide="ignore", invalid="ignore"):
                ratio = np.maximum(c[1:] / c[:-1], c[:-1] / c[1:])
            jump[off + 1 : off + n] = ~np.isfinite(ratio) | (ratio > PRICE_CONTINUITY_MAX_RATIO)
        self.jump = jump

    @classmethod
    def from_klines(
        cls,
        symbols: Iterable[str],
        timeframe: str,
        ids: dict[str, int],
        root: Path | None = None,
    ) -> "BarStore":
        opens, highs, lows, closes, times = [], [], [], [], []
        offset: dict[int, int] = {}
        n_bars: dict[int, int] = {}
        names: dict[int, str] = {}
        cursor = 0

        for symbol in symbols:
            sid = ids.get(symbol)
            if sid is None:
                continue
            df = read_klines(symbol, timeframe, root)
            if df.empty:
                continue

            opens.append(df["open"].to_numpy(dtype=np.float64))
            highs.append(df["high"].to_numpy(dtype=np.float64))
            lows.append(df["low"].to_numpy(dtype=np.float64))
            closes.append(df["close"].to_numpy(dtype=np.float64))
            times.append(df["open_time"].to_numpy(dtype=np.int64))

            offset[sid] = cursor
            n_bars[sid] = len(df)
            names[sid] = symbol
            cursor += len(df)

        empty = np.empty(0, dtype=np.float64)
        return cls(
            open=np.concatenate(opens) if opens else empty,
            high=np.concatenate(highs) if highs else empty,
            low=np.concatenate(lows) if lows else empty,
            close=np.concatenate(closes) if closes else empty,
            open_time=np.concatenate(times) if times else np.empty(0, dtype=np.int64),
            offset=offset,
            n_bars=n_bars,
            symbols=names,
        )

    @classmethod
    def from_arrays(cls, arrays: dict[int, dict[str, np.ndarray]]) -> "BarStore":
        """Testler için: {symbol_id: {"open": ..., "high": ...}} → BarStore."""
        opens, highs, lows, closes, times = [], [], [], [], []
        offset, n_bars, names = {}, {}, {}
        cursor = 0
        for sid, data in arrays.items():
            n = len(data["close"])
            opens.append(np.asarray(data.get("open", data["close"]), dtype=np.float64))
            highs.append(np.asarray(data["high"], dtype=np.float64))
            lows.append(np.asarray(data["low"], dtype=np.float64))
            closes.append(np.asarray(data["close"], dtype=np.float64))
            times.append(np.asarray(data.get("open_time", np.arange(n)), dtype=np.int64))
            offset[sid], n_bars[sid], names[sid] = cursor, n, data.get("symbol", f"#{sid}")
            cursor += n
        empty = np.empty(0, dtype=np.float64)
        return cls(
            open=np.concatenate(opens) if opens else empty,
            high=np.concatenate(highs) if highs else empty,
            low=np.concatenate(lows) if lows else empty,
            close=np.concatenate(closes) if closes else empty,
            open_time=np.concatenate(times) if times else np.empty(0, dtype=np.int64),
            offset=offset,
            n_bars=n_bars,
            symbols=names,
        )

    # -- vektörize erişim -------------------------------------------------

    def offsets_of(self, symbol_ids: np.ndarray) -> np.ndarray:
        return np.array([self.offset[int(s)] for s in symbol_ids], dtype=np.int64)

    def lengths_of(self, symbol_ids: np.ndarray) -> np.ndarray:
        return np.array([self.n_bars[int(s)] for s in symbol_ids], dtype=np.int64)

    def has(self, symbol_id: int) -> bool:
        return int(symbol_id) in self.offset

    def close_at(self, symbol_ids: np.ndarray, bar_idx: np.ndarray) -> np.ndarray:
        return self.close[self.offsets_of(symbol_ids) + np.asarray(bar_idx, dtype=np.int64)]

    def forward_window(
        self, symbol_ids: np.ndarray, t0: np.ndarray, horizon: int
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """``t0``'dan sonraki ``horizon`` barlık (N, T) OHLC matrisleri.

        Kısa kalan satırlar (delist / veri sonu) **asla bariyer tetiklemeyecek**
        değerlerle doldurulur: high → −inf, low → +inf. Geçerli bar sayısı ayrı
        maske olarak döner.
        """
        symbol_ids = np.asarray(symbol_ids)
        t0 = np.asarray(t0, dtype=np.int64)
        base = self.offsets_of(symbol_ids)
        avail = self.lengths_of(symbol_ids) - t0 - 1  # t0'dan sonraki bar sayısı

        steps = np.arange(1, horizon + 1, dtype=np.int64)[None, :]
        valid = steps <= avail[:, None]
        flat = base[:, None] + np.clip(t0[:, None] + steps, 0, None)
        flat = np.clip(flat, 0, max(0, self.close.size - 1))

        # Fiyat sıçramasından SONRAsı ölçülmez: sıçrama bir fiyat hareketi
        # değil, farklı bir varlık/birimdir. Sıçrama barı ve ötesi geçersiz.
        broke = np.cumsum(self.jump[flat] & valid, axis=1) > 0
        valid = valid & ~broke

        high = np.where(valid, self.high[flat], -np.inf)
        low = np.where(valid, self.low[flat], np.inf)
        open_ = np.where(valid, self.open[flat], np.nan)
        close = np.where(valid, self.close[flat], np.nan)
        return high, low, open_, close, valid  # type: ignore[return-value]


def build_store(
    symbols: Sequence[str], timeframe: str, ids: dict[str, int], root: Path | None = None
) -> BarStore:
    return BarStore.from_klines(symbols, timeframe, ids, root)
