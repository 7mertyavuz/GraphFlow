"""Parquet okuma/yazma katmanı — docs/01-mimari.md §2.2.

``data/klines/{timeframe}/{symbol}.parquet``

Yazımlar **atomiktir**: önce aynı dizine geçici dosya yazılır, sonra
``os.replace`` ile yerine taşınır. Böylece indirme yarıda kesilse bile bozuk
Parquet dosyası kalmaz — kesintiden devam (resume) bunun üzerine kurulur.

Append artımlıdır: mevcut dosya okunur, yeni barlarla birleştirilir,
``open_time`` (birincil anahtar) üzerinden tekilleştirilir ve sıralanır.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from engine.config import KLINES_DIR

#: docs/01-mimari.md §2.2 şeması. Sıra ve tipler birebir korunur.
KLINE_SCHEMA: pa.Schema = pa.schema(
    [
        ("open_time", pa.int64()),
        ("open", pa.float64()),
        ("high", pa.float64()),
        ("low", pa.float64()),
        ("close", pa.float64()),
        ("volume", pa.float64()),
        ("quote_volume", pa.float64()),
        ("trades", pa.int32()),
    ]
)

COLUMNS: tuple[str, ...] = tuple(KLINE_SCHEMA.names)


def kline_path(symbol: str, timeframe: str, root: Path | None = None) -> Path:
    base = KLINES_DIR if root is None else root
    return Path(base) / timeframe / f"{symbol}.parquet"


def klines_to_frame(klines: Iterable) -> pd.DataFrame:
    """``Kline`` nesnelerini (veya ham dizileri) şema uyumlu DataFrame'e çevirir."""
    rows: list[tuple] = []
    for k in klines:
        if isinstance(k, (list, tuple)):
            rows.append(
                (
                    int(k[0]),
                    float(k[1]),
                    float(k[2]),
                    float(k[3]),
                    float(k[4]),
                    float(k[5]),
                    float(k[7]),
                    int(k[8]),
                )
            )
        else:
            rows.append(
                (
                    k.open_time,
                    k.open,
                    k.high,
                    k.low,
                    k.close,
                    k.volume,
                    k.quote_volume,
                    k.trades,
                )
            )

    df = pd.DataFrame(rows, columns=list(COLUMNS))
    return _coerce(df)


def _coerce(df: pd.DataFrame) -> pd.DataFrame:
    return df.astype(
        {
            "open_time": "int64",
            "open": "float64",
            "high": "float64",
            "low": "float64",
            "close": "float64",
            "volume": "float64",
            "quote_volume": "float64",
            "trades": "int32",
        }
    )


def write_atomic(df: pd.DataFrame, path: Path) -> None:
    """Şema doğrulayıp geçici dosya üzerinden atomik olarak yazar."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(_coerce(df[list(COLUMNS)]), schema=KLINE_SCHEMA, preserve_index=False)

    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".parquet.tmp")
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        pq.write_table(table, tmp, compression="zstd")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def read_klines(
    symbol: str,
    timeframe: str,
    root: Path | None = None,
    columns: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Dosya yoksa boş ama şema uyumlu bir DataFrame döner."""
    path = kline_path(symbol, timeframe, root)
    if not path.exists():
        empty = pd.DataFrame({c: pd.Series(dtype=_pandas_dtype(c)) for c in COLUMNS})
        return empty if columns is None else empty[list(columns)]
    df = pq.read_table(path, columns=list(columns) if columns else None).to_pandas()
    return df


def _pandas_dtype(column: str) -> str:
    if column == "open_time":
        return "int64"
    if column == "trades":
        return "int32"
    return "float64"


def append_klines(
    symbol: str,
    timeframe: str,
    klines: Iterable,
    root: Path | None = None,
) -> int:
    """Yeni barları mevcut dosyaya ekler; eklenen (net yeni) bar sayısını döner.

    Çakışan ``open_time`` değerlerinde YENİ kayıt kazanır — son mum bir sonraki
    çalıştırmada kapanmış hâliyle güncellenebilsin diye.
    """
    new_df = klines_to_frame(klines)
    if new_df.empty:
        return 0

    path = kline_path(symbol, timeframe, root)
    existing = read_klines(symbol, timeframe, root)
    before = len(existing)

    merged = pd.concat([existing, new_df], ignore_index=True)
    merged = merged.drop_duplicates(subset="open_time", keep="last")
    merged = merged.sort_values("open_time", ignore_index=True)

    write_atomic(merged, path)
    return len(merged) - before


def last_open_time(symbol: str, timeframe: str, root: Path | None = None) -> int | None:
    """Kesintiden devam için: saklanan son barın açılış zamanı."""
    path = kline_path(symbol, timeframe, root)
    if not path.exists():
        return None
    col = pq.read_table(path, columns=["open_time"]).column("open_time")
    if len(col) == 0:
        return None
    return int(pa.compute.max(col).as_py())


def bar_count(symbol: str, timeframe: str, root: Path | None = None) -> int:
    path = kline_path(symbol, timeframe, root)
    if not path.exists():
        return 0
    return pq.read_metadata(path).num_rows


def available_symbols(timeframe: str, root: Path | None = None) -> list[str]:
    base = (KLINES_DIR if root is None else Path(root)) / timeframe
    if not base.exists():
        return []
    return sorted(p.stem for p in base.glob("*.parquet"))


# ---------------------------------------------------------------------------
# Küçük JSON yardımcıları (evren dosyası, ingest durumu) — aynı atomik desen
# ---------------------------------------------------------------------------


def write_json_atomic(payload, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".json.tmp")
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def read_json(path: Path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default
