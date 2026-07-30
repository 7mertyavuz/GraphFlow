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

#: data.binance.vision arşivinin S3 uç noktası (sembol dizinleri + ZIP'ler).
#: NOT: ``data.binance.vision`` CNAME'i bazı ağlardan erişilemez; bucket'ın
#: kendisi bu S3 adı üzerinden aynı içeriği verir. Arşiv, REST'te görünmeyen
#: delist edilmiş pariteleri de içerdiği için K-13'ün asıl kaynağıdır.
BINANCE_VISION_S3: Final[str] = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"

#: Arşiv yol şablonları (aylık dosya yoksa günlük dosyalara düşülür).
VISION_MONTHLY_PATH: Final[str] = "data/spot/monthly/klines/{symbol}/{interval}/{symbol}-{interval}-{year:04d}-{month:02d}.zip"
VISION_DAILY_PATH: Final[str] = "data/spot/daily/klines/{symbol}/{interval}/{symbol}-{interval}-{year:04d}-{month:02d}-{day:02d}.zip"

#: Arşivden eşzamanlı indirme sayısı. S3'te ağırlık limiti yok; bu sayı
#: nezaket ve yerel disk/CPU dengesi için.
VISION_MAX_WORKERS: Final[int] = 8

#: Arşiv, 2025-01'den itibaren zaman damgalarını MİKROSANİYE yazıyor; daha
#: eski dosyalar milisaniye. Bu eşiği aşan değer µs kabul edilip 1000'e
#: bölünür. (1e14 ms ≈ 5138 yılı — ms verinin bu değeri aşması imkânsız.)
#: Bu dönüşüm olmadan yeni barlar "kapanmamış mum" sanılıp sessizce düşer.
EPOCH_US_THRESHOLD: Final[int] = 100_000_000_000_000

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

#: Veri tazeliği invariant'ı (F3.5): depodaki en yeni bar, bugünden bu kadar
#: bardan fazla geride olamaz. Gerekçe: mikrosaniye hatası 19 aylık veriyi
#: SIFIR hata mesajıyla yok etti; bu sınıf hata bir daha sessiz kalmasın.
#:
#: Eşik zaman dilimi başınadır çünkü **kaynağın yayım gecikmesi** farklı
#: ölçekte vurur: arşiv (data.binance.vision) günlük dosyaları ~1 gün
#: gecikmeyle yayımlar. 1d'de bu 1 bar, 4h'de 6 bar eder. REST erişimi
#: olan bir ortamda 4h için de 3 bar hedeflenmelidir — 12 değeri arşiv
#: kısıtının kaydıdır, tasarım tercihi değil.
MAX_STALENESS_BARS: Final[dict[str, int]] = {
    "4h": 12,  # arşiv gecikmesi nedeniyle gevşek — REST'te 3 olmalı
    "1d": 3,
}

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
# F3.5 / K-10 — Sabitlenmiş (pegged) parite filtresi ve genlik varsayılanı
#
# F3 göz testi bulgusu: z-score, sabitlenmiş bir paritenin %4'lük
# dalgalanmasını kusursuz bir formasyona çeviriyor ve bunlar ilk sayfanın
# TEPESİNE yerleşiyor (OBO'da 1. ve 2. sıra PAXUSDT / TUSDUSDT).
#
# İki katmanlı çözüm — tek başına ikisi de yetmez:
#   1) Yapısal filtre: fiyatı geçmişinin çoğunda 1,0 ± %2 içinde kalan parite
#      evrenden düşer (stablecoin + sarmalanmış varlıklar: WBTCBTC, RENBTCBTC)
#   2) Genlik varsayılanı: düşük oynaklıklı meşru pariteleri de eler
# ---------------------------------------------------------------------------

#: Fiyatın "sabitlenmiş" sayılacağı bant (1,0 ± bu oran).
PEG_TOLERANCE: Final[float] = 0.02

#: Barların bu oranı bantta kalıyorsa parite sabitlenmiş kabul edilir.
#: Ölçüm: gerçek veride 0,96 üstü ile 0,30 altı arasında hiçbir sembol yok —
#: eşik geniş bir boşluğun ortasında, seçim hassas değil.
PEG_MIN_RATIO: Final[float] = 0.80

