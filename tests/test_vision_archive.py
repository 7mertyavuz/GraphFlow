"""F3 ADIM 0 — arşiv indiricisi testleri (ağ erişimi YOK).

Bu dosyanın merkezinde, F3 kapısının yakaladığı **sessiz veri kaybı** hatası
vardır: Binance arşivi 2025-01'den itibaren zaman damgalarını mikrosaniye
yazıyor; ms varsayan bir okuyucu bu barları "henüz kapanmamış mum" sanıp
düşürür ve **hiçbir hata vermeden** 19 aylık veriyi yok eder.
"""

from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone

import pytest

from engine.config import EPOCH_US_THRESHOLD, HISTORY_START_MS, TIMEFRAME_MS
from engine.ingest import vision_archive as va

DAY = 86_400_000


def _zip(rows: list[str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("data.csv", "\n".join(rows))
    return buf.getvalue()


def _row(open_time: int, close_time: int, close: float = 100.0) -> str:
    return (
        f"{open_time},99.0,101.0,98.0,{close},10.0,{close_time},1000.0,7,5.0,500.0,0"
    )


# ---------------------------------------------------------------------------
# Zaman damgası birimi — asıl regresyon
# ---------------------------------------------------------------------------


def test_microsecond_timestamps_are_converted():
    """2025+ arşiv dosyaları µs; ms'ye çevrilmezse bar 'gelecekte' görünür."""
    assert va.to_epoch_ms(1_740_787_200_000_000) == 1_740_787_200_000
    assert va.to_epoch_ms(1_704_067_200_000) == 1_704_067_200_000  # ms korunur
    assert va.to_epoch_ms(EPOCH_US_THRESHOLD) == EPOCH_US_THRESHOLD


def test_parse_handles_mixed_units_and_header():
    payload = _zip(
        [
            "open_time,open,high,low,close,volume,close_time,quote_volume,count,x,y,z",
            _row(1_704_067_200_000, 1_704_153_599_999),  # ms (eski dosya)
            _row(1_740_787_200_000_000, 1_740_873_599_999_999),  # µs (yeni dosya)
        ]
    )
    klines = va.parse_csv_zip(payload)

    assert len(klines) == 2  # başlık atlandı
    for k in klines:
        assert k.open_time < EPOCH_US_THRESHOLD
        assert k.close_time < EPOCH_US_THRESHOLD
    assert klines[1].open_time == 1_740_787_200_000


def test_microsecond_bars_are_not_dropped_as_unclosed(tmp_path, monkeypatch):
    """Regresyon: µs barlar 'kapanmamış mum' filtresine takılmamalı.

    Hatanın orijinal belirtisi tam olarak buydu — indirme hatasız bitiyor,
    ama 2025 sonrası hiç bar yazılmıyordu.
    """
    now_ms = int(datetime(2026, 7, 30, tzinfo=timezone.utc).timestamp() * 1000)
    start = int(datetime(2025, 3, 1, tzinfo=timezone.utc).timestamp() * 1000)
    rows = [_row((start + i * DAY) * 1000, (start + (i + 1) * DAY - 1) * 1000) for i in range(31)]
    payload = _zip(rows)

    monkeypatch.setattr(va, "fetch_file", lambda f, s=None: va.parse_csv_zip(payload))
    written = va.download_symbol("TESTUSDT", "1d", start_ms=start, end_ms=now_ms, root=tmp_path)

    assert written > 0, "µs barlar sessizce düşürüldü"


# ---------------------------------------------------------------------------
# Yarım mum (K-05 / K-15)
# ---------------------------------------------------------------------------


def test_unclosed_candle_is_still_dropped(tmp_path, monkeypatch):
    """Birim düzeltmesi, yarım mum kuralını devre dışı bırakmamalı."""
    start = int(datetime(2026, 7, 1, tzinfo=timezone.utc).timestamp() * 1000)
    now_ms = start + 3 * DAY + DAY // 2  # 4. gün henüz kapanmadı
    rows = [_row(start + i * DAY, start + (i + 1) * DAY - 1) for i in range(4)]
    payload = _zip(rows)

    monkeypatch.setattr(va, "fetch_file", lambda f, s=None: va.parse_csv_zip(payload))
    va.download_symbol("TESTUSDT", "1d", start_ms=start, end_ms=now_ms, root=tmp_path)

    from engine.ingest.store import read_klines

    df = read_klines("TESTUSDT", "1d", root=tmp_path)
    assert len(df) == 3
    assert df["open_time"].max() == start + 2 * DAY


# ---------------------------------------------------------------------------
# Dosya listesi üretimi
# ---------------------------------------------------------------------------


def test_archive_files_uses_monthly_then_daily():
    """Tamamlanmış aylar aylık ZIP, içinde bulunulan ay günlük ZIP."""
    start = int(datetime(2026, 5, 1, tzinfo=timezone.utc).timestamp() * 1000)
    end = int(datetime(2026, 7, 10, tzinfo=timezone.utc).timestamp() * 1000)
    files = va.archive_files("BTCUSDT", "1d", start, end)

    monthly = [f for f in files if "/monthly/" in f.url]
    daily = [f for f in files if "/daily/" in f.url]

    assert len(monthly) == 2  # Mayıs, Haziran
    # 1–9 Temmuz: 10 Temmuz gece yarısı bitiş anı olduğu için o günün barı
    # henüz kapanmamıştır ve istenmez.
    assert len(daily) == 9
    assert all(f.url.startswith("https://") for f in files)


def test_archive_files_covers_full_history():
    end = int(datetime(2026, 7, 30, tzinfo=timezone.utc).timestamp() * 1000)
    files = va.archive_files("BTCUSDT", "4h", HISTORY_START_MS, end)
    assert files[0].url.endswith("BTCUSDT-4h-2017-08.zip")
    assert len(files) > 100


def test_archive_files_empty_when_up_to_date():
    now = int(datetime(2026, 7, 30, tzinfo=timezone.utc).timestamp() * 1000)
    assert va.archive_files("BTCUSDT", "1d", now, now) == []


# ---------------------------------------------------------------------------
# Hata dayanıklılığı
# ---------------------------------------------------------------------------


class _Resp:
    def __init__(self, status_code, content=b""):
        self.status_code = status_code
        self.content = content


class _Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def get(self, url, timeout=None):
        self.calls += 1
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_404_is_not_an_error():
    """Parite o ay işlem görmemişse 404 döner — süreç durmamalı."""
    f = va.archive_files("X", "1d", 1_600_000_000_000, 1_602_000_000_000)[0]
    session = _Session([_Resp(404)])
    assert va.fetch_file(f, session) == []
    assert session.calls == 1  # tekrar denenmez


def test_network_error_is_retried():
    f = va.archive_files("X", "1d", 1_600_000_000_000, 1_602_000_000_000)[0]
    payload = _zip([_row(1_600_000_000_000, 1_600_086_399_999)])
    session = _Session([ConnectionError("koptu"), _Resp(200, payload)])
    assert len(va.fetch_file(f, session, sleep=lambda _s: None)) == 1


def test_corrupt_zip_does_not_raise():
    f = va.archive_files("X", "1d", 1_600_000_000_000, 1_602_000_000_000)[0]
    session = _Session([_Resp(200, b"bu bir zip degil")])
    assert va.fetch_file(f, session, sleep=lambda _s: None) == []


def test_resume_skips_stored_bars(tmp_path, monkeypatch):
    """Devam noktası Parquet'ten okunur; var olan barlar yeniden indirilmez."""
    start = int(datetime(2026, 6, 1, tzinfo=timezone.utc).timestamp() * 1000)
    now_ms = start + 20 * DAY
    rows = [_row(start + i * DAY, start + (i + 1) * DAY - 1) for i in range(20)]

    monkeypatch.setattr(va, "fetch_file", lambda f, s=None: va.parse_csv_zip(_zip(rows)))
    first = va.download_symbol("TESTUSDT", "1d", start_ms=start, end_ms=now_ms, root=tmp_path)
    second = va.download_symbol("TESTUSDT", "1d", start_ms=start, end_ms=now_ms, root=tmp_path)

    assert first > 0
    assert second == 0  # ikinci çalıştırma boş
