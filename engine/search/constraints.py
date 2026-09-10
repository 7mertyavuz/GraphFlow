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

from engine.config import (  # noqa: E402
    STRUCTURE_EQUAL_TOL,
    STRUCTURE_NOISE_SIGMA,
    STRUCTURE_PROMINENCE,
    STRUCTURE_STABILITY_DRAWS,
    STRUCTURE_STABILITY_SEED,
)


def _nearest_left(flags: np.ndarray) -> int:
    """Solda koşulu sağlayan **en yakın** indeks; yoksa 0.

    Bu satır bir hatanın kaydıdır. Eskiden ``np.argmax(flags)`` yazıyordu ve
    o, en soldaki (en UZAK) noktayı veriyordu — sağ taraf ise en yakını
    kullanıyordu. Sonuç: belirginlik aynaya göre değişiyordu. Ölçüldü, 32
    noktalık rastgele pencerelerin **%83'ünde** şekil ile ayna görüntüsü
    farklı uç kümesi veriyordu. Şekil eşleştiren bir motor için bu
    savunulamaz; ders kitabı tanımı iki tarafta da en yakın noktadır.
    """
    hits = np.flatnonzero(flags)
    return int(hits[-1]) if hits.size else 0


def prominent_extrema(y: np.ndarray, prominence: float) -> tuple[list[int], list[int]]:
    """Belirginliği eşiği aşan yerel tepe ve dip indeksleri.

    Belirginlik: uçtan, **kendisinden daha uç en yakın noktaya** varana kadar
    iki yönde inilen en küçük derinlik. Eşik olarak *sayı* değil *belirginlik*
    kullanılır: 32 noktalık z-score'lu pencerede onlarca minik salınım vardır,
    hepsini saymak her pencereyi "çok tepeli" ilan ederdi.

    Simetriktir: ``prominent_extrema(y)`` ile ``prominent_extrema(y[::-1])``
    birbirinin aynası olmak zorundadır ve bunu bir test tutar.
    """
    y = np.asarray(y, dtype=np.float64)
    peaks: list[int] = []
    troughs: list[int] = []

    for i in range(1, y.size - 1):
        left, right = y[:i], y[i + 1 :]
        if y[i] >= y[i - 1] and y[i] > y[i + 1]:
            hl, hr = left > y[i], right > y[i]
            base_l = left[_nearest_left(hl) :].min() if hl.any() else left.min()
            base_r = right[: int(np.argmax(hr)) + 1].min() if hr.any() else right.min()
            if y[i] - max(base_l, base_r) >= prominence:
                peaks.append(i)
        elif y[i] <= y[i - 1] and y[i] < y[i + 1]:
            ll, lr = left < y[i], right < y[i]
            base_l = left[_nearest_left(ll) :].max() if ll.any() else left.max()
            base_r = right[: int(np.argmax(lr)) + 1].max() if lr.any() else right.max()
            if min(base_l, base_r) - y[i] >= prominence:
                troughs.append(i)

    return peaks, troughs


