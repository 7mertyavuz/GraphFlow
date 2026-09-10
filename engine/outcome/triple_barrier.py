"""Triple-Barrier — ATR tabanlı göreli bariyerler (K-16).

Formasyonun bittiği bar ``t₀``, kapanış ``C₀``, ``ATR = ATR(14)`` yalnızca
``t₀``'a kadarki barlardan (lookahead yasak).

    TP = C₀ + k_tp × ATR     SL = C₀ − k_sl × ATR     T = round(0,5 × L)

Zaman bariyeri **pencere uzunluğuyla orantılıdır**; sabit 10 bar değil.
100 barlık bir çanak 10 barda yargılanırsa neredeyse tümü zaman bariyerinden
çıkar ve 4 matrisin sonuçları kıyaslanamaz hâle gelir.

**Vektörizasyon.** Python döngüsü yok: ~10.000 olay × 20 gölge × 50 bar = 10M
kontrol. Bariyer çarpması ``argmax`` hilesiyle bulunur — ``argmax`` hiç
çarpmayınca da 0 döndüğü için ``any()`` maskesi **zorunludur**.

**Ele alınan tuzaklar**

* ``T`` pencere uzunluğuna göre değişir → olaylar uzunluğa göre gruplanır,
  her grup kendi ``(N, T)`` matrisini kurar.
* Delist/veri sonunda satırlar kısa kalır → high dolgusu −inf, low dolgusu
  +inf; dolgu asla bariyer tetiklemez.
* **Gap/slipaj:** Bir mumun ``Open``'ı bariyerin ötesindeyse çıkış bariyer
  değil o mumun ``Open``'ıdır. **Her iki yöne de** uygulanır — yalnız SL'e
  uygulamak sistematik aşağı yanlılık yaratır ve edge'i olduğundan kötü
  gösterir.
* **Aynı barda TP ve SL** → muhafazakâr varsayım: SL önce çarptı.
* **Delist = zorunlu çıkış**, eleme değil. Elemek, ölmek üzere olan coinlerin
  en kötü sonuçlarını sistematik olarak atmak demektir; K-13'te evren
  düzeyinde önlenen survivorship bias outcome katmanından geri girer.
"""

from __future__ import annotations

import numpy as np

from engine.config import (
    BARRIER_CONFIGS,
    MIN_ATR_PCT,
    MIN_BARS_SINCE_LISTING,
    ROUNDTRIP_FEE_PCT,
    TIME_BARRIER_RATIO,
)
from engine.outcome.bars import BarStore

#: Bir outcome olayının girdisi.
EVENT_DTYPE = np.dtype(
    [
        ("symbol_id", "i4"),
        ("t0", "i4"),  # formasyonun bittiği bar (pencere sonu)
        ("length", "i4"),  # pencere uzunluğu → T = round(0,5 × L)
        ("atr", "f8"),
        ("end_time", "i8"),
    ]
)

#: Çıktı. ``outcome``: 0=tp, 1=sl, 2=time, 3=forced (delist / veri sonu)
RESULT_DTYPE = np.dtype(
    [
        ("symbol_id", "i4"),
        ("t0", "i4"),
        ("length", "i4"),
        ("end_time", "i8"),
        ("r_gross", "f8"),
        ("r_net", "f8"),
        ("outcome", "i1"),
        ("exit_bar", "i4"),
        ("atr_pct", "f8"),
        ("truncated", "?"),  # ileri pencere kesik miydi (delist / veri sonu)
    ]
)

OUTCOME_TP, OUTCOME_SL, OUTCOME_TIME, OUTCOME_FORCED = 0, 1, 2, 3

#: Yön. Short, ayna bariyerlerdir — ikinci bir kod yolu değil, işaret çarpanı.
LONG, SHORT = "long", "short"
DIRECTIONS = (LONG, SHORT)
OUTCOME_NAMES = {OUTCOME_TP: "tp", OUTCOME_SL: "sl", OUTCOME_TIME: "time", OUTCOME_FORCED: "forced"}


def time_barrier(length: int, ratio: float = TIME_BARRIER_RATIO) -> int:
    """``T = round(0,5 × L)`` — pencere uzunluğuyla orantılı (K-16.4)."""
    return max(1, int(round(ratio * int(length))))


#: Bir olayın istatistiğe neden GİRMEDİĞİ — eşleşme kartında gösterilir.
#: Boş dizge = uygun.
REASON_NO_DATA = "no_data"  # sembolün barı yok ya da ATR tanımsız
REASON_COST_FLOOR = "cost_floor"  # 1×ATR / C₀ < %1 (K-16.7)
REASON_LISTING = "listing"  # listelemeden sonra ATR ısınmadı


