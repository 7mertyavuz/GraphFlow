"""Örneklemi belirleyen motor davranışının parmak izi.

**Neden var.** ``data/f3`` altındaki ölçüm dosyaları (``/api/findings`` ve
docs/05–09 tablolarının dayanağı) bir kez üretilir ve motor değiştikçe
sessizce bayatlar. Eylül 2026'da tam olarak bu oldu: kararlılık kapısı
(K-20), zarf filtresi (K-21) ve belirginlik ayna düzeltmesi aynı gün
bağlandı; üçü de istatistiğe giren pencere kümesini değiştirdi (yükselen
üçgen 89 → 272 eşleşme). "Bulgular" sayfası ise önceki günün motorunun
istatistiğini göstermeye devam ediyordu — ve bunu söyleyecek hiçbir şey
yoktu.

**Neden config değil davranış.** Ayna düzeltmesi hiçbir sabiti
değiştirmedi; yalnız bir fonksiyonun gövdesini. Sabitlerin anlık görüntüsü
o değişikliği göremezdi. Parmak izi bu yüzden filtre katmanlarını ve Aşama 2
metriğini **sabit girdilerde çalıştırır** ve çıktıyı özetler: kod ya da
sabit fark etmez, örneklemi değiştiren her şey özeti değiştirir.

Kapsam bilinçli olarak dar: örneklemi belirleyen katmanlar (yapısal imza,
zarf imzası, kararlılık kapıları, Aşama 2 mesafesi) ve onları ayarlayan
sabitler. Korpusun kendisi (yeni bar, yeni sembol) parmak izine girmez —
o, ölçüm dosyasında ``data_as_of`` olarak ayrıca taşınır, çünkü korpusun
her gün büyümesi "başka bir motor" değil "daha yeni veri" demektir.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache

import numpy as np

from engine import config

#: Örneklemi doğrudan belirleyen sabitler. Hem raporlanır HEM özete girer.
#:
#: Eskiden yalnız raporlanıyordu ve eşleşme kararı yalnız davranış sondasına
#: bakıyordu: sondanın çalıştırmadığı bir sabiti (ör. yüzdelik eşikler)
#: değiştirmek fark edilmezdi.
SAMPLE_CONFIG_KEYS: tuple[str, ...] = (
    # Aşama 1-2 ve eşikler
    "STAGE2_METRIC",
    "STAGE1_TOPK",
    "STAGE2_TOPK",
    "SAKOE_CHIBA_RADIUS",
    "TOLERANCE_THRESHOLDS_BY_METRIC",
    "NULL_PERCENTILES",
    "NULL_SAMPLE_SIZE",
    "NULL_SEED",
    "NULL_MIN_SAMPLES",
    "OUTCOME_TOLERANCE",
    "WINDOW_LENGTHS",
    "DEFAULT_MIN_AMPLITUDE",
    # NMS ve örneklem
    "PRE_NMS_IOU",
    "POST_NMS_IOU",
    "MAX_RESULTS_PER_SYMBOL",
    "SEARCH_CACHE_MATCHES",
    "MIN_EVENTS_FOR_CLAIM",
    # Yapısal imza ve kapısı
    "STRUCTURE_FILTER",
    "STRUCTURE_STABILITY_GATE",
    "STRUCTURE_MIN_STABILITY",
    "STRUCTURE_PROMINENCE",
    "STRUCTURE_EQUAL_TOL",
    "STRUCTURE_MIN_SURVIVORS",
    "STRUCTURE_NOISE_SIGMA",
    "STRUCTURE_STABILITY_DRAWS",
    "STRUCTURE_STABILITY_SEED",
    "STRUCTURE_YIELDS_TO_ENVELOPE",
    # Zarf imzası ve kapısı
    "ENVELOPE_FILTER",
    "ENVELOPE_MIN_STABILITY",
    "ENVELOPE_SLOPE_THRESHOLD",
    "ENVELOPE_DEAD_BAND",
    "ENVELOPE_TOUCH_WIDTH",
    "ENVELOPE_MIN_SURVIVORS",
    # İki rejimli (direk + gövde) zarf imzası (K-22) ve yeniden sıralama (K-23)
    "REGIME_FILTER",
    "REGIME_POLE_K",
    "REGIME_BODY_START",
    "REGIME_POLE_HEIGHT",
    "REGIME_POLE_STRICT_HEIGHT",
    "REGIME_SLOPE_THRESHOLD",
    "REGIME_CONVERGENCE",
    "REGIME_MIN_STABILITY",
    "REGIME_MIN_SURVIVORS",
    "STRUCTURAL_RERANK",
)

#: Davranış sondası için sabit tohum ve boyut. Değiştirilirse tüm eski
#: ölçüm dosyaları "farklı motor" görünür — bu yüzden sabittir.
_PROBE_SEED = 20260910
_PROBE_ROWS = 96


def _config_snapshot() -> dict:
    snap: dict = {}
    for key in SAMPLE_CONFIG_KEYS:
        value = getattr(config, key, None)
        if isinstance(value, dict):
            value = {str(k): v for k, v in sorted(value.items())}
        snap[key] = value
    return snap


def _behavior_digest() -> str:
    """Filtre katmanlarının ve Aşama 2'nin sabit girdilerdeki çıktısının özeti."""
    from engine.search.constraints import (
        envelope_mask,
        envelope_signature,
        envelope_stability,
        filter_plan,
        pole_body_mask,
        pole_body_signature,
        pole_body_stability,
        signature_mask,
        signature_stability,
        structural_alignment_penalty,
        structural_signature,
    )
    from engine.search.ddtw import stage2_scores
    from engine.templates import load_all

    rng = np.random.default_rng(_PROBE_SEED)
    probe = rng.normal(size=(_PROBE_ROWS, config.N_POINTS))
    probe = (probe - probe.mean(axis=1, keepdims=True)) / probe.std(axis=1, keepdims=True)

    h = hashlib.sha256()
    for template_id, template in sorted(load_all().items()):
        q = np.asarray(template.vector, dtype=np.float64)
        parts = [
            template_id,
            repr(structural_signature(q)),
            f"{signature_stability(q):.4f}",
            repr(envelope_signature(q, strict=True)),
            f"{envelope_stability(q):.4f}",
            repr(pole_body_signature(q, strict=True)),
            f"{pole_body_stability(q):.4f}",
        ]
        # Orkestrasyon: hangi katman uygulanacak. Bu satır yokken "yapısal
        # filtre, zarf devredeyken çekilir" kuralı varsayılan davranışı
        # değiştirdi ama parmak izi aynı kaldı — sonda yapı taşlarını
        # sınıyordu, kararı değil. Argümanlar config'den ÇAĞRI anında okunur.
        plan = filter_plan(
            q,
            structure_filter=config.STRUCTURE_FILTER,
            structure_gate=config.STRUCTURE_STABILITY_GATE,
            envelope_filter=config.ENVELOPE_FILTER,
            structure_yields=config.STRUCTURE_YIELDS_TO_ENVELOPE,
            regime_filter=config.REGIME_FILTER,
        )
        parts.append(
            f"{plan.apply_structure}{plan.apply_envelope}{plan.apply_regime}{plan.structure_stable}"
        )
        smask = signature_mask(q, probe)
        emask = envelope_mask(q, probe)
        rmask = pole_body_mask(q, probe)
        parts.append("-" if smask is None else np.packbits(smask).tobytes().hex())
        parts.append("-" if emask is None else np.packbits(emask).tobytes().hex())
        parts.append("-" if rmask is None else np.packbits(rmask).tobytes().hex())
        pen = structural_alignment_penalty(
            q,
            probe,
            apply_structure=plan.apply_structure,
            apply_envelope=plan.apply_envelope,
            apply_regime=plan.apply_regime,
        )
        parts.append(np.round(pen, 6).tobytes().hex())
        # Aşama 2: yuvarlama, platformlar arası kayan nokta gürültüsünü
        # "farklı motor" sanmamak için.
        scores = stage2_scores(q, probe, config.SAKOE_CHIBA_RADIUS, config.STAGE2_METRIC)
        parts.append(np.round(scores, 6).tobytes().hex())
        h.update("|".join(parts).encode())
    # Null çekilişi: eşiği belirleyen örneklem. Çekiliş yöntemi satır
    # indeksinden pencere kimliğine geçtiğinde her sonuç değişti ama sonda
    # bunu görmüyordu — sabitler aynıydı (üçüncü kapsama deliği, docs/12).
    from engine.search.null_sample import null_sample

    sids = np.repeat(np.arange(40), 50)
    times = np.tile(np.arange(50, dtype=np.int64) * 86_400_000, 40)
    rows = null_sample(sids, times, sids % 3 != 0, 200, 64, config.NULL_SEED)
    h.update(rows.tobytes())
    # Sabitler de özete girer (yukarıdaki not).
    h.update(repr(sorted(_config_snapshot().items())).encode())
    return h.hexdigest()[:16]


