"""F4 — Outcome Engine testleri (K-06, K-12, K-16).

Çıkış şartı: rastgele pencerelerde 2:1 başarı ≈ %33, 1:1 ≈ %50, beklenti ≈ 0R.
Bu değerler teorik null'dan anlamlı şekilde sapıyorsa triple-barrier
uygulamasında hata vardır (lookahead, yanlış ATR penceresi, bar sıralaması) ve
**erken yakalanır**. Bu testler arama kalitesinden bağımsızdır.
"""

from __future__ import annotations

import numpy as np
import pytest

from engine.config import (
    MIN_ATR_PCT,
    MIN_BARS_SINCE_LISTING,
    ROUNDTRIP_FEE_PCT,
    TIME_BARRIER_RATIO,
)
from engine.normalize.atr import wilder_atr
from engine.outcome.bars import BarStore
from engine.outcome.metrics import (
    bootstrap_diff_ci,
    bootstrap_mean_ci,
    distribution,
    summarize,
    wilson_interval,
)
from engine.outcome.triple_barrier import (
    EVENT_DTYPE,
    OUTCOME_FORCED,
    OUTCOME_SL,
    OUTCOME_TIME,
    OUTCOME_TP,
    eligible,
    enforce_forward_separation,
    evaluate,
    evaluate_all_configs,
    theoretical_null,
    time_barrier,
)


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------


def martingale_ohlc(n: int, sigma: float, rng: np.random.Generator, start: float = 100.0):
    """Fiyatı martingale olan seri (log drift = −σ²/2).

    Teorik null ``P(üst) = k_sl/(k_tp+k_sl)`` driftsiz yürüyüş varsayar.
    Log getirilerin ortalaması 0 olsaydı **fiyat** yukarı sürüklenirdi (Itô);
    testin ölçtüğü şey null'dan sapma değil, o sürüklenme olurdu.
    """
    steps = rng.normal(-0.5 * sigma**2, sigma, n)
    close = start * np.exp(np.cumsum(steps))
    open_ = np.empty(n)
    open_[0] = close[0]
    open_[1:] = close[:-1]
    wick = np.abs(rng.normal(0, sigma * 0.4, (2, n)))
    high = np.maximum(open_, close) * (1 + wick[0])
    low = np.minimum(open_, close) * (1 - wick[1])
    return open_, high, low, close


def random_event_dataset(
    n_symbols: int = 40, n_bars: int = 600, sigma: float = 0.04, seed: int = 7, length: int = 40
):
    """Rastgele pencereler — formasyon YOK, yalnızca gürültü."""
    rng = np.random.default_rng(seed)
    arrays, events = {}, []

    for sid in range(n_symbols):
        open_, high, low, close = martingale_ohlc(n_bars, sigma, rng)
        arrays[sid] = {"open": open_, "high": high, "low": low, "close": close}
        atr = wilder_atr(high, low, close)

        horizon = time_barrier(length)
        for t0 in range(MIN_BARS_SINCE_LISTING + 5, n_bars - horizon - 1, horizon):
            if np.isfinite(atr[t0]):
                events.append((sid, t0, length, atr[t0], t0 * 86_400_000))

    store = BarStore.from_arrays(arrays)
    ev = np.empty(len(events), dtype=EVENT_DTYPE)
    for i, row in enumerate(events):
        ev[i] = row
    return ev, store


def simple_store(open_, high, low, close, sid: int = 0) -> BarStore:
    return BarStore.from_arrays(
        {sid: {"open": open_, "high": high, "low": low, "close": close}}
    )


def one_event(sid=0, t0=30, length=24, atr=2.0) -> np.ndarray:
    ev = np.empty(1, dtype=EVENT_DTYPE)
    ev[0] = (sid, t0, length, atr, 0)
    return ev


# ---------------------------------------------------------------------------
# ÇIKIŞ ŞARTI — rastgele pencerelerde teorik null
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def random_dataset():
    return random_event_dataset()


@pytest.mark.parametrize("config,k_tp,k_sl", [("2:1", 2.0, 1.0), ("1:1", 1.0, 1.0)])
def test_random_windows_match_theoretical_null(random_dataset, config, k_tp, k_sl):
    """Rastgele pencerelerde başarı oranı teorik null'a yakın olmalı.

    Ölçüm **karara bağlanmış** olaylar üzerindedir (tp veya sl): teorik null,
    "hangisine önce çarpılır" sorusunun cevabıdır; zaman bariyerinden çıkan
    olaylar bu soruyu yanıtlamaz.
    """
    events, store = random_dataset
    events = events[eligible(events, store)]
    results = evaluate(events, store, k_tp, k_sl)

    tp = int((results["outcome"] == OUTCOME_TP).sum())
    sl = int((results["outcome"] == OUTCOME_SL).sum())
    decided = tp + sl
    oran = tp / decided
    null = theoretical_null(k_tp, k_sl)
    lo, hi = wilson_interval(tp, decided)

    print(f"\n{config}: karara bağlanan {decided} olay, başarı %{100*oran:.1f} "
          f"(null %{100*null:.1f}, GA [%{100*lo:.1f}, %{100*hi:.1f}])")

    assert decided > 300, "yeterli karara bağlanmış olay yok"
    assert lo <= null <= hi, f"{config}: null {null:.3f} güven aralığının dışında"


def test_random_windows_expectancy_is_zero(random_dataset):
    """Rastgele pencerelerde beklenti ≈ 0R olmalı (GA sıfırı içermeli)."""
    events, store = random_dataset
    events = events[eligible(events, store)]
    results = evaluate(events, store, 2.0, 1.0)

    r = results["r_gross"]
    lo, hi = bootstrap_mean_ci(r, samples=2000)
    print(f"\nbeklenti {r.mean():+.4f}R, %95 GA [{lo:+.4f}, {hi:+.4f}], n={r.size}")
    assert lo <= 0.0 <= hi, "rastgele pencerelerde beklenti sıfırdan anlamlı sapıyor"


