"""Kullanıcıya dönen metinlerin iki dilli kataloğu (tr / en).

**İlke: motor veri üretir, metni API üretir.** Arama sonuçları önbelleğe
yazılır (Radar önbelleği birden çok kullanıcıya hizmet eder). Motorun okuması
ya da bir uyarı önbelleğe *metin* olarak yazılsaydı, Türkçe bir istemcinin
doldurduğu önbellekten İngilizce bir istemci Türkçe metin alırdı. Bu yüzden
önbellekte dilden bağımsız veri (imza demetleri, uyarı kodları) durur ve
metin yanıt anında, isteğin diliyle üretilir.

Dil ``Accept-Language`` başlığından okunur. Tarayıcı bu başlığı zaten
gönderir, dolayısıyla varsayılan kendiliğinden doğrudur; arayüzdeki dil
düğmesi başlığı açıkça ayarlar.
"""

from __future__ import annotations

from typing import Literal

Lang = Literal["tr", "en"]
LANGS: tuple[str, ...] = ("tr", "en")
DEFAULT_LANG: Lang = "tr"


def resolve_lang(header: str | None) -> Lang:
    """``Accept-Language`` değerinden desteklenen ilk dil.

    Kalite değerleri (``q=``) sıralamayı belirler; eşitlikte başlıktaki sıra
    korunur. Desteklenen dil yoksa varsayılan.
    """
    if not header:
        return DEFAULT_LANG
    ranked: list[tuple[float, int, str]] = []
    for pos, part in enumerate(header.split(",")):
        piece = part.strip()
        if not piece:
            continue
        tag, _, params = piece.partition(";")
        q = 1.0
        params = params.strip()
        if params.startswith("q="):
            try:
                q = float(params[2:])
            except ValueError:
                q = 0.0
        ranked.append((-q, pos, tag.strip().lower().split("-")[0]))
    for _, _, primary in sorted(ranked):
        if primary in LANGS:
            return primary  # type: ignore[return-value]
    return DEFAULT_LANG