def prominent_extrema_batch(
    V: np.ndarray, prominence: float, chunk: int = 1024
) -> tuple[np.ndarray, np.ndarray]:
    """(m, n) bool maskeler: belirgin tepeler ve dipler.

    ``prominent_extrema``nın vektörize hâli — aday listesi üzerinde Python
    döngüsü yazılmaz (CONTRIBUTING.md). Ölçüldü: 2.500 aday 250 ms → 6 ms.

    n = 32 sabit olduğu için O(n²) tensör formülasyonu ucuzdur; satırlar yine
    de parçalanır, yoksa (m, 32, 32) float64 dizileri 20 MB'ı aşar.

    Tekil yolla eşdeğerliği testle tutulur: ayrışırlarsa filtre sessizce
    başka bir şey elemeye başlar.
    """
    V = np.atleast_2d(np.asarray(V, dtype=np.float64))
    m, n = V.shape
    peaks = np.zeros((m, n), dtype=bool)
    troughs = np.zeros((m, n), dtype=bool)

    idx = np.arange(n)
    is_left = idx[None, :] < idx[:, None]   # [i, j] → j < i
    is_right = idx[None, :] > idx[:, None]  # [i, j] → j > i

    for a in range(0, m, chunk):
        b = min(a + chunk, m)
        block = V[a:b]
        higher = block[:, None, :] > block[:, :, None]
        lower = block[:, None, :] < block[:, :, None]

        for is_peak, cmp_ in ((True, higher), (False, lower)):
            # İki tarafta da EN YAKIN uç nokta — ayna simetrisi buna bağlı.
            cl = cmp_ & is_left
            cr = cmp_ & is_right
            has_l, has_r = cl.any(-1), cr.any(-1)
            left_stop = np.where(has_l, n - 1 - cl[:, :, ::-1].argmax(-1), 0)
            right_stop = np.where(has_r, cr.argmax(-1), n - 1)

            span_l = (idx[None, None, :] >= left_stop[:, :, None]) & is_left[None]
            span_r = (idx[None, None, :] <= right_stop[:, :, None]) & is_right[None]

            if is_peak:
                base_l = np.where(span_l, block[:, None, :], np.inf).min(-1)
                base_r = np.where(span_r, block[:, None, :], np.inf).min(-1)
                prom = block - np.maximum(base_l, base_r)
                local = np.zeros((b - a, n), dtype=bool)
                local[:, 1:-1] = (block[:, 1:-1] >= block[:, :-2]) & (block[:, 1:-1] > block[:, 2:])
                peaks[a:b] = local & (prom >= prominence)
            else:
                base_l = np.where(span_l, block[:, None, :], -np.inf).max(-1)
                base_r = np.where(span_r, block[:, None, :], -np.inf).max(-1)
                prom = np.minimum(base_l, base_r) - block
                local = np.zeros((b - a, n), dtype=bool)
                local[:, 1:-1] = (block[:, 1:-1] <= block[:, :-2]) & (block[:, 1:-1] < block[:, 2:])
                troughs[a:b] = local & (prom >= prominence)

    return peaks, troughs


def side_signature_batch(
    V: np.ndarray,
    side: int,
    prominence: float = STRUCTURE_PROMINENCE,
    tol: float = STRUCTURE_EQUAL_TOL,
) -> np.ndarray:
    """(m, 4) int16 imza dizisi; o tarafta uç yoksa satır ``-1``.

    Sütunlar ``side_signature`` ile birebir: (sayı, en uç olanın sırası,
    hepsi benzer mi, diğerleri benzer mi).
    """
    V = np.atleast_2d(np.asarray(V, dtype=np.float64))
    peaks, troughs = prominent_extrema_batch(V, prominence)
    mask = peaks if side > 0 else troughs

    count = mask.sum(axis=1)
    out = np.full((V.shape[0], 4), -1, dtype=np.int16)
    present = count > 0
    if not present.any():
        return out

    signed = V if side > 0 else -V
    hi = np.where(mask, signed, -np.inf)
    lo = np.where(mask, signed, np.inf)

    # En uç olanın SIRASI (kaçıncı uç), sütun indeksi değil.
    col = hi.argmax(axis=1)
    rank = np.take_along_axis(np.cumsum(mask, axis=1), col[:, None], axis=1)[:, 0] - 1

    all_similar = (hi.max(axis=1) - lo.min(axis=1)) <= tol

    rest = mask.copy()
    rest[np.arange(V.shape[0]), col] = False
    rest_n = rest.sum(axis=1)
    rest_hi = np.where(rest, signed, -np.inf).max(axis=1)
    rest_lo = np.where(rest, signed, np.inf).min(axis=1)
    others_similar = np.where(rest_n > 1, (rest_hi - rest_lo) <= tol, True)

    out[present, 0] = count[present]
    out[present, 1] = rank[present]
    out[present, 2] = all_similar[present]
    out[present, 3] = others_similar[present]
    return out


