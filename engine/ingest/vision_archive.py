"""data.binance.vision arşivinden gerçek OHLCV indirici.

**Neden REST değil:** `api.binance.com` her ağdan erişilebilir değildir
(bölgesel engel / bağlantı sıfırlama). Arşiv, aynı verinin resmî dökümüdür ve
K-13 açısından **daha iyidir**: `exchangeInfo`'da görünmeyen delist edilmiş
pariteler arşivde durur (LUNAUSDT'nin Mayıs 2022 çöküşü dahil).

Yapı:

* Aylık ZIP'ler tam aylar için (`.../monthly/klines/{sym}/{tf}/...`)
* İçinde bulunulan (tamamlanmamış) ay için günlük ZIP'ler
* Her ZIP, REST `/klines` ile **birebir aynı 12 sütunlu** CSV'dir

Kapanmamış mum diske yazılmaz (K-05 / K-15): `close_time >= now` olan bar
düşürülür. Kesintiden devam Parquet'in kendisinden okunur — ayrı durum
dosyasına güvenilmez.
"""

from __future__ import annotations

import io
import logging
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Sequence

import requests

from engine.config import (
    BINANCE_VISION_S3,
    EPOCH_US_THRESHOLD,
    HISTORY_START_MS,
    MAX_RETRIES,
    REQUEST_TIMEOUT_SEC,
    RETRY_BACKOFF_BASE_SEC,
    RETRY_BACKOFF_FACTOR,
    RETRY_BACKOFF_MAX_SEC,
    TIMEFRAME_MS,
    VISION_DAILY_PATH,
    VISION_MAX_WORKERS,
    VISION_MONTHLY_PATH,
)
from engine.ingest.binance_client import Kline
from engine.ingest.store import append_klines, last_open_time

log = logging.getLogger(__name__)

DAY_MS = 86_400_000


def make_session(workers: int = VISION_MAX_WORKERS) -> requests.Session:
    """Havuz boyutu iş parçacığı sayısına eşit oturum (bağlantı israfını önler)."""
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=workers, pool_maxsize=workers)
    session.mount("https://", adapter)
    return session


@dataclass(frozen=True)
class ArchiveFile:
    """İndirilecek tek bir arşiv dosyası."""

    symbol: str
    interval: str
    url: str
    period_start_ms: int
    period_end_ms: int  # dahil değil


# ---------------------------------------------------------------------------
# Dosya listesi üretimi
# ---------------------------------------------------------------------------


def _month_bounds(year: int, month: int) -> tuple[int, int]:
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    end = datetime(year + (month == 12), (month % 12) + 1, 1, tzinfo=timezone.utc)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def archive_files(
    symbol: str,
    interval: str,
    start_ms: int = HISTORY_START_MS,
    end_ms: int | None = None,
) -> list[ArchiveFile]:
    """Kapsanacak aylık dosyalar + içinde bulunulan ay için günlük dosyalar."""
    end_ms = end_ms if end_ms is not None else int(time.time() * 1000)
    start_dt = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
    end_dt = datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc)

    files: list[ArchiveFile] = []
    year, month = start_dt.year, start_dt.month
    while (year, month) <= (end_dt.year, end_dt.month):
        m_start, m_end = _month_bounds(year, month)
        current_month = (year, month) == (end_dt.year, end_dt.month)

        if current_month:
            # Aylık dosya ancak ay bittiğinde yayımlanır → günlük dosyalar.
            day = m_start
            while day < min(m_end, end_ms):
                d = datetime.fromtimestamp(day / 1000, tz=timezone.utc)
                files.append(
                    ArchiveFile(
                        symbol,
                        interval,
                        f"{BINANCE_VISION_S3}/"
                        + VISION_DAILY_PATH.format(
                            symbol=symbol, interval=interval, year=d.year, month=d.month, day=d.day
                        ),
                        day,
                        day + DAY_MS,
                    )
                )
                day += DAY_MS
        else:
            files.append(
                ArchiveFile(
                    symbol,
                    interval,
                    f"{BINANCE_VISION_S3}/"
                    + VISION_MONTHLY_PATH.format(
                        symbol=symbol, interval=interval, year=year, month=month
                    ),
                    m_start,
                    m_end,
                )
            )

        month += 1
        if month > 12:
            year, month = year + 1, 1

    return [f for f in files if f.period_end_ms > start_ms and f.period_start_ms < end_ms]


# ---------------------------------------------------------------------------
# İndirme ve ayrıştırma
# ---------------------------------------------------------------------------


def to_epoch_ms(value) -> int:
    """Arşiv damgasını milisaniyeye çevirir (2025-01'den itibaren µs).

    Bu dönüşüm olmadan yeni barların ``close_time``'ı bugünün ms damgasından
    ~1000 kat büyük çıkar, "henüz kapanmamış" sanılır ve **sessizce düşer** —
    tam olarak F3 ADIM 0'ın yakaladığı hata buydu (19 aylık veri kaybı).
    """
    v = int(value)
    return v // 1000 if v > EPOCH_US_THRESHOLD else v


