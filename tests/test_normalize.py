"""F1 — normalizasyon, genlik, ATR testleri (K-02, K-10, K-16.4)."""

from __future__ import annotations

import numpy as np
import pytest

from engine.config import ATR_PERIOD, FLAT_EPS, N_POINTS
from engine.normalize.amplitude import amplitude, amplitude_batch
from engine.normalize.atr import atr_at, true_range, wilder_atr
from engine.normalize.pipeline import (
    antialias,
    monotone_xy,
    normalize_batch,
    normalize_drawing,
    normalize_window,
    resample_to,
    zscore,
)
from tools.shapes import cup_and_handle, head_and_shoulders

RNG = np.random.default_rng(0)


# ---------------------------------------------------------------------------
# Değişmezlik (invariance) — K-02'nin tek gerçek çıkış şartı
# ---------------------------------------------------------------------------


def test_scale_invariance_100x_price_level():
    """Aynı şekil, 100x farklı fiyat seviyesinde → aynı vektör."""
    shape = head_and_shoulders(60)
    prices = 100.0 * np.exp(0.3 * shape)

    a = normalize_window(prices)
    b = normalize_window(prices * 100.0)  # BTC ile penny-coin farkı

    assert a is not None and b is not None
    np.testing.assert_allclose(a, b, atol=1e-6)


def test_log_step_makes_multiplicative_moves_identical():
    """Log adımı olmadan yüzdesel olarak aynı hareket farklı vektör üretirdi."""
    shape = cup_and_handle(48)
    small = 1.0 * np.exp(0.25 * shape)
    huge = 60_000.0 * np.exp(0.25 * shape)

    np.testing.assert_allclose(normalize_window(small), normalize_window(huge), atol=1e-6)


def test_amplitude_scaling_does_not_change_shape_vector():
    """Z-score hareketin şiddetini siler — K-10'un genlik meta-verisi bu yüzden var."""
    shape = head_and_shoulders(50)
    weak = 100.0 * np.exp(0.02 * shape)
    strong = 100.0 * np.exp(0.40 * shape)

    np.testing.assert_allclose(normalize_window(weak), normalize_window(strong), atol=1e-6)
    # ...ama genlik ikisini ayırt edebilmeli:
    assert amplitude(strong) > 10 * amplitude(weak)


def test_length_invariance_same_shape_different_bar_counts():
    """24 barlık ve 100 barlık aynı şekil aynı vektör uzayında buluşur."""
    a = normalize_window(100.0 * np.exp(0.3 * head_and_shoulders(24)))
    b = normalize_window(100.0 * np.exp(0.3 * head_and_shoulders(100)))
    assert np.corrcoef(a, b)[0, 1] > 0.995


def test_output_norm_is_sqrt_n():
    """‖z‖ = √32 — Aşama 1'in Pearson korelasyonuna eşitliği buna dayanır."""
    v = normalize_window(100.0 * np.exp(0.2 * cup_and_handle(70)))
    assert v.shape == (N_POINTS,)
    assert np.linalg.norm(v) == pytest.approx(np.sqrt(N_POINTS), rel=1e-6)


def test_flat_window_is_dropped():
    assert normalize_window(np.full(40, 100.0)) is None
    assert zscore(np.zeros(32)) is None


def test_invalid_prices_rejected():
    assert normalize_window(np.array([1.0, 2.0, -3.0, 4.0])) is None
    assert normalize_window(np.array([1.0, np.nan, 3.0])) is None


# ---------------------------------------------------------------------------
# Toplu (batch) yol tekil yolla birebir aynı olmalı
# ---------------------------------------------------------------------------


def test_batch_matches_single_window_path():
    windows = np.stack(
        [100.0 * np.exp(0.3 * head_and_shoulders(64) + 0.01 * RNG.normal(size=64)) for _ in range(20)]
    )
    vectors, valid = normalize_batch(windows)

    assert valid.all()
    for i in range(len(windows)):
        np.testing.assert_allclose(vectors[i], normalize_window(windows[i]), atol=1e-6)


def test_batch_marks_flat_and_invalid_rows():
    windows = np.stack(
        [
            100.0 * np.exp(0.2 * cup_and_handle(32)),
            np.full(32, 50.0),  # düz
            np.concatenate([np.full(31, 10.0), [-1.0]]),  # geçersiz fiyat
        ]
    )
    _, valid = normalize_batch(windows)
    assert valid.tolist() == [True, False, False]


