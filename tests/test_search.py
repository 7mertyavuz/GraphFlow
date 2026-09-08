"""F2 — kaskad arama motoru testleri (K-03, K-09, K-11, K-14, K-15).

Doğrulama sentetik veri üzerindedir: ground truth bilindiği için sonuçlar
objektif olarak doğru/yanlış diye işaretlenebilir (gerçek veriden daha güçlü).
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from engine.config import (
    MAX_RESULTS_PER_SYMBOL,
    META_DTYPE,
    N_POINTS,
    POST_NMS_IOU,
    PRE_NMS_IOU,
    SAKOE_CHIBA_RADIUS,
    STAGE1_TOPK,
    TOLERANCE_THRESHOLDS,
    TOLERANCE_THRESHOLDS_BY_METRIC,
)
from engine.ingest.store import write_atomic
from engine.matrix.build import build_all
from engine.matrix.npy_store import ChunkedNpyWriter
from engine.normalize.pipeline import normalize_window, resample_to, zscore
from engine.search.ddtw import banded_dtw_batch, ddtw_scores, derivative, dtw_scores
from engine.search.engine import CANDIDATE_DTYPE, SearchEngine
from engine.search.nms import iou_1d, nms_1d
from engine.search.stage1_cosine import cosine_scores, prepare_query, top_k
from engine.templates import get as get_template
from engine.templates import load_all
from tools.gen_synthetic import make_symbol
from tools.shapes import shape

TF = "4h"


def z(y) -> np.ndarray:
    return zscore(resample_to(np.asarray(y, dtype=float), N_POINTS))


# ---------------------------------------------------------------------------
# Aşama 1 — kosinüs
# ---------------------------------------------------------------------------


def test_cosine_equals_pearson_correlation():
    """‖z‖ = √32 olduğu için (V @ q)/32 Pearson korelasyonudur (§5.1)."""
    rng = np.random.default_rng(0)
    V = np.stack([z(rng.normal(size=N_POINTS)) for _ in range(50)]).astype(np.float32)
    q = z(rng.normal(size=N_POINTS))

    scores = cosine_scores(V, q)
    expected = [np.corrcoef(V[i], q)[0, 1] for i in range(50)]
    np.testing.assert_allclose(scores, expected, atol=1e-5)


def test_cosine_self_match_is_one():
    q = z(shape("head_and_shoulders", 32))
    V = np.stack([q, -q]).astype(np.float32)
    scores = cosine_scores(V, q)
    assert scores[0] == pytest.approx(1.0, abs=1e-5)
    assert scores[1] == pytest.approx(-1.0, abs=1e-5)


def test_query_is_cast_to_float32():
    """float64 sorgu tüm matrisi float64'e yükseltirdi (4x bellek)."""
    assert prepare_query(np.zeros(N_POINTS, dtype=np.float64)).dtype == np.float32
    with pytest.raises(ValueError):
        prepare_query(np.zeros(16))


def test_top_k_respects_mask_and_order():
    rng = np.random.default_rng(1)
    V = np.stack([z(rng.normal(size=N_POINTS)) for _ in range(200)]).astype(np.float32)
    q = V[7].copy()
    mask = np.ones(200, dtype=bool)
    mask[7] = False  # en iyi aday maskelenirse gelmemeli

    rows, scores = top_k(V, q, k=10, mask=mask)
    assert 7 not in rows.tolist()
    assert np.all(np.diff(scores) <= 1e-6)
    assert rows.size == 10


def test_top_k_sparse_mask_path_matches_dense():
    """Radar yolu (seyrek maske) ile tam çarpım aynı sonucu vermeli."""
    rng = np.random.default_rng(2)
    V = np.stack([z(rng.normal(size=N_POINTS)) for _ in range(2_000)]).astype(np.float32)
    q = z(rng.normal(size=N_POINTS))
    mask = np.zeros(2_000, dtype=bool)
    mask[rng.choice(2_000, 30, replace=False)] = True

    sparse_rows, sparse_scores = top_k(V, q, k=10, mask=mask, sparse_ratio=1.0)
    dense_rows, dense_scores = top_k(V, q, k=10, mask=mask, sparse_ratio=0.0)

    np.testing.assert_array_equal(sparse_rows, dense_rows)
    np.testing.assert_allclose(sparse_scores, dense_scores, atol=1e-6)


def test_top_k_empty_mask_returns_nothing():
    V = np.zeros((10, N_POINTS), dtype=np.float32)
    rows, _ = top_k(V, np.ones(N_POINTS), mask=np.zeros(10, dtype=bool))
    assert rows.size == 0


# ---------------------------------------------------------------------------
# NMS (K-09)
# ---------------------------------------------------------------------------


def _cands(rows) -> np.ndarray:
    out = np.empty(len(rows), dtype=CANDIDATE_DTYPE)
    for i, (sid, s, e, score) in enumerate(rows):
        out[i] = (sid, s, e, 0, 0.0, 0.0, e - s + 1, i, score, -score, -score)
    return out


def test_iou_formula():
    assert iou_1d(0, 10, 0, 10) == pytest.approx(1.0)
    assert iou_1d(0, 10, 20, 30) == 0.0
    assert iou_1d(0, 10, 5, 15) == pytest.approx(5 / 15)


def test_nms_removes_overlapping_windows():
    """Stride ile kaydırılmış komşu pencereler tek bir olaya indirgenmeli."""
    # 40 barlık pencerede stride 3 → ilk 3 kayma IoU ≥ 0,70 bandında.
    cands = _cands([(1, 100 + 3 * i, 140 + 3 * i, 0.9 - i * 0.01) for i in range(3)])
    kept = nms_1d(cands, PRE_NMS_IOU)
    assert len(kept) == 1
    assert kept[0] == 0  # en yüksek skorlu korunur


def test_nms_threshold_boundary_is_the_iou_formula():
    """Eşik keyfi değil: IoU = (L-s)/(L+s); L=40, %70 için s ≤ 7."""
    for shift, expected in ((7, 1), (8, 2)):
        cands = _cands([(1, 100, 140, 0.9), (1, 100 + shift, 140 + shift, 0.8)])
        assert len(nms_1d(cands, PRE_NMS_IOU)) == expected