#: Aramada varsayılan minimum genlik (%). 1d değeri ölçüldü: %15 eşiği likit
#: pencerelerin %95,2'sini koruyor — patolojik kuyruğu kesiyor, veriyi
#: budamıyor. 4h değeri GEÇİCİ: aynı bar sayısı 1/6 zaman kapsadığı için
#: oynaklık ~√6 ile ölçekleniyor; 4h matrisleri kurulunca ölçülmeli.
DEFAULT_MIN_AMPLITUDE: Final[dict[str, float]] = {
    "4h": 6.0,  # geçici — ölçülmedi
    "1d": 15.0,  # ölçüldü (F3.5)
}


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


# ---------------------------------------------------------------------------
# K-11 — Aşama 2 metriği (KARARA BAĞLANDI, F3 / 30 Temmuz 2026)
#
# F3 A/B'si (tools/ab_stage2.py): pozitifler kanonik şablonun kopyası değil,
# yapısal doğrulamadan geçmiş VARYANTLAR (asimetrik omuz, eğimli boyun
# çizgisi, kaymış zamanlama). 3 metrik × 4 pencere uzunluğu × 3 gürültü
# seviyesi, formasyon başına 300 örnek:
#
#   genel AUC:  hybrid 0.9045  >  dtw 0.8956  >  ddtw 0.8733
#   hybrid, 12/12 hücrede ve 9/9 formasyonda kazandı (eşli hücrelerin
#   %99'unda dtw'den, %80'inde ddtw'den iyi).
#
# DDTW tek başına en kötüsü: türev yüksek geçiren filtredir, gürültüyü
# büyütür; K-11'in dayandığı singularity ise Sakoe-Chiba + z-score varken
# zaten üretilemiyor. Ham DTW yalnız başına da hybrid'den geride — iki
# mesafenin ortalaması ikisinin de bilgisini taşıyor.
# Bkz. docs/03-f3-dogrulama-raporu.md ve K-11 "Karara bağlandı (F3)".
# ---------------------------------------------------------------------------

Stage2Metric = Literal["ddtw", "dtw", "hybrid"]

#: hybrid = (normalize DDTW mesafesi + normalize ham DTW mesafesi) / 2
STAGE2_METRIC: Final[str] = "hybrid"

#: Eşikler metrik başına ayrıdır: ham DTW mesafeleri DDTW'ninkinden ~4x
#: büyüktür; tek eşik setiyle metrik çevrildiğinde motor sessizce boş sonuç
#: döner.
#:
#: Değerler F3 ADIM 3'te **gerçek Binance verisinden** kalibre edildi:
#: 1.165 parite (delist edilenler dahil), 1d, 2017-08 → 2026-07, 1,92M
#: pencere; 14 şablon sorgusu + 32 negatif kontrol. Gerçek veride etiket
#: yoktur, dolayısıyla AUC hesaplanamaz; eşikler dağılımdan okunur:
#:
#:   Katı   = şablonların "12. sonuç" skorunun alt çeyreği
#:   Orta   = şablonların "12. sonuç" skorunun medyanı
#:   Esnek  = şablon skorlarının %95'lik diliminin üst çeyreği
#:   Üst sınır: hiçbiri anlamsız sorgu tabanının %90'ını aşamaz (K-18)
#:
#: Ölçülen anlamsız sorgu (white noise / whipsaw) tabanı — en gevşek kademe
#: bunun çok altında kalıyor, yani motor gürültüye "eşleşme yok" diyebiliyor:
#:   ddtw 0,1726 · dtw 0,2026 · hybrid 0,1897
#:
#: Üretim: notebooks/05_esik_kalibrasyon.ipynb, docs/03-f3-dogrulama-raporu.md
TOLERANCE_THRESHOLDS_BY_METRIC: Final[dict[str, dict[str, float]]] = {
    "ddtw": {"strict": 0.0118, "medium": 0.0162, "flexible": 0.0456},
    "dtw": {"strict": 0.0184, "medium": 0.0337, "flexible": 0.1097},
    "hybrid": {"strict": 0.0172, "medium": 0.0273, "flexible": 0.0836},
}

#: Aktif metriğin **mutlak** eşikleri. F3.5'ten itibaren yalnızca yedek yoldur
#: (null örneklemi çok küçükse); asıl kalibrasyon aşağıdaki yüzdelik sistemdir.
TOLERANCE_THRESHOLDS: Final[dict[str, float]] = TOLERANCE_THRESHOLDS_BY_METRIC[STAGE2_METRIC]


