"""F4 / F4.5 ölçümünü uçtan uca üretir — 14 şablon × 2 yön × 2 konfigürasyon.

**Neden yazıldı.** `data/f3/` altındaki `f4_outcomes.json`, `f4_bonferroni.json`,
`f45_raw.json`, `f45_bonferroni.json` dosyaları `/api/findings`'in ve
`docs/05` – `docs/06` raporlarının dayanağı. Ama bu dosyaları üreten hiçbir
araç depoda **yoktu**: tek seferlik betiklerle üretilip commit edilmişlerdi.

Sonucu, projenin en çok karşı olduğu şeydi: yayınlanan sayılar yeniden
üretilemiyordu. Korpus her değiştiğinde (yeni sembol, tazeleme, invariant
düzeltmesi) rakamlar sessizce bayatlıyor ve kimse fark edemiyordu —
F4.6'nın geçersiz tablosu tam olarak böyle üç hafta yayında kaldı.

**Yöntem** (K-12, K-16, F4.5):

1. Her şablon için arama → post-NMS tekil eşleşmeler
2. İleri pencere ayrımı + işlem maliyeti tabanı + ATR ısınması
3. Triple-barrier, iki konfigürasyon (2:1 ve 1:1), iki yön (long ve short)
4. Zaman-eşleştirmeli gölge dağılım
5. Edge GA'sı **ay-bloklu** bootstrap (iid karşılaştırma için saklanır)
6. Bonferroni: aile = ölçülebilen test sayısı

Tolerans kademesi `OUTCOME_TOLERANCE` ile sabittir — p-hacking kilidi.

    python -m tools.run_outcomes --timeframe 1d
    python -m tools.run_outcomes --timeframe 4h --out-suffix _4h
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np

from engine.config import CONFIDENCE_LEVEL, DATA_DIR, OUTCOME_TOLERANCE
from engine.fingerprint import provenance
from engine.outcome.bars import BarStore
from engine.outcome.metrics import bonferroni_level
from engine.outcome.pipeline import events_from_matches, load_shadow_pools, run_events
from engine.search.engine import SearchEngine

log = logging.getLogger("tools.run_outcomes")

DIRECTIONS = ("long", "short")


def _f(value) -> float | None:
    """NaN/inf yerine None — JSON'da NaN geçersizdir."""
    if value is None:
        return None
    v = float(value)
    return v if np.isfinite(v) else None


def _significant(lo, hi) -> bool:
    return lo is not None and hi is not None and (lo > 0.0 or hi < 0.0)


