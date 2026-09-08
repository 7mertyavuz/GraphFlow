"""F5 API testleri.

Kapsam, katmanın dürüstlük iddialarına birebir karşılık gelir:

* çıplak sayı dönmüyor (``StatEnvelope`` zarfı),
* oturum sayacı yalnızca **yeni arama** sayıyor (sayfalama hipotez testi değil),
* istatistik ekrandaki eşleşmelerden hesaplanıyor (ikinci arama yok),
* grafik karosu doğru sembolün barlarını çiziyor (yerel ↔ global indeks),
* normalizasyonun tek otoritesi motor (istemci ham nokta gönderir).
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

import engine.api.cache as cache_module
from engine.api.chart import build_chart
from engine.api.main import app, resolve_query, wrap_stat
from engine.api.cache import InMemoryCache
from engine.api.schemas import SearchRequest
from engine.config import N_POINTS
from engine.outcome.bars import BarStore

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_cache():
    """Her test kendi önbelleğiyle başlar.

    ``get_cache`` modül global'ini okur; singleton'ı değiştirmek onu içe
    aktarmış tüm modüller için geçerlidir (main, session).
    """
    previous = cache_module._cache_instance
    cache_module._cache_instance = InMemoryCache()
    yield cache_module._cache_instance
    cache_module._cache_instance = previous


@pytest.fixture(autouse=True)
def stub_freshness():
    """Tazelik gerçek parquet deposunu tarar; testte sabitlenir."""
    snapshot = {"4h": {"symbols": 1, "newest_open_time": 1_700_000_000_000, "stale_bars": 0.5, "limit_bars": 3, "ok": True}}
    with patch("engine.api.freshness.snapshot", return_value=snapshot), patch(
        "engine.api.freshness.data_as_of", return_value=1_700_000_000_000
    ), patch("engine.api.freshness.is_stale", return_value=False):
        yield


def _match_dict(i: int, **over) -> dict:
    data = {
        "symbol": f"SYM{i}",
        "symbol_id": i,
        "timeframe": "4h",
        "window_length": 24,
        "start_idx": 100,
        "end_idx": 123,
        "end_time": 1_600_000_000_000,
        "score": 0.9,
        "distance": 0.1,
        "amplitude": 10.0,
        "atr": 1.0,
        "percentile": 0.01,
        "warp_path": None,
    }
    data.update(over)
    return data


def _mock_result(n: int):
    result = MagicMock()
    matches = []
    for i in range(n):
        m = MagicMock()
        m.as_dict.return_value = _match_dict(i)
        m.end_time = 1_600_000_000_000
        m.window_length = 24
        matches.append(m)
    result.results = matches
    result.total = n
    result.elapsed_ms = 5.0
    result.discriminative = True
    result.warning = None
    # MagicMock her alanı otomatik üretir; JSON'a serileşmeyen bir mock
    # önbelleğe yazılırken patlıyordu. Yanıt sözleşmesindeki her alan
    # burada da açıkça verilmeli.
    result.structure_read = None
    result.structure_filtered = False
    result.structure_relaxed = False
    result.structure_stable = True
    result.null_dist = {}
    return result


def _query_points() -> list[float]:
    """Belirgin bir çanak — düz olmayan geçerli çizim."""
    return list(np.linspace(-1, 1, 40) ** 2 * -1)


# ---------------------------------------------------------------------------
# Zarf
# ---------------------------------------------------------------------------


def test_stat_envelope_completeness():
    envelope = wrap_stat(
        val=1.5,
        ci=(1.0, 2.0),
        ci_method="bootstrap",
        null_val=0.0,
        n_events=100,
        n_months=12,
        significant=True,
        verdict="anlamlı fark",
        design_effect=1.2,
    )
    assert envelope.value == 1.5
    assert envelope.ci95 == [1.0, 2.0]
    assert envelope.ci_method == "bootstrap"
    assert envelope.null == 0.0
    assert envelope.n_events == 100
    assert envelope.n_months == 12
    assert envelope.significant is True
    assert envelope.design_effect == 1.2
    assert envelope.shadow is None
    assert envelope.unit == "R"


def test_significant_verdict():
    assert wrap_stat(0.01, (-0.05, 0.07), "bootstrap", significant=False).significant is False
    assert wrap_stat(0.05, (0.01, 0.09), "bootstrap", significant=True).significant is True


# ---------------------------------------------------------------------------
# Sağlık
# ---------------------------------------------------------------------------


def test_health_reports_staleness_from_store():
    stale = {"1d": {"symbols": 3, "newest_open_time": 100, "stale_bars": 500.0, "limit_bars": 3, "ok": False}}
    with patch("engine.api.freshness.snapshot", return_value=stale):
        response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["stale_warning"] is True
    assert body["data_as_of"] == 100
    assert body["timeframes"]["1d"]["stale_bars"] == 500.0


# ---------------------------------------------------------------------------
# Sorgu çözümleme — normalizasyonun tek otoritesi motor
# ---------------------------------------------------------------------------


def test_raw_drawing_is_normalized_server_side():
    """İstemci ham nokta gönderir; sunucu 32 noktaya indirger ve z-score'lar."""
    vector = resolve_query(SearchRequest(points=_query_points()))
    assert vector.shape == (N_POINTS,)
    assert vector.mean() == pytest.approx(0.0, abs=1e-9)
    assert vector.std() == pytest.approx(1.0, abs=1e-9)


