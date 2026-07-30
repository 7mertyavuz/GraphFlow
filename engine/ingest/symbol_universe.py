"""Sembol evreni — delist edilenler dahil (K-13).

``exchangeInfo`` yalnızca **yaşayan** pariteleri verir. Sadece onunla çalışmak
survivorship bias üretir: LUNA ve FTT çöküşlerinden önce yüzlerce ders kitabı
formasyonu yaptı; bu grafikleri dışarıda bırakmak "formasyon çalışıyor"
sonucunu yapay olarak üretir.

Bu yüzden tarihsel evren iki kaynağın **birleşimidir**:

1. ``GET /api/v3/exchangeInfo``           — bugün işlem gören pariteler
2. ``data.binance.vision`` arşiv listesi  — bir zamanlar veri üretmiş TÜM
   pariteler (delist edilmiş olanlar dahil)

Ek olarak her çalıştırmada exchangeInfo'nun anlık görüntüsü saklanır; zamanla
bu görüntüler kendi başına bir delist kaydı oluşturur (bir sembol eski
görüntüde var, yenisinde yoksa aradaki dönemde delist edilmiştir).

Evren dosyası ``symbol_id`` alanını da taşır: matris meta'sındaki
``symbol_id`` bu dosyaya indeks olduğundan, id'ler **asla yeniden
numaralandırılmaz**; yeni semboller sona eklenir.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterable

import requests

from engine.config import (
    BINANCE_VISION_S3,
    EXCHANGE_INFO_DIR,
    QUOTE_ASSETS,
    REQUEST_TIMEOUT_SEC,
    UNIVERSE_FILE,
)
from engine.ingest.store import read_json, write_json_atomic

log = logging.getLogger(__name__)

_S3_NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"

STATUS_TRADING = "TRADING"
STATUS_DELISTED = "DELISTED"


# ---------------------------------------------------------------------------
# Kaynak 1 — exchangeInfo (yaşayanlar)
# ---------------------------------------------------------------------------


def snapshot_exchange_info(payload: dict[str, Any], directory: Path | None = None) -> Path:
    """exchangeInfo yanıtını zaman damgalı olarak saklar (delist kaydı için)."""
    directory = Path(directory or EXCHANGE_INFO_DIR)
    stamp = int(payload.get("serverTime", 0))
    path = directory / f"exchange_info_{stamp}.json"
    write_json_atomic(payload, path)
    return path


def parse_exchange_info(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """exchangeInfo → {symbol: {base_asset, quote_asset, status}} (yalnız SPOT)."""
    out: dict[str, dict[str, Any]] = {}
    for s in payload.get("symbols", []):
        quote = s.get("quoteAsset")
        if quote not in QUOTE_ASSETS:
            continue
        if s.get("isSpotTradingAllowed") is False:
            continue
        out[s["symbol"]] = {
            "base_asset": s.get("baseAsset"),
            "quote_asset": quote,
            "status": s.get("status", STATUS_TRADING),
        }
    return out


def load_snapshots(directory: Path | None = None) -> dict[str, dict[str, Any]]:
    """Saklanan tüm exchangeInfo görüntülerinin birleşimi.

    Bugünün exchangeInfo'sunda olmayan ama eski bir görüntüde geçen sembol,
    delist edilmiş demektir.
    """
    directory = Path(directory or EXCHANGE_INFO_DIR)
    if not directory.exists():
        return {}

    merged: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob("exchange_info_*.json")):
        payload = read_json(path, default=None)
        if not isinstance(payload, dict):
            continue
        for symbol, info in parse_exchange_info(payload).items():
            merged.setdefault(symbol, dict(info))
    return merged


# ---------------------------------------------------------------------------
# Kaynak 2 — data.binance.vision arşivi (delist edilenler dahil)
# ---------------------------------------------------------------------------


def parse_s3_listing(xml_text: str) -> tuple[list[str], str | None]:
    """S3 ListBucket XML'inden sembol adlarını ve devam işaretçisini çıkarır."""
    root = ET.fromstring(xml_text)

    symbols: list[str] = []
    for cp in root.findall(f"{_S3_NS}CommonPrefixes"):
        node = cp.find(f"{_S3_NS}Prefix")
        if node is None or not node.text:
            continue
        # ".../klines/BTCUSDT/" → "BTCUSDT"
        name = node.text.rstrip("/").rsplit("/", 1)[-1]
        if name:
            symbols.append(name)

    truncated = (root.findtext(f"{_S3_NS}IsTruncated") or "false").strip().lower() == "true"
    if not truncated:
        return symbols, None

    marker = root.findtext(f"{_S3_NS}NextContinuationToken") or root.findtext(f"{_S3_NS}NextMarker")
    if not marker and symbols:
        # NextMarker yoksa S3 son anahtarın kendisini işaretçi kabul eder.
        marker = f"{_prefix_of(root)}{symbols[-1]}/"
    return symbols, marker


def _prefix_of(root: ET.Element) -> str:
    return root.findtext(f"{_S3_NS}Prefix") or ""


