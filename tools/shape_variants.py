"""Formasyon **varyantları** — K-11 A/B'sindeki dairesellik kusurunun çözümü.

F2'deki A/B'de pozitif örnekler, sorgu olarak kullanılan kanonik şablonun
gürültülü kopyalarıydı. Bu, *"şablonu geri bulabiliyor mu"* sorusunu ölçer;
oysa asıl soru *"aynı formasyonun FARKLI bir örneğini tanıyor mu"*dur. DDTW'nin
iddiası (seviye değil eğim eşleştirdiği için varyasyona dayanıklı olmak) tam
olarak burada sınanmalıdır.

Varyasyon iki katmanda üretilir:

1. **Parametre örnekleme** — asimetrik omuz yükseklikleri, eğimli boyun
   çizgisi, farklı kulp derinliği/uzunluğu, farklı direk oranı, farklı
   salınım sayısı. (``tools/shapes.py``'deki parametreler.)
2. **Zaman ekseni bükme** — tepe/dip zamanlama kayması. Şekil yüksek
   çözünürlükte örneklenip **monoton** bir dönüşümle yeniden örneklenir:

       t' = clip(t^γ + a·sin(2πt)/(2π), 0, 1),   γ ∈ [0.75, 1.35], |a| ≤ 0.35

   ``|a| ≤ 0.35`` türevi pozitif tutar (1 + a·cos t > 0), yani sıralama
   korunur — şekil bozulur ama "zaman geri akmaz".

``strength=0`` kanonik şekli aynen verir; testlerde bu bir kontrol noktasıdır.
"""

from __future__ import annotations

import numpy as np

from tools.shapes import SHAPES, _unit

#: Her formasyon için (parametre → örnekleme aralığı). Aralıklar kanonik
#: değerin etrafında, hâlâ "o formasyon" sayılacak genişlikte seçildi.
PARAM_RANGES: dict[str, dict[str, tuple]] = {
    "head_and_shoulders": {
        "left_h": (0.40, 0.72),  # asimetrik omuzlar
        "right_h": (0.40, 0.72),
        "head_h": (0.85, 1.15),
        "neck_slope": (-0.18, 0.28),  # eğimli boyun çizgisi (iki yöne de)
        "mus": ((0.15, 0.28), (0.44, 0.56), (0.72, 0.85)),
        "sigmas": ((0.055, 0.095), (0.065, 0.105), (0.055, 0.095)),
    },
    "double_top": {
        "first_h": (0.88, 1.10),
        "second_h": (0.85, 1.08),  # eşit olmayan zirveler
        "drift": (-0.15, 0.25),
        "mus": ((0.22, 0.36), (0.64, 0.78)),
        "sigmas": ((0.065, 0.105), (0.065, 0.105)),
    },
    "cup_and_handle": {
        "cup_frac": (0.62, 0.84),  # kulp uzunluğu
        "handle_depth": (0.15, 0.45),  # kulp derinliği
        "handle_rise": (0.12, 0.38),
        "cup_power": (1.5, 2.8),  # sığ/derin fincan
    },
    "rounding_bottom": {"power": (1.5, 3.0), "center": (0.38, 0.62)},
    "bull_flag": {
        "pole_frac": (0.28, 0.52),
        "drift": (0.15, 0.42),
        "wiggle": (0.02, 0.10),
        "cycles": (1.5, 3.5),
    },
    "rising_wedge": {"slope": (0.65, 1.15), "cycles": (2.0, 3.5), "decay": (0.70, 0.95)},
    "falling_wedge": {"slope": (-1.15, -0.65), "cycles": (2.0, 3.5), "decay": (0.70, 0.95)},
}

# Ayna formasyonlar aynı parametreleri kullanır.
PARAM_RANGES["inverse_head_and_shoulders"] = PARAM_RANGES["head_and_shoulders"]
PARAM_RANGES["double_bottom"] = PARAM_RANGES["double_top"]
PARAM_RANGES["bear_flag"] = PARAM_RANGES["bull_flag"]

#: Zaman bükme sınırları (monotonluğu korur).
GAMMA_RANGE = (0.80, 1.28)
WARP_AMPLITUDE = 0.28

#: Varyant, kanonik şekilden bu çözünürlükte örneklenip yeniden örneklenir.
_HIRES = 512


def _sample(rng: np.random.Generator, spec, strength: float):
    """Aralıktan örnek çeker; ``strength`` sapmayı aralığın ortasına doğru kısar."""
    if isinstance(spec, tuple) and spec and isinstance(spec[0], tuple):
        return tuple(_sample(rng, s, strength) for s in spec)
    lo, hi = spec
    mid = (lo + hi) / 2.0
    return mid + (rng.uniform(lo, hi) - mid) * strength


