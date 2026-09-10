"""Yeni bir Aşama 2 metriği için eşikleri **aynı seçicilik** ilkesiyle türetir.

**Neden F3 prosedürü değil.** F3 eşikleri (``TOLERANCE_THRESHOLDS_BY_METRIC``)
bugünkü filtrelerden (yapısal imza, kararlılık kapıları, zarf filtresi)
önceki motorla, sonuç listelerinin skor dağılımından okundu. Aynı prosedürü
bugün yeni metrikle koşmak, iki metriği iki farklı motorda karşılaştırmak
olurdu: fark metrikten mi, motordan mı geliyor ayrılamaz.

**Aynı seçicilik.** Referans metriğin bir eşiği, bir sorgunun null
dağılımında belli bir yüzdeliğe denk gelir ("rastgele pencerelerin %0,4'ü bu
kadar iyi"). Yeni metriğin eşiği, AYNI sorgunun AYNI pencerelerdeki kendi
dağılımında aynı yüzdeliğe konur. Motorun yüzdelik sistemi (F3.5) zaten bu
ilkeye dayanır; burada yalnız mutlak akıl sağlığı tavanına uygulanıyor.
Sorgu × uzunluk hücreleri üzerinden medyan alınır.

Filtre katmanlarından bağımsızdır: yalnız Aşama 2 mesafeleri karşılaştırılır.

    python -m tools.calibrate_metric --metric hybrid_central
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

import numpy as np

from engine.config import (
    DATA_DIR,
    SAKOE_CHIBA_RADIUS,
    TOLERANCE_THRESHOLDS_BY_METRIC,
    WINDOW_LENGTHS,
)
from engine.search.ddtw import stage2_scores
from engine.search.engine import SearchEngine
from engine.templates import load_all

log = logging.getLogger("tools.calibrate_metric")


def calibrate(
    metric: str,
    reference: str = "hybrid",
    timeframe: str = "1d",
    sample: int = 40_000,
    seed: int = 20260910,
) -> dict:
    """Referansın her kademesi için yeni metrikte aynı seçicilikteki eşik."""
    ref_thr = TOLERANCE_THRESHOLDS_BY_METRIC[reference]
    engine = SearchEngine()
    rng = np.random.default_rng(seed)

    per_tier: dict[str, list[float]] = {t: [] for t in ref_thr}
    selectivity: dict[str, list[float]] = {t: [] for t in ref_thr}
    rank_corr: list[float] = []

    for length in WINDOW_LENGTHS:
        handle = engine.handle(timeframe, length)
        rows = np.sort(rng.choice(len(handle), size=min(sample, len(handle)), replace=False))
        V = np.asarray(handle.vectors[rows], dtype=np.float64)

        for template_id, template in sorted(load_all().items()):
            q = np.asarray(template.vector, dtype=np.float64)
            d_ref = np.sort(stage2_scores(q, V, SAKOE_CHIBA_RADIUS, reference))
            d_new_raw = stage2_scores(q, V, SAKOE_CHIBA_RADIUS, metric)
            d_new = np.sort(d_new_raw)

            for tier, t in ref_thr.items():
                p = np.searchsorted(d_ref, t, side="right") / d_ref.size
                selectivity[tier].append(p)
                # p = 0 ise referans eşiği örneklemin altında: bilgi yok, atla.
                if p > 0:
                    per_tier[tier].append(float(np.quantile(d_new, p)))

            # Sıralama ne kadar aynı: seçicilik eşlemesinin anlamlı olması için
            # iki metriğin aynı pencereleri benzer sırada görmesi gerekir.
            ref_unsorted = stage2_scores(q, V[:4000], SAKOE_CHIBA_RADIUS, reference)
            r1 = np.argsort(np.argsort(ref_unsorted))
            r2 = np.argsort(np.argsort(d_new_raw[:4000]))
            rank_corr.append(float(np.corrcoef(r1, r2)[0, 1]))
        log.info("uzunluk %d bitti (%d pencere)", length, V.shape[0])

    thresholds = {t: round(float(np.median(v)), 4) for t, v in per_tier.items()}
    return {
        "metric": metric,
        "reference": reference,
        "timeframe": timeframe,
        "thresholds": thresholds,
        "reference_thresholds": dict(ref_thr),
        "cells_used": {t: len(v) for t, v in per_tier.items()},
        "selectivity_median": {t: float(np.median(v)) for t, v in selectivity.items()},
        "spread_iqr": {
            t: [round(float(np.quantile(v, 0.25)), 4), round(float(np.quantile(v, 0.75)), 4)]
            for t, v in per_tier.items()
        },
        "rank_correlation_median": round(float(np.median(rank_corr)), 4),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--metric", required=True)
    p.add_argument("--reference", default="hybrid")
    p.add_argument("--timeframe", default="1d")
    p.add_argument("--sample", type=int, default=40_000)
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    out = calibrate(args.metric, args.reference, args.timeframe, args.sample)

    path = DATA_DIR / "f3" / f"thresholds_{args.metric}.json"
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")

    print()
    print(f"{args.metric} ← {args.reference} ile aynı seçicilik ({args.timeframe})")
    print(f"{'kademe':<10}{'referans':>10}{'seçicilik':>12}{'yeni eşik':>11}{'IQR':>20}")
    for tier, t in out["reference_thresholds"].items():
        iqr = out["spread_iqr"][tier]
        print(f"{tier:<10}{t:>10.4f}{out['selectivity_median'][tier]:>11.3%}"
              f"{out['thresholds'][tier]:>11.4f}{f'[{iqr[0]:.4f}; {iqr[1]:.4f}]':>20}")
    print(f"\nsıra korelasyonu (medyan): {out['rank_correlation_median']}")
    print(f"yazıldı: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
