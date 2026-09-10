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


def test_gt_benchmark_gurultu_sembollerine_aranan_formasyonu_koymaz():
    """Gürültü sembolleri aranan formasyonu İÇERMEMELİ.

    İçerselerdi "yanlış" saydığımız sonuçların bir kısmı aslında doğru
    olurdu ve ölçüm kendi kendini yanıltırdı. Bu nöbetçi ölçüm zemininin
    geçerliliğini korur.
    """
    from tools.gt_benchmark import FAMILIES

    for pattern in FAMILIES["all"]:
        others = tuple(p for p in FAMILIES["all"] if p != pattern)
        assert pattern not in others
        assert len(others) == len(FAMILIES["all"]) - 1


def test_gt_benchmark_skor_ground_truth_ile_esler():
    """Skorlayıcı örtüşen pencereyi doğru, örtüşmeyeni yanlış saymalı."""
    from types import SimpleNamespace

    from tools.gen_synthetic import Injection
    from tools.gt_benchmark import score

    truth = [Injection("AAAUSDT", "bull_flag", 100, 160, 61, 0.2, 0.03)]
    result = SimpleNamespace(
        total=2,
        results=[
            SimpleNamespace(symbol="AAAUSDT", start_idx=105, end_idx=165),  # örtüşür
            SimpleNamespace(symbol="AAAUSDT", start_idx=400, end_idx=460),  # örtüşmez
            SimpleNamespace(symbol="BBBUSDT", start_idx=100, end_idx=160),  # başka sembol
        ],
    )
    s = score(result, truth)
    assert s["correct"] == 1 and s["shown"] == 3
    assert s["recall"] == 1.0


def test_gercek_veri_enjeksiyonu_bar_ici_tutarliligi_bozmaz():
    """O/H/L bar başına aynı oranla ölçeklenmeli — high >= max(o,c) kalmalı.

    Kapanışı değiştirip diğerlerini bırakmak, motorun ATR ve genlik
    hesaplarına sessizce bozuk bar verirdi; enjeksiyon zemini bozmamalı.
    """
    import numpy as np
    import pandas as pd

    from tools.gen_synthetic import inject
    from tools.gt_benchmark import _inject_into_real

    n = 400
    rng = np.random.default_rng(5)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.02, n)))
    df = pd.DataFrame({
        "open_time": np.arange(n, dtype=np.int64) * 14_400_000,
        "open": close * 0.99,
        "high": close * 1.02,
        "low": close * 0.97,
        "close": close,
        "volume": np.full(n, 1000.0),
        "quote_volume": np.full(n, 100000.0),
        "trades": np.full(n, 50, dtype=np.int32),
    })

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        src, dst = Path(tmp) / "src.parquet", Path(tmp) / "TGT000USDT.parquet"
        df.to_parquet(src)
        inj = _inject_into_real(src, dst, "double_top", rng, n,
                                (40, 90), (0.18, 0.40), (0.01, 0.05))
        out = pd.read_parquet(dst)

    assert inj is not None and inj.pattern == "double_top"
    o, h, l, c = (out[k].to_numpy() for k in ("open", "high", "low", "close"))
    assert np.all(h >= np.maximum(o, c) - 1e-9), "high bar içi tavanın altında"
    assert np.all(l <= np.minimum(o, c) + 1e-9), "low bar içi tabanın üstünde"
    assert np.all(c > 0)
    # Hacim dokunulmamış olmalı: enjeksiyon fiyat yapısıdır, likidite değil.
    assert np.allclose(out["volume"].to_numpy(), 1000.0)