def test_already_normalized_vector_is_idempotent():
    once = resolve_query(SearchRequest(points=_query_points()))
    twice = resolve_query(SearchRequest(points=[float(v) for v in once]))
    assert np.allclose(once, twice, atol=1e-9)


def test_flat_drawing_is_rejected():
    """σ = 0 → şekil taşımayan sorgu. Motora hiç ulaşmamalı."""
    response = client.post("/api/search", json={"points": [1.0] * 32})
    assert response.status_code == 400


def test_xy_pairs_are_accepted():
    """İstemci ham (x, y) gönderir: çizim hızı düzensizdir, x ızgarası bilgidir."""
    ys = _query_points()
    # Kullanıcı ortada yavaşlamış: noktalar x'te düzgün dağılmıyor.
    xs = np.sqrt(np.linspace(0.0, 1.0, len(ys)))
    vector = resolve_query(SearchRequest(points=[[float(x), float(y)] for x, y in zip(xs, ys)]))
    assert vector.shape == (N_POINTS,)
    assert vector.std() == pytest.approx(1.0, abs=1e-9)


def test_xy_pairs_use_the_x_grid():
    """x sütunu yok sayılırsa düzensiz çizim yanlış şekle dönüşür."""
    ys = _query_points()
    uneven_x = np.sqrt(np.linspace(0.0, 1.0, len(ys)))

    with_x = resolve_query(
        SearchRequest(points=[[float(x), float(y)] for x, y in zip(uneven_x, ys)])
    )
    assume_even = resolve_query(SearchRequest(points=[float(y) for y in ys]))
    assert not np.allclose(with_x, assume_even, atol=1e-3)


def test_backtracking_drawing_is_not_reordered():
    """Sola dönen el sorguyu bozmamalı (bkz. test_normalize:monotone_xy)."""
    ys = _query_points()
    xs = list(np.linspace(0.0, 1.0, len(ys)))

    clean = resolve_query(SearchRequest(points=[[x, float(y)] for x, y in zip(xs, ys)]))
    # Son çeyreği çizip geri dönerek yeniden çiz.
    cut = int(len(ys) * 0.75)
    messy_pts = [[x, float(y)] for x, y in zip(xs, ys)]
    messy_pts = messy_pts[:] + [[xs[i], float(ys[i])] for i in range(cut, len(ys))]
    messy = resolve_query(SearchRequest(points=messy_pts))
    np.testing.assert_allclose(clean, messy, atol=1e-9)


