"""Null örneklemi pencere kimliğiyle çekilir — engine/search/null_sample.py."""

from __future__ import annotations

import numpy as np

from engine.search.null_sample import null_sample, window_keys


def _grid(n_symbols: int = 60, n_times: int = 300):
    sids = np.repeat(np.arange(n_symbols), n_times)
    times = np.tile(np.arange(n_times, dtype=np.int64) * 14_400_000, n_symbols)
    return sids, times


def test_ayni_kimlik_ayni_anahtar_siradan_bagimsiz():
    sids, times = _grid()
    perm = np.random.default_rng(0).permutation(sids.size)
    a = window_keys(sids, times, 64, 7)
    b = window_keys(sids[perm], times[perm], 64, 7)
    assert np.array_equal(a[perm], b)
    # Uzunluk ve tohum anahtarın parçası.
    assert not np.array_equal(a, window_keys(sids, times, 24, 7))
    assert not np.array_equal(a, window_keys(sids, times, 64, 8))


def test_sembol_dusunce_gerisi_aynen_kalir():
    """Asıl özellik: havuzdan çıkan yalnız kendisini götürür."""
    sids, times = _grid()
    full = np.ones(sids.size, dtype=bool)
    dropped = full & ~np.isin(sids, [3, 17, 41, 58])
    a = null_sample(sids, times, full, 2_000, 64, 11)
    b = null_sample(sids, times, dropped, 2_000, 64, 11)
    survivors = a[dropped[a]]
    assert np.isin(survivors, b).all()
    # Yerlerini havuzda sıradaki anahtarlar alır, örneklem boyu korunur.
    assert b.size == 2_000


def test_pencere_eklenince_eski_secimden_yalniz_yerini_verenler_duser():
    sids, times = _grid()
    old = sids < 50            # 10 sembol henüz yok
    a = null_sample(sids, times, old, 2_000, 64, 11)
    b = null_sample(sids, times, np.ones(sids.size, dtype=bool), 2_000, 64, 11)
    kept = np.intersect1d(a, b)
    newcomers = b[~old[b]]
    assert kept.size + newcomers.size == b.size
    assert np.isin(b[old[b]], a).all()


def test_orneklem_duzgun_rastgele():
    """Anahtar kimlikten türüyor ama seçim yine düzgün: sembol ve zaman
    ekseninde belirgin bir yığılma yok."""
    sids, times = _grid(100, 500)
    rows = null_sample(sids, times, None, 5_000, 64, 3)
    per_symbol = np.bincount(sids[rows], minlength=100)
    per_time = np.bincount((times[rows] // 14_400_000) // 50, minlength=10)
    # Binom(5000, 1/100): ort. 50, sd ~7; zaman dilimleri: ort. 500, sd ~21.
    assert per_symbol.min() > 20 and per_symbol.max() < 85
    assert per_time.min() > 420 and per_time.max() < 580


def test_havuz_kucukse_tamami():
    sids, times = _grid(2, 10)
    assert null_sample(sids, times, None, 100, 64, 1).size == 20
