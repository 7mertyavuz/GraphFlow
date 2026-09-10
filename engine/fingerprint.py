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

#: Örneklemi doğrudan belirleyen sabitler. Anlık görüntüsü raporlanır;
#: karşılaştırmayı yapan asıl şey davranış özetidir.
SAMPLE_CONFIG_KEYS: tuple[str, ...] = (
    "STAGE2_METRIC",
    "STAGE1_TOPK",
    "STAGE2_TOPK",
    "SAKOE_CHIBA_RADIUS",
    "OUTCOME_TOLERANCE",
    "SEARCH_CACHE_MATCHES",
    "STRUCTURE_FILTER",
    "STRUCTURE_STABILITY_GATE",
    "STRUCTURE_MIN_STABILITY",
    "STRUCTURE_PROMINENCE",
    "STRUCTURE_EQUAL_TOL",
    "ENVELOPE_FILTER",
    "ENVELOPE_MIN_STABILITY",
    "ENVELOPE_SLOPE_THRESHOLD",
    "ENVELOPE_DEAD_BAND",
    "POST_NMS_IOU",
    "MAX_RESULTS_PER_SYMBOL",
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
        signature_mask,
        signature_stability,
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
        ]
        smask = signature_mask(q, probe)
        emask = envelope_mask(q, probe)
        parts.append("-" if smask is None else np.packbits(smask).tobytes().hex())
        parts.append("-" if emask is None else np.packbits(emask).tobytes().hex())
        # Aşama 2: yuvarlama, platformlar arası kayan nokta gürültüsünü
        # "farklı motor" sanmamak için.
        scores = stage2_scores(q, probe, config.SAKOE_CHIBA_RADIUS, config.STAGE2_METRIC)
        parts.append(np.round(scores, 6).tobytes().hex())
        h.update("|".join(parts).encode())
    return h.hexdigest()[:16]


@lru_cache(maxsize=1)
def engine_fingerprint() -> dict:
    """``{"behavior": <16 hane>, "config": {...}}`` — süreç ömrü boyunca önbellekli."""
    return {"behavior": _behavior_digest(), "config": _config_snapshot()}


def compare(stored: dict | None) -> tuple[bool | None, str | None]:
    """Kayıtlı parmak izi bugünkü motorla uyuşuyor mu.

    ``(None, neden)`` — dosyada parmak izi yok (bu mekanizmadan önce
    üretilmiş); bilinmiyor, ama "uyuşuyor" da denemez.
    ``(False, neden)`` — farklı motor. Değişen sabitler varsa adlarıyla.
    """
    if not stored or "behavior" not in stored:
        return None, "Ölçüm dosyası motor parmak izi taşımıyor (bu mekanizmadan önce üretilmiş)."

    current = engine_fingerprint()
    if stored["behavior"] == current["behavior"]:
        return True, None

    old_cfg = stored.get("config") or {}
    changed = sorted(
        k for k in SAMPLE_CONFIG_KEYS if old_cfg.get(k) != current["config"].get(k)
    )
    if changed:
        return False, "Motor değişti; farklı sabitler: " + ", ".join(changed) + "."
    return False, "Motor değişti (sabitler aynı — bir filtre ya da metrik kodu değişmiş)."


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