def test_single_xy_point_is_rejected():
    """(1, 2) dizinin `size` değeri 2'dir ama tek noktadır."""
    response = client.post("/api/search", json={"points": [[0.5, 0.5]]})
    assert response.status_code in (400, 422)


def test_malformed_point_pairs_are_rejected():
    response = client.post("/api/search", json={"points": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]})
    assert response.status_code in (400, 422)


def test_oversized_drawing_is_rejected():
    """Üst sınır: dev yük interpolasyonu şişirmesin."""
    response = client.post("/api/search", json={"points": [0.0, 1.0] * 4_096})
    assert response.status_code == 422


def test_search_requires_a_query():
    assert client.post("/api/search", json={}).status_code == 400


def test_unknown_template_is_rejected():
    response = client.post("/api/search", json={"template_id": "yok_boyle_bir_sey"})
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Oturum sayacı
# ---------------------------------------------------------------------------


def test_session_counter_counts_distinct_shapes():
    """Sayaç AYRI şekilleri sayar — aynı şekli tekrar sormak yeni test değil."""
    headers = {"X-Session-ID": "oturum-1"}
    farkli_sekil = list(np.sin(np.linspace(0, 3 * np.pi, 40)))

    with patch("engine.api.main.get_engine") as mock_engine:
        mock_engine.return_value.search.return_value = _mock_result(0)
        mock_engine.return_value.compute_warp_paths.return_value = []

        first = client.post("/api/search", json={"points": _query_points()}, headers=headers)
        assert first.json()["session"]["session_queries"] == 1
        assert first.json()["session"]["multiple_comparison_warning"] is False

        # Aynı şekil yeniden: hipotez sayısı değişmez.
        again = client.post("/api/search", json={"points": _query_points()}, headers=headers)
        assert again.json()["session"]["session_queries"] == 1

        # Farklı şekil: ikinci hipotez.
        second = client.post("/api/search", json={"points": farkli_sekil}, headers=headers)
        session = second.json()["session"]
        assert session["session_queries"] == 2
        assert session["multiple_comparison_warning"] is True
        assert session["adjusted_alpha"] == 0.025
        assert session["warning_text"]


def test_pagination_does_not_inflate_session_counter():
    """"Daha fazla" yeni bir hipotez testi değildir — Bonferroni cezası yok."""
    headers = {"X-Session-ID": "oturum-2"}
    with patch("engine.api.main.get_engine") as mock_engine:
        mock_engine.return_value.search.return_value = _mock_result(20)
        mock_engine.return_value.compute_warp_paths.return_value = []
        created = client.post("/api/search", json={"points": _query_points()}, headers=headers)

    search_id = created.json()["search_id"]
    for _ in range(3):
        page = client.get(f"/api/search/{search_id}?offset=12&limit=12", headers=headers)
        assert page.status_code == 200
    assert page.json()["session"]["session_queries"] == 1


def test_counter_window_expires():
    """Süresiz sayaç hız limitini kalıcı kilide, oturumu sonsuz cezaya çevirirdi."""
    cache = InMemoryCache()
    clock = {"t": 1_000.0}
    with patch("engine.api.cache.time.time", lambda: clock["t"]):
        assert asyncio.run(cache.incr("k", 60)) == 1
        assert asyncio.run(cache.incr("k", 60)) == 2
        assert asyncio.run(cache.count("k")) == 2

        clock["t"] += 61
        assert asyncio.run(cache.count("k")) == 0
        assert asyncio.run(cache.incr("k", 60)) == 1


def test_count_does_not_create_a_counter():
    cache = InMemoryCache()
    assert asyncio.run(cache.count("hic-yok")) == 0


# ---------------------------------------------------------------------------
# Sayfalama
# ---------------------------------------------------------------------------


