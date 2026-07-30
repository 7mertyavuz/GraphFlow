"""Binance REST /api/v3/klines indiricisi.

Sorumluluklar:

* **Sayfalama** — tek çağrıda en fazla ``KLINES_LIMIT`` (1000) bar döner;
  imleç son barın açılış zamanına göre ilerletilir.
* **Rate-limit'e saygı** — yanıt başlığındaki ``X-MBX-USED-WEIGHT-1M`` takip
  edilir, güvenlik payı aşılırsa dakika penceresinin sonuna kadar beklenir.
  429/418 yanıtlarında ``Retry-After`` başlığına uyulur.
* **Dayanıklılık** — ağ hatası ve 5xx'te üstel geri çekilmeyle yeniden dener.

Anahtar gerektirmez (K-07). Ağ katmanı ``session`` parametresiyle dışarıdan
verilebilir; testler sahte bir oturum enjekte eder.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterator, Sequence

import requests

from engine.config import (
    BINANCE_API_BASE,
    EXCHANGE_INFO_WEIGHT,
    KLINES_LIMIT,
    KLINES_WEIGHT,
    MAX_RETRIES,
    REQUEST_TIMEOUT_SEC,
    RETRY_BACKOFF_BASE_SEC,
    RETRY_BACKOFF_FACTOR,
    RETRY_BACKOFF_MAX_SEC,
    TIMEFRAME_MS,
    WEIGHT_LIMIT_PER_MIN,
    WEIGHT_SAFETY_RATIO,
)

log = logging.getLogger(__name__)


class BinanceError(RuntimeError):
    """Binance'ten gelen, yeniden denemenin çözmeyeceği hata."""


class UnknownSymbolError(BinanceError):
    """Sembol borsada yok (delist edilmiş veya hiç listelenmemiş)."""


#: Binance'in "geçersiz sembol" hata kodu.
_ERR_BAD_SYMBOL = -1121


@dataclass(frozen=True)
class Kline:
    """Tek bir mum — docs/01-mimari.md §2.2 şemasının alanları."""

    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int
    quote_volume: float
    trades: int

    @classmethod
    def from_raw(cls, row: Sequence[Any]) -> "Kline":
        """Binance'in 12 elemanlı dizi formatından dönüştürür."""
        return cls(
            open_time=int(row[0]),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
            close_time=int(row[6]),
            quote_volume=float(row[7]),
            trades=int(row[8]),
        )


