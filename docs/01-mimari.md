# GraphFlow — Sistem Mimarisi

> **Belge türü:** Teknik Mimari Spesifikasyonu
> **Tarih:** 27 Temmuz 2026
> **Durum:** Uygulamaya hazır
> **Kararların gerekçeleri:** [00-tasarim-kararlari.md](00-tasarim-kararlari.md)

Bu belge **ne inşa edileceğini** tanımlar. **Neden böyle inşa edileceği** karar kaydı belgesindedir; tekrar edilmez, referans verilir.

---

## İçindekiler

1. [Sistem Genel Görünümü](#1-sistem-genel-görünümü)
2. [Veri Katmanı](#2-veri-katmanı)
3. [Normalizasyon Pipeline'ı](#3-normalizasyon-pipelineı)
4. [Matris Yapısı](#4-matris-yapısı)
5. [Arama Motoru (Kaskad)](#5-arama-motoru-kaskad)
6. [Sorgu Modları](#6-sorgu-modları)
7. [Şablon Kütüphanesi](#7-şablon-kütüphanesi)
8. [Outcome Engine (Sonuç Motoru)](#8-outcome-engine-sonuç-motoru)
9. [Cache Katmanı](#9-cache-katmanı)
10. [API Spesifikasyonu](#10-api-spesifikasyonu)
11. [Frontend Mimarisi](#11-frontend-mimarisi)
12. [Repo Yapısı](#12-repo-yapısı)
13. [Teknoloji Yığını](#13-teknoloji-yığını)
14. [Yol Haritası](#14-yol-haritası)
15. [Performans Bütçesi](#15-performans-bütçesi)
16. [Doğrulama Protokolü](#16-doğrulama-protokolü)

---

## 1. Sistem Genel Görünümü

```
┌──────────────────────────────────────────────────────────────────────┐
│                          FRONTEND (Next.js)                          │
│                                                                      │
│  ┌────────────┐  ┌──────────────────────┐  ┌────────────────────┐    │
│  │ Kütüphane  │  │   Kanvas             │  │  Sonuç Grid'i      │    │
│  │ (şablonlar)│─▶│  (Canvas + pointer)  │  │  3×4 = 12          │    │
│  └────────────┘  └──────────────────────┘  │  Lightweight Charts│    │
│                            │                └────────────────────┘    │
│                     32 nokta dizisi                  ▲               │
└────────────────────────────┼─────────────────────────┼───────────────┘
                             │ POST /api/search        │ GET /results
                             ▼                         │
┌──────────────────────────────────────────────────────┼───────────────┐
│                      API KATMANI (FastAPI)           │               │
│                                                       │               │
│   ┌──────────────────────────────────────────────────┴────────┐      │
│   │                   SearchEngine                            │      │
│   │                                                            │      │
│   │  Aşama 1: Kosinüs (vektörize)      ~12M → ~5.000          │      │
│   │      ↓                                                     │      │
│   │  Pre-NMS: 1D-IoU, gevşek (%70)     ~5.000 → ~1.000        │      │
│   │      ↓                                                     │      │
│   │  Aşama 2: DDTW + Sakoe-Chiba       ~1.000 → skorlanmış    │      │
│   │      ↓                                                     │      │
│   │  Post-NMS: IoU %50 + max/symbol=3  → nihai sıralı liste   │      │
│   └────────────────────────────┬───────────────────────────────┘      │
│                                │                                      │
│   ┌────────────────────────────▼───────────────────────────────┐      │
│   │  OutcomeEngine (Triple-Barrier + Gölge Dağılım)            │      │
│   └────────────────────────────────────────────────────────────┘      │
└───────────┬───────────────────────────────────┬──────────────────────┘
            │                                   │
            ▼                                   ▼
   ┌─────────────────┐                 ┌──────────────────┐
   │  Redis          │                 │  Vektör Matrisi  │
   │  search_id →    │                 │  8 × .npy memmap │
   │  sıralı liste   │                 │  ~1,5 GB         │
   │  TTL 1 saat     │                 └────────▲─────────┘
   └─────────────────┘                          │
                                                │ offline build
   ┌────────────────────────────────────────────┴─────────────────┐
   │                    VERİ KATMANI                              │
   │                                                              │
   │   Binance REST ──▶ Ingest (Cron 5dk) ──▶ Parquet (OHLCV)     │
   │                                       └─▶ Postgres (app)     │
   └──────────────────────────────────────────────────────────────┘
```

---

## 2. Veri Katmanı

### 2.1. Kaynak

| Parametre | Değer |
|---|---|
| Borsa | Binance |
| Endpoint | `GET /api/v3/klines` (REST, ücretsiz, anahtarsız) |
| Sembol listesi | `GET /api/v3/exchangeInfo` |
| Zaman dilimleri | `4h`, `1d` |
| Geçmiş | 2017-08 → bugün |
| Parite evreni | ~500 (USDT ve BTC bazlı, **delist edilenler dahil**) |
| Güncelleme | Cron, 5 dakikada bir (yalnızca son mumlar) |

> **Not:** Delist edilmiş pariteler `exchangeInfo`'da görünmez. Tarihsel sembol listesi Binance'in veri dökümü arşivinden (`data.binance.vision`) veya saklanan geçmiş `exchangeInfo` anlık görüntülerinden türetilir. Bkz. [K-13](00-tasarim-kararlari.md#k-13--survivorship-bias-ve-göreli-likidite-filtresi).

### 2.2. Ham veri deposu — Parquet

Ham OHLCV, sembol ve zaman dilimi başına birer Parquet dosyasında tutulur:

```
data/klines/{timeframe}/{symbol}.parquet
```

**Şema:**

| Alan | Tip | Açıklama |
|---|---|---|
| `open_time` | int64 (ms) | Mum açılış zamanı, birincil anahtar |
| `open` | float64 | |
| `high` | float64 | |
| `low` | float64 | |
| `close` | float64 | |
| `volume` | float64 | Baz varlık hacmi |
| `quote_volume` | float64 | Kote varlık hacmi (likidite filtresi için) |
| `trades` | int32 | İşlem sayısı |

**Neden Parquet, neden Postgres değil:** Sıcak yol (arama) zaten önceden hesaplanmış vektör matrisindedir. Ham mumlara yalnızca (a) matris inşasında ve (b) sonuç grafiği render'ında erişilir; ikisi de sütun bazlı toplu okumadır — Parquet'in tam olarak optimize olduğu erişim deseni. Bkz. [K-01](00-tasarim-kararlari.md#k-01--ölçek-gerçeği-problem-sanıldığı-kadar-büyük-değil).

### 2.3. Uygulama veritabanı — Postgres

Kullanıcı hesapları, kaydedilmiş çizimler, arama geçmişi, şablon kütüphanesi metadata'sı.

```sql
CREATE TABLE symbols (
    symbol        TEXT PRIMARY KEY,
    base_asset    TEXT NOT NULL,
    quote_asset   TEXT NOT NULL,
    listed_at     TIMESTAMPTZ,
    delisted_at   TIMESTAMPTZ,          -- NULL = hâlâ aktif
    status        TEXT                  -- TRADING | BREAK | DELISTED
);

CREATE TABLE liquidity_rank (
    symbol        TEXT NOT NULL,
    month         DATE NOT NULL,        -- ayın ilk günü
    quote_volume  DOUBLE PRECISION,
    pct_rank      REAL,                 -- 0..1, o ayın kesitinde
    PRIMARY KEY (symbol, month)
);

CREATE TABLE saved_queries (
    id            UUID PRIMARY KEY,
    user_id       UUID,
    name          TEXT,
    points        REAL[],               -- 32 elemanlı normalize dizi
    params        JSONB,
    created_at    TIMESTAMPTZ DEFAULT now()
);
```

`liquidity_rank` tablosu, [K-13](00-tasarim-kararlari.md#k-13--survivorship-bias-ve-göreli-likidite-filtresi)'teki aylık kesitsel likidite filtresini besler ve matris inşasında maske olarak kullanılır.

---

## 3. Normalizasyon Pipeline'ı

Bir pencere (uzunluk `L`, kapanış fiyatları `p₁…p_L`) şu adımlardan geçer. **Sıra önemlidir.**

### Adım 1 — Logaritmik fiyat

```python
x = np.log(p)                      # (L,)
```

### Adım 2 — Yeniden örnekleme, N = 32

```python
src = np.linspace(0, 1, L)
dst = np.linspace(0, 1, 32)
x32 = np.interp(dst, src, x)       # (32,)
```

`scipy.interpolate.interp1d` de kullanılabilir; `np.interp` lineer durumda daha hızlıdır.

### Adım 3 — Z-Score standardizasyonu

```python
mu    = x32.mean()
sigma = x32.std()                  # popülasyon std (ddof=0)
if sigma < EPS:
    return None                    # düz pencere → veri setinden düş
z = (x32 - mu) / sigma             # (32,), ‖z‖ = √32
```

### Adım 4 — Genlik meta-verisi (ham fiyatlardan)

```python
amplitude = (p.max() - p.min()) / p.min() * 100.0
```

Bkz. [K-10](00-tasarim-kararlari.md#k-10--genlik-amplitude-meta-verisi).

### Kullanıcı çizimi için aynı pipeline

Kanvastan gelen pointer noktaları, y ekseni ters çevrildikten (canvas y aşağı doğru artar) sonra **aynı Adım 2–3'ten** geçirilir. Çizimde "fiyat" olmadığı için Adım 1 (log) uygulanmaz — çizim zaten görsel/lineer uzaydadır ve z-score sonrası fark ortadan kalkar.

---

## 4. Matris Yapısı

### 4.1. Boyutlandırma

```
Zaman dilimleri     : {4h, 1d}                      →  2
Pencere uzunlukları : {24, 40, 64, 100}             →  4
                                                    ──────
Matris sayısı                                          8
```

Her matris ayrı bir `.npy` dosyasıdır:

```
data/matrix/{timeframe}_{window_length}/
    vectors.npy      # (K, 32) float32   — normalize şekil vektörleri
    meta.npy         # (K,)   yapılandırılmış dizi
```

**`meta` şeması:**

| Alan | Tip | Açıklama |
|---|---|---|
| `symbol_id` | int32 | `symbols` tablosuna indeks |
| `start_idx` | int32 | Pencere başlangıcı (bar indeksi) |
| `end_idx` | int32 | Pencere bitişi (bar indeksi, dahil) |
| `end_time` | int64 | Bitiş barının `open_time`'ı (ms) |
| `amplitude` | float32 | Genlik yüzdesi |
| `atr` | float32 | Pencere sonundaki ATR(14) |
| `liquid` | bool | O ayın kesitinde üst %40'ta mı |

### 4.2. Kayan pencere parametreleri

| Parametre | Değer | Not |
|---|---|---|
| Stride | 3 | Stride 1 ile komşu pencereler ~%99 aynı; stride 3 bilgi kaybetmeden hacmi 3'e böler. Bedeli **ölçüldü** (`tools/verify_stage1`): kaba kuvvete göre kosinüs farkı ortalama +0,021, en kötü +0,096. Telafisi denendi ve bağlanmadı (K-19) |
| Toplam pencere | ~12.000.000 (plan) | |

**Ölçülen (8 Eyl 2026, 1.097 sembol):**

| Zaman dilimi | Pencere | Likit pencere | Disk |
|---|---|---|---|
| 4h | **11.600.769** | 1.174.008 | ~1,7 GB |
| 1d | 1.884.157 | 192.481 | ~0,3 GB |
| **Toplam** | **13.484.926** | | **2,0 GB** |

Plan 12M/1,5 GB öngörüyordu; gerçek toplam yakın çıktı ama **dağılım
bambaşka**: hacmin %86'sı 4h'de. Sebebi bar yoğunluğu — aynı takvim aralığı
4h'de 6 kat fazla bar demek. 4h evreni uzun süre 80 sembolde kaldığı için bu
görülmemişti (bkz. `tools/backfill`).

### 4.3. Erişim — memmap

```python
V = np.load("vectors.npy", mmap_mode="r")     # RAM'e tam yüklenmez
```

İşletim sistemi sayfa cache'i, sık erişilen bölgeleri otomatik olarak RAM'de tutar. Sunucu RAM'i ≥ 4 GB ise matrisin tamamı pratikte cache'te kalır.

### 4.4. Yeniden inşa

- **Tam inşa:** Yalnızca ilk kurulumda veya normalizasyon parametreleri değiştiğinde
- **Artımlı (incremental):** Cron her çalıştığında yalnızca **yeni kapanan mumlar** için üretilen pencereler matrisin sonuna eklenir (append)

---

## 5. Arama Motoru (Kaskad)

### 5.1. Aşama 1 — Kosinüs Benzerliği (kaba eleme)

```python
q = normalize(user_drawing)          # (32,), z-score'lu
scores = (V @ q) / 32.0              # (K,) — Pearson korelasyonuna eşdeğer
```

- **Maliyet:** ~384M FLOP → **0,1–0,3 sn**
- **Filtreler (maskeleme, çarpımdan önce):** `liquid == True`, opsiyonel genlik aralığı
- **Çıktı:** en yüksek skorlu ~5.000 aday (`np.argpartition`)

**Matematiksel not:** `V` satırları z-score'lu olduğu için `‖v‖ = ‖q‖ = √32`. Dolayısıyla `cos(v,q) = (v·q)/32` ve bu, iki serinin **Pearson korelasyon katsayısına eşittir**.

### 5.2. Pre-NMS — Aday çeşitlendirme

```python
def nms_1d(candidates, iou_threshold):
    kept = []
    for c in sorted(candidates, key=lambda x: -x.score):
        if all(iou(c, k) < iou_threshold
               for k in kept if k.symbol_id == c.symbol_id):
            kept.append(c)
    return kept
```

**1D-IoU:**

```python
def iou(a, b):
    inter = max(0, min(a.end_idx, b.end_idx) - max(a.start_idx, b.start_idx))
    union = (a.end_idx - a.start_idx) + (b.end_idx - b.start_idx) - inter
    return inter / union if union > 0 else 0.0
```

| Parametre | Değer |
|---|---|
| `iou_threshold` | **0,70** (gevşek) |
| Giriş | ~5.000 |
| Çıkış | ~1.000 |

Bkz. [K-09](00-tasarim-kararlari.md#k-09--çift-aşamalı-nms-deduplication).

### 5.3. Aşama 2 — DDTW (ince sıralama)

**Türev dönüşümü (Keogh & Pazzani):**

```python
def derivative(x):
    d = np.empty(len(x) - 2)
    for i in range(1, len(x) - 1):
        d[i-1] = ((x[i] - x[i-1]) + (x[i+1] - x[i-1]) / 2) / 2
    return d                          # (30,) for N=32
```

**DTW, Sakoe-Chiba bandı ile:**

| Parametre | Değer |
|---|---|
| Band yarıçapı `r` | `0,15 × N ≈ 5` |
| Mesafe metriği | Kare Öklid |
| Kütüphane | `dtaidistance` veya `tslearn` (ikisi de C hızlandırmalı) |

**Skor normalizasyonu:**

```python
normal_score = dtw_distance / path_length
```

Bu bölme olmadan farklı pencere uzunluklarından gelen skorlar kıyaslanamaz. Bkz. [K-14](00-tasarim-kararlari.md#k-14--çoklu-çözünürlük-ve-skor-kıyaslanabilirliği).

### 5.4. Post-NMS — Nihai temizlik

| Parametre | Değer |
|---|---|
| `iou_threshold` | **0,50** (katı) |
| `max_results_per_symbol` | **3** |
| Giriş | ~1.000 (DDTW skorlu) |
| Çıkış | Nihai sıralı liste |

### 5.5. Kalibrasyon ve eşikler

`Katı / Orta / Esnek` toggle'ı, `normal_score` üzerinde bir üst sınır uygular. Eşik değerleri **notebook kalibrasyonundan** (bkz. [§16](#16-doğrulama-protokolü)) ROC mantığıyla çıkarılır — teorik olarak atanmaz.

Motorun **"iyi eşleşme yok"** diyebilmesi zorunludur: hiçbir aday eşiği geçemezse boş sonuç döner.

---

## 6. Sorgu Modları

Tek sınıf, tek kod yolu. Bkz. [K-15](00-tasarim-kararlari.md#k-15--tek-motor-i̇ki-mod).

```python
class SearchEngine:
    def search(
        self,
        query: np.ndarray,            # (32,) normalize
        mode: Literal["live", "historical"],
        timeframe: Literal["4h", "1d"],
        window_lengths: list[int] = [24, 40, 64, 100],
        tolerance: Literal["strict", "medium", "flexible"] = "medium",
        min_amplitude: float | None = None,
        limit: int = 12,
    ) -> SearchResult: ...
```

| Mod | Tarama alanı | Karşılaştırma | Süre |
|---|---|---|---|
| `historical` | Tüm matris | ~12.000.000 | ~0,3 sn |
| `live` | `meta.end_idx == son_bar` maskesi | ~1.165 × 4 = ~4.660 | < 50 ms |

### Ortak kural — yarım mum maskelenir

Her iki modda da **oluşmakta olan son mum** veriden düşürülür. Radar'da bu, sinyallerin sürekli yanıp sönmesini (flicker) engeller.

### Radar önbelleği

Radar sorguları çok ucuz olduğu için, **kütüphanedeki şablonlar** için sonuçlar Cron ile 5 dakikada bir önceden hesaplanıp Redis'e yazılır. Kullanıcı sol panelden "OBO" tıkladığında sonuç **anında** gelir. Serbest çizim ise talep üzerine hesaplanır (yine < 10 ms).

**Durum: uygulandı** (`engine/api/main.py:radar_key`, `RADAR_TTL = 300`).
Ölçülen: ilk çağrı 552 ms, sonraki çağrılar **1,2 ms** — aynı `search_id`
döndüğü için sayfalama ve istatistik tutarlı kalır. Yalnız kütüphane şablonu
ve canlı mod önbelleğe girer; serbest çizimde anahtar uzayı sınırsızdır ve
isabet oranı sıfıra yakındır. Tazelik önbellekten gelmez, her çağrıda
yeniden okunur.

Arayüz de aynı aralıkta kendini yeniler. Bunu mümkün kılan şey performans
değil muhasebedir: oturum sayacı artık **ayrı hipotez** sayar (parmak izi =
şekil + parametreler), yoksa açık bırakılmış bir sekme kullanıcı hiçbir şey
denemeden Bonferroni α'sını küçültürdü.

---

## 7. Şablon Kütüphanesi

Her formasyon, **32 elemanlı kanonik bir vektör** olarak tanımlanır. Kural motoru yoktur. Bkz. [K-04](00-tasarim-kararlari.md#k-04--kural-motorunun-i̇mhası-kanonik-şablon-vektörleri).

```
engine/templates/
    reversal/
        head_and_shoulders.json
        inverse_head_and_shoulders.json
        double_top.json
        double_bottom.json
        cup_and_handle.json
        rounding_bottom.json
    continuation/
        bull_flag.json
        bear_flag.json
        pennant.json
        rising_wedge.json
        falling_wedge.json
        ascending_triangle.json
        descending_triangle.json
        symmetrical_triangle.json
```

**Şablon şeması:**

```json
{
  "id": "head_and_shoulders",
  "name_tr": "Omuz Baş Omuz",
  "name_en": "Head and Shoulders",
  "category": "reversal",
  "bias": "bearish",
  "points": [0.0, 0.3, 0.6, 0.35, 0.2, 0.55, 0.9, 1.0, ...],
  "icon": "obo.svg",
  "description_tr": "..."
}
```

`points` dizisi yüklenirken aynı z-score normalizasyonundan geçirilir. **Yeni formasyon eklemek = yeni bir JSON dosyası** — kod değişikliği gerektirmez.

Kural mantığı yalnızca geometriye indirgenemeyen ek filtreler için kullanılır (hacim teyidi, boyun çizgisi kırılımı) ve **opsiyonel eklenti** olarak tasarlanır.

---

## 8. Outcome Engine (Sonuç Motoru)

Yalnızca `historical` modda çalışır. Ürünün ana farklılaştırıcısıdır. Bkz. [K-06](00-tasarim-kararlari.md#k-06--öldürücü-özellik-sonra-ne-oldu) ve [K-16](00-tasarim-kararlari.md#k-16--triple-barrier-atr-tabanlı-göreli-bariyerler).

### 8.1. Triple-Barrier tanımı

Formasyonun bittiği bar `t₀`, kapanış `C₀`, `ATR = ATR(14)` (yalnızca `t₀`'a kadarki barlardan — **lookahead yok**).

| Bariyer | Değer |
|---|---|
| Kâr Al (TP) | `C₀ + k_tp × ATR` |
| Zarar Kes (SL) | `C₀ − k_sl × ATR` |
| Süre | `T = round(0,5 × L)` bar |

İki konfigürasyon **birlikte** hesaplanır ve saklanır:

| Konfig | `k_tp` | `k_sl` | Teorik null | Amaç |
|---|---|---|---|---|
| **2:1** | 2 | 1 | %33,3 | İşlem edilebilir senaryo |
| **1:1** | 1 | 1 | %50,0 | Saf yön testi (akademik) |

### 8.2. Değerlendirme algoritması

```python
def triple_barrier(highs, lows, closes, t0, atr, k_tp, k_sl, T):
    C0 = closes[t0]
    tp = C0 + k_tp * atr
    sl = C0 - k_sl * atr

    for t in range(t0 + 1, min(t0 + T + 1, len(closes))):
        hit_tp = highs[t] >= tp
        hit_sl = lows[t]  <= sl
        if hit_tp and hit_sl:
            return -k_sl, "sl", t      # muhafazakâr varsayım: SL önce
        if hit_sl:
            return -k_sl, "sl", t
        if hit_tp:
            return +k_tp, "tp", t

    t_end = min(t0 + T, len(closes) - 1)
    return (closes[t_end] - C0) / atr, "time", t_end
```

**Muhafazakâr varsayım:** Aynı barda hem TP hem SL seviyesine dokunulmuşsa **SL'e önce çarpıldığı** kabul edilir. Bar içi sıralama bilinmediği için bu, sonuçları kasıtlı olarak kötümser yönde eğer ve rapor edilir.

### 8.3. Ön filtre — işlem maliyeti tabanı

```python
if (atr / C0) < 0.01:      # 1×ATR < %1
    skip()                 # istatistiğe girmez
```

Binance taker komisyonu gidiş-dönüş ~%0,1 + slipaj. Bu taban olmadan binlerce sahte "başarı" toplanır. Bkz. [K-16.7](00-tasarim-kararlari.md#k-16--triple-barrier-atr-tabanlı-göreli-bariyerler).

### 8.4. Gölge dağılım (zaman-eşleştirmeli baseline)

```python
def shadow_distribution(matches, P=20):
    shadow = []
    for m in matches:
        month = to_month(m.end_time)
        pool = windows_in(month, exclude_symbol=m.symbol_id, liquid=True)
        for s in random.sample(pool, min(P, len(pool))):
            shadow.append(triple_barrier(s, ...))
    return shadow
```

Kontrol grubunun **zaman dağılımı, eşleşmelerin zaman dağılımını birebir taklit eder**. Bkz. [K-12](00-tasarim-kararlari.md#k-12--zaman-eşleştirmeli-baseline-gölge-dağılım).

> **Kural:** Edge iddiası ekrana yalnızca gölge dağılım aşılırsa yazılır.

### 8.5. Raporlanan metrikler

| Metrik | Formül / Not |
|---|---|
| **Beklenti (R)** | `mean(R)` — **başrol metriği** |
| Başarı oranı | `p_tp` — yanında gösterilir, başrole konmaz |
| Teorik null | `k_sl / (k_tp + k_sl)` |
| Gölge dağılım | Ölçülmüş kontrol grubu beklentisi ve başarı oranı |
| Edge | `E_formasyon − E_gölge` |
| N | **Dedupe edilmiş bağımsız olay sayısı** |
| Rejim kırılımı | Yıl/dönem bazında ayrı tablo |

> **Neden beklenti başrolde:** SL 5×ATR yapılırsa kazanma oranı %85'e çıkar ama beklenti negatiftir. Kazanma oranı tek başına manipüle edilebilir bir metriktir.

### 8.6. Bağımsız N

İstatistiğe giren olaylar, **post-NMS'ten geçmiş** tekil olaylardır. Örtüşen pencereler sayılmaz; aksi hâlde `n` yapay olarak şişer ve güven aralığı sahte biçimde daralır.

### 8.7. Zorunlu arayüz uyarısı

> Bu veriler geçmiş dağılımlardır, kesin bir işlem sinyali değildir.

---

## 9. Cache Katmanı

**Redis.**

| Anahtar | Değer | TTL |
|---|---|---|
| `search:{search_id}` | Sıralı, NMS'ten geçmiş tam sonuç listesi (JSON) | 1 saat |
| `search:{search_id}:stats` | Outcome kartı verisi | 1 saat |
| `radar:{template_id}:{tf}` | Önceden hesaplanmış Radar sonuçları | 5 dakika |

**Sayfalama akışı:**

```
POST /api/search        → tüm matris skorlanır, liste cache'lenir
                        → { search_id, total: 1847, results: [12 adet] }
GET  /api/search/{id}?offset=12&limit=12
                        → cache'ten dilim, yeniden hesaplama YOK
```

Bkz. [K-08](00-tasarim-kararlari.md#k-08--sayfalama-12li-grid-ve-cachelenmiş-sıralı-liste).

---

## 10. API Spesifikasyonu

### `POST /api/search`

**İstek:**

```json
{
  "points": [0.0, 0.12, 0.31, "... 32 eleman"],
  "template_id": null,
  "mode": "historical",
  "timeframe": "4h",
  "window_lengths": [24, 40, 64, 100],
  "tolerance": "medium",
  "min_amplitude": 10.0,
  "limit": 12
}
```

`points` veya `template_id`'den **biri** verilir.

**Yanıt:**

```json
{
  "search_id": "b3f2...",
  "total": 1847,
  "elapsed_ms": 287,
  "results": [
    {
      "symbol": "SOLUSDT",
      "timeframe": "4h",
      "window_length": 64,
      "start_time": 1710000000000,
      "end_time": 1710921600000,
      "score": 0.912,
      "amplitude": 18.4,
      "atr_pct": 3.7
    }
  ]
}
```

### `GET /api/search/{search_id}?offset=12&limit=12`

Cache'lenmiş listeden dilim döndürür. Yeniden hesaplama yapmaz.

### `GET /api/search/{search_id}/stats`

```json
{
  "n_independent": 112,
  "configs": {
    "2:1": {
      "expectancy_r": 0.18,
      "win_rate": 0.41,
      "theoretical_null": 0.333,
      "shadow_win_rate": 0.34,
      "shadow_expectancy_r": 0.02,
      "edge_points": 6.0,
      "outcomes": { "tp": 46, "sl": 51, "time": 15 }
    },
    "1:1": { "...": "..." }
  },
  "by_regime": [
    { "period": "2021", "n": 38, "win_rate": 0.55, "expectancy_r": 0.31 },
    { "period": "2022", "n": 24, "win_rate": 0.29, "expectancy_r": -0.08 }
  ],
  "disclaimer": "Bu veriler geçmiş dağılımlardır, kesin bir işlem sinyali değildir."
}
```

### `GET /api/templates`

Şablon kütüphanesini (kategori, isim, ikon, önizleme noktaları) döndürür.

### `GET /api/chart/{symbol}?tf=4h&start=...&end=...`

Sonuç grafiğini render etmek için OHLCV döndürür. Eşleşen pencerenin sınırları vurgulanabilsin diye `highlight_start` / `highlight_end` alanları da eklenir.

---

## 11. Frontend Mimarisi

### 11.1. Layout

```
┌───────────────────────────────────────────────────────────────────┐
│  ÜST PANEL                                                        │
│  [4H] [1D]                                    Zaman Dilimi        │
│  [Radar] [Backtest]                           Mod sekmesi         │
├──────────────┬────────────────────────────────────────────────────┤
│              │                                                    │
│  SOL PANEL   │            KANVAS                                  │
│              │                                                    │
│  Dönüş       │      (Canvas + pointer events)                     │
│   ▸ OBO      │      Şablon seçilince şeffaf blueprint             │
│   ▸ Ters OBO │                                                    │
│   ▸ İkili... │      ┌──────────────────────────────┐              │
│   ▸ Fincan   │      │  Katı ─○───────── Esnek      │              │
│              │      │  Min. Volatilite: %10        │              │
│  Devam       │      └──────────────────────────────┘              │
│   ▸ Flama    │                    [ TARA ]                        │
│   ▸ Takoz    │                                                    │
│   ▸ Üçgen    │                                                    │
├──────────────┴────────────────────────────────────────────────────┤
│  SONUÇLAR — 1.847 eşleşme bulundu, en iyi 12                      │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                              │
│  │ SOL  │ │ AVAX │ │ INJ  │ │ TIA  │   ← Lightweight Charts       │
│  │ %91  │ │ %89  │ │ %87  │ │ %86  │      Volatilite: %18         │
│  └──────┘ └──────┘ └──────┘ └──────┘                              │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                              │
│  └──────┘ └──────┘ └──────┘ └──────┘                              │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                              │
│  └──────┘ └──────┘ └──────┘ └──────┘                              │
│                    [ Daha Fazla (+12) ]                           │
└───────────────────────────────────────────────────────────────────┘
```

### 11.2. Çizim bileşeni

**Düz HTML5 Canvas + native pointer events.** Fabric.js / Konva.js kullanılmaz. Bkz. [K-17](00-tasarim-kararlari.md#k-17--frontend-hafifleştirmesi).

```
onPointerDown  → çizime başla, nokta biriktir
onPointerMove  → nokta ekle, path'i çiz
onPointerUp    → 32 noktaya indir, y eksenini ters çevir, state'e yaz
```

Toplam ~100 satır. Tek dışa bağımlılık yok.

### 11.3. Sonuç kartı

Her kart:

- TradingView Lightweight Charts ile mini grafik
- Eşleşen pencere **vurgulanmış** (gölgeli bölge)
- Sembol adı + benzerlik skoru
- `Volatilite: %18` etiketi
- (Backtest modunda) tıklanınca outcome detayı

### 11.4. Outcome kartı

```
┌────────────────────────────────────────────────────┐
│  SONRA NE OLDU?                                    │
│                                                    │
│  Hedef: 2R (bu parite için ≈ %7,4)                 │
│  Stop:  1R (≈ %3,7)                                │
│                                                    │
│  Beklenti:  +0,18R                                 │
│  Başarı:    %41    (null: %33 · gölge: %34)        │
│  N = 112 bağımsız olay                             │
│                                                    │
│  ── Rejim kırılımı ──                              │
│  2021: %55 (n=38)    2022: %29 (n=24)              │
│                                                    │
│  ⓘ Bu veriler geçmiş dağılımlardır, kesin bir      │
│    işlem sinyali değildir.                         │
└────────────────────────────────────────────────────┘
```

---

## 12. Repo Yapısı

```
GraphFlow/
├── README.md
├── .gitignore
├── docs/
│   ├── 00-tasarim-kararlari.md      # Karar kaydı (bu projenin anayasası)
│   └── 01-mimari.md                 # Bu belge
│
├── engine/                          # Python — çekirdek
│   ├── ingest/
│   │   ├── binance_client.py        # REST klines indirici
│   │   ├── symbol_universe.py       # delist dahil sembol listesi
│   │   └── cron_update.py           # 5 dakikalık güncelleme
│   ├── normalize/
│   │   ├── pipeline.py              # log → resample → z-score
│   │   └── amplitude.py
│   ├── matrix/
│   │   ├── build.py                 # kayan pencere → .npy
│   │   ├── incremental.py           # append
│   │   └── liquidity.py             # aylık kesitsel sıralama
│   ├── search/
│   │   ├── engine.py                # SearchEngine (live | historical)
│   │   ├── stage1_cosine.py
│   │   ├── nms.py                   # 1D-IoU, pre/post
│   │   └── stage2_ddtw.py
│   ├── outcome/
│   │   ├── triple_barrier.py
│   │   ├── shadow.py                # zaman-eşleştirmeli baseline
│   │   └── metrics.py
│   ├── templates/                   # kanonik formasyon JSON'ları
│   │   ├── reversal/
│   │   └── continuation/
│   └── api/
│       ├── main.py                  # FastAPI
│       ├── routes/
│       └── cache.py                 # Redis
│
├── notebooks/
│   ├── 01_veri_kontrol.ipynb
│   ├── 02_normalizasyon_gorsel.ipynb
│   ├── 03_goz_testi.ipynb           # ⚠️ ÇIKIŞ KAPISI
│   ├── 04_negatif_kontrol.ipynb     # ⚠️ ÇIKIŞ KAPISI
│   └── 05_esik_kalibrasyon.ipynb    # ROC
│
├── frontend/                        # Next.js 16 + TypeScript + Tailwind v4
│   ├── src/app/                     # App Router (/, /radar, /backtest)
│   ├── src/components/
│   │   ├── canvas/                  # DrawPad, TemplatePicker
│   │   ├── charts/                  # MatchGrid, BlueprintChart, QueryPreview, SkeletonChart
│   │   ├── outcome/                 # StatEnvelope, RegimeTable, PValueWarning
│   │   ├── layout/                  # Header
│   │   └── ui/                      # shadcn/ui temel bileşenleri
│   ├── src/hooks/                   # useDraw, useGraphFlowApi, useSessionId
│   ├── src/services/                # apiClient, endpoints
│   ├── src/types/                   # openapi-typescript çıktısı (api.ts)
│   └── src/utils/                   # dtwCoords, formatters
│
└── data/                            # .gitignore
    ├── klines/
    └── matrix/
```

---

## 13. Teknoloji Yığını

| Katman | Seçim | Not |
|---|---|---|
| Motor | **Python 3.11 + NumPy** | Bkz. [K-01](00-tasarim-kararlari.md#k-01--ölçek-gerçeği-problem-sanıldığı-kadar-büyük-değil) |
| DTW | `dtaidistance` / `tslearn` | C hızlandırmalı |
| İnterpolasyon | `numpy.interp` / `scipy.interpolate` | |
| API | **FastAPI** | Async, otomatik OpenAPI |
| Ham veri | **Parquet** (`pyarrow`) | Sütun bazlı, sıkıştırılmış |
| Uygulama DB | **PostgreSQL** | Kullanıcı, sembol, likidite sıralaması |
| Cache | **Redis** | Sayfalama + Radar önbelleği |
| Zamanlama | **Cron** (5 dk) | Kafka yok |
| Frontend | **Next.js 16 + TailwindCSS v4 + TypeScript** | App Router |
| State / Cache | **TanStack React Query v5** | Sayfalama, stale-time, mutation |
| UI Bileşenleri | **shadcn/ui** (Base UI tabanı) | Button, Slider, Tooltip |
| API Tipleri | **openapi-typescript** | Backend OpenAPI → `src/types/api.ts` |
| Grafik | **TradingView Lightweight Charts v5** | |
| Çizim | **Düz HTML5 Canvas** | Bkz. [K-17](00-tasarim-kararlari.md#k-17--frontend-hafifleştirmesi) |
| Notebook | Jupyter + Matplotlib + `ipywidgets` | Doğrulama kapısı |

**Bilinçli olarak yok:** Kafka, Rust/Go, TimescaleDB, WebSocket, Fabric.js, Konva.js.

---

## 14. Yol Haritası

| Faz | İçerik | Çıktı | Kapı |
|---|---|---|---|
| **F0** | Veri indirme altyapısı | `data/klines/**.parquet` (2017→bugün, delist dahil) | Veri bütünlük kontrolü |
| **F1** | Normalizasyon + matris inşası | 8 adet `.npy` matris + meta | Görsel normalizasyon kontrolü |
| **F2** | Arama motoru (kaskad) | `SearchEngine.search()` çalışır | Birim testler |
| **F3** | **Notebook doğrulaması** | Göz testi + negatif kontrol + eşik kalibrasyonu | 🚦 **ZORUNLU KAPI** |
| **F4** | Outcome Engine | Triple-barrier + gölge dağılım + metrikler | İstatistiksel tutarlılık testi |
| **F5** | FastAPI + Redis | Çalışan API | Yük testi |
| **F6** | Next.js 16 — Radar (MVP 1) | Canlı tarayıcı arayüzü | Kullanıcı testi |
| **F7** | Next.js 16 — Backtest (MVP 2) | Tarihsel arama + outcome kartı | Kullanıcı testi |
| **F4.5** | Ay-bloklu bootstrap + short yönü | Kesitsel korelasyon düzeltmesi | Null kapısı (long ve short) |
| **F4.6** | Ön-getiri eşleştirmeli gölge | Şekil mi, momentum vekili mi? | Vekil testi |
| **F4.7** | Zaman dilimi çaprazlaması | Aynı 56 test 1d ve 4h'de | Replikasyon |

### Doğrulama araçları (faz dışı, sürekli)

Ölçümler tek seferlik betiklerle üretilmemeli — yayınlanan sayı yeniden
üretilemiyorsa bayatladığını kimse fark etmez (F4.6 tam olarak böyle üç hafta
geçersiz kaldı). Her ölçümün bir aracı vardır:

| Araç | Soru |
|---|---|
| `tools/verify_stage1` | Matris Parquet'le aynı mı? Stride'ın bedeli ne? |
| `tools/ci_calibration` | %95 dediğimiz aralık gerçekten %95 kapsıyor mu? |
| `tools/run_outcomes` | F4/F4.5 tablolarını üretir (14 şablon × 2 yön × 2 konfig) |
| `tools/f46_proxy_test` | Edge şekilden mi, ön-getiriden mi? |
| `tools/template_health` | Hangi şablon gerçek veride ölü? |
| `tools/measure_amplitude` | Genlik eşiği korpustan ne çıkıyor? |
| `tools/backfill` | Bir zaman dilimini diğerinin evrenine tamamlar |
| `tests/test_integration.py` | Gerçek korpusta uçtan uca sözleşmeler |

### F3 kapısının anlamı

**F3 geçilmeden F5'e geçilmez.** Motor göz testinden geçmiyorsa arayüz yazmak, yanlış bir ürünü cilalamaktır. Bkz. [K-18](00-tasarim-kararlari.md#k-18--doğrulama-protokolü-notebook-kapısı).

### Ertelenen kapsam

- 1H, 1W zaman dilimleri (aynı pipeline, kolay ekleme)
- Nasdaq / BIST100 / Forex (veri lisansı sonrası)
- Short (düşüş) yönü için ayna triple-barrier
- Hacim teyidi ve boyun çizgisi kırılımı eklentileri
- Kullanıcı hesapları, kaydedilmiş aramalar, uyarılar (alert)

---

## 15. Performans Bütçesi

| İşlem | Hedef | Not |
|---|---|---|
| Aşama 1 (kosinüs, 12M pencere) | < 300 ms | NumPy/BLAS matris çarpımı |
| — *ölçülen*, 4h **sıcak** | **306–333 ms** | motor içi; yapısal filtre vektörize edildikten sonra |
| — *ölçülen*, 4h **soğuk** | **537–595 ms** | ilk çağrı: sorgunun null dağılımı hesaplanıyor |
| — *ölçülen*, 1d sıcak | ~211 ms (medyan) | |

**Soğuk/sıcak farkı bütçede yoktu ve dürüstçe kayda geçiriliyor.** F3.5'in
sorgu-göreli null kalibrasyonu, her yeni şekil için uzunluk başına 2.000
rastgele pencereyi Aşama 2'den geçirir; bu ilk çağrıya ~180 ms ekler ve
sonraki çağrılarda önbellekten gelir (`NULL_CACHE_SIZE`). Bütçe yazıldığında
bu katman yoktu. Radar'da mesele değil (sonuç zaten önbellekli, 1,2 ms);
Backtest'te ilk sorgu 500 ms sınırını ~%15 aşıyordu.

**Çözüldü — açılışta ısıtma.** Kütüphane şablonları sabit ve sayılı olduğu
için null dağılımları açılışta arka planda hesaplanıyor
(`GRAPHFLOW_WARMUP=1`). Ölçüm: hiç çağrılmamış 4h şablonlarında ilk istek
**364–459 ms** — soğuk 537–595 ms yerine, bütçe içinde. Serbest çizim
ısıtılamaz (sonsuz uzay) ve ilk sorgusunda aşımı yaşamaya devam eder;
bu kabul edilen sınırdır.

**Filtre katmanları vektörize edildi (Eylül 2026).** İki yapısal katman da
aday listesi üzerinde Python döngüsü kullanıyordu; ölçüldü ve 2.500 adayda
şu bedeli çıkarıyordu:

| katman | önce | sonra |
|---|---|---|
| zarf imzası (trend çizgisi) | 160 ms | **4,8 ms** |
| yapısal imza (uç düzeni) | 250 ms | **47 ms** |

Yapısal imzanınki tek başına bütçenin yarısıydı. n = 32 sabit olduğu için
belirginlik O(n²) tensör olarak yazılabiliyor; satırlar 1.024'lük parçalara
bölünür, yoksa `(m, 32, 32)` float64 dizileri 20 MB'ı aşar. Her iki toplu
yolun tekil yolla **birebir** eşdeğerliği testle tutulur — ayrışırlarsa
filtre sessizce başka bir şey elemeye başlar ve bunu hiçbir doğruluk ölçümü
göstermez.
| Pre-NMS | < 20 ms | 5.000 aday |
| Aşama 2 (DDTW, 1.000 aday) | < 100 ms | C hızlandırmalı |
| Post-NMS | < 5 ms | |
| **Toplam arama (historical)** | **< 500 ms** | |
| **Radar (live)** | **< 50 ms** | ~1.165 sembol × 4 uzunluk; F3.5'te 10→50 ms güncellendi (bütçe 500 sembol varsayımıyla yazılmıştı, doğrusal ölçekleniyor) |
| Sayfalama (cache'ten) | < 5 ms | Redis okuma |
| Outcome hesabı | < 2 sn | Gölge dağılım dahil; async |
| Matris tam inşası | Dakikalar–saatler | Tek seferlik, offline |
| Cron artımlı güncelleme | < 30 sn | 5 dakikada bir |

---

## 16. Doğrulama Protokolü

### 16.1. Göz testi (F3-a)

20 farklı el çizimi × ilk 12 sonuç. Çıkış şartı: **"evet, bu çalışıyor"**.

### 16.2. Negatif kontrol (F3-b)

| Girdi | Beklenen davranış |
|---|---|
| Düz yatay çizgi | "Eşleşme bulunamadı" veya en iyi skor ≤ ~%40 |
| White noise | Aynı |
| Anlamsız testere (whipsaw) | Aynı |

Sistem bunlara yüksek skorlu sonuçlar döndürüyorsa **metrik ölçmüyor, uyduruyor** demektir → motor düzeltilir.

Bu test özellikle [K-11](00-tasarim-kararlari.md#k-11--dtw-yerine-ddtw-türev-dtw)'deki DDTW kararının doğrulamasıdır: ham DTW'de düz çizgi çanağa eşleşir, DDTW'de eşleşmemelidir.

### 16.3. Eşik kalibrasyonu (F3-c)

Pozitif ve negatif skor dağılımları çizilir. `Katı / Orta / Esnek` eşikleri, bu iki dağılımın kesişim bölgesinden **ROC eğrisi mantığıyla** seçilir.

### 16.4. Outcome doğrulaması (F4)

| Test | Beklenti |
|---|---|
| Rastgele pencerelerde 2:1 başarı oranı | ≈ %33 (teorik null'a yakın) |
| Rastgele pencerelerde 1:1 başarı oranı | ≈ %50 |
| Rastgele pencerelerde beklenti | ≈ 0R |

Bu değerler teorik null'dan **anlamlı şekilde sapıyorsa**, triple-barrier uygulamasında bir hata vardır (lookahead bias, yanlış ATR penceresi, bar sıralaması vb.) ve **erken yakalanır**. Bu, mimarinin kendi kendini denetleme mekanizmasıdır.

### 16.5. Lookahead bias denetimi

Her outcome hesabında ATR'nin **yalnızca `t₀`'a kadarki barlardan** hesaplandığı birim testle doğrulanır. Bu, tüm istatistik katmanının geçerliliğini belirleyen tek noktadır.

---

*İlgili belge: [00-tasarim-kararlari.md](00-tasarim-kararlari.md) — her kararın gerekçesi ve reddedilen alternatifler.*
