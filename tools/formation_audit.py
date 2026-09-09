"""İlk sayfadaki sonuçlar gerçekten O FORMASYON mu? — bağımsız yapı denetimi.

Kullanıcı şikâyeti: *"OBO çiziyorum, benzer şeyler getiriyor ama formasyonu
bulmuyor."* Bu, K-04'ün F3.5 ekinde ölçülmüş bir sorunun kullanıcı
tarafındaki karşılığı: **DTW noktaları hizalar, hizalanan noktaların
seviyelerinin mantıklı olup olmadığına bakmaz.** "Yükseliş–tümsek–düşüş"
yakalanır; omuz–baş–omuz olup olmadığı sorulmaz.

Bu araç o soruyu **bağımsız** sorar. Değerlendirici ne DTW kullanır ne de
kısıt katmanının çapa mekanizmasını — yoksa kısıt katmanını kendisiyle
sınamış olurduk. Bunun yerine 32 noktalık z-score'lu vektörde **belirginlik
(prominence)** tabanlı tepe/dip çıkarır ve formasyonun tanımını doğrudan
uygular:

``head_and_shoulders``
    3 belirgin tepe · ortadaki en yüksek · dış iki tepe birbirine yakın
``double_top``
    2 belirgin tepe · yaklaşık eşit · aralarında belirgin bir dip

Gürültü eşiği belirginliktir, tepe *sayısı* değil: ham 32 noktalık pencerede
onlarca minik salınım vardır, hepsini saymak her pencereyi "çok tepeli" ilan
ederdi.

**İkinci aile — zarf eğimleri (üçgen · takoz · flama · bayrak).** Uç *sayma*
bu formasyonları tanımlamaz: yükselen üçgeni tanımlayan şey tepelerin kaç
tane olduğu değil, **yatay bir direnç ile yükselen diplerdir**. Bu aile
tanımı doğrudan uygular: dokunuş noktalarından üst ve alt zarfa doğru
regresyon çekilir, eğimler karşılaştırılır. Uç sayısına hiç bakılmaz — yani
motorun yapısal imza katmanıyla **hiçbir mekanizma paylaşmaz**; denetim
gerçekten bağımsızdır.

Zarf dokunuşları **yalnız pencerenin içinden** alınır. Uçları saymak simetrik
üçgeni ters okuyordu: ölçüldü, uçlar dahilken alt zarf eğimi -0,47 (düşen
dipler) çıkıyor, uçlar hariçken +2,18 (yükselen dipler) — ders kitabı tanımı.
Pencere kesiği bir dönüş noktası değildir.

Denetçinin ayırt ediciliği ölçülür: 8 zarf denetimi × 14 kanonik şekil
çapraz tablosunda köşegen tamdır (her denetim yalnız kendi şeklini kabul
eder). Her şeye "evet" diyen bir denetçi hiçbir şey ölçmez.

    python -m tools.formation_audit --timeframe 4h
    python -m tools.formation_audit --timeframe 1d --top 12 --prominence 0.5
    python -m tools.formation_audit --family envelope --compare
"""

from __future__ import annotations

import argparse
import logging
import sys

import numpy as np

from engine.config import N_POINTS, OUTCOME_TOLERANCE
from engine.search.engine import SearchEngine

log = logging.getLogger("tools.formation_audit")

#: Bir tepenin/dibin "gerçek" sayılması için gereken en az belirginlik
#: (z-score birimi). Pencere z-score'lu olduğu için ölçek-değişmezdir.
DEFAULT_PROMINENCE = 0.5

#: İki zirvenin "yaklaşık eşit" sayılacağı fark (z birimi). Şablon
#: meta-verisindeki level_match toleransıyla aynı büyüklük mertebesinde.
DEFAULT_EQUAL_TOL = 0.8


def _nearest_left(flags: np.ndarray) -> int:
    """Solda koşulu sağlayan **en yakın** indeks; yoksa 0. Bkz. motordaki eşi."""
    hits = np.flatnonzero(flags)
    return int(hits[-1]) if hits.size else 0