@lru_cache(maxsize=1)
def engine_fingerprint() -> dict:
    """``{"behavior": <16 hane>, "config": {...}}`` — süreç ömrü boyunca önbellekli."""
    return {"behavior": _behavior_digest(), "config": _config_snapshot()}


def compare(stored: dict | None, lang: str = "tr") -> tuple[bool | None, str | None]:
    """Kayıtlı parmak izi bugünkü motorla uyuşuyor mu.

    ``(None, neden)`` — dosyada parmak izi yok (bu mekanizmadan önce
    üretilmiş); bilinmiyor, ama "uyuşuyor" da denemez.
    ``(False, neden)`` — farklı motor. Değişen sabitler varsa adlarıyla.
    """
    from engine.i18n import t

    if not stored or "behavior" not in stored:
        return None, t("prov.no_fingerprint", lang)  # type: ignore[arg-type]

    current = engine_fingerprint()
    if stored["behavior"] == current["behavior"]:
        return True, None

    old_cfg = stored.get("config") or {}
    changed = sorted(
        k for k in SAMPLE_CONFIG_KEYS if old_cfg.get(k) != current["config"].get(k)
    )
    if changed:
        return False, t("prov.config_changed", lang, keys=", ".join(changed))  # type: ignore[arg-type]
    return False, t("prov.code_changed", lang)  # type: ignore[arg-type]


def provenance(timeframe: str) -> dict:
    """Bir ölçüm dosyasının yanına yazılacak köken kaydı.

    ``fingerprint`` hangi motorun ölçtüğünü, ``data_as_of`` hangi veriyle
    ölçtüğünü söyler; ikisi ayrı sorulardır (modül belgesi).
    """
    from datetime import datetime, timezone

    from engine.api import freshness

    return {
        "fingerprint": engine_fingerprint(),
        "timeframe": timeframe,
        "data_as_of": freshness.data_as_of(timeframe),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
