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

    python -m tools.formation_audit --timeframe 4h
    python -m tools.formation_audit --timeframe 1d --top 12 --prominence 0.5
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


def _extrema(y: np.ndarray, prominence: float) -> tuple[list[int], list[int]]:
    """Belirginliği eşiği aşan yerel tepe ve dip indeksleri.

    Belirginlik: tepeden, kendisinden daha yüksek bir noktaya ulaşana kadar
    iki yönde inilen en küçük derinlik. scipy'siz, ~20 satır.
    """
    peaks: list[int] = []
    troughs: list[int] = []
    n = y.size

    for i in range(1, n - 1):
        if y[i] >= y[i - 1] and y[i] > y[i + 1]:
            left = y[:i]
            right = y[i + 1 :]
            hl = left[left > y[i]]
            hr = right[right > y[i]]
            base_l = left[np.argmax(left > y[i]) :].min() if hl.size else left.min()
            base_r = right[: np.argmax(right > y[i]) + 1].min() if hr.size else right.min()
            if y[i] - max(base_l, base_r) >= prominence:
                peaks.append(i)
        elif y[i] <= y[i - 1] and y[i] < y[i + 1]:
            left = y[:i]
            right = y[i + 1 :]
            ll = left[left < y[i]]
            lr = right[right < y[i]]
            base_l = left[np.argmax(left < y[i]) :].max() if ll.size else left.max()
            base_r = right[: np.argmax(right < y[i]) + 1].max() if lr.size else right.max()
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


def is_double_top(y: np.ndarray, prominence: float, tol: float, bottom: bool = False) -> bool:
    """2 belirgin tepe, yaklaşık eşit, aralarında belirgin bir dip."""
    z = -y if bottom else y
    peaks, troughs = _extrema(z, prominence)
    if len(peaks) != 2:
        return False
    a, b = (float(z[p]) for p in peaks)
    if abs(a - b) > tol:
        return False
    return any(peaks[0] < t < peaks[1] for t in troughs)


CHECKS = {
    "head_and_shoulders": lambda y, p, t: is_head_and_shoulders(y, p, t),
    "inverse_head_and_shoulders": lambda y, p, t: is_head_and_shoulders(y, p, t, inverse=True),
    "double_top": lambda y, p, t: is_double_top(y, p, t),
    "double_bottom": lambda y, p, t: is_double_top(y, p, t, bottom=True),
}


def audit(
    timeframe: str = "4h",
    top: int = 12,
    prominence: float = DEFAULT_PROMINENCE,
    tol: float = DEFAULT_EQUAL_TOL,
    tolerance: str = OUTCOME_TOLERANCE,
    templates: list[str] | None = None,
) -> list[dict]:
    """Şablon başına: ilk ``top`` sonucun kaçı gerçekten o formasyon?"""
    from engine.templates import load_all

    engine = SearchEngine()
    library = load_all()
    chosen = templates or list(CHECKS)
    rows: list[dict] = []

    for template_id in chosen:
        check = CHECKS.get(template_id)
        template = library.get(template_id)
        if check is None or template is None:
            continue

        query = np.asarray(template.vector, dtype=np.float64)

        # Kanonik şablonun kendisi denetimden geçmeli — geçmiyorsa denetçi
        # yanlıştır, sonuçlar değil.
        self_ok = check(query, prominence, tol)

        result = engine.search(query, timeframe=timeframe, tolerance=tolerance, limit=top)
        hits = 0
        for match in result.results:
            handle = engine.handle(match.timeframe, match.window_length)
            vector = np.asarray(handle.vectors[match.row], dtype=np.float64)
            if check(vector, prominence, tol):
                hits += 1

        rows.append({
            "template_id": template_id,
            "self_check": self_ok,
            "shown": len(result.results),
            "hits": hits,
            "total": result.total,
        })
    return rows


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--timeframe", default="4h")
    p.add_argument("--top", type=int, default=12)
    p.add_argument("--prominence", type=float, default=DEFAULT_PROMINENCE)
    p.add_argument("--tol", type=float, default=DEFAULT_EQUAL_TOL)
    p.add_argument("--tolerance", default=OUTCOME_TOLERANCE)
    p.add_argument("--templates", nargs="+", default=None)
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    rows = audit(args.timeframe, args.top, args.prominence, args.tol, args.tolerance, args.templates)

    print()
    print(f"{args.timeframe} · ilk {args.top} sonuç · belirginlik {args.prominence} · eşitlik toleransı {args.tol}")
    print()
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