def test_pagination_serves_from_cache():
    headers = {"X-Session-ID": "oturum-3"}
    with patch("engine.api.main.get_engine") as mock_engine:
        mock_engine.return_value.search.return_value = _mock_result(20)
        mock_engine.return_value.compute_warp_paths.return_value = []

        created = client.post("/api/search", json={"points": _query_points()}, headers=headers)
        assert created.status_code == 200
        assert len(created.json()["results"]) == 12  # varsayılan limit
        search_id = created.json()["search_id"]

        mock_engine.return_value.search.reset_mock()
        page = client.get(f"/api/search/{search_id}?offset=12&limit=12", headers=headers)

        assert len(page.json()["results"]) == 8
        assert page.json()["results"][0]["symbol"] == "SYM12"
        # Tüm matris yeniden skorlanmaz (K-08)
        mock_engine.return_value.search.assert_not_called()


def test_match_carries_window_start_time():
    with patch("engine.api.main.get_engine") as mock_engine:
        mock_engine.return_value.search.return_value = _mock_result(1)
        mock_engine.return_value.compute_warp_paths.return_value = []
        response = client.post("/api/search", json={"points": _query_points()})

    match = response.json()["results"][0]
    step = 4 * 3_600_000
    assert match["start_time"] == match["end_time"] - 23 * step


def test_missing_search_is_404():
    assert client.get("/api/search/yok-boyle-bir-id").status_code == 404


def test_live_mode_has_no_outcome_stats():
    """Radar eşleşmesinin ileri penceresi yoktur; istatistik uydurulmaz."""
    with patch("engine.api.main.get_engine") as mock_engine:
        mock_engine.return_value.search.return_value = _mock_result(3)
        mock_engine.return_value.compute_warp_paths.return_value = []
        created = client.post(
            "/api/search", json={"points": _query_points(), "mode": "live"}
        )

    search_id = created.json()["search_id"]
    assert client.get(f"/api/search/{search_id}/stats").status_code == 400


def test_stats_use_the_matches_the_user_sees():
    """``/stats`` ikinci bir arama çalıştırmaz; ekrandaki olaylar girdidir."""
    with patch("engine.api.main.get_engine") as mock_engine:
        mock_engine.return_value.search.return_value = _mock_result(4)
        mock_engine.return_value.compute_warp_paths.return_value = []
        created = client.post("/api/search", json={"points": _query_points()})
        search_id = created.json()["search_id"]

        outcome = MagicMock()
        outcome.stats = {}
        outcome.matches = 4
        outcome.events = 4
        outcome.dropped_separation = 0
        outcome.dropped_filters = 0
        outcome.direction = "long"
        outcome.shadow_report = {}

        mock_engine.return_value.search.reset_mock()
        with patch("engine.api.main.get_store"), patch("engine.api.main.get_pools"), patch(
            "engine.api.main.run_events", return_value=outcome
        ) as run:
            response = client.get(f"/api/search/{search_id}/stats")

        assert response.status_code == 200
        assert response.json()["n_events"] == 4
        assert response.json()["disclaimer"]
        mock_engine.return_value.search.assert_not_called()

        events = run.call_args[0][0]
        assert events.size == 4
        assert list(events["t0"]) == [123] * 4  # eşleşmelerin bitiş barı


# ---------------------------------------------------------------------------
# Grafik karosu
# ---------------------------------------------------------------------------


def _two_symbol_store() -> BarStore:
    """İki sembol: ilki 200 bar (fiyat ~100), ikincisi 200 bar (fiyat ~5000)."""
    rng = np.random.default_rng(7)
    arrays = {}
    for sid, base in ((1, 100.0), (2, 5000.0)):
        close = base * (1 + 0.01 * np.cumsum(rng.normal(size=200)))
        close = np.abs(close) + base * 0.1
        arrays[sid] = {
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "open_time": (1_600_000_000_000 + np.arange(200) * 14_400_000),
            "symbol": f"S{sid}",
        }
    return BarStore.from_arrays(arrays)


