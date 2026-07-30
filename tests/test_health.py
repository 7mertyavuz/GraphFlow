"""F3.5 — veri tazeliği invariant testleri.

Bu dosyanın varlık sebebi: arşivin mikrosaniye damgaya geçmesi, 19 aylık
veriyi **sıfır hata mesajıyla** yok etmişti. İndirme başarıyla bitiyor,
Parquet dosyaları yazılıyor, tüm testler geçiyordu — yalnızca veri yoktu.

Bu sınıf hatanın bir daha sessiz kalmaması için kalıcı bir invariant:
depodaki en yeni bar, bugünden ``MAX_STALENESS_BARS`` bardan fazla geride
olamaz.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from engine.config import KLINES_DIR, MAX_STALENESS_BARS, TIMEFRAME_MS

LIMIT_1D = MAX_STALENESS_BARS["1d"]
from engine.ingest.health import StaleDataError, check_freshness, freshness
from engine.ingest.store import available_symbols, write_atomic
DAY = TIMEFRAME_MS["1d"]


def _write(symbol: str, start_ms: int, n: int, root, timeframe="1d"):
    import pandas as pd
    import numpy as np

    step = TIMEFRAME_MS[timeframe]
    ot = start_ms + np.arange(n, dtype=np.int64) * step
    close = 100.0 + np.arange(n, dtype=float)
    df = pd.DataFrame(
        {
            "open_time": ot,
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.ones(n),
            "quote_volume": np.ones(n) * 1000,
            "trades": np.ones(n, dtype=np.int32),
        }
    )
    write_atomic(df, root / timeframe / f"{symbol}.parquet")


def test_fresh_data_passes(tmp_path):
    now = int(datetime(2026, 7, 30, 12, tzinfo=timezone.utc).timestamp() * 1000)
    _write("BTCUSDT", now - 100 * DAY, 100, tmp_path)  # son bar ~dün

    report = freshness("1d", root=tmp_path, now_ms=now)
    assert report.ok
    assert report.stale_bars < LIMIT_1D


def test_stale_data_is_detected(tmp_path):
    """Mikrosaniye hatasının belirtisi tam olarak buydu: veri 19 ay geride."""
    now = int(datetime(2026, 7, 30, tzinfo=timezone.utc).timestamp() * 1000)
    son_bar = int(datetime(2024, 12, 31, tzinfo=timezone.utc).timestamp() * 1000)
    _write("BTCUSDT", son_bar - 100 * DAY, 101, tmp_path)

    report = freshness("1d", root=tmp_path, now_ms=now)
    assert not report.ok
    assert report.stale_bars > 500  # ~19 ay
    with pytest.raises(StaleDataError):
        check_freshness("1d", root=tmp_path, now_ms=now)


def test_boundary_is_max_staleness_bars(tmp_path):
    now = int(datetime(2026, 7, 30, tzinfo=timezone.utc).timestamp() * 1000)

    _write("A", now - (LIMIT_1D - 1) * DAY, 1, tmp_path)
    assert freshness("1d", symbols=["A"], root=tmp_path, now_ms=now).ok

    _write("B", now - (LIMIT_1D + 1) * DAY, 1, tmp_path)
    assert not freshness("1d", symbols=["B"], root=tmp_path, now_ms=now).ok


def test_delisted_symbol_alone_does_not_fail_the_universe(tmp_path):
    """Delist edilmiş parite geride kalır (K-13) — ölçüt evrenin MAKSİMUMU."""
    now = int(datetime(2026, 7, 30, tzinfo=timezone.utc).timestamp() * 1000)
    _write("LUNAUSDT", now - 1000 * DAY, 100, tmp_path)  # çok eski, delist
    _write("BTCUSDT", now - 5 * DAY, 5, tmp_path)  # güncel

    report = freshness("1d", root=tmp_path, now_ms=now)
    assert report.ok
    assert report.symbols == 2


def test_empty_store_is_not_fresh(tmp_path):
    report = freshness("1d", root=tmp_path, now_ms=1_700_000_000_000)
    assert not report.ok
    assert report.newest_open_time is None


@pytest.mark.skipif(
    not (KLINES_DIR / "1d").exists() or not available_symbols("1d"),
    reason="gerçek veri deposu yok (CI)",
)
def test_real_store_is_fresh():
    """Gerçek depo varsa bayat olmamalı — mikrosaniye hatasının nöbetçisi."""
    report = freshness("1d")
    assert report.ok, str(report)
