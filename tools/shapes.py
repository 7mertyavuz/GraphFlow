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


def head_and_shoulders(
    n: int = 32,
    left_h: float = 0.55,
    head_h: float = 1.00,
    right_h: float = 0.55,
    mus: tuple[float, float, float] = (0.22, 0.50, 0.78),
    sigmas: tuple[float, float, float] = (0.075, 0.085, 0.075),
    neck_slope: float = 0.12,
) -> np.ndarray:
    """OBO — iki omuz ve aralarında daha yüksek bir baş.

    Varsayılan parametreler **kanonik** şekli verir (şablon JSON'ları bunu
    kullanır). Farklı değerler "aynı formasyonun başka bir örneğini" üretir:
    asimetrik omuz yükseklikleri, eğimli boyun çizgisi, kaymış zirveler.
    Bu, K-11 A/B'sindeki dairesellik kusurunun çözümüdür.
    """
    t = _grid(n)
    y = (
        left_h * _gauss(t, mus[0], sigmas[0])
        + head_h * _gauss(t, mus[1], sigmas[1])
        + right_h * _gauss(t, mus[2], sigmas[2])
        + neck_slope * t  # boyun çizgisi eğimi
    )
    return _unit(y)


def inverse_head_and_shoulders(n: int = 32, **kwargs) -> np.ndarray:
    """Ters OBO — OBO'nun ayna görüntüsü."""
    return _unit(-head_and_shoulders(n, **kwargs))


def double_top(
    n: int = 32,
    first_h: float = 1.00,
    second_h: float = 0.96,
    mus: tuple[float, float] = (0.30, 0.70),
    sigmas: tuple[float, float] = (0.085, 0.085),
    drift: float = 0.10,
) -> np.ndarray:
    """İkili tepe — yaklaşık eşit iki zirve, aralarında belirgin bir dip."""
    t = _grid(n)
    y = (
        first_h * _gauss(t, mus[0], sigmas[0])
        + second_h * _gauss(t, mus[1], sigmas[1])
        + drift * (1.0 - t)
    )
    return _unit(y)


def double_bottom(n: int = 32, **kwargs) -> np.ndarray:
    """İkili dip."""
    return _unit(-double_top(n, **kwargs))


def rounding_bottom(n: int = 32, power: float = 2.0, center: float = 0.5) -> np.ndarray:
    """Çanak — yumuşak U. ``center`` dip zamanlamasını kaydırır."""
    t = _grid(n)
    span = np.where(t <= center, t / max(center, 1e-6) - 1.0, (t - center) / max(1.0 - center, 1e-6))
    return _unit(np.abs(span) ** power)


def cup_and_handle(
    n: int = 32,
    cup_frac: float = 0.75,
    handle_depth: float = 0.60,
    handle_rise: float = 0.25,
    cup_power: float = 2.0,
) -> np.ndarray:
    """Fincan-kulp — çanak + geri çekilme ve kırılım.

    ``cup_frac`` kulbun uzunluğunu, ``handle_depth`` derinliğini değiştirir;
    gerçek örnekler arasında en çok değişen iki serbestlik derecesi bunlar.

    **F3.5 ölçümü — kulp derinliği neden 0,30'dan 0,60'a çıkarıldı:**
    Göz testinde fincan sonuçlarının çoğu kulpsuz saf U çıkıyordu. Ölçüm:
    ilk 12 sonuçta kulp taşıyan pencere sayısı derinliğe göre
    0,30 → 4/12 · 0,45 → 5/12 · **0,60 → 9/12** · 0,80 → 12/12.
    Sığ kulp 32 noktada gerçek gürültünün altında kalıyor, çözülemiyor.
    0,80 daha da iyi ama artık "ders kitabı kulbu" değil; 0,60 dengedir.
    Komşu şablonlara çarpmıyor: çanak ve ikili dip mesafeleri derinlikle
    ARTIYOR (çanak 0,0188 → 0,0405), sonuç kümesi örtüşmesi zaten ~%1.
    """
    t = _grid(n)
    y = np.empty_like(t)

    cup = t <= cup_frac
    u = t[cup] / cup_frac
    y[cup] = np.abs(2.0 * u - 1.0) ** cup_power

    handle = ~cup
    v = (t[handle] - cup_frac) / max(1.0 - cup_frac, 1e-6)
    y[handle] = 1.0 + handle_rise * v - handle_depth * np.sin(np.pi * v)
    return _unit(y)


# ---------------------------------------------------------------------------
# Devam formasyonları
# ---------------------------------------------------------------------------


def bull_flag(
    n: int = 32,
    pole_frac: float = 0.40,
    drift: float = 0.28,
    wiggle: float = 0.055,
    cycles: float = 2.5,
) -> np.ndarray:
    """Boğa bayrağı — dik direk + aşağı eğimli dar konsolidasyon."""
    t = _grid(n)
    y = np.empty_like(t)

    pole = t <= pole_frac
    y[pole] = t[pole] / pole_frac

    flag = ~pole
    v = (t[flag] - pole_frac) / max(1.0 - pole_frac, 1e-6)
    y[flag] = 1.0 - drift * v + wiggle * np.sin(2.0 * np.pi * cycles * v)
    return _unit(y)


def bear_flag(
    n: int = 32,
    pole_frac: float = 0.40,
    drift: float = 0.28,
    wiggle: float = 0.055,
    cycles: float = 2.5,
) -> np.ndarray:
    """Ayı bayrağı — dik düşüş + yukarı eğimli konsolidasyon."""
    t = _grid(n)
    y = np.empty_like(t)

    pole = t <= pole_frac
    y[pole] = 1.0 - t[pole] / pole_frac

    flag = ~pole
    v = (t[flag] - pole_frac) / max(1.0 - pole_frac, 1e-6)
    y[flag] = drift * v - wiggle * np.sin(2.0 * np.pi * cycles * v)
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


def rising_wedge(
    n: int = 32, slope: float = 0.9, cycles: float = 2.5, decay: float = 0.85
) -> np.ndarray:
    """Yükselen takoz — yukarı eğimli, daralan salınım (düşüş yönlü)."""
    return _unit(_wedge(n, slope=slope, cycles=cycles, decay=decay))


def falling_wedge(
    n: int = 32, slope: float = -0.9, cycles: float = 2.5, decay: float = 0.85
) -> np.ndarray:
    """Düşen takoz — aşağı eğimli, daralan salınım (yükseliş yönlü)."""
    return _unit(_wedge(n, slope=slope, cycles=cycles, decay=decay))


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