def run(
    timeframe: str = "1d",
    limit: int = 5_000,
    seed: int = 20260731,
    templates: list[str] | None = None,
    confidence: float = CONFIDENCE_LEVEL,
) -> dict:
    """Tüm şablonları iki yönde koşar; ham ve Bonferroni tablolarını döner."""
    from engine.templates import load_all

    engine = SearchEngine()
    symbols = engine.symbols_for(timeframe)
    if not symbols:
        raise SystemExit(f"{timeframe} için sembol haritası yok — matrisleri kur")

    store = BarStore.from_klines(
        list(symbols.values()), timeframe, {n: i for i, n in symbols.items()}
    )
    pools = load_shadow_pools(timeframe)
    log.info("bar deposu: %d sembol, %d bar", len(store.offset), store.close.size)

    all_templates = load_all()
    chosen = templates or list(all_templates)

    outcomes: list[dict] = []
    raw: list[dict] = []
    started = time.time()

    for i, template_id in enumerate(chosen, 1):
        template = all_templates.get(template_id)
        if template is None:
            log.warning("bilinmeyen şablon: %s", template_id)
            continue

        query = np.asarray(template.vector, dtype=np.float64)
        result = engine.search(
            query, timeframe=timeframe, tolerance=OUTCOME_TOLERANCE, limit=limit
        )
        events = events_from_matches(result.results)
        log.info(
            "[%d/%d] %s: %d eşleşme (%.0f ms)",
            i, len(chosen), template_id, len(result.results), result.elapsed_ms,
        )

        for direction in DIRECTIONS:
            outcome = run_events(
                events, store, pools,
                template_id=template_id, timeframe=timeframe,
                rng=np.random.default_rng(seed), direction=direction,
                confidence=confidence,
            )
            if direction == "long":
                # docs/05 (F4) tablosu long yönlüdür.
                outcomes.append(outcome.as_dict())

            for config, stats in outcome.stats.items():
                blok = stats.edge_ci or (None, None)
                iid = stats.edge_ci_iid or (None, None)
                raw.append({
                    "yon": direction,
                    "sablon": template_id,
                    "konf": config,
                    "N": int(stats.n),
                    "n_months": int(stats.n_months),
                    "beklenti": _f(stats.expectancy_r),
                    "net": _f(stats.expectancy_net_r),
                    "basari": _f(stats.win_rate),
                    "golge": _f(stats.shadow_expectancy_r),
                    "golge_N": int(stats.shadow_n),
                    "edge": _f(stats.edge_r),
                    "blok_alt": _f(blok[0]),
                    "blok_ust": _f(blok[1]),
                    "iid_alt": _f(iid[0]),
                    "iid_ust": _f(iid[1]),
                    "tasarim": _f(stats.design_effect),
                    "olculebilir": bool(stats.shadow_n > 0 and stats.n > 0),
                })

    measurable = [r for r in raw if r["olculebilir"]]
    family = max(1, len(measurable))
    level = bonferroni_level(family)
    log.info(
        "ölçülebilen test: %d/%d → Bonferroni güven düzeyi %.6f (%.0f sn)",
        family, len(raw), level, time.time() - started,
    )

    return {
        "outcomes": outcomes,
        "raw": raw,
        "family": family,
        "level": level,
        "timeframe": timeframe,
        "confidence": confidence,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--timeframe", default="1d")
    p.add_argument("--limit", type=int, default=5_000)
    p.add_argument("--seed", type=int, default=20260731)
    p.add_argument("--templates", nargs="+", default=None)
    p.add_argument("--out-suffix", default="", help="Dosya adlarına eklenecek son ek (ör. _4h)")
    p.add_argument("--log-level", default="INFO")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    report = run(args.timeframe, args.limit, args.seed, args.templates)

    # Bonferroni düzeltilmiş aralıklar için ikinci geçiş.
    log.info("Bonferroni geçişi (%.6f güven düzeyi)...", report["level"])
    corrected = _rerun_at_level(report, args.limit, args.seed, args.templates)

    out = DATA_DIR / "f3"
    out.mkdir(parents=True, exist_ok=True)
    sfx = args.out_suffix

    f45_bonf = []
    for r in report["raw"]:
        c = corrected.get((r["yon"], r["sablon"], r["konf"]), {})
        f45_bonf.append({
            "yon": r["yon"],
            "sablon": r["sablon"],
            "konf": r["konf"],
            "N": r["N"],
            "edge": r["edge"],
            "b_alt": c.get("blok_alt"),
            "b_ust": c.get("blok_ust"),
            "olculebilir": r["olculebilir"],
            "bonf_anlamli": bool(r["olculebilir"] and _significant(c.get("blok_alt"), c.get("blok_ust"))),
        })

    # F4 tablosu: long yön, %95 ve Bonferroni yan yana.
    f4_bonf = []
    for r in report["raw"]:
        if r["yon"] != "long":
            continue
        c = corrected.get((r["yon"], r["sablon"], r["konf"]), {})
        f4_bonf.append({
            "sablon": r["sablon"],
            "konf": r["konf"],
            "N": r["N"],
            "edge": r["edge"],
            "lo95": r["blok_alt"],
            "hi95": r["blok_ust"],
            "lo_bonf": c.get("blok_alt"),
            "hi_bonf": c.get("blok_ust"),
            "anlamli95": bool(r["olculebilir"] and _significant(r["blok_alt"], r["blok_ust"])),
            "anlamli_bonf": bool(r["olculebilir"] and _significant(c.get("blok_alt"), c.get("blok_ust"))),
        })

    files = {
        f"f4_outcomes{sfx}.json": report["outcomes"],
        f"f4_bonferroni{sfx}.json": f4_bonf,
        f"f45_raw{sfx}.json": report["raw"],
        f"f45_bonferroni{sfx}.json": f45_bonf,
        f"f45_meta{sfx}.json": {
            "family_size": report["family"],
            "bonferroni_level": report["level"],
            "confidence_level": CONFIDENCE_LEVEL,
            "timeframe": report["timeframe"],
            "tolerance": OUTCOME_TOLERANCE,
            # Hangi motor, hangi veri: /api/findings bunu bugünkü motorla
            # karşılaştırır. Eksik olsaydı bayat tablo sessizce yayında kalırdı.
            **provenance(report["timeframe"]),
        },
    }
    for name, payload in files.items():
        (out / name).write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
        log.info("yazıldı: %s", out / name)

    n95 = sum(1 for r in report["raw"]
              if r["olculebilir"] and _significant(r["blok_alt"], r["blok_ust"]))
    nb = sum(1 for r in f45_bonf if r["bonf_anlamli"])
    print()
    print(f"{report['timeframe']} · {report['family']} ölçülebilen test")
    print(f"  %95'te anlamlı      : {n95}")
    print(f"  Bonferroni'den geçen: {nb}")
    for r in f45_bonf:
        if r["bonf_anlamli"]:
            print(f"    {r['sablon']} {r['yon']} {r['konf']}  edge {r['edge']:+.3f}  "
                  f"[{r['b_alt']:+.3f}; {r['b_ust']:+.3f}]  N={r['N']}")
    print()
    return 0


def _rerun_at_level(report: dict, limit: int, seed: int, templates=None) -> dict:
    """Düzeltilmiş güven düzeyinde ikinci koşu.

    Aralığı analitik olarak "genişletmek" yerine yeniden bootstrap'lamak
    gerekir: blok bootstrap dağılımı simetrik değildir, ölçekleme yanlış
    aralık verirdi. ``confidence`` açıkça geçirilir — ``summarize``'ın
    varsayılanı tanım anında bağlandığı için modül global'ini değiştirmek
    hiçbir şey yapmazdı.
    """
    second = run(report["timeframe"], limit, seed, templates, confidence=report["level"])
    return {(r["yon"], r["sablon"], r["konf"]): r for r in second["raw"]}


if __name__ == "__main__":
    sys.exit(main())
