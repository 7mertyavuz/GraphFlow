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


# ---------------------------------------------------------------------------
# Yapısal imza — kural şablondan değil, SORGUDAN türer
# ---------------------------------------------------------------------------
#
# Yukarıdaki çapa mekanizması kuralı şablon meta-verisinden okur. Bunun iki
# sınırı ölçüldü:
#
#   1. Serbest çizimde meta-veri YOKTUR. Kullanıcı OBO çizdiğinde hiçbir
#      kısıt uygulanmıyordu — oysa ürünün yarısı serbest çizim.
#   2. Çapalar DTW hizalama yolundan okunuyor; yol güvenilmez olduğunda kural
#      da güvenilmez oluyor (ölçüldü: OBO'da ilk 12'nin yapıya uyanı 6'dan
#      4'e DÜŞÜYORDU).
#
# Yapısal imza her ikisini de çözer: kural, kullanıcının çizdiği şeklin
# kendisinden türetilir. Formasyon başına kod yoktur — K-04 aynen korunur,
# hatta saflaşır: artık şablon meta-verisi bile gerekmiyor.

from engine.config import STRUCTURE_EQUAL_TOL, STRUCTURE_PROMINENCE  # noqa: E402


def prominent_extrema(y: np.ndarray, prominence: float) -> tuple[list[int], list[int]]:
    """Belirginliği eşiği aşan yerel tepe ve dip indeksleri.

    Belirginlik: uçtan, kendisinden daha uç bir noktaya varana kadar iki
    yönde kat edilen en küçük mesafe. Eşik olarak *sayı* değil *belirginlik*
    kullanılır: 32 noktalık z-score'lu pencerede onlarca minik salınım vardır,
    hepsini saymak her pencereyi "çok tepeli" ilan ederdi.
    """
    y = np.asarray(y, dtype=np.float64)
    peaks: list[int] = []
    troughs: list[int] = []

    for i in range(1, y.size - 1):
        left, right = y[:i], y[i + 1 :]
        if y[i] >= y[i - 1] and y[i] > y[i + 1]:
            higher_l, higher_r = left[left > y[i]], right[right > y[i]]
            base_l = left[np.argmax(left > y[i]) :].min() if higher_l.size else left.min()
            base_r = right[: np.argmax(right > y[i]) + 1].min() if higher_r.size else right.min()
            if y[i] - max(base_l, base_r) >= prominence:
                peaks.append(i)
        elif y[i] <= y[i - 1] and y[i] < y[i + 1]:
            lower_l, lower_r = left[left < y[i]], right[right < y[i]]
            base_l = left[np.argmax(left < y[i]) :].max() if lower_l.size else left.max()
            base_r = right[: np.argmax(right < y[i]) + 1].max() if lower_r.size else right.max()
            if min(base_l, base_r) - y[i] >= prominence:
                troughs.append(i)

    return peaks, troughs


def dominant_side(y: np.ndarray, prominence: float = STRUCTURE_PROMINENCE) -> int:
    """Şeklin yapısını hangi uçlar taşıyor: tepeler (+1) mi dipler (-1) mi.

    Taraf **yalnız sorgudan** belirlenir ve adaylar hep o tarafta sınanır.
    Adayın kendi sayılarına bakmak kırılganlıktı: tepe ve dip sayısı eşit
    olan şekillerde (üçgenler, takozlar) küçük bir fark tarafı çeviriyor ve
    aday haksız yere eleniyordu — ölçüldü, yükselen üçgen 431 eşleşmeden
    18'e düşüyordu; taraf sabitlenince 47'ye çıktı, dört formasyonun
    doğruluğu ise %100'de kaldı.
    """
    peaks, troughs = prominent_extrema(y, prominence)
    return 1 if len(peaks) >= len(troughs) else -1


def side_signature(
    y: np.ndarray,
    side: int,
    prominence: float = STRUCTURE_PROMINENCE,
    tol: float = STRUCTURE_EQUAL_TOL,
) -> tuple | None:
    """Verilen taraftaki uçların yapısal kimliği. Uç yoksa ``None``.

    Dört bileşen, hiçbiri formasyona özel değil:

    ``count``           kaç belirgin uç var
    ``extreme``         en uç olanın kaçıncı sırada olduğu
    ``all_similar``     uçların HEPSİ birbirine yakın mı (ikili tepe: evet)
    ``others_similar``  en uç dışındakiler birbirine yakın mı (OBO omuzları)

    Son iki bileşen ayrı ayrı gerekli. ``all_similar`` olmadan "bir yüksek,
    bir cılız tepe" ikili tepe sayılıyordu (ölçüldü: 12'de 4 doğru).
    ``others_similar`` olmadan OBO'nun omuz eşitliği kaybolurdu.
    """
    y = np.asarray(y, dtype=np.float64)
    peaks, troughs = prominent_extrema(y, prominence)
    indices = peaks if side > 0 else troughs
    if not indices:
        return None

    values = [float(y[i]) for i in indices]
    extreme = int(np.argmax(values)) if side > 0 else int(np.argmin(values))
    others = [v for j, v in enumerate(values) if j != extreme]

    all_similar = bool(max(values) - min(values) <= tol)
    others_similar = bool(max(others) - min(others) <= tol) if len(others) > 1 else True
    return (len(indices), extreme, all_similar, others_similar)


def structural_signature(
    y: np.ndarray,
    prominence: float = STRUCTURE_PROMINENCE,
    tol: float = STRUCTURE_EQUAL_TOL,
) -> tuple | None:
    """Şeklin kendi baskın tarafındaki yapısal kimliği (taraf dahil)."""
    side = dominant_side(y, prominence)
    signature = side_signature(y, side, prominence, tol)
    return None if signature is None else (side, *signature)


def signature_mask(
    query: np.ndarray,
    vectors: np.ndarray,
    prominence: float = STRUCTURE_PROMINENCE,
    tol: float = STRUCTURE_EQUAL_TOL,
) -> np.ndarray | None:
    """Sorgunun yapısal imzasını taşıyan adayların maskesi.

    Sorgunun belirgin ucu yoksa (düz rampa, tek yönlü trend) ``None`` döner
    ve filtre uygulanmaz — böyle bir şeklin "yapısı" yoktur, uydurulmaz.

    **İmza tam formasyon kimliği değildir**, uç düzenidir: yükselen üçgen ile
    ikili tepe aynı imzayı taşır (2 benzer tepe). Ayrımı DTW mesafesi yapar;
    bu katman yalnızca "yükseliş-tümsek-düşüş" yakalayıp omuz-baş-omuz olup
    olmadığını sormamayı engeller.
    """
    side = dominant_side(query, prominence)
    target = side_signature(query, side, prominence, tol)
    if target is None:
        return None
    return np.fromiter(
        (side_signature(v, side, prominence, tol) == target for v in vectors),
        dtype=bool,
        count=len(vectors),
    )