def test_chart_uses_symbol_local_indices():
    """``start_idx`` sembol-yereldir; ofset unutulursa başka sembol çizilir."""
    store = _two_symbol_store()
    chart = build_chart(store, "S2", 2, "4h", start_idx=50, end_idx=73)

    prices = [c.close for c in chart.ohlcv]
    assert min(prices) > 1000  # ikinci sembolün fiyat bandı
    expected = store.close[store.offset[2] + 50]
    assert chart.ohlcv[chart.highlight_start].close == pytest.approx(expected)


def test_chart_highlight_is_relative_to_returned_bars():
    store = _two_symbol_store()
    chart = build_chart(store, "S1", 1, "4h", start_idx=80, end_idx=103)

    assert 0 <= chart.highlight_start < chart.highlight_end < len(chart.ohlcv)
    assert chart.highlight_end - chart.highlight_start == 23
    # Bağlam barları: formasyon nereden geldi, sonra ne oldu
    assert chart.highlight_start > 0
    assert chart.highlight_end < len(chart.ohlcv) - 1


def test_chart_times_are_real_seconds():
    store = _two_symbol_store()
    chart = build_chart(store, "S1", 1, "4h", start_idx=10, end_idx=33)
    assert chart.ohlcv[0].time == 1_600_000_000_000 // 1000 + 0  # ms → s
    assert chart.ohlcv[1].time - chart.ohlcv[0].time == 14_400


def test_blueprint_overlay_sits_on_the_price_scale():
    """Blueprint, normalizasyonun tersi: z-score → log fiyat → fiyat."""
    store = _two_symbol_store()
    query = np.linspace(-1.5, 1.5, N_POINTS)
    chart = build_chart(store, "S2", 2, "4h", start_idx=40, end_idx=103, query=query)

    assert len(chart.blueprint_overlay) == N_POINTS
    window = store.close[store.offset[2] + 40 : store.offset[2] + 104]
    values = [p.value for p in chart.blueprint_overlay]
    assert min(values) > window.min() * 0.3
    assert max(values) < window.max() * 3.0
    # Zaman ekseni pencerenin içinde kalmalı
    times = [p.time for p in chart.blueprint_overlay]
    assert times == sorted(times)
    assert chart.ohlcv[chart.highlight_start].time <= times[0]
    assert times[-1] <= chart.ohlcv[chart.highlight_end].time


def test_warped_overlay_needs_a_path():
    store = _two_symbol_store()
    query = np.linspace(-1.5, 1.5, N_POINTS)
    without = build_chart(store, "S1", 1, "4h", start_idx=40, end_idx=71, query=query)
    assert without.warped_overlay == []
    assert without.warp_amount is None

    path = [[i, i] for i in range(N_POINTS)]  # köşegen: bükülme yok
    with_path = build_chart(
        store, "S1", 1, "4h", start_idx=40, end_idx=71, query=query, warp_path=path
    )
    assert len(with_path.warped_overlay) == N_POINTS
    assert with_path.warp_amount == pytest.approx(0.0)


def test_overlay_times_are_strictly_increasing_on_short_windows():
    """24 barlık pencerede 32 nokta aynı bara düşerse grafik seriyi reddeder."""
    store = _two_symbol_store()
    query = np.linspace(-1.5, 1.5, N_POINTS)
    path = [[i, i] for i in range(N_POINTS)]
    chart = build_chart(
        store, "S1", 1, "4h", start_idx=40, end_idx=63, query=query, warp_path=path
    )

    for overlay in (chart.blueprint_overlay, chart.warped_overlay):
        times = [p.time for p in overlay]
        assert len(times) == 24  # bar sayısına indirgendi
        assert times == sorted(set(times))