def test_gercek_veri_dagiticilari_dokunulmamis_kalir():
    """``pattern=None`` verilen dosya birebir kopyalanmalı."""
    import numpy as np
    import pandas as pd
    import tempfile
    from pathlib import Path

    from tools.gt_benchmark import _inject_into_real

    n = 300
    rng = np.random.default_rng(9)
    close = 50.0 * np.exp(np.cumsum(rng.normal(0, 0.015, n)))
    df = pd.DataFrame({
        "open_time": np.arange(n, dtype=np.int64) * 14_400_000,
        "open": close, "high": close * 1.01, "low": close * 0.99, "close": close,
        "volume": np.full(n, 7.0), "quote_volume": np.full(n, 70.0),
        "trades": np.full(n, 3, dtype=np.int32),
    })
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = Path(tmp) / "s.parquet", Path(tmp) / "NOI000USDT.parquet"
        df.to_parquet(src)
        assert _inject_into_real(src, dst, None, rng, n, (0, 0), (0, 0), (0, 0)) is None
        out = pd.read_parquet(dst)
    assert np.allclose(out["close"].to_numpy(), close)


# ---------------------------------------------------------------------------
# F4.6 hedef listesi — tanımı sabit, değeri güncel ölçümden
# ---------------------------------------------------------------------------


def _f45_row(sablon, yon, lo, hi, edge=0.1):
    return {"sablon": sablon, "yon": yon, "konf": "2:1", "olculebilir": True,
            "blok_alt": lo, "blok_ust": hi, "edge": edge}


def test_f46_hedefleri_guncel_f45_olcumunden_gelir(tmp_path, monkeypatch):
    """Liste elle yazıldığında tanımıyla değeri ayrışmıştı.

    Motor değişince F4.5'in anlamlı kümesi değişti, liste değişmedi; iki
    zaman diliminde replike eden flama short 2:1 vekil testine hiç girmedi.
    """
    import json

    from tools import f46_proxy_test as f46

    (tmp_path / "f3").mkdir()
    rows = [
        _f45_row("pennant", "short", 0.02, 0.26),        # anlamlı, short → hedef
        _f45_row("double_top", "short", -0.80, -0.10),   # anlamlı (negatif) → hedef
        _f45_row("bull_flag", "short", -0.10, 0.20),     # sıfırı içeriyor → değil
        _f45_row("double_bottom", "long", -0.77, -0.25), # anlamlı ama long → değil
    ]
    (tmp_path / "f3" / "f45_raw.json").write_text(json.dumps(rows), encoding="utf-8")
    monkeypatch.setattr(f46, "DATA_DIR", tmp_path)

    assert f46.target_templates("1d") == ["double_top", "pennant"]


def test_f46_hedef_dosyasi_yoksa_yedek_listeye_duser(tmp_path, monkeypatch):
    from tools import f46_proxy_test as f46

    monkeypatch.setattr(f46, "DATA_DIR", tmp_path)
    assert f46.target_templates("1d") == f46.FALLBACK_TARGETS


def test_f46_bonferroni_gecisi_ayni_sablonlarla_kosar(monkeypatch):
    """İkinci geçiş şablon listesini ilk geçişten almalı.

    Eskiden liste iletilmiyordu: liste sabitken zararsızdı, veriden
    türetilince (ör. 1d hedefleri 4h'de sınanırken) ikinci geçiş başka bir
    listeyle koşar ve düzeltilmiş aralıklar sessizce eksik kalırdı.
    """
    from tools import f46_proxy_test as f46

    seen = {}

    def fake_run(timeframe="1d", templates=None, confidence=None, **_):
        seen["templates"] = templates
        seen["timeframe"] = timeframe
        return []

    monkeypatch.setattr(f46, "run_proxy_test", fake_run)
    first = [
        f46.ProxyResult("pennant", "short", "2:1", 0.25, 10, 100, 0.1, (0.0, 0.2), False, "return_matched"),
        f46.ProxyResult("double_top", "short", "2:1", 0.25, 10, 100, 0.1, (0.0, 0.2), False, "return_matched"),
    ]
    f46.apply_bonferroni(first, timeframe="4h")
    assert seen == {"templates": ["pennant", "double_top"], "timeframe": "4h"}
