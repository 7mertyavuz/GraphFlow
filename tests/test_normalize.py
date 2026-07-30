"""F1 — normalizasyon, genlik, ATR testleri (K-02, K-10, K-16.4)."""

from __future__ import annotations

import numpy as np
import pytest

from engine.config import ATR_PERIOD, FLAT_EPS, N_POINTS
from engine.normalize.amplitude import amplitude, amplitude_batch
from engine.normalize.atr import atr_at, true_range, wilder_atr
from engine.normalize.pipeline import (
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