def _extrema(y: np.ndarray, prominence: float) -> tuple[list[int], list[int]]:
    """Belirginliği eşiği aşan yerel tepe ve dip indeksleri.

    Belirginlik: uçtan, kendisinden daha uç **en yakın** noktaya ulaşana
    kadar iki yönde inilen en küçük derinlik. scipy'siz, ~20 satır.

    Bu, motordaki ``prominent_extrema``nın kasıtlı ikinci uygulamasıdır:
    denetçi motorun kodunu çağırırsa motoru kendisiyle sınamış oluruz.
    İkisinde de aynı ayna hatası vardı (sol taban en UZAK yüksek noktayı
    kullanıyordu) ve ikisinde de düzeltildi — ölçüldü, rastgele pencerelerin
    %83'ünde şekil ile aynası farklı uç kümesi veriyordu.
    """
    peaks: list[int] = []
    troughs: list[int] = []
    n = y.size

    for i in range(1, n - 1):
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


def is_head_and_shoulders(y: np.ndarray, prominence: float, tol: float, inverse: bool = False) -> bool:
    """3 belirgin tepe, ortadaki en yüksek, dış ikisi birbirine yakın."""
    z = -y if inverse else y
    peaks, _ = _extrema(z, prominence)
    if len(peaks) != 3:
        return False
    left, head, right = (float(z[p]) for p in peaks)
    if not (head > left and head > right):
        return False
    return abs(left - right) <= tol


#: İkili tepe/dip için tepelerin diplere göre taşıması gereken belirginlik
#: üstünlüğü. Sıfır bırakmak berabere kalan şekilleri yazı-tura yapardı.
DOMINANCE_MARGIN = 0.1


def _prominence(y: np.ndarray, i: int) -> float:
    """Tek bir tepenin belirginlik değeri (dip için ``-y`` verilir)."""
    left, right = y[:i], y[i + 1 :]
    higher_l, higher_r = left[left > y[i]], right[right > y[i]]
    base_l = left[np.argmax(left > y[i]) :].min() if higher_l.size else left.min()
    base_r = right[: np.argmax(right > y[i]) + 1].min() if higher_r.size else right.min()
    return float(y[i] - max(base_l, base_r))


def _peaks_dominate(z: np.ndarray, prominence: float) -> bool:
    """Pencerenin yapısını tepeler mi taşıyor (diplerden belirgin olarak)?

    Bu koşul olmadan denetçi iki formasyonu karıştırıyordu (ölçüldü):
    ters OBO, "iki yaklaşık eşit tepe + aralarında dip" tanımını harfiyen
    sağlıyor (boyun çizgisinin iki ucu) ve ikili tepe sayılıyordu; yükselen
    üçgen de öyle (yatay dirence iki dokunuş). İkisinde de tepeler yapının
    ASIL taşıyıcısı değil.

    Ölçülen belirginlik zirveleri — ikili tepe 2,79 / 2,32 (tepe kazanır),
    ters OBO 0,87 / 3,37 (dip kazanır), yükselen üçgen 2,64 / 2,64 (berabere).
    """
    peaks, troughs = _extrema(z, prominence)
    top = max((_prominence(z, i) for i in peaks), default=0.0)
    bottom = max((_prominence(-z, i) for i in troughs), default=0.0)
    return top - bottom > DOMINANCE_MARGIN


def is_double_top(y: np.ndarray, prominence: float, tol: float, bottom: bool = False) -> bool:
    """2 belirgin tepe, yaklaşık eşit, aralarında belirgin bir dip.

    Ek koşul: tepeler pencerenin baskın yapısı olmalı (``_peaks_dominate``).
    """
    z = -y if bottom else y
    peaks, troughs = _extrema(z, prominence)
    if len(peaks) != 2:
        return False
    a, b = (float(z[p]) for p in peaks)
    if abs(a - b) > tol:
        return False
    if not any(peaks[0] < t < peaks[1] for t in troughs):
        return False
    return _peaks_dominate(z, prominence)


