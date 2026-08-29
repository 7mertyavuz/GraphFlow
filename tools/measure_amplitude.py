"""Varsayılan genlik eşiğini korpustan ölçer (K-10 / F3.5).

`DEFAULT_MIN_AMPLITUDE` aramada varsayılan olarak uygulanır: pencere içindeki
toplam hareket bu eşiğin altındaysa sonuç listesine girmez. Gerekçesi F3 göz
testinden gelir — z-score, sabitlenmiş ya da ölü bir paritenin %2'lik
dalgalanmasını kusursuz bir formasyona çevirip ilk sayfanın tepesine
yerleştiriyordu.

Eşik teorik olarak seçilemez: doğru değer korpusun oynaklık dağılımına
bağlıdır ve zaman dilimine göre değişir. 1d için F3.5'te ölçüldü (%15 →
likit pencerelerin %95,2'si korunuyor). **4h için ölçülmemişti**; config'de
"geçici — ölçülmedi" notuyla √6 ölçeklemesinden tahmin edilmiş bir sayı
duruyordu. Bu araç o boşluğu kapatır.

Yöntem: likit pencerelerin genlik dağılımı okunur, hedef koruma oranını
(varsayılan %95) sağlayan yüzdelik bulunur ve okunabilir bir değere
yuvarlanır. Patolojik kuyruğu keser, veriyi budamaz.

    python -m tools.measure_amplitude
    python -m tools.measure_amplitude --timeframes 4h --keep 0.95
"""

from __future__ import annotations

import argparse
import logging
import sys

import numpy as np

from engine.config import DEFAULT_MIN_AMPLITUDE, TIMEFRAMES, WINDOW_LENGTHS
from engine.matrix.build import META_FILE, matrix_dir
from engine.matrix.npy_store import load_matrix

log = logging.getLogger("tools.measure_amplitude")

#: Eşik bu adımlara yuvarlanır — kalibrasyon hassas değilse okunabilirlik yeğ.
ROUND_STEPS = (1.0, 2.0, 2.5, 5.0)


def amplitudes(timeframe: str, lengths=WINDOW_LENGTHS, liquid_only: bool = True) -> np.ndarray:
    """Korpustaki pencere genlikleri (%)."""
    out: list[np.ndarray] = []
    for length in lengths:
        path = matrix_dir(timeframe, length) / META_FILE
        if not path.exists():
            log.warning("%s_%d matrisi yok", timeframe, length)
            continue
        meta = np.asarray(load_matrix(path))
        amp = np.asarray(meta["amplitude"], dtype=np.float64)
        if liquid_only:
            amp = amp[np.asarray(meta["liquid"])]
        out.append(amp[np.isfinite(amp)])
    return np.concatenate(out) if out else np.empty(0)


def _round_nice(value: float) -> float:
    """En yakın okunabilir adıma yuvarlar."""
    best = value
    gap = float("inf")
    for step in ROUND_STEPS:
        candidate = round(value / step) * step
        if candidate <= 0:
            continue
        d = abs(candidate - value)
        if d < gap:
            best, gap = candidate, d
    return float(best)


def measure(timeframe: str, keep: float = 0.95, lengths=WINDOW_LENGTHS) -> dict:
    """Hedef koruma oranını sağlayan eşik ve dağılım özeti."""
    amp = amplitudes(timeframe, lengths)
    if amp.size == 0:
        return {"timeframe": timeframe, "n": 0}

    raw = float(np.quantile(amp, 1.0 - keep))
    threshold = _round_nice(raw)
    return {
        "timeframe": timeframe,
        "n": int(amp.size),
        "median": float(np.median(amp)),
        "p05": float(np.quantile(amp, 0.05)),
        "p25": float(np.quantile(amp, 0.25)),
        "raw_threshold": raw,
        "threshold": threshold,
        "kept": float((amp >= threshold).mean()),
        "current": DEFAULT_MIN_AMPLITUDE.get(timeframe),
        "kept_at_current": (
            float((amp >= DEFAULT_MIN_AMPLITUDE[timeframe]).mean())
            if timeframe in DEFAULT_MIN_AMPLITUDE
            else None
        ),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--timeframes", nargs="+", default=list(TIMEFRAMES))
    p.add_argument("--keep", type=float, default=0.95, help="Korunacak likit pencere oranı")
    p.add_argument("--lengths", type=int, nargs="+", default=list(WINDOW_LENGTHS))
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    print()
    print(f"Hedef: likit pencerelerin %{args.keep * 100:.0f}'ini koru")
    print()
    for tf in args.timeframes:
        r = measure(tf, args.keep, args.lengths)
        if r["n"] == 0:
            print(f"{tf}: matris yok")
            continue
        print(f"{tf}  ({r['n']:,} likit pencere)")
        print(f"   dağılım      p05 %{r['p05']:.1f} · p25 %{r['p25']:.1f} · medyan %{r['median']:.1f}")
        print(f"   ölçülen eşik %{r['raw_threshold']:.2f}  →  yuvarlanmış %{r['threshold']:.1f}"
              f"   (korunan %{r['kept'] * 100:.1f})")
        if r["current"] is not None:
            print(f"   config'deki   %{r['current']:.1f}   (korunan %{r['kept_at_current'] * 100:.1f})")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
