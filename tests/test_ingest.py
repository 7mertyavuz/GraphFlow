"""F0 testleri — ağ erişimi YOK, sahte oturum enjekte edilir."""

from __future__ import annotations

import json

import pytest

from engine.config import KLINES_LIMIT, TIMEFRAME_MS
from engine.ingest import store
from engine.ingest.binance_client import (
    BinanceClient,
    BinanceError,
    UnknownSymbolError,
    WeightTracker,
)
from engine.ingest.download import download_symbol
from engine.ingest.symbol_universe import (
    build_universe,
    parse_exchange_info,
    parse_s3_listing,
    split_quote,
)

TF = "4h"
STEP = TIMEFRAME_MS[TF]


# ---------------------------------------------------------------------------
# Sahte HTTP katmanı
# ---------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = text or (json.dumps(payload) if payload is not None else "")

    def json(self):
        if self._payload is None:
            raise ValueError("gövde JSON değil")
        return self._payload


class FakeSession:
    """Sıralı yanıt kuyruğu döndürür ve çağrıları kaydeder."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, dict(params or {})))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def make_klines(start_ms: int, n: int, step: int = STEP, price: float = 100.0):
    """Binance'in 12 elemanlı ham dizi formatında n mum üretir."""
    rows = []
    for i in range(n):
        ot = start_ms + i * step
        p = price + i
        rows.append(
            [
                ot,
                f"{p}",
                f"{p + 1}",
                f"{p - 1}",
                f"{p + 0.5}",
                "10.0",
                ot + step - 1,
                "1000.0",
                7,
                "5.0",
                "500.0",
                "0",
            ]
        )
    return rows


