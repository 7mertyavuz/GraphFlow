"""Oluşmakta olan formasyon — ilk %75 görüldüğünde kalanı gelir mi?

**Soru.** Piyasadaki araçlar (ChartScout, altFINS "Emerging") formasyon
%75–80 olgunluktayken uyarı verir; ima edilen şey kalanın geleceğidir. Bunun
bilgi taşıyıp taşımadığı ölçülebilir:

    Bir formasyonun ilk %75'ine benzeyen pencerelerde, GERÇEK devam formasyonu
    tamamlamaya, aynı aydan çekilmiş RASTGELE bir devamdan daha mı yakın?

**Yöntem.**

1. Önek sorgusu: şablonun 32 noktasının ilk %75'i, 32 noktaya yeniden
   örneklenip z-score'lanır (çizimle aynı normalizasyon, K-02).
2. Motor önek sorgusuyla tarihsel aramayı koşar (orta tolerans). Önek
   uzunluğu ``L`` olan eşleşmenin tam formasyonu ``L / 0,75`` bar sürer;
   kalan ``R = L/3`` bar.
3. **Gerçek:** ``[t0−L+1, t0+R]`` penceresi normalize edilir, tam şablona
   Aşama 2 mesafesi ölçülür.
4. **Kontrol:** aynı önek + başka bir sembolün AYNI AYDAKİ ``R`` barlık
   log getirileri (K-12'nin zaman eşleştirmesi). Getiriler iki biçimde
   ölçeklenir:

   * ``prefix`` — önekin kendi oynaklığına: "rastgele bir devam".
   * ``shape`` — gerçek devamın gerçekleşen oynaklığına: yalnız YÖN ve ŞEKİL
     sınanır, büyüklük değil (gerçek devamın büyüklüğü kontrolle paylaşılır;
     ölçek geleceğe baksa da bu bir kontrol kolunun ayarıdır, sinyal değil).

5. Olay başına skor: gerçeğin, ``K`` kontrolün kaçından tam şablona daha
   yakın olduğu (eşitlik ½). Ortalaması bir AUC'dir; bilgi yoksa 0,5.
   Güven aralığı **ay-bloklu** bootstrap (K-12), aile 14 şablon × 2 ölçek
   için Bonferroni, bulgu iki dilimde de aranır (F4.7).

Ek olarak okunurluk için "tamamlandı" oranı: tam şablona mesafesi F3'te
kalibre edilmiş mutlak "orta" eşiğin altında kalan pencere oranı — gerçek ve
kontrol için ayrı.

    python -m tools.emerging_test --timeframes 1d 4h
"""

from __future__ import annotations

import argparse
import json
import logging
import time

import numpy as np

from engine.config import (
    CONFIDENCE_LEVEL,
    DATA_DIR,
    N_POINTS,
    OUTCOME_TOLERANCE,
    SAKOE_CHIBA_RADIUS,
    STAGE2_METRIC,
    TOLERANCE_THRESHOLDS_BY_METRIC,
)
from engine.fingerprint import provenance
from engine.normalize.pipeline import normalize_batch, resample_to, zscore
from engine.outcome.bars import BarStore
from engine.outcome.metrics import bonferroni_level, block_bootstrap_diff_ci, month_of
from engine.search.ddtw import stage2_scores
from engine.search.engine import SearchEngine
from engine.templates import load_all

log = logging.getLogger(__name__)

PREFIX = 0.75
CONTROLS = 20
SEED = 20260911
SCALES = ("prefix", "shape")


def prefix_query(vector: np.ndarray, fraction: float = PREFIX) -> np.ndarray:
    """Şablonun ilk ``fraction`` kadarı → 32 nokta, z-score (K-02)."""
    k = int(round(fraction * N_POINTS))
    head = resample_to(np.asarray(vector, dtype=np.float64)[:k], N_POINTS)
    z = zscore(head)
    if z is None:
        raise ValueError("önek düz")
    return z


def remaining_bars(prefix_len: int, fraction: float = PREFIX) -> int:
    return int(round(prefix_len * (1.0 - fraction) / fraction))