# ---------------------------------------------------------------------------
# Lookahead — tüm istatistik katmanının geçerliliği buna bağlı
# ---------------------------------------------------------------------------


def test_outcome_uses_only_bars_after_t0():
    """t₀ SONRASI barlar değişince sonuç değişmeli; ÖNCESİ değişince değişmemeli."""
    rng = np.random.default_rng(3)
    open_, high, low, close = martingale_ohlc(200, 0.03, rng)
    atr = wilder_atr(high, low, close)
    t0 = 100

    base = evaluate(one_event(t0=t0, atr=atr[t0]), simple_store(open_, high, low, close), 2.0, 1.0)

    # (a) t₀'dan ÖNCEKİ barları boz → sonuç aynı kalmalı
    o2, h2, l2, c2 = open_.copy(), high.copy(), low.copy(), close.copy()
    h2[:t0] *= 3.0
    l2[:t0] /= 3.0
    before = evaluate(one_event(t0=t0, atr=atr[t0]), simple_store(o2, h2, l2, c2), 2.0, 1.0)
    assert before["r_gross"][0] == pytest.approx(base["r_gross"][0])
    assert before["outcome"][0] == base["outcome"][0]

    # (b) t₀'dan SONRAKİ barları boz → sonuç değişmeli
    o3, h3, l3, c3 = open_.copy(), high.copy(), low.copy(), close.copy()
    h3[t0 + 1 :] *= 5.0
    after = evaluate(one_event(t0=t0, atr=atr[t0]), simple_store(o3, h3, l3, c3), 2.0, 1.0)
    assert after["outcome"][0] == OUTCOME_TP


def test_atr_input_is_computed_without_lookahead():
    """ATR'nin kendisi t₀'a kadarki barlardan gelmeli (K-16.4)."""
    rng = np.random.default_rng(5)
    _, high, low, close = martingale_ohlc(300, 0.03, rng)
    t0 = 150
    tam = wilder_atr(high, low, close)[t0]
    kesik = wilder_atr(high[: t0 + 1], low[: t0 + 1], close[: t0 + 1])[-1]
    assert tam == pytest.approx(kesik, rel=0, abs=0)


# ---------------------------------------------------------------------------
# Bariyer mekaniği — tuzaklar
# ---------------------------------------------------------------------------


def test_same_bar_tp_and_sl_counts_as_sl():
    """Muhafazakâr varsayım: aynı barda ikisi de vurulduysa SL önce (K-16.4)."""
    n = 60
    close = np.full(n, 100.0)
    open_ = np.full(n, 100.0)
    high = np.full(n, 100.0)
    low = np.full(n, 100.0)
    high[35] = 105.0  # TP = 100 + 2×2 = 104
    low[35] = 97.0  # SL = 100 − 1×2 = 98

    r = evaluate(one_event(t0=30, atr=2.0), simple_store(open_, high, low, close), 2.0, 1.0)
    assert r["outcome"][0] == OUTCOME_SL
    assert r["r_gross"][0] == pytest.approx(-1.0)


def test_gap_through_stop_exits_at_open():
    """Bariyer 98, mum 95'ten açıldıysa 98'de satamazdın — çıkış 95."""
    n = 60
    close = np.full(n, 100.0)
    open_ = np.full(n, 100.0)
    high = np.full(n, 100.5)
    low = np.full(n, 99.5)
    open_[35], high[35], low[35], close[35] = 95.0, 95.5, 94.0, 95.0

    r = evaluate(one_event(t0=30, atr=2.0), simple_store(open_, high, low, close), 2.0, 1.0)
    assert r["outcome"][0] == OUTCOME_SL
    assert r["r_gross"][0] == pytest.approx((95.0 - 100.0) / 2.0)  # −2,5R, −1R değil


def test_gap_through_target_exits_at_open():
    """Aynı kural yukarı yönde de geçerli — yalnız SL'e uygulamak yanlılık yaratır."""
    n = 60
    close = np.full(n, 100.0)
    open_ = np.full(n, 100.0)
    high = np.full(n, 100.5)
    low = np.full(n, 99.5)
    open_[35], high[35], low[35], close[35] = 110.0, 111.0, 109.5, 110.0

    r = evaluate(one_event(t0=30, atr=2.0), simple_store(open_, high, low, close), 2.0, 1.0)
    assert r["outcome"][0] == OUTCOME_TP
    assert r["r_gross"][0] == pytest.approx((110.0 - 100.0) / 2.0)  # +5R, +2R değil


def test_time_barrier_exits_at_close_of_last_bar():
    """T süresince bariyer vurulmazsa çıkış t₀+T barının Close'u."""
    n = 80
    close = 100.0 + 0.01 * np.arange(n)  # çok yavaş yükseliş, bariyere değmez
    open_ = close.copy()
    high = close + 0.02
    low = close - 0.02

    ev = one_event(t0=30, length=24, atr=5.0)  # T = 12
    r = evaluate(ev, simple_store(open_, high, low, close), 2.0, 1.0)

    assert r["outcome"][0] == OUTCOME_TIME
    assert r["exit_bar"][0] == time_barrier(24)
    beklenen = (close[30 + time_barrier(24)] - close[30]) / 5.0
    assert r["r_gross"][0] == pytest.approx(beklenen)


def test_time_barrier_scales_with_window_length():
    """T = round(0,5 × L) — sabit 10 bar değil (K-16.4)."""
    assert time_barrier(24) == 12
    assert time_barrier(100) == 50
    assert time_barrier(40) == 20


def test_padding_never_triggers_a_barrier():
    """Kısa satırların dolgusu (−inf / +inf) bariyer tetiklememeli."""
    n = 40
    close = np.full(n, 100.0)
    store = simple_store(close.copy(), close + 0.1, close - 0.1, close)

    # t0 = 35, T = 12 → yalnızca 4 bar var
    r = evaluate(one_event(t0=35, length=24, atr=2.0), store, 2.0, 1.0)
    assert r["outcome"][0] == OUTCOME_FORCED
    assert bool(r["truncated"][0])