def client_with(responses, **kwargs):
    return BinanceClient(
        session=FakeSession(responses),
        sleep=lambda _s: None,
        weights=WeightTracker(sleep=lambda _s: None),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Sayfalama
# ---------------------------------------------------------------------------


def test_pagination_advances_cursor_and_stops_on_short_page():
    full = make_klines(0, KLINES_LIMIT)
    tail = make_klines(KLINES_LIMIT * STEP, 5)
    c = client_with([FakeResponse(payload=full), FakeResponse(payload=tail)])

    pages = list(c.iter_klines("BTCUSDT", TF, start_time=0))

    assert [len(p) for p in pages] == [KLINES_LIMIT, 5]
    # İkinci çağrı, ilk sayfanın son barından bir periyot sonra başlamalı.
    assert c.session.calls[1][1]["startTime"] == full[-1][0] + STEP
    # Kısa sayfa geldiğinde üçüncü istek atılmaz.
    assert len(c.session.calls) == 2


def test_pagination_stops_on_empty_page():
    c = client_with([FakeResponse(payload=make_klines(0, KLINES_LIMIT)), FakeResponse(payload=[])])
    pages = list(c.iter_klines("BTCUSDT", TF, start_time=0))
    assert len(pages) == 1


def test_pagination_has_no_duplicate_open_times():
    p1 = make_klines(0, KLINES_LIMIT)
    p2 = make_klines(KLINES_LIMIT * STEP, KLINES_LIMIT)
    p3 = make_klines(2 * KLINES_LIMIT * STEP, 3)
    c = client_with([FakeResponse(payload=p) for p in (p1, p2, p3)])

    times = [k.open_time for page in c.iter_klines("BTCUSDT", TF, 0) for k in page]
    assert len(times) == len(set(times))
    assert times == sorted(times)


# ---------------------------------------------------------------------------
# Rate-limit ve yeniden deneme
# ---------------------------------------------------------------------------


def test_retries_on_network_error_then_succeeds():
    c = client_with([ConnectionError("bağlantı koptu"), FakeResponse(payload=make_klines(0, 2))])
    assert len(c.klines("BTCUSDT", TF)) == 2


def test_retries_on_5xx():
    c = client_with([FakeResponse(status_code=502, text="bad gateway"), FakeResponse(payload=[])])
    assert c.klines("BTCUSDT", TF) == []


def test_429_respects_retry_after():
    slept: list[float] = []
    c = BinanceClient(
        session=FakeSession(
            [
                FakeResponse(status_code=429, headers={"Retry-After": "7"}, payload={}),
                FakeResponse(payload=make_klines(0, 1)),
            ]
        ),
        sleep=slept.append,
        weights=WeightTracker(sleep=lambda _s: None),
    )
    assert len(c.klines("BTCUSDT", TF)) == 1
    assert 7.0 in slept


def test_unknown_symbol_is_not_retried():
    c = client_with([FakeResponse(status_code=400, payload={"code": -1121, "msg": "Invalid symbol."})])
    with pytest.raises(UnknownSymbolError):
        c.klines("GHOSTUSDT", TF)
    assert len(c.session.calls) == 1


def test_gives_up_after_max_retries():
    c = client_with([ConnectionError("x")] * 3, max_retries=3)
    with pytest.raises(BinanceError):
        c.klines("BTCUSDT", TF)


def test_weight_tracker_waits_when_budget_exhausted():
    slept: list[float] = []
    now = [0.0]
    w = WeightTracker(limit=100, safety_ratio=1.0, sleep=slept.append, clock=lambda: now[0])
    for _ in range(50):
        w.acquire(2)
    assert slept == []
    w.acquire(2)  # bütçe doldu
    assert slept and slept[0] == pytest.approx(60.0)


def test_weight_tracker_adopts_server_header():
    w = WeightTracker(sleep=lambda _s: None)
    w.acquire(2)
    w.observe({"X-MBX-USED-WEIGHT-1M": "1234"})
    assert w.used == 1234


# ---------------------------------------------------------------------------
# Store — atomik yazım, artımlı append, resume
# ---------------------------------------------------------------------------


def test_append_and_read_roundtrip(tmp_path):
    store.append_klines("BTCUSDT", TF, make_klines(0, 5), root=tmp_path)
    df = store.read_klines("BTCUSDT", TF, root=tmp_path)

    assert list(df.columns) == list(store.COLUMNS)
    assert len(df) == 5
    assert df["open_time"].is_monotonic_increasing
    assert df["trades"].dtype == "int32"


def test_append_deduplicates_and_sorts(tmp_path):
    store.append_klines("BTCUSDT", TF, make_klines(0, 5), root=tmp_path)
    # Örtüşen aralık: 3 eski + 3 yeni bar
    added = store.append_klines("BTCUSDT", TF, make_klines(2 * STEP, 6), root=tmp_path)

    df = store.read_klines("BTCUSDT", TF, root=tmp_path)
    assert added == 3
    assert len(df) == 8
    assert df["open_time"].tolist() == sorted(set(df["open_time"].tolist()))


def test_append_last_write_wins_for_same_open_time(tmp_path):
    store.append_klines("BTCUSDT", TF, make_klines(0, 3, price=100.0), root=tmp_path)
    store.append_klines("BTCUSDT", TF, make_klines(0, 3, price=999.0), root=tmp_path)
    df = store.read_klines("BTCUSDT", TF, root=tmp_path)
    assert len(df) == 3
    assert df["open"].iloc[0] == pytest.approx(999.0)


def test_write_is_atomic_no_tmp_left_behind(tmp_path):
    store.append_klines("BTCUSDT", TF, make_klines(0, 4), root=tmp_path)
    leftovers = list((tmp_path / TF).glob("*.tmp"))
    assert leftovers == []


def test_last_open_time_and_empty_read(tmp_path):
    assert store.last_open_time("NOPE", TF, root=tmp_path) is None
    assert store.read_klines("NOPE", TF, root=tmp_path).empty

    store.append_klines("BTCUSDT", TF, make_klines(0, 4), root=tmp_path)
    assert store.last_open_time("BTCUSDT", TF, root=tmp_path) == 3 * STEP


# ---------------------------------------------------------------------------
# İndirme: resume ve yarım mum
# ---------------------------------------------------------------------------


def test_download_symbol_drops_unclosed_candle(tmp_path):
    n = 10
    now = 9 * STEP + STEP // 2  # 10. mum henüz kapanmadı
    c = client_with([FakeResponse(payload=make_klines(0, n))])

    written = download_symbol(c, "BTCUSDT", TF, now_ms=now, start_ms=0, root=tmp_path)
    df = store.read_klines("BTCUSDT", TF, root=tmp_path)

    assert written == 9
    assert df["open_time"].max() == 8 * STEP


def test_download_symbol_resumes_from_last_stored_bar(tmp_path):
    now = 20 * STEP
    c1 = client_with([FakeResponse(payload=make_klines(0, 10))])
    download_symbol(c1, "BTCUSDT", TF, now_ms=now, start_ms=0, root=tmp_path)

    c2 = client_with([FakeResponse(payload=make_klines(10 * STEP, 5))])
    written = download_symbol(c2, "BTCUSDT", TF, now_ms=now, start_ms=0, root=tmp_path)

    # İkinci çalıştırma baştan değil, 10. bardan devam etmeli.
    assert c2.session.calls[0][1]["startTime"] == 10 * STEP
    assert written == 5
    assert len(store.read_klines("BTCUSDT", TF, root=tmp_path)) == 15


def test_download_symbol_noop_when_up_to_date(tmp_path):
    now = 10 * STEP + 1
    c1 = client_with([FakeResponse(payload=make_klines(0, 10))])
    download_symbol(c1, "BTCUSDT", TF, now_ms=now, start_ms=0, root=tmp_path)

    c2 = client_with([])  # hiç istek atılmamalı
    assert download_symbol(c2, "BTCUSDT", TF, now_ms=now, start_ms=0, root=tmp_path) == 0
    assert c2.session.calls == []


# ---------------------------------------------------------------------------
# Sembol evreni (K-13)
# ---------------------------------------------------------------------------

_S3_XML = """<?xml version="1.0" encoding="UTF-8"?>
<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
  <Prefix>data/spot/monthly/klines/</Prefix>
  <IsTruncated>{truncated}</IsTruncated>
  {marker}
  <CommonPrefixes><Prefix>data/spot/monthly/klines/BTCUSDT/</Prefix></CommonPrefixes>
  <CommonPrefixes><Prefix>data/spot/monthly/klines/LUNAUSDT/</Prefix></CommonPrefixes>
  <CommonPrefixes><Prefix>data/spot/monthly/klines/ETHBTC/</Prefix></CommonPrefixes>
</ListBucketResult>
"""


def test_parse_s3_listing():
    symbols, marker = parse_s3_listing(_S3_XML.format(truncated="false", marker=""))
    assert symbols == ["BTCUSDT", "LUNAUSDT", "ETHBTC"]
    assert marker is None


def test_parse_s3_listing_truncated_returns_marker():
    xml = _S3_XML.format(truncated="true", marker="<NextMarker>x/</NextMarker>")
    _, marker = parse_s3_listing(xml)
    assert marker == "x/"


def test_split_quote():
    assert split_quote("BTCUSDT") == ("BTC", "USDT")
    assert split_quote("ETHBTC") == ("ETH", "BTC")
    assert split_quote("ETHEUR") is None


def test_universe_includes_delisted_symbols():
    """K-13: exchangeInfo'da olmayan ama arşivde geçen parite evrende kalmalı."""
    info = {
        "symbols": [
            {
                "symbol": "BTCUSDT",
                "baseAsset": "BTC",
                "quoteAsset": "USDT",
                "status": "TRADING",
                "isSpotTradingAllowed": True,
            }
        ]
    }
    universe = build_universe(exchange_info=info, archive_symbols=["BTCUSDT", "LUNAUSDT", "FTTUSDT"])
    by_symbol = {r["symbol"]: r for r in universe}

    assert set(by_symbol) == {"BTCUSDT", "LUNAUSDT", "FTTUSDT"}
    assert by_symbol["BTCUSDT"]["status"] == "TRADING"
    assert by_symbol["LUNAUSDT"]["status"] == "DELISTED"
    assert by_symbol["FTTUSDT"]["base_asset"] == "FTT"


def test_universe_ignores_non_target_quotes():
    universe = build_universe(archive_symbols=["BTCUSDT", "ETHEUR", "BNBTRY"])
    assert [r["symbol"] for r in universe] == ["BTCUSDT"]


def test_universe_preserves_symbol_ids():
    """symbol_id matris meta'sına indeks — asla yeniden numaralandırılmaz."""
    first = build_universe(archive_symbols=["BTCUSDT", "ETHUSDT"])
    ids = {r["symbol"]: r["symbol_id"] for r in first}

    second = build_universe(archive_symbols=["AAAUSDT", "BTCUSDT", "ETHUSDT"], previous=first)
    new_ids = {r["symbol"]: r["symbol_id"] for r in second}

    assert new_ids["BTCUSDT"] == ids["BTCUSDT"]
    assert new_ids["ETHUSDT"] == ids["ETHUSDT"]
    assert new_ids["AAAUSDT"] == max(ids.values()) + 1
    assert len({r["symbol_id"] for r in second}) == 3


def test_parse_exchange_info_filters_quote_assets():
    info = {
        "symbols": [
            {"symbol": "BTCUSDT", "baseAsset": "BTC", "quoteAsset": "USDT", "status": "TRADING"},
            {"symbol": "BTCEUR", "baseAsset": "BTC", "quoteAsset": "EUR", "status": "TRADING"},
        ]
    }
    assert set(parse_exchange_info(info)) == {"BTCUSDT"}
