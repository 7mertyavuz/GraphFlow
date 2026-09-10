"""İleri yol fanı — eşleşmelerden sonra fiyatın izlediği yolların dağılımı.

**Neden var.** Piyasadaki benzer-grafik araçları (Chart Library'nin fan
grafikleri, TradingView'daki "ileri izdüşüm" betikleri) eşleşmelerden sonraki
fiyat yolunu gösterir. Triple-barrier istatistiği tek bir soruyu yanıtlar
("işlem ne oldu"); fan başka bir soruyu: *fiyat ne yaptı, ve ne kadar
dağıldı?* Beklenti bir ortalamadır ve yolun şeklini gizler.

**Neden gölgeyle birlikte.** Bu araçların hiçbiri yolu bir kontrol grubuyla
yan yana koymuyor; tek başına bir fan, piyasanın o dönemde zaten yaptığını
formasyonun başarısı gibi gösterir (K-12). Burada eşleşmelerin fanı daima
aynı aylardan çekilmiş gölge olayların fanıyla birlikte döner.

**Birimler.**

* Fiyat ekseni ATR cinsindendir: ``(C[t0+k] − C[t0]) / ATR(t0)``. Farklı
  oynaklıktaki semboller karşılaştırılabilir olur ve istatistik panelindeki
  R ile aynı birimdir (1R = 1×ATR stop).
* Zaman ekseni her olayın **kendi zaman bariyerine** göre normalize edilir
  (0 → t0, 1 → t0 + T, T = pencere uzunluğunun yarısı, K-16.4). Fan böylece
  istatistik panelinin ölçtüğü ufkun tam aynısını kapsar; 24 ve 100 barlık
  pencereler aynı eksende durur.

Bariyer yoktur: yol, TP ya da SL'ye değse de devam eder — soru "fiyat ne
yaptı", "işlem ne oldu" değil. Fiyat sıçraması (redenominasyon) ve veri sonu
yolu keser; kesilen noktalar sayıma girmez ve her noktada kaç yolun
ölçüldüğü ayrıca döner.
"""

from __future__ import annotations

import numpy as np

from engine.config import FAN_GRID_POINTS, FAN_QUANTILES
from engine.outcome.bars import BarStore
from engine.outcome.triple_barrier import time_barrier


def forward_paths(events: np.ndarray, store: BarStore, grid: int = FAN_GRID_POINTS) -> np.ndarray:
    """(N, grid) ileri yollar — ATR cinsinden, zaman bariyerine göre normalize.

    Ölçülemeyen noktalar (veri sonu, fiyat sıçraması) NaN'dır.
    """
    n = int(events.size)
    out = np.full((n, grid), np.nan)
    if n == 0:
        return out

    horizons = np.array([time_barrier(int(L)) for L in events["length"]], dtype=np.int64)
    h_max = int(horizons.max())
    _, _, _, close, valid = store.forward_window(events["symbol_id"], events["t0"], h_max)
    c0 = store.close_at(events["symbol_id"], events["t0"])
    atr = np.asarray(events["atr"], dtype=np.float64)

    # (N, h_max + 1): k = 0 noktası daima 0.
    steps = np.full((n, h_max + 1), np.nan)
    steps[:, 0] = 0.0
    with np.errstate(invalid="ignore", divide="ignore"):
        steps[:, 1:] = np.where(valid, (close - c0[:, None]) / atr[:, None], np.nan)

    # Her olayın 0..T aralığı ortak ızgaraya doğrusal ara değerlemeyle iner.
    # Vektörize: olay başına kesirli indeks = u·T; komşu iki bar arasında karışım.
    u = np.linspace(0.0, 1.0, grid)[None, :]
    # Yuvarlama: u·T tam bir bara düşmesi gerekirken 4,0000000001 çıkarsa
    # sağ komşu (belki NaN) gereksiz yere karışıma girer.
    pos = np.round(u * horizons[:, None], 9)  # (N, grid)
    lo = np.floor(pos).astype(np.int64)
    hi = np.minimum(lo + 1, horizons[:, None])
    w = pos - lo
    rows = np.arange(n)[:, None]
    a = steps[rows, lo]
    b = steps[rows, hi]
    # Komşulardan biri ölçülemiyorsa nokta da ölçülemez (uydurulmaz) — ama
    # nokta tam bir bara düşüyorsa (w = 0) sağ komşu gerekmez; yoksa bir
    # sıçramadan hemen önceki geçerli bar da kaybolurdu.
    blended = np.where(np.isfinite(a) & np.isfinite(b), (1.0 - w) * a + w * b, np.nan)
    return np.where(w == 0.0, a, blended)


def fan(paths: np.ndarray, quantiles: tuple[float, ...] = FAN_QUANTILES) -> dict:
    """Izgara noktası başına yüzdelikler ve kaç yolun ölçüldüğü."""
    grid = paths.shape[1] if paths.ndim == 2 else 0
    counts = np.isfinite(paths).sum(axis=0) if paths.size else np.zeros(grid, dtype=int)
    bands: dict[str, list[float | None]] = {}
    for q in quantiles:
        if paths.size:
            with np.errstate(all="ignore"):
                values = np.nanquantile(paths, q, axis=0) if np.isfinite(paths).any() else np.full(grid, np.nan)
        else:
            values = np.full(grid, np.nan)
        bands[f"p{int(round(q * 100)):02d}"] = [
            round(float(v), 4) if np.isfinite(v) else None for v in values
        ]
    return {
        "u": [round(float(x), 4) for x in np.linspace(0.0, 1.0, grid)],
        "n": [int(c) for c in counts],
        **bands,
    }


def fan_report(events: np.ndarray, shadow_events: np.ndarray, store: BarStore) -> dict:
    """Eşleşmelerin ve gölgenin fanı — daima birlikte (K-12)."""
    return {
        "matches": fan(forward_paths(events, store)),
        "shadow": fan(forward_paths(shadow_events, store)),
    }