# ---------------------------------------------------------------------------
# F3.5 — Sorgu-göreli null kalibrasyonu (K-12'nin skorlama katmanına uygulanmışı)
#
# F3, üç bulgunun (S-1 rampa, S-2 şablon başına zorluk farkı, S-3 uzunluk
# dengesizliği) **aynı kökten** geldiğini gösterdi: mutlak mesafe ölçeği,
# sorgunun yapısal karmaşıklığına ve pencere uzunluğuna bağlı.
#
#   * Monoton rampanın uyuşmazlık üretecek yapısı yok → 0,0025
#   * Bayrak basit (0,008), üçgen karmaşık (0,056)
#   * Uzun pencerede daha çok yapı → daha çok uyuşmazlık → sistematik ceza
#
# Çözüm: arama anında sorgu, her pencere uzunluğu için rastgele pencerelere
# karşı skorlanır → **o sorgunun kendi null dağılımı**. Eşik mutlak sayı değil,
# bu dağılımın yüzdelik dilimidir. Sıralama da uzunluk-içi yüzdelik dilime göre
# yapılır; böylece 24 barlık pencereler 100 barlıkları ezemez.
#
# Şablon başına eşik neden değil: serbest çizimde kalibrasyon verisi yok, ki
# ürünün yarısı o.
# ---------------------------------------------------------------------------

#: Pencere uzunluğu **başına** çekilecek rastgele pencere sayısı.
NULL_SAMPLE_SIZE: Final[int] = 2_000

#: Null örneklemi sabit tohumlu → aynı sorgu aynı sonucu verir (tekrarlanabilirlik).
NULL_SEED: Final[int] = 20_260_731

#: Bu sayının altında örneklem varsa yüzdelik güvenilmez → mutlak eşiğe düşülür.
NULL_MIN_SAMPLES: Final[int] = 200

#: Null dağılımı (sorgu, uzunluk, metrik, maske) başına sabittir; önbellek
#: Radar'ın 5 dakikalık cron döngüsünde ilk çağrı dışındaki maliyeti kaldırır.
#: Girdi başına ~16 KB.
NULL_CACHE_SIZE: Final[int] = 128

#: Tolerans kademeleri artık null dağılımının yüzdelik dilimleridir.
#: "strict = 0,0005" → rastgele pencerelerin yalnızca %0,05'i bu kadar iyi.
NULL_PERCENTILES: Final[dict[str, float]] = {
    "strict": 0.0005,
    "medium": 0.0025,
    "flexible": 0.0150,
}

#: **Akıl sağlığı tavanı** — yüzdelik eşiğin yanında MUTLAK bir üst sınır.
#:
#: Saf yüzdelik eşik, tanımı gereği her sorguya sonuç döndürür: "en iyi %0,25"
#: her zaman vardır. Bu, motorun *"iyi eşleşme yok"* diyebilme yetisini yok
#: eder (§5.5, K-18) — ölçüldü: white noise ve whipsaw sorguları yüzdelik
#: sisteme geçince 40–100 sonuç dönmeye başladı.
#:
#: Bu yüzden iki koşul BİRLİKTE aranır: aday hem kendi null dağılımının
#: yüzdelik diliminde olmalı, hem de mutlak mesafesi bu tavanın altında.
#: Değer, F3'te gerçek veriden kalibre edilen "esnek" eşiktir; ölçülen
#: ayrım: şablonların en iyi skoru 0,014–0,067, white noise 0,34, whipsaw 0,55.
NULL_ABSOLUTE_CAP: Final[float] = TOLERANCE_THRESHOLDS["flexible"]

#: Yapısal benzerlik uyarısı.
#:
#: ``null_medyan / null_p01`` oranı, korpusta sorguya *yapısal olarak* benzeyen
#: bir şey olup olmadığını ölçer. Ölçülen değerler:
#:   whipsaw 1,3 · white noise 1,4–1,5 · simetrik üçgen 2,4 · OBO 8,1 ·
#:   bayrak 15,1 · rampa 55,6
#: Düşük oran = "korpusta buna benzeyen hiçbir yapı yok" (dağılımın tamamı
#: aynı derecede kötü). Bu, ölçümden çıkan bir sinyaldir; elle kodlanmış bir
#: "düzlük ölçer" değildir.
NULL_DISCRIMINATIVE_RATIO: Final[float] = 2.0


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