def test_delisted_symbol_is_forced_exit_not_dropped():
    """⛔ Kesik ileri pencereli olay ELENMEZ — survivorship bias arka kapısı.

    Elenirse, ölmek üzere olan coinlerin en kötü sonuçları sistematik olarak
    atılmış olur; K-13'te evren düzeyinde önlenen bias buradan geri girer.
    """
    n = 45
    close = np.concatenate([np.full(40, 100.0), np.full(5, 40.0)])  # çöküş, sonra delist
    open_ = close.copy()
    r = evaluate(
        one_event(t0=38, length=40, atr=2.0),  # T = 20 ama yalnız 6 bar var
        simple_store(open_, close + 0.1, close - 0.1, close),
        2.0,
        1.0,
    )
    assert r.size == 1, "kesik pencereli olay düşürülmüş"
    assert r["outcome"][0] in (OUTCOME_SL, OUTCOME_FORCED)
    assert r["r_gross"][0] < 0  # çöküş sonucu istatistiğe giriyor


def test_event_without_forward_bars_is_dropped():
    """t₀ son bar ise ölçülecek bir şey yok."""
    n = 40
    close = np.full(n, 100.0)
    r = evaluate(one_event(t0=n - 1, atr=2.0), simple_store(close, close, close, close), 2.0, 1.0)
    assert r.size == 0


# ---------------------------------------------------------------------------
# Ön filtreler
# ---------------------------------------------------------------------------


def test_min_atr_pct_floor():
    """1×ATR / C₀ < %1 → pencere istatistiğe girmez (K-16.7)."""
    n = 60
    close = np.full(n, 100.0)
    store = simple_store(close, close + 1, close - 1, close)

    dusuk = one_event(t0=30, atr=100.0 * MIN_ATR_PCT * 0.5)
    yuksek = one_event(t0=30, atr=100.0 * MIN_ATR_PCT * 2.0)
    assert not eligible(dusuk, store)[0]
    assert eligible(yuksek, store)[0]


def test_atr_warmup_filter():
    """Listeleme sonrası ilk barlarda ATR ısınmamıştır (2 × ATR_PERIOD)."""
    n = 80
    close = np.full(n, 100.0)
    store = simple_store(close, close + 5, close - 5, close)
    erken = one_event(t0=MIN_BARS_SINCE_LISTING - 1, atr=3.0)
    gec = one_event(t0=MIN_BARS_SINCE_LISTING + 1, atr=3.0)
    assert not eligible(erken, store)[0]
    assert eligible(gec, store)[0]


def test_commission_reduces_r():
    """R_net = R_brüt − komisyon/atr_pct; ikisi de raporlanır."""
    n = 60
    close = np.full(n, 100.0)
    open_ = close.copy()
    high = close.copy()
    low = close.copy()
    high[35] = 106.0  # TP

    r = evaluate(one_event(t0=30, atr=2.0), simple_store(open_, high, low, close), 2.0, 1.0)
    atr_pct = 2.0 / 100.0
    assert r["r_net"][0] == pytest.approx(r["r_gross"][0] - ROUNDTRIP_FEE_PCT / atr_pct)
    assert r["r_net"][0] < r["r_gross"][0]


# ---------------------------------------------------------------------------
# Bağımsız N — ileri pencere örtüşmesi (K-09)
# ---------------------------------------------------------------------------


def test_forward_separation_removes_overlapping_horizons():
    """NMS formasyon pencerelerini ayırır ama SONUÇ pencerelerini denetlemez."""
    ev = np.empty(4, dtype=EVENT_DTYPE)
    ev["symbol_id"] = [1, 1, 1, 2]
    ev["t0"] = [100, 105, 130, 100]  # L=24 → T=12
    ev["length"] = 24
    ev["atr"] = 1.0
    ev["end_time"] = 0

    keep = enforce_forward_separation(ev)
    kalan = ev[keep]
    assert keep.sum() == 3  # 105 elenir (100'e 5 bar mesafede, T=12)
    assert set(zip(kalan["symbol_id"].tolist(), kalan["t0"].tolist())) == {(1, 100), (1, 130), (2, 100)}


def test_forward_separation_uses_window_length():
    """Ayrım eşiği T'dir; L büyüdükçe daha çok olay elenir."""
    ev = np.empty(2, dtype=EVENT_DTYPE)
    ev["symbol_id"] = 1
    ev["t0"] = [100, 130]
    ev["atr"] = 1.0
    ev["end_time"] = 0

    ev["length"] = 24  # T = 12 → 30 bar ayrım yeterli
    assert enforce_forward_separation(ev).sum() == 2

    ev["length"] = 100  # T = 50 → 30 bar yetersiz
    assert enforce_forward_separation(ev).sum() == 1


# ---------------------------------------------------------------------------
# Gölge dağılım (K-12)
# ---------------------------------------------------------------------------


def _pool_meta(n_symbols=20, months=3, per_month=30, length=24):
    from engine.config import META_DTYPE

    rows = []
    for sid in range(n_symbols):
        for m in range(months):
            base = 1_600_000_000_000 + m * 31 * 86_400_000
            for k in range(per_month):
                rows.append((sid, 0, 40 + k * 3, base + k * 86_400_000, 20.0, 1.5, True))
    meta = np.empty(len(rows), dtype=META_DTYPE)
    for i, row in enumerate(rows):
        meta[i] = row
    return meta


def test_shadow_samples_same_month_different_symbols():
    """Kontrol grubu: aynı ay, FARKLI sembol (K-12)."""
    from engine.matrix.liquidity import month_key
    from engine.outcome.shadow import ShadowPool, sample_shadow

    meta = _pool_meta()
    pool = ShadowPool.from_meta(meta, 24)

    ev = np.empty(1, dtype=EVENT_DTYPE)
    ev[0] = (0, 100, 24, 1.5, meta["end_time"][0])

    shadow, report = sample_shadow(ev, {24: pool}, p=10, rng=np.random.default_rng(1))

    assert shadow.size > 0
    assert not (shadow["symbol_id"] == 0).any(), "gölge aynı sembolden çekilmiş"
    hedef_ay = month_key(np.array([ev["end_time"][0]]))[0]
    assert (month_key(shadow["end_time"]) == hedef_ay).all(), "gölge farklı aydan"
    assert report["shadow_events"] == shadow.size


