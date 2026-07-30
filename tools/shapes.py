"""Kanonik formasyon şekillerinin **matematiksel** tanımları.

Elle uydurulmuş sayı dizisi yoktur: her formasyon gauss toplamları veya
parçalı eğrilerle üretilir. Bu sayede

* şablon vektörleri (``tools/gen_templates.py`` → ``engine/templates/*.json``)
* sentetik doğrulama verisine enjekte edilen formasyonlar
  (``tools/gen_synthetic.py``)

**aynı** matematikten gelir; ground truth ile şablon arasında tanım kayması
olmaz.

Her fonksiyon ``t ∈ [0, 1]`` üzerinde tanımlıdır ve ``[0, 1]`` aralığına
ölçeklenmiş ``(n,)`` dizi döndürür. Yönelim daima fiyat mantığındadır
(büyük değer = yüksek fiyat); kanvasın ters y ekseniyle ilgisi yoktur.
"""

from __future__ import annotations

import numpy as np


def _grid(n: int) -> np.ndarray:
    return np.linspace(0.0, 1.0, n)


def _unit(y: np.ndarray) -> np.ndarray:
    """Şekli [0, 1] aralığına ölçekler (z-score zaten sonradan uygulanır)."""
    lo, hi = float(np.min(y)), float(np.max(y))
    if hi - lo < 1e-12:
        return np.zeros_like(y)
    return (y - lo) / (hi - lo)


def _gauss(t: np.ndarray, mu: float, sigma: float) -> np.ndarray:
    return np.exp(-0.5 * ((t - mu) / sigma) ** 2)


# ---------------------------------------------------------------------------
# Dönüş formasyonları
# ---------------------------------------------------------------------------


def head_and_shoulders(n: int = 32) -> np.ndarray:
    """OBO — iki eşit omuz ve aralarında daha yüksek bir baş."""
    t = _grid(n)
    y = (
        0.55 * _gauss(t, 0.22, 0.075)
        + 1.00 * _gauss(t, 0.50, 0.085)
        + 0.55 * _gauss(t, 0.78, 0.075)
        + 0.12 * t  # hafif yükselen boyun çizgisi
    )
    return _unit(y)


def inverse_head_and_shoulders(n: int = 32) -> np.ndarray:
    """Ters OBO — OBO'nun ayna görüntüsü."""
    return _unit(-head_and_shoulders(n))


def double_top(n: int = 32) -> np.ndarray:
    """İkili tepe — yaklaşık eşit iki zirve, aralarında belirgin bir dip."""
    t = _grid(n)
    y = 1.00 * _gauss(t, 0.30, 0.085) + 0.96 * _gauss(t, 0.70, 0.085) + 0.10 * (1.0 - t)
    return _unit(y)


def double_bottom(n: int = 32) -> np.ndarray:
    """İkili dip."""
    return _unit(-double_top(n))


def rounding_bottom(n: int = 32) -> np.ndarray:
    """Çanak — simetrik, yumuşak U."""
    t = _grid(n)
    return _unit((2.0 * t - 1.0) ** 2)


def cup_and_handle(n: int = 32) -> np.ndarray:
    """Fincan-kulp — çanak (%75) + sığ geri çekilme ve kırılım (%25)."""
    t = _grid(n)
    y = np.empty_like(t)

    cup = t <= 0.75
    u = t[cup] / 0.75
    y[cup] = (2.0 * u - 1.0) ** 2

    handle = ~cup
    v = (t[handle] - 0.75) / 0.25
    y[handle] = 1.0 + 0.25 * v - 0.30 * np.sin(np.pi * v)
    return _unit(y)


# ---------------------------------------------------------------------------
# Devam formasyonları
# ---------------------------------------------------------------------------


def bull_flag(n: int = 32) -> np.ndarray:
    """Boğa bayrağı — dik direk (%40) + aşağı eğimli dar konsolidasyon."""
    t = _grid(n)
    y = np.empty_like(t)

    pole = t <= 0.40
    y[pole] = t[pole] / 0.40

    flag = ~pole
    v = (t[flag] - 0.40) / 0.60
    y[flag] = 1.0 - 0.28 * v + 0.055 * np.sin(2.0 * np.pi * 2.5 * v)
    return _unit(y)


def bear_flag(n: int = 32) -> np.ndarray:
    """Ayı bayrağı — dik düşüş + yukarı eğimli konsolidasyon."""
    t = _grid(n)
    y = np.empty_like(t)

    pole = t <= 0.40
    y[pole] = 1.0 - t[pole] / 0.40

    flag = ~pole
    v = (t[flag] - 0.40) / 0.60
    y[flag] = 0.28 * v - 0.055 * np.sin(2.0 * np.pi * 2.5 * v)
    return _unit(y)


