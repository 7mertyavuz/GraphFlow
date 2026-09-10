"""Outcome metrikleri — hiçbir sayı güven aralığı olmadan yayınlanmaz.

**Neden beklenti başrolde:** SL 5×ATR yapılırsa kazanma oranı %85'e çıkar ama
beklenti negatiftir. Kazanma oranı tek başına manipüle edilebilir bir
metriktir (K-16.5).

**Neden GA zorunlu:** ``n = 112``, ``p = 0,41`` → %95 GA ≈ ±9 puan →
``[%32, %50]``. Teorik null %33 bu aralığın **içinde**; yani "+6 puan edge"
istatistiksel olarak anlamsız olurdu. Karar kuralı: edge'in %95 GA'sı sıfırı
içeriyorsa çıktı *"anlamlı fark ölçülemedi"*dir.

| Metrik | Yöntem |
|---|---|
| Beklenti (R) | Bootstrap (R sürekli değişken; binom GA'sı uygun değil) |
| Başarı oranı | Wilson skor aralığı |
| Edge | İki bağımsız örneklemin farkı için bootstrap |
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from engine.config import (
    BOOTSTRAP_SAMPLES,
    CONFIDENCE_LEVEL,
    MIN_EVENTS_FOR_CLAIM,
    MIN_REGIME_N,
    REGIMES,
)
from engine.outcome.triple_barrier import (
    OUTCOME_NAMES,
    OUTCOME_SL,
    OUTCOME_TP,
    theoretical_null,
)

DISCLAIMER = "Bu veriler geçmiş dağılımlardır, kesin bir işlem sinyali değildir."


def _z(confidence: float) -> float:
    """Normal dağılımın iki yanlı kritik değeri (scipy'siz)."""
    return float(math.sqrt(2.0) * _erfinv(confidence))


def _erfinv(x: float) -> float:
    # Winitzki yaklaşımı — %95 civarında 1e-4'ten iyi.
    a = 0.147
    ln = math.log(1.0 - x * x)
    t = 2.0 / (math.pi * a) + ln / 2.0
    return math.copysign(math.sqrt(max(0.0, math.sqrt(t * t - ln / a) - t)), x)


def wilson_interval(successes: int, n: int, confidence: float = CONFIDENCE_LEVEL) -> tuple[float, float]:
    """Başarı oranı için Wilson skor aralığı (küçük n'de normal yaklaşımdan iyi)."""
    if n == 0:
        return (float("nan"), float("nan"))
    z = _z(confidence)
    p = successes / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def bootstrap_mean_ci(
    values: np.ndarray,
    samples: int = BOOTSTRAP_SAMPLES,
    confidence: float = CONFIDENCE_LEVEL,
    rng: np.random.Generator | None = None,
) -> tuple[float, float]:
    """Ortalama için bootstrap GA. R sürekli değişkendir; binom GA'sı yanlıştır."""
    values = np.asarray(values, dtype=np.float64)
    if values.size == 0:
        return (float("nan"), float("nan"))
    rng = rng if rng is not None else np.random.default_rng(20260731)
    idx = rng.integers(0, values.size, size=(samples, values.size))
    means = values[idx].mean(axis=1)
    alpha = (1.0 - confidence) / 2.0
    return (float(np.quantile(means, alpha)), float(np.quantile(means, 1.0 - alpha)))


def bootstrap_diff_ci(
    a: np.ndarray,
    b: np.ndarray,
    samples: int = BOOTSTRAP_SAMPLES,
    confidence: float = CONFIDENCE_LEVEL,
    rng: np.random.Generator | None = None,
) -> tuple[float, float]:
    """İki **bağımsız** örneklemin ortalama farkı için bootstrap GA."""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    if a.size == 0 or b.size == 0:
        return (float("nan"), float("nan"))
    rng = rng if rng is not None else np.random.default_rng(20260731)
    ia = rng.integers(0, a.size, size=(samples, a.size))
    ib = rng.integers(0, b.size, size=(samples, b.size))
    diffs = a[ia].mean(axis=1) - b[ib].mean(axis=1)
    alpha = (1.0 - confidence) / 2.0
    return (float(np.quantile(diffs, alpha)), float(np.quantile(diffs, 1.0 - alpha)))


def month_of(end_time: np.ndarray) -> np.ndarray:
    """Olayları takvim ayına indirger — blok bootstrap'ın blok birimi."""
    from engine.matrix.liquidity import month_key

    return month_key(np.asarray(end_time))


def block_bootstrap_diff_ci(
    a_values: np.ndarray,
    a_months: np.ndarray,
    b_values: np.ndarray,
    b_months: np.ndarray,
    samples: int = BOOTSTRAP_SAMPLES,
    confidence: float = CONFIDENCE_LEVEL,
    rng: np.random.Generator | None = None,
) -> tuple[tuple[float, float], float]:
    """**Ay-bloklu** bootstrap: örnekleme birimi olay değil, takvim ayıdır.

    Gölge havuzu "aynı ay, farklı sembol" kuralıyla çekiliyor — ama kripto
    sembolleri birbirine yüksek korelasyonludur. Aynı aydan 20 farklı sembol
    **20 bağımsız gözlem vermez**. iid bootstrap onları bağımsız sayar →
    gölgenin varyansı olduğundan küçük ölçülür → edge'in GA'sı sahte biçimde
    dar çıkar → **anlamsız bir farkı anlamlı ilan etme riski**.

    Blok bootstrap'ta aylar yerine koyarak çekilir; seçilen ayın **tüm**
    eşleşmeleri ve **tüm** gölgeleri birlikte alınır. Böylece ay içi korelasyon
    bloğun içinde kalır ve eşleştirme (K-12) korunur.

    Döner: ``((alt, üst), tasarım_etkisi)`` — tasarım etkisi ``SE_blok/SE_iid``,
    korelasyonun anlamlılığı ne kadar şişirdiğini gösteren tek sayı.
    """
    a_values = np.asarray(a_values, dtype=np.float64)
    b_values = np.asarray(b_values, dtype=np.float64)
    if a_values.size == 0 or b_values.size == 0:
        return (float("nan"), float("nan")), float("nan")

    rng = rng if rng is not None else np.random.default_rng(20260731)
    months = np.array(sorted(set(np.asarray(a_months).tolist()) | set(np.asarray(b_months).tolist())))
    if months.size < 2:
        return bootstrap_diff_ci(a_values, b_values, samples, confidence, rng), float("nan")

    # Ay → o aya ait değerlerin toplamı ve sayısı (blok istatistikleri)
    def block_stats(values, month_labels):
        idx = {m: i for i, m in enumerate(months)}
        sums = np.zeros(months.size)
        counts = np.zeros(months.size)
        for v, m in zip(values, np.asarray(month_labels)):
            j = idx[m]
            sums[j] += v
            counts[j] += 1
        return sums, counts

    a_sum, a_cnt = block_stats(a_values, a_months)
    b_sum, b_cnt = block_stats(b_values, b_months)

    draws = rng.integers(0, months.size, size=(samples, months.size))
    a_s, a_c = a_sum[draws].sum(axis=1), a_cnt[draws].sum(axis=1)
    b_s, b_c = b_sum[draws].sum(axis=1), b_cnt[draws].sum(axis=1)

    ok = (a_c > 0) & (b_c > 0)
    diffs = np.where(ok, a_s / np.maximum(a_c, 1) - b_s / np.maximum(b_c, 1), np.nan)
    diffs = diffs[np.isfinite(diffs)]
    if diffs.size < 100:
        return bootstrap_diff_ci(a_values, b_values, samples, confidence, rng), float("nan")

    alpha = (1.0 - confidence) / 2.0
    ci = (float(np.quantile(diffs, alpha)), float(np.quantile(diffs, 1.0 - alpha)))

    # Tasarım etkisi: blok SE / iid SE
    ia = rng.integers(0, a_values.size, size=(min(samples, 4000), a_values.size))
    ib = rng.integers(0, b_values.size, size=(min(samples, 4000), b_values.size))
    iid = a_values[ia].mean(axis=1) - b_values[ib].mean(axis=1)
    design = float(diffs.std() / iid.std()) if iid.std() > 0 else float("nan")
    return ci, design


def bonferroni_level(n_tests: int, alpha: float = 1.0 - CONFIDENCE_LEVEL) -> float:
    """Çoklu karşılaştırma düzeltmesi: 14 şablon × 2 konfigürasyon = 28 test.

    %95 ile 28 test yaparsan şans eseri ~1,4 "anlamlı" sonuç beklersin.
    "En iyi 3 formasyon" sunumu tam olarak bu tuzaktır; bu yüzden tüm
    şablonlar tek tabloda raporlanır ve edge iddiaları düzeltilmiş güven
    düzeyiyle de sınanır.
    """
    return 1.0 - alpha / max(1, int(n_tests))


@dataclass
class OutcomeStats:
    """Tek bir bariyer konfigürasyonunun raporu."""

    config: str
    k_tp: float
    k_sl: float
    n: int
    expectancy_r: float
    expectancy_ci: tuple[float, float]
    expectancy_net_r: float
    win_rate: float
    win_rate_ci: tuple[float, float]
    theoretical_null: float
    outcomes: dict[str, int]
    truncated: int
    #: Medyan R ve olayların kaçının artıda kapandığı.
    #:
    #: Beklenti bir **ortalamadır** ve üçlü bariyerde ortalama, dağılımın
    #: şeklini tamamen gizler: OBO 2:1'de beklenti +0,015R iken medyan
    #: **−1,000R**'dir — olayların yarısından fazlası tam stop yer. Ortalamaya
    #: bakan biri bu deneyimi göremez.
    #:
    #: Yüzdelik BANT (p10–p90) bilerek raporlanmıyor: ölçüldü, 12/12 hücrede
    #: tam olarak bariyerlere oturuyor (−k_sl, +k_tp). Üçlü bariyer sonucu üç
    #: noktada toplanır; bant veriden değil bariyer ayarından gelir, yani
    #: sıfır bilgi taşır. Bilgi taşıyan iki sayı medyan ve artıda kapanma
    #: oranıdır — ikisi de hücreden hücreye değişiyor.
    #:
    #: ``share_positive`` kazanma oranından farklıdır: kazanma oranı yalnız
    #: TP'ye çarpanları sayar, bu ise zaman bariyerinden artıda çıkanları da
    #: sayar — "sonunda yeşil miydim" sorusunun cevabı.
    r_median: float = float("nan")
    share_positive: float = float("nan")

    shadow_expectancy_r: float | None = None
    shadow_win_rate: float | None = None
    shadow_r_median: float | None = None
    shadow_share_positive: float | None = None
    shadow_n: int = 0
    edge_r: float | None = None
    edge_ci: tuple[float, float] | None = None
    edge_ci_iid: tuple[float, float] | None = None
    design_effect: float | None = None
    n_months: int = 0
    direction: str = "long"
    by_regime: list[dict] = field(default_factory=list)

    @property
    def insufficient(self) -> bool:
        """Örneklem, başlık sayılarının okunabileceği tabanın altında mı?

        Güven aralığı zaten geniş çıkar ve hüküm "anlamlı fark ölçülemedi"
        der — ama ekranın ortasındaki büyük sayı yine de okunur. N = 4 ile
        hesaplanmış "+0,80R beklenti" teknik olarak doğru, iletişim olarak
        yanlıştır.
        """
        return self.n < MIN_EVENTS_FOR_CLAIM

    @property
    def edge_is_significant(self) -> bool:
        """GA sıfırı içeriyorsa edge iddiası ekrana YAZILMAZ (K-12)."""
        if self.edge_ci is None or not all(np.isfinite(self.edge_ci)):
            return False
        return self.edge_ci[0] > 0.0 or self.edge_ci[1] < 0.0

    def verdict_text(self, lang: str = "tr") -> str:
        """Hüküm, istenen dilde (``engine.i18n``)."""
        from engine.i18n import t

        if self.insufficient:
            return t("verdict.insufficient", lang, n=self.n)  # type: ignore[arg-type]
        if self.shadow_n == 0:
            return t("verdict.no_shadow", lang)  # type: ignore[arg-type]
        if not self.edge_is_significant:
            return t("verdict.not_significant", lang)  # type: ignore[arg-type]
        side = t("verdict.favorable" if (self.edge_r or 0) > 0 else "verdict.unfavorable", lang)  # type: ignore[arg-type]
        return t("verdict.significant", lang, side=side, edge=f"{self.edge_r:+.3f}")  # type: ignore[arg-type]

    @property
    def verdict(self) -> str:
        return self.verdict_text("tr")

    def as_dict(self) -> dict:
        return {
            "config": self.config,
            "n_independent": self.n,
            "insufficient": self.insufficient,
            "expectancy_r": round(self.expectancy_r, 4),
            "expectancy_ci": [round(x, 4) for x in self.expectancy_ci],
            "expectancy_net_r": round(self.expectancy_net_r, 4),
            "r_median": round(self.r_median, 4),
            "share_positive": round(self.share_positive, 4),
            "shadow_r_median": None if self.shadow_r_median is None else round(self.shadow_r_median, 4),
            "shadow_share_positive": (
                None if self.shadow_share_positive is None else round(self.shadow_share_positive, 4)
            ),
            "win_rate": round(self.win_rate, 4),
            "win_rate_ci": [round(x, 4) for x in self.win_rate_ci],
            "theoretical_null": round(self.theoretical_null, 4),
            "shadow_expectancy_r": None if self.shadow_expectancy_r is None else round(self.shadow_expectancy_r, 4),
            "shadow_win_rate": None if self.shadow_win_rate is None else round(self.shadow_win_rate, 4),
            "shadow_n": self.shadow_n,
            "edge_r": None if self.edge_r is None else round(self.edge_r, 4),
            "edge_ci": None if self.edge_ci is None else [round(x, 4) for x in self.edge_ci],
            "edge_ci_iid": None if self.edge_ci_iid is None else [round(x, 4) for x in self.edge_ci_iid],
            "design_effect": None if self.design_effect is None else round(self.design_effect, 3),
            "n_months": self.n_months,
            "direction": self.direction,
            "edge_is_significant": self.edge_is_significant,
            "verdict": self.verdict,
            "outcomes": self.outcomes,
            "truncated": self.truncated,
            "by_regime": self.by_regime,
            "disclaimer": DISCLAIMER,
        }


def distribution(r: np.ndarray) -> tuple[float, float]:
    """``(medyan, artıda kapanma oranı)`` — ortalamanın gizlediği şey.

    Bunlar bir **iddia** değil, gözlenen olayların betimlemesidir; belirsizlik
    iddiası taşıyan sayılar (beklenti, edge) güven aralıklarıyla döner.

    Yüzdelik bant (p10–p90) bilerek dönülmüyor — ölçüldü, 12/12 hücrede tam
    bariyerlere oturuyor. Üçlü bariyer sonucu üç noktada toplandığı için bant
    veriden değil konfigürasyondan gelir.
    """
    if r.size == 0:
        return float("nan"), float("nan")
    return float(np.median(r)), float((r > 0.0).mean())


def _counts(results: np.ndarray) -> dict[str, int]:
    return {
        name: int((results["outcome"] == code).sum()) for code, name in OUTCOME_NAMES.items()
    }


def regime_of(end_time: np.ndarray) -> np.ndarray:
    """Yıl bazında kırmak hücre başına ~14 olay bırakır — 3 kaba rejim (K-06)."""
    years = pd.to_datetime(np.asarray(end_time), unit="ms", utc=True).year.to_numpy()
    out = np.full(years.shape, "?", dtype=object)
    for name, start, end in REGIMES:
        out[(years >= start) & (years <= end)] = name
    return out


def _regime_table(results: np.ndarray) -> list[dict]:
    if results.size == 0:
        return []
    regimes = regime_of(results["end_time"])
    rows = []
    for name, _, _ in REGIMES:
        sel = regimes == name
        n = int(sel.sum())
        if n == 0:
            continue
        r = results["r_gross"][sel]
        wins = int((results["outcome"][sel] == OUTCOME_TP).sum())
        rows.append({
            "period": name,
            "n": n,
            "expectancy_r": round(float(r.mean()), 4),
            "win_rate": round(wins / n, 4),
            "insufficient": n < MIN_REGIME_N,
        })
    return rows


def summarize(
    results: np.ndarray,
    k_tp: float,
    k_sl: float,
    config: str = "",
    shadow: np.ndarray | None = None,
    rng: np.random.Generator | None = None,
    direction: str = "long",
    confidence: float = CONFIDENCE_LEVEL,
) -> OutcomeStats:
    """Bir konfigürasyonun tüm metriklerini GA'larıyla birlikte hesaplar.

    Edge GA'sı **ay-bloklu** bootstrap'tır (F4.5): gölge havuzu aynı aydan
    çekildiği ve kripto sembolleri yüksek korelasyonlu olduğu için iid
    bootstrap efektif örneklem büyüklüğünü olduğundan büyük sayar.
    Karşılaştırma amacıyla iid GA da saklanır.
    """
    n = int(results.size)
    r = results["r_gross"].astype(np.float64) if n else np.empty(0)
    r_net = results["r_net"].astype(np.float64) if n else np.empty(0)
    decided = results["outcome"] != OUTCOME_SL if n else np.empty(0, dtype=bool)
    wins = int((results["outcome"] == OUTCOME_TP).sum()) if n else 0

    stats = OutcomeStats(
        config=config or f"{k_tp:g}:{k_sl:g}",
        k_tp=k_tp,
        k_sl=k_sl,
        n=n,
        expectancy_r=float(r.mean()) if n else float("nan"),
        expectancy_ci=bootstrap_mean_ci(r, rng=rng) if n else (float("nan"), float("nan")),
        expectancy_net_r=float(r_net.mean()) if n else float("nan"),
        win_rate=wins / n if n else float("nan"),
        win_rate_ci=wilson_interval(wins, n) if n else (float("nan"), float("nan")),
        theoretical_null=theoretical_null(k_tp, k_sl),
        outcomes=_counts(results) if n else {},
        truncated=int(results["truncated"].sum()) if n else 0,
        by_regime=_regime_table(results),
    )

    stats.direction = direction
    stats.n_months = int(np.unique(month_of(results["end_time"])).size) if n else 0
    stats.r_median, stats.share_positive = distribution(r)

    if shadow is not None and shadow.size and n:
        s = shadow["r_gross"].astype(np.float64)
        s_wins = int((shadow["outcome"] == OUTCOME_TP).sum())
        stats.shadow_expectancy_r = float(s.mean())
        stats.shadow_win_rate = s_wins / shadow.size
        stats.shadow_r_median, stats.shadow_share_positive = distribution(s)
        stats.shadow_n = int(shadow.size)
        stats.edge_r = float(r.mean() - s.mean())
        stats.edge_ci_iid = bootstrap_diff_ci(r, s, confidence=confidence, rng=rng)
        stats.edge_ci, stats.design_effect = block_bootstrap_diff_ci(
            r, month_of(results["end_time"]), s, month_of(shadow["end_time"]),
            confidence=confidence, rng=rng,
        )

    return stats
