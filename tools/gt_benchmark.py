"""Ground truth ölçüm zemini — motorun *bulması gereken* şey bilindiğinde.

**Neden ayrı bir araç.** ``tools/formation_audit`` sonuçların yapısını
denetler; iyi bir denetçidir ama zarf eğimlerini kullanır. Zarf eğimlerine
dayanan bir *filtre* onunla ölçülürse ölçüm dairesel olur: filtre kendi
ölçütünü optimize eder ve tablo iyileşir, ürün iyileşmeden.

Bu araç dairesellikten tek bilinen yolla kaçar: **formasyonu biz koyarız.**
Sentetik GBM serisine bilinen bir formasyon bilinen bir bar aralığına
enjekte edilir; motorun döndürdüğü pencere o aralıkla örtüşüyorsa doğru,
örtüşmüyorsa yanlıştır. Ölçüt motorun mekanizmasından da denetçinin
mekanizmasından da bağımsızdır.

Gürültü sembollerine **başka** formasyonlar enjekte edilir. Üçgen ararken
bir bayrağın üstüne düşmek isabet sayılmaz — asıl sorulan soru budur.

    python -m tools.gt_benchmark --pattern ascending_triangle
    python -m tools.gt_benchmark --family slope --compare-structure
"""

from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from pathlib import Path

import numpy as np

from engine.matrix.build import build_all
from engine.ingest.store import write_atomic
from engine.search.engine import SearchEngine
from engine.search.nms import iou_1d
from engine.templates import get as get_template
from tools.gen_synthetic import Injection, make_symbol

log = logging.getLogger("tools.gt_benchmark")

TF = "4h"

#: Eğimle tanımlı aile — F4.9'da motorun zayıf olduğu ölçülen küme.
SLOPE_FAMILY = (
    "ascending_triangle",
    "descending_triangle",
    "symmetrical_triangle",
    "rising_wedge",
    "falling_wedge",
    "pennant",
    "bull_flag",
    "bear_flag",
)

#: Dönüş ailesi — yapısal filtrenin belirleyici olduğu ölçülen küme.
REVERSAL_FAMILY = (
    "head_and_shoulders",
    "inverse_head_and_shoulders",
    "double_top",
    "double_bottom",
)

FAMILIES = {
    "slope": SLOPE_FAMILY,
    "reversal": REVERSAL_FAMILY,
    "all": REVERSAL_FAMILY + SLOPE_FAMILY,
}

#: Bir sonucun enjeksiyonu "yakaladı" sayılması için gereken örtüşme.
#: 0,3 tesadüfi bir değer değil: motorun pencere ızgarası (stride 3, dört
#: uzunluk) enjeksiyonun sınırlarına tam oturamaz.
MIN_IOU = 0.30


def build_corpus(
    pattern: str,
    root: Path,
    n_targets: int = 24,
    n_noise: int = 40,
    seed: int = 2026,
) -> list[Injection]:
    """Hedef formasyonu bilinen yerlere koyar, etrafını başka şekillerle doldurur.

    Gürültü sembollerine aranan formasyon **hariç** diğerleri enjekte edilir:
    "üçgen ararken bayrak buldu" bir isabet değil, tam da ölçmek istediğimiz
    hatadır.
    """
    rng = np.random.default_rng(seed)
    truth: list[Injection] = []

    for i in range(n_targets):
        df, injections = make_symbol(
            f"TGT{i:03d}USDT",
            rng,
            n_bars=900,
            patterns=(pattern,),
            n_injections=1,
            length_range=(40, 90),
            amplitude_range=(0.18, 0.40),
            noise_range=(0.01, 0.05),
        )
        write_atomic(df, root / "klines" / TF / f"TGT{i:03d}USDT.parquet")
        truth.extend(injections)

    others = tuple(p for p in FAMILIES["all"] if p != pattern)
    for i in range(n_noise):
        df, _ = make_symbol(
            f"NOI{i:03d}USDT", rng, n_bars=900, patterns=others, n_injections=3
        )
        write_atomic(df, root / "klines" / TF / f"NOI{i:03d}USDT.parquet")

    build_all(
        timeframes=[TF],
        klines_root=root / "klines",
        out_root=root / "matrix",
        use_liquidity=False,  # sentetik korpusta kesitsel filtre anlamsız
    )
    return truth