class WeightTracker:
    """Kayan bir dakikalık ağırlık penceresi.

    Binance kullanılan ağırlığı her yanıtta başlıkla bildirir; asıl doğruluk
    kaynağı odur. Başlık yoksa (ör. bağlantı hatası) yerel sayaç kullanılır.
    """

    def __init__(
        self,
        limit: int = WEIGHT_LIMIT_PER_MIN,
        safety_ratio: float = WEIGHT_SAFETY_RATIO,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limit = limit
        self.budget = int(limit * safety_ratio)
        self._sleep = sleep
        self._clock = clock
        self._used = 0
        self._window_start = clock()

    @property
    def used(self) -> int:
        return self._used

    def _roll(self) -> None:
        if self._clock() - self._window_start >= 60.0:
            self._window_start = self._clock()
            self._used = 0

    def acquire(self, weight: int) -> None:
        """İstek göndermeden önce çağrılır; gerekirse pencere sonuna kadar bekler."""
        self._roll()
        if self._used + weight <= self.budget:
            self._used += weight
            return
        wait = max(0.0, 60.0 - (self._clock() - self._window_start))
        log.info("Ağırlık bütçesi doldu (%d/%d) — %.1f sn bekleniyor", self._used, self.budget, wait)
        self._sleep(wait)
        self._window_start = self._clock()
        self._used = weight

    def observe(self, headers: Any) -> None:
        """Yanıt başlığındaki gerçek kullanılmış ağırlığı benimser."""
        if not headers:
            return
        for key in ("X-MBX-USED-WEIGHT-1M", "x-mbx-used-weight-1m", "X-MBX-USED-WEIGHT"):
            raw = headers.get(key) if hasattr(headers, "get") else None
            if raw is None:
                continue
            try:
                reported = int(raw)
            except (TypeError, ValueError):
                continue
            # Borsa bizden daha yüksek biliyorsa onu esas al.
            self._used = max(self._used, reported)
            return


class BinanceClient:
    """İnce, durum tutan REST istemcisi."""

    def __init__(
        self,
        base_url: str = BINANCE_API_BASE,
        session: Any | None = None,
        timeout: float = REQUEST_TIMEOUT_SEC,
        max_retries: int = MAX_RETRIES,
        sleep: Callable[[float], None] = time.sleep,
        weights: WeightTracker | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session if session is not None else requests.Session()
        self.timeout = timeout
        self.max_retries = max_retries
        self._sleep = sleep
        self.weights = weights if weights is not None else WeightTracker(sleep=sleep)

    # -- alt seviye -------------------------------------------------------

    def _backoff(self, attempt: int) -> float:
        delay = RETRY_BACKOFF_BASE_SEC * (RETRY_BACKOFF_FACTOR**attempt)
        return min(delay, RETRY_BACKOFF_MAX_SEC)

    def _get(self, path: str, params: dict[str, Any], weight: int) -> Any:
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            self.weights.acquire(weight)
            try:
                resp = self.session.get(
                    f"{self.base_url}{path}", params=params, timeout=self.timeout
                )
            except Exception as exc:  # ağ katmanı hatası → yeniden dene
                last_error = exc
                delay = self._backoff(attempt)
                log.warning("Ağ hatası (%s) — %.1f sn sonra tekrar: %s", path, delay, exc)
                self._sleep(delay)
                continue

            self.weights.observe(getattr(resp, "headers", None))
            status = resp.status_code

            if status == 200:
                return resp.json()

            if status in (429, 418):
                # Rate-limit / geçici ban. Retry-After'a uy, yoksa üstel bekle.
                retry_after = None
                headers = getattr(resp, "headers", None)
                if headers is not None and hasattr(headers, "get"):
                    retry_after = headers.get("Retry-After") or headers.get("retry-after")
                try:
                    delay = float(retry_after) if retry_after is not None else self._backoff(attempt)
                except (TypeError, ValueError):
                    delay = self._backoff(attempt)
                log.warning("Rate-limit (%d) — %.1f sn bekleniyor", status, delay)
                self._sleep(delay)
                last_error = BinanceError(f"HTTP {status}")
                continue

            if 400 <= status < 500:
                payload = _safe_json(resp)
                code = payload.get("code") if isinstance(payload, dict) else None
                msg = payload.get("msg") if isinstance(payload, dict) else resp.text
                if code == _ERR_BAD_SYMBOL:
                    raise UnknownSymbolError(f"{params.get('symbol')}: {msg}")
                raise BinanceError(f"HTTP {status} — {msg}")

            # 5xx → geçici, yeniden dene
            last_error = BinanceError(f"HTTP {status}")
            delay = self._backoff(attempt)
            log.warning("Sunucu hatası %d — %.1f sn sonra tekrar", status, delay)
            self._sleep(delay)

        raise BinanceError(f"{path} için {self.max_retries} deneme başarısız") from last_error

    # -- uç noktalar ------------------------------------------------------

    def exchange_info(self) -> dict[str, Any]:
        """Yalnızca YAŞAYAN pariteleri döndürür — delist olanlar için K-13."""
        return self._get("/api/v3/exchangeInfo", {}, EXCHANGE_INFO_WEIGHT)

    def server_time_ms(self) -> int:
        return int(self._get("/api/v3/time", {}, 1)["serverTime"])

    def klines(
        self,
        symbol: str,
        interval: str,
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int = KLINES_LIMIT,
    ) -> list[Kline]:
        params: dict[str, Any] = {
            "symbol": symbol,
            "interval": interval,
            "limit": min(limit, KLINES_LIMIT),
        }
        if start_time is not None:
            params["startTime"] = int(start_time)
        if end_time is not None:
            params["endTime"] = int(end_time)
        rows = self._get("/api/v3/klines", params, KLINES_WEIGHT)
        return [Kline.from_raw(r) for r in rows]

    def iter_klines(
        self,
        symbol: str,
        interval: str,
        start_time: int,
        end_time: int | None = None,
    ) -> Iterator[list[Kline]]:
        """``start_time``'dan itibaren sayfa sayfa mum üretir.

        Her sayfa en fazla ``KLINES_LIMIT`` bar içerir. İmleç son barın açılış
        zamanı + bir periyot olarak ilerletilir; böylece sınırda tekrar eden
        bar oluşmaz. Boş sayfa veya ilerlemeyen imleç döngüyü sonlandırır.
        """
        step = TIMEFRAME_MS[interval]
        cursor = int(start_time)

        while True:
            if end_time is not None and cursor > end_time:
                return
            page = self.klines(symbol, interval, start_time=cursor, end_time=end_time)
            if not page:
                return

            yield page

            next_cursor = page[-1].open_time + step
            if next_cursor <= cursor:  # ilerleme yok → sonsuz döngü koruması
                return
            cursor = next_cursor

            if len(page) < KLINES_LIMIT:
                return


def _safe_json(resp: Any) -> Any:
    try:
        return resp.json()
    except Exception:
        return {}