class DonorPool:
    """Aynı aydan, başka sembolden devam getirisi çeken havuz (K-12)."""

    def __init__(self, store: BarStore, rng: np.random.Generator) -> None:
        self.store = store
        self.rng = rng
        self.months: dict[int, list[tuple[int, int, int]]] = {}
        for sid, off in store.offset.items():
            n = store.n_bars[sid]
            keys = month_of(store.open_time[off : off + n])
            change = np.flatnonzero(np.diff(keys)) + 1
            starts = np.concatenate([[0], change])
            ends = np.concatenate([change, [n]])
            for a, b in zip(starts, ends):
                self.months.setdefault(int(keys[a]), []).append((int(sid), int(a), int(b)))

    def draw(self, month: int, exclude_sid: int, horizon: int, k: int) -> np.ndarray:
        """(k, horizon) log getiri; bulunamayan satırlar NaN."""
        out = np.full((k, horizon), np.nan)
        spans = [s for s in self.months.get(month, []) if s[0] != exclude_sid and s[2] - s[1] > 1]
        if not spans:
            return out
        st = self.store
        filled = 0
        for _ in range(k * 6):
            if filled == k:
                break
            sid, a, b = spans[int(self.rng.integers(len(spans)))]
            t = a + int(self.rng.integers(b - a))
            n = st.n_bars[sid]
            if t + horizon >= n:
                continue
            off = st.offset[sid]
            c = st.close[off + t : off + t + horizon + 1]
            if np.any(c <= 0) or st.jump[off + t + 1 : off + t + horizon + 1].any():
                continue
            lr = np.diff(np.log(c))
            if not np.all(np.isfinite(lr)) or lr.std() == 0:
                continue
            out[filled] = lr
            filled += 1
        return out


def score_event(
    full: np.ndarray,
    closes: np.ndarray,
    prefix_len: int,
    donor_lr: np.ndarray,
    threshold: float,
) -> dict | None:
    """Tek olay: gerçek devam, kontrol devamlarından tam şablona daha mı yakın?

    ``closes``: önek + gerçek devam (``prefix_len + R`` bar). ``donor_lr``:
    (k, R) kontrol log getirileri. Döner: ölçek başına ``(skor, kontrolde
    tamamlanma oranı)`` ve gerçekte tamamlandı mı; ölçülemezse None.
    """
    L = prefix_len
    prefix_lr = np.diff(np.log(closes[:L]))
    real_lr = np.diff(np.log(closes[L - 1 :]))
    if prefix_lr.std() == 0 or real_lr.std() == 0 or donor_lr.shape[0] == 0:
        return None
    vec_real, valid = normalize_batch(closes[None, :])
    if not valid[0]:
        return None
    d_real = float(stage2_scores(full, vec_real, SAKOE_CHIBA_RADIUS, STAGE2_METRIC)[0])

    c0 = closes[L - 1]
    out: dict = {"complete": float(d_real <= threshold)}
    for scale in SCALES:
        target = prefix_lr.std() if scale == "prefix" else real_lr.std()
        lr = donor_lr * (target / donor_lr.std(axis=1, keepdims=True))
        tails = c0 * np.exp(np.cumsum(lr, axis=1))
        paths = np.concatenate([np.broadcast_to(closes[:L], (tails.shape[0], L)), tails], axis=1)
        vecs, ok = normalize_batch(paths)
        d_ctrl = stage2_scores(full, vecs[ok], SAKOE_CHIBA_RADIUS, STAGE2_METRIC)
        if d_ctrl.size == 0:
            return None
        out[scale] = (
            float(np.mean((d_real < d_ctrl) + 0.5 * (d_real == d_ctrl))),
            float(np.mean(d_ctrl <= threshold)),
        )
    return out


def measure_template(
    engine: SearchEngine,
    store: BarStore,
    donors: DonorPool,
    template_id: str,
    vector: np.ndarray,
    timeframe: str,
    controls: int = CONTROLS,
) -> dict:
    full = np.asarray(vector, dtype=np.float64)
    result = engine.search(
        prefix_query(full), timeframe=timeframe, tolerance=OUTCOME_TOLERANCE, limit=5_000
    )
    thr = TOLERANCE_THRESHOLDS_BY_METRIC[STAGE2_METRIC]["medium"]

    scores: dict[str, list[float]] = {s: [] for s in SCALES}
    ctrl_done: dict[str, list[float]] = {s: [] for s in SCALES}
    real_done: list[float] = []
    months: list[int] = []

    for m in result.results:
        sid, t0, L = int(m.symbol_id), int(m.end_idx), int(m.window_length)
        R = remaining_bars(L)
        if not store.has(sid) or t0 - L + 1 < 0 or t0 + R >= store.n_bars[sid]:
            continue
        off = store.offset[sid]
        closes = store.close[off + t0 - L + 1 : off + t0 + R + 1]
        # Pencere içinde fiyat sıçraması (redenominasyon) varsa şekil yoktur.
        if np.any(closes <= 0) or store.jump[off + t0 - L + 2 : off + t0 + R + 1].any():
            continue
        month = int(month_of(np.array([m.end_time]))[0])
        donor = donors.draw(month, sid, R, controls)
        donor = donor[np.all(np.isfinite(donor), axis=1)]
        if donor.shape[0] < controls // 2:
            continue
        ev = score_event(full, closes, L, donor, thr)
        if ev is None:
            continue
        real_done.append(ev["complete"])
        months.append(month)
        for scale in SCALES:
            scores[scale].append(ev[scale][0])
            ctrl_done[scale].append(ev[scale][1])

    report: dict = {
        "template": template_id,
        "timeframe": timeframe,
        "matches": len(result.results),
        "events": len(months),
        "completion_real": float(np.mean(real_done)) if real_done else None,
        "_months": months,
    }
    for scale in SCALES:
        arr = np.asarray(scores[scale])
        report[scale] = {
            "auc": float(arr.mean()) if arr.size else None,
            "completion_control": float(np.mean(ctrl_done[scale])) if ctrl_done[scale] else None,
            "_scores": arr.tolist(),
        }
    return report