def test_shadow_enforces_forward_separation_across_pool():
    """Gölge pencerelerin ileri ufukları kesişirse null otokorelasyonlu olur.

    Sonuç: gölgenin varyansı olduğundan küçük ölçülür → edge'in GA'sı sahte
    biçimde daralır → anlamsız bir farkı anlamlı ilan edersin.
    """
    from engine.outcome.shadow import ShadowPool, sample_shadow

    meta = _pool_meta(n_symbols=3, per_month=40)
    pool = ShadowPool.from_meta(meta, 24)

    ev = np.empty(3, dtype=EVENT_DTYPE)
    for i in range(3):
        ev[i] = (99, 100 + i * 50, 24, 1.5, meta["end_time"][0])

    shadow, _ = sample_shadow(ev, {24: pool}, p=20, rng=np.random.default_rng(2))

    horizon = time_barrier(24)
    for sid in np.unique(shadow["symbol_id"]):
        ends = np.sort(shadow["end_idx" if "end_idx" in shadow.dtype.names else "t0"][shadow["symbol_id"] == sid])
        if ends.size > 1:
            assert np.all(np.diff(ends) >= horizon), "gölgede örtüşen ileri pencere var"


def test_shadow_reports_short_pools():
    """Havuz yetersizse P < 20'ye düşülür ve KAYDEDİLİR — sessizce eksilmez."""
    from engine.outcome.shadow import ShadowPool, sample_shadow

    meta = _pool_meta(n_symbols=2, months=1, per_month=3)
    pool = ShadowPool.from_meta(meta, 24)

    ev = np.empty(1, dtype=EVENT_DTYPE)
    ev[0] = (0, 100, 24, 1.5, meta["end_time"][0])

    shadow, report = sample_shadow(ev, {24: pool}, p=20, rng=np.random.default_rng(3))
    assert report["matches_with_short_pool"] == 1
    assert shadow.size < 20


# ---------------------------------------------------------------------------
# Metrikler ve güven aralıkları
# ---------------------------------------------------------------------------


def test_wilson_matches_documented_example():
    """n=112, p=%41 → %95 GA ≈ [%32, %50] (belgedeki örnek)."""
    lo, hi = wilson_interval(46, 112)
    assert lo == pytest.approx(0.32, abs=0.01)
    assert hi == pytest.approx(0.50, abs=0.01)


def test_edge_claim_requires_significant_ci():
    """Edge'in GA'sı sıfırı içeriyorsa 'anlamlı fark ölçülemedi' denir."""
    rng = np.random.default_rng(4)
    a = rng.normal(0.18, 1.4, 112)
    b = rng.normal(0.02, 1.4, 400)
    lo, hi = bootstrap_diff_ci(a, b, samples=2000, rng=rng)
    assert lo < 0 < hi  # bu örneklem büyüklüğünde fark anlamlı değil


def test_summarize_verdict_is_honest(random_dataset):
    """Rastgele veride edge iddiası YAPILMAMALI."""
    events, store = random_dataset
    events = events[eligible(events, store)]
    results = evaluate(events, store, 2.0, 1.0)

    yarim = results.size // 2
    stats = summarize(results[:yarim], 2.0, 1.0, "2:1", shadow=results[yarim:],
                      rng=np.random.default_rng(0))

    assert stats.n == yarim
    assert not stats.edge_is_significant
    assert stats.verdict == "anlamlı fark ölçülemedi"
    assert stats.theoretical_null == pytest.approx(1 / 3)
    assert "disclaimer" in stats.as_dict()


def test_distribution_reports_what_the_mean_hides():
    """Aynı ortalamaya sahip iki dağılım aynı DEĞİLDİR."""
    # Aynı beklenti (+0,1R), tamamen farklı deneyim.
    steady = np.concatenate([np.full(90, 0.2), np.full(10, -0.8)])
    lottery = np.concatenate([np.full(90, -0.2), np.full(10, 2.8)])
    assert steady.mean() == pytest.approx(lottery.mean(), abs=1e-9)

    s_med, s_pos = distribution(steady)
    l_med, l_pos = distribution(lottery)

    # Ortalama aynı; medyan ve artıda kapanma oranı taban tabana zıt.
    assert s_med > 0 > l_med
    assert s_pos == pytest.approx(0.90) and l_pos == pytest.approx(0.10)


def test_share_positive_counts_more_than_the_win_rate(random_dataset):
    """Kazanma oranı yalnız TP'yi sayar; artıda kapanma zaman çıkışlarını da."""
    events, store = random_dataset
    events = events[eligible(events, store)]
    results = evaluate(events, store, 2.0, 1.0)
    stats = summarize(results, 2.0, 1.0, "2:1", rng=np.random.default_rng(0))
    assert stats.share_positive >= stats.win_rate - 1e-12


def test_summarize_carries_distribution_for_matches_and_shadow(random_dataset):
    """İki sayı da hem eşleşmeler hem gölge için dolar — kıyaslanabilir olmalı."""
    events, store = random_dataset
    events = events[eligible(events, store)]
    results = evaluate(events, store, 2.0, 1.0)
    half = results.size // 2

    stats = summarize(results[:half], 2.0, 1.0, "2:1", shadow=results[half:],
                      rng=np.random.default_rng(0))

    assert np.isfinite(stats.r_median)
    assert 0.0 <= stats.share_positive <= 1.0
    assert stats.shadow_r_median is not None
    assert 0.0 <= stats.shadow_share_positive <= 1.0

    payload = stats.as_dict()
    assert "share_positive" in payload and "shadow_share_positive" in payload


def test_both_configs_are_computed_together(random_dataset):
    """2:1 ve 1:1 birlikte hesaplanır ve saklanır (K-16.6)."""
    events, store = random_dataset
    events = events[eligible(events, store)]
    out = evaluate_all_configs(events, store)
    assert set(out) == {"2:1", "1:1"}
    assert out["2:1"].size == out["1:1"].size


