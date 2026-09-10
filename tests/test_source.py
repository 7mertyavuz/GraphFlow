"""Gerçek grafikten sorgu — engine/search/source.py."""

from __future__ import annotations

import numpy as np
import pytest

from engine.config import SOURCE_MAX_BARS, SOURCE_MIN_BARS
from engine.normalize.pipeline import normalize_batch, normalize_window
from engine.outcome.bars import BarStore
from engine.search.source import ChartWindow, SourceError, chart_window, excluded

STEP = 14_400_000  # 4h


def _store(closes: dict[int, np.ndarray]) -> BarStore:
    arrays = {}
    for sid, c in closes.items():
        c = np.asarray(c, dtype=np.float64)
        arrays[sid] = {
            "close": c,
            "high": c * 1.01,
            "low": c * 0.99,
            "open_time": np.arange(c.size, dtype=np.int64) * STEP,
        }
    return BarStore.from_arrays(arrays)


def _wave(n: int = 300, level: float = 100.0) -> np.ndarray:
    x = np.linspace(0, 6 * np.pi, n)
    return level * np.exp(0.2 * np.sin(x) + 0.001 * np.arange(n))


def test_parca_matris_penceresiyle_ayni_normalizasyondan_gecer():
    """İki normalizasyon = iki farklı sonuç listesi (K-02): parça vektörü,
    matrisin toplu normalizasyonunun aynı pencere için ürettiğiyle aynı."""
    closes = _wave()
    w = chart_window(_store({1: closes}), 1, length=64)
    batch, valid = normalize_batch(closes[w.start_idx : w.end_idx + 1][None, :])
    assert valid[0]
    np.testing.assert_allclose(w.vector, batch[0], atol=1e-5)
    np.testing.assert_allclose(w.vector, normalize_window(closes[-64:]))


def test_varsayilan_son_kapanmis_bar_ve_zaman_secimi():
    store = _store({1: _wave()})
    last = chart_window(store, 1, length=40)
    assert (last.start_idx, last.end_idx, last.length) == (260, 299, 40)
    assert last.end_time == 299 * STEP and last.start_time == 260 * STEP

    # Bar açılışına denk gelmeyen zaman: o anda ya da önce açılmış son bar.
    mid = chart_window(store, 1, length=40, end_time=150 * STEP + STEP // 2)
    assert mid.end_idx == 150
    exact = chart_window(store, 1, length=40, end_time=150 * STEP)
    assert exact.end_idx == 150


def test_seviye_ve_olcek_degismezligi():
    """Aynı şekil, farklı fiyat seviyesi → aynı sorgu vektörü."""
    a = chart_window(_store({1: _wave(level=0.002)}), 1, length=64)
    b = chart_window(_store({1: _wave(level=65_000.0)}), 1, length=64)
    np.testing.assert_allclose(a.vector, b.vector, atol=1e-9)


@pytest.mark.parametrize(
    "kwargs, code",
    [
        ({"length": SOURCE_MIN_BARS - 1}, "bad_length"),
        ({"length": SOURCE_MAX_BARS + 1}, "bad_length"),
        ({"length": 64, "end_time": 30 * STEP}, "not_enough_bars"),
        ({"length": 64, "end_time": -1}, "not_enough_bars"),
    ],
)
def test_gecersiz_parca_reddedilir(kwargs, code):
    with pytest.raises(SourceError) as err:
        chart_window(_store({1: _wave()}), 1, **kwargs)
    assert err.value.code == code


def test_bilinmeyen_sembol_ve_duz_parca():
    store = _store({1: _wave(), 2: np.full(300, 5.0)})
    with pytest.raises(SourceError) as err:
        chart_window(store, 9, length=64)
    assert err.value.code == "unknown_symbol"
    with pytest.raises(SourceError) as err:
        chart_window(store, 2, length=64)
    assert err.value.code == "flat"


def test_pencere_icindeki_fiyat_sicramasi_reddedilir():
    """Redenominasyon bir şekil değil birim değişikliğidir."""
    closes = _wave()
    closes[270:] *= 1000.0  # 269 → 270 geçişi sıçrama
    store = _store({1: closes})
    with pytest.raises(SourceError) as err:
        chart_window(store, 1, length=64)
    assert err.value.code == "price_jump"

    # Sıçrama tam ilk barda (önceki bara göre) → pencere dışındaki bir
    # geçiştir; pencerenin kendisi tutarlıdır.
    ok = chart_window(store, 1, length=30)
    assert ok.start_idx == 270


def _window(symbol_id: int = 1, start: int = 100, end: int = 163) -> ChartWindow:
    return ChartWindow(symbol_id, start, end, start * STEP, end * STEP, np.zeros(32))


def test_tarihsel_modda_ayni_donem_tum_sembollerde_dislanir():
    w = _window()
    sym = np.array([1, 2, 2, 3, 1])
    start = np.array([90, 150, 164, 0, 170]) * STEP
    end = np.array([130, 200, 200, 99, 230]) * STEP
    # 0: kendisi (örtüşüyor) · 1: başka sembol aynı dönem · 2: hemen sonrası
    # (ortak bar yok) · 3: hemen öncesi · 4: aynı sembol, sonra
    assert excluded(sym, start, end, w, same_period=True).tolist() == [True, True, False, False, False]


def test_radar_modunda_yalniz_sorgu_sembolu_dislanir():
    w = _window()
    sym = np.array([1, 2, 1])
    start = np.array([120, 120, 164]) * STEP
    end = np.array([183, 183, 227]) * STEP
    assert excluded(sym, start, end, w, same_period=False).tolist() == [True, False, False]


def test_tek_ortak_bar_da_ortusmedir():
    w = _window(start=100, end=163)
    sym = np.array([2, 2])
    start = np.array([163, 40]) * STEP
    end = np.array([200, 100]) * STEP
    assert excluded(sym, start, end, w, same_period=True).tolist() == [True, True]