# ---------------------------------------------------------------------------
# İkinci aile: zarf eğimleri — üçgen, takoz, flama, bayrak
# ---------------------------------------------------------------------------
#
# Uç *sayısı* bu formasyonları tanımlamaz. Yükselen üçgeni tanımlayan şey
# "iki tepe" değil, **yatay direnç + yükselen dipler**dir. Burada tanım
# doğrudan uygulanır: dokunuş noktalarına regresyon, eğim karşılaştırması.

#: Zarfın "yatay" sayılacağı azami eğim (z birimi / tam pencere).
FLAT_SLOPE = 0.6
#: Zarfın "belirgin eğimli" sayılacağı asgari eğim. FLAT ile arasındaki
#: boşluk kasıtlı: kararsız bölgeye düşen aday hiçbir denetimi geçmez.
TREND_SLOPE = 1.0
#: İki zarfın "yakınsıyor" sayılması için gereken eğim farkı. Takozu
#: bayraktan ayıran tek ölçü budur: bayrağın kanalı paraleldir.
#: Ölçüldü — düşen takoz 1,85 · yükselen takoz 2,22 · boğa bayrağı 0,08.
CONVERGENCE = 0.8
#: Direğin asgari yüksekliği (z birimi) ve pencerenin ne kadarını kapladığı.
POLE_HEIGHT, POLE_FRACTION = 1.5, 0.35