def test_regime_breakdown_flags_small_cells(random_dataset):
    """n < 30 olan rejim hücresi 'yetersiz örnek' işaretlenir."""
    events, store = random_dataset
    events = events[eligible(events, store)][:40]
    results = evaluate(events, store, 2.0, 1.0)
    stats = summarize(results, 2.0, 1.0, "2:1", rng=np.random.default_rng(0))
    for row in stats.by_regime:
        assert row["insufficient"] == (row["n"] < 30)


# ---------------------------------------------------------------------------
# Fiyat sürekliliği (F4 bulgusu) — redenominasyon / ticker yeniden kullanımı
# ---------------------------------------------------------------------------


def test_forward_window_stops_at_price_discontinuity():
    """LUNAUSDT'de 177.400x bar-bar oranı bir fiyat hareketi DEĞİLDİR.

    Binance ticker'ı LUNA2 için yeniden kullandı: aynı sembol adı altında
    farklı bir varlık başlıyor. Ölçüm o noktada kesilmezse tek bir olay
    gölge dağılımın ortalamasını +39R'ye taşıyabiliyor.
    """
    n = 60
    close = np.full(n, 100.0)
    close[40:] = 0.0005  # ticker yeniden kullanımı / redenominasyon
    open_ = close.copy()

    r = evaluate(
        one_event(t0=30, length=40, atr=2.0),  # T = 20 → sıçramayı kapsıyor
        simple_store(open_, close * 1.01, close * 0.99, close),
        2.0,
        1.0,
    )
    assert r.size == 1
    assert bool(r["truncated"][0]), "sıçramadan sonrası ölçüme girmiş"
    assert abs(r["r_gross"][0]) < 10, f"absürt R: {r['r_gross'][0]}"


def test_normal_volatility_is_not_treated_as_discontinuity():
    """Gerçek pump kesilmemeli — eşik sıçrama için, oynaklık için değil."""
    n = 60
    close = np.full(n, 100.0)
    close[35:] = 250.0  # tek barda +%150: sert ama gerçek
    open_ = close.copy()

    r = evaluate(one_event(t0=30, length=40, atr=2.0), simple_store(open_, close * 1.01, close * 0.99, close), 2.0, 1.0)
    assert r["outcome"][0] == OUTCOME_TP
    assert not bool(r["truncated"][0])


def test_leveraged_tokens_are_filtered_from_universe():
    """Kaldıraçlı tokenlar spot parite değil, çürüyen türev ürünlerdir."""
    from engine.matrix.universe_filter import is_leveraged_token

    assert is_leveraged_token("BTCUPUSDT")
    assert is_leveraged_token("ETHDOWNUSDT")
    assert is_leveraged_token("XRPBULLUSDT")
    assert not is_leveraged_token("BTCUSDT")
    assert not is_leveraged_token("JUPUSDT")  # yanlış pozitif olmamalı


# ---------------------------------------------------------------------------
# F4.5 — Ayna (short) yönü
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("config,k_tp,k_sl", [("2:1", 2.0, 1.0), ("1:1", 1.0, 1.0)])
def test_short_null_matches_long_null(random_dataset, config, k_tp, k_sl):
    """Short null kapısı: fiyat martingale olduğu için long ile AYNI olmalı.

    Değilse bariyer çevirmede hata var — ucuz ve kesin bir kontrol.
    """
    events, store = random_dataset
    events = events[eligible(events, store)]
    results = evaluate(events, store, k_tp, k_sl, direction="short")

    tp = int((results["outcome"] == OUTCOME_TP).sum())
    sl = int((results["outcome"] == OUTCOME_SL).sum())
    decided = tp + sl
    null = theoretical_null(k_tp, k_sl)
    lo, hi = wilson_interval(tp, decided)

    print(f"\nshort {config}: {decided} karara bağlanan, başarı %{100*tp/decided:.1f} "
          f"(null %{100*null:.1f}, GA [%{100*lo:.1f}, %{100*hi:.1f}])")
    assert lo <= null <= hi, f"short {config}: null aralık dışında — bariyer çevirmede hata"


def test_short_barriers_are_mirrored():
    """TP aşağıda, SL yukarıda; kâr fiyat DÜŞÜNCE."""
    n = 60
    close = np.full(n, 100.0)
    open_ = close.copy()
    high = close.copy()
    low = close.copy()
    low[35] = 94.0  # short TP = 100 − 2×2 = 96

    r = evaluate(one_event(t0=30, atr=2.0), simple_store(open_, high, low, close), 2.0, 1.0,
                 direction="short")
    assert r["outcome"][0] == OUTCOME_TP
    assert r["r_gross"][0] > 0  # düşüş short'ta kârdır


def test_short_same_bar_rule_still_favours_sl():
    """Short'ta SL yukarıdadır; aynı barda ikisi de vurulduysa yine SL önce."""
    n = 60
    close = np.full(n, 100.0)
    open_ = close.copy()
    high = np.full(n, 100.0)
    low = np.full(n, 100.0)
    high[35] = 103.0  # short SL = 102
    low[35] = 95.0  # short TP = 96

    r = evaluate(one_event(t0=30, atr=2.0), simple_store(open_, high, low, close), 2.0, 1.0,
                 direction="short")
    assert r["outcome"][0] == OUTCOME_SL
    assert r["r_gross"][0] == pytest.approx(-1.0)


def test_short_gap_rule_is_symmetric():
    """Short'ta yukarı gap SL'i kötüleştirir, aşağı gap TP'yi iyileştirir."""
    n = 60
    close = np.full(n, 100.0)
    open_ = close.copy()
    high = np.full(n, 100.5)
    low = np.full(n, 99.5)
    open_[35], high[35], low[35], close[35] = 112.0, 113.0, 111.0, 112.0  # SL'i aşan gap

    r = evaluate(one_event(t0=30, atr=2.0), simple_store(open_, high, low, close), 2.0, 1.0,
                 direction="short")
    assert r["outcome"][0] == OUTCOME_SL
    assert r["r_gross"][0] == pytest.approx((100.0 - 112.0) / 2.0)  # −6R, −1R değil