def pennant(n: int = 32) -> np.ndarray:
    """Flama — direk + daralan simetrik salınım."""
    t = _grid(n)
    y = np.empty_like(t)

    pole = t <= 0.35
    y[pole] = t[pole] / 0.35

    body = ~pole
    v = (t[body] - 0.35) / 0.65
    y[body] = 0.85 + 0.15 * (1.0 - v) * np.cos(2.0 * np.pi * 2.0 * v)
    return _unit(y)


def _wedge(n: int, slope: float, cycles: float = 2.5, decay: float = 0.85) -> np.ndarray:
    t = _grid(n)
    envelope = 1.0 - decay * t
    return slope * t + 0.35 * envelope * np.sin(2.0 * np.pi * cycles * t)


def rising_wedge(n: int = 32) -> np.ndarray:
    """Yükselen takoz — yukarı eğimli, daralan salınım (düşüş yönlü)."""
    return _unit(_wedge(n, slope=0.9))


def falling_wedge(n: int = 32) -> np.ndarray:
    """Düşen takoz — aşağı eğimli, daralan salınım (yükseliş yönlü)."""
    return _unit(_wedge(n, slope=-0.9))


def symmetrical_triangle(n: int = 32) -> np.ndarray:
    """Simetrik üçgen — yatay eksende daralan salınım."""
    return _unit(_wedge(n, slope=0.0, cycles=3.0, decay=0.9))


def ascending_triangle(n: int = 32) -> np.ndarray:
    """Yükselen üçgen — yatay direnç, yükselen dipler."""
    t = _grid(n)
    lower = 0.65 * t
    wave = 0.5 - 0.5 * np.cos(2.0 * np.pi * 2.5 * t)
    return _unit(lower + (1.0 - lower) * wave)


def descending_triangle(n: int = 32) -> np.ndarray:
    """Alçalan üçgen — yatay destek, alçalan tepeler."""
    t = _grid(n)
    upper = 1.0 - 0.65 * t
    wave = 0.5 + 0.5 * np.cos(2.0 * np.pi * 2.5 * t)
    return _unit(upper * wave)


#: id → (fonksiyon, kategori, tr ad, en ad, yön)
SHAPES: dict[str, tuple] = {
    "head_and_shoulders": (head_and_shoulders, "reversal", "Omuz Baş Omuz", "Head and Shoulders", "bearish"),
    "inverse_head_and_shoulders": (
        inverse_head_and_shoulders,
        "reversal",
        "Ters Omuz Baş Omuz",
        "Inverse Head and Shoulders",
        "bullish",
    ),
    "double_top": (double_top, "reversal", "İkili Tepe", "Double Top", "bearish"),
    "double_bottom": (double_bottom, "reversal", "İkili Dip", "Double Bottom", "bullish"),
    "cup_and_handle": (cup_and_handle, "reversal", "Fincan-Kulp", "Cup and Handle", "bullish"),
    "rounding_bottom": (rounding_bottom, "reversal", "Çanak Dip", "Rounding Bottom", "bullish"),
    "bull_flag": (bull_flag, "continuation", "Boğa Bayrağı", "Bull Flag", "bullish"),
    "bear_flag": (bear_flag, "continuation", "Ayı Bayrağı", "Bear Flag", "bearish"),
    "pennant": (pennant, "continuation", "Flama", "Pennant", "bullish"),
    "rising_wedge": (rising_wedge, "continuation", "Yükselen Takoz", "Rising Wedge", "bearish"),
    "falling_wedge": (falling_wedge, "continuation", "Düşen Takoz", "Falling Wedge", "bullish"),
    "ascending_triangle": (
        ascending_triangle,
        "continuation",
        "Yükselen Üçgen",
        "Ascending Triangle",
        "bullish",
    ),
    "descending_triangle": (
        descending_triangle,
        "continuation",
        "Alçalan Üçgen",
        "Descending Triangle",
        "bearish",
    ),
    "symmetrical_triangle": (
        symmetrical_triangle,
        "continuation",
        "Simetrik Üçgen",
        "Symmetrical Triangle",
        "neutral",
    ),
}


def shape(name: str, n: int = 32) -> np.ndarray:
    """Ada göre şekil üretir."""
    if name not in SHAPES:
        raise KeyError(f"bilinmeyen formasyon: {name}")
    return SHAPES[name][0](n)