MESSAGES: dict[str, dict[str, str]] = {
    # --- motorun okuması: yapısal imza --------------------------------------
    "sig.peak": {"tr": "tepe", "en": "peak"},
    "sig.trough": {"tr": "dip", "en": "trough"},
    "sig.peaks": {"tr": "tepe", "en": "peaks"},
    "sig.troughs": {"tr": "dip", "en": "troughs"},
    "sig.count": {"tr": "{n} belirgin {what}", "en": "{n} prominent {what}"},
    "sig.all_similar": {"tr": "hepsi benzer seviyede", "en": "all at similar levels"},
    "sig.first": {"tr": "ilki", "en": "the first"},
    "sig.last": {"tr": "sonuncusu", "en": "the last"},
    "sig.middle": {"tr": "ortadaki", "en": "the middle one"},
    "sig.nth": {"tr": "{k}. sıradaki", "en": "number {k}"},
    "sig.highest": {"tr": "{who} en yüksek", "en": "{who} highest"},
    "sig.deepest": {"tr": "{who} en derin", "en": "{who} deepest"},
    "sig.others_similar": {"tr": "diğerleri benzer seviyede", "en": "the others at similar levels"},
    # --- motorun okuması: trend çizgisi (zarf) ------------------------------
    "env.upper.-1": {"tr": "alçalan tepeler", "en": "falling highs"},
    "env.upper.0": {"tr": "yatay direnç", "en": "flat resistance"},
    "env.upper.1": {"tr": "yükselen tepeler", "en": "rising highs"},
    "env.lower.-1": {"tr": "alçalan dipler", "en": "falling lows"},
    "env.lower.0": {"tr": "yatay destek", "en": "flat support"},
    "env.lower.1": {"tr": "yükselen dipler", "en": "rising lows"},
    "env.conv.-1": {"tr": "genişleyen", "en": "widening"},
    "env.conv.0": {"tr": "paralel", "en": "parallel"},
    "env.conv.1": {"tr": "daralan", "en": "narrowing"},
    # --- arama uyarıları ----------------------------------------------------
    "warn.structure_relaxed": {
        "tr": (
            "Çizdiğiniz yapıyı (tepe/dip düzenini) taşıyan yeterli pencere "
            "bulunamadı; sonuçlar yapısal filtre UYGULANMADAN listelendi. "
            "Şekil benzer olabilir ama formasyonun kendisi olmayabilir."
        ),
        "en": (
            "Not enough windows carry the structure you drew (its peak/trough "
            "pattern); results are listed WITHOUT the structural filter. The "
            "shape may be similar without being the formation itself."
        ),
    },
    "warn.not_discriminative": {
        "tr": (
            "Bu çizime yapısal olarak benzeyen bir hareket bulunamadı; "
            "sonuçlar anlamlı olmayabilir. Daha belirgin bir formasyon deneyin."
        ),
        "en": (
            "No price movement structurally resembles this drawing; the "
            "results may not be meaningful. Try a more distinct formation."
        ),
    },
    # --- istatistik hükümleri -----------------------------------------------
    "verdict.insufficient": {
        "tr": "yetersiz örnek (N = {n}) — sayılar okunmamalı",
        "en": "insufficient sample (N = {n}) — do not read these numbers",
    },
    "verdict.no_shadow": {
        "tr": "gölge dağılım yok — edge iddiası yapılamaz",
        "en": "no shadow distribution — no edge claim can be made",
    },
    "verdict.not_significant": {
        "tr": "anlamlı fark ölçülemedi",
        "en": "no significant difference measured",
    },
    "verdict.significant": {
        "tr": "anlamlı fark ({side}): {edge}R",
        "en": "significant difference ({side}): {edge}R",
    },
    "verdict.favorable": {"tr": "lehte", "en": "favorable"},
    "verdict.unfavorable": {"tr": "aleyhte", "en": "unfavorable"},
    "disclaimer": {
        "tr": (
            "Geçmiş dağılım gelecek getirinin garantisi değildir. Burada gösterilen "
            "her sayı ölçülmüş bir geçmiş istatistiktir; işlem tavsiyesi değildir."
        ),
        "en": (
            "A past distribution is no guarantee of future returns. Every number "
            "shown here is a measured historical statistic, not trading advice."
        ),
    },
    "live_no_stats": {
        "tr": "Canlı radar sonuçlarının ileri penceresi yok; istatistik için tarihsel mod kullanın",
        "en": "Live radar results have no forward window yet; use historical mode for statistics",
    },
    # --- gerçek grafikten sorgu (engine/search/source.py) --------------------
    "source.unknown_symbol": {
        "tr": "Bu zaman diliminde böyle bir sembol yok: {symbol}",
        "en": "No such symbol in this timeframe: {symbol}",
    },
    "source.not_enough_bars": {
        "tr": "Seçilen noktadan geriye {length} bar yok",
        "en": "There are not {length} bars before the selected point",
    },
    "source.price_jump": {
        "tr": (
            "Parçada fiyat sıçraması var (redenominasyon ya da ticker yeniden "
            "kullanımı); bu bir şekil değil birim değişikliği"
        ),
        "en": (
            "The segment contains a price jump (redenomination or ticker reuse); "
            "that is a change of unit, not a shape"
        ),
    },
    "source.flat": {
        "tr": "Parça düz: şekil taşımayan bir sorgu aranamaz (σ ≈ 0)",
        "en": "The segment is flat: a query without shape cannot be searched (σ ≈ 0)",
    },
    "source.bad_length": {
        "tr": "Parça uzunluğu {min}–{max} bar olmalı",
        "en": "Segment length must be {min}–{max} bars",
    },
    # --- oturum (çoklu karşılaştırma) ---------------------------------------
    "session.warning": {
        "tr": (
            "Bu oturumda {n} farklı şekil denendi. Bonferroni düzeltilmiş "
            "anlamlılık eşiği α = {alpha}; bu eşiği geçmeyen bulgular şans "
            "eseri ortaya çıkmış olabilir."
        ),
        "en": (
            "{n} different shapes were tried in this session. The Bonferroni-"
            "corrected significance threshold is α = {alpha}; findings that do "
            "not clear it may have appeared by chance."
        ),
    },
    # --- ölçüm kökeni -------------------------------------------------------
    "prov.no_fingerprint": {
        "tr": "Ölçüm dosyası motor parmak izi taşımıyor (bu mekanizmadan önce üretilmiş).",
        "en": "The measurement file carries no engine fingerprint (produced before this mechanism).",
    },
    "prov.config_changed": {
        "tr": "Motor değişti; farklı sabitler: {keys}.",
        "en": "The engine changed; different constants: {keys}.",
    },
    "prov.code_changed": {
        "tr": "Motor değişti (sabitler aynı — bir filtre ya da metrik kodu değişmiş).",
        "en": "The engine changed (same constants — a filter or metric implementation changed).",
    },
    # --- bulgular sayfası ---------------------------------------------------
    "cells.none": {"tr": "hiçbiri", "en": "none"},
    "stage.f4": {"tr": "F4 — ham triple-barrier", "en": "F4 — raw triple-barrier"},
    "stage.f4.desc": {
        "tr": "ATR bariyerleri, iid bootstrap, tüm-geçmiş baseline",
        "en": "ATR barriers, i.i.d. bootstrap, all-history baseline",
    },
    "stage.f45": {"tr": "F4.5 — ay-bloklu bootstrap", "en": "F4.5 — month-block bootstrap"},
    "stage.f45.desc": {
        "tr": "Kesitsel korelasyon düzeltmesi; iid belirsizliği ~%29 eksik ölçüyordu",
        "en": "Cross-sectional correlation correction; i.i.d. understated uncertainty by ~29%",
    },
    "stage.f45b": {"tr": "F4.5 — Bonferroni (long + short)", "en": "F4.5 — Bonferroni (long + short)"},
    "stage.f45b.desc": {
        "tr": "14 şablon × 2 yön × 2 konfigürasyon, aile bazlı düzeltme",
        "en": "14 templates × 2 directions × 2 configurations, family-wise correction",
    },
    "stage.f46": {
        "tr": "F4.6 — ön-getiri eşleştirmeli gölge (1d)",
        "en": "F4.6 — return-matched shadow (1d)",
    },
    "stage.f46.desc": {
        "tr": (
            "Gölge havuzuna 'benzer ön-getiri' kısıtı eklendi: fark buharlaşıyorsa "
            "ölçülen şey şekil değil, momentum tersine dönüşüdür. Sınanan şablonlar "
            "F4.5'te short yönde anlamlı çıkanlardır ({cells}); liste güncel "
            "ölçümden hesaplanır, elle yazılmaz."
        ),
        "en": (
            "The shadow pool is restricted to windows with a similar prior return: "
            "if the difference evaporates, what was measured is momentum reversal, "
            "not shape. Tested templates are those significant on the short side in "
            "F4.5 ({cells}); the list is computed from the current measurement, never "
            "hand-written."
        ),
    },
    "stage.f46b": {"tr": "F4.6 — Bonferroni", "en": "F4.6 — Bonferroni"},
    "stage.f46b.desc": {
        "tr": "Aynı aile, çoklu karşılaştırma düzeltmesiyle.",
        "en": "The same family, with multiple-comparison correction.",
    },
    "stage.f46r": {"tr": "F4.6 — 4h replikasyonu", "en": "F4.6 — 4h replication"},
    "stage.f46r.desc": {
        "tr": (
            "Eşleştirmeli gölgeden sonra İKİ zaman diliminde de aynı yönde anlamlı "
            "kalan: {cells}. Tek dilimde kalan etki bulgu değildir (replikasyon kuralı)."
        ),
        "en": (
            "Significant in the same direction on BOTH timeframes after the matched "
            "shadow: {cells}. An effect on one timeframe only is not a finding "
            "(replication rule)."
        ),
    },
    "stage.f47": {
        "tr": "F4.7 — zaman dilimi çaprazlaması",
        "en": "F4.7 — timeframe cross-check",
    },
    "stage.f47.robust": {
        "tr": (
            " Bu sayı tek bir null çekilişinindir; {seeds} çekilişin hepsinde replike "
            "eden: {cells} (tohum kararlılığı tablosu)."
        ),
        "en": (
            " This count comes from a single null draw; replicated in all {seeds} "
            "draws: {cells} (see the seed-stability table)."
        ),
    },
    "stage.f47.desc": {
        "tr": (
            "Aynı 56 test 1d ve 4h'de ayrı ayrı koşuldu. Sayılan: iki dilimde de "
            "AYNI YÖNDE anlamlı çıkan hücreler — {cells}. Bu hücreler F4.6'da "
            "momentum vekili olup olmadıkları için ayrıca sınanır."
        ),
        "en": (
            "The same 56 tests were run separately on 1d and 4h. Counted: cells "
            "significant in the SAME DIRECTION on both — {cells}. These cells are "
            "then tested in F4.6 for being momentum proxies."
        ),
    },
    "methodology": {
        "tr": (
            "Aylık kesitsel likidite filtresi (üst %40), takvim ayı bloklu bootstrap, "
            "Bonferroni çoğul test düzeltmesi (m={m}) ve ön-getiri eşleştirmeli gölge "
            "dağılım (±{band}σ). Bariyerler ATR tabanlıdır; aynı barda TP ve SL "
            "çarpıldığında SL varsayılır."
        ),
        "en": (
            "Monthly cross-sectional liquidity filter (top 40%), calendar-month block "
            "bootstrap, Bonferroni multiple-test correction (m={m}) and a return-matched "
            "shadow distribution (±{band}σ). Barriers are ATR-based; when TP and SL are "
            "hit on the same bar, SL is assumed."
        ),
    },
}


def t(key: str, lang: Lang = DEFAULT_LANG, **kwargs: object) -> str:
    """Katalogdan ileti. Bilinmeyen dil varsayılana düşer; bilinmeyen anahtar hatadır."""
    entry = MESSAGES[key]
    text = entry.get(lang) or entry[DEFAULT_LANG]
    return text.format(**kwargs) if kwargs else text