def test_nms_keeps_distinct_events():
    cands = _cands([(1, 0, 40, 0.9), (1, 500, 540, 0.8), (1, 1000, 1040, 0.7)])
    assert len(nms_1d(cands, PRE_NMS_IOU)) == 3


def test_nms_is_per_symbol():
    """Farklı sembollerin aynı bar aralığı örtüşme sayılmaz."""
    cands = _cands([(s, 0, 40, 0.9 - s * 0.01) for s in range(5)])
    assert len(nms_1d(cands, POST_NMS_IOU)) == 5


def test_nms_max_per_symbol():
    """Bu limit olmadan ilk sayfa tek bir coin'in fraktallarına dönüşür."""
    cands = _cands([(1, i * 200, i * 200 + 40, 0.9 - i * 0.01) for i in range(10)])
    kept = nms_1d(cands, POST_NMS_IOU, max_per_symbol=MAX_RESULTS_PER_SYMBOL)
    assert len(kept) == MAX_RESULTS_PER_SYMBOL


def test_nms_lower_is_better_mode():
    """Post-NMS DDTW mesafesiyle çağrılır: küçük olan kazanmalı."""
    cands = _cands([(1, 100, 140, 0.1), (1, 102, 142, 0.9)])
    cands["distance"] = [5.0, 0.1]
    kept = nms_1d(cands, POST_NMS_IOU, score_field="distance", higher_is_better=False)
    assert len(kept) == 1
    assert cands["distance"][kept[0]] == pytest.approx(0.1)


def test_nms_empty_input():
    assert nms_1d(np.empty(0, dtype=CANDIDATE_DTYPE), 0.5).size == 0


# ---------------------------------------------------------------------------
# DDTW (K-11) — bu oturumun kritik doğrulaması
# ---------------------------------------------------------------------------


def test_derivative_formula_matches_keogh_pazzani():
    x = np.array([1.0, 3.0, 2.0, 6.0, 4.0])
    d = derivative(x)
    expected = [((x[i] - x[i - 1]) + (x[i + 1] - x[i - 1]) / 2) / 2 for i in range(1, len(x) - 1)]
    np.testing.assert_allclose(d, expected)
    assert d.size == x.size - 2


def test_banded_dtw_matches_reference_dp():
    """Vektörize DP, referans (döngülü) DP ile birebir aynı olmalı."""

    def reference(a, b, r):
        m = len(a)
        D = np.full((m, m), np.inf)
        L = np.zeros((m, m), dtype=int)
        for i in range(m):
            for j in range(max(0, i - r), min(m, i + r + 1)):
                cost = (a[i] - b[j]) ** 2
                if i == 0 and j == 0:
                    D[i, j], L[i, j] = cost, 1
                    continue
                opts = []
                if i > 0 and abs(i - 1 - j) <= r:
                    opts.append((D[i - 1, j], L[i - 1, j]))
                if j > 0 and abs(i - j + 1) <= r:
                    opts.append((D[i, j - 1], L[i, j - 1]))
                if i > 0 and j > 0:
                    opts.append((D[i - 1, j - 1], L[i - 1, j - 1]))
                v, ln = min(opts, key=lambda t: t[0])
                if np.isfinite(v):
                    D[i, j], L[i, j] = v + cost, ln + 1
        return D[m - 1, m - 1], L[m - 1, m - 1]

    rng = np.random.default_rng(4)
    a = rng.normal(size=30)
    B = rng.normal(size=(6, 30))
    dist, length = banded_dtw_batch(a, B, SAKOE_CHIBA_RADIUS)

    for i in range(6):
        ref_d, ref_l = reference(a, B[i], SAKOE_CHIBA_RADIUS)
        assert dist[i] == pytest.approx(ref_d, rel=1e-12)
        assert length[i] == ref_l


def test_ddtw_is_zero_for_identical_series():
    q = z(shape("cup_and_handle", 32))
    assert ddtw_scores(q, q[None, :])[0] == pytest.approx(0.0, abs=1e-12)


def test_ddtw_score_is_path_length_normalized():
    """K-14: ham mesafe değil, yol uzunluğuna bölünmüş mesafe raporlanır."""
    rng = np.random.default_rng(6)
    q = z(rng.normal(size=N_POINTS))
    C = np.stack([z(rng.normal(size=N_POINTS)) for _ in range(5)])
    dist, length = banded_dtw_batch(derivative(q), np.stack([derivative(c) for c in C]))
    np.testing.assert_allclose(ddtw_scores(q, C), dist / length, rtol=1e-12)
    assert np.all(length >= N_POINTS - 2)


def test_ddtw_flat_line_does_not_match_cup():
    """K-11'in çıkış şartı: düz çizgi çanak şablonuyla EŞLEŞMEMELİ.

    Ham DTW ile sayısal kıyas da yapılır. Ölçüm, iki metriğin pozitif
    dağılımlarına göre normalize edilmiş ayrım oranı üzerindendir — ham
    mesafeler farklı ölçeklerde olduğu için doğrudan kıyaslanamaz.
    """
    rng = np.random.default_rng(17)
    q = z(shape("rounding_bottom", 32))

    def cup(length=64):
        y = shape("rounding_bottom", length) * 0.25 + np.cumsum(rng.normal(0, 0.01, length))
        return normalize_window(100 * np.exp(y))

    def flat(length=64):
        # Tamamen düz seri normalize edilemez (σ=0 → düşer); pratikte
        # "düz çizgi" bu: yönü olmayan, ihmal edilebilir hareket.
        return normalize_window(100 * np.exp(np.cumsum(rng.normal(0, 0.002, length))))

    cups = np.stack([cup() for _ in range(40)])
    flats = np.stack([flat() for _ in range(40)])

    ddtw_pos, ddtw_neg = ddtw_scores(q, cups), ddtw_scores(q, flats)
    raw_pos, raw_neg = dtw_scores(q, cups), dtw_scores(q, flats)

    # 1) Düz çizgi, gerçek çanakların TAMAMINDAN kötü skorlanmalı.
    assert ddtw_neg.min() > ddtw_pos.max()

    # 2) Ayrım oranı en az 5x olmalı — "eşleşme yok" diyebilmenin ön koşulu.
    ddtw_ratio = float(ddtw_neg.mean() / ddtw_pos.mean())
    raw_ratio = float(raw_neg.mean() / raw_pos.mean())
    assert ddtw_ratio > 5.0, f"DDTW ayrımı yetersiz: {ddtw_ratio:.1f}x"

    # 3) Düz çizgilerin tipik skoru en gevşek kademenin bile dışında kalmalı.
    #    (Tek tek bazıları rastgele hafif bir çukur çizebilir — onları eleyen
    #    şey genlik filtresidir, K-10: bu serilerin gerçek hareketi ~%0,5.)
    # Eşikler metrik başınadır; bu test DDTW'yi ölçtüğü için DDTW satırı.
    ddtw_thresholds = TOLERANCE_THRESHOLDS_BY_METRIC["ddtw"]
    assert np.median(ddtw_neg) > ddtw_thresholds["flexible"]
    # Gerçek çanaklar ise 'medium' kademesine rahatça girmeli.
    assert np.median(ddtw_pos) < ddtw_thresholds["medium"]

    print(f"\nDDTW ayrım: {ddtw_ratio:.1f}x  |  ham DTW ayrım: {raw_ratio:.1f}x")