def test_chart_clamps_out_of_range_window():
    store = _two_symbol_store()
    chart = build_chart(store, "S1", 1, "4h", start_idx=190, end_idx=400)
    assert len(chart.ohlcv) > 0
    assert chart.highlight_end < len(chart.ohlcv)


def test_unknown_symbol_chart_is_404():
    with patch("engine.api.main.get_engine") as mock_engine:
        mock_engine.return_value.symbol_id_of.return_value = None
        with patch("engine.api.main.get_store", return_value=_two_symbol_store()):
            assert client.get("/api/chart/YOKUSDT?start=0&end=10").status_code == 404


def test_symbol_id_space_is_per_timeframe(tmp_path):
    """Aynı id iki zaman diliminde iki farklı sembole düşer.

    Tek global harita tutmak, 1d eşleşmelerinin 4h sembol adıyla
    etiketlenmesi demekti — sessiz ve tehlikeli bir hata.
    """
    from engine.matrix.build import symbols_file
    from engine.search.engine import SearchEngine

    (tmp_path / symbols_file("4h")).write_text('{"AAVEUSDT": 0}', encoding="utf-8")
    (tmp_path / symbols_file("1d")).write_text('{"ZRXUSDT": 0}', encoding="utf-8")

    engine = SearchEngine(matrix_root=tmp_path)
    assert engine.symbol_name(0, "4h") == "AAVEUSDT"
    assert engine.symbol_name(0, "1d") == "ZRXUSDT"
    assert engine.symbol_id_of("zrxusdt", "1d") == 0
    assert engine.symbol_id_of("ZRXUSDT", "4h") is None
    # Haritası olmayan id gizlenmez, "#id" olarak görünür
    assert engine.symbol_name(99, "1d") == "#99"


# ---------------------------------------------------------------------------
# Şablonlar ve bulgular
# ---------------------------------------------------------------------------


def test_templates_expose_vectors_and_descriptions():
    response = client.get("/api/templates")
    assert response.status_code == 200
    templates = response.json()
    assert len(templates) == 14
    for t in templates:
        assert len(t["vector"]) == N_POINTS
        assert t["name"] and t["category"]


def test_findings_report_every_stage():
    """Elenen bulgular da raporlanır — 'anlamlı 2' sayısı tek başına yanıltıcı."""
    body = client.get("/api/findings").json()
    assert len(body["stages"]) == 6
    assert "Bonferroni" in body["methodology"]
    for stage in body["stages"]:
        assert 0 <= stage["significant"] <= stage["total"]


def test_findings_counts_come_from_the_measurement_files():
    """Sayılar elle yazılamaz.

    Sabit kodluyken veriyle çelişiyorlardı: F4.5 Bonferroni "14/52" yazıyordu,
    ``f45_bonferroni.json`` ise 2 diyor. Dürüstlük sayfasının kendi ölçümüne
    uymaması, sayfanın anlatmaya çalıştığı şeyin tam tersidir.
    """
    from engine.api.main import _load_findings_file

    rows = _load_findings_file("f45_bonferroni.json")
    if not rows:
        pytest.skip("ölçüm dosyası yok (data/f3)")

    measurable = [r for r in rows if r.get("olculebilir")]
    expected = sum(1 for r in measurable if r.get("bonf_anlamli"))

    body = client.get("/api/findings").json()
    bonferroni = next(s for s in body["stages"] if "Bonferroni" in s["stage"])
    assert bonferroni["significant"] == expected
    assert bonferroni["total"] == len(measurable)


