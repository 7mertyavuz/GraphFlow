"""Null örnekleminin rastgeleliği bulguları ne kadar oynatıyor?

Arama eşiği sorgunun null dağılımının yüzdeliğidir (F3.5): "orta" tolerans
2.000 rastgele pencerenin %0,25'lik dilimi — yani ~5. en küçük değer. Bu
kadar derin bir sıra istatistiği gürültülüdür; hangi 2.000 pencerenin
çekildiğini sabit bir tohum belirler. Bu araç **yalnız o tohumu**
değiştirir (veri, motor, istatistik aynı) ve F4.5'i yeniden koşar:

* her tohumda kaç hücre %95'te / Bonferroni'de anlamlı,
* her hücre tohumların kaçında anlamlı (0 < k < tohum sayısı → kararsız),
* 1d ve 4h'de aynı yönde anlamlı hücreler (F4.7 replikasyonu) tohumdan
  tohuma nasıl değişiyor.

Sonuç ``data/f3/null_sensitivity.json``.

    python -m tools.null_sensitivity --sizes 2000 20000 --seeds 5
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from functools import partialmethod

import engine.search.engine as search_engine
from engine.config import DATA_DIR, NULL_SEED
from engine.outcome.metrics import bonferroni_level
from tools.run_outcomes import _significant, run

log = logging.getLogger(__name__)

TIMEFRAMES = ("1d", "4h")


def _cells(report: dict) -> dict[tuple[str, str, str], dict]:
    return {
        (r["yon"], r["sablon"], r["konf"]): r for r in report["raw"] if r["olculebilir"]
    }


def measure(sizes: list[int], seeds: list[int], timeframes=TIMEFRAMES) -> dict:
    original_search = search_engine.SearchEngine.search
    runs: list[dict] = []
    try:
        for size in sizes:
            search_engine.SearchEngine.search = partialmethod(original_search, null_sample=size)
            for seed in seeds:
                search_engine.NULL_SEED = seed
                row: dict = {"null_sample": size, "null_seed": seed}
                for tf in timeframes:
                    t0 = time.time()
                    base = run(tf)
                    level = bonferroni_level(max(1, base["family"]))
                    strict = run(tf, confidence=level)
                    cells, cells_b = _cells(base), _cells(strict)
                    sig95 = {
                        "|".join(k): (1 if r["blok_alt"] > 0 else -1)
                        for k, r in cells.items()
                        if _significant(r["blok_alt"], r["blok_ust"])
                    }
                    sig_b = sorted(
                        "|".join(k) for k, r in cells_b.items() if _significant(r["blok_alt"], r["blok_ust"])
                    )
                    n_events = {"|".join(k): int(r["N"]) for k, r in cells.items()}
                    row[tf] = {"sig95": sig95, "bonferroni": sig_b, "n": n_events}
                    log.info(
                        "n=%d tohum=%d %s: %%95 %d · Bonferroni %d (%.0f sn)",
                        size, seed, tf, len(sig95), len(sig_b), time.time() - t0,
                    )
                if len(timeframes) == 2:
                    a, b = (row[tf]["sig95"] for tf in timeframes)
                    row["replicated"] = sorted(k for k in a if k in b and a[k] == b[k])
                runs.append(row)
    finally:
        search_engine.SearchEngine.search = original_search
        search_engine.NULL_SEED = NULL_SEED
    return {"sizes": sizes, "seeds": seeds, "timeframes": list(timeframes), "runs": runs}


def summarize(result: dict) -> list[str]:
    lines = []
    for size in result["sizes"]:
        runs = [r for r in result["runs"] if r["null_sample"] == size]
        lines.append(f"null örneklemi n = {size}  ({len(runs)} tohum)")
        for tf in result["timeframes"]:
            n95 = [len(r[tf]["sig95"]) for r in runs]
            nb = [len(r[tf]["bonferroni"]) for r in runs]
            counts: dict[str, int] = {}
            for r in runs:
                for k in r[tf]["sig95"]:
                    counts[k] = counts.get(k, 0) + 1
            stable = sum(1 for c in counts.values() if c == len(runs))
            flicker = sum(1 for c in counts.values() if c < len(runs))
            lines.append(
                f"  {tf}: %95 anlamlı hücre {min(n95)}–{max(n95)} · Bonferroni {min(nb)}–{max(nb)}"
                f" · her tohumda anlamlı {stable} · bazı tohumlarda {flicker}"
            )
        if "replicated" in runs[0]:
            reps = [len(r["replicated"]) for r in runs]
            every = set.intersection(*(set(r["replicated"]) for r in runs)) if runs else set()
            lines.append(f"  replikasyon: {min(reps)}–{max(reps)} hücre · her tohumda: {sorted(every)}")
    return lines


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sizes", nargs="+", type=int, default=[2_000, 20_000])
    p.add_argument("--seeds", type=int, default=5, help="tohum sayısı (NULL_SEED'den başlayarak)")
    p.add_argument("--timeframes", nargs="+", default=list(TIMEFRAMES))
    p.add_argument("--log-level", default="INFO")
    args = p.parse_args(argv)
    logging.basicConfig(level=args.log_level.upper(), format="%(asctime)s %(message)s")
    # Alt modüllerin ayrıntılı logları ölçümü boğmasın.
    for name in ("engine", "tools.run_outcomes"):
        logging.getLogger(name).setLevel(logging.WARNING)

    seeds = [NULL_SEED + k for k in range(args.seeds)]
    result = measure(args.sizes, seeds, tuple(args.timeframes))
    out = DATA_DIR / "f3" / "null_sensitivity.json"
    out.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    print("\n".join(summarize(result)))
    print(f"yazıldı: {out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