def test_long_and_short_cannot_both_win_on_a_trend():
    """Aynı pencerede iki yön birden kazanamaz — tutarlılık kontrolü."""
    n = 120
    close = np.linspace(100, 180, n)
    store = simple_store(close, close * 1.001, close * 0.999, close)
    ev = one_event(t0=40, length=40, atr=3.0)

    uzun = evaluate(ev, store, 2.0, 1.0, direction="long")["r_gross"][0]
    kisa = evaluate(ev, store, 2.0, 1.0, direction="short")["r_gross"][0]
    assert not (uzun > 0 and kisa > 0), "aynı pencerede long ve short birlikte kazanıyor"


def test_direction_is_validated():
    n = 60
    close = np.full(n, 100.0)
    with pytest.raises(ValueError):
        evaluate(one_event(), simple_store(close, close, close, close), 2.0, 1.0, direction="yukarı")


# ---------------------------------------------------------------------------
# F4.5 — Ay-bloklu bootstrap
# ---------------------------------------------------------------------------


def test_block_bootstrap_preserves_pairing():
    """Blok çekiminde ayın TÜM eşleşmeleri ve TÜM gölgeleri birlikte gelir.

    Ay etkisi her ikisinde de ortak olduğu için farkta birbirini götürür;
    K-12'nin zaman eşleştirmesi bootstrap'ta da korunur.
    """
    from engine.outcome.metrics import block_bootstrap_diff_ci, bootstrap_diff_ci

    rng = np.random.default_rng(0)
    ay = rng.normal(0, 0.5, 12)  # güçlü ay etkisi
    a, am, b, bm = [], [], [], []
    for m in range(12):
        a += list(ay[m] + rng.normal(0.1, 0.05, 20))
        am += [m] * 20
        b += list(ay[m] + rng.normal(0.0, 0.05, 20))
        bm += [m] * 20

    a, b = np.array(a), np.array(b)
    iid = bootstrap_diff_ci(a, b, samples=3000, rng=rng)
    blok, design = block_bootstrap_diff_ci(a, np.array(am), b, np.array(bm), samples=3000, rng=rng)

    # Ortak ay etkisi götürüldüğü için blok GA daha dar olmalı
    assert (blok[1] - blok[0]) < (iid[1] - iid[0])
    assert np.isfinite(design)


def test_block_bootstrap_widens_when_effect_is_not_shared():
    """Ay etkisi yalnız bir tarafta ise blok bootstrap GA'yı GENİŞLETİR."""
    from engine.outcome.metrics import block_bootstrap_diff_ci, bootstrap_diff_ci

    rng = np.random.default_rng(1)
    ay = rng.normal(0, 0.6, 10)
    a, am, b, bm = [], [], [], []
    for m in range(10):
        a += list(ay[m] + rng.normal(0.0, 0.05, 25))  # ay etkisi yalnız eşleşmelerde
        am += [m] * 25
        b += list(rng.normal(0.0, 0.05, 25))
        bm += [m] * 25

    iid = bootstrap_diff_ci(np.array(a), np.array(b), samples=3000, rng=rng)
    blok, design = block_bootstrap_diff_ci(
        np.array(a), np.array(am), np.array(b), np.array(bm), samples=3000, rng=rng
    )
    assert (blok[1] - blok[0]) > (iid[1] - iid[0])
    assert design > 1.0


def test_bonferroni_family_grows_with_short():
    """Short eklenince aile 28 → 56; long sonuçlar da yeni eşikle sertleşir."""
    from engine.outcome.metrics import bonferroni_level

    assert bonferroni_level(28) == pytest.approx(1 - 0.05 / 28)
    assert bonferroni_level(56) == pytest.approx(1 - 0.05 / 56)
    assert bonferroni_level(56) > bonferroni_level(28)


# ---------------------------------------------------------------------------
# F4.6 — Ön-getiri eşleştirmeli gölge testleri
# ---------------------------------------------------------------------------


def _shadow_pool_with_returns(n_symbols=10, n_bars=200, length=40):
    """Ön-getirili gölge havuzu için test veri seti oluşturur."""
    from engine.outcome.shadow import ShadowPool

    rng = np.random.default_rng(42)
    meta_rows = []
    all_close = []
    offsets = {}
    offset = 0

    for sid in range(n_symbols):
        open_, high, low, close = martingale_ohlc(n_bars, 0.04, rng)
        offsets[sid] = offset
        all_close.extend(close)
        offset += n_bars

        atr = wilder_atr(high, low, close)
        stride = 3
        for start in range(0, n_bars - length, stride):
            end = start + length
            if end >= n_bars:
                break
            a = atr[end] if end < n_bars and np.isfinite(atr[end]) else 0.0
            if a <= 0:
                continue
            amp = (max(close[start:end + 1]) - min(close[start:end + 1])) / min(close[start:end + 1]) * 100
            meta_rows.append((sid, start, end, end * 86_400_000, amp, a, True))

    from engine.config import META_DTYPE
    meta = np.array(meta_rows, dtype=META_DTYPE)
    klines_close = np.array(all_close, dtype=np.float64)

    pool = ShadowPool.from_meta(
        meta, length,
        klines_close=klines_close,
        klines_offsets=offsets,
    )
    return pool, meta, klines_close, offsets


