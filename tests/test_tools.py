"""Doğrulama ve bakım araçlarının testleri.

Bu araçlar motoru denetliyor; denetleyenin kendisi denetlenmezse, sessiz bir
hata "her şey yolunda" raporu üretir — projenin iki kez yaşadığı hata sınıfı
tam olarak budur.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tools.backfill import missing_symbols, symbols_of
from tools.ci_calibration import simulate


# ---------------------------------------------------------------------------
# tools.backfill — hangi sembol eksik?
# ---------------------------------------------------------------------------


def _make_store(root, timeframe: str, symbols: list[str]) -> None:
    directory = root / timeframe
    directory.mkdir(parents=True, exist_ok=True)
    for s in symbols:
        pd.DataFrame({"open_time": [0], "close": [1.0]}).to_parquet(directory / f"{s}.parquet")


def test_symbols_of_reads_the_store(tmp_path):
    _make_store(tmp_path, "1d", ["BTCUSDT", "ETHUSDT"])
    assert symbols_of("1d", tmp_path) == ["BTCUSDT", "ETHUSDT"]


def test_symbols_of_missing_timeframe_is_empty_not_error(tmp_path):
    assert symbols_of("4h", tmp_path) == []


def test_missing_symbols_is_the_set_difference(tmp_path):
    _make_store(tmp_path, "1d", ["AAA", "BBB", "CCC"])
    _make_store(tmp_path, "4h", ["BBB"])
    assert missing_symbols("4h", "1d", tmp_path) == ["AAA", "CCC"]


def test_missing_symbols_empty_when_target_is_complete(tmp_path):
    """Zincir iki kez koşturulursa ikinci koşu hiçbir şey indirmemeli."""
    _make_store(tmp_path, "1d", ["AAA", "BBB"])
    _make_store(tmp_path, "4h", ["AAA", "BBB"])
    assert missing_symbols("4h", "1d", tmp_path) == []


# ---------------------------------------------------------------------------
# tools.ci_calibration — simülasyon gerçekten iddia ettiği veriyi üretiyor mu?
# ---------------------------------------------------------------------------


def test_simulation_has_zero_true_edge():
    """Kapsama ölçümünün tamamı 'gerçek edge sıfır' varsayımına dayanıyor."""
    rng = np.random.default_rng(0)
    diffs = []
    for _ in range(200):
        a, _, b, _ = simulate(rng, n_months=30, per_month=6, shadow_per_match=20, rho=0.384)
        diffs.append(a.mean() - b.mean())
    # Ortalama fark sıfır etrafında olmalı; sistematik kayma varsa simülasyon
    # kapsamayı değil kendi hatasını ölçerdi.
    assert abs(float(np.mean(diffs))) < 0.05


def test_simulation_produces_the_requested_within_month_correlation():
    """ρ parametresi gerçekten ay içi korelasyona dönüşüyor mu?"""
    rng = np.random.default_rng(1)
    target = 0.4
    a, am, _, _ = simulate(rng, n_months=200, per_month=40, shadow_per_match=1, rho=target)

    # Ay ortalamalarının varyansı ≈ ρ (bireysel gürültü ortalamada sönümlenir).
    frame = pd.DataFrame({"v": a, "m": am})
    month_means = frame.groupby("m")["v"].mean().to_numpy()
    assert float(np.var(month_means)) == pytest.approx(target, abs=0.08)


def test_match_only_factor_breaks_the_cancellation():
    """``rho_match`` eşleşme-gölge farkının varyansını ARTIRMALI.

    Ortak ay şoku farkta birbirini götürür; götürülmeyen tek şey budur ve
    F4.5'in gerçek veride ölçtüğü tasarım etkisi > 1 rejimi buradan doğar.
    """
    def spread(rho_match: float) -> float:
        rng = np.random.default_rng(5)
        diffs = []
        for _ in range(150):
            a, _, b, _ = simulate(
                rng, n_months=30, per_month=6, shadow_per_match=20,
                rho=0.384, rho_match=rho_match,
            )
            diffs.append(a.mean() - b.mean())
        return float(np.std(diffs))

    assert spread(0.30) > spread(0.0) * 1.5


# ---------------------------------------------------------------------------
# Denetçinin kendisi — F4.9 (docs/10-formasyon-denetimi.md)
# ---------------------------------------------------------------------------


def test_denetci_kosegeni_tam():
    """Her denetim yalnız kendi kanonik şeklini kabul etmeli.

    Bu, projedeki en kritik nöbetçilerden biri: denetçi gevşerse ölçtüğü
    doğruluk oranı da yükselir ve motor iyileşmiş GİBİ görünür. Her şeye
    "evet" diyen bir kontrol %100 raporlar ve hiçbir şey ölçmez.
    """
    from tools.formation_audit import CHECKS, cross_check

    matrix = cross_check()
    off = [
        (shape_id, name)
        for shape_id, row in matrix.items()
        for name, ok in row.items()
        if ok and name != shape_id
    ]
    assert off == [], f"köşegen dışı kabul: {off}"

    missing = [n for n in CHECKS if not matrix[n][n]]
    assert missing == [], f"kendi şeklini tanımayan denetim: {missing}"


def test_zarf_dokunuslari_pencere_ucunu_saymaz():
    """Uçlar dahil edilirse simetrik üçgenin alt zarfı TERS okunuyor.

    Ölçüldü: uçlarla -0,47 (düşen dipler), iç noktalarla +2,18 (yükselen
    dipler). Pencerenin ilk ve son barı bir dönüş noktası değil, verinin
    kesildiği yerdir.
    """
    import numpy as np

    from tools.formation_audit import envelope_slopes, envelope_touches
    from tools import shapes

    y = np.asarray(shapes.shape("symmetrical_triangle", 32), dtype=np.float64)
    y = (y - y.mean()) / y.std()

    highs, lows = envelope_touches(y)
    assert 0 not in highs and 0 not in lows
    assert (y.size - 1) not in highs and (y.size - 1) not in lows

    upper, lower = envelope_slopes(y)[:2]
    assert upper < -1.0, "simetrik üçgende tepeler düşmeli"
    assert lower > 1.0, "simetrik üçgende dipler yükselmeli"


def test_bayrak_takozdan_ayrilir():
    """Bayrağın kanalı paralel, takozunki yakınsak.

    Bu ayrım olmadan boğa bayrağı düşen takoz denetimini de geçiyordu —
    denetçi iki formasyonu karıştırıyorsa ölçtüğü şey formasyon değildir.
    """
    import numpy as np

    from tools.formation_audit import envelope_slopes, is_flag, is_wedge
    from tools import shapes

    def z(name: str):
        y = np.asarray(shapes.shape(name, 32), dtype=np.float64)
        return (y - y.mean()) / y.std()

    assert is_flag(z("bull_flag"), +1) and not is_wedge(z("bull_flag"), -1)
    assert is_wedge(z("falling_wedge"), -1) and not is_flag(z("falling_wedge"), +1)

    up, low = envelope_slopes(z("falling_wedge"))[:2]
    assert low - up > 0.8, "takoz yakınsamalı"
