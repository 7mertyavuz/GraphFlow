"""F0 CLI giriş noktası:  ``python -m engine.ingest.download``

Akış:

1. Sembol evrenini tazele (delist edilenler dahil — K-13)
2. Her (timeframe, symbol) için Parquet'teki son bardan itibaren devam et
3. Sayfa sayfa indir, ``INGEST_FLUSH_PAGES``'te bir atomik olarak yaz
4. Durumu ``data/meta/ingest_state.json``'a yaz → kesintiden devam

**Yarım mum indirilmez** (K-05 / K-15): yalnızca ``close_time`` şu andan küçük
olan, yani kapanmış mumlar saklanır. Kapanmamış mumu diske yazmak, bir sonraki
çalıştırmada değişen bir "geçmiş" üretir ve matrisi kirletir.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from engine.config import (
    HISTORY_START_MS,
    INGEST_FLUSH_PAGES,
    INGEST_STATE_FILE,
    KLINES_DIR,
    QUOTE_ASSETS,
    TIMEFRAME_MS,
    TIMEFRAMES,
)
from engine.ingest.binance_client import BinanceClient, UnknownSymbolError
from engine.ingest.store import (
    append_klines,
    last_open_time,
    read_json,
    write_json_atomic,
)
from engine.ingest.symbol_universe import load_universe, refresh_universe

log = logging.getLogger("engine.ingest.download")


# ---------------------------------------------------------------------------
# Durum dosyası (resume)
# ---------------------------------------------------------------------------


def load_state(path: Path | None = None) -> dict[str, Any]:
    return read_json(Path(path or INGEST_STATE_FILE), default={}) or {}


def save_state(state: dict[str, Any], path: Path | None = None) -> None:
    write_json_atomic(state, Path(path or INGEST_STATE_FILE))


def _entry(state: dict[str, Any], timeframe: str, symbol: str) -> dict[str, Any]:
    return state.setdefault(timeframe, {}).setdefault(symbol, {})


# ---------------------------------------------------------------------------
# Tek sembol indirme
# ---------------------------------------------------------------------------


def download_symbol(
    client: BinanceClient,
    symbol: str,
    timeframe: str,
    now_ms: int,
    start_ms: int = HISTORY_START_MS,
    root: Path | None = None,
    flush_pages: int = INGEST_FLUSH_PAGES,
) -> int:
    """Bir sembolün eksik barlarını indirir; yazılan yeni bar sayısını döner.

    Devam noktası Parquet dosyasının kendisinden okunur — ayrı bir durum
    dosyasına güvenilmez, böylece durum dosyası kaybolsa da tekrar indirme
    yapılmaz.
    """
    step = TIMEFRAME_MS[timeframe]
    last = last_open_time(symbol, timeframe, root)
    cursor = start_ms if last is None else last + step

    # Kapanmamış mumu hiç istemiyoruz: son KAPANMIŞ barın açılışı.
    last_closed_open = ((now_ms // step) * step) - step
    if cursor > last_closed_open:
        return 0

    written = 0
    buffer: list = []
    pages = 0

    for page in client.iter_klines(symbol, timeframe, start_time=cursor, end_time=now_ms):
        closed = [k for k in page if k.close_time < now_ms]
        buffer.extend(closed)
        pages += 1

        if pages % flush_pages == 0 and buffer:
            written += append_klines(symbol, timeframe, buffer, root)
            buffer = []

        if len(closed) < len(page):  # yarım muma ulaşıldı → bitti
            break

    if buffer:
        written += append_klines(symbol, timeframe, buffer, root)
    return written


# ---------------------------------------------------------------------------
# Toplu indirme
# ---------------------------------------------------------------------------


def download_all(
    client: BinanceClient,
    symbols: Iterable[str],
    timeframes: Iterable[str] = TIMEFRAMES,
    start_ms: int = HISTORY_START_MS,
    root: Path | None = None,
    state_path: Path | None = None,
    now_ms: int | None = None,
    retry_failed: bool = False,
) -> dict[str, Any]:
    symbols = list(symbols)
    timeframes = list(timeframes)
    state = load_state(state_path)
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)

    total_written = 0
    for timeframe in timeframes:
        for i, symbol in enumerate(symbols, 1):
            entry = _entry(state, timeframe, symbol)
            if entry.get("status") == "unknown_symbol" and not retry_failed:
                continue

            try:
                written = download_symbol(
                    client, symbol, timeframe, now_ms=now_ms, start_ms=start_ms, root=root
                )
                entry["status"] = "ok"
            except UnknownSymbolError:
                # Delist edilmiş parite REST'te yok — arşiv verisi ayrı bir yoldan
                # gelmelidir; süreci durdurmaz.
                log.warning("%s %s: sembol REST'te yok (delist?)", symbol, timeframe)
                entry["status"] = "unknown_symbol"
                written = 0
            except KeyboardInterrupt:
                save_state(state, state_path)
                raise
            except Exception as exc:
                log.error("%s %s: %s", symbol, timeframe, exc)
                entry["status"] = "error"
                entry["error"] = str(exc)
                written = 0

            entry["last_open_time"] = last_open_time(symbol, timeframe, root)
            entry["updated_at"] = now_ms
            total_written += written

            if written:
                log.info("[%s %d/%d] %s +%d bar", timeframe, i, len(symbols), symbol, written)
            if i % 10 == 0:
                save_state(state, state_path)

    save_state(state, state_path)
    log.info("Toplam %d yeni bar yazıldı", total_written)
    return state


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_time(value: str) -> int:
    """ISO tarih ('2017-08-17') veya ms damgası kabul eder."""
    if value.isdigit():
        return int(value)
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m engine.ingest.download",
        description="Binance klines indirici (F0). Kesintiden devam edebilir.",
    )
    p.add_argument("--timeframes", nargs="+", default=list(TIMEFRAMES), choices=list(TIMEFRAME_MS))
    p.add_argument("--symbols", nargs="+", default=None, help="Belirtilmezse evrenin tamamı")
    p.add_argument("--quote", nargs="+", default=list(QUOTE_ASSETS), help="Kote varlık filtresi")
    p.add_argument("--start", default=str(HISTORY_START_MS), help="ISO tarih veya ms")
    p.add_argument("--limit-symbols", type=int, default=None, help="İlk N sembolle sınırla")
    p.add_argument("--data-root", default=str(KLINES_DIR))
    p.add_argument("--skip-universe", action="store_true", help="Evreni tazeleme, dosyadan oku")
    p.add_argument("--no-archive", action="store_true", help="data.binance.vision listesini atla")
    p.add_argument("--retry-failed", action="store_true")
    p.add_argument("--log-level", default="INFO")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    client = BinanceClient()

    if args.symbols:
        symbols = list(args.symbols)
    else:
        universe = (
            load_universe()
            if args.skip_universe
            else refresh_universe(client, use_archive=not args.no_archive)
        )
        if not universe:
            log.error("Sembol evreni boş. Önce --skip-universe olmadan çalıştırın.")
            return 1
        quotes = set(args.quote)
        symbols = [r["symbol"] for r in universe if r.get("quote_asset") in quotes]

    if args.limit_symbols:
        symbols = symbols[: args.limit_symbols]

    log.info("%d sembol × %s zaman dilimi indirilecek", len(symbols), args.timeframes)
    download_all(
        client,
        symbols,
        timeframes=args.timeframes,
        start_ms=parse_time(args.start),
        root=Path(args.data_root),
        retry_failed=args.retry_failed,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