def score(result, truth: list[Injection], min_iou: float = MIN_IOU) -> dict:
    """Kesinlik (ilk k'nin kaçı doğru) ve duyarlılık (enjeksiyonların kaçı bulundu)."""
    by_symbol: dict[str, list[Injection]] = {}
    for inj in truth:
        by_symbol.setdefault(inj.symbol, []).append(inj)

    correct = 0
    found: set[tuple[str, int]] = set()
    for match in result.results:
        for inj in by_symbol.get(match.symbol, ()):
            if iou_1d(match.start_idx, match.end_idx, inj.start, inj.end) >= min_iou:
                correct += 1
                found.add((inj.symbol, inj.start))
                break

    shown = len(result.results)
    return {
        "shown": shown,
        "correct": correct,
        "precision": correct / shown if shown else 0.0,
        "recall": len(found) / len(truth) if truth else 0.0,
        "total": result.total,
    }


def benchmark(
    patterns: tuple[str, ...],
    limit: int = 24,
    n_targets: int = 24,
    n_noise: int = 40,
    seed: int = 2026,
    tolerance: str = "flexible",
    variants: dict[str, dict] | None = None,
) -> list[dict]:
    """Formasyon başına: enjekte edilenleri bulabiliyor mu?

    ``variants`` her biri ``engine.search`` kwargs'ı olan adlandırılmış
    konfigürasyonlardır; aynı korpus üzerinde karşılaştırılır.
    """
    variants = variants or {"": {}}
    rows: list[dict] = []

    for pattern in patterns:
        with tempfile.TemporaryDirectory(prefix=f"gt-{pattern}-") as tmp:
            root = Path(tmp)
            truth = build_corpus(pattern, root, n_targets, n_noise, seed)
            engine = SearchEngine(root / "matrix")
            query = np.asarray(get_template(pattern).vector, dtype=np.float64)

            row = {"pattern": pattern, "injected": len(truth)}
            for label, kwargs in variants.items():
                result = engine.search(
                    query, mode="historical", timeframe=TF,
                    tolerance=tolerance, limit=limit, **kwargs
                )
                suffix = f"_{label}" if label else ""
                for key, value in score(result, truth).items():
                    row[f"{key}{suffix}"] = value
            rows.append(row)
            log.info("%s bitti", pattern)
    return rows


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pattern", nargs="+", default=None)
    p.add_argument("--family", choices=sorted(FAMILIES), default="slope")
    p.add_argument("--limit", type=int, default=24)
    p.add_argument("--targets", type=int, default=24)
    p.add_argument("--noise", type=int, default=40)
    p.add_argument("--seed", type=int, default=2026)
    p.add_argument("--tolerance", default="flexible")
    p.add_argument("--compare-structure", action="store_true",
                   help="Yapısal filtre AÇIK/KAPALI karşılaştırması")
    p.add_argument("--compare-envelope", action="store_true",
                   help="Zarf (trend çizgisi) filtresi AÇIK/KAPALI karşılaştırması")
    p.add_argument("--compare-gate", action="store_true",
                   help="Kararlılık kapısı AÇIK (seçici) / KAPALI (her sorguda filtre)")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    patterns = tuple(args.pattern or FAMILIES[args.family])
    if args.compare_structure:
        variants = {"on": {"structure_filter": True}, "off": {"structure_filter": False}}
    elif args.compare_gate:
        variants = {
            "kapı": {"structure_filter": True, "structure_gate": True},
            "hep": {"structure_filter": True, "structure_gate": False},
        }
    elif args.compare_envelope:
        variants = {"on": {"envelope_filter": True}, "off": {"envelope_filter": False}}
    else:
        variants = {"": {}}

    rows = benchmark(patterns, args.limit, args.targets, args.noise,
                     args.seed, args.tolerance, variants)

    print()
    print(f"ground truth · {TF} · {args.targets} hedef + {args.noise} gürültü sembolü"
          f" · ilk {args.limit} · IoU ≥ {MIN_IOU}")
    print()
    labels = [k for k in variants]
    header = f"{'formasyon':<26}"
    for label in labels:
        header += f"{('kesinlik ' + label).strip():>16}{('duyarlılık ' + label).strip():>18}"
    print(header)
    print("-" * len(header))
    for r in rows:
        line = f"{r['pattern']:<26}"
        for label in labels:
            s = f"_{label}" if label else ""
            line += f"{r['correct'+s]}/{r['shown'+s]} = {r['precision'+s]:>4.0%}".rjust(16)
            line += f"{r['recall'+s]:>17.0%} "
        print(line)
    print()
    for label in labels:
        s = f"_{label}" if label else ""
        c = sum(r["correct" + s] for r in rows)
        n = sum(r["shown" + s] for r in rows)
        rec = np.mean([r["recall" + s] for r in rows])
        tag = f" ({label})" if label else ""
        print(f"genel{tag}: kesinlik {c}/{n} = %{100*c/max(1,n):.0f} · ortalama duyarlılık %{100*rec:.0f}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