def test_batch_resample_matches_np_interp():
    windows = np.exp(RNG.normal(size=(5, 47)))
    vectors, _ = normalize_batch(windows)
    for i in range(5):
        np.testing.assert_allclose(vectors[i], normalize_window(windows[i]), atol=1e-6)


def test_resample_endpoints_preserved():
    x = np.linspace(3.0, 9.0, 17)
    r = resample_to(x, N_POINTS)
    assert r[0] == pytest.approx(3.0)
    assert r[-1] == pytest.approx(9.0)


# ---------------------------------------------------------------------------
# Çizim yolu — y ters, log YOK
# ---------------------------------------------------------------------------


def test_drawing_inverts_y_axis():
    """Kanvasta y aşağı doğru artar: küçük y = yüksek fiyat."""
    canvas_y = np.array([100.0, 80.0, 60.0, 40.0, 20.0])  # ekranda yukarı çıkan çizgi
    v = normalize_drawing(canvas_y)
    assert v[0] < v[-1]  # fiyat mantığında yükseliş


def test_drawing_skips_log_step():
    """Çizim lineer uzayda: aynı şeklin log'u ALINMAZ."""
    y = head_and_shoulders(40)
    drawn = normalize_drawing(y, invert_y=False)
    linear = zscore(resample_to(y, N_POINTS))
    np.testing.assert_allclose(drawn, linear, atol=1e-6)


def test_drawing_matches_price_window_for_same_shape():
    """Çizim ile aynı şekli taşıyan (küçük genlikli) fiyat penceresi eşleşmeli."""
    s = head_and_shoulders(80)
    drawn = normalize_drawing(-s, invert_y=True)  # kanvas yönelimi
    priced = normalize_window(100.0 * np.exp(0.05 * s))
    assert np.dot(drawn, priced) / N_POINTS > 0.99


def test_drawing_handles_uneven_xy_points():
    """Kullanıcı hızlı/yavaş çizdiğinde noktalar düzgün dağılmaz."""
    xs = np.array([0.0, 0.05, 0.07, 0.4, 0.9, 1.0])
    ys = -np.interp(xs, np.linspace(0, 1, 32), head_and_shoulders(32))
    v = normalize_drawing(np.column_stack([xs, ys]))
    assert v.shape == (N_POINTS,)
    assert np.linalg.norm(v) == pytest.approx(np.sqrt(N_POINTS), rel=1e-6)


def test_drawing_flat_line_returns_none():
    assert normalize_drawing(np.full(20, 5.0)) is None


# ---------------------------------------------------------------------------
# Çizim sözleşmesi: y = f(x)
# ---------------------------------------------------------------------------


def test_backtracking_stroke_is_not_reordered():
    """Sola dönen el, şekli yeniden dizmemeli.

    Eskiden ``argsort`` vardı: kullanıcı bir bölümü düzeltmek için sola
    döndüğünde y değerleri x sırasına diziliyor ve **çizilmemiş** bir şekil
    aranıyordu. Doğru davranış: geri dönülen aralık yeniden çiziliyordur.
    """
    # Sağa çizip 0,6'ya geri dön, oradan farklı bir y ile devam et.
    xs = np.array([0.0, 0.3, 0.6, 0.9, 0.6, 0.75, 1.0])
    ys = np.array([0.0, 0.5, 1.0, 0.2, 1.0, 0.9, 0.8])

    kept_x, kept_y = monotone_xy(xs, ys)

    assert np.all(np.diff(kept_x) > 0), "x kesin artan olmalı"
    # 0,9'daki nokta düşmeli: kullanıcı ondan önceye dönüp yeniden çizdi.
    assert 0.9 not in kept_x[:-1]
    np.testing.assert_allclose(kept_x, [0.0, 0.3, 0.6, 0.75, 1.0])
    np.testing.assert_allclose(kept_y, [0.0, 0.5, 1.0, 0.9, 0.8])


def test_monotone_xy_keeps_last_value_on_duplicate_x():
    """Aynı x'te dikey hareket: son y kazanır (tepe korunur)."""
    xs = np.array([0.0, 0.5, 0.5, 0.5, 1.0])
    ys = np.array([0.0, 0.2, 0.6, 0.9, 0.1])
    kept_x, kept_y = monotone_xy(xs, ys)
    np.testing.assert_allclose(kept_x, [0.0, 0.5, 1.0])
    np.testing.assert_allclose(kept_y, [0.0, 0.9, 0.1])


