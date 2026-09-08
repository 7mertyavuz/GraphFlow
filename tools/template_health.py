"""Şablon kütüphanesinin sağlık raporu — hangi şablon gerçek veride ölü?

Kütüphanedeki 14 formasyon eşit görünür: hepsi kanonik 32 noktalık vektör,
hepsi aynı pipeline'dan geçer (K-04). Ama gerçek korpusta eşit davranmazlar.
F4.7 ölçümünde göze çarptı:

    symmetrical_triangle  →  1d'de 4, 4h'de 16 eşleşme
    diğer 13 şablon       →  166 – 799 eşleşme

Sebep motor hatası değil, **şablonun temsil sınırına dayanması**: kanonik
vektör 3 tam salınım istiyor, 32 nokta ise çevrim başına ~10 nokta bırakıyor.
Parametre taraması bunu doğruladı (1d, orta tolerans):

    çevrim 1,5 → 260 eşleşme      çevrim 2,5 →  23
    çevrim 2,0 → 165 eşleşme      çevrim 3,0 →   4  ← mevcut şablon

Şablon **kusurlu değil** — kendi gürültülü varyantlarına mesafesi (0,0037)
diğer şablonlarla aynı bantta. Yalnızca gerçek piyasada o kadar temiz üç
çevrim nadir.

Bu araç aynı hatanın sessiz kalmasını engeller: her şablon için gerçek
korpusta kaç eşleşme bulunduğunu ve null yayılımını raporlar. Ayırt edicilik
uyarı eşiğine yakın ya da eşleşme sayısı tabanın altında olan şablonlar
işaretlenir.

    python -m tools.template_health --timeframe 1d
    python -m tools.template_health --timeframe 4h --min-matches 50
"""

from __future__ import annotations

import argparse
import logging
import sys

import numpy as np

from engine.config import (
    MIN_EVENTS_FOR_CLAIM,
    NULL_DISCRIMINATIVE_RATIO,
    OUTCOME_TOLERANCE,
)
from engine.search.engine import SearchEngine

log = logging.getLogger("tools.template_health")

#: Bu sayının altında eşleşme veren şablon, istatistik üretemez (bkz.
#: MIN_EVENTS_FOR_CLAIM: eşleşmelerin bir kısmı ayrım ve filtrelerde düşer).
DEFAULT_MIN_MATCHES = MIN_EVENTS_FOR_CLAIM


def health(
    timeframe: str = "1d",
    tolerance: str = OUTCOME_TOLERANCE,
    min_matches: int = DEFAULT_MIN_MATCHES,
) -> list[dict]:
    """Şablon başına eşleşme sayısı, null yayılımı ve uyarılar."""
    from engine.templates import load_all

    engine = SearchEngine()
    rows: list[dict] = []

    for template_id, template in sorted(load_all().items()):
        query = np.asarray(template.vector, dtype=np.float64)
        result = engine.search(query, timeframe=timeframe, tolerance=tolerance, limit=12)

        spreads = [
            s.spread for s in result.null_stats.values()
            if not s.used_absolute and np.isfinite(s.spread)
        ]
        spread = float(np.median(spreads)) if spreads else float("nan")

        rows.append({
            "template_id": template_id,
            "total": int(result.total),
            "spread": spread,
            "discriminative": bool(result.discriminative),
            "first_score": float(result.results[0].score) if result.results else float("nan"),
            "elapsed_ms": float(result.elapsed_ms),
            "too_few": int(result.total) < min_matches,
            "near_warning": np.isfinite(spread) and spread < NULL_DISCRIMINATIVE_RATIO * 1.5,
        })
    return rows


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--timeframe", default="1d")
    p.add_argument("--tolerance", default=OUTCOME_TOLERANCE)
    p.add_argument("--min-matches", type=int, default=DEFAULT_MIN_MATCHES)
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    rows = health(args.timeframe, args.tolerance, args.min_matches)

    print()
    print(f"{args.timeframe} · tolerans {args.tolerance} · eşleşme tabanı {args.min_matches}")
    print(f"ayırt edicilik uyarı eşiği: null yayılımı < {NULL_DISCRIMINATIVE_RATIO}")
    print()
    print(f"{'şablon':<30}{'eşleşme':>9}{'yayılım':>9}{'ilk r':>8}  durum")
    print("-" * 72)

    problems = 0
    for r in sorted(rows, key=lambda x: x["total"]):
        notes = []
        if r["too_few"]:
            notes.append("EŞLEŞME AZ")
        if not r["discriminative"]:
            notes.append("AYIRT EDİCİ DEĞİL")
        elif r["near_warning"]:
            notes.append("uyarı eşiğine yakın")
        if notes:
            problems += 1
        spread = f"{r['spread']:.1f}" if np.isfinite(r["spread"]) else "—"
        first = f"{r['first_score']:.3f}" if np.isfinite(r["first_score"]) else "—"
        print(f"{r['template_id']:<30}{r['total']:>9}{spread:>9}{first:>8}  {' · '.join(notes)}")

    print()
    if problems:
        print(f"⚠ {problems} şablon işaretlendi. Az eşleşme veren bir şablon kusurlu")
        print("  olmak zorunda değil — kanonik vektör temsil sınırına dayanıyor da")
        print("  olabilir (32 noktada çok sayıda salınım). Parametreyi değiştirmek")
        print("  F3 eşik kalibrasyonunun girdisini değiştirir; ölçmeden dokunma.")
    else:
        print("✅ tüm şablonlar taban üstünde ve ayırt edici")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