def ineligible_reasons(events: np.ndarray, store: BarStore) -> np.ndarray:
    """Olay başına elenme sebebi (``""`` = istatistiğe girebilir).

    * ``1×ATR / C₀ < %1`` → işlem maliyeti tabanı (K-16.7): bariyerler spread
      ve komisyonun içinde kaybolur, binlerce sahte "başarı" toplanır.
    * ``t₀ < MIN_BARS_SINCE_LISTING`` → ATR ısınmamış; listeleme günlerinin
      pump/dump oynaklığı hem ATR'yi hem sonucu bozar.

    ``eligible`` bunun ince bir sarmalayıcısıdır: kartın söylediği sebep ile
    istatistiğin uyguladığı filtre ayrı kodda yaşarsa bir gün ayrışır.
    """
    reasons = np.full(events.size, "", dtype="<U10")
    if events.size == 0:
        return reasons

    known = np.array([store.has(int(s)) for s in events["symbol_id"]], dtype=bool)
    ok = known & np.isfinite(events["atr"]) & (events["atr"] > 0)
    reasons[~ok] = REASON_NO_DATA
    if not ok.any():
        return reasons

    c0 = np.zeros(events.size, dtype=np.float64)
    c0[ok] = store.close_at(events["symbol_id"][ok], events["t0"][ok])

    with np.errstate(divide="ignore", invalid="ignore"):
        atr_pct = np.where(c0 > 0, events["atr"] / c0, np.nan)

    cost = ok & ~(np.isfinite(atr_pct) & (atr_pct >= MIN_ATR_PCT))
    reasons[cost] = REASON_COST_FLOOR
    listing = ok & ~cost & (events["t0"] < MIN_BARS_SINCE_LISTING)
    reasons[listing] = REASON_LISTING
    return reasons


def eligible(events: np.ndarray, store: BarStore) -> np.ndarray:
    """İstatistiğe girebilecek olayların maskesi (sebepler: ``ineligible_reasons``)."""
    return ineligible_reasons(events, store) == ""


def enforce_forward_separation(events: np.ndarray, ratio: float = TIME_BARRIER_RATIO) -> np.ndarray:
    """Aynı sembolde ardışık olaylar arasında en az ``T`` bar ayrım (bağımsız N).

    NMS **formasyon** pencerelerinin örtüşmediğini garanti eder ama **sonuç**
    pencerelerini denetlemez: aynı sembolde 5 bar arayla iki eşleşme, ``T=12``
    ile 7 bar örtüşen ileri pencerelere sahiptir → sonuçlar korelasyonludur →
    ``N`` şişer, güven aralığı sahte biçimde daralır (K-09, K-12).
    """
    if events.size == 0:
        return np.zeros(0, dtype=bool)

    keep = np.zeros(events.size, dtype=bool)
    order = np.lexsort((events["t0"], events["symbol_id"]))
    last_by_symbol: dict[int, int] = {}

    for i in order:
        sid = int(events["symbol_id"][i])
        t0 = int(events["t0"][i])
        horizon = time_barrier(int(events["length"][i]), ratio)
        previous = last_by_symbol.get(sid)
        if previous is None or t0 - previous >= horizon:
            keep[i] = True
            last_by_symbol[sid] = t0
    return keep