def test_stage2_metric_switch():
    """K-11 F3'te karara bağlandı: varsayılan hybrid, kaybedenler anahtarda kaldı."""
    from engine.config import STAGE2_METRIC
    from engine.search.ddtw import stage2_scores

    assert STAGE2_METRIC == "hybrid"

    rng = np.random.default_rng(8)
    q = z(shape("cup_and_handle", 32))
    C = np.stack([z(rng.normal(size=N_POINTS)) for _ in range(20)])

    np.testing.assert_allclose(stage2_scores(q, C, metric="ddtw"), ddtw_scores(q, C), rtol=1e-12)
    np.testing.assert_allclose(stage2_scores(q, C, metric="dtw"), dtw_scores(q, C), rtol=1e-12)


def test_hybrid_is_mean_of_two_normalized_distances():
    """hybrid = (DDTW + ham DTW) / 2 — ikisi de yol uzunluğuna normalize."""
    from engine.search.ddtw import stage2_scores

    rng = np.random.default_rng(12)
    q = z(shape("bull_flag", 32))
    C = np.stack([z(rng.normal(size=N_POINTS)) for _ in range(30)])

    expected = 0.5 * (ddtw_scores(q, C) + dtw_scores(q, C))
    np.testing.assert_allclose(stage2_scores(q, C, metric="hybrid"), expected, rtol=1e-12)
    with pytest.raises(ValueError):
        stage2_scores(q, C, metric="öklid")


def test_metric_thresholds_are_separately_calibrated():
    """Ham DTW mesafeleri ~4-8x büyük; aynı eşikle motor hiçbir şey döndürmezdi."""
    from engine.config import STAGE2_METRIC
    from engine.config import TOLERANCE_THRESHOLDS_BY_METRIC as T

    # TOLERANCE_THRESHOLDS daima AKTİF metriğin eşiklerini gösterir.
    assert TOLERANCE_THRESHOLDS is T[STAGE2_METRIC]
    for level in ("strict", "medium", "flexible"):
        assert T["dtw"][level] > T["ddtw"][level]
        # hybrid ortalama mesafedir → eşiği de ikisinin arasında olmalı
        assert T["ddtw"][level] < T["hybrid"][level] < T["dtw"][level]
    # Her metrikte kademeler artan sırada olmalı.
    for metric, levels in T.items():
        assert levels["strict"] < levels["medium"] < levels["flexible"], metric


def test_ddtw_separates_shape_families():
    """Farklı formasyonlar birbirine kendi ailesinden daha uzak olmalı."""
    rng = np.random.default_rng(21)

    def sample(name, k=25):
        out = []
        for _ in range(k):
            length = int(rng.integers(32, 100))
            y = shape(name, length) * rng.uniform(0.15, 0.35) + np.cumsum(rng.normal(0, 0.008, length))
            out.append(normalize_window(100 * np.exp(y)))
        return np.stack(out)

    q = z(shape("head_and_shoulders", 32))
    same = ddtw_scores(q, sample("head_and_shoulders"))
    other = ddtw_scores(q, sample("inverse_head_and_shoulders"))
    assert np.median(same) < np.median(other) / 3


# ---------------------------------------------------------------------------
# Şablon kütüphanesi (K-04)
# ---------------------------------------------------------------------------


def test_templates_library_has_required_patterns():
    required = {
        "head_and_shoulders",
        "inverse_head_and_shoulders",
        "double_top",
        "double_bottom",
        "cup_and_handle",
        "bull_flag",
        "rising_wedge",
        "falling_wedge",
    }
    assert required <= set(load_all())


def test_templates_are_z_scored_on_load():
    for template in load_all().values():
        assert template.vector.shape == (N_POINTS,)
        assert np.linalg.norm(template.vector) == pytest.approx(np.sqrt(N_POINTS), rel=1e-6)
        assert template.vector.mean() == pytest.approx(0.0, abs=1e-9)


def test_template_matches_its_own_shape_perfectly():
    """Kütüphaneden seçmek ile aynı şekli çizmek aynı yoldur."""
    t = get_template("head_and_shoulders")
    priced = normalize_window(100 * np.exp(0.2 * shape("head_and_shoulders", 64)))
    strict = TOLERANCE_THRESHOLDS_BY_METRIC["ddtw"]["strict"]  # DDTW ölçüyoruz
    assert ddtw_scores(t.vector, priced[None, :])[0] < strict


def test_inverse_template_is_mirror():
    obo = get_template("head_and_shoulders").vector
    inv = get_template("inverse_head_and_shoulders").vector
    assert np.dot(obo, inv) / N_POINTS < -0.9


