"""Gerçek bir grafikten sorgu — "BTC'nin son 64 barı neye benziyor?"

**Neden var.** Piyasadaki benzer-grafik araçlarının (Chart Library,
TradingView'daki desen eşleştirme betikleri) çoğu sorguyu çizimle değil,
gerçek bir grafiğin bir parçasıyla kurar. GraphFlow'un çizim ve kütüphane
yolları ölçülmüş bir şekli arar; bu yol, kullanıcının zaten baktığı bir
grafiği sorar.

**Aynı normalizasyon.** Parça, matris pencereleriyle birebir aynı yoldan
geçer (``normalize_window``: log fiyat → 32 nokta → z-score, K-02). Çizim
yolunun yumuşatması uygulanmaz: bar verisi el titremesi taşımaz ve eşikler
filtrelenmemiş pencerelerden kalibre edildi.

**Kendisiyle eşleşme.** Sorgu penceresi matriste de vardır; dışlanmazsa ilk
sonuç sorgunun kendisi, ardından bir-iki bar kaymış kopyaları olur ve
"benzeri bulundu" demek kendini bulmak olur. Dışlama kuralı (``excluded``):

* **Tarihsel mod** — sorgu penceresiyle ZAMANDA örtüşen her pencere, hangi
  sembolde olursa olsun dışlanır. Aynı dönemde ETH'nin BTC'ye benzemesi
  tarihsel bir benzer değil, aynı piyasa hareketidir; sayılsaydı örneklem
  bağımsız olmayan kopyalarla dolar (K-09'un kesitsel karşılığı, K-12).
* **Radar (canlı) mod** — yalnız sorgu sembolünün örtüşen pencereleri
  dışlanır. Soru zaten "şu an hangi grafik buna benziyor"; aynı dönem
  sorunun kendisidir.

Veri kalitesi: pencere içinde fiyat sıçraması (redenominasyon, K-16'daki
süreklilik kuralı) varsa sorgu reddedilir — o parça bir şekil değil, bir
birim değişikliğidir.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from engine.config import SOURCE_MAX_BARS, SOURCE_MIN_BARS
from engine.normalize.pipeline import normalize_window
from engine.outcome.bars import BarStore


class SourceError(ValueError):
    """Parça sorguya dönüştürülemedi; ``code`` i18n anahtarının sonekidir."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ChartWindow:
    symbol_id: int
    start_idx: int
    end_idx: int
    #: Barların açılış zamanı (ms) — eşleşmelerin ``end_time`` sözleşmesiyle aynı.
    start_time: int
    end_time: int
    vector: np.ndarray

    @property
    def length(self) -> int:
        return self.end_idx - self.start_idx + 1


def chart_window(
    store: BarStore,
    symbol_id: int,
    length: int,
    end_time: int | None = None,
) -> ChartWindow:
    """Sembolün ``end_time``'da (yoksa son kapanmış barda) biten parçası.

    ``end_time`` bir barın açılışına denk gelmek zorunda değildir: o anda ya
    da ondan önce açılmış son bar alınır. Depo yalnız kapanmış mumları
    tutar (K-05), dolayısıyla "son bar" daima kapanmıştır.
    """
    if not SOURCE_MIN_BARS <= length <= SOURCE_MAX_BARS:
        raise SourceError("bad_length")
    if not store.has(symbol_id):
        raise SourceError("unknown_symbol")

    off = store.offset[int(symbol_id)]
    n = store.n_bars[int(symbol_id)]
    times = store.open_time[off : off + n]

    if end_time is None:
        end_idx = n - 1
    else:
        end_idx = int(np.searchsorted(times, end_time, side="right")) - 1
    start_idx = end_idx - length + 1
    if start_idx < 0:
        raise SourceError("not_enough_bars")

    # Sıçrama bayrağı barın kendisinde durur (önceki bara göre); pencerenin
    # ilk barındaki bayrak pencere DIŞINDAKİ bir geçişi anlatır.
    if store.jump[off + start_idx + 1 : off + end_idx + 1].any():
        raise SourceError("price_jump")

    vector = normalize_window(store.close[off + start_idx : off + end_idx + 1])
    if vector is None:
        raise SourceError("flat")

    return ChartWindow(
        symbol_id=int(symbol_id),
        start_idx=start_idx,
        end_idx=end_idx,
        start_time=int(times[start_idx]),
        end_time=int(times[end_idx]),
        vector=vector,
    )


def excluded(
    symbol_id: np.ndarray,
    start_time: np.ndarray,
    end_time: np.ndarray,
    window: ChartWindow,
    same_period: bool,
) -> np.ndarray:
    """Dışlanacak adaylar (bool maske) — kural modül belgesinde.

    Zamanlar barların açılış zamanıdır; iki pencere, biri diğeri bitmeden
    başladıysa örtüşür. Tek bir ortak bar da örtüşmedir: ortak bar ortak
    fiyat demektir.
    """
    overlap = (np.asarray(end_time) >= window.start_time) & (
        np.asarray(start_time) <= window.end_time
    )
    if same_period:
        return overlap
    return overlap & (np.asarray(symbol_id) == window.symbol_id)