def test_backtracked_drawing_matches_clean_redraw():
    """Geri dönüp düzeltilen çizim, temiz çizilmiş hâliyle aynı vektörü vermeli."""
    shape = head_and_shoulders(24)
    xs_clean = np.linspace(0.0, 1.0, 24)

    # Aynı şekil, ortasında bir geri dönüşle: 12..17 arası çizilip silinerek
    # yeniden çizildi.
    xs_msgy = np.concatenate([xs_clean[:18], xs_clean[12:]])
    ys_msgy = np.concatenate([shape[:18], shape[12:]])

    clean = normalize_drawing(np.column_stack([xs_clean, shape]), invert_y=False)
    messy = normalize_drawing(np.column_stack([xs_msgy, ys_msgy]), invert_y=False)
    np.testing.assert_allclose(clean, messy, atol=1e-9)


# ---------------------------------------------------------------------------
# Aliasing — decimation öncesi alçak geçiren
# ---------------------------------------------------------------------------


def test_antialias_is_noop_below_decimation_threshold():
    """k <= 2n: indirgeme yok denecek kadar az, filtre de yok."""
    y = np.random.default_rng(0).normal(size=2 * N_POINTS)
    np.testing.assert_array_equal(antialias(y, N_POINTS), y)


def test_antialias_suppresses_subresolution_tremor():
    """Çıktı çözünürlüğünün altındaki titreme sönmeli, taşıyıcı şekil kalmalı."""
    rng = np.random.default_rng(7)
    k = 16 * N_POINTS
    base = head_and_shoulders(k)
    tremor = 0.25 * rng.normal(size=k)

    noisy = base + tremor
    filtered = antialias(noisy, N_POINTS)

    # Titreme sönüyor...
    assert np.std(filtered - base) < np.std(tremor) / 2
    # ...ve şekil yerinde duruyor: filtre, taşıyıcıya olan benzerliği
    # BOZMUYOR, artırıyor. Sabit bir eşik yerine bunu ölçmek doğrudur —
    # eşik gürültü seviyesine göre keyfîdir, iddia ise değildir.
    assert np.corrcoef(filtered, base)[0, 1] > np.corrcoef(noisy, base)[0, 1]


def test_smoothing_makes_shaky_hand_match_the_clean_shape():
    """El titremesi olan çizim, filtreyle temiz şekle yaklaşmalı.

    Bu, kullanıcının "çizdiğimi yanlış anlıyor" şikâyetinin ölçülebilir hâli:
    32 noktaya indirgemeden önce filtrelenmeyen titreme, çizilmemiş bir yapı
    olarak sorguya giriyordu.
    """
    rng = np.random.default_rng(11)
    k = 12 * N_POINTS
    clean_curve = head_and_shoulders(k)
    shaky = clean_curve + 0.3 * rng.normal(size=k)

    target = normalize_drawing(clean_curve, invert_y=False)
    raw = normalize_drawing(shaky, invert_y=False, smooth=False)
    smoothed = normalize_drawing(shaky, invert_y=False, smooth=True)

    similarity = lambda v: float(np.dot(v, target) / N_POINTS)  # noqa: E731
    assert similarity(smoothed) > similarity(raw)


def test_templates_are_not_smoothed_by_default():
    """Şablon vektörleri F3 eşiklerinin dayanağıdır: sessizce değişemezler."""
    points = np.column_stack([np.linspace(0, 1, N_POINTS), head_and_shoulders(N_POINTS)])
    default = normalize_drawing(points, invert_y=False)
    explicit = normalize_drawing(points, invert_y=False, smooth=False)
    np.testing.assert_array_equal(default, explicit)


# ---------------------------------------------------------------------------
# Genlik (K-10)
# ---------------------------------------------------------------------------


def test_amplitude_formula():
    p = np.array([100.0, 150.0, 120.0])
    assert amplitude(p) == pytest.approx(50.0)


def test_amplitude_is_scale_free():
    p = np.array([2.0, 3.0, 2.5])
    assert amplitude(p) == pytest.approx(amplitude(p * 1000.0))


def test_amplitude_batch_matches_single():
    windows = np.exp(RNG.normal(size=(30, 40))) * 10.0
    batch = amplitude_batch(windows)
    for i in range(len(windows)):
        assert batch[i] == pytest.approx(amplitude(windows[i]), rel=1e-5)


# ---------------------------------------------------------------------------
# ATR — lookahead yasağı (K-16.4, docs §16.5)
# ---------------------------------------------------------------------------


