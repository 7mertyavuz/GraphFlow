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