def dominant_side(y: np.ndarray, prominence: float = STRUCTURE_PROMINENCE) -> int:
    """Şeklin yapısını hangi uçlar taşıyor: tepeler (+1) mi dipler (-1) mi.

    Taraf **yalnız sorgudan** belirlenir ve adaylar hep o tarafta sınanır.
    Adayın kendi sayılarına bakmak kırılganlıktı: tepe ve dip sayısı eşit
    olan şekillerde (üçgenler, takozlar) küçük bir fark tarafı çeviriyor ve
    aday haksız yere eleniyordu — ölçüldü, yükselen üçgen 431 eşleşmeden
    18'e düşüyordu; taraf sabitlenince 47'ye çıktı, dört formasyonun
    doğruluğu ise %100'de kaldı.

    Eşitlikte (tepe sayısı = dip sayısı) yapıyı **daha belirgin uç** taşır.
    Eskiden eşitlik kuralı ``>=`` idi, yani eşitlikte her zaman tepeler —
    şekil ters çevrilse bile. Ölçüldü: rastgele pencerelerin %50'si eşitlik
    durumunda ve hepsinde ``structural_signature(-y)`` ile
    ``structural_signature(y)`` birbirinin çevrilmişi değildi. Somut sonucu:
    yükselen üçgenin dikey çevrilmişi alçalan üçgenin ta kendisidir, ama
    motor birini yatay direncinden (kararlılık %36), ötekini eğimli
    tepelerinden (%81) okuyordu — birbirinin aynası iki formasyon farklı
    muamele görüyordu.

    Belirginlikler de eşitse hiçbir taraf baskın değildir: ``0`` döner ve
    yapı uydurulmaz. Yazı-tura atan bir kural, çevrilince tura atar.
    """
    peaks, troughs = prominent_extrema(y, prominence)
    if len(peaks) != len(troughs):
        return 1 if len(peaks) > len(troughs) else -1
    y = np.asarray(y, dtype=np.float64)
    top = max((_prominence_at(y, i, peak=True) for i in peaks), default=0.0)
    bottom = max((_prominence_at(y, i, peak=False) for i in troughs), default=0.0)
    if abs(top - bottom) <= 1e-9:
        return 0
    return 1 if top > bottom else -1


def _prominence_at(y: np.ndarray, i: int, peak: bool) -> float:
    """``prominent_extrema`` ile birebir aynı tanımla tek bir ucun belirginliği."""
    left, right = y[:i], y[i + 1 :]
    if peak:
        hl, hr = left > y[i], right > y[i]
        base_l = left[_nearest_left(hl) :].min() if hl.any() else left.min()
        base_r = right[: int(np.argmax(hr)) + 1].min() if hr.any() else right.min()
        return float(y[i] - max(base_l, base_r))
    ll, lr = left < y[i], right < y[i]
    base_l = left[_nearest_left(ll) :].max() if ll.any() else left.max()
    base_r = right[: int(np.argmax(lr)) + 1].max() if lr.any() else right.max()
    return float(min(base_l, base_r) - y[i])


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
    if side == 0:
        return None
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
    if side == 0:  # hiçbir taraf baskın değil — kural uydurulmaz
        return None
    target = side_signature(query, side, prominence, tol)
    if target is None:
        return None
    sig = side_signature_batch(np.asarray(vectors, dtype=np.float64), side, prominence, tol)
    return (sig == np.asarray(target, dtype=np.int16)).all(axis=1)


def signature_stability(
    y: np.ndarray,
    sigma: float = STRUCTURE_NOISE_SIGMA,
    draws: int = STRUCTURE_STABILITY_DRAWS,
    prominence: float = STRUCTURE_PROMINENCE,
    tol: float = STRUCTURE_EQUAL_TOL,
) -> float:
    """İmza, sorgunun kendisine eklenen gürültüye ne kadar dayanıyor (0–1).

    **Neden gerekli:** İmza uç *düzenini* okur. Bazı formasyonları tanımlayan
    şey uç düzeni değil **eğimdir** — yükselen üçgeni yatay direnç ile
    yükselen dipler tanımlar, "iki tepe" değil. Böyle bir şekilde imza
    kararsızdır: küçük bir gürültü uç sayısını değiştirir. Kararsız bir
    özelliği adaylarda *aynen* aramak, yapıya göre değil gürültüye göre
    elemektir.

    Ölçüldü (σ=0,10, 400 çekim) — OBO %98 · ters OBO %96 · ikili tepe %94 ·
    ikili dip %94 · boğa bayrağı %92 · ayı bayrağı %91 ‖ simetrik üçgen %75 ·
    düşen takoz %74 · alçalan üçgen %72 · yükselen takoz %62 · yükselen üçgen
    %42 · flama %16. İki küme arasında %75–%91 bandı boştur; eşik oraya
    konur, kenarına değil.

    Tohum sabittir: arama yeniden üretilebilir olmalı (``tools/run_outcomes``
    aynı sorguyu iki kez koşup aynı olay kümesini beklerse, rastgele bir
    kapı bunu sessizce bozardı).
    """
    y = np.asarray(y, dtype=np.float64)
    base = structural_signature(y, prominence, tol)
    if base is None:
        return 0.0
    rng = np.random.default_rng(STRUCTURE_STABILITY_SEED)
    noise = rng.normal(scale=sigma, size=(draws, y.size))
    hits = sum(
        structural_signature(y + noise[k], prominence, tol) == base for k in range(draws)
    )
    return hits / draws


