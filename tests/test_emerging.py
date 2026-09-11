"""tools/emerging_test — aracın kendisi denetlenir: bilgi yokken 0,5, varken ≫ 0,5."""

from __future__ import annotations

import numpy as np

from engine.config import N_POINTS
from engine.templates import load_all
from tools.emerging_test import prefix_query, remaining_bars, score_event

THRESHOLD = 0.0273


def _template_path(template_id: str, length: int, noise: float, rng) -> np.ndarray:
    """Şablonu ``length`` bara açan log-fiyat yolu (+ gürültü) → kapanışlar."""
    v = np.asarray(load_all()[template_id].vector, dtype=np.float64)
    x = np.interp(np.linspace(0, N_POINTS - 1, length), np.arange(N_POINTS), v)
    return 100.0 * np.exp(0.08 * x + rng.normal(0, noise, length))


def test_onek_sorgusu_ilk_yuzde75_ve_normalize():
    q = prefix_query(np.asarray(load_all()["head_and_shoulders"].vector))
    assert q.shape == (N_POINTS,)
    assert abs(q.mean()) < 1e-9 and abs(q.std() - 1.0) < 1e-9
    assert [remaining_bars(L) for L in (24, 40, 64, 100)] == [8, 13, 21, 33]


def test_devam_sablonu_tamamliyorsa_auc_bire_yakin():
    """Pozitif kontrol: gerçek devam şablonun kendisi → kontrollerden hep yakın."""
    rng = np.random.default_rng(1)
    full = np.asarray(load_all()["head_and_shoulders"].vector)
    L, R = 48, remaining_bars(48)
    scores = []
    for _ in range(30):
        closes = _template_path("head_and_shoulders", L + R, 0.002, rng)
        donor = rng.normal(0, 0.01, size=(20, R))
        ev = score_event(full, closes, L, donor, THRESHOLD)
        scores.append(ev["prefix"][0])
    assert np.mean(scores) > 0.9


def test_devam_rastgeleyse_auc_yarim():
    """Negatif kontrol: gerçek devam kontrollerle AYNI süreçten (aynı oynaklık)
    → iki ölçekte de ~0,5. Bulursa ölçüm değil, uydurma yapıyordur."""
    rng = np.random.default_rng(2)
    full = np.asarray(load_all()["double_bottom"].vector)
    L, R = 48, remaining_bars(48)
    prefix = _template_path("double_bottom", L, 0.002, rng)
    sigma = np.diff(np.log(prefix)).std()
    scores = {"prefix": [], "shape": []}
    for _ in range(400):
        real_tail = prefix[-1] * np.exp(np.cumsum(rng.normal(0, sigma, R)))
        closes = np.concatenate([prefix, real_tail])
        donor = rng.normal(0, sigma, size=(20, R))
        ev = score_event(full, closes, L, donor, THRESHOLD)
        for k in scores:
            scores[k].append(ev[k][0])
    for k, v in scores.items():
        assert abs(np.mean(v) - 0.5) < 0.04, (k, np.mean(v))


def test_prefix_olcegi_oynaklik_degisimini_sekil_sanabilir_shape_sanmaz():
    """Karıştırıcı: devam önekten daha oynak ama YÖNÜ rastgele.

    ``prefix`` ölçeği kontrolü önekin oynaklığına çeker; gerçek devamla
    büyüklük farkı AUC'yi 0,5'ten uzaklaştırır — şekil bilgisi olmadan.
    ``shape`` ölçeği büyüklüğü eşitler ve 0,5'te kalır. Birincil ölçü bu
    yüzden ``shape``'tir (docs/13).
    """
    rng = np.random.default_rng(3)
    full = np.asarray(load_all()["double_bottom"].vector)
    L, R = 48, remaining_bars(48)
    prefix = _template_path("double_bottom", L, 0.002, rng)
    sigma = np.diff(np.log(prefix)).std()
    scores = {"prefix": [], "shape": []}
    for _ in range(400):
        real_tail = prefix[-1] * np.exp(np.cumsum(rng.normal(0, 5 * sigma, R)))
        closes = np.concatenate([prefix, real_tail])
        donor = rng.normal(0, sigma, size=(20, R))
        ev = score_event(full, closes, L, donor, THRESHOLD)
        for k in scores:
            scores[k].append(ev[k][0])
    assert abs(np.mean(scores["prefix"]) - 0.5) > 0.1
    assert abs(np.mean(scores["shape"]) - 0.5) < 0.04
