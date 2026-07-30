"""Kanonik şablon JSON'larını üretir (docs/01-mimari.md §7, K-04).

Vektörler **elle uydurulmaz**: ``tools/shapes.py``'deki matematiksel tanımlardan
(gauss toplamları / parçalı eğriler) örneklenir. Kural motoru yoktur; her
formasyon 32 elemanlı bir vektördür ve aynı DTW pipeline'ından geçer.

Yeni formasyon eklemek = ``SHAPES``'e bir fonksiyon + bu script'i çalıştırmak.

    python -m tools.gen_templates
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from engine.config import N_POINTS, TEMPLATE_DIR
from tools.shapes import SHAPES

DESCRIPTIONS: dict[str, str] = {
    "head_and_shoulders": "İki eşit omuz arasında daha yüksek bir baş; boyun çizgisi kırılımıyla dönüş beklenir.",
    "inverse_head_and_shoulders": "OBO'nun ayna görüntüsü; düşüş trendinin sonunda yükseliş dönüşü.",
    "double_top": "Yaklaşık eşit iki zirve ve aralarındaki dip; ikinci zirvenin aşılamaması dönüş sinyali sayılır.",
    "double_bottom": "Yaklaşık eşit iki dip; ikinci dibin korunması yükseliş dönüşü olarak okunur.",
    "cup_and_handle": "Yuvarlak taban (fincan) ve ardından sığ geri çekilme (kulp); kulp kırılımı devam sinyali.",
    "rounding_bottom": "Uzun ve simetrik yuvarlak taban; kademeli birikim.",
    "bull_flag": "Dik yükseliş (direk) sonrası aşağı eğimli dar konsolidasyon; trend devamı.",
    "bear_flag": "Dik düşüş sonrası yukarı eğimli dar konsolidasyon; düşüş devamı.",
    "pennant": "Direk sonrası daralan simetrik salınım; kısa soluklanma.",
    "rising_wedge": "Yukarı eğimli, daralan salınım; genellikle düşüş yönlü çözülür.",
    "falling_wedge": "Aşağı eğimli, daralan salınım; genellikle yükseliş yönlü çözülür.",
    "ascending_triangle": "Yatay direnç ve yükselen dipler; direncin kırılması beklenir.",
    "descending_triangle": "Yatay destek ve alçalan tepeler; desteğin kırılması beklenir.",
    "symmetrical_triangle": "Simetrik daralma; yön kırılımla belli olur.",
}


#: Geometrik kısıtlar (F3.5, Adım 7) — kanonik vektördeki çapa indeksleri.
#: Kural KODA değil ŞABLON META-VERİSİNE yazılır; tek genel değerlendirici
#: ``engine/search/constraints.py``'dedir. Böylece K-04 korunur: formasyon
#: başına if-else yok. Çapalar kanonik şeklin dönüş noktalarından okundu
#: (OBO: tepeler 7/16/24, dipler 10/21 — ikili tepe: tepeler 9/22).
CONSTRAINTS: dict[str, list[dict]] = {
    # OBO'yu yuvarlak tepeden ayıran şey "orta nokta yüksek" DEĞİLDİR —
    # parabol de onu sağlar. Ayırt edici olan OMUZ BELİRGİNLİĞİ: omuzların
    # komşu diplerin üstünde durması. F3.5 ölçümünde bu kural eksikti ve
    # katman bu yüzden katkı gösterememişti.
    "head_and_shoulders": [
        {"type": "level_match", "anchors": [10, 21], "max_diff": 0.60,
         "comment": "boyun çizgisi: omuz-baş arası iki dip aynı seviyede"},
        {"type": "level_order", "anchors": [7, 16, 24], "order": ["<", ">"],
         "comment": "baş, iki omuzdan da yüksek"},
        {"type": "level_order", "anchors": [10, 7], "order": ["<"],
         "comment": "sol omuz, boyun çizgisinin üstünde (belirginlik)"},
        {"type": "level_order", "anchors": [21, 24], "order": ["<"],
         "comment": "sağ omuz, boyun çizgisinin üstünde (belirginlik)"},
    ],
    "inverse_head_and_shoulders": [
        {"type": "level_match", "anchors": [10, 21], "max_diff": 0.60,
         "comment": "boyun çizgisi (ayna)"},
        {"type": "level_order", "anchors": [7, 16, 24], "order": [">", "<"],
         "comment": "baş, iki omuzdan da düşük"},
        {"type": "level_order", "anchors": [10, 7], "order": [">"],
         "comment": "sol omuz belirginliği (ayna)"},
        {"type": "level_order", "anchors": [21, 24], "order": [">"],
         "comment": "sağ omuz belirginliği (ayna)"},
    ],
    "double_top": [
        {"type": "level_match", "anchors": [9, 22], "max_diff": 0.60,
         "comment": "iki zirve yaklaşık eşit"},
        {"type": "level_order", "anchors": [16, 9], "order": ["<"],
         "comment": "aradaki dip, zirvelerin altında (tek tepe değil)"},
        {"type": "level_order", "anchors": [16, 22], "order": ["<"],
         "comment": "aradaki dip, ikinci zirvenin de altında"},
    ],
    "double_bottom": [
        {"type": "level_match", "anchors": [9, 22], "max_diff": 0.60,
         "comment": "iki dip yaklaşık eşit"},
        {"type": "level_order", "anchors": [16, 9], "order": [">"],
         "comment": "aradaki tepe, diplerin üstünde"},
        {"type": "level_order", "anchors": [16, 22], "order": [">"],
         "comment": "aradaki tepe, ikinci dibin de üstünde"},
    ],
}


def build_template(template_id: str, n: int = N_POINTS) -> dict:
    fn, category, name_tr, name_en, bias = SHAPES[template_id]
    points = [round(float(v), 6) for v in fn(n)]
    kisitlar = CONSTRAINTS.get(template_id)
    return {
        "id": template_id,
        "name_tr": name_tr,
        "name_en": name_en,
        "category": category,
        "bias": bias,
        "points": points,
        "icon": f"{template_id}.svg",
        "description_tr": DESCRIPTIONS.get(template_id, ""),
        **({"constraints": kisitlar} if kisitlar else {}),
    }


def generate(out_dir: Path | None = None, n: int = N_POINTS) -> list[Path]:
    out_dir = Path(out_dir or TEMPLATE_DIR)
    written: list[Path] = []

    for template_id in SHAPES:
        payload = build_template(template_id, n)
        path = out_dir / payload["category"] / f"{template_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(path)

    return written


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI
    p = argparse.ArgumentParser(prog="python -m tools.gen_templates")
    p.add_argument("--out", default=str(TEMPLATE_DIR))
    p.add_argument("--points", type=int, default=N_POINTS)
    args = p.parse_args(argv)

    written = generate(Path(args.out), args.points)
    print(f"{len(written)} sablon yazildi -> {args.out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
