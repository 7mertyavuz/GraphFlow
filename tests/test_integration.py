"""Gerçek korpus üzerinde uçtan uca nöbetçiler.

Diğer 247 testin tamamı **sentetik** veriyle çalışır ve bu doğrudur: birim
testi veri deposuna bağımlı olmamalı. Ama projeyi iki kez ısıran hataların
ikisi de tam olarak bu boşlukta yaşadı:

* mikrosaniye zaman damgası 19 aylık veriyi sessizce yok etti,
* zaman dilimi başına sembol haritası karışınca 1d koşusu 4h evrenini okudu
  ve F4.6 üç hafta geçersiz sayılarla yayında kaldı.

İkisi de birim testlerinden geçerdi: kod doğruydu, **veriyle ilişkisi**
yanlıştı. Buradaki testler o ilişkiyi sınar ve veri yoksa atlanır (CI'da
depo bulunmaz).

Sınanan sözleşmeler:

* eşleşmeler gerçek sembol adına çözülüyor (``#897`` değil)
* pencere sınırları sembolün bar dizisinin içinde
* ``end_time`` gerçekten ``start_time + (uzunluk-1) × adım``
* skor tanım aralığında ve sıralama yüzdeliğe göre monoton
* aynı sorgu iki kez aynı sonucu veriyor (null tohumu sabit)
"""

from __future__ import annotations

import numpy as np
import pytest

from engine.config import TIMEFRAME_MS, WINDOW_LENGTHS
from engine.matrix.build import META_FILE, matrix_dir

TIMEFRAME = "1d"

_has_matrix = (matrix_dir(TIMEFRAME, WINDOW_LENGTHS[0]) / META_FILE).exists()
pytestmark = pytest.mark.skipif(
    not _has_matrix, reason="gerçek matris yok (CI) — python -m engine.matrix.build"
)


@pytest.fixture(scope="module")
def engine():
    from engine.search.engine import SearchEngine

    return SearchEngine()


@pytest.fixture(scope="module")
def query():
    from engine.templates import load_all

    return np.asarray(load_all()["head_and_shoulders"].vector, dtype=np.float64)


@pytest.fixture(scope="module")
def result(engine, query):
    return engine.search(query, timeframe=TIMEFRAME, tolerance="medium", limit=48)


def test_real_search_returns_matches(result):
    assert result.total > 0, "gerçek korpusta kanonik OBO için sonuç yok"
    assert result.results, "toplam > 0 ama liste boş"


def test_symbols_resolve_to_real_names(result):
    """``#897`` biçimi, sembol haritasının karıştığının imzasıdır."""
    unresolved = [m.symbol for m in result.results if m.symbol.startswith("#")]
    assert not unresolved, f"çözülemeyen sembol: {unresolved[:5]}"


def test_windows_are_inside_the_symbol_bars(result):
    """Pencere uzunluğu ile indeks aralığı tutarlı olmalı."""
    for m in result.results:
        assert m.start_idx >= 0
        assert m.end_idx > m.start_idx
        assert m.end_idx - m.start_idx == m.window_length - 1, (
            f"{m.symbol}: pencere {m.window_length} bar olmalı, "
            f"{m.end_idx - m.start_idx + 1} bulundu"
        )


def test_end_time_matches_window_length(result):
    """``end_time`` pencere uzunluğuyla tutarlı olmalı.

    Tutarsızlık, mikrosaniye/milisaniye karışmasının ya da boşluklu pencerenin
    matrise sızdığının işaretidir — zaman sürekliliği invariant'ı (F3.5) tam
    da bunu engellemek için var.
    """
    step = TIMEFRAME_MS[TIMEFRAME]
    for m in result.results:
        start_time = m.end_time - (m.window_length - 1) * step
        assert start_time > 0
        # 2017'den önce bar yok, gelecekte de olmamalı.
        assert 1_400_000_000_000 < start_time < 4_000_000_000_000, (
            f"{m.symbol}: makul olmayan start_time {start_time}"
        )