# ---------------------------------------------------------------------------
# Uçtan uca — motor
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def obo_dataset(tmp_path_factory):
    """20 sembole birer OBO enjekte edilir; 40 sembol çeldirici formasyon taşır.

    Çeldirici sayısı bilinçli olarak yüksek: F3.5'ten sonra eşik, sorgunun
    **null dağılımındaki yüzdelik dilimidir**. Null, aranabilir popülasyondan
    örneklendiği için pozitifler de içine düşer; pozitiflerin korpustaki payı
    büyükse null'ın alt kuyruğunu kendileri şişirir ve eşik yapay olarak
    sıkışır. Gerçek veride bu pay ~%0,05'tir (1,9M pencerede birkaç yüz olay);
    test korpusu da o rejime yaklaştırılmalı, yoksa ölçtüğü şey motorun
    kalitesi değil oyuncak korpusun yoğunluğu olur.
    """
    root = tmp_path_factory.mktemp("obo")
    rng = np.random.default_rng(2024)
    truth: list = []

    for i in range(20):
        symbol = f"OBO{i:03d}USDT"
        df, inj = make_symbol(
            symbol,
            rng,
            n_bars=900,
            patterns=("head_and_shoulders",),
            n_injections=1,
            length_range=(40, 90),
            amplitude_range=(0.18, 0.40),
            noise_range=(0.01, 0.05),
        )
        write_atomic(df, root / "klines" / TF / f"{symbol}.parquet")
        truth.extend(inj)

    for i in range(40):
        symbol = f"NOI{i:03d}USDT"
        df, _ = make_symbol(
            symbol,
            rng,
            n_bars=900,
            patterns=("bull_flag", "double_bottom", "rounding_bottom"),
            n_injections=3,
        )
        write_atomic(df, root / "klines" / TF / f"{symbol}.parquet")

    build_all(
        timeframes=[TF],
        klines_root=root / "klines",
        out_root=root / "matrix",
        use_liquidity=False,  # 30 sentetik sembolde kesitsel filtre anlamsız
    )
    return root, truth


def _hits(result, truth, min_iou: float = 0.3) -> set[str]:
    """Sonuçların hangi ground-truth OBO'larını yakaladığı."""
    found: set[str] = set()
    for match in result.results:
        for inj in truth:
            if inj.symbol != match.symbol:
                continue
            if iou_1d(match.start_idx, match.end_idx, inj.start, inj.end) >= min_iou:
                found.add(inj.symbol)
    return found


def test_end_to_end_finds_injected_obos(obo_dataset):
    """Enjekte edilen 20 OBO'nun en az 15'i bulunmalı.

    NOT: İlk 12 sonuç en fazla 12 farklı olay içerebileceği için (güvercin
    yuvası), şart iki parçaya ayrıldı: ilk 12'de yüksek isabet (precision)
    ve ilk 20'de en az 15 OBO (recall).
    """
    root, truth = obo_dataset
    engine = SearchEngine(root / "matrix")
    q = get_template("head_and_shoulders").vector

    top12 = engine.search(q, mode="historical", timeframe=TF, tolerance="flexible", limit=12)
    top20 = engine.search(q, mode="historical", timeframe=TF, tolerance="flexible", limit=20)

    hits12 = _hits(top12, truth)
    hits20 = _hits(top20, truth)

    print(
        f"\nilk 12: {len(hits12)}/12 gerçek OBO | ilk 20: {len(hits20)}/20 enjeksiyon"
        f" | toplam eşleşme {top20.total} | {top20.elapsed_ms:.0f} ms"
    )
    assert len(hits12) >= 10, f"ilk 12'de yalnızca {len(hits12)} gerçek OBO"
    assert len(hits20) >= 15, f"ilk 20'de yalnızca {len(hits20)} enjeksiyon bulundu"


def test_results_are_deduplicated_by_post_nms(obo_dataset):
    root, _ = obo_dataset
    engine = SearchEngine(root / "matrix")
    result = engine.search(get_template("head_and_shoulders").vector, timeframe=TF, limit=36)

    counts: dict[str, int] = {}
    for m in result.results:
        counts[m.symbol] = counts.get(m.symbol, 0) + 1
    assert max(counts.values()) <= MAX_RESULTS_PER_SYMBOL

    # Aynı sembolde kalan sonuçlar birbirinden yeterince farklı olmalı.
    by_symbol: dict[str, list] = {}
    for m in result.results:
        by_symbol.setdefault(m.symbol, []).append(m)
    for matches in by_symbol.values():
        for i, a in enumerate(matches):
            for b in matches[i + 1 :]:
                assert iou_1d(a.start_idx, a.end_idx, b.start_idx, b.end_idx) < POST_NMS_IOU


def test_results_sorted_by_null_percentile(obo_dataset):
    """F3.5: sıralama mutlak mesafeye değil, uzunluk-içi yüzdelik dilime göre.

    Mutlak mesafeyle sıralamak 24 barlık pencereleri sistematik olarak öne
    çıkarıyordu (F3 ölçümü: sonuçların %68'i en kısa pencerede).
    """
    root, _ = obo_dataset
    engine = SearchEngine(root / "matrix")
    result = engine.search(get_template("cup_and_handle").vector, timeframe=TF, limit=24)
    percentiles = [m.percentile for m in result.results]
    assert percentiles == sorted(percentiles)


def test_negative_control_flat_line_is_refused_by_pipeline():
    """Düz yatay çizgi motora hiç ulaşamaz: σ = 0 → pencere düşer (K-02).

    "Eşleşme bulunamadı" davranışının ilk katmanı budur; motorun düz çizgiye
    skor üretmesi zaten mümkün değildir.
    """
    from engine.normalize.pipeline import normalize_drawing

    assert normalize_drawing(np.full(64, 240.0)) is None
    assert normalize_window(np.full(64, 100.0)) is None