# ---------------------------------------------------------------------------
# Zarf imzası — eğimle tanımlı formasyonlar için
# ---------------------------------------------------------------------------
#
# Yapısal imza uç DÜZENİNİ okur ve dönüş formasyonlarında belirleyicidir
# (ilk 50'de %99 vs %28). Eğimle tanımlı formasyonlarda ise etkisizdir
# (%49 vs %50, K-20): yükselen üçgeni "iki tepe" değil, yatay direnç +
# yükselen dipler tanımlar.
#
# Ground truth ölçümü sorunun nerede olduğunu gösterdi (tools/gt_benchmark):
# aynı sentetik korpusta gürültü sembolü 40 → 120 → 300 yapıldığında
# DUYARLILIK sabit kaldı (%58) ama KESİNLİK %88 → %65 → %58'e düştü. Motor
# enjekte edilen üçgenleri her yoğunlukta aynı oranda buluyor; kaybettiği
# yer sıralama — havuz büyüdükçe "DTW'ye yakın ama üçgen değil" pencereler
# gerçek olanların üstüne çıkıyor. Gerçek korpusun yoğunluğunda (11,6M
# pencere) ölçülen %34 bu eğrinin devamıdır.
#
# Bu katman o sahtekârları eler. Kural yine SORGUDAN türer; formasyon başına
# kod yoktur (K-04).

from engine.config import (  # noqa: E402
    ENVELOPE_DEAD_BAND,
    ENVELOPE_SLOPE_THRESHOLD,
    ENVELOPE_TOUCH_WIDTH,
)


def envelope_touches(
    y: np.ndarray, width: int = ENVELOPE_TOUCH_WIDTH
) -> tuple[list[int], list[int]]:
    """Üst ve alt zarfa dokunan **iç** noktalar.

    Uçlar dışlanır: pencerenin ilk ve son barı bir dönüş noktası değil,
    verinin kesildiği yerdir. Ölçüldü — uçlar dahilken simetrik üçgenin alt
    zarfı -0,47 (düşen dipler) okunuyor, iç noktalarla +2,18 (yükselen).
    """
    y = np.asarray(y, dtype=np.float64)
    n = y.size
    highs: list[int] = []
    lows: list[int] = []
    for i in range(1, n - 1):
        a, b = max(0, i - width), min(n, i + width + 1)
        if y[i] >= y[a:b].max() - 1e-12 and (y[i] > y[i - 1] or y[i] > y[i + 1]):
            highs.append(i)
        if y[i] <= y[a:b].min() + 1e-12 and (y[i] < y[i - 1] or y[i] < y[i + 1]):
            lows.append(i)
    return highs, lows


def envelope_slopes(y: np.ndarray) -> tuple[float | None, float | None]:
    """(üst zarf eğimi, alt zarf eğimi). İki dokunuştan az ise ``None``.

    Eğim z birimi / tam pencere cinsindendir; pencere z-score'lu olduğu için
    ölçek-değişmezdir (K-02).
    """
    y = np.asarray(y, dtype=np.float64)
    highs, lows = envelope_touches(y)
    x = np.arange(y.size, dtype=np.float64) / (y.size - 1)

    def fit(idx: list[int]) -> float | None:
        if len(idx) < 2:
            return None
        k = np.asarray(idx)
        return float(np.polyfit(x[k], y[k], 1)[0])

    return fit(highs), fit(lows)


