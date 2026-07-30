"""Aylık kesitsel likidite sıralaması — K-13.2.

Sabit dolar eşiği (ör. 10 M$) **kullanılmaz**: 2018'de günlük 10 M$ üstü
hacme sahip parite sayısı bir elin parmaklarını geçmiyordu. Sabit eşik,
survivorship bias'ı düzeltmek için geri çekilen tarihi bu kez likidite
kapısından siler — iki düzeltme birbirini götürür.

Bunun yerine **her ayın kendi kesitinde** hacim sıralaması hesaplanır ve o
ayın üst ``LIQUIDITY_TOP_PCT`` dilimine girmeyen pariteler o ayki pencerelerde
maskelenir. Böylece hem 2018 hem 2025 verisi adilce temsil edilir.

Çıktı, docs/01-mimari.md §2.3'teki ``liquidity_rank`` tablosuyla aynı
alanlara sahiptir: ``symbol, month, quote_volume, pct_rank``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

import numpy as np
import pandas as pd

from engine.config import LIQUIDITY_TOP_PCT
from engine.ingest.store import read_klines


def month_key(open_time_ms) -> np.ndarray:
    """ms zaman damgası → ayın ilk gününün ms damgası (kesit anahtarı)."""
    ts = np.asarray(open_time_ms, dtype="int64").astype("datetime64[ms]")
    return ts.astype("datetime64[M]").astype("datetime64[ms]").astype("int64")


def monthly_volume(df: pd.DataFrame) -> pd.Series:
    """Bir sembolün aylık toplam kote hacmi (index: ay ms)."""
    if df.empty:
        return pd.Series(dtype="float64")
    months = month_key(df["open_time"].to_numpy())
    return pd.Series(df["quote_volume"].to_numpy(), index=months).groupby(level=0).sum()


def build_liquidity_table(volumes: Mapping[str, pd.Series]) -> pd.DataFrame:
    """{symbol: aylık hacim serisi} → kesitsel sıralama tablosu.

    ``pct_rank`` o ayın kesitinde 0..1 arası yüzdelik sıradır (1 = en likit).
    ``liquid``, üst ``LIQUIDITY_TOP_PCT`` dilimine girenler için True.
    """
    frames = []
    for symbol, series in volumes.items():
        if series is None or len(series) == 0:
            continue
        frames.append(
            pd.DataFrame(
                {
                    "symbol": symbol,
                    "month": series.index.astype("int64"),
                    "quote_volume": series.to_numpy(dtype="float64"),
                }
            )
        )

    if not frames:
        return pd.DataFrame(
            {
                "symbol": pd.Series(dtype="object"),
                "month": pd.Series(dtype="int64"),
                "quote_volume": pd.Series(dtype="float64"),
                "pct_rank": pd.Series(dtype="float32"),
                "liquid": pd.Series(dtype="bool"),
            }
        )

    table = pd.concat(frames, ignore_index=True)
    table["pct_rank"] = (
        table.groupby("month")["quote_volume"].rank(pct=True, method="average").astype("float32")
    )
    table["liquid"] = table["pct_rank"] > (1.0 - LIQUIDITY_TOP_PCT)
    return table


def build_from_klines(
    symbols: Iterable[str], timeframe: str, root: Path | None = None
) -> pd.DataFrame:
    """Parquet deposundan doğrudan likidite tablosu üretir."""
    volumes: dict[str, pd.Series] = {}
    for symbol in symbols:
        df = read_klines(symbol, timeframe, root, columns=["open_time", "quote_volume"])
        if not df.empty:
            volumes[symbol] = monthly_volume(df)
    return build_liquidity_table(volumes)


class LiquidityMask:
    """(sembol, ay) → likit mi? Matris inşasında maske olarak kullanılır."""

    def __init__(self, table: pd.DataFrame) -> None:
        if table.empty:
            self._liquid: set[tuple[str, int]] = set()
        else:
            liq = table.loc[table["liquid"], ["symbol", "month"]]
            self._liquid = set(zip(liq["symbol"], liq["month"].astype("int64")))

    def lookup(self, symbol: str, month_ms) -> np.ndarray:
        months = np.atleast_1d(np.asarray(month_ms, dtype="int64"))
        return np.fromiter(
            ((symbol, int(m)) in self._liquid for m in months), dtype=bool, count=months.size
        )

    def __len__(self) -> int:
        return len(self._liquid)


def save_table(table: pd.DataFrame, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    table.to_parquet(path, index=False)


def load_table(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path)
