"""F4.6 — Vekil testi: yükselen takoz gerçek mi, momentum mu?

Bu araç, F4.5'te short yönde anlamlı çıkan formasyonların edge'inin
şekle mi yoksa "yakın zamanda çok yükseldi" momentum tersine dönüşüne
mi bağlı olduğunu test eder.

Yöntem:
  1) Standart gölge: aynı ay + farklı sembol (mevcut F4/F4.5)
  2) Ön-getiri eşleştirmeli gölge: aynı ay + farklı sembol + benzer ön-getiri

Karar:
  • Edge SAĞ KALIRSA → bulgu şekille ilgili
  • Edge KAYBOLURSA → formasyon bir VEKİLdir

Çalıştırma:
  python -m tools.f46_proxy_test
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from engine.config import (
    DATA_DIR,
    RETURN_MATCH_BAND_SENSITIVITY,
    RETURN_MATCH_BAND_SIGMA,
    SHADOW_SAMPLES_PER_MATCH,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("f46_proxy_test")

# Test edilecek formasyonlar — F4.5'te short yönde anlamlı çıkanlar
TARGET_TEMPLATES = [
    "rising_wedge",
    "inverse_head_and_shoulders",
    "rounding_bottom",
    "cup_and_handle",
    "double_bottom",
]

# Her iki konfigürasyon da test edilir
CONFIGS_TO_TEST = ["2:1", "1:1"]


@dataclass
class ProxyResult:
    """Tek bir (formasyon, yön, konfigürasyon, band) sonucu."""

    template_id: str
    direction: str
    config: str
    band_sigma: float
    n_events: int
    n_shadow: int
    edge_r: float | None
    edge_ci: tuple[float, float] | None
    edge_is_significant: bool
    shadow_type: str  # "standard" veya "return_matched"
    fallback_band_widened: int = 0
    fallback_month_expanded: int = 0
    n_months: int = 0
    design_effect: float | None = None


def run_proxy_test(
    timeframe: str = "1d",
    templates: list[str] | None = None,
    bands: tuple[float, ...] = RETURN_MATCH_BAND_SENSITIVITY,
    seed: int = 20260731,
) -> list[ProxyResult]:
    """Vekil testini çalıştırır.

    Her hedef formasyon için:
      1) Standart gölge ile short outcome
      2) Her band genişliği için ön-getiri eşleştirmeli gölge ile short outcome
    """
    from engine.outcome.bars import BarStore
    from engine.outcome.pipeline import load_shadow_pools, run_template
    from engine.search.engine import SearchEngine
    from engine.templates import load_all

    templates = templates or TARGET_TEMPLATES
    all_templates = load_all()

    engine = SearchEngine()
    symbols_dict = engine.symbols
    symbols = list(symbols_dict.values())
    ids = {name: sid for sid, name in symbols_dict.items()}
    store = BarStore.from_klines(symbols, timeframe, ids)
    log.info("Bar deposu: %d sembol, %d bar", len(store.offset), store.close.size)

    # Standart gölge havuzu (ön-getiri yok)
    pools_standard = load_shadow_pools(timeframe)

    # Ön-getiri eşleştirmeli gölge havuzu
    pools_matched = load_shadow_pools(timeframe, store=store)

    results: list[ProxyResult] = []
    rng = np.random.default_rng(seed)

    for template_id in templates:
        template = all_templates.get(template_id)
        if template is None:
            log.warning("Şablon bulunamadı: %s", template_id)
            continue

        log.info("━" * 60)
        log.info("Formasyon: %s", template_id)

        # 1) Standart gölge — short
        log.info("  Standart gölge (short)...")
        outcome_std = run_template(
            engine, template_id, template.vector, store, pools_standard,
            timeframe=timeframe, rng=np.random.default_rng(seed),
            direction="short",
        )
        for config_name, stats in outcome_std.stats.items():
            results.append(ProxyResult(
                template_id=template_id,
                direction="short",
                config=config_name,
                band_sigma=0.0,
                n_events=stats.n,
                n_shadow=stats.shadow_n,
                edge_r=stats.edge_r,
                edge_ci=stats.edge_ci,
                edge_is_significant=stats.edge_is_significant,
                shadow_type="standard",
                n_months=stats.n_months,
                design_effect=stats.design_effect,
            ))
            sig = "✅ anlamlı" if stats.edge_is_significant else "❌ anlamsız"
            edge_str = f"{stats.edge_r:+.3f}R" if stats.edge_r is not None else "N/A"
            log.info("    %s: edge=%s %s (N=%d)", config_name, edge_str, sig, stats.n)

        # 2) Ön-getiri eşleştirmeli gölge — her band için
        for band in bands:
            log.info("  Ön-getiri eşleştirmeli gölge (band=±%.2fσ, short)...", band)
            outcome_matched = run_template(
                engine, template_id, template.vector, store, pools_matched,
                timeframe=timeframe, rng=np.random.default_rng(seed),
                direction="short",
                return_matched_shadow=True,
                return_band_sigma=band,
            )
            for config_name, stats in outcome_matched.stats.items():
                shadow_report = outcome_matched.shadow_report
                results.append(ProxyResult(
                    template_id=template_id,
                    direction="short",
                    config=config_name,
                    band_sigma=band,
                    n_events=stats.n,
                    n_shadow=stats.shadow_n,
                    edge_r=stats.edge_r,
                    edge_ci=stats.edge_ci,
                    edge_is_significant=stats.edge_is_significant,
                    shadow_type="return_matched",
                    fallback_band_widened=shadow_report.get("fallback_band_widened", 0),
                    fallback_month_expanded=shadow_report.get("fallback_month_expanded", 0),
                    n_months=stats.n_months,
                    design_effect=stats.design_effect,
                ))
                sig = "✅ anlamlı" if stats.edge_is_significant else "❌ anlamsız"
                edge_str = f"{stats.edge_r:+.3f}R" if stats.edge_r is not None else "N/A"
                log.info("    %s: edge=%s %s (N=%d, fb_band=%d, fb_month=%d)",
                         config_name, edge_str, sig, stats.n,
                         shadow_report.get("fallback_band_widened", 0),
                         shadow_report.get("fallback_month_expanded", 0))

    return results


def format_results_table(results: list[ProxyResult]) -> str:
    """Sonuçları markdown tablo olarak formatlar."""
    lines = [
        "| Formasyon | Konfig | Gölge Tipi | Band σ | N | Gölge N | Edge (R) | GA %95 | Anlamlı | DE |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        ci_str = f"[{r.edge_ci[0]:+.3f}, {r.edge_ci[1]:+.3f}]" if r.edge_ci and all(np.isfinite(r.edge_ci)) else "—"
        edge_str = f"{r.edge_r:+.3f}" if r.edge_r is not None else "—"
        sig_str = "✅" if r.edge_is_significant else "❌"
        de_str = f"{r.design_effect:.2f}" if r.design_effect is not None and np.isfinite(r.design_effect) else "—"
        band_str = f"±{r.band_sigma:.2f}" if r.band_sigma > 0 else "—"
        lines.append(
            f"| {r.template_id} | {r.config} | {r.shadow_type} | {band_str} | "
            f"{r.n_events} | {r.n_shadow} | {edge_str} | {ci_str} | {sig_str} | {de_str} |"
        )
    return "\n".join(lines)


def decide_verdict(results: list[ProxyResult]) -> str:
    """Vekil testi kararını oluşturur."""
    # Yükselen takoz, 2:1 konfigürasyonu, standard vs matched karşılaştırması
    rw_std = [r for r in results
              if r.template_id == "rising_wedge" and r.config == "2:1"
              and r.shadow_type == "standard"]
    rw_matched = [r for r in results
                  if r.template_id == "rising_wedge" and r.config == "2:1"
                  and r.shadow_type == "return_matched" and abs(r.band_sigma - RETURN_MATCH_BAND_SIGMA) < 0.01]

    lines = ["\n## Karar\n"]

    if rw_std and rw_matched:
        std = rw_std[0]
        matched = rw_matched[0]

        if matched.edge_is_significant:
            lines.append(
                "**SONUÇ: Yükselen takoz şekil bulgusudur.**\n\n"
                f"Ön-getiri eşleştirmeli gölge ile edge SAĞ KALDI: "
                f"{matched.edge_r:+.3f}R (N={matched.n_events}).\n\n"
                "Bu, formasyonun şeklinin momentum tersine dönüşünden BAĞIMSIZ "
                "olarak ek bilgi taşıdığı anlamına gelir. Benzer büyüklükte "
                "yükselmiş pencerelere göre de daha kötü performans veriyor."
            )
        else:
            lines.append(
                "**SONUÇ: Yükselen takoz bir VEKİLdir.**\n\n"
                f"Ön-getiri eşleştirmeli gölge ile edge KAYBOLDU: "
                f"{matched.edge_r:+.3f}R (GA sıfırı içeriyor, N={matched.n_events}).\n\n"
                "Formasyon, kriptoda kısa vadeli momentum tersine dönüşünü "
                "seçiyor ama ŞEKİL ek bilgi taşımıyor. Bu da değerli ve "
                "dürüst bir bulgudur."
            )

    # Diğer formasyonlar için özet
    other_templates = set(r.template_id for r in results if r.template_id != "rising_wedge")
    if other_templates:
        lines.append("\n### Diğer formasyonlar\n")
        for tid in sorted(other_templates):
            matched_results = [r for r in results
                               if r.template_id == tid and r.config == "2:1"
                               and r.shadow_type == "return_matched"
                               and abs(r.band_sigma - RETURN_MATCH_BAND_SIGMA) < 0.01]
            if matched_results:
                r = matched_results[0]
                status = "şekil" if r.edge_is_significant else "vekil/anlamsız"
                edge_str = f"{r.edge_r:+.3f}R" if r.edge_r is not None else "?"
                lines.append(f"- **{tid}**: {edge_str} → {status}")

    # Toplu karar: hepsi birlikte kaybolursa tek-etki hipotezi doğrulanmış
    all_matched = [r for r in results
                   if r.shadow_type == "return_matched" and r.config == "2:1"
                   and abs(r.band_sigma - RETURN_MATCH_BAND_SIGMA) < 0.01]
    n_significant = sum(1 for r in all_matched if r.edge_is_significant)
    lines.append(f"\n**{len(all_matched)} formasyondan {n_significant}'i ön-getiri eşleştirmeli "
                 f"gölge ile anlamlı kaldı.**")
    if n_significant == 0:
        lines.append("\n→ Tek-etki hipotezi DOĞRULANDI: tüm bulgular momentum tersine dönüşünün vekilleridir.")

    return "\n".join(lines)


def main():
    log.info("F4.6 Vekil Testi başlıyor...")

    results = run_proxy_test()

    # Tablo
    table = format_results_table(results)
    log.info("\n%s", table)

    # Karar
    verdict = decide_verdict(results)
    log.info(verdict)

    # Sonuçları kaydet
    output_dir = DATA_DIR / "f3"
    output_dir.mkdir(parents=True, exist_ok=True)

    # JSON
    raw = []
    for r in results:
        raw.append({
            "template_id": r.template_id,
            "direction": r.direction,
            "config": r.config,
            "band_sigma": r.band_sigma,
            "n_events": r.n_events,
            "n_shadow": r.n_shadow,
            "edge_r": r.edge_r,
            "edge_ci": list(r.edge_ci) if r.edge_ci else None,
            "edge_is_significant": r.edge_is_significant,
            "shadow_type": r.shadow_type,
            "fallback_band_widened": r.fallback_band_widened,
            "fallback_month_expanded": r.fallback_month_expanded,
            "n_months": r.n_months,
            "design_effect": r.design_effect,
        })
    with open(output_dir / "f46_raw.json", "w") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)
    log.info("Sonuçlar: %s", output_dir / "f46_raw.json")

    # Markdown rapor
    report = f"""# F4.6 — Vekil Testi Raporu

> **Tarih:** {__import__('datetime').datetime.now().strftime('%d %B %Y')}
> **Kapsam:** Ön-getiri eşleştirmeli gölge ile 5 formasyon testi

## Sonuç Tablosu

{table}

{verdict}

## Yöntem

Her eşleşme için standart gölge (aynı ay + farklı sembol) ve ön-getiri
eşleştirmeli gölge (aynı ay + farklı sembol + benzer ön-getiri) ile
triple-barrier outcome hesaplanmıştır.

Ön-getiri eşleştirme bandı: ±{RETURN_MATCH_BAND_SIGMA}σ (evren geneli σ).
Duyarlılık: ±0.15σ, ±0.25σ, ±0.50σ.

Fallback zinciri: band genişlet → ay esnet (±1 ay) → uyarı ver.
"""
    with open(output_dir / "f46_raporu.md", "w") as f:
        f.write(report)
    log.info("Rapor: %s", output_dir / "f46_raporu.md")


if __name__ == "__main__":
    main()