def add_intervals(reports: list[dict], confidence: float) -> None:
    rng = np.random.default_rng(SEED)
    for rep in reports:
        months = np.asarray(rep["_months"])
        for scale in SCALES:
            scores = np.asarray(rep[scale]["_scores"])
            if scores.size < 20:
                rep[scale][f"ci_{confidence}"] = None
                continue
            (lo, hi), design = block_bootstrap_diff_ci(
                scores, months, np.full(scores.size, 0.5), months, confidence=confidence, rng=rng
            )
            rep[scale][f"ci_{confidence}"] = [0.5 + lo, 0.5 + hi]
            rep[scale]["design_effect"] = design


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--timeframes", nargs="+", default=["1d", "4h"])
    p.add_argument("--templates", nargs="+", default=None)
    p.add_argument("--controls", type=int, default=CONTROLS)
    p.add_argument("--log-level", default="INFO")
    args = p.parse_args(argv)
    logging.basicConfig(level=args.log_level.upper(), format="%(asctime)s %(message)s")
    logging.getLogger("engine").setLevel(logging.WARNING)

    templates = load_all()
    chosen = args.templates or sorted(templates)
    family = len(chosen) * len(SCALES)
    level = bonferroni_level(family)
    engine = SearchEngine()
    out: dict = {"prefix": PREFIX, "controls": args.controls, "family": family,
                 "bonferroni_level": level, "reports": {}, "provenance": {}}

    for tf in args.timeframes:
        symbols = engine.symbols_for(tf)
        store = BarStore.from_klines(list(symbols.values()), tf, {n: i for i, n in symbols.items()})
        donors = DonorPool(store, np.random.default_rng(SEED))
        reports = []
        for tid in chosen:
            t0 = time.time()
            rep = measure_template(engine, store, donors, tid, templates[tid].vector, tf, args.controls)
            reports.append(rep)
            log.info("%s %s: %d eşleşme, %d olay (%.0f sn)", tf, tid, rep["matches"], rep["events"], time.time() - t0)
        add_intervals(reports, CONFIDENCE_LEVEL)
        add_intervals(reports, level)
        for rep in reports:
            rep.pop("_months", None)
            for scale in SCALES:
                rep[scale].pop("_scores", None)
        out["reports"][tf] = reports
        out["provenance"][tf] = provenance(tf)

    path = DATA_DIR / "f3" / "emerging_test.json"
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")

    def sig(ci):
        return ci is not None and (ci[0] > 0.5 or ci[1] < 0.5)

    for tf, reports in out["reports"].items():
        print(f"\n{tf} — önek %{int(PREFIX * 100)}, {args.controls} kontrol/olay")
        print(f"{'şablon':24s} {'olay':>5s}  {'tamam gerçek':>12s}  " + "  ".join(
            f"{s:>6s} AUC [%95] tamam-k  B" for s in SCALES))
        for rep in reports:
            cells = []
            for s in SCALES:
                r = rep[s]
                ci = r.get(f"ci_{CONFIDENCE_LEVEL}")
                cib = r.get(f"ci_{level}")
                auc = r["auc"]
                cells.append(
                    f"{auc if auc is not None else float('nan'):.3f} "
                    f"[{ci[0]:.3f};{ci[1]:.3f}]{'*' if sig(ci) else ' '} "
                    f"{(r['completion_control'] or 0):.2f} {'B' if sig(cib) else ' '}"
                    if ci else f"{'—':>24s}"
                )
            comp = rep["completion_real"]
            print(f"{rep['template']:24s} {rep['events']:5d}  {comp if comp is not None else float('nan'):12.2f}  " + "  ".join(cells))
    print(f"\nyazıldı: {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
