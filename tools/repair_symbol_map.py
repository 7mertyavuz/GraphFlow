"""Matris sembol haritasını yeniden kurar ve **doğrular**.

Neden gerekti: ``symbols.json`` zaman dilimlerinden bağımsız tek bir dosyaydı,
oysa ``symbol_id`` uzayı zaman dilimi başınadır (4h evreni likit alt kümedir,
1d evreni tüm geçmişi kapsar). Son inşa edilen dilimin haritası diğerini
eziyordu; 1d eşleşmeleri sembol adı yerine ``#897`` olarak görünüyordu.

Matrisleri yeniden inşa etmeye gerek yok: id ataması, ``build_all``'ın kuralı
gereği **sabitlenmiş pariteler elendikten sonraki sembol listesindeki sıra**dır.
Bu araç o sırayı yeniden üretir, ama körlemesine yazmaz — yazmadan önce
rastgele satırlarda matristeki vektörü ilgili sembolün Parquet verisinden
yeniden hesaplayıp karşılaştırır. Doğrulama geçmezse dosya yazılmaz:
yanlış etiketlenmiş bir grafik, etiketsiz bir grafikten daha kötüdür.

Kullanım:

    python -m tools.repair_symbol_map            # doğrula ve yaz
    python -m tools.repair_symbol_map --dry-run  # yalnızca doğrula
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np

from engine.config import MATRIX_DIR, TIMEFRAMES, WINDOW_LENGTHS
from engine.ingest.store import available_symbols, read_klines, write_json_atomic
from engine.matrix.build import META_FILE, VECTORS_FILE, matrix_dir, symbols_file
from engine.matrix.npy_store import load_matrix
from engine.matrix.universe_filter import filter_universe
from engine.normalize.pipeline import normalize_window

log = logging.getLogger(__name__)

#: Zaman dilimi başına doğrulanacak rastgele satır sayısı.
SAMPLE_ROWS = 12
SEED = 20260813


def rebuild_map(timeframe: str, klines_root: Path | None = None) -> dict[str, int]:
    """``sembol → symbol_id`` — build_all ile birebir aynı sıra."""
    symbols = available_symbols(timeframe, klines_root)
    kept, _pegged = filter_universe(symbols, timeframe, klines_root)
    return {symbol: index for index, symbol in enumerate(kept)}


def verify(
    timeframe: str,
    mapping: dict[str, int],
    matrix_root: Path | None = None,
    klines_root: Path | None = None,
    sample: int = SAMPLE_ROWS,
) -> tuple[int, int]:
    """Rastgele satırlarda vektörü Parquet'ten yeniden hesaplayıp karşılaştırır.

    Döner: ``(doğrulanan, denenen)``.
    """
    by_id = {sid: symbol for symbol, sid in mapping.items()}
    rng = np.random.default_rng(SEED)
    checked = passed = 0

    for length in WINDOW_LENGTHS:
        directory = matrix_dir(timeframe, length, matrix_root)
        if not (directory / META_FILE).exists():
            continue

        meta = np.asarray(load_matrix(directory / META_FILE))
        vectors = load_matrix(directory / VECTORS_FILE)
        if meta.shape[0] == 0:
            continue

        unknown = set(np.unique(meta["symbol_id"]).tolist()) - set(by_id)
        if unknown:
            log.error(
                "%s_%d: haritada olmayan %d symbol_id (ör. %s)",
                timeframe, length, len(unknown), sorted(unknown)[:5],
            )
            return passed, checked + 1

        rows = rng.choice(meta.shape[0], size=min(sample, meta.shape[0]), replace=False)
        for row in rows:
            record = meta[int(row)]
            symbol = by_id[int(record["symbol_id"])]
            frame = read_klines(symbol, timeframe, klines_root)
            close = frame["close"].to_numpy()[int(record["start_idx"]) : int(record["end_idx"]) + 1]
            rebuilt = normalize_window(close)
            checked += 1
            if rebuilt is not None and np.allclose(rebuilt, np.asarray(vectors[int(row)]), atol=1e-4):
                passed += 1
            else:
                log.error(
                    "%s_%d satır %d: %s ile eşleşmedi (start=%d)",
                    timeframe, length, row, symbol, record["start_idx"],
                )
    return passed, checked


def repair(
    matrix_root: Path | None = None,
    klines_root: Path | None = None,
    dry_run: bool = False,
) -> dict[str, bool]:
    root = Path(matrix_root or MATRIX_DIR)
    outcome: dict[str, bool] = {}

    for timeframe in TIMEFRAMES:
        if not any((root / f"{timeframe}_{length}").exists() for length in WINDOW_LENGTHS):
            log.info("%s: matris yok, atlanıyor", timeframe)
            continue

        mapping = rebuild_map(timeframe, klines_root)
        passed, checked = verify(timeframe, mapping, root, klines_root)
        ok = checked > 0 and passed == checked
        outcome[timeframe] = ok

        log.info("%s: %d sembol, doğrulama %d/%d", timeframe, len(mapping), passed, checked)
        if not ok:
            log.error("%s: doğrulama başarısız — harita YAZILMADI", timeframe)
            continue
        if dry_run:
            log.info("%s: --dry-run, yazılmadı", timeframe)
            continue

        write_json_atomic(mapping, root / symbols_file(timeframe))
        log.info("%s → %s", timeframe, symbols_file(timeframe))

    return outcome


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="yalnızca doğrula")
    parser.add_argument("--matrix-root", type=Path, default=None)
    parser.add_argument("--klines-root", type=Path, default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    outcome = repair(args.matrix_root, args.klines_root, args.dry_run)
    return 0 if outcome and all(outcome.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