def envelope_touches(y: np.ndarray, width: int = 2) -> tuple[list[int], list[int]]:
    """Üst ve alt zarfa dokunan **iç** noktalar.

    Uçlar dışlanır: pencerenin ilk ve son barı bir dönüş noktası değil,
    verinin kesildiği yerdir. Ölçüldü — uçlar dahilken simetrik üçgenin alt
    zarfı -0,47 (düşen) okunuyordu; iç noktalarla +2,18 (yükselen).
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


def envelope_slopes(
    y: np.ndarray, start: float = 0.0
) -> tuple[float | None, float | None, np.ndarray]:
    """(üst eğim, alt eğim, incelenen dilim). Dokunuş < 2 ise eğim ``None``.

    ``start`` pencerenin ne kadarının atlanacağıdır: bayrak ve flamanın
    gövdesi direkten SONRA başlar, direği dahil etmek kanalın eğimini
    direğin eğimiyle boğar.
    """
    y = np.asarray(y, dtype=np.float64)
    segment = y[int(round(start * (y.size - 1))) :]
    highs, lows = envelope_touches(segment)

    def fit(idx: list[int]) -> float | None:
        if len(idx) < 2:
            return None
        x = np.asarray(idx, dtype=np.float64) / (segment.size - 1)
        return float(np.polyfit(x, segment[np.asarray(idx)], 1)[0])

    return fit(highs), fit(lows), segment


def _narrowing(segment: np.ndarray) -> float:
    """İkinci yarının genlik açıklığı / ilkinin. < 1 ise daralıyor."""
    half = segment.size // 2
    return float(np.ptp(segment[half:]) / max(1e-9, np.ptp(segment[:half])))


def is_triangle(y: np.ndarray, upper: str, lower: str) -> bool:
    """Üçgen: bir zarf yatay ya da eğimli, diğeri karşı yönde; genlik daralır.

    ``upper``/``lower`` ∈ {"flat", "up", "down"} — tanımın kendisi, formasyon
    başına kod değil.
    """
    sh, sl, segment = envelope_slopes(y)
    if sh is None or sl is None:
        return False
    test = {
        "flat": lambda s: abs(s) <= FLAT_SLOPE,
        "up": lambda s: s >= TREND_SLOPE,
        "down": lambda s: s <= -TREND_SLOPE,
    }
    if not (test[upper](sh) and test[lower](sl)):
        return False
    return _narrowing(segment) <= 0.90


def is_wedge(y: np.ndarray, direction: int) -> bool:
    """Takoz: iki zarf da AYNI yöne eğimli, ama birbirine yakınsıyor."""
    sh, sl, _ = envelope_slopes(y)
    if sh is None or sl is None:
        return False
    if direction > 0 and not (sh >= TREND_SLOPE and sl >= TREND_SLOPE):
        return False
    if direction < 0 and not (sh <= -TREND_SLOPE and sl <= -TREND_SLOPE):
        return False
    # Yakınsama daima aynı işaretlidir: alt zarf üste göre yükselir.
    return (sl - sh) >= CONVERGENCE


def _has_pole(y: np.ndarray, direction: int) -> bool:
    y = np.asarray(y, dtype=np.float64)
    k = max(2, int(round(POLE_FRACTION * y.size)))
    return direction * float(y[k - 1] - y[0]) >= POLE_HEIGHT


def is_flag(y: np.ndarray, direction: int) -> bool:
    """Bayrak: direk + karşı yönde **paralel** kanal.

    Takozdan tek farkı paralellik. Bu ayrım olmadan boğa bayrağı düşen takoz
    denetimini de geçiyordu (ölçüldü) — denetçi iki formasyonu karıştırıyorsa
    ölçtüğü şey formasyon değildir.
    """
    if not _has_pole(y, direction):
        return False
    sh, sl, _ = envelope_slopes(y, start=POLE_FRACTION)
    if sh is None or sl is None:
        return False
    counter = (lambda s: s <= -0.3) if direction > 0 else (lambda s: s >= 0.3)
    if not (counter(sh) and counter(sl)):
        return False
    return abs(sh - sl) <= CONVERGENCE


def is_pennant(y: np.ndarray) -> bool:
    """Flama: direk + daralan simetrik salınım (bayrağın yakınsayan hâli)."""
    if not _has_pole(y, +1):
        return False
    sh, sl, _ = envelope_slopes(y, start=POLE_FRACTION)
    if sh is None or sl is None:
        return False
    return sh <= -0.3 and sl >= 0.3


EXTREMA_CHECKS = {
    "head_and_shoulders": lambda y, p, t: is_head_and_shoulders(y, p, t),
    "inverse_head_and_shoulders": lambda y, p, t: is_head_and_shoulders(y, p, t, inverse=True),
    "double_top": lambda y, p, t: is_double_top(y, p, t),
    "double_bottom": lambda y, p, t: is_double_top(y, p, t, bottom=True),
}

ENVELOPE_CHECKS = {
    "ascending_triangle": lambda y, p, t: is_triangle(y, "flat", "up"),
    "descending_triangle": lambda y, p, t: is_triangle(y, "down", "flat"),
    "symmetrical_triangle": lambda y, p, t: is_triangle(y, "down", "up"),
    "rising_wedge": lambda y, p, t: is_wedge(y, +1),
    "falling_wedge": lambda y, p, t: is_wedge(y, -1),
    "pennant": lambda y, p, t: is_pennant(y),
    "bull_flag": lambda y, p, t: is_flag(y, +1),
    "bear_flag": lambda y, p, t: is_flag(y, -1),
}

#: Denetlenebilen tüm formasyonlar. Kütüphanenin 14 öğesinden 12'si burada;
#: ``cup_and_handle`` ve ``rounding_bottom`` **denetimsizdir** — ikisi de
#: eğrilikle tanımlanır, ne uç düzeni ne zarf eğimi onları ayırt eder.
#: Denetimsiz olduklarını yazmak, uydurma bir denetim yazmaktan iyidir.
CHECKS = {**EXTREMA_CHECKS, **ENVELOPE_CHECKS}

FAMILIES = {"extrema": EXTREMA_CHECKS, "envelope": ENVELOPE_CHECKS, "all": CHECKS}


def freehand_query(template_id: str, seed: int, noise: float = 0.035, n: int = 240) -> np.ndarray:
    """Elle çizim taklidi: titrek el + düzensiz çizim hızı.

    Kütüphaneden seçmek ile elle çizmek AYNI yol değildir. Ölçüldü: filtresiz
    hâlde OBO şablonu ilk 12'de 6 doğru verirken, elle çizilmiş OBO yalnız
    **1** veriyordu. Kullanıcının şikâyeti bu farkın kendisiydi.
    """
    from engine.normalize.pipeline import normalize_drawing
    from tools import shapes

    fn = getattr(shapes, template_id)
    rng = np.random.default_rng(seed)
    y = fn(n) + noise * rng.normal(size=n)
    x = np.sort(rng.uniform(0.0, 1.0, n))
    x = (x - x[0]) / (x[-1] - x[0])
    return normalize_drawing(np.column_stack([x, y]), invert_y=False, smooth=True)


def cross_check(prominence: float = DEFAULT_PROMINENCE, tol: float = DEFAULT_EQUAL_TOL) -> dict:
    """Denetçinin kendi ayırt ediciliği: her denetim × her kanonik şekil.

    Bu tablo denetçiyi denetler. Her şeye "evet" diyen bir kontrol, sonuçların
    %100'ünü doğru ilan eder ve hiçbir şey ölçmez. Köşegen dışı her ✅ ya
    denetimin gevşek olduğunu ya da iki formasyonun gerçekten ayırt
    edilemediğini söyler.
    """
    from tools import shapes

    matrix: dict[str, dict[str, bool]] = {}
    for shape_id in shapes.SHAPES:
        y = np.asarray(shapes.shape(shape_id, N_POINTS), dtype=np.float64)
        y = (y - y.mean()) / max(1e-12, y.std())
        matrix[shape_id] = {
            name: bool(check(y, prominence, tol)) for name, check in CHECKS.items()
        }
    return matrix


def audit(
    timeframe: str = "4h",
    top: int = 12,
    prominence: float = DEFAULT_PROMINENCE,
    tol: float = DEFAULT_EQUAL_TOL,
    tolerance: str = OUTCOME_TOLERANCE,
    templates: list[str] | None = None,
    freehand: bool = False,
    seed: int = 3,
    family: str = "all",
    compare: bool = False,
) -> list[dict]:
    """Şablon başına: ilk ``top`` sonucun kaçı gerçekten o formasyon?

    ``compare`` açıkken aynı sorgu yapısal filtre AÇIK ve KAPALI iki kez
    koşulur. Filtrenin dört dönüş formasyonunda işe yaradığı ölçülmüştü;
    üçgen/takoz/bayrak ailesinde işe yarayıp yaramadığı **ölçülmemişti** —
    ölçülmemiş bir kazanç kazanç değildir.
    """
    from engine.templates import load_all

    engine = SearchEngine()
    library = load_all()
    checks = FAMILIES.get(family, CHECKS)
    chosen = templates or list(checks)
    rows: list[dict] = []

    for template_id in chosen:
        check = CHECKS.get(template_id)
        template = library.get(template_id)
        if check is None or template is None:
            continue

        query = (
            freehand_query(template_id, seed)
            if freehand
            else np.asarray(template.vector, dtype=np.float64)
        )

        # Kanonik şablonun kendisi denetimden geçmeli — geçmiyorsa denetçi
        # yanlıştır, sonuçlar değil.
        self_ok = check(query, prominence, tol)

        row = {"template_id": template_id, "self_check": self_ok}
        for label, use_filter in (("", True),) if not compare else (("on", True), ("off", False)):
            result = engine.search(
                query,
                timeframe=timeframe,
                tolerance=tolerance,
                limit=top,
                structure_filter=use_filter,
            )
            hits = sum(
                check(
                    np.asarray(
                        engine.handle(m.timeframe, m.window_length).vectors[m.row],
                        dtype=np.float64,
                    ),
                    prominence,
                    tol,
                )
                for m in result.results
            )
            suffix = f"_{label}" if label else ""
            row[f"shown{suffix}"] = len(result.results)
            row[f"hits{suffix}"] = int(hits)
            row[f"total{suffix}"] = result.total
        rows.append(row)
    return rows


def _print_cross(matrix: dict) -> None:
    names = list(CHECKS)
    print()
    print("Denetçinin ayırt ediciliği — satır: kanonik şekil, sütun: denetim")
    print()
    print(f"{'':<28}" + "".join(f"{n[:8]:>10}" for n in names))
    off_diagonal = 0
    for shape_id, row in matrix.items():
        cells = ""
        for n in names:
            ok = row[n]
            if ok and n != shape_id:
                off_diagonal += 1
            cells += f"{('  ✅' if ok else '  ·'):>10}"
        print(f"{shape_id:<28}{cells}")
    print()
    missing = [n for n in names if not matrix.get(n, {}).get(n)]
    print(f"köşegen dışı kabul: {off_diagonal}" + ("  ✅ tam ayrışma" if off_diagonal == 0 else "  ⚠️"))
    if missing:
        print(f"⚠️ kendi şeklini tanımayan denetim: {', '.join(missing)}")
    unaudited = [s for s in matrix if s not in CHECKS]
    if unaudited:
        print(f"denetimsiz şablon: {', '.join(unaudited)} (eğrilikle tanımlı — bkz. modül belgesi)")
    print()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--timeframe", default="4h")
    p.add_argument("--top", type=int, default=12)
    p.add_argument("--prominence", type=float, default=DEFAULT_PROMINENCE)
    p.add_argument("--tol", type=float, default=DEFAULT_EQUAL_TOL)
    p.add_argument("--tolerance", default=OUTCOME_TOLERANCE)
    p.add_argument("--templates", nargs="+", default=None)
    p.add_argument("--family", choices=sorted(FAMILIES), default="all",
                   help="extrema: OBO/ikili · envelope: üçgen/takoz/bayrak · all")
    p.add_argument("--compare", action="store_true",
                   help="Yapısal filtre AÇIK ve KAPALI karşılaştırması")
    p.add_argument("--cross", action="store_true",
                   help="Yalnız denetçinin kendi ayırt edicilik tablosunu bas (veri gerekmez)")
    p.add_argument("--freehand", action="store_true",
                   help="Şablon yerine elle çizim taklidi kullan (titrek el, düzensiz hız)")
    p.add_argument("--seed", type=int, default=3)
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.cross:
        _print_cross(cross_check(args.prominence, args.tol))
        return 0

    rows = audit(args.timeframe, args.top, args.prominence, args.tol, args.tolerance,
                 args.templates, args.freehand, args.seed, args.family, args.compare)

    kaynak = "elle çizim" if args.freehand else "kütüphane şablonu"
    print()
    print(f"{args.timeframe} · {kaynak} · ilk {args.top} sonuç · belirginlik {args.prominence}"
          f" · aile: {args.family}")
    print()

    if args.compare:
        print(f"{'şablon':<28}{'filtre AÇIK':>14}{'filtre KAPALI':>15}{'havuz aç/kap':>16}")
        print("-" * 73)
        for r in rows:
            a = f"{r['hits_on']}/{r['shown_on']}"
            b = f"{r['hits_off']}/{r['shown_off']}"
            print(f"{r['template_id']:<28}{a:>14}{b:>15}"
                  f"{f'{r
["total_on"]} / {r["total_off"]}':>16}")
        print()
        on_h = sum(r["hits_on"] for r in rows); on_s = sum(r["shown_on"] for r in rows)
        off_h = sum(r["hits_off"] for r in rows); off_s = sum(r["shown_off"] for r in rows)
        if on_s and off_s:
            print(f"genel: filtre AÇIK {on_h}/{on_s} = %{100*on_h/on_s:.0f} · "
                  f"KAPALI {off_h}/{off_s} = %{100*off_h/off_s:.0f}")
    else:
        print(f"{'şablon':<30}{'yapıya uyan':>13}{'oran':>8}{'şablonun kendisi':>19}")
        print("-" * 72)
        for r in rows:
            ratio = r["hits"] / r["shown"] if r["shown"] else 0.0
            print(f"{r['template_id']:<30}{r['hits']:>6}/{r['shown']:<6}{ratio:>7.0%}"
                  f"{'✅' if r['self_check'] else '❌ DENETÇİ HATALI':>19}")
        print()
        total_hits = sum(r["hits"] for r in rows)
        total_shown = sum(r["shown"] for r in rows)
        if total_shown:
            print(f"genel: {total_hits}/{total_shown} = %{100 * total_hits / total_shown:.0f}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