def _evaluate_group(
    events: np.ndarray,
    store: BarStore,
    k_tp: float,
    k_sl: float,
    horizon: int,
    direction: str = LONG,
) -> np.ndarray:
    """Tek bir pencere uzunluğu grubu (aynı ``T``) — tamamen vektörize.

    ``direction`` yalnızca bir **işaret çarpanıdır**; ikinci bir kod yolu
    açılmaz. Short'ta bariyerler çevrilir (TP aşağıda, SL yukarıda) ama
    muhafazakâr aynı-bar kuralı, gap kuralı, komisyon ve zorunlu çıkış aynen
    geçerlidir.
    """
    sign = 1.0 if direction == LONG else -1.0
    sid, t0 = events["symbol_id"], events["t0"]
    atr = events["atr"].astype(np.float64)
    c0 = store.close_at(sid, t0)

    tp = c0 + sign * k_tp * atr
    sl = c0 - sign * k_sl * atr

    high, low, open_, close, valid = store.forward_window(sid, t0, horizon)
    n_valid = valid.sum(axis=1)

    if direction == LONG:
        tp_hit = high >= tp[:, None]
        sl_hit = low <= sl[:, None]
    else:  # short: TP aşağıda (low ile), SL yukarıda (high ile)
        tp_hit = low <= tp[:, None]
        sl_hit = high >= sl[:, None]

    # argmax hiç çarpmayınca da 0 döner → any() maskesi ZORUNLU
    tp_idx = np.where(tp_hit.any(axis=1), tp_hit.argmax(axis=1), horizon)
    sl_idx = np.where(sl_hit.any(axis=1), sl_hit.argmax(axis=1), horizon)

    hit_any = np.minimum(tp_idx, sl_idx) < horizon
    is_sl = sl_idx <= tp_idx  # aynı barda ikisi de → SL önce (muhafazakâr)
    first = np.where(is_sl, sl_idx, tp_idx)

    rows = np.arange(events.size)
    safe_first = np.clip(first, 0, horizon - 1)
    bar_open = open_[rows, safe_first]

    # Gap/slipaj: mumun Open'ı bariyerin ötesindeyse çıkış Open'dır.
    # Her iki yöne de uygulanır; yukarı gap'te TP çıkışı 2R'den iyi olabilir —
    # bu gerçektir, kırpılmaz.
    if direction == LONG:
        gapped_sl = bar_open <= sl
        gapped_tp = bar_open >= tp
    else:  # short'ta yönler simetrik olarak çevrilir
        gapped_sl = bar_open >= sl
        gapped_tp = bar_open <= tp
    exit_sl = np.where(np.isfinite(bar_open) & gapped_sl, bar_open, sl)
    exit_tp = np.where(np.isfinite(bar_open) & gapped_tp, bar_open, tp)
    exit_price = np.where(is_sl, exit_sl, exit_tp)

    outcome = np.where(is_sl, OUTCOME_SL, OUTCOME_TP).astype(np.int8)
    exit_bar = safe_first + 1  # t0'a göre kaç bar sonra

    # Bariyer vurulmadıysa: zaman bariyeri veya (kesik ise) zorunlu çıkış.
    truncated = n_valid < horizon
    last_valid = np.clip(n_valid - 1, 0, horizon - 1)
    time_price = close[rows, last_valid]

    no_hit = ~hit_any
    forced = no_hit & truncated & (n_valid > 0)
    timed = no_hit & ~truncated

    exit_price = np.where(no_hit, time_price, exit_price)
    exit_bar = np.where(no_hit, last_valid + 1, exit_bar)
    outcome = np.where(forced, OUTCOME_FORCED, np.where(timed, OUTCOME_TIME, outcome)).astype(np.int8)

    r_gross = sign * (exit_price - c0) / atr
    atr_pct = atr / c0
    r_net = r_gross - ROUNDTRIP_FEE_PCT / atr_pct

    out = np.empty(events.size, dtype=RESULT_DTYPE)
    out["symbol_id"] = sid
    out["t0"] = t0
    out["length"] = events["length"]
    out["end_time"] = events["end_time"]
    out["r_gross"] = r_gross
    out["r_net"] = r_net
    out["outcome"] = outcome
    out["exit_bar"] = exit_bar
    out["atr_pct"] = atr_pct
    out["truncated"] = truncated

    # İleri penceresi hiç olmayan olay (t0 = son bar) istatistiğe giremez.
    return out[n_valid > 0]


def evaluate(
    events: np.ndarray,
    store: BarStore,
    k_tp: float,
    k_sl: float,
    ratio: float = TIME_BARRIER_RATIO,
    direction: str = LONG,
) -> np.ndarray:
    """Tüm olaylar için triple-barrier. Olaylar ``T``'ye göre gruplanır."""
    if events.size == 0:
        return np.empty(0, dtype=RESULT_DTYPE)
    if direction not in (LONG, SHORT):
        raise ValueError(f"bilinmeyen yön: {direction}")

    parts = []
    for length in np.unique(events["length"]):
        group = events[events["length"] == length]
        parts.append(
            _evaluate_group(group, store, k_tp, k_sl, time_barrier(int(length), ratio), direction)
        )

    return np.concatenate(parts) if parts else np.empty(0, dtype=RESULT_DTYPE)


def evaluate_all_configs(
    events: np.ndarray,
    store: BarStore,
    configs: dict[str, tuple[float, float]] = BARRIER_CONFIGS,
    direction: str = LONG,
) -> dict[str, np.ndarray]:
    """2:1 ve 1:1 **birlikte** hesaplanır (K-16.6) — maliyeti sıfıra yakın.

    1:1'in null'u tam %50'dir: "bu formasyonun gerçekten yön bilgisi var mı"
    sorusunun akademik savunması olan hâli.
    """
    return {
        name: evaluate(events, store, k_tp, k_sl, direction=direction)
        for name, (k_tp, k_sl) in configs.items()
    }


def theoretical_null(k_tp: float, k_sl: float) -> float:
    """Driftsiz rastgele yürüyüşte üst bariyere önce çarpma olasılığı.

    ``P(üst) = k_sl / (k_tp + k_sl)`` — ATR tabanlı bariyerlerin asıl
    kazandırdığı budur: analitik olarak bilinen bir null hipotezi (K-16.3).
    """
    return float(k_sl / (k_tp + k_sl))
