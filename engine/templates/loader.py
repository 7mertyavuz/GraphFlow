"""Şablon kütüphanesi yükleyicisi (docs/01-mimari.md §7, K-04).

Şablonlar JSON dosyalarıdır ve **aynı z-score normalizasyonundan** geçirilir:
kütüphaneden "OBO" seçmek ile aynı şekli kanvasa çizmek motor açısından
birebir aynı yoldur. Kural motoru yoktur; tutarsız iki sonuç listesi
üretilemez.

``points`` fiyat mantığında verilir (büyük değer = yüksek fiyat), bu yüzden
kanvasın y-ters çevirme adımı **uygulanmaz**. Log adımı da uygulanmaz —
şablon zaten şekil uzayındadır (bkz. §3, çizim yolu).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from engine.config import N_POINTS, TEMPLATE_DIR
from engine.normalize.pipeline import normalize_drawing

REQUIRED_FIELDS = ("id", "name_tr", "category", "points")


@dataclass(frozen=True)
class Template:
    id: str
    name_tr: str
    name_en: str
    category: str
    bias: str
    points: np.ndarray  # ham (şekil uzayı)
    vector: np.ndarray  # (32,) z-score'lu — motora giden
    icon: str = ""
    description_tr: str = ""

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name_tr": self.name_tr,
            "name_en": self.name_en,
            "category": self.category,
            "bias": self.bias,
            "points": [round(float(v), 6) for v in self.points],
            "icon": self.icon,
            "description_tr": self.description_tr,
        }


def _from_payload(payload: dict) -> Template:
    missing = [f for f in REQUIRED_FIELDS if f not in payload]
    if missing:
        raise ValueError(f"şablon alanları eksik: {missing}")

    points = np.asarray(payload["points"], dtype=np.float64)
    vector = normalize_drawing(points, n=N_POINTS, invert_y=False)
    if vector is None:
        raise ValueError(f"şablon düz: {payload['id']}")

    return Template(
        id=payload["id"],
        name_tr=payload["name_tr"],
        name_en=payload.get("name_en", payload["name_tr"]),
        category=payload["category"],
        bias=payload.get("bias", "neutral"),
        points=points,
        vector=vector,
        icon=payload.get("icon", ""),
        description_tr=payload.get("description_tr", ""),
    )


def load_file(path: Path) -> Template:
    return _from_payload(json.loads(Path(path).read_text(encoding="utf-8")))


def load_all(directory: Path | None = None) -> dict[str, Template]:
    """Kategori alt dizinlerindeki tüm şablonları yükler."""
    directory = Path(directory or TEMPLATE_DIR)
    out: dict[str, Template] = {}
    for path in sorted(directory.rglob("*.json")):
        template = load_file(path)
        out[template.id] = template
    return out


@lru_cache(maxsize=1)
def _cached_library() -> dict[str, Template]:
    return load_all()


def get(template_id: str) -> Template:
    """Kütüphaneden tek şablon (önbellekli)."""
    library = _cached_library()
    if template_id not in library:
        raise KeyError(f"bilinmeyen şablon: {template_id}")
    return library[template_id]


def list_templates() -> list[dict]:
    """API'nin ``GET /api/templates`` yanıtı için hafif liste."""
    return [t.as_dict() for t in _cached_library().values()]