def fetch_archive_symbols(
    session: Any | None = None,
    prefix: str = "data/spot/monthly/klines/",
    timeout: float = REQUEST_TIMEOUT_SEC,
    max_pages: int = 100,
) -> set[str]:
    """Arşivde dizini bulunan tüm spot paritelerini listeler.

    Ağ erişilemezse boş küme döner — çağıran taraf exchangeInfo ve saklanan
    görüntülerle devam eder (evren daralır ama süreç durmaz).
    """
    session = session if session is not None else requests.Session()
    found: set[str] = set()
    marker: str | None = None

    for _ in range(max_pages):
        params: dict[str, Any] = {"delimiter": "/", "prefix": prefix}
        if marker:
            params["marker"] = marker
        try:
            resp = session.get(BINANCE_VISION_S3, params=params, timeout=timeout)
            if resp.status_code != 200:
                log.warning("Arşiv listesi HTTP %s — atlanıyor", resp.status_code)
                break
            page, marker = parse_s3_listing(resp.text)
        except Exception as exc:  # ağ/parse hatası → elimizdekiyle devam
            log.warning("Arşiv listesi alınamadı: %s", exc)
            break

        found.update(page)
        if not marker:
            break

    return {s for s in found if _looks_like_symbol(s)}


_SYMBOL_RE = re.compile(r"^[A-Z0-9]{4,20}$")


def _looks_like_symbol(name: str) -> bool:
    return bool(_SYMBOL_RE.match(name))


def split_quote(symbol: str) -> tuple[str, str] | None:
    """Sembolü (base, quote) olarak ayırır; kote varlık evrende değilse None."""
    for quote in sorted(QUOTE_ASSETS, key=len, reverse=True):
        if symbol.endswith(quote) and len(symbol) > len(quote):
            return symbol[: -len(quote)], quote
    return None


# ---------------------------------------------------------------------------
# Birleştirme
# ---------------------------------------------------------------------------


def build_universe(
    exchange_info: dict[str, Any] | None = None,
    archive_symbols: Iterable[str] | None = None,
    snapshots: dict[str, dict[str, Any]] | None = None,
    previous: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Üç kaynağı birleştirip ``symbol_id``'leri koruyarak evreni üretir."""
    live = parse_exchange_info(exchange_info) if exchange_info else {}
    known: dict[str, dict[str, Any]] = {}

    # Önce arşiv + eski görüntüler (delist adayları), sonra yaşayanlar ezer.
    for symbol, info in (snapshots or {}).items():
        known[symbol] = {**info, "status": STATUS_DELISTED, "source": "snapshot"}

    for symbol in archive_symbols or []:
        parts = split_quote(symbol)
        if parts is None:
            continue
        base, quote = parts
        if symbol in known:
            known[symbol]["source"] = "snapshot+archive"
            continue
        known[symbol] = {
            "base_asset": base,
            "quote_asset": quote,
            "status": STATUS_DELISTED,
            "source": "archive",
        }

    for symbol, info in live.items():
        known[symbol] = {**info, "source": "exchange_info"}

    # symbol_id'ler kalıcıdır: matris meta'sı bunlara referans verir.
    ordered: list[dict[str, Any]] = []
    used_ids: set[int] = set()
    for row in previous or []:
        symbol = row["symbol"]
        sid = int(row["symbol_id"])
        merged = {**row, **known.get(symbol, {}), "symbol": symbol, "symbol_id": sid}
        ordered.append(merged)
        used_ids.add(sid)

    next_id = (max(used_ids) + 1) if used_ids else 0
    existing = {row["symbol"] for row in ordered}
    for symbol in sorted(set(known) - existing):
        ordered.append({"symbol": symbol, "symbol_id": next_id, **known[symbol]})
        next_id += 1

    return ordered


def save_universe(universe: list[dict[str, Any]], path: Path | None = None) -> Path:
    path = Path(path or UNIVERSE_FILE)
    write_json_atomic(universe, path)
    return path


def load_universe(path: Path | None = None) -> list[dict[str, Any]]:
    return read_json(Path(path or UNIVERSE_FILE), default=[]) or []


def symbol_id_map(universe: list[dict[str, Any]] | None = None) -> dict[str, int]:
    rows = universe if universe is not None else load_universe()
    return {row["symbol"]: int(row["symbol_id"]) for row in rows}


def refresh_universe(
    client: Any,
    session: Any | None = None,
    universe_path: Path | None = None,
    snapshot_dir: Path | None = None,
    use_archive: bool = True,
) -> list[dict[str, Any]]:
    """Canlı + arşiv + saklanan görüntülerden evreni günceller ve diske yazar."""
    info = client.exchange_info()
    snapshot_exchange_info(info, snapshot_dir)

    archive = fetch_archive_symbols(session) if use_archive else set()
    log.info("Arşivde %d parite bulundu", len(archive))

    universe = build_universe(
        exchange_info=info,
        archive_symbols=archive,
        snapshots=load_snapshots(snapshot_dir),
        previous=load_universe(universe_path),
    )
    save_universe(universe, universe_path)

    n_live = sum(1 for r in universe if r["status"] == STATUS_TRADING)
    log.info("Evren: %d parite (%d aktif, %d delist)", len(universe), n_live, len(universe) - n_live)
    return universe