def _slope_class(slope: float | None, strict: bool = False) -> int | None:
    """Eğimi {düşen, yatay, yükselen} = {-1, 0, +1} kümesine yerleştirir.

    ``strict`` KURALIN KAYNAĞI için kullanılır: eşiğin ölü bandına düşen bir
    eğimin sınıfı yazı-turadır, öyle bir sorgudan kural türetilmez. Adaylar
    tek eşikle sınıflanır — onlarda karar zaten kuralın kendisi değildir.
    """
    if slope is None:
        return None
    t = ENVELOPE_SLOPE_THRESHOLD
    if strict:
        lo, hi = t - ENVELOPE_DEAD_BAND, t + ENVELOPE_DEAD_BAND
        if lo < abs(slope) < hi:
            return None
    if abs(slope) <= t:
        return 0
    return 1 if slope > 0 else -1


def envelope_signature(y: np.ndarray, strict: bool = False) -> tuple[int, int, int] | None:
    """Trend çizgisi kimliği: (üst sınıf, alt sınıf, **yakınsama sınıfı**).

    Kanonik şekillerde ölçülen ilk iki bileşen — yükselen üçgen (0, +1) ·
    alçalan üçgen (-1, 0) · simetrik üçgen (-1, +1) · yükselen takoz (+1, +1)
    · düşen takoz ve boğa bayrağı (-1, -1) · ayı bayrağı (+1, +1).

    Üçüncü bileşen olmadan katman ÖLÜYDÜ. Ölçüldü (4h, ilk 50): yükselen
    takoz sorgusunda sonuçların **50/50'si** ilk iki bileşeni zaten
    taşıyordu, düşen takozda 46/50 — filtrenin eleyecek bir şeyi yoktu.
    Oysa aynı sonuçların yalnız 26/50 ve 32/50'si formasyonun tanımını
    geçiyordu. Eksik bilgi *bağıl* eğimdeydi: takoz yakınsar, bayrağın
    kanalı paraleldir. ``alt - üst`` farkı tam olarak bunu ölçer ve
    kategorik imza onu atıyordu.
    """
    upper, lower = envelope_slopes(y)
    a, b = _slope_class(upper, strict), _slope_class(lower, strict)
    if a is None or b is None:
        return None
    c = _slope_class(lower - upper, strict)
    return None if c is None else (a, b, c)


def _touch_masks(V: np.ndarray, width: int = ENVELOPE_TOUCH_WIDTH) -> tuple[np.ndarray, np.ndarray]:
    """(m, n) bool maskeler: her satırda üst ve alt zarfa dokunan iç noktalar.

    Vektörize: aday listesi üzerinde Python döngüsü yazılmaz (CONTRIBUTING.md).
    Kenar doldurması ±inf'tir; iç noktalar için kesilmiş pencereyle birebir
    aynı sonucu verir, uç noktalar zaten dışlandığı için fark doğurmaz.
    """
    m, n = V.shape
    pad = np.full((m, width), np.inf)
    lo_max = np.lib.stride_tricks.sliding_window_view(
        np.concatenate([-pad, V, -pad], axis=1), 2 * width + 1, axis=1
    ).max(axis=2)
    lo_min = np.lib.stride_tricks.sliding_window_view(
        np.concatenate([pad, V, pad], axis=1), 2 * width + 1, axis=1
    ).min(axis=2)

    interior = np.zeros(n, dtype=bool)
    interior[1 : n - 1] = True
    left = np.empty_like(V)
    right = np.empty_like(V)
    left[:, 1:] = V[:, :-1]
    left[:, 0] = V[:, 0]
    right[:, :-1] = V[:, 1:]
    right[:, -1] = V[:, -1]

    highs = (V >= lo_max - 1e-12) & ((V > left) | (V > right)) & interior
    lows = (V <= lo_min + 1e-12) & ((V < left) | (V < right)) & interior
    return highs, lows


