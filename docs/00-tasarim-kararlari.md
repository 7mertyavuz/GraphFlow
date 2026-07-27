# GraphFlow — Tasarım Kararları ve Gerekçeleri

> **Belge türü:** Karar Kaydı (Architecture Decision Record / Design Log)
> **Tarih:** 27 Temmuz 2026
> **Durum:** Motor tasarımı kapandı, uygulama fazına geçilebilir
> **İlgili belge:** [01-mimari.md](01-mimari.md)

Bu belge, GraphFlow'un ilk vizyonundan nihai motor tasarımına kadar alınan **her kararı, gerekçesini ve reddedilen alternatifleri** kaydeder. Amaç, altı ay sonra "bunu neden böyle yapmıştık?" sorusuna cevap verebilmek ve aynı tartışmaları tekrar etmemektir.

---

## İçindekiler

1. [Ürün Tanımı](#1-ürün-tanımı)
2. [Başlangıç Vizyonu (v0)](#2-başlangıç-vizyonu-v0)
3. [K-01 — Ölçek Gerçeği: Problem Sanıldığı Kadar Büyük Değil](#k-01--ölçek-gerçeği-problem-sanıldığı-kadar-büyük-değil)
4. [K-02 — Projenin Gerçek Kalbi: Normalizasyon](#k-02--projenin-gerçek-kalbi-normalizasyon)
5. [K-03 — Kaskad Arama Stratejisi](#k-03--kaskad-arama-stratejisi)
6. [K-04 — Kural Motorunun İmhası: Kanonik Şablon Vektörleri](#k-04--kural-motorunun-i̇mhası-kanonik-şablon-vektörleri)
7. [K-05 — İki Ürün Modu: Radar ve Backtest](#k-05--iki-ürün-modu-radar-ve-backtest)
8. [K-06 — Öldürücü Özellik: "Sonra Ne Oldu?"](#k-06--öldürücü-özellik-sonra-ne-oldu)
9. [K-07 — Veri Kapsamı: Sadece Kripto](#k-07--veri-kapsamı-sadece-kripto)
10. [K-08 — Sayfalama: 12'li Grid ve Cache'lenmiş Sıralı Liste](#k-08--sayfalama-12li-grid-ve-cachelenmiş-sıralı-liste)
11. [K-09 — Çift Aşamalı NMS (Deduplication)](#k-09--çift-aşamalı-nms-deduplication)
12. [K-10 — Genlik (Amplitude) Meta-Verisi](#k-10--genlik-amplitude-meta-verisi)
13. [K-11 — DTW Yerine DDTW (Türev DTW)](#k-11--dtw-yerine-ddtw-türev-dtw)
14. [K-12 — Zaman-Eşleştirmeli Baseline (Gölge Dağılım)](#k-12--zaman-eşleştirmeli-baseline-gölge-dağılım)
15. [K-13 — Survivorship Bias ve Göreli Likidite Filtresi](#k-13--survivorship-bias-ve-göreli-likidite-filtresi)
16. [K-14 — Çoklu Çözünürlük ve Skor Kıyaslanabilirliği](#k-14--çoklu-çözünürlük-ve-skor-kıyaslanabilirliği)
17. [K-15 — Tek Motor, İki Mod](#k-15--tek-motor-i̇ki-mod)
18. [K-16 — Triple-Barrier: ATR Tabanlı Göreli Bariyerler](#k-16--triple-barrier-atr-tabanlı-göreli-bariyerler)
19. [K-17 — Frontend Hafifleştirmesi](#k-17--frontend-hafifleştirmesi)
20. [K-18 — Doğrulama Protokolü: Notebook Kapısı](#k-18--doğrulama-protokolü-notebook-kapısı)
21. [Reddedilen Fikirler Özeti](#reddedilen-fikirler-özeti)
22. [Açık Sorular](#açık-sorular)

---

## 1. Ürün Tanımı

**GraphFlow**, kullanıcının bir grafik formasyonu (chart pattern) çizdiği veya kütüphaneden seçtiği bir şekli alıp, bu şekle benzeyen gerçek piyasa grafiklerini bulan bir görsel arama motorudur.

İki kullanım senaryosu vardır:

| Mod | Soru | Kullanıcı |
|---|---|---|
| **Radar (Canlı)** | "Şu an hangi coin'ler bu şekli yapıyor?" | İşlem açmak isteyen trader |
| **Backtest (Tarihsel)** | "Geçmişte bu şekil oluştuğunda ne olmuş?" | Araştırmacı / strateji geliştirici |

**Ürünün tek gerçek riski**, teknik ölçeklenebilirlik değil, **algısal doğruluktur**: Bir trader sonuçlara baktığında "evet, bu benim çizdiğim şey" diyebilmeli. Bütün mimari kararlar bu hedefe hizmet eder.

**Ürünün satılabilirlik iddiası** ise "sinyal" değil, **ölçülmüş ve dürüstçe raporlanmış geçmiş dağılım**dır.

---

## 2. Başlangıç Vizyonu (v0)

İlk plan aşağıdaki gibiydi. Büyük kısmı korundu, bazı bileşenleri elendi.

### 2.1. Arayüz kurgusu (büyük ölçüde korundu)

- **Sol Panel — Kütüphane:** Kategorize edilmiş formasyonlar (Dönüş / Devam formasyonları), minimalist vektörel ikonlarla. Omuz Baş Omuz (OBO), Ters OBO, Fincan-Kulp, Flama, İkili Tepe/Dip, Takoz (Kama). Tıklanınca kanvasa şeffaf "blueprint" taslak düşer.
- **Üst Panel — Konfigürasyon:** Zaman dilimi sekmeleri (1m, 5m, 15m, 1H, 4H, 1D, 1W) ve pazar çoklu-seçim (Kripto, Nasdaq, BIST100, Forex).
- **Orta Panel — Kanvas:** Serbest çizim modu; kullanıcı hazır formasyon dışında spesifik bir fiyat hareketi de çizebilir. Altında "Benzerlik Oranı" slider'ı.
- **Alt/Sağ Panel — Sonuç akışı:** Eşleşen grafikler grid halinde.

### 2.2. Backend kurgusu (büyük ölçüde elendi)

- WebSocket ile canlı OHLCV toplama
- TimescaleDB / QuestDB / InfluxDB zaman serisi veritabanı
- Eşleştirme motoru Go / Rust / C++ ile
- Apache Kafka mesaj kuyruğu
- Redis cache, Postgres kullanıcı verisi
- Hibrit algoritma: hazır formasyonlar için kural tabanlı (if-else), serbest çizim için DTW

### 2.3. Neden değişti

Aşağıdaki kararlar bu v0 planını, **aynı ürünü çok daha az parçayla ve çok daha yüksek doğrulukla** üretecek şekilde yeniden şekillendirdi.

---

## K-01 — Ölçek Gerçeği: Problem Sanıldığı Kadar Büyük Değil

**Karar:** Kafka, Rust/Go worker'ları ve özel zaman serisi veritabanı MVP'den çıkarıldı. Motor Python + NumPy ile yazılacak.

### Gerekçe

v0 planı "milyonlarca veri noktasında anlık arama" korkusuyla ağır bir dağıtık mimari seçmişti. Rakamlar konulduğunda bu korkunun yersiz olduğu görüldü:

```
Sembol sayısı          : ~500 likit parite (Binance)
Geçmiş (4H, 8 yıl)     : ~17.500 bar/sembol
Pencere uzunlukları    : 4 farklı ({24, 40, 64, 100})
Stride (kaydırma adımı): 3
─────────────────────────────────────────────────────
Toplam pencere         : ~12.000.000
Vektör boyutu          : 32 nokta × float32 = 128 byte
─────────────────────────────────────────────────────
Toplam bellek          : ~1.5 GB
```

1.5 GB **tek makinenin RAM'ine sığar**. `numpy.memmap` ile diskten sayfalanarak RAM'e tam yüklenmeden dahi okunabilir.

Arama işlemi bu matris üzerinde **tek bir matris-vektör çarpımı**dır:

```
12.000.000 × 32 = 384M çarpma-toplama ≈ 0.1–0.3 saniye (NumPy/BLAS)
```

### Kritik içgörü

> Asıl hız kazancı programlama dilinden değil, **vektörleri önceden hesaplayıp tek bir bitişik (contiguous) matris olarak tutmaktan** gelir.

Rust'a geçmek 3–5x kazandırır. Doğru veri yapısına geçmek 1000x kazandırır. Rust, motor doğrulandıktan ve gerçek bir darboğaz ölçüldükten *sonra* değerlendirilecek bir optimizasyondur — mimari bir gereklilik değil.

### Reddedilenler

| Bileşen | Neden reddedildi |
|---|---|
| **Apache Kafka** | Dağıtılacak canlı akış yok. 4H/1D taramada 5 dakikada bir REST çekmek yeterli. |
| **Go / Rust / C++ motor** | Darboğaz dil değil, veri yapısı. Ölçülmemiş bir problem için erken optimizasyon. |
| **TimescaleDB / QuestDB / InfluxDB** | Sıcak yol (hot path) zaten önceden hesaplanmış matriste. Ham mumlar için Parquet + Postgres yeterli. |
| **WebSocket canlı akış** | MVP'de gereksiz. 4H mumda 5 dakikalık gecikmenin hiçbir maliyeti yok. |

---

## K-02 — Projenin Gerçek Kalbi: Normalizasyon

**Karar:** Normalizasyon pipeline'ı projenin en kritik bileşeni olarak ele alınır. Sıra: **log fiyat → resample (N=32) → z-score**.

### Gerekçe

v0 planında normalizasyondan hiç bahsedilmemişti. Oysa başarı-başarısızlık çizgisi tam olarak buradadır. Ham fiyatlarla karşılaştırma yapılırsa:

- 60.000 $ değerindeki BTC ile 0,002 $ değerindeki bir altcoin **asla** eşleşmez
- Yükselen bir trend ile aynı şeklin daha küçük ölçekli hâli farklı görünür

### Adımlar

**1. Logaritmik fiyat**

```
x_t = ln(p_t)
```

Gerekçe: Piyasada anlamlı olan mutlak fiyat değişimi değil, **yüzdesel** değişimdir. Logaritmik uzayda eşit dikey mesafe = eşit yüzdesel hareket. Bu olmadan yüksek fiyatlı varlıkların hareketleri şişik, düşük fiyatlıların hareketleri bastırılmış görünür.

**2. Yeniden örnekleme (Resample) — N = 32 nokta**

`scipy.interpolate` ile lineer interpolasyon kullanılarak her pencere (uzunluğu 24 de olsa 100 de olsa) sabit 32 noktaya indirgenir.

Gerekçe: Farklı uzunluktaki pencereleri **tek bir vektör uzayında** kıyaslayabilmek için. 32 sayısı, formasyon şekillerinin karakteristik özelliklerini (tepe, dip, boyun çizgisi) korumaya yeterken gürültüyü doğal olarak filtreleyecek kadar düşük.

**3. Z-Score standardizasyonu**

```
z_i = (x_i − μ) / σ        (μ, σ pencerenin kendi içinden)
```

Gerekçe: Şeklin "kimliğini" fiyat seviyesinden ve hareket büyüklüğünden ayrıştırır. Bundan sonra geriye sadece **saf geometrik form** kalır.

**Kenar durum:** σ = 0 (tamamen düz pencere) → pencere veri setinden düşürülür.

### Yan etki ve telafisi

Z-score, hareketin **şiddetini** tamamen siler. Bu bilinçli bir kayıptır ama telafi edilmesi gerekir → bkz. [K-10](#k-10--genlik-amplitude-meta-verisi).

---

## K-03 — Kaskad Arama Stratejisi

**Karar:** Tek aşamalı DTW yerine iki aşamalı kaskad (cascade) kullanılır.

### Gerekçe

DTW'nin hesaplama maliyeti O(N·M)'dir. 12 milyon pencerenin tamamında çalıştırmak dakikalar sürer — interaktif bir ürün için kabul edilemez. Ama DTW'nin sağladığı zaman-bükme esnekliği de değerlidir.

Çözüm, bilgisayarlı görü ve bilgi erişiminde standart olan **kaba eleme → ince sıralama** kaskadıdır.

### Aşama 1 — Kaba Eleme (Kosinüs Benzerliği)

Önceden hesaplanmış normalize matris üzerinde vektörize kosinüs benzerliği:

```python
scores = M @ q / N        # M: (12M, 32), q: (32,)
```

- Süre: ~0,1–0,3 saniye
- Çıktı: en yüksek skorlu ~1.000 aday

**Matematiksel not:** Vektörler z-score'landığı için `‖z‖ = √N` sabittir. Dolayısıyla bu işlem **Pearson korelasyonuna matematiksel olarak eşittir**. Bu istenen davranıştır — şekil korelasyonu ölçüyoruz.

### Aşama 2 — İnce Sıralama (DDTW)

Sadece bu ~1.000 aday üzerinde, Sakoe-Chiba bandı ile kısıtlanmış türev-DTW çalıştırılır.

- Süre: milisaniyeler
- Çıktı: nihai sıralama

### Kazanç

Aynı kalitede sonuç, **~1000 kat daha ucuz**.

---

## K-04 — Kural Motorunun İmhası: Kanonik Şablon Vektörleri

**Karar:** Hazır formasyonlar için `if-else` tabanlı kural motoru tamamen kaldırıldı. Her formasyon, sisteme **32 noktalık kanonik (ideal) bir vektör eğrisi** olarak gömülür ve aynı DTW pipeline'ından geçer.

### Gerekçe

v0 planı hibrit bir yaklaşım öneriyordu: OBO için `Tepe1 < Tepe2 > Tepe3` ve `Tepe1 ≈ Tepe3` gibi Fibonacci/oran kuralları kodlamak.

Bunun sorunları:

1. **Bakım maliyeti:** 20 formasyon = 20 ayrı, birbirinden bağımsız, kırılgan kural seti. Her biri ayrı ayrı ayarlanmalı, test edilmeli, hata ayıklanmalı.
2. **Tutarsızlık:** Kural motoru ile DTW motoru aynı sorguya farklı sonuçlar verir. Kullanıcı "OBO" seçtiğinde ile OBO çizdiğinde farklı listeler görür — bu bir üründe kabul edilemez.
3. **Kapsam:** Kurallar sadece kodlanan formasyonları bulur. Şablon vektörleri ise sınırsız genişletilebilir; yeni bir formasyon eklemek = yeni bir 32 elemanlı dizi yazmak.

### Sonuç

- **Tek motor**, iki giriş yolu (kütüphane seçimi / serbest çizim)
- Yeni formasyon eklemek dakikalar sürer, gün değil
- Kural mantığı **sadece gerçekten gerektiği yerde** kullanılır: hacim teyidi, boyun çizgisi kırılımı gibi geometriye indirgenemeyen ek filtreler

---

## K-05 — İki Ürün Modu: Radar ve Backtest

**Karar:** Ürün arayüzde iki net sekmeye ayrılır. Ancak arka planda **tek motor** kullanılır (bkz. [K-15](#k-15--tek-motor-i̇ki-mod)).

### Gerekçe

v0 planı bu ayrımı yapmıyordu ve iki farklı ürünü tek bir akışta karıştırıyordu. Oysa bu ikisinin hem hesaplama profili hem kullanıcı niyeti tamamen farklıdır:

| | **Radar (Canlı)** | **Backtest (Tarihsel)** |
|---|---|---|
| Soru | "Şu an kim bu şekli yapıyor?" | "Geçmişte bu şekil ne getirmiş?" |
| Arama uzayı | Her sembolün **sadece son penceresi** | Tüm kayan pencere matrisi |
| Karşılaştırma sayısı | ~500 × 4 uzunluk = ~2.000 | ~12.000.000 |
| Maliyet | Neredeyse bedava | Saniyenin onda biri |
| Kullanıcı niyeti | İşlem açmak | Araştırma / doğrulama |
| Öncelik | **MVP 1** | MVP 2 |

### Radar'a özel kural: yarım mum maskelenir

Oluşmakta olan (henüz kapanmamış) son mum **her zaman veriden düşürülür**.

Gerekçe: Yarım mum şekli bozar ve her yenilemede sonuç değiştirir. Bu, arayüzde sinyallerin sürekli yanıp sönmesine (**flicker**) yol açar ve kullanıcının sisteme güvenini yok eder.

---

## K-06 — Öldürücü Özellik: "Sonra Ne Oldu?"

**Karar:** Tarihsel arama sonuçlarının yanına, o formasyondan sonra ne olduğunu gösteren istatistik kartı eklenir. Bu, ürünün ana farklılaştırıcısıdır.

### Gerekçe

Bu özellik olmadan GraphFlow "şık bir grafik görüntüleyici"dir — ilgi çekici ama satılabilir değil. Bu özellikle birlikte **ölçülmüş bir edge iddiası** taşıyan bir araştırma aracına dönüşür.

### Kart tasarımı

```
Hedef: 2R (bu parite için ≈ %7,4)   ·   Stop: 1R (≈ %3,7)
Beklenti: +0,18R
Başarı:   %41   (teorik null: %33   ·   gölge dağılım: %34)
N = 112 bağımsız olay
```

### Dürüstlük şartları

Bu iddianın geçerli olabilmesi için **üç şey** zorunludur — üçü de ayrı birer karar olarak aşağıda ele alınmıştır:

1. **Baseline kıyaslaması** → [K-12](#k-12--zaman-eşleştirmeli-baseline-gölge-dağılım)
2. **Dedupe edilmiş bağımsız N** → [K-09](#k-09--çift-aşamalı-nms-deduplication)
3. **Risk-normalize edilmiş bariyerler** → [K-16](#k-16--triple-barrier-atr-tabanlı-göreli-bariyerler)

### Arayüz uyarısı (zorunlu)

> Bu veriler geçmiş dağılımlardır, kesin bir işlem sinyali değildir.

Ayrıca sonuçlar **rejim bazında** (yıl/dönem) kırılarak sunulur; böylece kullanıcı bir formasyonun gerçekten mi çalıştığını yoksa sadece bir boğa piyasasını mı örneklediğini görebilir.

---

## K-07 — Veri Kapsamı: Sadece Kripto

**Karar:** MVP yalnızca kripto (Binance) verisiyle çalışır. Nasdaq, BIST100 ve Forex ertelendi.

### Gerekçe

**Hukuki/mali sürtünme:**

- Nasdaq gerçek zamanlı veri lisansı pahalıdır
- **BIST veri lisansı** ayrı bir bürokratik süreç ve maliyet kalemidir — projeyi haftalarca kilitleyebilir
- Binance REST klines verisi **ücretsiz ve lisanssızdır**

**Ürün avantajı:**

- 7/24 kesintisiz veri (seans boşluğu, tatil, gap yok — zaman serisi analizi için ideal)
- En kalabalık ve en çok formasyon-odaklı kullanıcı kitlesi
- Yüksek volatilite = daha zengin formasyon çeşitliliği

### Kapsam

| Parametre | Değer |
|---|---|
| Borsa | Binance |
| Parite sayısı | ~500 likit (delist olanlar dahil) |
| Zaman dilimleri | 4H ve 1D |
| Geçmiş | 2017'den bugüne |
| Güncelleme | 5 dakikada bir Cron job |
| Depolama | Parquet (soğuk) + Postgres (uygulama verisi) |

**Zaman dilimi notu:** v0'daki 1m/5m/15m gibi düşük zaman dilimleri kapsam dışı bırakıldı. Gerekçe: veri hacmini onlarca kat artırırken formasyon analizi için sinyal/gürültü oranı çok düşüktür. 1H ve 1W ileride kolayca eklenebilir (aynı pipeline).

---

## K-08 — Sayfalama: 12'li Grid ve Cache'lenmiş Sıralı Liste

**Karar:** Sonuçlar **3×4 = 12'li grid** halinde gösterilir, "Daha Fazla" ile +12 yüklenir. Tüm sıralı liste bir kez hesaplanıp cache'lenir.

### Reddedilen v0 fikri: "4'er 4'er tarama"

v0 planı, "tüm grafikleri taramasın diye" sonuçların 4'er 4'er verilmesini öneriyordu.

**Bu mantık hatalıydı:** En iyi 4 sonucu bulabilmek için **zaten hepsini skorlamak zorundasınız**. Tembel (lazy) tarama yapılırsa gösterilen 4 sonuç "en benzer 4" değil, "rastgele bulunan ilk 4" olur. Kullanıcı ilk ekranda çöp görür ve ürüne bir daha dönmez.

### Neden 12?

- **4 sonuç kalite yargısı için yetersizdir** — kullanıcı motorun iyi mi kötü mü olduğunu anlayamaz
- 12 küçük grafik tek ekranda taranabilir ve "evet, bu şey çalışıyor" hissi verir
- 50+ sonuç render maliyeti ve bilişsel yük yaratır

### Doğru akış

```
1. Sorgu gelir           → tüm matris skorlanır (0,1–0,3 sn)
2. NMS uygulanır         → sıralı, tekilleştirilmiş liste
3. Liste Redis'e yazılır → search_id ile, TTL 1 saat
4. UI ilk 12'yi çeker    → "1.847 eşleşme bulundu — en iyi 12"
5. "Daha Fazla"          → cache'ten offset ile sonraki 12
```

Üstteki toplam sayı ("1.847 eşleşme") arka plandaki motorun gücünü hissettirirken, 12 grafik görsel kanıt sunar.

---

## K-09 — Çift Aşamalı NMS (Deduplication)

**Karar:** Non-Maximum Suppression **iki ayrı noktada** uygulanır: Aşama 1 sonrası gevşek, Aşama 2 sonrası katı.

### Problem 1 — İlk 12 sonucun tamamı aynı grafik olur

Stride 1–3 ile kayan pencerelerde, komşu pencereler z-score sonrası birbirinin **%99 aynısıdır**. BTC 14 Mart'ta bir çanak formasyonu yaptıysa, o çanağın 40 farklı kaydırılmış versiyonu skor tablosunun tepesini doldurur.

Kullanıcı 12 kutuda **pratikte aynı grafiği** görür ve ürünü çöp sanar. Bu, planın en büyük gizli hatasıydı.

### Problem 2 — Aşama 2'nin bütçesi çöpe gider

Daha ince ama daha maliyetli bir sorun: Aşama 1'den çıkan 1.000 aday dedupe edilmemişse, aslında **~50 farklı olayın 20'şer kopyasıdır**. DTW 950 kez aynı şeye çalıştırılır ve gerçek çeşitlilik hiç görünmez.

### Çözüm — İki geçişli NMS

**Pre-NMS (Aşama 1 sonrası)**

- Amaç: DTW'ye giden aday havuzunu **çeşitlendirmek**
- Yöntem: hızlı 1D-IoU (Intersection over Union)
- Eşik: **gevşek** — %70 overlap
- Çıktı: gerçekten farklı ~1.000 aday

**Post-NMS (Aşama 2 sonrası)**

- Amaç: Kullanıcıya gösterilecek nihai listeyi temizlemek
- Yöntem: nihai DDTW skorları üzerinde
- Eşikler: **katı** — %50 overlap + `max_results_per_symbol = 3`
- Çıktı: UI'a giden liste

### 1D-IoU formülü

İki pencere `[s₁, e₁]` ve `[s₂, e₂]` için (aynı sembol, aynı zaman dilimi):

```
kesişim = max(0, min(e₁,e₂) − max(s₁,s₂))
birleşim = (e₁−s₁) + (e₂−s₂) − kesişim
IoU = kesişim / birleşim
```

IoU eşiği aşarsa, düşük skorlu olan silinir.

### `max_per_symbol = 3` neden gerekli

Bu limit olmadan ilk sayfa, sadece Bitcoin'in farklı fraktallarına dönüşür. Kullanıcı 500 parite arasından arama yaptığını sanırken tek bir coin görür.

### Kritik sıralama notu

Dedupe **sadece tek bir yerde** yapılırsa iki hatadan biri kaçınılmazdır:
- Yalnız başta yapılırsa → yanlış skorla (kaba skorla) eleme yapılmış olur
- Yalnız sonda yapılırsa → Aşama 2 bütçesi boşa harcanır

Bu yüzden iki geçiş de zorunludur.

---

## K-10 — Genlik (Amplitude) Meta-Verisi

**Karar:** Vektör matrisine şekil verisinin yanına bir **genlik özniteliği** eklenir: `[32_boyutlu_şekil, genlik_yüzdesi]`.

### Gerekçe

Z-score'un doğrudan sonucu: **%2'lik yatay bir testere hareketi ile %40'lık bir mega ralli tamamen aynı vektörü üretir.**

Bu, bir trader'ın en çok tepki göstereceği şeydir. Motor teknik olarak doğru çalışıyor olsa bile, kullanıcı sonuçlara baktığında "bu saçmalık" der ve güvenini kaybeder.

### Hesaplama

```
genlik = (max(p) − min(p)) / min(p) × 100
```

Pencerenin ham fiyatları üzerinden, normalizasyondan **önce** hesaplanır ve saklanır.

### İki kullanım

1. **Filtre:** Arayüzde "yalnızca %10'dan büyük hareketleri göster" gibi kullanıcı kontrolü
2. **Şeffaflık:** Her sonuç grafiğinin altında etiket → `Volatilite: %18`

Opsiyonel olarak, kullanıcının çizim genliğine yakın olanlara skor bonusu verilebilir (kalibrasyon aşamasında değerlendirilecek).

---

## K-11 — DTW Yerine DDTW (Türev DTW)

**Karar:** Aşama 2'de ham z-score serileri yerine **yerel türevler** üzerinde DTW çalıştırılır (Derivative DTW).

### Problem — DTW singularity

Klasik DTW'nin bilinen hastalığı **singularity**'dir: tek bir nokta, karşı serideki 15 noktaya hizalanabilir. Pratik sonucu:

> **Düz yatay bir çizgi, bir çanak formasyonunun tüm noktalarıyla eşleşir** ve yüksek benzerlik skoru alır.

Bu, bir şekil arama motoru için ölümcül bir hatadır. Sakoe-Chiba bandı bunu **azaltır ama çözmez**.

### Çözüm

Noktaların mutlak (z-score) değerleri yerine **yerel eğimleri** hizalanır. Böylece algoritma şeklin **yönünü ve momentumunu** karşılaştırır, seviyesini değil.

Keogh & Pazzani'nin türev tahmini kullanılır:

```
D[i] = ( (x[i] − x[i−1]) + (x[i+1] − x[i−1]) / 2 ) / 2       1 ≤ i ≤ N−2
```

Bu tahmin, tek noktalı basit farktan daha gürültü-dayanıklıdır çünkü hem sol komşuyu hem de iki noktalı ortalama eğimi hesaba katar.

### Maliyet

Bir kerelik `diff` hesabı — pratikte **sıfır**. Zaten sadece ~1.000 aday üzerinde çalışıyor.

### Ek kısıt

Sakoe-Chiba bandı korunur: `r = 0.15 × N ≈ 5` (N = 32 için). Hem maliyeti düşürür hem de aşırı bükülmeyi engeller.

---

## K-12 — Zaman-Eşleştirmeli Baseline (Gölge Dağılım)

**Karar:** Başarı oranı asla tek başına gösterilmez. Her zaman, **eşleşmelerle aynı takvim dönemlerinden örneklenmiş** bir kontrol grubuyla kıyaslanır.

### Problem

Kripto piyasasında long yönlü her test doğal bir bias taşır. "10 barda +%3" taban oranı zaten yüksektir (yükselen dönem ağırlığı nedeniyle).

Daha kötüsü: Bir formasyon tarihte 100 kez bulunduysa ve bunların 60'ı Mart 2021'de kümelendiyse, tüm-geçmiş baseline'ıyla kıyaslamak **sahte bir edge** üretir. Ölçtüğünüz şey formasyonun başarısı değil, **piyasanın o dönemdeki başarısıdır**.

### Çözüm — Gölge Dağılım (Shadow Distribution)

Her eşleşen pencere için:

1. Pencerenin **bitiş tarihini** al
2. **Aynı dönemden** (aynı ay), **farklı sembollerden**, aynı likidite filtresini geçen **P adet rastgele pencere** çek
3. Bu havuza aynı triple-barrier ölçümünü uygula

Sonuç, eşleşmelerin zaman dağılımını **birebir taklit eden** bir kontrol grubudur. Formasyonun 60 örneği Mart 2021'deyse, gölge dağılımın da 60 örneği Mart 2021'dendir.

### Kural

> "+6 puanlık edge" iddiası ekrana **ancak gölge dağılım aşılırsa** yazılır.

### İkinci referans: teorik null

ATR tabanlı asimetrik bariyerler, analitik olarak bilinen bir null hipotezi de sağlar (bkz. [K-16](#k-16--triple-barrier-atr-tabanlı-göreli-bariyerler)). İki referans birbirini doğruluyorsa metodoloji sağlamdır; ayrışıyorsa bir yerde hata vardır ve bu **erken görülür**. Bu, kendi kendini denetleyen bir tasarımdır.

---

## K-13 — Survivorship Bias ve Göreli Likidite Filtresi

### 13.1. Survivorship Bias

**Karar:** Delist edilmiş pariteler veri setinde **tutulur**.

**Gerekçe:** Sadece bugün hayatta olan projeleri test etmek tüm istatistikleri yukarı büker. LUNA ve FTT, çöküşlerinden önce yüzlerce ders kitabı formasyonu oluşturdu. Bu grafikleri veri setinden çıkarmak, "formasyon çalışıyor" sonucunu **yapay olarak** üretir.

Binance sürekli parite delist eder; bu bias kripto piyasasında hisse senedi piyasasından bile daha güçlüdür.

### 13.2. Göreli Likidite Filtresi

**Karar:** Sabit dolar eşiği yerine, **her ayın kendi içinde göreli (cross-sectional)** eşik kullanılır.

**Problem:** 2018 Binance hacimlerini bugünün dolar eşiğiyle (örn. 10 M$) filtrelemek, tarihi yok etmek demektir. 2018'de günlük 10 M$ üstü hacme sahip parite sayısı bir elin parmaklarını geçmiyordu. Survivorship bias'ı düzeltmek için tarihi geriye çekip sonra sabit eşikle o tarihi kesmek, **iki düzeltmenin birbirini götürmesidir**.

**Çözüm:**

| Mod | Filtre |
|---|---|
| **Backtest (tarihsel)** | Her ayın başında hacim/turnover sıralaması hesaplanır. O ayın kesitinde **üst %40**'ta olmayan pariteler o ayki taramada maskelenir. |
| **Radar (canlı)** | Son 24 saat hacmi > **5 M$** (sabit, güncel eşik) |

Böylece hem 2018 hem 2025 verisi adilce temsil edilir, hem de "işlem açılamayacak parite" mantığı korunur.

**Neden likidite filtresi zorunlu:** Filtre olmadan ilk 12 sonucun yarısı, slipaj yüzünden hiç kimsenin işlem açamayacağı ölü paritelerden gelir ve arayüzü kirletir.

---

## K-14 — Çoklu Çözünürlük ve Skor Kıyaslanabilirliği

### 14.1. Pencere uzunluğu seti

**Karar:** `{24, 40, 64, 100}` bar uzunluklarında **4 ayrı matris** oluşturulur. 4H ve 1D için ayrı ayrı → toplam **8 matris**.

**Gerekçe:** Kullanıcının çizdiği şeklin kaç barlık bir hareketi temsil ettiğini bilemeyiz. Kullanıcıya sormak kötü bir UX'tir (çoğu kullanıcı cevabı bilmez). Çözüm, birden fazla çözünürlükte aramak ve en iyi eşleşmeyi bulmaktır.

**Bellek:** ~1,5 GB toplam. `numpy.memmap` ile disk üzerinden sayfalanarak okunur; RAM'e tam yüklenmesi bile gerekmez.

### 14.2. Skor hizalaması

**Karar:** Aşama 2 çıktısında DTW mesafesi **hizalama yolu uzunluğuna bölünerek** normalize edilir.

```
Normal_Skor = DTW_Mesafesi / Hizalama_Yolu_Uzunluğu
```

**Gerekçe:** Farklı uzunluktaki pencerelerden gelen ham DTW mesafeleri **asla doğrudan kıyaslanamaz** — 100 barlık bir yolun mesafesi doğal olarak daha büyüktür. Bu normalizasyon yapılmazsa, tek bir sıralı listede 24 barlık pencereler sistematik olarak 100 barlıkları ezer ve kullanıcı hiçbir zaman uzun formasyon göremez.

**Aşama 1'de sorun yok:** Kosinüs benzerliği zaten 32 boyuta indirgenmiş vektörler üzerinde çalıştığı için doğal olarak kıyaslanabilirdir.

---

## K-15 — Tek Motor, İki Mod

**Karar:** Radar ve Backtest için **iki ayrı sistem yazılmaz**. Tek bir sorgu sınıfı, mod parametresi alır.

```python
engine.search(query, mode='historical' | 'live', ...)
```

| Mod | Davranış |
|---|---|
| `historical` | Tüm kayan pencere matrisi taranır |
| `live` | Matrisin sadece `son_index − pencere_boyutu` kesiti taranır |

### Gerekçe

Radar, tarihsel motorun `offset = son bar` özel hâlinden başka bir şey değildir. İki ayrı kod yolu yazmak:

- Kod tabanını gereksiz şişirir
- **Tutarsız sonuçlara yol açar** — kullanıcı Radar'da gördüğü bir eşleşmeyi Backtest'te bulamazsa güvenini kaybeder
- Her düzeltmenin iki yerde yapılmasını gerektirir

### Uygulama sırası notu

Radar MVP 1 olsa da, **önce matris motoru yazılır**, Radar onun üstüne ~30 satırla bindirilir.

### Ortak kural

Tamamlanmamış son (anlık) mum **her iki modda da** veriden düşürülür/maskelenir.

---

## K-16 — Triple-Barrier: ATR Tabanlı Göreli Bariyerler

**Karar:** Sonuç ölçümü için **Triple-Barrier metodu** (Marcos López de Prado) kullanılır ve bariyerler **statik yüzde değil, ATR tabanlı** tanımlanır.

### 16.1. Neden Triple-Barrier?

Çıplak "maksimum getiri" metriği gerçek bir işlem senaryosunu temsil etmez. Triple-barrier, Kâr Al (TP), Zarar Kes (SL) ve Süre Limiti bariyerlerinden **hangisine önce çarpıldığını** ölçer — bu, gerçekte olacak şeydir.

### 16.2. Neden statik yüzde DEĞİL?

Sabit %5 TP / %3 SL koyulduğunda, bariyere çarpma olasılığı büyük ölçüde **paritenin oynaklığına** bağlıdır:

- Yüksek volatiliteli altcoin'ler, rastgele yürüyüşle bile %5'i teğet geçer → yapay olarak "başarılı" görünür
- BTC 10 barda %5 yapmadığı için sistematik olarak "başarısız" çıkar

> Statik bariyerle ölçülen şey **"bu formasyon işe yarıyor mu"** değil, **"bu formasyon volatil coinlerde mi çıkıyor"**dur.

Bu, [K-12](#k-12--zaman-eşleştirmeli-baseline-gölge-dağılım)'de temizlenmeye çalışılan kirliliğin **farklı bir kapıdan geri girmesidir**.

Aynı problem zaman ekseninde de vardır: 2021'in ATR'si 2024'ün ~3 katıdır. Statik %5, iki dönemde tamamen farklı zorlukta bir hedeftir.

### 16.3. ATR'nin asıl kazandırdığı: analitik null hipotezi

Bu, satılabilirlik açısından belirleyici argümandır.

Driftsiz rastgele yürüyüşte, üst bariyer `a` ve alt bariyer `b` için üste önce çarpma olasılığı:

```
P(üst) = b / (a + b)
```

2×ATR TP / 1×ATR SL konfigürasyonu için:

```
P_null = 1 / (1 + 2) ≈ %33
```

Yani **hiçbir edge'i olmayan bir formasyonun teorik başarı oranı %33'tür.** Ölçülen değer %41 ise, elde **savunulabilir bir iddia** vardır.

Statik yüzdede bu sayı her parite ve her dönem için farklıdır; hiçbir şeyle kıyaslanamaz.

### 16.4. Konfigürasyon

| Parametre | Değer | Gerekçe |
|---|---|---|
| ATR periyodu | ATR(14), **pencerenin son barına kadar** | Lookahead bias'ı kapatır — bariyer, formasyon tamamlandığı anda bilinebilir olmalı |
| TP | `C₀ + 2 × ATR` | 2R hedef |
| SL | `C₀ − 1 × ATR` | 1R risk |
| Zaman bariyeri | `0,5 × pencere_uzunluğu` bar | **Sabit 10 bar değil!** |

**Zaman bariyeri neden orantılı olmalı:** 100 barlık bir çanak formasyonu 10 barda yargılanırsa neredeyse tümü zaman bariyerinden çıkar. Zaman bariyeri de formasyonun kendi ölçeğiyle orantılı olmalıdır — tıpkı DTW mesafesinin normalize edilmesi gibi ([K-14](#k-14--çoklu-çözünürlük-ve-skor-kıyaslanabilirliği)). Aksi hâlde 4 matrisin sonuçları kıyaslanamaz.

**Aynı barda hem TP hem SL:** Muhafazakâr varsayım — **SL'e önce çarpıldığı** kabul edilir. Bu varsayım dokümante edilmeli ve sonuçlarda belirtilmelidir.

### 16.5. Kazanma oranı tek başına manipüle edilebilir

SL 5×ATR yapılırsa başarı oranı %85'e çıkar ve ürün harika görünür — ama beklenti negatiftir.

Bu yüzden asıl metrik **R cinsinden beklenti**tir:

```
E = p_TP × 2R − p_SL × 1R + p_time × R̄_time
```

`+0,18R` tek başına dürüst bir sayıdır ve doğrudan pozisyon boyutlandırmaya çevrilebilir. Kazanma oranı yanında gösterilir ama **başrole konmaz**.

### 16.6. Simetrik versiyon da hesaplanır

`1×ATR TP / 1×ATR SL` konfigürasyonu, null'u tam **%50** olan en saf yön testidir.

| Konfigürasyon | Null | Amaç |
|---|---|---|
| 2:1 (2×ATR / 1×ATR) | %33 | İşlem edilebilir senaryo |
| **1:1 (1×ATR / 1×ATR)** | **%50** | "Bu formasyonun gerçekten yön bilgisi var mı?" — akademik savunması olan sayı |

Hesaplama maliyeti sıfıra yakındır; **ikisi de saklanır**.

### 16.7. İşlem maliyeti tabanı

**Kural:** `1 × ATR < %1` ise o pencere istatistiğe **girmez**.

**Gerekçe:** Ölü bir paritede ATR %0,3 ise, bariyerler spread ve komisyonun içinde kaybolur. Binance taker komisyonu gidiş-dönüş ~%0,1, üstüne slipaj eklenir. Bu taban olmadan binlerce **sahte "başarı"** toplanır ve ölçülen edge'in tamamı komisyona gider.

### 16.8. Arayüz sunumu

Kullanıcı ATR bilmez. İçeride ATR ile hesaplanır, **ekranda ikisi birden** gösterilir:

```
Hedef: 2R (bu parite için ≈ %7,4)  ·  Stop: 1R (≈ %3,7)
Beklenti: +0,18R   ·   Başarı: %41  (null: %33, gölge dağılım: %34)
N = 112 bağımsız olay
```

Hem trader'ın anladığı dilde, hem de istatistikçinin itiraz edemeyeceği kadar açık.

---

## K-17 — Frontend Hafifleştirmesi

### 17.1. Çizim: Fabric.js / Konva.js reddedildi

**Karar:** React component'i içine gömülmüş **düz HTML5 Canvas** ve native pointer event'leri (`onPointerDown`, `onPointerMove`, `onPointerUp`).

**Gerekçe:** Fabric.js ve Konva.js birer **çizim editörü** kütüphanesidir — katman yönetimi, nesne seçimi, dönüştürme, serileştirme sunarlar. GraphFlow bir editör değildir; kullanıcı sadece **tek bir polyline** çizer.

Gerekli olan: pointer noktalarını topla, 32 noktaya indir, API'ye gönder. **~100 satır.** Ağır kütüphanelerin getirdiği bundle boyutu ve API karmaşıklığı tamamen gereksizdir.

### 17.2. Esneklik ayarı: yüzde slider reddedildi

**Karar:** "%85 Benzerlik" gibi kalibre edilemez bir metrik yerine, **3–4 kademeli `Katı ↔ Esnek` toggle**'ı.

**Gerekçe:** DTW mesafesi bir yüzde değildir. Kullanıcıya "%85" göstermek, anlamı olmayan bir sayıyı anlamlıymış gibi sunmaktır — bu, ürünün geri kalanındaki istatistiksel dürüstlük duruşuyla çelişir.

Toggle, arka planda DTW mesafe eşiğini ayarlar. Eşik değerleri teorik olarak değil, **notebook kalibrasyonundan** ([K-18](#k-18--doğrulama-protokolü-notebook-kapısı)) çıkarılır.

### 17.3. Korunanlar

- **Next.js (React) + TailwindCSS** — arayüz iskeleti
- **TradingView Lightweight Charts** — sonuç grafiklerinin render'ı (doğru seçim, hafif ve amaca uygun)
- Sol panel kütüphane, üst panel konfigürasyon, orta panel kanvas, alt panel sonuç akışı — v0'daki layout kurgusu korunuyor

---

## K-18 — Doğrulama Protokolü: Notebook Kapısı

**Karar:** Next.js'e **bir satır kod yazılmadan önce**, motor bir Jupyter Notebook'ta görsel olarak doğrulanır. Bu bir öneri değil, **geçilmesi zorunlu bir kapıdır (gate)**.

> Yazılım dünyasının en büyük yalanı "arayüzü yapalım, arkası toparlanır" lafıdır.

### Protokol

**1. Ortam**

Python, NumPy, Matplotlib, `ipywidgets` (kanvas çizimi için).

**2. Pozitif test**

20 farklı el çizimi: Fincan-Kulp, OBO, Ters OBO, Takoz, Flama, İkili Tepe, İkili Dip vb. Her biri için ilk 12 sonuç çizdirilir.

**3. Göz testi (çıkış şartı)**

Gelen 12 sonuca bakıp **"evet, bu lanet olası şey çalışıyor"** denmeden bu defterden çıkılmaz.

**4. Negatif kontrol testi** ⚠️

Göz testinin çoğu projede atlanan yarısı budur. Sisteme **eşleşmemesi gereken** girdiler verilir:

- Düz yatay çizgi
- Tamamen rastgele white noise
- Anlamsız testere (whipsaw) hareketi

**Beklenen davranış:** Sistem "eşleşme bulunamadı" demeli veya en iyi skor %40'lar bandında kalmalı.

Sistem bunlara da %0,94 skorlu 12 sonuç döndürüyorsa, **metrik ölçmüyor, uyduruyor** demektir. Sağlıklı bir motorun *"bunun iyi bir eşleşmesi yok"* diyebilmesi gerekir.

**5. Eşik kalibrasyonu**

`Katı / Orta / Esnek` eşikleri **teorik olarak değil**, pozitif ve negatif dağılım eğrilerinin kesiştiği noktalardan — ROC eğrisi mantığıyla — seçilir.

Bu, eşiklerin asıl kaynağının **negatif testler** olduğu anlamına gelir; pozitiflerden eşik çıkarılmaz.

---

## Reddedilen Fikirler Özeti

| # | Reddedilen | Yerine | Gerekçe (özet) |
|---|---|---|---|
| 1 | Apache Kafka | 5 dakikalık Cron + REST | Dağıtılacak canlı akış yok |
| 2 | Go / Rust / C++ motor | Python + NumPy | Darboğaz dil değil, veri yapısı |
| 3 | TimescaleDB / QuestDB / InfluxDB | Parquet + Postgres | Sıcak yol önceden hesaplanmış matriste |
| 4 | WebSocket canlı akış | REST + Cron | 4H/1D'de 5 dk gecikmenin maliyeti yok |
| 5 | `if-else` kural motoru (OBO, Kama…) | Kanonik şablon vektörleri | Kırılgan, bakımı pahalı, motorla tutarsız |
| 6 | Tek aşamalı DTW | Kaskad (kosinüs → DDTW) | O(N·M) 12M pencerede kabul edilemez |
| 7 | Ham DTW | DDTW (türev) | Singularity: düz çizgi çanağa eşleşiyor |
| 8 | 4'er 4'er tembel tarama | 12'li grid + cache'li sıralı liste | En iyi 4'ü bulmak için zaten hepsi skorlanmalı |
| 9 | Tek geçişli NMS | Çift aşamalı NMS | Ya bütçe yanar ya yanlış skorla elenir |
| 10 | Nasdaq / BIST / Forex (MVP'de) | Sadece Binance kripto | Veri lisansı maliyeti ve bürokrasisi |
| 11 | 1m / 5m / 15m zaman dilimleri | 4H + 1D | Sinyal/gürültü oranı çok düşük |
| 12 | Sabit dolar likidite eşiği | Aylık kesitsel üst %40 | 2017–2019 verisini tamamen siliyordu |
| 13 | Tüm-geçmiş baseline | Zaman-eşleştirmeli gölge dağılım | Rejim etkisini formasyon edge'i sanmak |
| 14 | Statik yüzde bariyerler | ATR tabanlı göreli bariyerler | Formasyonu değil volatiliteyi ölçüyor |
| 15 | Sabit 10 barlık zaman bariyeri | `0,5 × pencere_uzunluğu` | 100 barlık formasyonu 10 barda yargılamak |
| 16 | Sadece kazanma oranı | R cinsinden beklenti (+ kazanma oranı) | Kazanma oranı SL genişleterek manipüle edilebilir |
| 17 | Fabric.js / Konva.js | Düz Canvas + pointer events | Editör kütüphanesi; biz editör yapmıyoruz |
| 18 | "%85 Benzerlik" slider'ı | `Katı ↔ Esnek` toggle | DTW mesafesi yüzde değil; kalibre edilemez |
| 19 | Sadece yaşayan pariteler | Delist edilenler dahil | Survivorship bias istatistikleri yukarı büker |

---

## Açık Sorular

Motor tasarımı kapandı, ancak uygulama sırasında karara bağlanacak noktalar:

1. **Genlik skor bonusu:** Kullanıcının çizim genliğine yakın sonuçlara skor bonusu verilecek mi, yoksa genlik yalnızca filtre/etiket olarak mı kalacak? → Notebook kalibrasyonunda test edilecek.
2. **Aday havuzu boyutu:** Aşama 1 çıktısı 1.000 sabit mi, yoksa skor eşiğine göre dinamik mi olacak? → Negatif kontrol testleri bunu belirleyecek.
3. **Gölge dağılım örnek sayısı (P):** Her eşleşme için kaç kontrol penceresi çekilecek? İstatistiksel güç ile hesaplama maliyeti arasında denge. Başlangıç önerisi: P = 20.
4. **Şablon kütüphanesi kaynağı:** Kanonik vektörler elle mi çizilecek, yoksa literatürdeki ideal formasyon tanımlarından mı türetilecek?
5. **Short yönü:** Triple-barrier şu an long varsayımıyla tanımlı. Düşüş formasyonları için ayna versiyonu ne zaman eklenecek?
6. **1H ve 1W:** Aynı pipeline'a eklenmesi kolay; hangi kullanıcı geri bildiriminden sonra açılacak?

---

*Bu belge canlıdır. Yeni bir mimari karar alındığında buraya yeni bir `K-xx` bölümü olarak eklenmeli ve reddedilen alternatifler tablosu güncellenmelidir.*