def test_shadow_return_matching_filters_by_band():
    """Ön-getiri eşleştirmeli gölge, band dışındaki adayları elemeli."""
    from engine.outcome.shadow import sample_shadow

    pool, meta, klines_close, offsets = _shadow_pool_with_returns()

    # Yüksek ön-getirili bir olay oluştur
    ev = np.empty(1, dtype=EVENT_DTYPE)
    # Havuzun ilk ayından bir olay seç
    first_month = sorted(pool.by_month.keys())[0]
    first_rows = pool.by_month[first_month]
    ev[0] = (0, int(pool.end_idx[first_rows[0]]), pool.length,
             float(pool.atr[first_rows[0]]), int(pool.end_time[first_rows[0]]))

    # match_return=False → standart gölge
    std_shadow, std_report = sample_shadow(
        ev, {pool.length: pool}, p=5, match_return=False,
        rng=np.random.default_rng(99),
    )

    # match_return=True → ön-getiri eşleştirmeli gölge
    matched_shadow, matched_report = sample_shadow(
        ev, {pool.length: pool}, p=5, match_return=True,
        return_band_sigma=0.25,
        rng=np.random.default_rng(99),
    )

    # Rapor return_matched alanı
    assert std_report["return_matched"] is False
    assert matched_report["return_matched"] is True
    assert "return_band_sigma" in matched_report


def test_shadow_return_matching_backward_compatible():
    """match_return=False ise mevcut davranış korunmalı — geriye uyumlu."""
    from engine.outcome.shadow import sample_shadow

    pool, _, _, _ = _shadow_pool_with_returns()

    ev = np.empty(1, dtype=EVENT_DTYPE)
    first_month = sorted(pool.by_month.keys())[0]
    first_rows = pool.by_month[first_month]
    ev[0] = (0, int(pool.end_idx[first_rows[0]]), pool.length,
             float(pool.atr[first_rows[0]]), int(pool.end_time[first_rows[0]]))

    shadow, report = sample_shadow(
        ev, {pool.length: pool}, p=5, match_return=False,
        rng=np.random.default_rng(99),
    )

    # Raporda fallback alanları OLMAMALI
    assert "fallback_band_widened" not in report
    assert "fallback_month_expanded" not in report


def test_shadow_pool_log_return_computed():
    """ShadowPool.from_meta ile log return hesaplanmalı."""
    pool, _, _, _ = _shadow_pool_with_returns()

    assert pool.log_return.size > 0
    assert pool.return_sigma > 0
    # Log return'lerin çoğu sıfır olmamalı (martingale fiyatlar)
    nonzero = np.abs(pool.log_return) > 1e-10
    assert nonzero.sum() > 0


def test_shadow_pool_without_klines_has_zero_returns():
    """Klines verilmezse log return sıfır ve sigma 1.0 olmalı."""
    from engine.outcome.shadow import ShadowPool
    from engine.config import META_DTYPE

    rng = np.random.default_rng(42)
    meta_rows = []
    for sid in range(3):
        for end in range(40, 100, 3):
            meta_rows.append((sid, end - 40, end, end * 86_400_000, 20.0, 2.0, True))
    meta = np.array(meta_rows, dtype=META_DTYPE)

    pool = ShadowPool.from_meta(meta, 40)
    assert pool.return_sigma == 1.0
    assert np.all(pool.log_return == 0)


def test_shadow_fallback_reports_counts():
    """Fallback kullanıldığında raporda fallback sayıları olmalı."""
    from engine.outcome.shadow import sample_shadow

    pool, _, _, _ = _shadow_pool_with_returns(n_symbols=3, n_bars=100)

    # Çok dar band ile zorla fallback tetikle
    ev = np.empty(1, dtype=EVENT_DTYPE)
    first_month = sorted(pool.by_month.keys())[0]
    first_rows = pool.by_month[first_month]
    ev[0] = (0, int(pool.end_idx[first_rows[0]]), pool.length,
             float(pool.atr[first_rows[0]]), int(pool.end_time[first_rows[0]]))

    _, report = sample_shadow(
        ev, {pool.length: pool}, p=5, match_return=True,
        return_band_sigma=0.001,  # Çok dar band → fallback zorunlu
        rng=np.random.default_rng(99),
    )

    assert "fallback_band_widened" in report
    assert "fallback_month_expanded" in report


def test_adjacent_months():
    """Komşu ay hesaplama doğruluğu."""
    from engine.outcome.shadow import _adjacent_months
    from engine.matrix.liquidity import month_key

    # 2023-06-01 → ms
    base_ms = int(np.datetime64("2023-06-01").astype("datetime64[ms]").astype("int64"))
    adj = _adjacent_months(base_ms, 1)

    # ±1 ay: Mayıs ve Temmuz
    expected_may = int(np.datetime64("2023-05-01").astype("datetime64[ms]").astype("int64"))
    expected_jul = int(np.datetime64("2023-07-01").astype("datetime64[ms]").astype("int64"))

    assert expected_may in adj
    assert expected_jul in adj
    assert len(adj) == 2



def test_small_sample_is_flagged_and_says_so(random_dataset):
    """N < MIN_EVENTS_FOR_CLAIM → sayılar döner ama iddia diye sunulmaz.

    Ölçülen boşluk: `symmetrical_triangle` 1d'de yalnız 4 eşleşme veriyordu,
    buna rağmen API "beklenti +0,803R" diye normal bir kart döndürüyordu.
    Güven aralığı doğruydu ve hüküm "anlamlı fark ölçülemedi" diyordu — ama
    ekranın ortasındaki sayı yine de +0,80R'ydi.
    """
    from engine.config import MIN_EVENTS_FOR_CLAIM

    events, store = random_dataset
    events = events[eligible(events, store)]
    results = evaluate(events, store, 2.0, 1.0)

    few = summarize(results[:4], 2.0, 1.0, "2:1", rng=np.random.default_rng(0))
    assert few.insufficient
    assert "yetersiz örnek" in few.verdict
    assert few.as_dict()["insufficient"] is True

    many = summarize(results[:MIN_EVENTS_FOR_CLAIM], 2.0, 1.0, "2:1",
                     rng=np.random.default_rng(0))
    assert not many.insufficient
    assert "yetersiz örnek" not in many.verdict


# ---------------------------------------------------------------------------
# İleri yol fanı
# ---------------------------------------------------------------------------


def _fan_store(closes: dict[int, list[float]]):
    from engine.outcome.bars import BarStore

    arrays = {}
    for sid, c in closes.items():
        c = np.asarray(c, dtype=np.float64)
        arrays[sid] = {"open": c, "high": c * 1.001, "low": c * 0.999, "close": c}
    return BarStore.from_arrays(arrays)