def test_scores_are_in_range_and_ranking_is_monotone(result):
    scores = np.array([m.score for m in result.results])
    percentiles = np.array([m.percentile for m in result.results])

    assert np.all(scores >= -1.0001) and np.all(scores <= 1.0001)
    assert np.all(percentiles >= 0.0) and np.all(percentiles <= 1.0)
    # Sıralama yüzdelik dilime göredir (K-14 / F3.5), skora göre değil.
    assert np.all(np.diff(percentiles) >= -1e-9), "yüzdelik sıralaması bozuk"


def test_same_query_is_reproducible(engine, query):
    """Null örneklemi sabit tohumlu: aynı sorgu aynı listeyi vermeli."""
    a = engine.search(query, timeframe=TIMEFRAME, tolerance="medium", limit=12)
    b = engine.search(query, timeframe=TIMEFRAME, tolerance="medium", limit=12)
    assert [m.symbol for m in a.results] == [m.symbol for m in b.results]
    assert [m.start_idx for m in a.results] == [m.start_idx for m in b.results]


def test_noise_query_is_not_discriminative(engine):
    """Negatif kontrol (K-18): gürültüye motor 'yapı yok' demeli."""
    rng = np.random.default_rng(7)
    from engine.normalize.pipeline import zscore

    noise = zscore(rng.normal(size=32))
    result = engine.search(noise, timeframe=TIMEFRAME, tolerance="medium", limit=12)

    # Ya ayırt edici değil, ya da sonuç sayısı şablonlarınkinin çok altında.
    assert (not result.discriminative) or result.total < 50, (
        f"white noise {result.total} sonuç döndürdü ve ayırt edici sayıldı"
    )


def test_matrix_and_symbol_map_agree(engine):
    """Matristeki her symbol_id haritada karşılık bulmalı.

    Bulmuyorsa eşleşmeler ``#897`` olarak görünür ve BarStore başka sembolün
    fiyatlarını okur — F4.6'yı geçersiz kılan hata buydu.
    """
    from engine.matrix.npy_store import load_matrix

    symbols = engine.symbols_for(TIMEFRAME)
    assert symbols, "sembol haritası boş"

    meta = np.asarray(load_matrix(matrix_dir(TIMEFRAME, WINDOW_LENGTHS[0]) / META_FILE))
    ids = set(np.unique(meta["symbol_id"]).tolist())
    missing = sorted(i for i in ids if int(i) not in symbols)
    assert not missing, f"haritada olmayan symbol_id: {missing[:10]}"


def test_cache_pool_covers_every_template(engine):
    """Hiçbir şablonun eşleşme toplamı önbellek havuzunu aşmamalı.

    Aşarsa istatistik **yanlı bir alt örneklemden** hesaplanır: kırpma
    rastgele değil, en iyi sıralanmış olanları tutar. Ölçülmüştü —
    rounding_bottom 4h'de 600 sınırıyla beklentiyi +0,0391R gösteriyordu,
    sınır kalkınca +0,0018R'ye düştü (21 kat).

    Bu test korpus büyüdükçe sınırın yeniden yetersiz kalmasını yakalar.
    """
    from engine.config import OUTCOME_TOLERANCE, SEARCH_CACHE_MATCHES
    from engine.templates import load_all

    over: list[tuple[str, int]] = []
    for template_id, template in load_all().items():
        query = np.asarray(template.vector, dtype=np.float64)
        total = engine.search(
            query, timeframe=TIMEFRAME, tolerance=OUTCOME_TOLERANCE, limit=1
        ).total
        if total > SEARCH_CACHE_MATCHES:
            over.append((template_id, total))

    assert not over, (
        f"SEARCH_CACHE_MATCHES={SEARCH_CACHE_MATCHES} yetersiz: {over}. "
        "İstatistik bu havuzdan hesaplanıyor; sınır aşılırsa örneklem "
        "en iyi eşleşmelere doğru yanlı kesilir."
    )