def parse_csv_zip(payload: bytes) -> list[Kline]:
    """ZIP içindeki CSV'yi Kline listesine çevirir.

    * Binance bazı dosyalara başlık satırı ekliyor → sayısal olmayan satır atlanır.
    * Zaman damgaları ms/µs karışık olabilir → ``to_epoch_ms`` ile tekilleştirilir.
    """
    out: list[Kline] = []
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        for name in zf.namelist():
            for line in zf.read(name).decode("utf-8").splitlines():
                if not line:
                    continue
                parts = line.split(",")
                try:
                    kline = Kline.from_raw(parts)
                except (ValueError, IndexError):
                    continue  # başlık satırı veya bozuk kayıt
                out.append(
                    replace(
                        kline,
                        open_time=to_epoch_ms(kline.open_time),
                        close_time=to_epoch_ms(kline.close_time),
                    )
                )
    return out


def fetch_file(
    file: ArchiveFile,
    session: requests.Session | None = None,
    max_retries: int = MAX_RETRIES,
    sleep=time.sleep,
) -> list[Kline]:
    """Tek dosyayı indirir. 404 (o ay veri yok) boş liste döner — hata değil."""
    session = session or requests.Session()
    delay = RETRY_BACKOFF_BASE_SEC

    for attempt in range(max_retries):
        try:
            resp = session.get(file.url, timeout=REQUEST_TIMEOUT_SEC)
        except Exception as exc:
            log.debug("ağ hatası %s: %s", file.url, exc)
            sleep(min(delay, RETRY_BACKOFF_MAX_SEC))
            delay *= RETRY_BACKOFF_FACTOR
            continue

        if resp.status_code == 404:
            return []  # parite o ay işlem görmemiş (listelenmemiş/delist)
        if resp.status_code == 200:
            try:
                return parse_csv_zip(resp.content)
            except zipfile.BadZipFile:
                log.warning("bozuk ZIP: %s", file.url)
                return []

        sleep(min(delay, RETRY_BACKOFF_MAX_SEC))
        delay *= RETRY_BACKOFF_FACTOR

    log.warning("%s indirilemedi (%d deneme)", file.url, max_retries)
    return []


def download_symbol(
    symbol: str,
    interval: str,
    start_ms: int = HISTORY_START_MS,
    end_ms: int | None = None,
    root: Path | None = None,
    session: requests.Session | None = None,
    workers: int = VISION_MAX_WORKERS,
) -> int:
    """Bir sembolün eksik geçmişini indirir; yazılan yeni bar sayısını döner."""
    now_ms = end_ms if end_ms is not None else int(time.time() * 1000)
    step = TIMEFRAME_MS[interval]

    stored = last_open_time(symbol, interval, root)
    resume_from = start_ms if stored is None else stored + step
    if resume_from >= now_ms:
        return 0

    files = archive_files(symbol, interval, resume_from, now_ms)
    if not files:
        return 0

    session = session or make_session(workers)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        batches = list(pool.map(lambda f: fetch_file(f, session), files))

    klines = [
        k
        for batch in batches
        for k in batch
        if k.open_time >= resume_from and k.close_time < now_ms  # yarım mum yok
    ]
    if not klines:
        return 0

    klines.sort(key=lambda k: k.open_time)
    return append_klines(symbol, interval, klines, root)


def download_many(
    symbols: Sequence[str],
    intervals: Sequence[str],
    start_ms: int = HISTORY_START_MS,
    end_ms: int | None = None,
    root: Path | None = None,
    workers: int = VISION_MAX_WORKERS,
    progress_every: int = 10,
) -> dict[str, int]:
    """Sembolleri sırayla, dosyaları paralel indirir."""
    session = make_session(workers)
    written: dict[str, int] = {}

    for interval in intervals:
        for i, symbol in enumerate(symbols, 1):
            try:
                n = download_symbol(symbol, interval, start_ms, end_ms, root, session, workers)
            except Exception as exc:  # tek sembol tüm süreci durdurmasın
                log.error("%s %s: %s", symbol, interval, exc)
                n = 0
            written[f"{interval}:{symbol}"] = n
            if i % progress_every == 0 or n:
                log.info("[%s %d/%d] %s +%d bar", interval, i, len(symbols), symbol, n)

    return written


# ---------------------------------------------------------------------------
# Evren bootstrap: hacimce sıralama (REST /ticker erişilemediği için arşivden)
# ---------------------------------------------------------------------------


def probe_month_volume(
    symbols: Iterable[str],
    year: int,
    month: int,
    interval: str = "1d",
    session: requests.Session | None = None,
    workers: int = VISION_MAX_WORKERS,
) -> dict[str, float]:
    """Tek bir ayın kote hacmini ölçer — evreni hacme göre sıralamak için.

    REST ``/ticker/24hr`` erişilemediğinde "hacimce ilk N parite" seçimi
    böyle yapılır: küçük tek bir aylık dosya (~2 KB) her parite için yeter.
    """
    symbols = list(symbols)
    session = session or make_session(workers)
    m_start, m_end = _month_bounds(year, month)

    def one(symbol: str) -> tuple[str, float]:
        f = ArchiveFile(
            symbol,
            interval,
            f"{BINANCE_VISION_S3}/"
            + VISION_MONTHLY_PATH.format(symbol=symbol, interval=interval, year=year, month=month),
            m_start,
            m_end,
        )
        return symbol, sum(k.quote_volume for k in fetch_file(f, session))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return {s: v for s, v in pool.map(one, symbols) if v > 0}


def iter_intervals(symbol: str, interval: str, start_ms: int, end_ms: int) -> Iterator[ArchiveFile]:
    """Test/hata ayıklama kolaylığı için dosya listesini akış olarak verir."""
    yield from archive_files(symbol, interval, start_ms, end_ms)