def _ohlc(n=200, seed=3):
    rng = np.random.default_rng(seed)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.02, n)))
    high = close * (1 + np.abs(rng.normal(0, 0.01, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.01, n)))
    return high, low, close


def test_atr_has_no_lookahead():
    """ATR[t0], yalnızca [0..t0] barlarıyla hesaplanan değere BİREBİR eşit olmalı."""
    high, low, close = _ohlc()
    full = wilder_atr(high, low, close)

    for t0 in (ATR_PERIOD - 1, 20, 57, 199):
        truncated = wilder_atr(high[: t0 + 1], low[: t0 + 1], close[: t0 + 1])
        assert full[t0] == pytest.approx(truncated[-1], rel=0, abs=0)
        assert atr_at(high, low, close, t0) == pytest.approx(truncated[-1], rel=0, abs=0)


def test_atr_ignores_future_bars_even_if_extreme():
    """t0'dan sonraki bir şok barı ATR[t0]'ı DEĞİŞTİRMEMELİ."""
    high, low, close = _ohlc()
    t0 = 100
    base = wilder_atr(high, low, close)[t0]

    shocked_high = high.copy()
    shocked_low = low.copy()
    shocked_high[t0 + 1 :] *= 5.0
    shocked_low[t0 + 1 :] /= 5.0
    after = wilder_atr(shocked_high, shocked_low, close)[t0]

    assert base == pytest.approx(after, rel=0, abs=0)


def test_atr_undefined_before_period():
    high, low, close = _ohlc(50)
    atr = wilder_atr(high, low, close)
    assert np.isnan(atr[: ATR_PERIOD - 1]).all()
    assert np.isfinite(atr[ATR_PERIOD - 1 :]).all()


def test_atr_wilder_recursion():
    high, low, close = _ohlc(60)
    tr = true_range(high, low, close)
    atr = wilder_atr(high, low, close)

    assert atr[ATR_PERIOD - 1] == pytest.approx(tr[:ATR_PERIOD].mean())
    expected = (atr[ATR_PERIOD - 1] * (ATR_PERIOD - 1) + tr[ATR_PERIOD]) / ATR_PERIOD
    assert atr[ATR_PERIOD] == pytest.approx(expected)


def test_true_range_uses_previous_close():
    high = np.array([10.0, 12.0])
    low = np.array([9.0, 11.5])
    close = np.array([9.5, 12.0])
    tr = true_range(high, low, close)
    assert tr[0] == pytest.approx(1.0)
    assert tr[1] == pytest.approx(2.5)  # |12 - 9.5| gap'i yakalar


def test_atr_too_short_series_is_all_nan():
    high, low, close = _ohlc(5)
    assert np.isnan(wilder_atr(high, low, close)).all()


def test_flat_eps_is_used_not_hardcoded_zero():
    tiny = np.full(32, 100.0) + np.linspace(0, FLAT_EPS / 10, 32)
    assert normalize_window(tiny) is None


def test_drawing_smooth_preserves_sharp_peak_under_uneven_speed():
    """Hızlı çizilen sivri tepe + yavaş çizilen yatay plato x-uzayı Gauss'uyla korunmalı."""
    x_fast = np.linspace(0.0, 0.30, 12)
    x_slow = np.linspace(0.305, 1.0, 480)
    xs = np.concatenate([x_fast, x_slow])
    ys = np.interp(xs, [0.0, 0.15, 0.30, 1.0], [0.2, 0.95, 0.2, 0.22])

    ref = normalize_drawing(np.column_stack([xs, ys]), invert_y=False, smooth=False)
    smoothed = normalize_drawing(np.column_stack([xs, ys]), invert_y=False, smooth=True)
    assert ref is not None and smoothed is not None
    assert np.corrcoef(smoothed, ref)[0, 1] > 0.99

    # Yüksek frekanslı el titremesini hâlâ sönümlemeli
    rng = np.random.default_rng(19)
    noisy_ys = ys + 0.08 * rng.normal(size=xs.size)
    noisy_pts = np.column_stack([xs, noisy_ys])
    raw_noisy = normalize_drawing(noisy_pts, invert_y=False, smooth=False)
    smooth_noisy = normalize_drawing(noisy_pts, invert_y=False, smooth=True)
    assert raw_noisy is not None and smooth_noisy is not None
    assert np.corrcoef(smooth_noisy, ref)[0, 1] > np.corrcoef(raw_noisy, ref)[0, 1]