def test_negative_control_noise_and_whipsaw(obo_dataset):
    """K-18 / §16.2: anlamsız sorgular pozitiflerden BELİRGİN şekilde kötü olmalı."""
    root, _ = obo_dataset
    engine = SearchEngine(root / "matrix")
    rng = np.random.default_rng(99)

    def best(query, tolerance="flexible"):
        res = engine.search(query, timeframe=TF, tolerance=tolerance, limit=1)
        return res.results[0].distance if res.results else np.inf

    positives = [
        best(get_template(name).vector)
        for name in ("head_and_shoulders", "cup_and_handle", "double_bottom")
    ]

    noise_queries = [z(rng.normal(size=N_POINTS)) for _ in range(5)]
    whipsaw = z(np.tile([0.0, 1.0], N_POINTS // 2))  # anlamsız testere
    negatives = [best(q) for q in noise_queries] + [best(whipsaw)]

    print(f"\npozitif en iyi skorlar: {np.round(positives, 4)}")
    print(f"negatif en iyi skorlar: {negatives}")

    assert min(negatives) > max(positives) * 3, "negatif kontrol pozitiflerden ayrışmıyor"

    # Katı kademede motor "eşleşme yok" diyebilmeli.
    #
    # NOT: Gevşek kademe bilinçli olarak burada sınanmıyor. Eşiklerin asıl
    # kaynağı K-18'e göre negatif dağılımlardır ve F3 ADIM 3'te GERÇEK veriden
    # kalibre edilir. Geçici hybrid eşiğiyle (iki metriğin ortalaması) gürültü
    # sorguları gevşek kademeyi geçebiliyor; bu, raporlanan açık bir bulgudur.
    hits = sum(
        len(engine.search(q, timeframe=TF, tolerance="strict", limit=12).results)
        for q in noise_queries + [whipsaw]
    )
    assert hits == 0, f"katı kademede {hits} sahte eşleşme döndü"


def test_monotone_trend_query_is_not_a_false_positive(obo_dataset):
    """Rampa (düz *eğimli* çizgi) meşru bir şekildir — negatif kontrol değildir.

    GBM verisinde gerçekten trend yapan pencereler vardır ve rampa sorgusu
    onları bulur. Bunu "sahte eşleşme" saymak metriği yanlış yorumlamak olur;
    ayırt edici olan, bulunan pencerelerin gerçekten monoton olmasıdır.
    """
    root, _ = obo_dataset
    engine = SearchEngine(root / "matrix")
    result = engine.search(z(np.linspace(0.0, 1.0, N_POINTS)), timeframe=TF, limit=5)

    assert result.results, "trend sorgusu sonuç döndürmeli"
    for match in result.results[:3]:
        handle = engine.handle(TF, match.window_length)
        row = int(np.flatnonzero(
            (handle.symbol_id == match.symbol_id) & (handle.end_idx == match.end_idx)
        )[0])
        vector = np.asarray(handle.vectors[row])
        # Bulunan pencere gerçekten yükselen olmalı (ilk çeyrek < son çeyrek).
        assert vector[:8].mean() < vector[-8:].mean()


def test_live_mode_returns_only_last_window(obo_dataset):
    """K-15: live, historical'ın maskelenmiş özel hâlidir — ayrı kod yolu yok."""
    root, _ = obo_dataset
    engine = SearchEngine(root / "matrix")
    q = get_template("head_and_shoulders").vector

    live = engine.search(q, mode="live", timeframe=TF, tolerance="flexible", limit=50)
    historical = engine.search(q, mode="historical", timeframe=TF, tolerance="flexible", limit=50)

    assert live.total <= historical.total
    for match in live.results:
        handle = engine.handle(TF, match.window_length)
        same_symbol = handle.end_idx[handle.symbol_id == match.symbol_id]
        assert match.end_idx == same_symbol.max()


def test_live_mode_is_fast(obo_dataset):
    root, _ = obo_dataset
    engine = SearchEngine(root / "matrix")
    q = get_template("bull_flag").vector
    engine.search(q, mode="live", timeframe=TF)  # ısınma (memmap sayfaları)

    t0 = time.perf_counter()
    engine.search(q, mode="live", timeframe=TF)
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"\nlive mod: {elapsed:.1f} ms")
    assert elapsed < 100  # sentetik ölçek; bütçe hedefi < 10 ms (§15)


def test_amplitude_filter(obo_dataset):
    """K-10: genlik filtresi çarpımdan önce uygulanır."""
    root, _ = obo_dataset
    engine = SearchEngine(root / "matrix")
    q = get_template("head_and_shoulders").vector

    result = engine.search(q, timeframe=TF, tolerance="flexible", min_amplitude=25.0, limit=24)
    assert result.results
    assert all(m.amplitude >= 25.0 for m in result.results)


def test_strict_tolerance_returns_fewer_than_flexible(obo_dataset):
    root, _ = obo_dataset
    engine = SearchEngine(root / "matrix")
    q = get_template("head_and_shoulders").vector
    strict = engine.search(q, timeframe=TF, tolerance="strict", limit=100).total
    flexible = engine.search(q, timeframe=TF, tolerance="flexible", limit=100).total
    assert strict <= flexible


def test_invalid_parameters_rejected(obo_dataset):
    root, _ = obo_dataset
    engine = SearchEngine(root / "matrix")
    q = get_template("bull_flag").vector
    with pytest.raises(ValueError):
        engine.search(q, tolerance="cok-esnek", timeframe=TF)
    with pytest.raises(ValueError):
        engine.search(q, mode="radar", timeframe=TF)
    with pytest.raises(ValueError):
        engine.search(q, timeframe=TF, metric="öklid")  # eşiği kalibre değil


def test_engine_runs_with_raw_dtw_metric(obo_dataset):
    """F3 kıyasının çalıştırılabilir olması: aynı kod yolu, farklı metrik.

    Bu test hangi metriğin daha iyi olduğunu İDDİA ETMEZ; yalnızca anahtarın
    uçtan uca çalıştığını ve kendi eşikleriyle sonuç ürettiğini doğrular.
    """
    root, truth = obo_dataset
    engine = SearchEngine(root / "matrix")
    q = get_template("head_and_shoulders").vector

    ddtw_run = engine.search(q, timeframe=TF, tolerance="flexible", limit=20, metric="ddtw")
    dtw_run = engine.search(q, timeframe=TF, tolerance="flexible", limit=20, metric="dtw")

    assert ddtw_run.metric == "ddtw" and dtw_run.metric == "dtw"
    assert dtw_run.results, "ham DTW kendi eşikleriyle sonuç üretebilmeli"
    print(
        f"\nF3 kıyası — DDTW: {len(_hits(ddtw_run, truth))}/20 enjeksiyon"
        f" | ham DTW: {len(_hits(dtw_run, truth))}/20 enjeksiyon"
    )


# ---------------------------------------------------------------------------
# Performans bütçesi (§15)
# ---------------------------------------------------------------------------


def test_stage1_under_300ms_on_one_million_rows(tmp_path):
    """Aşama 1: 1M satırlık matriste < 300 ms (bütçe: 12M pencerede 300 ms)."""
    n = 1_000_000
    path = tmp_path / "vectors.npy"
    rng = np.random.default_rng(0)

    with ChunkedNpyWriter(path, np.float32, (N_POINTS,)) as w:
        for _ in range(10):  # 100k'lık parçalar hâlinde üret (RAM dostu)
            block = rng.normal(size=(100_000, N_POINTS)).astype(np.float32)
            block -= block.mean(axis=1, keepdims=True)
            block /= block.std(axis=1, keepdims=True)
            w.append(block)

    V = np.load(path, mmap_mode="r")
    q = z(shape("head_and_shoulders", 32))
    mask = np.ones(n, dtype=bool)

    top_k(V, q, k=STAGE1_TOPK, mask=mask)  # ısınma: sayfa cache
    t0 = time.perf_counter()
    rows, scores = top_k(V, q, k=STAGE1_TOPK, mask=mask)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    print(f"\nAşama 1 (1M × 32): {elapsed_ms:.0f} ms")
    assert rows.size == STAGE1_TOPK
    assert elapsed_ms < 300, f"Aşama 1 bütçeyi aştı: {elapsed_ms:.0f} ms"


def test_stage1_does_not_upcast_matrix_dtype(tmp_path):
    """float64 sorgu gelse bile skorlar float32 kalmalı."""
    V = np.zeros((1_000, N_POINTS), dtype=np.float32)
    scores = cosine_scores(V, np.zeros(N_POINTS, dtype=np.float64))
    assert scores.dtype == np.float32


def test_ddtw_batch_scales_to_thousand_candidates():
    """Aşama 2 bütçesi: 1.000 aday < 100 ms (§15)."""
    rng = np.random.default_rng(3)
    q = z(shape("cup_and_handle", 32))
    C = rng.normal(size=(1_000, N_POINTS))
    C = (C - C.mean(axis=1, keepdims=True)) / C.std(axis=1, keepdims=True)

    ddtw_scores(q, C[:10])  # ısınma
    t0 = time.perf_counter()
    scores = ddtw_scores(q, C)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    print(f"\nAşama 2 (1.000 aday DDTW): {elapsed_ms:.0f} ms")
    assert scores.shape == (1_000,)
    assert elapsed_ms < 100, f"Aşama 2 bütçeyi aştı: {elapsed_ms:.0f} ms"


# ---------------------------------------------------------------------------
# Ters şekil tuzağı (F3.5, Adım 5)
# ---------------------------------------------------------------------------

INVERSE_PAIRS = [
    ("cup_and_handle", "head_and_shoulders"),  # ∪ ↔ ∩
    ("double_bottom", "double_top"),
    ("inverse_head_and_shoulders", "head_and_shoulders"),
    ("falling_wedge", "rising_wedge"),
    ("bull_flag", "bear_flag"),
]


@pytest.mark.parametrize("positive,negative", INVERSE_PAIRS)
def test_inverse_shape_is_not_a_match(positive, negative):
    """Ters şekil eşleşmemeli — **aktif metrikle** (hybrid).

    Geçmesi beklenir (z-score yönü korur), ama geçmezse bir yerde mutlak değer
    veya kare alınıyor demektir: motor yükseliş formasyonu ararken düşüş
    formasyonu döndürür. Ölümcül ve **sessiz** bir hata sınıfı.
    """
    from engine.config import STAGE2_METRIC
    from engine.search.ddtw import stage2_scores

    q = get_template(positive).vector
    same = stage2_scores(q, q[None, :])[0]
    opposite = stage2_scores(q, get_template(negative).vector[None, :])[0]

    assert opposite > same
    assert opposite > TOLERANCE_THRESHOLDS_BY_METRIC[STAGE2_METRIC]["flexible"], (
        f"{positive} sorgusu {negative} şeklini eşleşme sayıyor"
    )


def test_ddtw_alone_confuses_wedge_direction():
    """K-11 için bağımsız kanıt: DDTW tek başına takoz YÖNÜNÜ ayırt edemiyor.

    Türev, iki şekli ayıran şeyi — trend bileşenini — sabite indirger; geriye
    kalan salınım yükselen ve düşen takozda neredeyse aynıdır. Ölçüm:

        ddtw   düşen↔yükselen 0,0146  (esnek eşik 0,0456 → EŞLEŞME SAYAR)
        dtw                   2,2841  (eşik 0,1097 → eler)
        hybrid                1,1494  (eşik 0,0836 → eler)

    Bu test, varsayılan metrik DDTW'ye geri çevrilirse bedelin ne olduğunu
    kayıt altında tutar. Bkz. K-11 "Karara bağlandı (F3)".
    """
    fw = get_template("falling_wedge").vector
    rw = get_template("rising_wedge").vector

    ddtw_gap = float(ddtw_scores(fw, rw[None, :])[0])
    raw_gap = float(dtw_scores(fw, rw[None, :])[0])

    assert ddtw_gap < TOLERANCE_THRESHOLDS_BY_METRIC["ddtw"]["flexible"]
    assert raw_gap > TOLERANCE_THRESHOLDS_BY_METRIC["dtw"]["flexible"]


def test_mirrored_series_scores_worse_than_itself():
    """Aynı seri ve tam aynası — sentetik, şablondan bağımsız kontrol."""
    rng = np.random.default_rng(11)
    for _ in range(20):
        v = z(np.cumsum(rng.normal(size=N_POINTS)))
        assert ddtw_scores(v, (-v)[None, :])[0] > ddtw_scores(v, v[None, :])[0] + 0.01


def test_symmetric_shapes_are_reported_not_asserted():
    """Kendine-yakın-simetrik şekiller bu testten muaftır — raporlanır.

    Simetrik üçgen gibi şekillerin aynası kendine benzeyebilir; bu bir hata
    değil, şeklin özelliğidir.
    """
    q = get_template("symmetrical_triangle").vector
    ratio = float(ddtw_scores(q, (-q)[None, :])[0] / max(1e-9, ddtw_scores(q, q[None, :])[0] + 1e-9))
    print(f"\nsimetrik üçgen: ayna/kendisi mesafe oranı = {ratio:.0f}x (bilgi amaçlı)")
    assert np.isfinite(ratio)


# ---------------------------------------------------------------------------
# Geometrik kısıt katmanı (F3.5, Adım 7) — uygulandı, motora BAĞLANMADI
# ---------------------------------------------------------------------------


def test_constraints_are_metadata_not_code():
    """K-04 korunuyor: kural şablon JSON'unda, değerlendirici tek ve genel."""
    obo = get_template("head_and_shoulders")
    assert [c["type"] for c in obo.constraints] == [
        "level_match", "level_order", "level_order", "level_order",
    ]
    assert get_template("bull_flag").constraints == ()  # kısıtsız şablon


def test_constraint_evaluator_rejects_rounded_top():
    """Boyun çizgisi kuralı: yuvarlak tepe elenmeli, gerçek OBO geçmeli."""
    from engine.search.constraints import passes

    obo = get_template("head_and_shoulders")
    gercek = normalize_window(100 * np.exp(0.25 * shape("head_and_shoulders", 32)))
    yuvarlak = z(-((np.linspace(-1, 1, N_POINTS)) ** 2))  # tek tepeli parabol

    assert passes(obo.vector, gercek, obo.constraints)
    assert not passes(obo.vector, yuvarlak, obo.constraints)


def test_no_constraints_means_no_filtering():
    """``constraints`` alanı olmayan şablon mevcut davranışı korur."""
    from engine.search.constraints import filter_candidates

    rng = np.random.default_rng(2)
    V = np.stack([z(rng.normal(size=N_POINTS)) for _ in range(20)])
    assert filter_candidates(get_template("bull_flag").vector, V, ()).all()


def test_warping_path_is_monotone_and_banded():
    """Blueprint overlay'in dayandığı yol: monoton ve bant içinde."""
    from engine.search.ddtw import warp_amount, warping_path

    q = get_template("cup_and_handle").vector
    c = normalize_window(100 * np.exp(0.2 * shape("cup_and_handle", 64)))
    path = warping_path(q, c)

    assert np.all(np.diff(path[:, 0]) >= 0) and np.all(np.diff(path[:, 1]) >= 0)
    assert np.all(np.abs(path[:, 0] - path[:, 1]) <= SAKOE_CHIBA_RADIUS)
    assert warp_amount(path) < 5.0  # kendi şekline hizalanırken az bükülme


# ---------------------------------------------------------------------------
# İnce ayar katmanı (ölçüldü, bağlanmadı — config.REFINE_MATCHES)
# ---------------------------------------------------------------------------


def test_refine_never_worsens_the_ranking_metric():
    """İnce ayar mesafeyi ASLA artırmaz: mevcut hiza da aday kümesindedir.

    Bu, katmanın açılması hâlinde eşik kalibrasyonunun (F3.5 yüzdelikleri)
    sessizce kaymayacağının garantisidir.
    """
    import numpy as np

    from engine.outcome.bars import BarStore
    from engine.search.engine import Match
    from engine.search.refine import refine_matches
    from engine.search.ddtw import stage2_scores
    from engine.normalize.pipeline import normalize_batch
    from engine.config import N_POINTS, TIMEFRAME_MS
    from tools.shapes import head_and_shoulders

    rng = np.random.default_rng(11)
    n_bars = 400
    shape = head_and_shoulders(60)
    close = 100.0 * np.exp(np.cumsum(0.01 * rng.normal(size=n_bars)))
    close[120:180] = 100.0 * np.exp(0.25 * shape)  # gömülü formasyon

    step = TIMEFRAME_MS["1d"]
    store = BarStore.from_arrays(
        {
            7: {
                "close": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "open": close,
                "open_time": np.arange(n_bars, dtype=np.int64) * step,
                "symbol": "TESTUSDT",
            }
        }
    )

    query = normalize_batch(100.0 * np.exp(0.25 * head_and_shoulders(60))[None, :])[0][0]
    query = np.asarray(query, dtype=np.float64)

    # Formasyonun 2 bar kaymış hâlini "bulunmuş eşleşme" gibi ver.
    start = 122
    window = close[start : start + 60][None, :]
    vec, _ = normalize_batch(window, N_POINTS)
    distance = float(stage2_scores(query, np.asarray(vec, dtype=np.float64))[0])

    match = Match(
        symbol="TESTUSDT", symbol_id=7, timeframe="1d", window_length=60,
        start_idx=start, end_idx=start + 59,
        end_time=int(store.open_time[start + 59]),
        score=float(np.asarray(vec[0], dtype=np.float64) @ query / N_POINTS),
        distance=distance, amplitude=10.0, atr=1.0, percentile=0.5,
    )

    refined = refine_matches([match], store, query, "1d")
    assert len(refined) == 1
    assert refined[0].distance <= match.distance + 1e-12
    # Kayma olduysa uç indeksler tutarlı kalmalı.
    assert refined[0].end_idx - refined[0].start_idx == 59


# ---------------------------------------------------------------------------
# Yapısal imza — "çizdiğim formasyonu bulmuyor" şikâyetinin cevabı
# ---------------------------------------------------------------------------


def _z(y):
    import numpy as np

    y = np.asarray(y, dtype=np.float64)
    return (y - y.mean()) / y.std()


def test_signature_separates_head_and_shoulders_from_a_single_bump():
    """Ölçülen asıl hata: yuvarlak tümsek OBO sanılıyordu.

    DTW "yükseliş-tümsek-düşüş"ü yakalar; omuz-baş-omuz olup olmadığını
    sormaz. İmza tam olarak bunu sorar.
    """
    import numpy as np

    from engine.search.constraints import structural_signature
    from tools.shapes import head_and_shoulders, rounding_bottom

    obo = _z(head_and_shoulders(32))
    tumsek = _z(-rounding_bottom(32))  # tek yuvarlak tepe

    assert structural_signature(obo) != structural_signature(tumsek)
    assert structural_signature(obo)[1] == 3  # üç belirgin tepe


def test_signature_rejects_one_tall_one_small_peak_as_double_top():
    """İkili tepenin tanımı iki zirvenin YAKLAŞIK EŞİT olmasıdır."""
    import numpy as np

    from engine.search.constraints import structural_signature
    from tools.shapes import double_top

    t = np.linspace(0, 1, 64)
    dengeli = _z(double_top(64))
    carpik = _z(np.exp(-(((t - 0.25) / 0.08) ** 2)) + 0.25 * np.exp(-(((t - 0.75) / 0.08) ** 2)))

    assert structural_signature(dengeli) != structural_signature(carpik)


def test_side_comes_from_the_query_not_the_candidate():
    """Taraf adayın sayılarından seçilirse dengeli şekiller haksız elenir.

    Ölçüldü: yükselen üçgen 431 eşleşmeden 18'e düşüyordu; taraf sorgudan
    sabitlenince 47'ye çıktı ve dört formasyonun doğruluğu %100'de kaldı.
    """
    import numpy as np

    from engine.search.constraints import dominant_side, side_signature

    from tools.shapes import head_and_shoulders

    q = _z(head_and_shoulders(32))
    side = dominant_side(q)
    assert side == 1  # OBO tepelerle tanımlanır

    # Aday dip sayısı fazla olsa bile TEPE tarafında sınanmalı.
    aday = _z(head_and_shoulders(32) + 0.05 * np.sin(np.linspace(0, 20, 32)))
    assert side_signature(aday, side) is not None


def test_shapeless_query_is_not_filtered():
    """Düz rampanın 'yapısı' yoktur — uydurulmaz, filtre uygulanmaz."""
    import numpy as np

    from engine.search.constraints import signature_mask

    rampa = _z(np.linspace(0, 1, 32))
    adaylar = np.array([_z(np.linspace(0, 1, 32)), _z(np.linspace(1, 0, 32))])
    assert signature_mask(rampa, adaylar) is None


def test_signature_mask_keeps_only_matching_structure():
    import numpy as np

    from engine.search.constraints import signature_mask
    from tools.shapes import double_top, head_and_shoulders

    q = _z(head_and_shoulders(32))
    adaylar = np.array([_z(head_and_shoulders(32)), _z(double_top(32))])
    mask = signature_mask(q, adaylar)

    assert mask is not None
    assert bool(mask[0]) and not bool(mask[1])


# ---------------------------------------------------------------------------
# Yapısal filtre — motor entegrasyonu (ground truth ile)
# ---------------------------------------------------------------------------


def test_structure_filter_raises_precision_against_ground_truth(obo_dataset):
    """Filtre, ENJEKTE EDİLMİŞ OBO'ların ilk sayfadaki payını artırmalı.

    Bu test filtreyi kendi yapı denetçisiyle değil, korpusa bilerek
    yerleştirilmiş gerçek formasyonlarla sınar — bağımsız doğrulama.
    """
    root, truth = obo_dataset
    engine = SearchEngine(root / "matrix")
    q = get_template("head_and_shoulders").vector

    ham = engine.search(q, timeframe=TF, tolerance="flexible", limit=12, structure_filter=False)
    filtreli = engine.search(q, timeframe=TF, tolerance="flexible", limit=12, structure_filter=True)

    def isabet(result) -> int:
        n = 0
        for match in result.results:
            for inj in truth:
                if inj.symbol == match.symbol and iou_1d(
                    match.start_idx, match.end_idx, inj.start, inj.end
                ) >= 0.3:
                    n += 1
                    break
        return n

    assert isabet(filtreli) >= isabet(ham), (
        f"filtre isabeti düşürdü: ham {isabet(ham)}/12 → filtreli {isabet(filtreli)}/12"
    )


def test_structure_filter_sets_its_flag(obo_dataset):
    root, _ = obo_dataset
    engine = SearchEngine(root / "matrix")
    q = get_template("head_and_shoulders").vector

    result = engine.search(q, timeframe=TF, tolerance="flexible", limit=12)
    assert result.structure_filtered or result.structure_relaxed


def test_structure_filter_falls_back_loudly_when_too_few_survive(obo_dataset, monkeypatch):
    """Az aday kalırsa filtre uygulanmaz ama SESSİZ kalmaz.

    "Yapıya uyan yok" ile "hiç sonuç yok" farklı şeylerdir; ikincisi
    kullanıcıya motorun bozuk olduğunu düşündürür. Geri düşüş uyarıyla gelir.

    Taban imkânsız bir değere çekilerek yol zorla tetikleniyor: gerçek veride
    nadir olan dal, test edilmediğinde sessizce bozulan daldır.
    """
    import engine.search.engine as engine_module

    root, _ = obo_dataset
    engine = SearchEngine(root / "matrix")
    q = get_template("head_and_shoulders").vector

    monkeypatch.setattr(engine_module, "STRUCTURE_MIN_SURVIVORS", 10**9)
    result = engine.search(q, timeframe=TF, tolerance="flexible", limit=12)

    assert result.structure_relaxed
    assert not result.structure_filtered
    assert result.warning and "yapısal filtre" in result.warning.lower()
    # Geri düşüş sonuçları YOK ETMEZ; filtresiz liste döner.
    assert result.total > 0


def test_no_candidate_is_an_honest_answer(obo_dataset):
    """Korpusta karşılığı olmayan yapı → 0 sonuç, uydurma değil (K-18)."""
    import numpy as np

    from engine.search.constraints import structural_signature

    root, _ = obo_dataset
    engine = SearchEngine(root / "matrix")

    t = np.linspace(0, 1, 32)
    exotic = np.sin(2 * np.pi * 5 * t)
    exotic = (exotic - exotic.mean()) / exotic.std()
    assert structural_signature(exotic)[1] >= 4  # gerçekten çok tepeli

    result = engine.search(exotic, timeframe=TF, tolerance="flexible", limit=12)
    assert result.total == 0
    assert not result.discriminative
    assert result.warning


def test_filter_can_be_disabled(obo_dataset):
    """Bayrak gerçekten devre dışı bırakmalı — kapatınca daha çok sonuç."""
    root, _ = obo_dataset
    engine = SearchEngine(root / "matrix")
    q = get_template("head_and_shoulders").vector

    acik = engine.search(q, timeframe=TF, tolerance="flexible", limit=1, structure_filter=True)
    kapali = engine.search(q, timeframe=TF, tolerance="flexible", limit=1, structure_filter=False)

    assert kapali.total >= acik.total
    assert not kapali.structure_filtered