def test_replication_stage_counts_only_same_direction_agreement():
    """F4.7: iki dilimde de anlamlı VE aynı işaretli hücreler sayılır.

    İşaret dönüyorsa bu replikasyon değil çelişkidir; saymak, gürültüyü
    kanıt diye sunmak olurdu.
    """
    from engine.api.main import _load_findings_file, _replicated

    if not _load_findings_file("f45_raw_4h.json"):
        pytest.skip("4h ölçümü yok (data/f3)")

    one = {(r["sablon"], r["yon"], r["konf"]): r for r in _load_findings_file("f45_raw.json")}
    four = {(r["sablon"], r["yon"], r["konf"]): r for r in _load_findings_file("f45_raw_4h.json")}

    def sig(r):
        lo, hi = r.get("blok_alt"), r.get("blok_ust")
        return lo is not None and hi is not None and (lo > 0.0 or hi < 0.0)

    expected = sum(
        1 for k, r in one.items()
        if k in four and sig(r) and sig(four[k]) and r["edge"] * four[k]["edge"] > 0
    )
    assert _replicated() == expected

    # Ters işaretli hücreler sayılmamalı.
    opposite = sum(
        1 for k, r in one.items()
        if k in four and sig(r) and sig(four[k]) and r["edge"] * four[k]["edge"] < 0
    )
    assert _replicated() + opposite <= len(one)


def test_bonferroni_cannot_increase_the_significant_count():
    """Düzeltme bir sayıyı artıramaz; artıyorsa aşamalar karışmıştır."""
    body = client.get("/api/findings").json()
    by_stage = {s["stage"]: s for s in body["stages"]}
    block = next(s for name, s in by_stage.items() if "ay-bloklu" in name)
    bonf = next(s for name, s in by_stage.items() if "Bonferroni" in name)
    if block["total"] == 0 or bonf["total"] == 0:
        pytest.skip("ölçüm dosyası yok (data/f3)")
    assert bonf["total"] == block["total"], "aynı test ailesi olmalı"
    assert bonf["significant"] <= block["significant"]


# ---------------------------------------------------------------------------
# Radar önbelleği (docs/01-mimari.md §6)
# ---------------------------------------------------------------------------


def test_radar_key_only_for_library_templates():
    """Serbest çizim önbelleğe alınmaz: anahtar uzayı sınırsız, isabet ~0."""
    from engine.api.main import radar_key

    live_template = SearchRequest(template_id="head_and_shoulders", mode="live")
    assert radar_key(live_template, [24, 40]) is not None

    # Tarihsel mod: Radar değil.
    assert radar_key(SearchRequest(template_id="head_and_shoulders", mode="historical"), [24]) is None
    # Serbest çizim: şablon yok.
    assert radar_key(SearchRequest(points=_query_points(), mode="live"), [24]) is None


def test_radar_key_separates_every_parameter():
    """Aynı anahtar farklı parametreye düşerse yanlış sonuç servis edilir."""
    from engine.api.main import radar_key

    base = dict(template_id="bull_flag", mode="live")
    key = radar_key(SearchRequest(**base, timeframe="4h", tolerance="medium"), [24, 40])

    assert key != radar_key(SearchRequest(**base, timeframe="1d", tolerance="medium"), [24, 40])
    assert key != radar_key(SearchRequest(**base, timeframe="4h", tolerance="strict"), [24, 40])
    assert key != radar_key(SearchRequest(**base, timeframe="4h", tolerance="medium"), [24, 64])
    assert key != radar_key(
        SearchRequest(**base, timeframe="4h", tolerance="medium", min_amplitude=20.0), [24, 40]
    )
    # Pencere sırası anahtarı değiştirmemeli.
    assert key == radar_key(SearchRequest(**base, timeframe="4h", tolerance="medium"), [40, 24])


def test_radar_cache_serves_second_call_without_rescanning(fresh_cache):
    """İkinci çağrı matrisi yeniden taramamalı ama tazeliği yeniden okumalı."""
    engine = MagicMock()
    engine.search.return_value = _mock_result(3)
    engine.compute_warp_paths.return_value = []
    engine.symbols_for.return_value = {}

    payload = {"template_id": "bull_flag", "mode": "live", "timeframe": "4h", "limit": 3}
    with patch("engine.api.main.get_engine", return_value=engine), patch(
        "engine.api.main.REFINE_MATCHES", False
    ):
        first = client.post("/api/search", json=payload, headers={"X-Session-Id": "r1"})
        second = client.post("/api/search", json=payload, headers={"X-Session-Id": "r1"})

    assert first.status_code == second.status_code == 200
    # Motor yalnız BİR kez tarandı.
    assert engine.search.call_count == 1
    # Aynı search_id → sayfalama ve istatistik tutarlı kalır.
    assert first.json()["search_id"] == second.json()["search_id"]
    # Aynı hipotez → sayaç ARTMAZ (Bonferroni ailesi ayrı şekil sayar).
    assert second.json()["session"]["session_queries"] == 1


