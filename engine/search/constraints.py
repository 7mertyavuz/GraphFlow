"""Çapa tabanlı geometrik kısıt katmanı — K-04'ün korunarak genişletilmesi.

**Sorun (F3 göz testinde ölçüldü):** DTW noktaları *hizalar*, hizalanan
noktaların **seviyelerinin** mantıklı olup olmadığını umursamaz. OBO
sorgusunda yuvarlak tepelerin sızması bundandır: "yükseliş–tümsek–düşüş"
yakalanır, ama omuz–baş arasındaki iki dibin aynı seviyede olup olmadığına
(boyun çizgisi) bakılmaz.

**K-04 nasıl korunuyor:** Formasyon başına ``if-else`` yazılmaz. Kural,
koda değil **şablon meta-verisine** yazılır; burada tek bir genel
değerlendirici vardır. ``constraints`` alanı olmayan şablon hiçbir ek
filtreden geçmez → mevcut davranış korunur.

**Çapalar nereden okunur:** Ayrı bir tepe/dip sezgiseli yazılmaz. Elimizde
zaten DTW hizalama yolu var — kanonik şablonun *i*. noktasının aday
penceredeki hangi noktaya hizalandığını biliyoruz. Seviyeler oradan okunur.

Kısıt türleri:

``level_match``
    Belirtilen çapaların seviyeleri birbirine yakın olmalı
    (``max_diff``, z-score birimi → ölçek-değişmez).
``level_order``
    Çapaların seviyeleri verilen sırayı sağlamalı (``["<", ">"]`` gibi).
"""

from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np

from engine.config import SAKOE_CHIBA_RADIUS
from engine.search.ddtw import warping_path


def anchor_levels(
    query: np.ndarray,
    candidate: np.ndarray,
    anchors: Sequence[int],
    radius: int = SAKOE_CHIBA_RADIUS,
    path: np.ndarray | None = None,
) -> np.ndarray:
    """Şablonun ``anchors`` noktalarının aday penceredeki seviyeleri.

    Hizalama yolu türev uzayında kurulduğu için indeksler bir kayıktır
    (``D[i] ↔ x[i+1]``); dönüşüm burada tek yerde yapılır.
    """
    q = np.asarray(query, dtype=np.float64)
    c = np.asarray(candidate, dtype=np.float64)
    path = warping_path(q, c, radius) if path is None else path

    # Şablon noktası → aday noktaları (birden fazla olabilir; ortalaması alınır)
    mapping: dict[int, list[int]] = {}
    for qi, cj in path:
        mapping.setdefault(int(qi) + 1, []).append(int(cj) + 1)

    levels = np.empty(len(anchors), dtype=np.float64)
    for k, a in enumerate(anchors):
        targets = mapping.get(int(a))
        if not targets:  # bant dışında kaldıysa aynı indeks
            targets = [int(np.clip(a, 0, c.size - 1))]
        levels[k] = float(np.mean(c[np.clip(targets, 0, c.size - 1)]))
    return levels


def check_constraint(levels: np.ndarray, rule: dict) -> bool:
    kind = rule.get("type")

    if kind == "level_match":
        return float(np.max(levels) - np.min(levels)) <= float(rule["max_diff"])

    if kind == "level_order":
        order = rule["order"]
        if len(order) != len(levels) - 1:
            raise ValueError("level_order: 'order' uzunluğu çapa sayısı - 1 olmalı")
        for i, op in enumerate(order):
            if op == "<" and not levels[i] < levels[i + 1]:
                return False
            if op == ">" and not levels[i] > levels[i + 1]:
                return False
        return True

    raise ValueError(f"bilinmeyen kısıt türü: {kind}")


def passes(
    query: np.ndarray,
    candidate: np.ndarray,
    constraints: Iterable[dict] | None,
    radius: int = SAKOE_CHIBA_RADIUS,
) -> bool:
    """Aday, şablonun tüm geometrik kısıtlarını sağlıyor mu?"""
    rules = list(constraints or [])
    if not rules:
        return True  # kısıtsız şablon → mevcut davranış

    path = warping_path(np.asarray(query, dtype=np.float64), np.asarray(candidate, dtype=np.float64), radius)
    for rule in rules:
        levels = anchor_levels(query, candidate, rule["anchors"], radius, path)
        if not check_constraint(levels, rule):
            return False
    return True


def filter_candidates(
    query: np.ndarray,
    vectors: np.ndarray,
    constraints: Iterable[dict] | None,
    radius: int = SAKOE_CHIBA_RADIUS,
) -> np.ndarray:
    """(n,) bool maske — hangi adaylar kısıtları geçiyor."""
    rules = list(constraints or [])
    if not rules:
        return np.ones(len(vectors), dtype=bool)
    return np.fromiter(
        (passes(query, v, rules, radius) for v in vectors), dtype=bool, count=len(vectors)
    )