def _masked_slope(V: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Maskelenen noktalara en küçük kareler eğimi; 2'den az nokta → NaN."""
    n = V.shape[1]
    x = np.arange(n, dtype=np.float64) / (n - 1)
    w = mask.astype(np.float64)
    k = w.sum(axis=1)
    sx = w @ x
    sy = (w * V).sum(axis=1)
    sxy = (w * V * x).sum(axis=1)
    sxx = w @ (x * x)

    with np.errstate(divide="ignore", invalid="ignore"):
        denom = sxx - sx * sx / k
        slope = (sxy - sx * sy / k) / denom
    return np.where((k >= 2) & (np.abs(denom) > 1e-12), slope, np.nan)


def _class_of(slope: np.ndarray) -> np.ndarray:
    cls = np.where(np.abs(slope) <= ENVELOPE_SLOPE_THRESHOLD, 0, np.sign(slope))
    return np.where(np.isnan(slope), -128, cls).astype(np.int8)


def envelope_signature_batch(V: np.ndarray) -> np.ndarray:
    """(m, 3) int8: (üst sınıf, alt sınıf, yakınsama sınıfı); tanımsız → -128."""
    V = np.atleast_2d(np.asarray(V, dtype=np.float64))
    highs, lows = _touch_masks(V)
    upper = _masked_slope(V, highs)
    lower = _masked_slope(V, lows)
    return np.column_stack(
        [_class_of(upper), _class_of(lower), _class_of(lower - upper)]
    ).astype(np.int8)


def envelope_stability(
    y: np.ndarray,
    sigma: float = STRUCTURE_NOISE_SIGMA,
    draws: int = STRUCTURE_STABILITY_DRAWS,
) -> float:
    """Zarf imzası, sorguya eklenen gürültüye ne kadar dayanıyor (0–1).

    K-20'nin dersi ikinci katmana da uygulanır: kararsız bir kuralla eleme
    yapmak yapıya göre değil gürültüye göre elemektir. Ölçüldü (σ=0,10,
    300 çekim) — simetrik üçgen 100 · yükselen takoz 100 · düşen takoz 99 ·
    yükselen üçgen 99 · alçalan üçgen 99 ‖ ayı bayrağı 78 · boğa bayrağı 76
    ‖ **ters OBO 45 · OBO 41**.

    Son satır kapının asıl gerekçesi: OBO'nun zarf imzası ``(0, 0, 0)``
    ile *tanımlıdır* ama yazı-turadır. Kapısız bir zarf filtresi dönüş
    ailesini — motorun tek güçlü olduğu aileyi — gürültüyle elerdi.
    """
    y = np.asarray(y, dtype=np.float64)
    base = envelope_signature(y, strict=True)
    if base is None:
        return 0.0
    rng = np.random.default_rng(STRUCTURE_STABILITY_SEED)
    noise = rng.normal(scale=sigma, size=(draws, y.size))
    sig = envelope_signature_batch(y + noise)
    return float((sig == np.asarray(base, dtype=np.int8)).all(axis=1).mean())


def envelope_mask(query: np.ndarray, vectors: np.ndarray) -> np.ndarray | None:
    """Sorgunun trend çizgisi kimliğini taşıyan adayların maskesi.

    Sorgunun kimliği belirsizse (zarfına iki dokunuş düşmüyor ya da eğim
    eşiğin ölü bandında) ``None`` döner ve filtre uygulanmaz — kararsız bir
    kuraldan eleme yapmak yapıya göre değil gürültüye göre elemektir (K-20).
    """
    target = envelope_signature(query, strict=True)
    if target is None:
        return None
    sig = envelope_signature_batch(np.asarray(vectors, dtype=np.float64))
    return (sig == np.asarray(target, dtype=np.int8)).all(axis=1)


def describe_envelope(signature: tuple[int, int, int] | None) -> str | None:
    """Trend çizgisi imzasını okunur bir cümleye çevirir.

    Uç düzeni okuması eğimle tanımlı formasyonlarda kararsızdır ve motor onu
    eleme için kullanmaz (K-20). Kullanıcıya yalnız o okumayı göstermek,
    motorun aslında NEYE göre daralttığını gizlemek olurdu.
    """
    if signature is None:
        return None

    upper, lower, converge = signature
    ust = {-1: "alçalan tepeler", 0: "yatay direnç", 1: "yükselen tepeler"}[upper]
    alt = {-1: "alçalan dipler", 0: "yatay destek", 1: "yükselen dipler"}[lower]
    yon = {-1: "genişleyen", 0: "paralel", 1: "daralan"}[converge]
    return f"{ust} · {alt} · {yon}"


def describe_signature(signature: tuple | None) -> str | None:
    """Yapısal imzayı okunur bir cümleye çevirir.

    Kullanıcının asıl şikâyeti *"çizdiğimi anlamıyor"*du. Motorun çizimden ne
    anladığını **göstermek**, o şikâyetin doğrudan cevabı: yanlış okuduysa
    (el titremesi fazladan bir tepe yarattıysa, omuzlar eşit çıkmadıysa)
    kullanıcı bunu görür ve yeniden çizer. Görünmeyen bir yorum, tartışılamaz
    bir yorumdur.
    """
    if signature is None:
        return None

    side, count, extreme, all_similar, others_similar = signature
    uc = "tepe" if side > 0 else "dip"
    en = "yüksek" if side > 0 else "derin"
    parts = [f"{count} belirgin {uc}"]

    if count >= 2:
        if all_similar:
            parts.append("hepsi benzer seviyede")
        else:
            if extreme == 0:
                sira = "ilki"
            elif extreme == count - 1:
                sira = "sonuncusu"
            elif count == 3 and extreme == 1:
                sira = "ortadaki"
            else:
                sira = f"{extreme + 1}. sıradaki"
            parts.append(f"{sira} en {en}")
            if count >= 3 and others_similar:
                parts.append("diğerleri benzer seviyede")

    return " · ".join(parts)


# ---------------------------------------------------------------------------
# Filtre planı — hangi katman uygulanacak (motor ve parmak izi AYNI kodu çalıştırır)
# ---------------------------------------------------------------------------

from dataclasses import dataclass  # noqa: E402

from engine.config import (  # noqa: E402
    ENVELOPE_FILTER,
    ENVELOPE_MIN_STABILITY,
    STRUCTURE_FILTER,
    STRUCTURE_MIN_STABILITY,
    STRUCTURE_STABILITY_GATE,
    STRUCTURE_YIELDS_TO_ENVELOPE,
)


@dataclass(frozen=True)
class FilterPlan:
    """Bir sorgu için filtre kararı ve okumaları."""

    structure_read: str | None
    structure_stable: bool
    envelope_read: str | None
    apply_structure: bool
    apply_envelope: bool


def filter_plan(
    q: np.ndarray,
    structure_filter: bool = STRUCTURE_FILTER,
    structure_gate: bool = STRUCTURE_STABILITY_GATE,
    envelope_filter: bool = ENVELOPE_FILTER,
    structure_yields: bool = STRUCTURE_YIELDS_TO_ENVELOPE,
) -> FilterPlan:
    """Sorgu hangi katmanlardan geçecek — K-20, K-21 ve alternatiflik kuralı.

    Bu karar eskiden ``SearchEngine.search`` gövdesine gömülüydü ve motor
    parmak izi onu GÖRMÜYORDU: parmak izi yapı taşlarını (imza, kararlılık,
    maske) sınıyordu, "hangisi uygulanacak" kararını değil. Sonuç ölçüldü —
    "yapısal filtre, zarf devredeyken çekilir" kuralı bağlandığında varsayılan
    davranış değişti ama parmak izi aynı kaldı. Karar artık tek yerde; motor
    ve parmak izi bu fonksiyonu çağırır.
    """
    q = np.asarray(q, dtype=np.float64)
    signature = structural_signature(q)
    stable = True if signature is None else signature_stability(q) >= STRUCTURE_MIN_STABILITY

    # K-20: kararsız imzayla eleme yapılmaz.
    apply_structure = bool(structure_filter) and not (structure_gate and not stable)
    # K-21: zarf filtresi yalnız trend çizgisi okuması kararlıyken.
    apply_envelope = bool(envelope_filter) and envelope_stability(q) >= ENVELOPE_MIN_STABILITY
    # Alternatiflik: trend çizgisi okuması kararlıysa uç sayısı sorulmaz.
    if structure_yields and apply_envelope:
        apply_structure = False

    return FilterPlan(
        structure_read=describe_signature(signature),
        structure_stable=bool(stable),
        envelope_read=describe_envelope(envelope_signature(q, strict=True)) if apply_envelope else None,
        apply_structure=apply_structure,
        apply_envelope=apply_envelope,
    )
