"""GraphFlow — merkezi konfigürasyon.

Buradaki sabitler docs/00-tasarim-kararlari.md'deki kararlara birebir karşılık
gelir. Bir değeri değiştirmeden önce ilgili K-xx bölümünü oku.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final, Literal

# ---------------------------------------------------------------------------
# Yollar
# ---------------------------------------------------------------------------

ROOT: Final[Path] = Path(__file__).resolve().parent.parent

#: Veri kökü. Depo dışına (harici disk, worktree, dağıtım hedefi) taşınabilsin
#: diye ``GRAPHFLOW_DATA_DIR`` ile geçersiz kılınabilir. 517 MB'lık klines +
#: matris deposu asla commit edilmediği için tek çalışan kopya paylaşılır.
DATA_DIR: Final[Path] = Path(os.environ.get("GRAPHFLOW_DATA_DIR") or (ROOT / "data"))
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

#: Gerçek grafikten sorgu (engine/search/source.py): kullanıcının seçtiği
#: parçanın bar sayısı. Alt sınır en kısa matris penceresi — daha kısa bir
#: parça 32 noktaya çıkarken şekil değil ara değerleme taşır. Üst sınır en
#: uzun pencerenin iki katı; şekil ölçekten bağımsız aranır (K-02), daha
#: uzun bir parça 32 noktada ayrıntısını kaybeder.
SOURCE_MIN_BARS: Final[int] = 24
SOURCE_MAX_BARS: Final[int] = 200
SOURCE_DEFAULT_BARS: Final[int] = 64

#: Radar popülasyonu (K-15): her sembolün son penceresi — ama yalnız o
#: pencere matrisin en yeni penceresine bu kadar bar yakınsa. Izgara 0'dan
#: STRIDE ile hizalandığı için güncel bir sembolün son penceresi en fazla
#: STRIDE−1 bar geride biter; daha gerisi delist olmuş (ya da verisi
#: güncellenmemiş) bir semboldür. Ölçüldü: sınır yokken her matriste ~1.095
#: radar satırının ~640'ı delist sembollerin yıllar önceki son penceresiydi,
#: ~106'sı likidite maskesinden geçip "şu an buna benziyor" diye aranıyordu.
LIVE_MAX_LAG_BARS: Final[int] = STRIDE - 1

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
    "1d": 5,
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

#: **Fiyat sürekliliği** invariant'ı (F4). Bar-bar fiyat oranı bu değeri
#: aşıyorsa bu bir fiyat hareketi değil, **redenominasyon / token swap /
#: ticker yeniden kullanımı**dır ve pencereyi de sonucu da geçersiz kılar.
#:
#: Ölçüm (1.146 parite, 1d): 3-8x bandında 52 sembol (gerçek pump olabilir),
#: 8-20x bandında 6 (STRAX, VIDT, SKY, SNM — hepsi belgelenmiş token swap),
#: >20x bandında 12 (DREP 1:100, COCOS 1:1000, BNX...). En uç örnek
#: LUNAUSDT: 177.400x — bu bir fiyat hareketi değil, ticker'ın LUNA2 için
#: yeniden kullanılmasıdır.
PRICE_CONTINUITY_MAX_RATIO: Final[float] = 10.0

#: **İkiz (türev) varlık** filtresi: günlük getirisi evrendeki başka bir
#: sembolünkiyle bu korelasyonun üstünde olan ve daha KISA geçmişe sahip
#: parite evrenden düşer (WBTCUSDT ≈ BTCUSDT, WBETHUSDT ≈ ETHUSDT). Peg
#: filtresi WBTCBTC'yi (≈1,0) yakalıyordu ama WBTCUSDT 1,0'a değil BTC'ye
#: sabitli — BTC ile aynı fiyat serisidir.
#:
#: Ölçüm (1d, 1.065 sembol, ≥180 ortak gün): 0,97 üstünde yalnız 5 çift —
#: BNSOL/SOL 0,9992 · WBTC/BTC 0,9987 · WBETH/ETH 0,9986 · BETH/ETH 0,9975,
#: sonra ANCBTC/ANCUSDT 0,9771 (farklı seri: biri BTC'ye oran). Eşik bu
#: boşluğun ortasında, seçim hassas değil. Etkisi: 28 hücrede 9.981
#: eşleşmenin 40'ı ikiz sembolde, 9'u aslıyla aynı dönemde (çift sayım);
#: Radar ve grafik sorgusunda ise ikiz, aslının en üst "benzeri" çıkıyordu.
TWIN_MIN_CORR: Final[float] = 0.99
TWIN_MIN_OVERLAP_BARS: Final[int] = 180

#: Kaldıraçlı token sonekleri (BTCUPUSDT, ETHDOWNUSDT...). Bunlar spot parite
#: değil, **çürüyen türev ürünlerdir**: periyodik yeniden fiyatlandırma yaptıkları
#: için tek barda 100.000x "hareket" üretirler. Evrenden düşerler.
LEVERAGED_TOKEN_SUFFIXES: Final[tuple[str, ...]] = ("UP", "DOWN", "BULL", "BEAR")

#: Aramada varsayılan minimum genlik (%). Eşik teorik olarak seçilemez:
#: doğru değer korpusun oynaklık dağılımına bağlıdır ve zaman dilimine göre
#: değişir. Ölçüt: likit pencerelerin %95'ini koru — patolojik kuyruğu kes,
#: veriyi budama. Üretim: ``python -m tools.measure_amplitude``.
#:
#: **4h ÖLÇÜLDÜ** (29 Ağu 2026, 4.644.712 likit pencere): p05 %6,0 ·
#: p25 %13,0 · medyan %21,8 → eşik %6,0, korunan %95,0. Buradaki değer
#: daha önce √6 ölçeklemesinden TAHMİN edilmişti ve "geçici — ölçülmedi"
#: notu taşıyordu; ölçüm tahmini doğruladı, sayı değişmedi ama artık
#: dayanağı var. (Ölçüm ancak 4h evreni 80'den 1.097 sembole çıkarılıp
#: matrisler yeniden kurulduktan sonra anlamlıydı.)
#:
#: 1d değeri F3.5'te ölçüldü ve **değiştirilmedi**. Bugünkü korpusta aynı
#: ölçüt %18,5 veriyor; %15 ise pencerelerin %96,9'unu koruyor (F3.5'te
#: %95,2'ydi). Fark korpus değişiminden gelir — evren, peg filtresi ve
#: süreklilik invariant'ı o günden beri değişti. Kalibre edilmiş bir sabiti
#: ve ona bağlı tüm F3/F4 ölçümlerini tek taraflı kaydırmak yerine fark
#: kayda geçiriliyor.
DEFAULT_MIN_AMPLITUDE: Final[dict[str, float]] = {
    "4h": 6.0,  # ölçüldü (29 Ağu 2026) — korunan %95,0
    "1d": 15.0,  # ölçüldü (F3.5); bugünkü korpusta ölçüt %18,5 verir
}


# ---------------------------------------------------------------------------
# K-03 / K-09 / K-11 — Kaskad arama
# ---------------------------------------------------------------------------

#: Aşama 1 (kosinüs) çıktısında tutulacak aday sayısı.
#:
#: 5.000'den 12.500'e çıkarıldı (Eylül 2026). Sebep: yapısal imza filtresi
#: (K-04 Eylül eki) adayların %70-85'ini eliyor ve bu, istatistiksel gücü
#: düşürüyordu (F4.8: ortalama N 291→114). Filtre yalnız Aşama 2'ye giren
#: adaylar üzerinde çalıştığı için havuzu büyütmek kaybın bir kısmını geri
#: veriyor — ölçüldü, 4h'de şablon başına sonuç 224 → 358.
STAGE1_TOPK: Final[int] = 12_500

#: Pre-NMS sonrası Aşama 2'ye (DDTW) girecek aday sayısı.
#:
#: 1.000 → 2.500. Maliyet ölçüldü (ısınmış önbellekle, 5 şablon):
#:
#:   4h : medyan 251 → 333 ms · en kötü 275 → 400 ms
#:   1d : medyan 114 → 211 ms · en kötü 148 → 237 ms
#:
#: Performans bütçesi (§15) toplam arama için < 500 ms diyor; en kötü durum
#: 400 ms ile içeride. Aşama 2 aday başına ~35 µs, yani doğrusal ve öngörülür.
STAGE2_TOPK: Final[int] = 2_500

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

Stage2Metric = Literal["ddtw", "dtw", "hybrid", "hybrid_central"]

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
    # K-11 açık sorusunun ölçüm adayı — VARSAYILAN DEĞİL. F3 prosedürüyle
    # değil, hybrid ile AYNI SEÇİCİLİK ilkesiyle türetildi
    # (tools/calibrate_metric): gerçek 1d verisinde 40.000 pencere × 4 uzunluk
    # × 14 şablon, hybrid ile sıra korelasyonu 0,999. İyi belirlenen tek çapa
    # esnek kademe (seçicilik %1,16 → 0,0773, oran 0,9246); katı/orta o oranla
    # ölçeklendi — rastgele pencerelerin neredeyse hiçbiri o eşiklerin altında
    # olmadığı için doğrudan tahminleri gürültülü ve yalnız yedek yolda
    # kullanılıyorlar. Yöntem doğrulaması: aynı araç F3'te bağımsız kalibre
    # edilmiş dtw eşiklerini %5 içinde yeniden üretiyor.
    "hybrid_central": {"strict": 0.0159, "medium": 0.0252, "flexible": 0.0773},
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
#:
#: Eşik bu örneklemin DERİN bir yüzdeliğidir: "orta" %0,25 → 2.000'lik
#: örneklemde ~5. en küçük değer, "katı" %0,05 → tek bir değer. Bu kadar
#: derin sıra istatistiği gürültülüdür ve hangi pencerelerin çekildiğini
#: yalnız tohum belirler. Ölçüldü (Eylül 2026, 6 şablon × 6 tohum, veri ve
#: motor sabit, yalnız NULL_SEED değişiyor): orta toleransta eşleşme sayısının
#: değişim katsayısı n = 2.000'de 1d 0,124 · 4h 0,087 (flama 334–552),
#: n = 20.000'de 1d 0,048 · 4h 0,021. Matris 4 ikiz sembol eksilince bile
#: satır indeksleri kaydığı için null yeniden çekiliyor ve anlamlı hücre
#: kümesi değişiyordu — "sınırdaki bulgu kırılgandır" (F4.7) kaydındaki
#: oynamanın bir kısmı verinin değil bu gürültünün eseriydi.
#:
#: Bedel: soğuk aramada 1d ~230 → ~610 ms, 4h ~370 → ~770 ms (DTW çekirdeği
#: ×3,7 hızlandırıldıktan sonra); null önbellekte olduğu için sıcak arama
#: değişmez, kütüphane şablonları açılışta ısıtılır (§15).
NULL_SAMPLE_SIZE: Final[int] = 20_000

#: Null örneklemi sabit tohumlu → aynı sorgu aynı sonucu verir (tekrarlanabilirlik).
NULL_SEED: Final[int] = 20_260_731

#: Bu sayının altında örneklem varsa yüzdelik güvenilmez → mutlak eşiğe düşülür.
NULL_MIN_SAMPLES: Final[int] = 200

#: Null dağılımı (sorgu, uzunluk, metrik, maske) başına sabittir; önbellek
#: Radar'ın 5 dakikalık cron döngüsünde ilk çağrı dışındaki maliyeti kaldırır.
#: Girdi başına ~160 KB (20.000 float64) → dolu önbellek ~20 MB.
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

# ---------------------------------------------------------------------------
# Yapısal imza filtresi — "çizdiğim formasyonu bulmuyor" şikâyetinin cevabı
#
# Ölçülen sorun (4h, ilk 12 sonuç, bağımsız yapı denetimi ile —
# `tools/formation_audit`): sonuçların yalnız **%42'si** gerçekten o
# formasyondu. İkili tepede 12'de 3. DTW noktaları hizalar, hizalanan
# noktaların SEVİYELERİNİN mantıklı olup olmadığına bakmaz (K-04'ün F3.5 eki).
#
# Denenen üç yol:
#
#   ham (filtresiz)                        %42
#   çapa tabanlı kısıt katmanı (K-04 eki)  %54   — OBO'da KÖTÜLEŞTİ (6→4)
#   sorgudan türetilen yapısal imza        %100
#
# Çapa yolu iki yerde tıkanıyordu: serbest çizimde meta-veri yok (ürünün
# yarısı), ve çapalar DTW hizalama yolundan okunduğu için yol bozulduğunda
# kural da bozuluyor. Yapısal imza kuralı **çizimin kendisinden** türetir;
# formasyon başına kod yoktur, K-04 aynen korunur.
#
# Maliyet ölçüldü: kosinüs 0,930→0,914 · 0,940→0,916 · 0,919→0,889 ·
# 0,923→0,899 (ortalama ~0,02 kayıp), hayatta kalan 31–67 sonuç (12
# gösteriliyor), ~50 ms.
# ---------------------------------------------------------------------------

#: Bir tepenin/dibin "gerçek" sayılması için gereken en az belirginlik
#: (z-score birimi — pencere z-score'lu olduğu için ölçek-değişmez).
STRUCTURE_PROMINENCE: Final[float] = 0.5

#: İki ucun "yaklaşık eşit" sayılacağı fark (z birimi). Şablon
#: meta-verisindeki level_match toleransıyla aynı mertebede.
STRUCTURE_EQUAL_TOL: Final[float] = 0.8

#: Filtre açık mı. Kapatıldığında motor F4.7 öncesi davranışa döner.
STRUCTURE_FILTER: Final[bool] = True

#: --- İmza kararlılık kapısı (K-20, Eylül düzeltmesi) -----------------------
#:
#: İmza uç DÜZENİNİ okur. Bazı formasyonları tanımlayan şey uç düzeni değil
#: EĞİMDİR: yükselen üçgeni "iki tepe" değil, yatay direnç + yükselen dipler
#: tanımlar. Böyle şekillerde imza kararsızdır — sorguya küçük bir gürültü
#: uç sayısını değiştirir. Kararsız bir kuralla adayları elemek, yapıya göre
#: değil gürültüye göre elemektir.
#:
#: Kararlılık = sorguya σ gürültü eklendiğinde imzanın hayatta kalma oranı
#: (128 çekim, sabit tohum). Ölçülen (ayna hatası düzeltildikten sonra):
#:
#:   OBO 100 · fincan 100 · yuvarlak dip 100 · ters OBO 99 · ikili tepe 98
#:   ikili dip 98 · simetrik üçgen 95 · boğa bayrağı 94 · ayı bayrağı 92
#:   ‖ düşen takoz 88 · alçalan üçgen 81 · yükselen takoz 73
#:   ‖ yükselen üçgen 36 · flama 25
#:
#: **Kapı AÇIK.** İlk kararda (K-20) kapatılmıştı; o karar YANLIŞTI ve
#: gerekçesi ölçüm aracının kör noktasıydı. `tools/formation_audit` yalnız
#: KESİNLİK ölçer — motorun döndürdüğü sonuçlara bakar. Filtre gerçek
#: formasyonları eliyorsa denetçi onları hiç görmez; kalanlar tanımı aynı
#: oranda geçtiği için filtre "etkisiz" görünür. Zarar duyarlılıktaydı.
#:
#: Ground truth ölçümü (tools/gt_benchmark, enjekte edilmiş formasyon):
#:
#:   kapılı filtre  202/288 · duyarlılık %67
#:   filtresiz      184/288 · duyarlılık %61
#:
#: Kazanç dönüş ailesinde yoğunlaşır (OBO 16→21 · ters OBO 15→22 · ikili
#: tepe 14→18 · ikili dip 16→19); eğim ailesinde kapı filtreyi zaten
#: çoğunlukla kapatır.
#:
#: Gerçek piyasa zemininde de replike edildi (dağıtıcılar gerçek veri):
#: kapılı 210/288 · %69 duyarlılık ‖ her sorguda filtre 183/267 · %61.
STRUCTURE_NOISE_SIGMA: Final[float] = 0.10

#: Kararlılık tahmininin çekim sayısı. 128 → standart hata ~0,03; eşiğin
#: iki yanındaki boşluk (%80-%91) bundan çok daha geniş. Maliyet 11 ms.
STRUCTURE_STABILITY_DRAWS: Final[int] = 128

#: Sabit tohum: arama yeniden üretilebilir olmalı.
STRUCTURE_STABILITY_SEED: Final[int] = 0

#: Okumanın "sağlam" sayılacağı kararlılık. Ölçülen boş bandın (%80-%91)
#: ortasına konur, kenarına değil.
STRUCTURE_MIN_STABILITY: Final[float] = 0.85

#: Kapı açık mı. Kapatıldığında filtre her sorguda uygulanır (K-20 öncesi
#: davranış) — eğim tabanlı formasyonlarda duyarlılığı düşürür.
STRUCTURE_STABILITY_GATE: Final[bool] = True

#: Filtre sonrası bu sayının altında aday kalırsa filtre UYGULANMAZ.
#: Gerekçe: "yapıya uyan yok" ile "hiç sonuç yok" farklı şeylerdir; ikincisi
#: kullanıcıya motorun bozuk olduğunu düşündürür. Geri düşüldüğünde yanıt
#: bunu uyarı olarak taşır — sessizce filtresiz sonuç döndürmek yalan olurdu.
STRUCTURE_MIN_SURVIVORS: Final[int] = 12

#: --- Zarf imzası (trend çizgisi katmanı) -----------------------------------
#:
#: Yapısal imza uç DÜZENİNİ okur; eğimle tanımlı formasyonlarda (üçgen,
#: takoz, flama, bayrak) bilgi taşımaz (K-20). Bu katman trend çizgilerini
#: okur: dokunuş noktalarından üst ve alt zarfa regresyon, eğim sınıfı.
#:
#: Ölçüldü (tools/gt_benchmark, ground truth): aynı korpusta gürültü
#: sembolü 40 → 120 → 300 yapıldığında duyarlılık sabit (%58), kesinlik
#: %88 → %65 → %58. Motor enjekte edilen üçgenleri her yoğunlukta buluyor;
#: kaybettiği yer sıralama. Gerçek korpusta ölçülen %34 bu eğrinin devamı.

#: Zarf dokunuşu için yerel pencere yarıçapı (bar). 2 → 5 barlık pencere.
ENVELOPE_TOUCH_WIDTH: Final[int] = 2

#: Eğimin "yatay" ile "eğimli" arasındaki sınırı (z birimi / tam pencere).
#: Kanonik ölçümlerin ortasına konur: yatay zarflar 0,01-0,03 · eğimli
#: zarflar 0,89-4,32. Aradaki bant tamamen boş.
ENVELOPE_SLOPE_THRESHOLD: Final[float] = 0.8

#: Kuralın KAYNAĞI için ölü bant: sorgunun eğimi eşiğe bu kadar yakınsa
#: sınıfı yazı-turadır ve o sorgudan kural türetilmez. Adaylar tek eşikle
#: sınıflanır — onlarda karar zaten kuralın kendisi değildir.
ENVELOPE_DEAD_BAND: Final[float] = 0.2

#: Zarf imzasının "sağlam" sayılacağı kararlılık. Ölçülen (σ=0,10, 300
#: çekim) boş bandın ortasına konur: simetrik üçgen 100 · yükselen takoz
#: 100 · düşen takoz 99 · yükselen üçgen 99 · alçalan üçgen 99 ‖ ayı
#: bayrağı 78 · boğa bayrağı 76 ‖ ters OBO 45 · OBO 41.
#:
#: Son çift kapının asıl gerekçesi: OBO'nun zarf imzası (0,0,0) ile
#: TANIMLIDIR ama yazı-turadır. Kapısız bir zarf filtresi dönüş ailesini —
#: motorun tek güçlü olduğu aileyi — gürültüyle elerdi.
ENVELOPE_MIN_STABILITY: Final[float] = 0.90

#: Yapısal filtre, zarf filtresi devredeyken ÇEKİLİR: iki katman üst üste
#: değil, birbirinin alternatifidir. Trend çizgisi okuması kararlıysa
#: formasyon eğimle tanımlıdır ve uç SAYISI sorulmaz.
#:
#: Bulgu (düşen takoz, en zayıf formasyon): 2.000 sonuç derinliğinde enjekte
#: edilen takozların üçte biri hiç dönmüyordu (duyarlılık %67); yapısal
#: filtre kapatılınca %96. Takozun yapısal imzası ("2 belirgin tepe · ilki
#: en yüksek") sorguya eklenen gürültüye karşı kararlı (%88, kapıyı geçiyor)
#: ama gerçek takozlar 2 ya da 3 kez dokunur — kapı eklenen gürültüye karşı
#: kararlılığı ölçer, formasyonun doğal çeşitliliğine karşı ölçmez. Zarf
#: filtresi ise aynı derinlikte 140 sahtekârı 1 doğru kaybıyla eliyordu.
#:
#: Ölçüm (tools/gt_benchmark --compare-yield, alternatif / yığın):
#:   sentetik, ilk 24          düşen takoz 10 / 9   · genel 203 / 202
#:   sentetik, havuz 2.000     düşen takoz duyarlılık %96 / %67
#:   gerçek piyasa, ilk 24     düşen takoz 14 / 11  · genel 209 / 206
#:   elle çizim (6/formasyon)  düşen takoz 63 / 61  · genel 1171 / 1169
#:   sentetik, 2. tohum        düşen takoz 12 / 9   · genel 209 / 206
#: Beş ölçümün hiçbirinde bir formasyon kötüleşmiyor. Kural yalnız iki
#: okumanın birden kararlı olduğu sorgulara dokunur (kanonik şablonlarda
#: yalnız düşen takoz; elle çizimde 6'da 1 takoz).
STRUCTURE_YIELDS_TO_ENVELOPE: Final[bool] = True

#: Zarf filtresi açık mı. Ölçüm sonucu için bkz. K-21.
ENVELOPE_FILTER: Final[bool] = True

#: Zarf filtresi sonrası bu sayının altında aday kalırsa UYGULANMAZ —
#: yapısal filtredeki gerekçenin aynısı.
ENVELOPE_MIN_SURVIVORS: Final[int] = 12

#: --- İki rejimli (direk + gövde) zarf imzası (K-22) ------------------------
#:
#: Bayrak ve flama gibi iki rejimli şekillerde pencerenin başındaki dik
#: dürtü (direk, ~%35), z-score varyansını tek başına domine eder ve geri
#: kalan konsolidasyon gövdesinin zarf eğimlerini bastırır. Ölçüldü: flama
#: tam pencere zarfında (-0,90, +0,89) eğim vererek K-21'in ölü bandına
#: (0,80 ± 0,20) düşüyor ve hiç filtrelenemiyordu (formation_audit 4h ilk
#: 12'de 1/12 = %8); boğa/ayı bayrağında ise direk tabanındaki tek bir iç
#: dokunuş tüm pencere regresyonunu bozuyordu (ilk 50'de %50–%62).
#:
#: Kural yine SORGUDAN türer (formasyon başına kod yok, K-04): sorgunun bir
#: ucunda dik bir direk (>= 2,0σ) ve karşı tarafında daha dar bir gövde
#: (açıklık <= 0,65 × direk) varsa, zarf eğimleri yalnız gövde dilimi
#: üzerinde okunur. Hem baştaki hem sondaki direk simetrik okunur (zaman-ayna
#: eşdeğerliği).
REGIME_FILTER: Final[bool] = True
REGIME_POLE_K: Final[int] = 11
REGIME_BODY_START: Final[int] = 8
REGIME_POLE_HEIGHT: Final[float] = 1.5
REGIME_POLE_STRICT_HEIGHT: Final[float] = 2.0
REGIME_SLOPE_THRESHOLD: Final[float] = 0.25
REGIME_CONVERGENCE: Final[float] = 0.80
REGIME_MIN_STABILITY: Final[float] = 0.85
REGIME_MIN_SURVIVORS: Final[int] = 6

#: --- Sürekli sol-kuyruk yüzdeliği ve yapısal yeniden sıralama (K-23) -------
#:
#: 1) Empirik null yüzdeliğinde ``d < null[0]`` olan tüm adaylar 0,0 yüzdelik
#:    alıp Post-NMS'te birbirine eşitleniyor ve Aşama 1 kosinüs sırasına geri
#:    düşüyordu. Sol kuyruk ``p01``'e doğrusal çapalanarak sıralama korunur.
#: 2) Sert filtreyi geçen adaylar arasında sorgunun sürekli yapısal/zarf
#:    özelliklerinden (düz kenar eğimi, daralma oranı, karşı taraf uç sayısı,
#:    çanak kenar simetrisi) sapanlara küçük sürekli ceza eklenir.
STRUCTURAL_RERANK: Final[bool] = True

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

#: İleri yol fanı (engine/outcome/paths.py): zaman bariyerine göre normalize
#: edilmiş ızgaranın nokta sayısı ve gösterilen yüzdelikler. 21 nokta →
#: bariyerin her %5'i; 24 barlık pencerenin bariyeri (12 bar) bile ara
#: değerlemeyle temsil edilir.
FAN_GRID_POINTS: Final[int] = 21
FAN_QUANTILES: Final[tuple[float, ...]] = (0.10, 0.25, 0.50, 0.75, 0.90)

#: İşlem maliyeti tabanı: 1*ATR / close bu oranın altındaysa pencere
#: istatistiğe girmez (K-16.7). Binance taker gidiş-dönüş ~%0.1 + slipaj.
MIN_ATR_PCT: Final[float] = 0.01

#: Gölge dağılımda her eşleşme için çekilecek kontrol penceresi sayısı (K-12).
SHADOW_SAMPLES_PER_MATCH: Final[int] = 20

# ---------------------------------------------------------------------------
# F4.6 — Ön-getiri eşleştirmeli gölge (vekil testi)
#
# Şüphe: short yönde iyi çıkan formasyonların hepsi yükselen bir hareketin
# tepesinde bitiyor. Ölçülen şey formasyonun ŞEKLİ değil, "yakın zamanda çok
# yükseldi" nin ortalamaya dönüşü olabilir. Bunu ayırmak için gölge havuzuna
# "benzer ön-getiri" kısıtı eklenir.
#
# Fallback zinciri (gölge tüketimi riski):
#   1) Bandı genişlet (±0.25σ → ±0.50σ)
#   2) Hâlâ yoksa ay kısıtını ±1 ay esnet
#   3) Hâlâ yoksa uyarı ver
# ---------------------------------------------------------------------------

#: Pencere ön-getirisi eşleştirme bandı (evren geneli σ'nın katı).
RETURN_MATCH_BAND_SIGMA: Final[float] = 0.25

#: Duyarlılık testi için band genişlikleri.
RETURN_MATCH_BAND_SENSITIVITY: Final[tuple[float, ...]] = (0.15, 0.25, 0.50)

#: Fallback'te bandı bu değere kadar genişletmeye izin verilir.
RETURN_MATCH_BAND_FALLBACK: Final[float] = 0.50

#: Fallback'te ay kısıtını bu kadar ay genişletmeye izin verilir (±).
RETURN_MATCH_MONTH_EXPAND: Final[int] = 1

#: Binance taker gidiş-dönüş komisyonu (~%0,05 × 2). Brüt ve net ayrı raporlanır.
#: MIN_ATR_PCT tabanına EKtir: taban patolojik pencereyi eler, komisyon
#: düzeltmesi kalanların getirisini gerçekçileştirir.
ROUNDTRIP_FEE_PCT: Final[float] = 0.001

#: ATR ısınma süresi (2 × ATR_PERIOD). Wilder ATR bir EMA özyinelemesidir;
#: 14 barda tohumlanır ama ~2 periyot yakınsamaya devam eder. Ayrıca
#: listeleme günlerinin pump/dump oynaklığı hem ATR'yi hem sonucu bozar.
MIN_BARS_SINCE_LISTING: Final[int] = 2 * ATR_PERIOD

#: p-hacking kilidi: outcome daima bu kademeyle hesaplanır. Skorlar yüzdelik
#: olduğu için kademe değişince N ve beklenti de değişir; kademe oynatarak
#: sayı güzelleştirmek yasaktır.
OUTCOME_TOLERANCE: Final[str] = "medium"

#: Güven aralığı: hiçbir sayı GA'sız yayınlanmaz.
#: Beklenti (R) sürekli değişken → bootstrap; başarı oranı → Wilson.
CONFIDENCE_LEVEL: Final[float] = 0.95
BOOTSTRAP_SAMPLES: Final[int] = 10_000

#: Rejim kırılımı. Yıl bazında kırmak hücre başına ~14 olay bırakır —
#: kullanılamaz. Üç kaba rejim, (başlangıç yılı, bitiş yılı) dahil.
REGIMES: Final[tuple[tuple[str, int, int], ...]] = (
    ("2017-2020", 2017, 2020),
    ("2021-2022", 2021, 2022),
    ("2023+", 2023, 9999),
)

#: Bu sayının altındaki rejim hücresi "yetersiz örnek" işaretlenir.
MIN_REGIME_N: Final[int] = 30

#: Bu sayının altında BAŞLIK istatistikleri de "yetersiz örnek" işaretlenir.
#:
#: Rejim satırlarının bayrağı vardı, başlık sayılarının yoktu — ve boşluk
#: ölçüldü: `symmetrical_triangle` 1d'de yalnız 4 eşleşme veriyor (null
#: yayılımı 2,4 ile 14 şablonun en düşüğü), buna rağmen API "beklenti
#: +0,803R" diye normal bir kart döndürüyordu. Güven aralığı doğruydu
#: ([-0,39; +2,00]) ve hüküm "anlamlı fark ölçülemedi" diyordu, ama ekranın
#: ortasındaki sayı yine de +0,80R'ydi.
#:
#: Ayrı bir sabit: rejim hücresiyle başlık sayısının eşiği aynı olmak
#: zorunda değil, ikisi farklı soruları yanıtlar.
MIN_EVENTS_FOR_CLAIM: Final[int] = 30


# ---------------------------------------------------------------------------
# K-08 — Sayfalama
# ---------------------------------------------------------------------------

PAGE_SIZE: Final[int] = 12


# ---------------------------------------------------------------------------
# F5 — API katmanı
# ---------------------------------------------------------------------------

#: Bir aramada önbelleğe alınan eşleşme sayısı. Sayfalama bu havuzdan beslenir;
#: "Daha fazla" tüm matrisi yeniden skorlamaz (K-08).
#:
#: **Bu bir gösterim sabiti DEĞİL, örneklem sınırıdır.** ``/stats`` istatistiği
#: bu havuzdan hesaplar (K-09: ekranda görülen olaylar). Havuz post-NMS
#: toplamının altında kalırsa üç sayı birbirinden ayrışır: başlıkta yazan
#: eşleşme sayısı, sayfalanabilen liste ve istatistiğin N'i. Üstelik kırpma
#: rastgele değildir — en iyi sıralanmış olanları tutar, yani istatistik
#: **yanlı bir alt örneklemden** hesaplanırdı.
#:
#: Ölçüm (8 Eyl 2026, 14 şablon × 2 dilim, orta tolerans): en yüksek toplam
#: **758** (rounding_bottom, 4h); 600 sınırını 4h'de 5 şablon aşıyordu
#: (bear_flag 736, rounding_bottom 758, bull_flag 650, cup_and_handle 635,
#: pennant 605). 4h evreni 80 sembolden 1.097'ye çıkınca ortaya çıkan bir
#: sorun — eski korpusta hiçbir şablon 600'e yaklaşmıyordu.
#:
#: 2.000: gözlenen en yüksek değerin ~2,6 katı, korpus büyümesine pay bırakır.
#: Bellek maliyeti arama başına ~600 KB (TTL 1 saat).
SEARCH_CACHE_MATCHES: Final[int] = 2_000

#: DTW hizalama yolu yalnızca ilk N eşleşme için hesaplanır — yol çıkarımı
#: aday başına O(32²) Python döngüsüdür, sıcak yolda değildir.
WARP_PATH_TOP_N: Final[int] = 60

#: Gösterilecek eşleşmelerin bar bazında ince ayarı — ÖLÇÜLDÜ, KAPALI.
#:
#: Hipotez: matris STRIDE=3 ile kurulduğu için gösterilen pencere en iyi
#: hizadan 1-2 bar kaymış olabilir. tools/verify_stage1 stride bedelini
#: doğruladı: kaba kuvvet (stride 1) ile matrisin en iyi penceresi arasında
#: kosinüs farkı ortalama +0,021 · %95 +0,074 · en kötü +0,096.
#:
#: Ama telafi denendiğinde hipotez ÇÖKTÜ. 1d, 5 şablon, ilk 60 eşleşme;
#: ±(STRIDE-1) barlık pencerede üç ayrı hedefle tarandı:
#:
#:   hedef                              Δmesafe    Δkosinüs
#:   mesafeyi enküçült                 -0,00207     -0,0145
#:   kosinüsü enbüyült                 +0,00171     +0,0063
#:   mesafeyi bozmadan kosinüs enbüyük -0,00121     -0,0018
#:
#: Hiçbiri ikisini birden iyileştirmiyor: iki metrik alt-stride hizalamada
#: birbiriyle TAKAS ediyor. Kısıtlı varyantta bile (mesafe asla artmaz)
#: kosinüs düşüyor — yani mesafeyi iyileştiren offsetler görsel benzerliği
#: bozuyor. Eşikler mesafe üzerinde kalibre edildiği için kosinüs hedefiyle
#: açmak, kalibre edilmiş eşiği sessizce kaydırırdı.
#:
#: Sonuç: pencere sınırları algılanan uyumsuzluğun sebebi DEĞİL. Kod
#: engine/search/refine.py'de duruyor (K-04'ün kısıt katmanı gibi: ölçülmüş
#: katkı göstermeyen katman bağlanmaz), bayrakla açılabilir.
REFINE_MATCHES: Final[bool] = False

#: İnce ayar açılırsa uygulanacağı eşleşme sayısı (bar verisi gerektirir).
REFINE_TOP_N: Final[int] = 120

#: Eşleşme karosunda pencerenin iki yanına eklenen bağlam barı, pencere
#: uzunluğunun oranı olarak. Bağlamsız bir karo "formasyon nereden geldi,
#: sonra ne oldu" sorusunu cevaplayamaz.
CHART_CONTEXT_RATIO: Final[float] = 0.4

#: Oturum başına dakikalık arama limiti. Her arama tam matris taramasıdır.
SEARCH_RATE_LIMIT: Final[int] = 30

#: Tazelik raporu bu kadar saniye önbellekte tutulur (her sembolün parquet
#: ayak izini okumak arama başına yapılacak iş değildir).
FRESHNESS_TTL_SECONDS: Final[int] = 60


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
