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

### ⚙️ F3.5 eki — çapa tabanlı kısıt katmanı (uygulandı, BAĞLANMADI)

F3 göz testi, K-04'ün öngördüğü "geometriye indirgenemeyen ek filtre"
ihtiyacını **ölçülmüş hâle getirdi**: DTW noktaları hizalar, hizalanan
noktaların *seviyelerinin* mantıklı olup olmadığına bakmaz. OBO sorgusunda
yuvarlak tepeler bu yüzden sızıyor (ilk 12'de 2 karo).

Mekanizma K-04'ü bozmadan kuruldu: kural **koda değil şablon meta-verisine**
yazılır (`constraints` alanı), tek genel değerlendirici
`engine/search/constraints.py`, çapalar DTW hizalama yolundan okunur.
Kısıtsız şablon hiçbir ek filtreden geçmez.

**Ama motora bağlanmadı.** Ölçülen katkı: OBO 5/12 → 6/12, ikili tepe
1/12 → 2/12; bunun için aday havuzunun %60'ı atılıyor. Kural katmanı ancak
ölçülmüş katkı gösterirse kalır — göstermedi.
Ayrıntı: [04-f35-raporu.md](04-f35-raporu.md#adım-7--geometrik-kısıt-katmanı--bağlanmadı).

### ✅ Eylül 2026 eki — yapısal imza: kural şablondan değil, SORGUDAN türer

Kullanıcı şikâyeti sorunu geri getirdi: *"OBO ya da çift tepe çiziyorum,
benzer şeyler getiriyor ama formasyonu bulmuyor."* Bağımsız ölçüm
(`tools/formation_audit` — DTW'den ve çapa mekanizmasından ayrı, belirginlik
tabanlı tepe/dip denetimi) şikâyeti doğruladı:

| Sorgu kaynağı | İlk 12'de gerçekten o formasyon olan |
|---|---|
| kütüphane şablonu | **%42** (ikili tepede 12'de 3) |
| **elle çizim** | **daha kötü** — OBO'da 12'de **1** |

Elle çizimin daha kötü olması tesadüf değil: çapa tabanlı kısıt katmanı
şablon meta-verisinden okur, serbest çizimde **meta-veri yoktur**. Ürünün
yarısı hiçbir kısıttan geçmiyordu.

Üç yol ölçüldü (4h, ilk 12):

| Yaklaşım | Doğruluk |
|---|---|
| ham (filtresiz) | %42 |
| çapa tabanlı kısıt katmanı | %54 — **OBO'da kötüleşti** (6→4) |
| **sorgudan türetilen yapısal imza** | **%100** |

Çapa yolunun ikinci sınırı: çapalar DTW hizalama yolundan okunur, yol
bozulduğunda kural da bozulur.

**Yapısal imza** (`engine/search/constraints.py`) kuralı çizimin kendisinden
türetir: baskın uç tarafı (tepe/dip), belirgin uç sayısı, en uç olanın sırası,
hepsinin ve en uç dışındakilerin birbirine yakın olup olmadığı. Formasyon
başına kod yoktur — K-04 korunur, hatta **saflaşır**: artık şablon
meta-verisi bile gerekmiyor, dolayısıyla serbest çizimde de çalışır.

Elle çizimde sonuç: OBO 1/12 → **12/12**, ters OBO 5/12 → 12/12, çift tepe
6/12 → 12/12, çift dip 6/12 → 12/12.

Maliyet ölçüldü ve kabul edildi: kosinüs ~0,02 düşüyor, hayatta kalan 51–574
eşleşme (12 gösteriliyor), ~50 ms. Filtre sonrası taban altında aday kalırsa
uygulanmaz ve yanıt bunu **uyarı olarak taşır** — "yapıya uyan yok" ile "hiç
sonuç yok" farklı şeylerdir.

**Dürüst sınır:** imza tam formasyon kimliği değil, uç düzenidir. Yükselen
üçgen ile ikili tepe aynı imzayı taşır; ayrımı DTW mesafesi yapar. Bu katman
yalnızca *"yükseliş–tümsek–düşüş yakalayıp omuz–baş–omuz olup olmadığını
sormama"* hatasını engeller.

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

### ✅ Durum: KARARA BAĞLANDI (F3 ölçümü, 30 Temmuz 2026)

**Karar: `STAGE2_METRIC = "hybrid"`** — Aşama 2 skoru, normalize DDTW mesafesi
ile normalize ham DTW mesafesinin **ortalamasıdır**. DDTW tek başına
kullanılmaz; ham DTW de tek başına kullanılmaz. Kaybeden metrikler silinmedi,
`config.STAGE2_METRIC` anahtarında kaldı.

**Ölçüm** (`tools/ab_stage2.py`, tam koşul tablosu
[03-f3-dogrulama-raporu.md](03-f3-dogrulama-raporu.md#adim-1--k-11-ab-ddtw-mi-ham-dtw-mi-hybrid-mi)):

| Metrik | Genel AUC | Kazandığı hücre |
|---|---|---|
| **hybrid** | **0,9045** | **12/12** |
| dtw | 0,8956 | 0/12 |
| ddtw | 0,8733 | 0/12 |

3 metrik × 4 pencere uzunluğu × 3 gürültü seviyesi, formasyon başına 300 örnek,
9 formasyon. hybrid 9/9 formasyonda da kazandı; 108 eşli hücrenin %99'unda
dtw'den, %80'inde ddtw'den iyi.

**F2'deki iki metodolojik kusur bu ölçümde giderildi:**

1. **Dairesellik.** Pozitifler artık kanonik şablonun gürültülü kopyası değil,
   `tools/shape_variants.py` ile üretilen **farklı örnekler**: asimetrik omuz
   yükseklikleri, eğimli boyun çizgisi, farklı kulp derinliği/uzunluğu, tepe-dip
   zamanlama kayması. Yapısal doğrulayıcı (tepe/dip sayısı) etiketin doğruluğunu
   garanti ediyor — %100 geçiş.
2. **Uzunluk kırılımı.** AUC pencere uzunluğuna göre ayrı hesaplandı.

**DDTW neden kaybetti:** Türev almak yüksek geçiren filtredir; gürültü gücü
frekansla arttığı için diferansiyasyon gürültüyü yükseltir. Kayıp gürültü ve
pencere uzunluğuyla büyüyor (100 bar / %4 gürültüde ddtw 0,637'ye karşı dtw
0,746). Buna karşılık K-11'in dayandığı singularity senaryosu, Sakoe-Chiba
bandı (r=5, N=32) ve z-score varken **üretilemiyor**. Yani DDTW, olmayan bir
tehlikeye karşı gürültü dayanıklılığından feragat ediyordu.

**Ham DTW neden tek başına yetmedi:** hybrid, dtw'yi 12/12 hücrede geçti. İki
mesafenin ortalaması, tek başına hiçbirinin taşımadığı bilgiyi taşıyor —
DDTW bileşeni küçük ağırlığına rağmen (ham DTW mesafeleri ~2–4x büyük olduğu
için düz ortalama ham DTW ağırlıklıdır) katkı sağlıyor.

**F3.5'te iki bağımsız doğrulama daha:**

1. **Zaman ekseni sınaması** — bozulma şiddetine göre AUC: hafif 0,896/0,907/**0,920**,
   orta 0,872/0,895/**0,907**, şiddetli 0,810/0,872/**0,882** (ddtw/dtw/hybrid).
   En ağır bozulmada 9/9 formasyonda hybrid kazandı; DDTW'nin açığı büyüyor.
2. **Ters şekil tuzağı** — DDTW **tek başına düşen ve yükselen takozu ayırt
   edemiyor** (mesafe 0,0146; esnek eşiği 0,0456 → eşleşme sayar). Türev,
   iki şekli ayıran trend bileşenini sabite indirger. Ham DTW 2,28, hybrid 1,15
   ile eler. Bu bir **yön hatası**dır: motor yükseliş formasyonu ararken düşüş
   formasyonu döndürürdü.

**Açık kalan:** Ölçek-eşitlenmiş (z-skor) harman denenmedi; ileride ölçülebilir.

---

### ⚠️ Durum: YENİDEN AÇILDI (F2 ölçümü, 30 Temmuz 2026) — *yukarıda kapatıldı*

F2 uygulamasında sentetik veriyle yapılan ölçüm, bu kararın **gerekçesini doğrulamadı**. Karar şimdilik korunuyor ama F3 ROC kalibrasyonunda karara bağlanacak.

**Ölçülenler:**

| Test | DDTW | Ham DTW |
|---|---|---|
| Düz çizgi ↔ çanak ayrımı | 20,5× (örtüşme yok) | 37,6× (örtüşme yok) |
| AUC, bar gürültüsü %2 | 0,90 | **0,92** |
| AUC, bar gürültüsü %4 | 0,74 | **0,84** |

**Yorum:** K-11'in dayandığı singularity senaryosu bu konfigürasyonda **üretilemiyor**. Nedeni büyük olasılıkla, singularity'yi engelleyen iki mekanizmanın zaten pipeline'da bulunması:

- **Sakoe-Chiba bandı** (`r=5`, N=32) hizalama yolunu sınırlar; tek bir noktanın 15 noktaya yayılması band tarafından zaten yasaklanmış oluyor. K-11'deki *"band azaltır ama çözmez"* varsayımı bu ölçekte yanlış çıktı.
- **Z-score** ([K-02](#k-02--projenin-gerçek-kalbi-normalizasyon)), DDTW'nin adreslediği seviye-kayması problemini zaten çözüyor.

**Ters etki:** Türev alma bir **yüksek geçiren filtredir** ve gürültü gücü frekansla arttığı için diferansiyasyon gürültüyü yükseltir. Finansal seriler doğası gereği gürültülüdür; %4 gürültüde 10 puanlık AUC kaybı bununla tutarlı. Yani DDTW, singularity dayanıklılığını **gürültü hassasiyetiyle takas ediyor** — ve bu konfigürasyonda takas edilecek bir singularity problemi yok.

**Neden hemen değiştirilmedi:** Mevcut kanıt sentetiktir ve iki metodolojik zayıflığı vardır:

1. **Dairesellik.** Pozitif örnekler, sorgu olarak kullanılan kanonik şablonların gürültülü kopyalarıdır. Bu, "şablonu geri bulabiliyor mu"yu ölçer; "aynı formasyonun farklı bir örneğini tanıyor mu"yu değil. Gerçek formasyon varyasyonu (asimetrik omuzlar, eğimli boyun çizgisi, farklı kulp derinliği) temsil edilmiyor.
2. **Pencere uzunluğu etkileşimi ölçülmedi.** 100 bar → 32 nokta bir *alçak geçiren* işlemdir (yumuşatır), 24 bar → 32 nokta ise *yukarı örneklemedir* (yumuşatmaz, interpolasyon artefaktı üretir). DDTW'nin bu iki uçta farklı davranması beklenir; şu anki ölçüm uzunluk kırılımı içermiyor.

**F3'te karara bağlanacak:**

- Aşama 2 metriği `config.STAGE2_METRIC` ile seçilebilir hâle getirilir: `"ddtw" | "dtw" | "hybrid"` (varsayılan `"ddtw"`).
- Pozitif örnekler **şekil bozulmasıyla** üretilir (yalnız ölçek/uzunluk/gürültü değil).
- ROC, **pencere uzunluğuna göre kırılarak** hesaplanır.
- Gerçek Binance verisinde tekrarlanır.
- Kazanan metrik kalır; kaybeden bu belgeye gerekçesiyle yazılır.

> Aşama 2 yalnızca ~1.000 aday üzerinde çalışıyor ve 8 ms sürüyor. İki metriği birden hesaplayıp harmanlamak (`hybrid`) hesaplama açısından bedavadır — ama kanıt olmadan eklenmez.

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

### ⚙️ F4.5 eki — kesitsel korelasyon ve ay-bloklu bootstrap

Gölge dağılımın **çekilmesi** zaman-eşleştirmelidir, ama **güven aralığının
hesaplanması** başlangıçta değildi: iid bootstrap, aynı aydan çekilen 20
gölgeyi 20 bağımsız gözlem sayıyordu.

Ölçülen ampirik değer (250 parite, 37 ay): **ay içi ortalama ikili getiri
korelasyonu 0,384**. Kripto sembolleri birlikte hareket eder; aynı ayın 20
sembolü efektif olarak çok daha az bağımsız bilgi taşır.

**Yöntemin parçası (F4.5'ten itibaren):** Edge güven aralıkları **ay-bloklu
bootstrap** ile hesaplanır. Blok birimi takvim ayıdır; seçilen ayın *tüm*
eşleşmeleri ve *tüm* gölgeleri birlikte çekilir — ay içi korelasyon bloğun
içinde kalır, zaman eşleştirmesi bootstrap'ta da korunur.

Ölçülen tasarım etkisi (`SE_blok / SE_iid`): **medyan 1,28**, aralık
0,89–2,03. iid varsayımı belirsizliği ortalama %29 eksik ölçüyordu.

**Somut sonucu:** F4'ün tek pozitif bulgusu (alçalan üçgen, edge +0,29R)
bu düzeltmeyle anlamlılığını **kaybetti** — o testte tasarım etkisi 1,91'di.
Bkz. [06-f45-raporu.md](06-f45-raporu.md).

### 🔬 Kapsama sınaması (29 Ağustos 2026) — iddia doğrulandı, bir uyarıyla

F4.5'in hükmü tasarım etkisiyle **dolaylı** gösterilmişti. Bir güven
aralığının tek anlamı olan soru ise sorulmamıştı: *%95 dediğimiz aralık
gerçekten vakaların %95'inde doğru cevabı içeriyor mu?*

`tools/ci_calibration.py` bunu simülasyonla ölçer: gerçek edge'in **sıfır
olduğu bilinen** veri üretilir, aralığın sıfırı kaç kez içerdiği sayılır.

İlk sonuç beklenenin tersiydi — iid %97–100 kapsıyordu, yani *muhafazakâr*.
Sebebi yöntemin kendisinde: ay şoku hem eşleşmede hem gölgede ortak olduğu
için **farkta birbirini götürür**. K-12'nin zaman eşleştirmesi, tek başına
iid'yi güvenli kılıyor. Götürülmeyen tek şey, eşleşmelerin *yalnız kendi
aralarında* paylaştığı yapıdır — gerçek eşleşmeler rastgele pencere değil,
aynı formasyonu aynı piyasa hâlinde taşıyan pencerelerdir.

Bu faktör (`ρ_eşleşmeye_özel`) modele eklenince gerçek rejim çıktı
(ρ_ortak = 0,384, nominal %95, 300 tekrar):

| ρ_eşleşmeye_özel | Tasarım etkisi | Ay-bloklu kapsama | iid kapsama |
|---|---|---|---|
| 0,00 | 0,77 | %92,0 | %97,0 |
| 0,05 | 0,91 | %92,0 | %94,3 |
| **0,15** | **1,13** | %92,3 | **%89,0** |
| **0,30** | **1,41** | %92,0 | **%77,0** |

F4.5 gerçek veride tasarım etkisi medyanını **1,28** ölçmüştü → gerçek rejim
0,15 ile 0,30 arasında. Yani iid'nin fiili kapsaması %95 değil **~%80–89**.
"iid ile ölçülen anlamlılık sahtedir" hükmü doğrudan doğrulandı ve büyüklüğü
ilk kez ölçüldü.

⚠️ **Yeni uyarı:** ay-bloklu bootstrap da tam nominal değil — ρ = 0,384'te
kapsama **%92**. iid'den belirgin biçimde iyi ama kusursuz değil. Blokla
ölçülen anlamlılık da bir miktar iyimser okunmalıdır; F4.6'nın tek Bonferroni
bulgusunun ihtiyatla karşılanma sebeplerinden biri budur.

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

## K-19 — Alt-Stride Hizalama: Ölçüldü, Bağlanmadı

**Karar:** Eşleşmelerin bar bazında ince ayarı **uygulanmadı**. Kod
`engine/search/refine.py`'de duruyor, `config.REFINE_MATCHES = False`.

### Hipotez

Matris `STRIDE = 3` ile kurulur ([K-01](#k-01--ölçek-gerçeği-problem-sanıldığı-kadar-büyük-değil)).
Dolayısıyla gösterilen pencere, gerçek en iyi hizadan 1–2 bar kaymış olabilir.
`tools/verify_stage1.py` bu bedeli **ölçtü** — kaba kuvvet (stride 1) ile
matrisin bulduğu en iyi pencere arasında kosinüs farkı:

```
ortalama +0,021 · %95 +0,074 · en kötü +0,096
```

Gerçek aramalarda ilk sonuçlar r ≈ 0,93 bandında geldiği için bu fark
görünürdür: motor doğru formasyonu bulup **yanlış hizada** gösteriyor olabilir.

### Ölçüm — hipotez çöktü

Gösterilen ilk 60 eşleşme, ±(STRIDE−1) barlık pencerede üç ayrı hedefle
yeniden tarandı (1d, 5 şablon):

| Hedef | Δ mesafe | Δ kosinüs |
|---|---|---|
| mesafeyi enküçült | −0,00207 | **−0,0145** |
| kosinüsü enbüyült | **+0,00171** | +0,0063 |
| mesafeyi bozmadan kosinüs enbüyük | −0,00121 | **−0,0018** |

**Hiçbiri ikisini birden iyileştirmiyor.** İki metrik alt-stride hizalamada
birbiriyle takas ediyor: mesafeyi iyileştiren offsetler görsel benzerliği
bozuyor. Kısıtlı varyantta bile — mesafenin asla artmadığı kurulumda —
kosinüs düşüyor.

### Neden bağlanmadı

Eşikler mesafe üzerinde kalibre edildi (F3.5 yüzdelikleri). Kosinüs hedefiyle
açmak, kalibre edilmiş eşiği sessizce kaydırırdı. Ölçülen katkı ise her iki
yönde de yok.

Bu, [K-04](#k-04--kural-motorunun-i̇mhası-kanonik-şablon-vektörleri)'ün kısıt
katmanıyla aynı muameledir: **ölçülmüş katkı göstermeyen katman bağlanmaz.**

### Asıl değeri: negatif bulgu

Pencere sınırları, algılanan uyumsuzluğun sebebi **değil**. Bu, aramayı asıl
darboğaza yönlendirdi: korpus büyüklüğü. 4h evreni 80 sembol / 881K pencerede
kalmıştı, 1d ise 1.165 sembol / 1,87M — ve arayüzün varsayılanı 4h'ydi.
Kullanıcı, motorun kalibre edildiği korpusun %7'sinde arama yapıyordu.

Nöbetçi test korundu: ince ayar mesafeyi **asla artıramaz** (mevcut hiza da
aday kümesindedir), böylece katman açılırsa eşikler sessizce kaymaz.

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
| 7 | ~~Ham DTW~~ → **Yalnız DDTW** | **hybrid** (DDTW + ham DTW ortalaması) | ✅ **F3'te karara bağlandı**: AUC hybrid 0,9045 > dtw 0,8956 > ddtw 0,8733; hybrid 12/12 hücrede kazandı. Singularity, Sakoe-Chiba + z-score varken üretilemiyor; türev ise gürültüyü yükseltiyor (bkz. K-11) |
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
| 20 | Alt-stride hizalama ince ayarı | (bağlanmadı) | Mesafe ve kosinüs takas ediyor; ölçülen net katkı yok (K-19) |
| 21 | İmza kararlılık kapısı | (bağlanmadı) | Eğim tabanlı formasyonlarda filtre zararlı değil etkisiz — 400'de 5 fark (K-20) |

---

## Açık Sorular

Motor tasarımı kapandı, ancak uygulama sırasında karara bağlanacak noktalar:

1. **Genlik skor bonusu:** Kullanıcının çizim genliğine yakın sonuçlara skor bonusu verilecek mi, yoksa genlik yalnızca filtre/etiket olarak mı kalacak? → Notebook kalibrasyonunda test edilecek.
2. **Aday havuzu boyutu:** Aşama 1 çıktısı 1.000 sabit mi, yoksa skor eşiğine göre dinamik mi olacak? → Negatif kontrol testleri bunu belirleyecek.
3. **Gölge dağılım örnek sayısı (P):** Her eşleşme için kaç kontrol penceresi çekilecek? İstatistiksel güç ile hesaplama maliyeti arasında denge. Başlangıç önerisi: P = 20.
4. **Şablon kütüphanesi kaynağı:** Kanonik vektörler elle mi çizilecek, yoksa literatürdeki ideal formasyon tanımlarından mı türetilecek?
5. **Short yönü:** Triple-barrier şu an long varsayımıyla tanımlı. Düşüş formasyonları için ayna versiyonu ne zaman eklenecek?
6. **1H ve 1W:** Aynı pipeline'a eklenmesi kolay; hangi kullanıcı geri bildiriminden sonra açılacak?
7. ~~**`symmetrical_triangle` şablonu yeniden parametrelenmeli mi?**~~ **KAPANDI
   (8 Eyl 2026): çevrim 3,0 → 2,0.** 2,0, simetrik üçgenin ders kitabı
   tanımındaki asgari dokunuş sayısıdır (her kenara iki temas) ve ölçümde
   165 eşleşme veriyordu. Kalibrasyon riski düşük bulundu: F3.5'ten beri
   eşikler sorgu-göreli yüzdeliktir, mutlak sabitler yalnız akıl sağlığı
   tavanıdır; bir şablonun vektörü o sabitleri değiştirmez. Sonuç: 16 → 129
   eşleşme, null yayılımı 2,4 → 3,3. Aşağıdaki ölçüm kayıt için duruyor.

   *(özgün soru)* (8 Eyl 2026)
   Kanonik vektör 3 tam salınım istiyor; 32 noktada bu çevrim başına ~10
   nokta demek, yani temsil sınırı. Gerçek veride sonucu 1d'de **4**, 4h'de
   **16** eşleşme — diğer 13 şablon 166–799 veriyor. Ölçülen tarama
   (`tools/template_health`, 1d, orta tolerans):

   | çevrim | eşleşme | null yayılımı |
   |---|---|---|
   | 1,5 | 260 | 4,5 |
   | 2,0 | 165 | 3,1 |
   | 2,5 | 23 | 2,5 |
   | **3,0** | **4** | **2,4** ← eskisi |

   Şablon **kusurlu değil**: kendi gürültülü varyantlarına mesafesi (0,0037)
   diğer şablonlarla aynı bantta, yani motor onu tanıyor. Gerçek piyasada o
   kadar temiz üç çevrim nadir. `cycles = 2,0` kütüphane öğesini diriltir
   ama **F3 eşik kalibrasyonunun girdisini değiştirir** (eşikler 14 şablon
   sorgusundan okundu) — bu yüzden tek taraflı değiştirilmedi.

---

---

## Eylül 2026 — üç karar birden

Kullanıcı "ne öneriyorsan onu yap" dedi; üç açık soru şöyle bağlandı.

### 1. Yapısal imza filtresi AÇIK kalır

Ürün kalitesi ile istatistiksel güç arasında bir takas var ve ölçüldü:

| | Filtre kapalı | Filtre açık |
|---|---|---|
| İlk 12'de gerçekten o formasyon | %42 (elle çizimde 1/12) | **%100 (12/12)** |
| Ortalama N (1d) | 291 | 114 |
| %95'te anlamlı (1d) | 14/56 | 6/56 |

Filtre **açık kalıyor**, çünkü kapalı hâlde daha fazla "güç" aldığımız
örneklemin %58'i aranan formasyon bile değildi. Kirli bir örneklem üzerinde
daha yüksek çözünürlük, yanlış soruyu daha hassas ölçmektir.
Ayrıntı: [09-yapisal-filtre-ve-istatistik.md](09-yapisal-filtre-ve-istatistik.md).

Güç kaybının bir kısmı aday havuzu büyütülerek geri alındı
(`STAGE1_TOPK` 5.000 → 12.500, `STAGE2_TOPK` 1.000 → 2.500): şablon başına
sonuç 4h'de 224 → 358, en kötü arama süresi 400 ms ile bütçe içinde.

### 2. `symmetrical_triangle` yeniden parametrelendi (Açık Soru #7)

3 çevrim → 2 çevrim. Yukarıda.

### 3. 1d genlik eşiği %15'te KALIR

Ölçülen "likit pencerelerin %95'ini koru" eşiği bugünkü korpusta **%18,5**;
config'deki %15 ise pencerelerin **%96,9'unu** koruyor (F3.5'te %95,2'ydi).

Değiştirilmedi, üç gerekçeyle:

* Sapma yönü **güvenli**: %15 daha az filtreliyor, yani veriyi daha az
  buduyor. Ölçütün amacı patolojik kuyruğu kesmekti; kesiyor.
* Fark küçük (%96,9 ↔ %95) ve kalibre bir sabiti oynatmanın bedeli büyük:
  F4/F4.5/F4.6/F4.7/F4.8 tablolarının tamamı yeniden üretilir.
* Kalibre sabitler ancak **ölçülmüş bir kusur** gösterdiğinde değişir; burada
  gösterilen tek şey ölçütün tanımındaki bir yumuşaklık.

Ölçüm `tools/measure_amplitude` ile her zaman tekrarlanabilir; karar
değişirse dayanağı orada.

---

## K-20 — İmza Kararlılık Kapısı: Ölçüldü, Bağlanmadı

**Karar:** Yapısal imza filtresi **her sorguda** uygulanır. İmzanın kararlı
olup olmadığına bakan bir kapı yazıldı, ölçüldü ve **bağlanmadı**.

### Hipotez

Yapısal imza uç *düzenini* okur. Bazı formasyonları tanımlayan şey uç düzeni
değil **eğimdir**: yükselen üçgeni "iki tepe" değil, yatay direnç + yükselen
dipler tanımlar. Böyle şekillerde imza kararsızdır — sorguya küçük bir
gürültü uç sayısını değiştirir. Kararsız bir özelliği adaylarda *aynen*
aramak, yapıya göre değil gürültüye göre elemek olmalıydı.

Kararlılık ölçülebilir: sorguya σ = 0,10 gürültü ekle, imzanın hayatta kalma
oranına bak (128 çekim, sabit tohum). İki küme temiz ayrışıyor ve arada
%80–%91 boş bandı var:

| sağlam | kararsız |
|---|---|
| yuvarlak dip 100 · OBO 97 · ikili tepe 97 · ters OBO 96 | düşen takoz 80 · alçalan üçgen 70 |
| boğa bayrağı 94 · ayı bayrağı 92 · ikili dip 91 · fincan 91 | simetrik üçgen 61 · yükselen takoz 59 · yükselen üçgen 33 · flama 23 |

### Ölçüm

`tools/formation_audit --compare --top 50` (4h, 1.097 sembol, 11,6M pencere):

| aile | filtre AÇIK | filtre KAPALI |
|---|---|---|
| dönüş (OBO, ters OBO, ikili tepe/dip) | **197/200 · %99** | 56/200 · %28 |
| eğim (üçgen, takoz, flama, bayrak) | 195/400 · %49 | 200/400 · %50 |

### Neden bağlanmadı

Eğim ailesinde filtre **zararlı değil, etkisiz** — 400 denemede 5 fark.
Kapatmanın ölçülebilir bir kazancı yok, dolayısıyla bağlanmadı (K-19 ile
aynı ilke: ölçülmüş, net katkısı yok, motora girmiyor).

**Metodolojik not.** İlk ölçüm ilk 12 sonuçla yapıldığında alçalan üçgende
3'e 7, yükselen takozda 7'ye 10'luk bir "zarar" görünüyordu ve kapı haklı
çıkmış gibi duruyordu. Hücre başına 12 Bernoulli denemesinde standart hata
~1,7 sonuçtur; yani o farklar gürültüydü ve n = 50'de kayboldular. Güç
artırılmadan bağlansaydı gürültüye göre mimari değiştirmiş olurduk. **Bir
"zarar" bulgusu, bir "kazanç" bulgusu kadar güç ister.**

### Bağlı olan kullanım: raporlama

Kararlılık, ölçülen doğrulukla birebir örtüşüyor (sağlam aile %99, kararsız
aile %49). Kararsız bir okumayı kesinmiş gibi göstermek fazla iddiadır;
`SearchResponse.structure_stable` bunu taşır ve arayüz okumanın yanına
kararsız olduğunu ve ölçülen doğruluğu yazar. Maliyet 11 ms.

### Açık kalan

Eğim tabanlı formasyonlarda motor ~%50'de, flamada 5/50. Sebep ölçülmüş
durumda: DTW şekli noktasal hizalar, *trend çizgisi* diye bir kavramı
yoktur. Zarf eğimlerini aday elemesinde kullanmak bir sonraki adımın
konusudur; `tools/formation_audit` o adımın ölçüm zeminidir.

Ayrıntı: [10-formasyon-denetimi.md](10-formasyon-denetimi.md).

---

*Bu belge canlıdır. Yeni bir mimari karar alındığında buraya yeni bir `K-xx` bölümü olarak eklenmeli ve reddedilen alternatifler tablosu güncellenmelidir.*
