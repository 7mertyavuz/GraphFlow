"""Aşama 1 doğrulaması: matris gerçekten en iyi pencereleri mi taşıyor?

İki bağımsız soru sorulur, ikisi de **kaba kuvvetle** yanıtlanır:

1. **Bütünlük.** Matristeki vektör, Parquet'ten yeniden hesaplananla birebir
   aynı mı? Bu projeyi iki kez ısıran hata sınıfı tam olarak buydu:
   mikrosaniye damgası 19 aylık veriyi ve zaman dilimi başına sembol haritası
   1d koşusunu **sıfır hata mesajıyla** yok etti. Sessiz bozulmanın tek
   panzehiri, aynı sayıyı ikinci bir yoldan üretip karşılaştırmaktır.

2. **Stride maliyeti.** Matris ``STRIDE = 3`` ile kurulur; kaba kuvvet
   ``stride = 1``'dir. Aradaki en iyi skor farkı, hız için ödenen doğruluk
   bedelidir. Ölçülmemiş bir bedel, bedel değil varsayımdır.

Kaba kuvvet **üretim kod yolunu** kullanır (``build_symbol_rows``, stride=1):
zaman sürekliliği, fiyat sürekliliği ve düz pencere invariant'ları aynen
uygulanır. Ayrı bir referans uygulaması yazmak, iki uygulamanın farkını
"hata" sanma riskini getirirdi.

    python -m tools.verify_stage1 --timeframe 1d --symbols 12
    python -m tools.verify_stage1 --timeframe 4h --template head_and_shoulders
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np

from engine.config import N_POINTS, STRIDE, WINDOW_LENGTHS
from engine.ingest.store import read_klines
from engine.matrix.build import META_FILE, VECTORS_FILE, build_symbol_rows, matrix_dir
from engine.matrix.npy_store import load_matrix
from engine.search.engine import SearchEngine
from engine.search.stage1_cosine import prepare_query

log = logging.getLogger("tools.verify_stage1")


def brute_force(df, symbol: str, symbol_id: int, length: int, timeframe: str, query: np.ndarray):
    """stride=1 tarama. ``(en_iyi_skor, en_iyi_start, pencere_sayısı, vektörler)``."""
    best_score, best_start, total = -np.inf, -1, 0
    by_start: dict[int, np.ndarray] = {}

    for vectors, meta in build_symbol_rows(
        df, symbol, symbol_id, length, timeframe, liquidity=None, stride=1
    ):
        if vectors.size == 0:
            continue
        scores = (np.asarray(vectors, dtype=np.float32) @ query) / np.float32(N_POINTS)
        total += scores.size
        for v, m in zip(vectors, meta):
            by_start[int(m["start_idx"])] = np.asarray(v)
        i = int(np.argmax(scores))
        if float(scores[i]) > best_score:
            best_score = float(scores[i])
            best_start = int(meta["start_idx"][i])

    return best_score, best_start, total, by_start


def verify(
    timeframe: str = "1d",
    n_symbols: int = 12,
    template_id: str | None = None,
    lengths=WINDOW_LENGTHS,
    seed: int = 20260829,
    matrix_root: Path | None = None,
) -> dict:
    """Bütünlük ve stride maliyeti raporu."""
    from engine.templates import load_all

    engine = SearchEngine(matrix_root)
    symbols = engine.symbols_for(timeframe)
    if not symbols:
        raise SystemExit(f"{timeframe} için sembol haritası yok")

    templates = load_all()
    tid = template_id or "head_and_shoulders"
    if tid not in templates:
        raise SystemExit(f"bilinmeyen şablon: {tid}")
    query = prepare_query(np.asarray(templates[tid].vector, dtype=np.float64))

    rng = np.random.default_rng(seed)
    ids = sorted(symbols)
    picked = [int(i) for i in rng.choice(ids, size=min(n_symbols, len(ids)), replace=False)]

    mismatches: list[str] = []
    checked_vectors = 0
    gaps: list[float] = []
    rows_bf = rows_mx = 0

    for length in lengths:
        d = matrix_dir(timeframe, length, matrix_root)
        if not (d / META_FILE).exists():
            log.warning("%s_%d matrisi yok, atlanıyor", timeframe, length)
            continue
        meta = np.asarray(load_matrix(d / META_FILE))
        vecs = load_matrix(d / VECTORS_FILE)

        for sid in picked:
            symbol = symbols[sid]
            df = read_klines(symbol, timeframe)
            if df.empty:
                continue

            sel = np.flatnonzero(meta["symbol_id"] == sid)
            if sel.size == 0:
                continue

            bf_score, bf_start, bf_n, bf_by_start = brute_force(
                df, symbol, sid, length, timeframe, query
            )
            if bf_n == 0:
                continue

            # --- 1) Bütünlük: matris satırı == Parquet'ten yeniden hesap ----
            sample = sel if sel.size <= 8 else rng.choice(sel, size=8, replace=False)
            for row in sample:
                start = int(meta["start_idx"][row])
                expected = bf_by_start.get(start)
                if expected is None:
                    mismatches.append(
                        f"{symbol} L={length} start={start}: matriste var, "
                        "stride=1 taramasında yok (invariant ayrışması)"
                    )
                    continue
                stored = np.asarray(vecs[row], dtype=np.float64)
                if not np.allclose(stored, expected, atol=1e-5):
                    delta = float(np.max(np.abs(stored - expected)))
                    mismatches.append(f"{symbol} L={length} start={start}: vektör farkı {delta:.2e}")
                checked_vectors += 1

            # --- 2) Stride maliyeti ---------------------------------------
            mx_scores = (np.asarray(vecs[sel], dtype=np.float32) @ query) / np.float32(N_POINTS)
            mx_best = float(mx_scores.max())
            gaps.append(bf_score - mx_best)
            rows_bf += bf_n
            rows_mx += int(sel.size)

            log.debug(
                "%s L=%d: kaba %0.4f @%d · matris %0.4f · fark %+.4f",
                symbol, length, bf_score, bf_start, mx_best, bf_score - mx_best,
            )

    gap_arr = np.asarray(gaps, dtype=np.float64)
    report = {
        "timeframe": timeframe,
        "template": tid,
        "symbols": len(picked),
        "checked_vectors": checked_vectors,
        "mismatches": mismatches,
        "comparisons": int(gap_arr.size),
        "rows_bruteforce": rows_bf,
        "rows_matrix": rows_mx,
        "gap_mean": float(gap_arr.mean()) if gap_arr.size else float("nan"),
        "gap_max": float(gap_arr.max()) if gap_arr.size else float("nan"),
        "gap_p95": float(np.quantile(gap_arr, 0.95)) if gap_arr.size else float("nan"),
    }
    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--timeframe", default="1d")
    p.add_argument("--symbols", type=int, default=12)
    p.add_argument("--template", default=None)
    p.add_argument("--lengths", type=int, nargs="+", default=list(WINDOW_LENGTHS))
    p.add_argument("--log-level", default="INFO")
    args = p.parse_args(argv)

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(message)s")
    r = verify(args.timeframe, args.symbols, args.template, args.lengths)

    print()
    print(f"Zaman dilimi     : {r['timeframe']}   şablon: {r['template']}")
    print(f"Sembol           : {r['symbols']}")
    print(f"Taranan pencere  : kaba kuvvet {r['rows_bruteforce']:,} · matris {r['rows_matrix']:,}"
          f"  (stride {STRIDE})")
    print()
    print(f"1) BÜTÜNLÜK      : {r['checked_vectors']} vektör Parquet'ten yeniden hesaplandı")
    if r["mismatches"]:
        print(f"   ❌ {len(r['mismatches'])} UYUŞMAZLIK:")
        for m in r["mismatches"][:20]:
            print(f"      {m}")
    else:
        print("   ✅ tamamı birebir aynı")
    print()
    print(f"2) STRIDE BEDELİ : {r['comparisons']} karşılaştırma (kosinüs skoru farkı)")
    print(f"   ortalama {r['gap_mean']:+.5f} · %95 {r['gap_p95']:+.5f} · en kötü {r['gap_max']:+.5f}")
    print()
    return 1 if r["mismatches"] else 0


if __name__ == "__main__":
    sys.exit(main())
