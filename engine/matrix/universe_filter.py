"""Sabitlenmiş (pegged) parite filtresi — F3.5, K-10'un ölçülmüş uzantısı.

F3 göz testinde ölçülen sorun: z-score, şeklin *kimliğini* fiyat seviyesinden
ve hareket büyüklüğünden ayırır (K-02). Bu, sabitlenmiş bir paritede kusursuz
ama **anlamsız** formasyonlar üretir — PAXUSDT'nin %4'lük dalgalanması, OBO
sorgusunda birinci sıraya yerleşiyordu.

Genlik filtresi (K-10) tek başına yeterli değil: eşiği, düşük oynaklıklı ama
meşru pariteleri de eleyecek kadar yükseltmek gerekirdi. Bu yüzden **yapısal**
bir filtre eklenir: fiyatı geçmişinin çoğunda ``1,0 ± PEG_TOLERANCE`` içinde
kalan parite evrenden düşer.

Kural yalnızca sabitlenmiş varlıkları yakalar, "ucuz" olanları değil: ölçüt
1,0 civarında **kalmak**, küçük olmak değil. Gerçek veride ayrım keskin çıktı —
oranı 0,96'nın üstünde 19 parite var, 0,30 ile 0,96 arasında hiç yok.

Yakalananlar arasında sarmalanmış varlıklar da vardır (``WBTCBTC``,
``RENBTCBTC``, ``BTCBBTC``): onlar da kendi dayanağına sabitlidir ve aynı
sorunu üretir.

**İkizler.** Aynı sarmalanmış varlığın USDT paritesi (``WBTCUSDT``) 1,0'a
değil dayanağına sabitlidir; peg filtresi onu göremez. Onu ``detect_twins``
yakalar: günlük getirisi başka bir sembolünkiyle neredeyse birebir olan ve
daha kısa geçmişe sahip parite. İkiz evrende kalırsa aynı fiyat hareketi iki
"bağımsız" olay sayılır (K-09) ve Radar'da aslının en üst benzeri çıkar.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

from engine.config import (
    LEVERAGED_TOKEN_SUFFIXES,
    META_DIR,
    PEG_MIN_RATIO,
    PEG_TOLERANCE,
    PRICE_CONTINUITY_MAX_RATIO,
    TWIN_MIN_CORR,
    TWIN_MIN_OVERLAP_BARS,
)
from engine.ingest.store import read_json, read_klines, write_json_atomic

log = logging.getLogger(__name__)

PEGGED_FILE = "pegged_symbols.json"


def peg_ratio(close: np.ndarray, tolerance: float = PEG_TOLERANCE) -> float:
    """Fiyatın 1,0 ± tolerance bandında kaldığı bar oranı."""
    c = np.asarray(close, dtype=np.float64)
    if c.size == 0:
        return 0.0
    return float(np.mean(np.abs(c - 1.0) <= tolerance))


def is_pegged(
    close: np.ndarray,
    tolerance: float = PEG_TOLERANCE,
    min_ratio: float = PEG_MIN_RATIO,
    min_bars: int = 30,
) -> bool:
    c = np.asarray(close, dtype=np.float64)
    if c.size < min_bars:
        return False
    return peg_ratio(c, tolerance) >= min_ratio


def is_leveraged_token(symbol: str) -> bool:
    """Kaldıraçlı token mu? (BTCUPUSDT, ETHDOWNUSDT, XRPBULLUSDT…)

    Bunlar spot parite değil, **çürüyen türev ürünlerdir**. Periyodik yeniden
    fiyatlandırma (redenomination) yaptıkları için tek barda 100.000x "hareket"
    üretirler; F4 ölçümünde gölge dağılımın ortalamasını +39R'ye taşıyan sebep
    buydu. Ad tabanlı tespit güvenlidir: Binance'in adlandırması sistematiktir.
    """
    from engine.ingest.symbol_universe import split_quote

    parts = split_quote(symbol)
    if parts is None:
        return False
    base = parts[0]
    return any(base.endswith(sfx) and len(base) > len(sfx) + 1 for sfx in LEVERAGED_TOKEN_SUFFIXES)


def detect_pegged(
    symbols: Iterable[str],
    timeframe: str,
    root: Path | None = None,
    tolerance: float = PEG_TOLERANCE,
    min_ratio: float = PEG_MIN_RATIO,
) -> list[str]:
    """Sabitlenmiş pariteleri bulur (oranlarıyla loglar)."""
    found: list[str] = []
    for symbol in symbols:
        df = read_klines(symbol, timeframe, root, columns=["close"])
        if df.empty:
            continue
        close = df["close"].to_numpy()
        if is_pegged(close, tolerance, min_ratio):
            found.append(symbol)
            log.debug("sabitlenmiş: %s (oran %.3f)", symbol, peg_ratio(close, tolerance))
    return sorted(found)


def twin_pairs(
    closes: dict[str, "pd.Series"],
    min_corr: float = TWIN_MIN_CORR,
    min_overlap: int = TWIN_MIN_OVERLAP_BARS,
) -> list[tuple[str, str, float]]:
    """Getirisi neredeyse birebir olan (ikiz, asıl, korelasyon) üçlüleri.

    ``closes``: sembol → açılış zamanıyla indekslenmiş kapanış serisi.
    Korelasyon yalnız iki serinin ORTAK günleri üzerinden hesaplanır
    (vektörize: tek matris çarpımı; 1.065 sembolde ~2 sn). Fiyat sıçraması
    (redenominasyon) getirisi yok sayılır — tek bir 1000x bar korelasyonu
    tek başına belirlerdi. İkizden hangisinin düşeceği: geçmişi KISA olan;
    asıl daha önce listelenmiştir (BTC, WBTC'den önce vardı).
    """
    import pandas as pd

    series = {s: c for s, c in closes.items() if len(c) >= min_overlap}
    if len(series) < 2:
        return []
    frame = pd.DataFrame(
        {s: np.log(c.astype(np.float64).where(c > 0)).diff() for s, c in series.items()}
    )
    x = frame.to_numpy(dtype=np.float64, copy=True)
    x[np.abs(x) > np.log(PRICE_CONTINUITY_MAX_RATIO)] = np.nan
    names = list(frame.columns)
    history = {s: int(np.isfinite(frame[s]).sum()) for s in names}

    m = np.isfinite(x).astype(np.float64)
    z = np.where(m > 0, x, 0.0)
    n = m.T @ m
    safe_n = np.maximum(n, 1.0)
    sx = (z.T @ m) / safe_n  # [i, j]: i'nin ortak günlerdeki ortalaması
    sxx = ((z * z).T @ m) / safe_n
    sxy = (z.T @ z) / safe_n
    cov = sxy - sx * sx.T
    with np.errstate(invalid="ignore", divide="ignore"):
        corr = cov / np.sqrt((sxx - sx * sx) * (sxx - sx * sx).T)

    iu, ju = np.triu_indices(len(names), 1)
    hit = (n[iu, ju] >= min_overlap) & (corr[iu, ju] > min_corr)
    out: list[tuple[str, str, float]] = []
    for i, j in zip(iu[hit], ju[hit]):
        a, b = names[i], names[j]
        twin, original = (a, b) if (history[a], b) < (history[b], a) else (b, a)
        out.append((twin, original, float(corr[i, j])))
    return sorted(out, key=lambda t: -t[2])


def detect_twins(
    symbols: Iterable[str],
    root: Path | None = None,
    timeframes: Sequence[str] = ("1d",),
) -> list[str]:
    """Evrenden düşecek ikizler. Tespit GÜNLÜK veriyle yapılır ve iki zaman
    dilimine aynen uygulanır: ikizlik varlığın özelliğidir, dilimin değil;
    4h'nin gürültülü getirisi eşiği farklı yerde kesip iki evreni
    ayrıştırabilirdi. Günlük veri yoksa (yalnız 4h indirilmiş bir depo)
    sıradaki dilime düşülür."""
    symbols = list(symbols)
    closes: dict = {}
    for timeframe in timeframes:
        closes = {}
        for symbol in symbols:
            df = read_klines(symbol, timeframe, root, columns=["open_time", "close"])
            if not df.empty:
                closes[symbol] = df.set_index("open_time")["close"]
        if len(closes) >= 2:
            break
    pairs = twin_pairs(closes)
    for twin, original, c in pairs:
        log.info("ikiz: %s ≈ %s (korelasyon %.4f) — %s düşer", twin, original, c, twin)
    return sorted({twin for twin, _, _ in pairs})


def filter_universe(
    symbols: Sequence[str],
    timeframe: str,
    root: Path | None = None,
    save_to: Path | None = None,
) -> tuple[list[str], list[str]]:
    """(kalanlar, düşenler) döndürür ve düşenleri diske kaydeder."""
    pegged = detect_pegged(symbols, timeframe, root)
    pegged += [s for s in symbols if s not in set(pegged) and is_leveraged_token(s)]
    # İkizler günlük veriyle bulunur (bkz. detect_twins). Kök ``.../klines/<tf>``
    # değil ``.../klines`` olduğundan günlük dosyalar aynı kökten okunur.
    pegged += detect_twins(
        [s for s in symbols if s not in set(pegged)], root, timeframes=("1d", timeframe)
    )
    pegged = sorted(set(pegged))
    kept = [s for s in symbols if s not in set(pegged)]

    if pegged:
        path = Path(save_to or (META_DIR / PEGGED_FILE))
        existing = read_json(path, default={}) or {}
        existing[timeframe] = pegged
        write_json_atomic(existing, path)
        log.info("%s: %d sabitlenmiş parite evrenden düştü", timeframe, len(pegged))

    return kept, pegged


def load_pegged(timeframe: str, path: Path | None = None) -> list[str]:
    data = read_json(Path(path or (META_DIR / PEGGED_FILE)), default={}) or {}
    return list(data.get(timeframe, []))