def test_historical_search_is_not_cached(fresh_cache):
    """Tarihsel sorgu her seferinde taranır — Radar önbelleği ona ait değil."""
    engine = MagicMock()
    engine.search.return_value = _mock_result(2)
    engine.compute_warp_paths.return_value = []
    engine.symbols_for.return_value = {}

    payload = {"template_id": "bull_flag", "mode": "historical", "timeframe": "4h", "limit": 2}
    with patch("engine.api.main.get_engine", return_value=engine), patch(
        "engine.api.main.REFINE_MATCHES", False
    ):
        client.post("/api/search", json=payload, headers={"X-Session-Id": "h1"})
        client.post("/api/search", json=payload, headers={"X-Session-Id": "h1"})

    assert engine.search.call_count == 2


# ---------------------------------------------------------------------------
# Oturum sayacı ayrı hipotez sayar
# ---------------------------------------------------------------------------


def test_fingerprint_is_shape_and_parameters():
    """Aynı şekil + aynı parametre = aynı parmak izi."""
    from engine.api.main import query_fingerprint

    ys = _query_points()
    vector = resolve_query(SearchRequest(points=ys))
    a = SearchRequest(points=ys, timeframe="4h", tolerance="medium")
    b = SearchRequest(points=list(ys), timeframe="4h", tolerance="medium")
    assert query_fingerprint(a, vector, [24, 40]) == query_fingerprint(b, vector, [24, 40])

    # Parametre değişince ayrı hipotez.
    other = SearchRequest(points=ys, timeframe="1d", tolerance="medium")
    assert query_fingerprint(a, vector, [24, 40]) != query_fingerprint(other, vector, [24, 40])

    # Şablon ile çizim ayrı parmak izi taşır.
    tmpl = SearchRequest(template_id="bull_flag", timeframe="4h", tolerance="medium")
    assert query_fingerprint(tmpl, vector, [24, 40]).startswith("t:")
    assert query_fingerprint(a, vector, [24, 40]).startswith("d:")


def test_repeating_a_query_does_not_inflate_bonferroni(fresh_cache):
    """Açık bırakılmış bir Radar sekmesi α'yı zamanla küçültmemeli."""
    engine = MagicMock()
    engine.search.return_value = _mock_result(2)
    engine.compute_warp_paths.return_value = []
    engine.symbols_for.return_value = {}

    same = {"template_id": "bull_flag", "mode": "historical", "timeframe": "4h", "limit": 2}
    other = {**same, "tolerance": "strict"}

    with patch("engine.api.main.get_engine", return_value=engine), patch(
        "engine.api.main.REFINE_MATCHES", False
    ):
        r1 = client.post("/api/search", json=same, headers={"X-Session-Id": "s9"})
        r2 = client.post("/api/search", json=same, headers={"X-Session-Id": "s9"})
        r3 = client.post("/api/search", json=other, headers={"X-Session-Id": "s9"})

    assert r1.json()["session"]["session_queries"] == 1
    assert r2.json()["session"]["session_queries"] == 1  # aynı hipotez
    assert r3.json()["session"]["session_queries"] == 2  # farklı tolerans → ayrı test
    # α ayrı hipotez sayısına bölünür.
    assert r3.json()["session"]["adjusted_alpha"] == pytest.approx(0.05 / 2)
