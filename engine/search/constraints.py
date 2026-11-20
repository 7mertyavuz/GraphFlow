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
    t_arr = np.asarray(target, dtype=np.int16)
    if target[2]:  # all_similar=True: hangi ucun 0.01σ daha uç olduğu yazı-turadır
        return (sig[:, [0, 2, 3]] == t_arr[[0, 2, 3]]).all(axis=1)
    return (sig == t_arr).all(axis=1)


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


def describe_envelope(signature: tuple | None, lang: str = "tr") -> str | None:
    """Trend çizgisi (veya direk + gövde zarf) imzasını okunur bir cümleye çevirir.

    Uç düzeni okuması eğimle tanımlı formasyonlarda kararsızdır ve motor onu
    eleme için kullanmaz (K-20). Kullanıcıya yalnız o okumayı göstermek,
    motorun aslında NEYE göre daralttığını gizlemek olurdu.
    """
    from engine.i18n import t

    if signature is None:
        return None
    if len(signature) == 5:
        pole_side, pole_dir, upper, lower, converge = signature
        pole_key = (
            f"env.pole.{int(pole_dir)}"
            if int(pole_side) > 0
            else f"env.pole_trail.{int(pole_dir)}"
        )
        return " · ".join(
            (
                t(pole_key, lang),  # type: ignore[arg-type]
                t(f"env.upper.{int(upper)}", lang),  # type: ignore[arg-type]
                t(f"env.lower.{int(lower)}", lang),  # type: ignore[arg-type]
                t(f"env.conv.{int(converge)}", lang),  # type: ignore[arg-type]
            )
        )
    upper, lower, converge = signature
    return " · ".join(
        (
            t(f"env.upper.{int(upper)}", lang),  # type: ignore[arg-type]
            t(f"env.lower.{int(lower)}", lang),  # type: ignore[arg-type]
            t(f"env.conv.{int(converge)}", lang),  # type: ignore[arg-type]
        )
    )


# ---------------------------------------------------------------------------
# İki rejimli (direk + gövde) zarf imzası (K-22) ve yapısal yeniden sıralama (K-23)
# ---------------------------------------------------------------------------

from engine.config import (  # noqa: E402
    REGIME_BODY_START,
    REGIME_CONVERGENCE,
    REGIME_FILTER,
    REGIME_MIN_STABILITY,
    REGIME_POLE_HEIGHT,
    REGIME_POLE_K,
    REGIME_POLE_STRICT_HEIGHT,
    REGIME_SLOPE_THRESHOLD,
)


def _sub_slopes_1d(sub: np.ndarray) -> tuple[float | None, float | None]:
    hi, lo = envelope_touches(sub)
    if len(hi) < 2 or len(lo) < 2:
        return None, None
    scale = float(sub.size - 1)
    sh = float(np.polyfit(np.asarray(hi, dtype=np.float64) / scale, sub[hi], 1)[0])
    sl = float(np.polyfit(np.asarray(lo, dtype=np.float64) / scale, sub[lo], 1)[0])
    return sh, sl


