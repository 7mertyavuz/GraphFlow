"""K-11 A/B — Aşama 2 metriği: DDTW mi, ham DTW mi, hybrid mi?

F2 ölçümünün iki metodolojik kusuru burada kapatılır:

**(a) Dairesellik.** Pozitifler artık sorgu şablonunun gürültülü kopyası
değil, ``tools/shape_variants.py`` ile üretilmiş **farklı örneklerdir**:
asimetrik omuzlar, eğimli boyun çizgisi, farklı kulp derinliği, kaymış
tepe/dip zamanlaması. Yapısal doğrulamadan geçerler (etiket güvenilir).

**(b) Uzunluk kırılımı.** AUC pencere uzunluğuna göre **ayrı ayrı** hesaplanır.
100 bar → 32 nokta bir alçak geçiren işlemdir (yumuşatır); 24 bar → 32 nokta
yukarı örneklemedir (yumuşatmaz). Türev bu farkı büyütür, tek ortalama gizler.

Ölçüm **yalnızca Aşama 2'yi** izole eder: sorgu ile aday vektörleri doğrudan
karşılaştırılır, Aşama 1 (kosinüs) devrede değildir. Kaskadın toplam geri
çağırma tavanı ayrıca ölçülür (``stage1_recall``).

    python -m tools.ab_stage2 --out data/f3/ab_stage2.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from engine.config import N_POINTS, STAGE1_TOPK, WINDOW_LENGTHS
from engine.normalize.pipeline import normalize_window
from engine.search.ddtw import stage2_scores
from engine.templates import get as get_template
from tools.shape_variants import variant

#: A/B'de kullanılan formasyonlar — kütüphanenin dört köşesi (dönüş/devam,
#: boğa/ayı, tek/çok tepeli).
AB_PATTERNS: tuple[str, ...] = (
    "head_and_shoulders",
    "inverse_head_and_shoulders",
    "double_top",
    "double_bottom",
    "cup_and_handle",
    "rounding_bottom",
    "bull_flag",
    "rising_wedge",
    "falling_wedge",
)

METRICS: tuple[str, ...] = ("ddtw", "dtw", "hybrid")

#: Bar başına log-getiri standart sapması. %2 gerçek 4H/1D kripto ölçeğidir;
#: %1 sakin, %4 çalkantılı rejimi temsil eder.
NOISE_LEVELS: tuple[float, ...] = (0.01, 0.02, 0.04)


def auc(positive: np.ndarray, negative: np.ndarray) -> float:
    """Mesafe metriği için AUC (küçük mesafe = pozitif). Bağlar 0,5 sayılır."""
    pos = np.asarray(positive)[:, None]
    neg = np.asarray(negative)[None, :]
    return float((pos < neg).mean() + 0.5 * (pos == neg).mean())


def make_positive(name: str, length: int, noise: float, rng: np.random.Generator) -> np.ndarray:
    """Formasyonun farklı bir örneği + rastgele ölçek + GBM gürültüsü."""
    shape_curve = variant(name, length, rng, strength=1.0)
    amplitude = rng.uniform(0.15, 0.40)  # log fiyat aralığı
    log_price = shape_curve * amplitude + np.cumsum(rng.normal(0.0, noise, length))
    return normalize_window(100.0 * np.exp(log_price))


def make_negative(length: int, noise: float, rng: np.random.Generator) -> np.ndarray:
    """Saf GBM penceresi — formasyon yok."""
    return normalize_window(100.0 * np.exp(np.cumsum(rng.normal(0.0, noise, length))))


def run(
    samples: int = 300,
    lengths=WINDOW_LENGTHS,
    noises=NOISE_LEVELS,
    metrics=METRICS,
    patterns=AB_PATTERNS,
    seed: int = 4242,
) -> dict:
    """3 metrik × 4 pencere uzunluğu × 3 gürültü seviyesi AUC tablosu."""
    rng = np.random.default_rng(seed)
    rows: list[dict] = []

    for length in lengths:
        for noise in noises:
            negatives = np.stack([make_negative(length, noise, rng) for _ in range(samples)])
            for name in patterns:
                query = get_template(name).vector
                positives = np.stack(
                    [make_positive(name, length, noise, rng) for _ in range(samples)]
                )
                for metric in metrics:
                    rows.append(
                        {
                            "pattern": name,
                            "length": int(length),
                            "noise": float(noise),
                            "metric": metric,
                            "auc": auc(
                                stage2_scores(query, positives, metric=metric),
                                stage2_scores(query, negatives, metric=metric),
                            ),
                        }
                    )

    return {"rows": rows, "samples": samples, "seed": seed}


def stage1_recall(
    samples: int = 300,
    lengths=WINDOW_LENGTHS,
    noise: float = 0.02,
    patterns=AB_PATTERNS,
    pool: int = 20_000,
    top_k: int = STAGE1_TOPK,
    seed: int = 99,
) -> dict:
    """Kaskadın tavanı: pozitifler Aşama 1'in top-K'sine girebiliyor mu?

    Aşama 2 metriği ne olursa olsun, Aşama 1'in eleyip attığı pencere bir daha
    geri gelmez. Bu yüzden metrik tartışmasından bağımsız olarak ölçülür.
    """
    rng = np.random.default_rng(seed)
    out: dict[str, dict] = {}

    for length in lengths:
        distractors = np.stack([make_negative(length, noise, rng) for _ in range(pool)])
        for name in patterns:
            query = get_template(name).vector.astype(np.float64)
            positives = np.stack([make_positive(name, length, noise, rng) for _ in range(samples)])

            neg_scores = distractors @ query / N_POINTS
            pos_scores = positives @ query / N_POINTS

            # Havuzda top_k oranını koru: pozitif, negatiflerin üst dilimine
            # girebiliyor mu?
            keep_ratio = min(1.0, top_k / max(1, pool))
            cutoff = np.quantile(neg_scores, 1.0 - keep_ratio)
            out[f"{name}@{length}"] = {
                "recall": float((pos_scores >= cutoff).mean()),
                "cutoff": float(cutoff),
                "median_pos_cosine": float(np.median(pos_scores)),
            }

    return out


def summarize(result: dict) -> str:
    rows = result["rows"]
    lengths = sorted({r["length"] for r in rows})
    noises = sorted({r["noise"] for r in rows})
    metrics = sorted({r["metric"] for r in rows}, key=lambda m: METRICS.index(m))

    lines = ["| gürültü | uzunluk | " + " | ".join(metrics) + " | kazanan |", "|---|---|" + "---|" * (len(metrics) + 1)]
    for noise in noises:
        for length in lengths:
            cells = []
            for metric in metrics:
                vals = [r["auc"] for r in rows if r["metric"] == metric and r["length"] == length and r["noise"] == noise]
                cells.append(float(np.mean(vals)))
            winner = metrics[int(np.argmax(cells))]
            lines.append(
                f"| %{noise*100:.0f} | {length} | " + " | ".join(f"{c:.3f}" for c in cells) + f" | **{winner}** |"
            )

    overall = {m: float(np.mean([r["auc"] for r in rows if r["metric"] == m])) for m in metrics}
    lines.append("")
    lines.append("Genel ortalama: " + ", ".join(f"{m}={v:.4f}" for m, v in overall.items()))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI
    p = argparse.ArgumentParser(prog="python -m tools.ab_stage2")
    p.add_argument("--samples", type=int, default=300)
    p.add_argument("--out", default="data/f3/ab_stage2.json")
    p.add_argument("--skip-recall", action="store_true")
    args = p.parse_args(argv)

    result = run(samples=args.samples)
    if not args.skip_recall:
        result["stage1_recall"] = stage1_recall(samples=args.samples)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")

    print(summarize(result))
    print(f"\n-> {out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