def _enforce_structure(name: str, params: dict) -> dict:
    """Formasyonu formasyon yapan kısıtları korur.

    Varyasyon "aynı formasyonun başka bir örneği" olmalı; kısıt bozulursa
    üretilen şey artık o formasyon değildir ve **etiketi yanlış olur** —
    bu da AUC ölçümünü sessizce bozar.
    """
    if name in ("head_and_shoulders", "inverse_head_and_shoulders"):
        # Baş, her iki omuzdan belirgin biçimde yüksek olmalı.
        shoulder = max(params["left_h"], params["right_h"])
        params["head_h"] = max(params["head_h"], shoulder + 0.25)
        # Boyun çizgisi eğimi omuz belirginliğini ezmemeli; ezerse ortaya
        # çıkan şey "üç tümsekli bir trend" olur, OBO değil.
        limit = 0.35 * min(params["left_h"], params["right_h"])
        params["neck_slope"] = float(np.clip(params["neck_slope"], -limit, limit))
    elif name in ("double_top", "double_bottom"):
        # İki zirve "yaklaşık eşit" olmalı; aksi hâlde tek tepe olur.
        if abs(params["first_h"] - params["second_h"]) > 0.18:
            params["second_h"] = params["first_h"] - np.sign(
                params["first_h"] - params["second_h"]
            ) * 0.18
    return params


def sample_params(name: str, rng: np.random.Generator, strength: float = 1.0) -> dict:
    """Formasyona özgü parametreleri örnekler. Tanımsızsa boş sözlük."""
    ranges = PARAM_RANGES.get(name)
    if not ranges or strength <= 0.0:
        return {}
    return _enforce_structure(name, {k: _sample(rng, spec, strength) for k, spec in ranges.items()})


def time_warp(t: np.ndarray, gamma: float, amplitude: float) -> np.ndarray:
    """Monoton zaman bükmesi — tepe/dip zamanlamasını kaydırır."""
    warped = t**gamma + amplitude * np.sin(2.0 * np.pi * t) / (2.0 * np.pi)
    return np.clip(warped, 0.0, 1.0)


#: Formasyon → beklenen tepe/dip yapısı: (yerel maksimum, yerel minimum) sayısı.
#: Varyant bu yapıyı taşımıyorsa **etiketi yanlış olur** ve örnek reddedilir.
EXPECTED_TURNS: dict[str, tuple[int, int]] = {
    "head_and_shoulders": (3, 2),
    "inverse_head_and_shoulders": (2, 3),
    "double_top": (2, 1),
    "double_bottom": (1, 2),
}

_MAX_RESAMPLE = 25


def _turn_counts(y: np.ndarray) -> tuple[int, int]:
    d = np.diff(y)
    sign = np.sign(d[np.abs(d) > 1e-12])
    if sign.size == 0:
        return 0, 0
    flips = np.flatnonzero(np.diff(sign) != 0)
    peaks = int(np.sum(sign[flips] > 0))
    troughs = int(np.sum(sign[flips] < 0))
    return peaks, troughs


def has_expected_structure(name: str, y: np.ndarray) -> bool:
    """Üretilen eğri hâlâ o formasyon mu? (etiket doğrulaması)"""
    expected = EXPECTED_TURNS.get(name)
    if expected is None:
        return True
    return _turn_counts(y) == expected


def variant(
    name: str,
    n: int = 32,
    rng: np.random.Generator | None = None,
    strength: float = 1.0,
) -> np.ndarray:
    """Aynı formasyonun rastgele bir **örneğini** üretir.

    ``strength=0`` → kanonik şekil (kontrol). Büyüdükçe parametre sapması ve
    zaman bükmesi artar. Yapısal doğrulamayı geçemeyen örnek yeniden çekilir;
    çünkü "OBO" etiketli ama OBO olmayan bir pozitif, AUC'yi sessizce bozar.
    """
    if name not in SHAPES:
        raise KeyError(f"bilinmeyen formasyon: {name}")
    rng = rng if rng is not None else np.random.default_rng()
    fn = SHAPES[name][0]

    if strength <= 0.0:
        return fn(n)

    src = np.linspace(0.0, 1.0, _HIRES)
    fallback = None

    for _ in range(_MAX_RESAMPLE):
        params = sample_params(name, rng, strength)
        hires = fn(_HIRES, **params)

        gamma = 1.0 + (rng.uniform(*GAMMA_RANGE) - 1.0) * strength
        amplitude = rng.uniform(-WARP_AMPLITUDE, WARP_AMPLITUDE) * strength
        dst = time_warp(np.linspace(0.0, 1.0, n), gamma, amplitude)

        y = _unit(np.interp(dst, src, hires))
        if has_expected_structure(name, y):
            return y
        fallback = y

    # Yapısal kısıtı sağlayan örnek bulunamadı (dar n'de olabilir): kanoniğe dön.
    return fn(n) if fallback is None else fallback


def variant_batch(
    name: str,
    count: int,
    n: int = 32,
    rng: np.random.Generator | None = None,
    strength: float = 1.0,
) -> np.ndarray:
    rng = rng if rng is not None else np.random.default_rng()
    return np.stack([variant(name, n, rng, strength) for _ in range(count)])
