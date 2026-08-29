"""Bir zaman dilimini, başka bir zaman diliminin evrenine kadar tamamlar.

**Neden gerekti:** 4h evreni 80 sembolde kalmıştı, 1d evreni 1.165. Arayüzün
varsayılanı ise 4h. Yani kullanıcı, sistemin kalibre edildiği korpusun
%7'sinde arama yapıyordu — motor "kötü sonuç" vermiyordu, *bakacak yeri*
yoktu. F3/F4 ölçümlerinin tamamı 1d'de yapıldığı için bu fark ölçüme de
yansımamıştı.

REST yerine **arşiv** (data.binance.vision) kullanılır: delist edilmiş
pariteler REST'te görünmez ve onları atlamak K-13'ün survivorship bias
düzeltmesini sessizce geri alır.

    python -m tools.backfill --timeframe 4h
    python -m tools.backfill --timeframe 4h --from-timeframe 1d --limit 50
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from engine.config import HISTORY_START_MS, KLINES_DIR, TIMEFRAME_MS, VISION_MAX_WORKERS
from engine.ingest.store import last_open_time
from engine.ingest.vision_archive import download_symbol, make_session

log = logging.getLogger("tools.backfill")


def symbols_of(timeframe: str, root: Path | None = None) -> list[str]:
    """Depoda o zaman dilimi için parquet'i bulunan semboller."""
    directory = Path(root or KLINES_DIR) / timeframe
    if not directory.exists():
        return []
    return sorted(p.stem for p in directory.glob("*.parquet"))


def missing_symbols(target: str, source: str, root: Path | None = None) -> list[str]:
    """Kaynakta olup hedefte olmayan semboller."""
    have = set(symbols_of(target, root))
    return [s for s in symbols_of(source, root) if s not in have]


def backfill(
    timeframe: str,
    from_timeframe: str = "1d",
    limit: int | None = None,
    root: Path | None = None,
    workers: int = VISION_MAX_WORKERS,
    include_existing: bool = False,
) -> dict[str, int]:
    """Eksik sembolleri arşivden indirir; sembol -> yazılan bar sayısı."""
    if include_existing:
        targets = symbols_of(from_timeframe, root)
    else:
        targets = missing_symbols(timeframe, from_timeframe, root)
    if limit is not None:
        targets = targets[:limit]

    log.info(
        "%s: %d sembol indirilecek (%s evreninden, %d zaten var)",
        timeframe,
        len(targets),
        from_timeframe,
        len(symbols_of(timeframe, root)),
    )

    session = make_session(workers)
    written: dict[str, int] = {}
    started = time.time()

    for i, symbol in enumerate(targets, 1):
        try:
            n = download_symbol(
                symbol, timeframe, HISTORY_START_MS, None, root, session, workers
            )
        except Exception as exc:  # tek sembol tüm koşuyu durdurmasın
            log.error("%s: %s", symbol, exc)
            n = 0
        written[symbol] = n

        if i % 25 == 0 or i == len(targets):
            elapsed = time.time() - started
            rate = i / max(elapsed, 1e-9)
            remaining = (len(targets) - i) / max(rate, 1e-9)
            log.info(
                "[%d/%d] %s +%d bar · %.1f sembol/dk · kalan ~%.0f dk · toplam %d bar",
                i,
                len(targets),
                symbol,
                n,
                rate * 60,
                remaining / 60,
                sum(written.values()),
            )

    return written


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--timeframe", required=True, choices=list(TIMEFRAME_MS))
    p.add_argument("--from-timeframe", default="1d", choices=list(TIMEFRAME_MS))
    p.add_argument("--limit", type=int, default=None, help="İlk N sembolle sınırla")
    p.add_argument("--workers", type=int, default=VISION_MAX_WORKERS)
    p.add_argument(
        "--include-existing",
        action="store_true",
        help="Mevcut sembolleri de tazele (varsayılan: yalnız eksikler)",
    )
    p.add_argument("--data-root", default=None)
    p.add_argument("--log-level", default="INFO")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    root = Path(args.data_root) if args.data_root else None

    written = backfill(
        args.timeframe,
        args.from_timeframe,
        args.limit,
        root,
        args.workers,
        args.include_existing,
    )
    total = sum(written.values())
    got = sum(1 for v in written.values() if v > 0)
    log.info("bitti: %d sembolden %d'ine veri geldi, toplam %d bar", len(written), got, total)
    log.info("sonraki adım: python -m engine.matrix.build --timeframes %s", args.timeframe)
    return 0


if __name__ == "__main__":
    sys.exit(main())