def _sub_slopes_batch(sub: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    hi, lo = _touch_masks(sub)
    return _masked_slope(sub, hi), _masked_slope(sub, lo)


def pole_body_signature(
    y: np.ndarray,
    strict: bool = False,
    body_start: int = REGIME_BODY_START,
    slope_thr: float = REGIME_SLOPE_THRESHOLD,
    conv_thr: float = REGIME_CONVERGENCE,
) -> tuple[int, int, int, int, int] | None:
    """Sorguda iki rejimli (direk + konsolidasyon gövdesi) zarf kimliği.

    Dönen 5-demet: ``(pole_side, pole_dir, upper_cls, lower_cls, conv_cls)``
      - ``pole_side``: ``+1`` (solda direk) veya ``-1`` (sağda direk — ayna simetrisi)
      - ``pole_dir``:  ``+1`` (yükselen) veya ``-1`` (düşen)
      - ``upper_cls``, ``lower_cls``, ``conv_cls``: gövde zarfının eğim ve yakınsama sınıfı

    Zaman-ayna (``y[::-1]``) ve dikey-ters (``-y``) dönüşümleri altında tam eşdeğerdir.
    """
    y = np.asarray(y, dtype=np.float64)
    n = y.size
    min_h = REGIME_POLE_STRICT_HEIGHT if strict else REGIME_POLE_HEIGHT
    max_ratio = 0.65 if strict else 0.85

    left_disp = float(y[REGIME_POLE_K - 1] - y[0])
    left_span = float(np.ptp(y[REGIME_POLE_K - 1 :]))
    right_disp = float(y[-1] - y[n - REGIME_POLE_K])
    right_span = float(np.ptp(y[: n - REGIME_POLE_K + 1]))

    has_left = abs(left_disp) >= min_h and left_span <= abs(left_disp) * max_ratio
    has_right = abs(right_disp) >= min_h and right_span <= abs(right_disp) * max_ratio
    if has_left == has_right:
        return None

    if has_left:
        pole_side = 1
        pole_dir = 1 if left_disp > 0 else -1
        sh, sl = _sub_slopes_1d(y[body_start:])
    else:
        pole_side = -1
        pole_dir = 1 if right_disp > 0 else -1
        sh, sl = _sub_slopes_1d(y[: n - body_start])

    if sh is None or sl is None:
        return None

    u_cls = 0 if abs(sh) <= slope_thr else (1 if sh > 0 else -1)
    l_cls = 0 if abs(sl) <= slope_thr else (1 if sl > 0 else -1)
    if u_cls != 0 and l_cls != 0 and u_cls != l_cls:
        c_cls = 1 if (sl - sh) > 0 else -1
    else:
        c_cls = 0 if abs(sl - sh) <= conv_thr else (1 if (sl - sh) > 0 else -1)
    return (pole_side, pole_dir, u_cls, l_cls, c_cls)


def pole_body_signature_batch(
    V: np.ndarray,
    body_start: int = REGIME_BODY_START,
    slope_thr: float = REGIME_SLOPE_THRESHOLD,
    conv_thr: float = REGIME_CONVERGENCE,
) -> np.ndarray:
    """(m, 5) int8: ``pole_body_signature(strict=False)`` vektörize karşılığı."""
    V = np.atleast_2d(np.asarray(V, dtype=np.float64))
    m, n = V.shape
    out = np.full((m, 5), -128, dtype=np.int8)

    left_disp = V[:, REGIME_POLE_K - 1] - V[:, 0]
    left_span = np.ptp(V[:, REGIME_POLE_K - 1 :], axis=1)
    right_disp = V[:, -1] - V[:, n - REGIME_POLE_K]
    right_span = np.ptp(V[:, : n - REGIME_POLE_K + 1], axis=1)

    has_left = (np.abs(left_disp) >= REGIME_POLE_HEIGHT) & (
        left_span <= np.abs(left_disp) * 0.85
    )
    has_right = (np.abs(right_disp) >= REGIME_POLE_HEIGHT) & (
        right_span <= np.abs(right_disp) * 0.85
    )
    valid = has_left ^ has_right
    if not valid.any():
        return out

    sh_l, sl_l = _sub_slopes_batch(V[:, body_start:])
    sh_r, sl_r = _sub_slopes_batch(V[:, : n - body_start])

    sh = np.where(has_left, sh_l, sh_r)
    sl = np.where(has_left, sl_l, sl_r)
    ok = valid & np.isfinite(sh) & np.isfinite(sl)
    if not ok.any():
        return out

    pole_side = np.where(has_left, 1, -1)
    pole_dir = np.where(has_left, np.sign(left_disp), np.sign(right_disp))
    u_cls = np.where(np.abs(sh) <= slope_thr, 0, np.sign(sh))
    l_cls = np.where(np.abs(sl) <= slope_thr, 0, np.sign(sl))
    diff = sl - sh
    opp = (u_cls != 0) & (l_cls != 0) & (u_cls != l_cls)
    c_cls = np.where(
        opp, np.sign(diff), np.where(np.abs(diff) <= conv_thr, 0, np.sign(diff))
    )

    out[ok, 0] = pole_side[ok]
    out[ok, 1] = pole_dir[ok]
    out[ok, 2] = u_cls[ok]
    out[ok, 3] = l_cls[ok]
    out[ok, 4] = c_cls[ok]
    return out


def pole_body_stability(
    y: np.ndarray,
    sigma: float = STRUCTURE_NOISE_SIGMA,
    draws: int = 300,
) -> float:
    """Direk + gövde zarf imzasının gürültü altındaki kararlılığı (0–1)."""
    y = np.asarray(y, dtype=np.float64)
    base = pole_body_signature(y, strict=True)
    if base is None:
        return 0.0
    rng = np.random.default_rng(STRUCTURE_STABILITY_SEED)
    noise = rng.normal(scale=sigma, size=(draws, y.size))
    sig = pole_body_signature_batch(y + noise)
    return float((sig == np.asarray(base, dtype=np.int8)).all(axis=1).mean())


def pole_body_mask(query: np.ndarray, vectors: np.ndarray) -> np.ndarray | None:
    """Sorgunun direk + gövde zarf kimliğini taşıyan adayların maskesi."""
    target = pole_body_signature(query, strict=True)
    if target is None:
        return None
    V = np.atleast_2d(np.asarray(vectors, dtype=np.float64))
    t_arr = np.asarray(target, dtype=np.int8)
    m_start = (pole_body_signature_batch(V, body_start=REGIME_BODY_START) == t_arr).all(axis=1)
    m_core = (
        pole_body_signature_batch(V, body_start=REGIME_POLE_K, slope_thr=0.30) == t_arr
    ).all(axis=1)
    return m_start | m_core


def _quad_r2(W: np.ndarray, side: int) -> tuple[np.ndarray, np.ndarray]:
    """Birim-ortogonal Legendre tabanında 2. derece polinom (parabol) R² ve eğrilik (K-24).

    Ayna (``W[:, ::-1]``) ve dikey çevirme (``-W, -side``) dönüşümleri altında
    birebir değişmezdir; aday listesi üzerinde iki matris-vektör çarpımıyla
    hesaplanır.
    """
    W = np.atleast_2d(np.asarray(W, dtype=np.float64))
    k = W.shape[1]
    u = np.linspace(-1.0, 1.0, k)
    u1 = u / np.linalg.norm(u)
    u2 = u * u - float(np.mean(u * u))
    u2 = u2 / np.linalg.norm(u2)
    Wc = W - np.mean(W, axis=1, keepdims=True)
    ss_tot = np.maximum(1e-12, np.sum(Wc * Wc, axis=1))
    c1 = Wc @ u1
    c2 = -side * (Wc @ u2)
    r2 = np.where(c2 > 0.0, (c1 * c1 + c2 * c2) / ss_tot, 0.0)
    return r2, c2


def pip_skeleton(
    q: np.ndarray,
    prom: float = 0.25,
    pip_tol: float = 0.40,
    max_pts: int = 10,
) -> tuple[list[int], list[int]]:
    """Ayna ve çevirme eşdeğişken algısal kritik noktalar (Qetch + Fu-Chung-Luk PIP-VD).

    Dönen türler: ``+1`` (belirgin tepe), ``-1`` (belirgin dip), ``0`` (uç/dirsek).
    Eşit hata durumunda tüm eş-maksimum indeksleri simetrik eklenir ki ayna
    çevriminde aynı iskelet üretilsin (K-26).
    """
    q = np.asarray(q, dtype=np.float64)
    n = q.size
    if n < 2:
        return ([0], [0]) if n == 1 else ([], [])

    peaks, troughs = prominent_extrema(q, prom)
    kind_map: dict[int, int] = {0: 0, n - 1: 0}
    for idx_list, kind in ((peaks, 1), (troughs, -1)):
        for i in idx_list:
            pos = int(i)
            kind_map[pos] = kind
            # Düz plato uçları (ör. rounding_bottom n=32 ortası): soldaki eşit
            # değerleri de ekle ki yatay aynalamada aynı iskelet üretilsin.
            j = pos - 1
            while j >= 1 and abs(float(q[j]) - float(q[pos])) <= 1e-12:
                kind_map[j] = kind
                j -= 1

    pts = sorted(kind_map.keys())
    grid = np.arange(n, dtype=np.float64)
    while len(pts) < max_pts:
        interp = np.interp(grid, pts, q[pts])
        err = np.abs(q - interp)
        err[pts] = -1.0
        best_val = float(err.max())
        if best_val < pip_tol:
            break
        ties = np.flatnonzero(err >= best_val - 1e-12)
        for idx in ties:
            if int(idx) not in kind_map:
                kind_map[int(idx)] = 0
                pts.append(int(idx))
        pts.sort()

    pts = sorted(kind_map.keys())
    return pts, [kind_map[i] for i in pts]


def perceptual_sketch_penalty(
    query: np.ndarray,
    vectors: np.ndarray,
    delta: int = 2,
) -> np.ndarray:
    """Evrensel Qetch-PIP algısal şekil sapma cezası (K-26).

    Doğrudan nokta-bazlı sadakat (``RMSE``, ``L_inf``), kritik dönüş/dirsek
    seviyeleri (``kp_rmse``), Qetch monotonik bacak salınımı (``leg_err`` +
    ``missing_swing``), aynı tip uçların göreceli sırası (``order_pen``) ve
    aşırı tırtıklılık (``rough_pen``) ile görsel benzerliği ölçer.

    Eşzamanlı zaman-ayna (``q[::-1], V[:, ::-1]``) ve dikey çevirme (``-q, -V``)
    altında birebir değişmezdir.
    """
    q = np.asarray(query, dtype=np.float64)
    V = np.atleast_2d(np.asarray(vectors, dtype=np.float64))
    m, n = V.shape
    if m == 0:
        return np.empty(0, dtype=np.float64)

    diff = V - q[None, :]
    rmse = np.sqrt(np.mean(diff * diff, axis=1))
    linf = np.max(np.abs(diff), axis=1)

    pts, kinds = pip_skeleton(q)
    k = len(pts)
    q_lev = q[pts]
    v_lev = np.empty((m, k), dtype=np.float64)
    for idx_k, (t, kind) in enumerate(zip(pts, kinds)):
        if kind == 0:
            v_lev[:, idx_k] = V[:, t]
        else:
            lo = max(0, t - delta)
            hi = min(n, t + delta + 1)
            v_lev[:, idx_k] = (
                V[:, lo:hi].max(axis=1) if kind > 0 else V[:, lo:hi].min(axis=1)
            )

    kp_rmse = np.sqrt(np.mean((v_lev - q_lev[None, :]) ** 2, axis=1))
    dq = np.diff(q_lev)
    dv = np.diff(v_lev, axis=1)
    leg_err = np.mean(np.abs(dv - dq[None, :]), axis=1)

    missing_swing = np.zeros(m, dtype=np.float64)
    for j in range(k - 1):
        mag = abs(float(dq[j]))
        if mag >= 0.25:
            sgn = 1.0 if dq[j] > 0 else -1.0
            proj = dv[:, j] * sgn
            missing_swing += np.maximum(0.0, 0.50 * mag - proj) / max(0.5, mag)

    order_pen = np.zeros(m, dtype=np.float64)
    n_pairs = 0
    for a in range(k):
        for b in range(a + 1, k):
            if kinds[a] == kinds[b] and kinds[a] != 0:
                gap_q = float(q_lev[a] - q_lev[b])
                if abs(gap_q) >= 0.30:
                    n_pairs += 1
                    sgn = 1.0 if gap_q > 0 else -1.0
                    gap_v = (v_lev[:, a] - v_lev[:, b]) * sgn
                    order_pen += np.maximum(0.0, 0.30 * abs(gap_q) - gap_v)
    if n_pairs > 0:
        order_pen /= n_pairs

    tv_q = float(np.sum(np.abs(np.diff(q))))
    tv_v = np.sum(np.abs(np.diff(V, axis=1)), axis=1)
    rough_pen = np.maximum(0.0, (tv_v / max(1e-9, tv_q)) - 1.25)

    return (
        0.0045 * rmse
        + 0.0015 * np.maximum(0.0, linf - 0.55)
        + 0.0035 * kp_rmse
        + 0.0022 * leg_err
        + 0.0050 * missing_swing
        + 0.0040 * order_pen
        + 0.0010 * rough_pen
    )


from engine.config import PERCEPTUAL_RERANK  # noqa: E402


def structural_alignment_penalty(
    query: np.ndarray,
    vectors: np.ndarray,
    apply_structure: bool = False,
    apply_envelope: bool = False,
    apply_regime: bool = False,
    perceptual: bool = PERCEPTUAL_RERANK,
) -> np.ndarray:
    """Sorgu ile adaylar arasındaki sürekli yapısal/zarf/eğrilik/algısal sapma cezası (K-23, K-24, K-26).

    Yüzdelik dilim birimi cinsinden küçük pozitif cezalar üretir; Post-NMS
    öncesinde ``percentile`` alanına eklenerek aynı kademedeki adaylar
    arasından yapısal ve görsel olarak en temiz olanları üste taşır. Eşzamanlı
    zaman-ayna (``q[::-1], V[:, ::-1]``) ve dikey-ters (``-q, -V``) dönüşümleri
    altında birebir değişmezdir.
    """
    q = np.asarray(query, dtype=np.float64)
    V = np.atleast_2d(np.asarray(vectors, dtype=np.float64))
    m, n = V.shape
    if m == 0:
        return np.empty(0, dtype=np.float64)

    has_gate = bool(apply_structure or apply_envelope or apply_regime)
    if not has_gate:
        if not perceptual:
            return np.zeros(m, dtype=np.float64)
        return perceptual_sketch_penalty(q, V)

    unwarped_dist = 1.0 - (V @ q) / float(n)
    pen = 0.005 * np.clip(unwarped_dist, 0.0, 2.0)

    if apply_regime:
        pb = pole_body_signature(q, strict=True)
        if pb is not None:
            core_sig = pole_body_signature_batch(
                V, body_start=REGIME_POLE_K, slope_thr=0.30, conv_thr=REGIME_CONVERGENCE
            )
            t_arr = np.asarray(pb, dtype=np.int8)
            core_mismatch = ~(core_sig == t_arr).all(axis=1)
            pen += np.where(core_mismatch, 0.004, 0.0)

    if apply_envelope:
        q_env = envelope_signature(q, strict=True)
        q_up, q_lo = envelope_slopes(q)
        if q_env is not None and q_up is not None and q_lo is not None:
            hi_m, lo_m = _touch_masks(V)
            c_up = _masked_slope(V, hi_m)
            c_lo = _masked_slope(V, lo_m)
            if q_env[0] == 0:
                dev = np.where(np.isfinite(c_up), np.abs(c_up - q_up), 1.0)
                pen += np.where(dev > 0.55, 0.004 + 0.001 * dev, 0.0003 * dev)
            if q_env[1] == 0:
                dev = np.where(np.isfinite(c_lo), np.abs(c_lo - q_lo), 1.0)
                pen += np.where(dev > 0.55, 0.004 + 0.001 * dev, 0.0003 * dev)
            half = n // 2
            span_l = np.ptp(V[:, :half], axis=1)
            span_r = np.ptp(V[:, half:], axis=1)
            u = np.linspace(-1.0, 1.0, n)
            u_norm = u / np.sqrt(np.sum(u * u))
            q_resid = q - float(np.mean(q)) - float(np.dot(q, u_norm)) * u_norm
            v_mean = np.mean(V, axis=1, keepdims=True)
            v_resid = (V - v_mean) - ((V @ u_norm)[:, None] * u_norm[None, :])
            r_l_q = float(np.std(q_resid[:half]))
            r_r_q = float(np.std(q_resid[half:]))
            r_l_v = np.std(v_resid[:, :half], axis=1)
            r_r_v = np.std(v_resid[:, half:], axis=1)
            if q_env[2] > 0:
                nar = span_r / np.maximum(1e-9, span_l)
                pen += np.where(nar > 0.90, 0.005, 0.0)
                r_nar = r_r_v / np.maximum(1e-9, r_l_v)
                pen += np.where((r_nar > 0.72) | (r_l_v < 0.78 * r_l_q), 0.004, 0.0)
            elif q_env[2] < 0:
                nar = span_l / np.maximum(1e-9, span_r)
                pen += np.where(nar > 0.90, 0.005, 0.0)
                r_nar = r_l_v / np.maximum(1e-9, r_r_v)
                pen += np.where((r_nar > 0.72) | (r_r_v < 0.78 * r_r_q), 0.004, 0.0)

    if apply_structure:
        q_sig = structural_signature(q)
        if q_sig is not None:
            side = int(q_sig[0])
            opp_sig = side_signature(q, -side)
            c_opp_batch = side_signature_batch(V, -side)
            c_opp_count = np.where(c_opp_batch[:, 0] < 0, 0, c_opp_batch[:, 0])
            q_opp_count = 0 if opp_sig is None else int(opp_sig[0])
            pen += np.where(c_opp_count != q_opp_count, 0.003, 0.0)
            if q_opp_count == 0:
                if abs(float(q[0] - q[-1])) <= 0.30:
                    pen += np.where(
                        np.abs(V[:, 0] - V[:, -1]) > STRUCTURE_EQUAL_TOL, 0.004, 0.0
                    )
                r2_q, _ = _quad_r2(q[None, :], side)
                if float(r2_q[0]) >= 0.90:
                    r2_v, c2_v = _quad_r2(V, side)
                    pen += 0.012 * np.clip(float(r2_q[0]) - r2_v, 0.0, 1.0)
                    pen += np.where(c2_v < 1.2, 0.004, 0.0)
            elif q_opp_count == 1 and int(q_sig[1]) == 2 and not bool(q_sig[3]):
                cup_len = int(round(0.75 * n))
                q_cup = q[:cup_len] if int(q_sig[2]) == 0 else q[n - cup_len :]
                v_cup = V[:, :cup_len] if int(q_sig[2]) == 0 else V[:, n - cup_len :]
                r2_q, _ = _quad_r2(q_cup[None, :], side)
                if float(r2_q[0]) >= 0.90:
                    r2_v, _ = _quad_r2(v_cup, side)
                    pen += 0.025 * np.clip(float(r2_q[0]) - r2_v, 0.0, 1.0)
                    pen += np.where(r2_v < 0.90, 0.004, 0.0)
                peaks_q, troughs_q = prominent_extrema(q, STRUCTURE_PROMINENCE)
                opp_idx = (troughs_q if side > 0 else peaks_q)[0]
                outer_q = float(q[0]) if int(q_sig[2]) == 0 else float(q[-1])
                if abs(outer_q - float(q[opp_idx])) <= 0.30:
                    peaks_v, troughs_v = prominent_extrema_batch(V, STRUCTURE_PROMINENCE)
                    opp_mask = troughs_v if side > 0 else peaks_v
                    signed_opp = np.where(
                        opp_mask, V if side < 0 else -V, -np.inf
                    ).max(axis=1)
                    c_opp_val = signed_opp if side < 0 else -signed_opp
                    c_outer = (
                        (np.max(V[:, :4], axis=1) if side < 0 else np.min(V[:, :4], axis=1))
                        if int(q_sig[2]) == 0
                        else (np.max(V[:, -4:], axis=1) if side < 0 else np.min(V[:, -4:], axis=1))
                    )
                    pen += np.where(
                        np.abs(c_outer - c_opp_val) > 0.45, 0.0015, 0.0
                    )

    if perceptual:
        pen = pen + 0.15 * perceptual_sketch_penalty(q, V)

    return pen


def describe_signature(signature: tuple | None, lang: str = "tr") -> str | None:
    """Yapısal imzayı okunur bir cümleye çevirir.

    Kullanıcının asıl şikâyeti *"çizdiğimi anlamıyor"*du. Motorun çizimden ne
    anladığını **göstermek**, o şikâyetin doğrudan cevabı: yanlış okuduysa
    (el titremesi fazladan bir tepe yarattıysa, omuzlar eşit çıkmadıysa)
    kullanıcı bunu görür ve yeniden çizer. Görünmeyen bir yorum, tartışılamaz
    bir yorumdur.

    Metin katalogdan gelir (``engine.i18n``); imza dilden bağımsızdır ve
    önbelleğe metin değil imza yazılır.
    """
    from engine.i18n import t

    if signature is None:
        return None

    side, count, extreme, all_similar, others_similar = signature
    L = lang  # type: ignore[assignment]
    if side > 0:
        what = t("sig.peaks" if count > 1 else "sig.peak", L)
    else:
        what = t("sig.troughs" if count > 1 else "sig.trough", L)
    parts = [t("sig.count", L, n=count, what=what)]

    if count >= 2:
        if all_similar:
            parts.append(t("sig.all_similar", L))
        else:
            if extreme == 0:
                who = t("sig.first", L)
            elif extreme == count - 1:
                who = t("sig.last", L)
            elif count == 3 and extreme == 1:
                who = t("sig.middle", L)
            else:
                who = t("sig.nth", L, k=extreme + 1)
            parts.append(t("sig.highest" if side > 0 else "sig.deepest", L, who=who))
            if count >= 3 and others_similar:
                parts.append(t("sig.others_similar", L))

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
    apply_regime: bool = False
    #: Dilden bağımsız okumalar — önbelleğe bunlar yazılır, metin değil.
    structure_signature: tuple | None = None
    envelope_signature: tuple | None = None


def filter_plan(
    q: np.ndarray,
    structure_filter: bool = STRUCTURE_FILTER,
    structure_gate: bool = STRUCTURE_STABILITY_GATE,
    envelope_filter: bool = ENVELOPE_FILTER,
    structure_yields: bool = STRUCTURE_YIELDS_TO_ENVELOPE,
    regime_filter: bool = REGIME_FILTER,
) -> FilterPlan:
    """Sorgu hangi katmanlardan geçecek — K-20, K-21, K-22 ve alternatiflik kuralı.

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
    # K-22: iki rejimli (direk + gövde) zarf filtresi.
    apply_regime = (
        bool(envelope_filter)
        and bool(regime_filter)
        and not apply_envelope
        and pole_body_stability(q) >= REGIME_MIN_STABILITY
    )
    # Alternatiflik: trend çizgisi ya da direk+gövde okuması kararlıysa uç sayısı sorulmaz.
    if structure_yields and (apply_envelope or (structure_gate and apply_regime)):
        apply_structure = False

    if apply_envelope:
        env_sig: tuple | None = envelope_signature(q, strict=True)
    elif apply_regime:
        env_sig = pole_body_signature(q, strict=True)
    else:
        env_sig = None

    return FilterPlan(
        structure_read=describe_signature(signature),
        structure_stable=bool(stable),
        envelope_read=describe_envelope(env_sig),
        apply_structure=apply_structure,
        apply_envelope=apply_envelope,
        apply_regime=apply_regime,
        structure_signature=signature,
        envelope_signature=env_sig,
    )