def _event(sid: int, t0: int, length: int, atr: float):
    from engine.outcome.triple_barrier import EVENT_DTYPE

    ev = np.zeros(1, dtype=EVENT_DTYPE)
    ev["symbol_id"], ev["t0"], ev["length"], ev["atr"], ev["end_time"] = sid, t0, length, atr, 0
    return ev


def test_fan_yolu_atr_cinsinden_ve_bariyere_gore_normalize():
    """Her barda +1 ATR yükselen fiyat: yol 0'dan T'ye doğrusal çıkmalı.

    T = pencere uzunluğunun yarısı (K-16.4). 24 barlık pencere → T = 12,
    100 barlık → T = 50; ikisi de aynı [0, 1] zaman ekseninde durur.
    """
    from engine.outcome.paths import forward_paths

    closes = 100.0 + np.arange(200.0)          # bar başına +1
    store = _fan_store({1: closes})
    events = np.concatenate([_event(1, 20, 24, 1.0), _event(1, 40, 100, 1.0)])
    paths = forward_paths(events, store, grid=5)

    assert np.allclose(paths[0], [0, 3, 6, 9, 12])    # T = 12
    assert np.allclose(paths[1], [0, 12.5, 25, 37.5, 50])  # T = 50


def test_fan_veri_sonu_ve_fiyat_sicramasini_uydurmaz():
    """Ölçülemeyen nokta NaN'dır; kesilen yol sayımdan düşer."""
    from engine.outcome.paths import fan, forward_paths

    closes = list(100.0 + np.arange(30.0))
    closes[25] = closes[24] * 20              # redenominasyon (>10x) — sıçrama
    store = _fan_store({1: closes})
    ev = _event(1, 20, 24, 1.0)              # T = 12 → t0+12 = 32 > veri sonu
    paths = forward_paths(ev, store, grid=13)
    assert paths[0, 0] == 0.0
    assert np.isfinite(paths[0, :5]).all()      # t0+1..t0+4 ölçülebilir
    assert np.isnan(paths[0, 5:]).all()         # sıçrama barı ve ötesi yok

    rep = fan(paths)
    assert rep["n"][0] == 1 and rep["n"][-1] == 0
    assert rep["p50"][-1] is None


def test_fan_yuzdelikleri_sirali_ve_golge_hep_birlikte():
    from engine.outcome.paths import fan_report

    rng = np.random.default_rng(3)
    closes = {sid: 100 + np.cumsum(rng.normal(0, 1, 400)) + 200 for sid in range(1, 6)}
    store = _fan_store(closes)
    events = np.concatenate([_event(sid, 100 + 10 * sid, 40, 2.0) for sid in range(1, 6)])
    shadow = np.concatenate([_event(sid, 250, 40, 2.0) for sid in range(1, 6)])
    rep = fan_report(events, shadow, store)

    assert set(rep) == {"matches", "shadow"}, "fan asla gölgesiz dönmemeli (K-12)"
    for side in rep.values():
        for i in range(len(side["u"])):
            vals = [side[k][i] for k in ("p10", "p25", "p50", "p75", "p90")]
            assert vals == sorted(vals)


# ---------------------------------------------------------------------------
# Eşleşme başına defter
# ---------------------------------------------------------------------------


def test_defter_her_eslesmenin_durumunu_girdi_sirasiyla_soyler():
    """Toplamın hangi olaylardan kurulduğu tek tek görünür — sayılmayanlar dahil."""
    from engine.outcome.pipeline import run_events

    closes = 100.0 + np.arange(400.0)          # bar başına +1
    store = _fan_store({1: closes})
    events = np.concatenate(
        [
            _event(1, 100, 40, 5.0),   # A: sayılır — +1/bar, 2:1'de TP (+10) 10. barda
            _event(1, 105, 40, 5.0),   # B: A'nın ileri penceresiyle örtüşür (T = 20)
            _event(1, 10, 24, 5.0),    # C: listelemeden sonra ATR ısınmadı (t0 < 28)
            _event(1, 200, 40, 0.5),   # D: 0,5 / 300 < %1 → işlem maliyeti tabanı
            _event(9, 150, 40, 5.0),   # E: deposu olmayan sembol
            _event(1, 399, 24, 5.0),   # F: son bar — ileri pencere yok
        ]
    )
    out = run_events(events, store, {}, timeframe="4h", with_ledger=True)
    ledger = out.ledger

    assert [row["status"] for row in ledger] == [
        "counted", "overlap", "listing", "cost_floor", "no_data", "no_forward",
    ]
    assert [(r["symbol_id"], r["end_idx"], r["window_length"]) for r in ledger] == [
        (int(e["symbol_id"]), int(e["t0"]), int(e["length"])) for e in events
    ]

    a = ledger[0]["outcomes"]
    assert set(a) == set(out.stats)
    assert a["2:1"]["outcome"] == "tp" and a["2:1"]["exit_bar"] == 10
    assert a["2:1"]["r"] == pytest.approx(2.0, abs=0.01)
    assert all(not row["outcomes"] for row in ledger[1:])

    # Defter ile toplam aynı olay kümesinden: sayılanların R ortalaması beklentidir.
    for name, stats in out.stats.items():
        counted = [row["outcomes"][name]["r"] for row in ledger if name in row["outcomes"]]
        assert len(counted) == stats.n
        assert np.mean(counted) == pytest.approx(stats.expectancy_r, abs=1e-3)


def test_eleme_sebebi_ile_istatistik_filtresi_ayni_koddan():
    """Kartın söylediği sebep ile istatistiğin uyguladığı filtre ayrışamaz."""
    from engine.outcome.triple_barrier import eligible, ineligible_reasons

    store = _fan_store({1: 100.0 + np.arange(400.0)})
    events = np.concatenate(
        [_event(1, t0, 40, atr) for t0 in (5, 50, 300) for atr in (0.1, 5.0, np.nan)]
    )
    assert (eligible(events, store) == (ineligible_reasons(events, store) == "")).all()
