"""GraphFlow — merkezi konfigürasyon.

Buradaki sabitler docs/00-tasarim-kararlari.md'deki kararlara birebir karşılık
gelir. Bir değeri değiştirmeden önce ilgili K-xx bölümünü oku.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final, Literal

# ---------------------------------------------------------------------------
# Yollar
# ---------------------------------------------------------------------------

ROOT: Final[Path] = Path(__file__).resolve().parent.parent
DATA_DIR: Final[Path] = ROOT / "data"
KLINES_DIR: Final[Path] = DATA_DIR / "klines"
MATRIX_DIR: Final[Path] = DATA_DIR / "matrix"
TEMPLATE_DIR: Final[Path] = Path(__file__).resolve().parent / "templates"

#: Sembol evreni, exchangeInfo anlık görüntüleri, ingest durum dosyası.
META_DIR: Final[Path] = DATA_DIR / "meta"
EXCHANGE_INFO_DIR: Final[Path] = META_DIR / "exchange_info"
UNIVERSE_FILE: Final[Path] = META_DIR / "symbol_universe.json"
INGEST_STATE_FILE: Final[Path] = META_DIR / "ingest_state.json"


# ---------------------------------------------------------------------------
# K-02 — Normalizasyon
# ---------------------------------------------------------------------------

#: Her pencerenin indirgeneceği sabit nokta sayısı.
N_POINTS: Final[int] = 32

#: Standart sapma bu değerin altındaysa pencere "düz" kabul edilip düşürülür.
FLAT_EPS: Final[float] = 1e-12


# ---------------------------------------------------------------------------
# K-07 / K-14 — Veri kapsamı ve çoklu çözünürlük
# ---------------------------------------------------------------------------

Timeframe = Literal["4h", "1d"]

TIMEFRAMES: Final[tuple[str, ...]] = ("4h", "1d")

#: Kayan pencere uzunlukları (bar). Her (timeframe, length) çifti ayrı matris.
WINDOW_LENGTHS: Final[tuple[int, ...]] = (24, 40, 64, 100)

#: Kayan pencere adımı. Stride 1'de komşu pencereler ~%99 aynı olur.
STRIDE: Final[int] = 3

#: Matris inşasında tek seferde işlenecek pencere sayısı. Tüm pencereleri
#: aynı anda RAM'e almamak için; asıl kazanç bitişik matris yapısında (K-01).
MATRIX_CHUNK_WINDOWS: Final[int] = 8_192

#: Binance geçmişinin başlangıcı.
HISTORY_START_MS: Final[int] = 1_502_928_000_000  # 2017-08-17

TIMEFRAME_MS: Final[dict[str, int]] = {
    "1h": 3_600_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}


# ---------------------------------------------------------------------------
# K-07 / K-13 — Binance ingest
#
# REST klines ücretsiz ve anahtarsızdır. Delist edilmiş pariteler
# exchangeInfo'da GÖRÜNMEZ; tarihsel evren data.binance.vision arşivinden
# veya saklanan exchangeInfo anlık görüntülerinden türetilir (K-13).
# ---------------------------------------------------------------------------

BINANCE_API_BASE: Final[str] = "https://api.binance.com"

#: data.binance.vision arşivinin S3 listeleme uç noktası (sembol dizinleri).
BINANCE_VISION_S3: Final[str] = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"

#: Tek /api/v3/klines çağrısında dönebilecek maksimum bar (Binance limiti).
KLINES_LIMIT: Final[int] = 1_000

#: /api/v3/klines ağırlığı (weight). exchangeInfo çok daha ağırdır.
KLINES_WEIGHT: Final[int] = 2
EXCHANGE_INFO_WEIGHT: Final[int] = 20

#: Binance IP başına dakikalık ağırlık limiti ve güvenlik payı.
#: Limiti tam doldurmak 418 (ban) riski taşır; %75'inde duruluyor.
WEIGHT_LIMIT_PER_MIN: Final[int] = 6_000
WEIGHT_SAFETY_RATIO: Final[float] = 0.75

#: HTTP zaman aşımı ve ağ hatasında yeniden deneme politikası.
REQUEST_TIMEOUT_SEC: Final[float] = 20.0
MAX_RETRIES: Final[int] = 5
RETRY_BACKOFF_BASE_SEC: Final[float] = 1.0
RETRY_BACKOFF_FACTOR: Final[float] = 2.0
RETRY_BACKOFF_MAX_SEC: Final[float] = 60.0

#: Evrene alınacak kote varlıklar (K-07: ~500 likit parite, USDT + BTC bazlı).
QUOTE_ASSETS: Final[tuple[str, ...]] = ("USDT", "BTC")

#: İndirmede kaç sayfada bir diske yazılacağı. Sık yazmak kesintiden devamı
#: hassaslaştırır, seyrek yazmak Parquet yeniden yazma maliyetini düşürür.
INGEST_FLUSH_PAGES: Final[int] = 10


# ---------------------------------------------------------------------------
# K-13 — Likidite filtreleri
# ---------------------------------------------------------------------------

#: Backtest: her ayın kesitinde hacimce üst bu orana girenler geçerli sayılır.
LIQUIDITY_TOP_PCT: Final[float] = 0.40

#: Radar: son 24 saat kote hacmi eşiği (USD).
LIVE_MIN_QUOTE_VOLUME: Final[float] = 5_000_000.0


# ---------------------------------------------------------------------------
# K-03 / K-09 / K-11 — Kaskad arama
# ---------------------------------------------------------------------------

#: Aşama 1 (kosinüs) çıktısında tutulacak aday sayısı.
STAGE1_TOPK: Final[int] = 5_000

#: Pre-NMS sonrası Aşama 2'ye (DDTW) girecek aday sayısı.
STAGE2_TOPK: Final[int] = 1_000

#: Aşama 1'de memmap üzerinden tek seferde işlenecek satır sayısı. Skorlama
#: chunk'lanır ki 12M satırlık matris için geçici dizi RAM'i şişirmesin (K-01).
STAGE1_CHUNK_ROWS: Final[int] = 1_000_000

#: Maske bu orandan seyrekse satırlar toplanarak (gather) skorlanır; tüm
#: matrisi çarpmak yerine. Radar (live) modu tam olarak bu durumdadır (K-15).
STAGE1_SPARSE_MASK_RATIO: Final[float] = 0.05

#: Pre-NMS: gevşek IoU eşiği — amaç aday havuzunu çeşitlendirmek.
PRE_NMS_IOU: Final[float] = 0.70

#: Post-NMS: katı IoU eşiği — kullanıcıya gidecek listeyi temizler.
POST_NMS_IOU: Final[float] = 0.50

#: Post-NMS: tek bir sembolden gösterilecek maksimum sonuç.
MAX_RESULTS_PER_SYMBOL: Final[int] = 3

#: DTW Sakoe-Chiba band yarıçapı (K-11): 0.15 * N.
SAKOE_CHIBA_RADIUS: Final[int] = max(1, round(0.15 * N_POINTS))


# ---------------------------------------------------------------------------
# K-17 — Esneklik kademeleri
#
# Değerler normalize DDTW mesafesi üzerinde ÜST SINIR'dır (küçük = benzer).
# UYARI: Bu değerler geçici başlangıç değerleridir. Nihai değerler F3
# notebook kalibrasyonundan (ROC) çıkarılacaktır — bkz. K-18.
# ---------------------------------------------------------------------------

Tolerance = Literal["strict", "medium", "flexible"]

TOLERANCE_THRESHOLDS: Final[dict[str, float]] = {
    "strict": 0.015,
    "medium": 0.040,
    "flexible": 0.090,
}


# ---------------------------------------------------------------------------
# K-16 — Triple-Barrier
# ---------------------------------------------------------------------------

#: ATR periyodu (Wilder).
ATR_PERIOD: Final[int] = 14

#: Bariyer konfigürasyonları: ad -> (k_tp, k_sl).
#: 2:1  → teorik null = 1/3
#: 1:1  → teorik null = 1/2  (saf yön testi, akademik referans)
BARRIER_CONFIGS: Final[dict[str, tuple[float, float]]] = {
    "2:1": (2.0, 1.0),
    "1:1": (1.0, 1.0),
}

#: Zaman bariyeri = bu oran * pencere uzunluğu (K-16.4).
TIME_BARRIER_RATIO: Final[float] = 0.5

#: İşlem maliyeti tabanı: 1*ATR / close bu oranın altındaysa pencere
#: istatistiğe girmez (K-16.7). Binance taker gidiş-dönüş ~%0.1 + slipaj.
MIN_ATR_PCT: Final[float] = 0.01

#: Gölge dağılımda her eşleşme için çekilecek kontrol penceresi sayısı (K-12).
SHADOW_SAMPLES_PER_MATCH: Final[int] = 20


# ---------------------------------------------------------------------------
# K-08 — Sayfalama
# ---------------------------------------------------------------------------

PAGE_SIZE: Final[int] = 12


# ---------------------------------------------------------------------------
# Meta dizisinin dtype'ı (docs/01-mimari.md §4.1)
# ---------------------------------------------------------------------------

import numpy as np  # noqa: E402

META_DTYPE: Final[np.dtype] = np.dtype(
    [
        ("symbol_id", "i4"),
        ("start_idx", "i4"),
        ("end_idx", "i4"),
        ("end_time", "i8"),
        ("amplitude", "f4"),
        ("atr", "f4"),
        ("liquid", "?"),
    ]
)
