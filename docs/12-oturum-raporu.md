# Geliştirme raporu — 24 Ağustos – 10 Eylül 2026

> **Kapsam:** Bu belge, 24 Ağustos 2026'da başlayan geliştirme oturumunda
> yapılan her şeyi anlatır: 64 commit, her birinin gerekçesi, dayandığı
> ölçüm, alınan ve **geri alınan** kararlar, bulunan hatalar ve açık
> kalanlar. Sonundaki commit dizini git'ten otomatik üretilmiştir.
>
> **Okuma sırası:** Bölüm 1 bir sayfalık özettir. Bölüm 2 zaman çizelgesidir
> (kullanıcının her isteği ve karşılığında yapılan). Bölüm 3–11 konulara göre
> ayrıntıdır. Bölüm 12 benim hatalarım, Bölüm 13 açık kalanlar.

---

## İçindekiler

1. [Özet](#1-özet)
2. [Zaman çizelgesi](#2-zaman-çizelgesi)
3. [Çizim paneli: "çizdiğimi anlamıyor"](#3-çizim-paneli-çizdiğimi-anlamıyor)
4. [Genel hata taraması](#4-genel-hata-taraması)
5. [Açık kaynak araştırması ve ödünç alınanlar](#5-açık-kaynak-araştırması-ve-ödünç-alınanlar)
6. [Korpus: 4h evreni 80 → 1.097 sembol](#6-korpus-4h-evreni-80--1097-sembol)
7. [İstatistik katmanı düzeltmeleri](#7-istatistik-katmanı-düzeltmeleri)
8. [Formasyon tanıma: asıl şikâyet](#8-formasyon-tanıma-asıl-şikâyet)
9. [Ölçüm altyapısı](#9-ölçüm-altyapısı)
10. [Motorun çekirdeğinde bulunan hatalar](#10-motorun-çekirdeğinde-bulunan-hatalar)
11. [Performans ve arayüz](#11-performans-ve-arayüz)
12. [Kendi hatalarım](#12-kendi-hatalarım)
13. [Açık kalanlar](#13-açık-kalanlar)
14. [Yeniden üretme](#14-yeniden-üretme)
15. [Ek: commit dizini](#15-ek-commit-dizini)

---

## 1. Özet

| | 24 Ağustos | 10 Eylül |
|---|---|---|
| 4h korpusu | 80 sembol · 881K pencere | **1.097 sembol · 11,6M pencere** |
| Elle çizilmiş OBO, ilk 12'de doğru | 1/12 | **12/12** |
| Dönüş formasyonları, gerçek korpus, ilk 50 | %28 (filtresiz) | **%98–99** |
| Ground truth, 12 formasyon (sentetik) | 169/287 · %59 | **202/288 · %70** |
| Ground truth, gerçek piyasa zemini | 183/267 · %69 | **206/288 · %72** ¹ |
| Duyarlılık (enjekte edilenlerin bulunma oranı) | %57 | **%67** |
| Sıcak arama (4h, API) | ~505 ms | **294–325 ms** |
| Test fonksiyonu | 214 | **313** (parametreli 320 test) |
| Karar kaydı | K-01…K-18 | **K-01…K-21**, K-04/K-11 ekleri |

¹ Bugünkü motorla en son ölçüm (`--compare-metric`, hybrid sütunu). Kapının
replikasyonu ayna düzeltmesinden önceki kodla 210/288 vermişti (Bölüm 8.4).
Başlangıç sütunundaki sayılar filtre her sorguda açıkken, kapı bağlanmadan
önceki motora aittir.

**Ürün açısından:** Kullanıcı OBO ya da ikili tepe çizdiğinde motor artık
o formasyonu buluyor, çizimi nasıl okuduğunu ekranda söylüyor, okuması
kararsızsa bunu da söylüyor. Üçgen, takoz ve bayraklarda trend çizgilerini
okuyor. Tarihsel istatistik, çalışan motorla ölçülmediyse sayfa bunu
kendiliğinden bildiriyor.

**Bilimsel açıdan:** Projenin manşeti — *"formasyonun şekli, kısa vadeli
momentum tersine dönüşünden bağımsız bilgi taşımıyor"* — bu oturumda iki
kez yeniden sınandı. İlk sınamanın bayat bir hedef listesiyle ve tek zaman
diliminde yapıldığı ortaya çıktı; doğru hedeflerle ve **iki zaman diliminde**
sınandığında manşet ayakta kaldı (Bölüm 7.5).

**Yöntem açısından:** Oturumun en önemli çıktısı tek bir özellik değil,
ölçüm disiplini: dairesel olmayan ground truth zemini (`gt_benchmark`),
denetçinin kendisinin denetlenmesi (`formation_audit --cross`), değişmezlik
testleri ve motor davranışının parmak izi. Bu araçların her biri en az bir
hatayı — bir kısmı benim — yakaladı.

---

## 2. Zaman çizelgesi

| tarih | kullanıcının isteği | yapılan |
|---|---|---|
| 24 Ağu | "Projeyi iyice analiz et" | Tüm katmanlar okundu; F4.6'nın geçersiz veriyle yayınlandığı ve `/api/findings` sayılarının veriyle çeliştiği bulundu |
| 24 Ağu | "Çizim yeri stabil değil, çizdiğimi anlamıyor; genel bug fix" | Çizim yolunda beş ayrı hata düzeltildi (Bölüm 3), tarama bulguları (Bölüm 4) |
| 24 Ağu | "GitHub'a pushla", "localhost'u hazırla" | Depo bağlandı, satır sonları sabitlendi, `.claude/launch.json` |
| 29 Ağu | "Açık kaynak benzerlerini araştır" | Beş katmanlı tarama (Bölüm 5) |
| 29 Ağu | "Alabileceğimiz özelliklerin hepsini al, hâlâ güzel çalışmıyor" | Kaba kuvvet doğrulaması, ince ayar (ölçüldü, bağlanmadı), GA kapsama sınaması, **4h korpusunun %7'de kaldığı** bulundu ve düzeltildi |
| 8 Eyl | "Geliştirmeye devam et, bol commit" | F4.7 çaprazlama, Radar önbelleği, oturum sayacı, örneklem kırpması |
| 8 Eyl | "Çift tepe, OBO çiziyorum ama formasyonu bulmuyor" | Ölçüldü (%42), yapısal imza filtresi (Bölüm 8.1) |
| 8 Eyl | "Ne öneriyorsan onu yap" | Üç açık karar bağlandı |
| 9 Eyl | "Devam et" | Denetim 12 formasyona, ground truth zemini, K-20/K-21, ayna hatası |
| 10 Eyl | "Devam" | Bulguların bayatladığı bulundu, köken mekanizması, değişmezlik taraması |
| 10 Eyl | "Önerini yap" (merkezi fark türevi) | Yazıldı, kalibre edildi, ölçüldü; Keogh kaldı (Bölüm 10.4) |
| 10 Eyl | "Yaptığın her şeyi detaylı dokümante et" | Bu belge |

---

## 3. Çizim paneli: "çizdiğimi anlamıyor"

`2517d41` — Tek bir sebep yoktu; çizim yolunda beş ayrı hata birikmişti.

| hata | etkisi | düzeltme |
|---|---|---|
| **Geri çizim sıralanıyordu.** `resample()` ve `normalize_drawing()` x'e göre sort ediyordu | El sola kaydığı an y değerleri x sırasına diziliyor, **kullanıcının çizmediği bir şekil** aranıyordu | "Sonra yazan kazanır": `monotone_xy` (sunucu) ve `useDraw.push` (istemci) — iki tarafta aynı kural |
| **Dikey hareket düşüyordu.** yatay adımı `MIN_STEP`'ten küçük olan örnekler atılıyordu | Dik çizilen bir tepenin zirvesi — formasyonun tanımlayıcı yeri — kayboluyordu | Nokta düşmüyor, son noktanın y'si güncelleniyor |
| **`pointerleave` darbeyi bitiriyordu** | Panelden taşan bir baş tam orada kesiliyordu | İşaretçi yakalanıyor (`setPointerCapture`); iptali `pointercancel` taşır |
| **Kanvas her `pointermove`'da yeniden tahsis ediliyordu** | Uzun darbelerde kare düşüyor, nokta kayboluyordu | Boyama `requestAnimationFrame` ile kare başına bire indi, `getCoalescedEvents` açıldı |
| **Titreme filtresiz 32 noktaya iniyordu** | ~300 noktayı 32'ye indirmek bir decimation'dır; alçak geçiren filtre olmadan titreme *aliasing* ile çizilmemiş bir yapıya katlanır, DDTW türev alıp bir daha yükseltir | `antialias()` — **yalnız serbest çizimde**; şablonlar filtrelenmez çünkü F3 eşikleri onların ham hâlinden kalibre edildi |

Bir de sözleşme hatası vardı: istemci x ızgarasını kendi uyduruyordu
(yalnız y listesi gönderiyordu), yani `normalize_drawing`'in "kullanıcı
hızlı/yavaş çizer" diye yazılmış `(x, y)` dalı API'den hiç erişilemiyordu.
Artık ham `[[x, y], ...]` gidiyor; tek normalizasyon otoritesi motor (K-02).

`8c4be2f` — Ölçülmemiş (sıfır genişlikli) kapta darbe başlatılmıyor: gizli
bir sekmede tüm noktalar aynı x'e düşüyor ve `y = f(x)` sözleşmesi darbeyi
tek noktaya indiriyordu. Çöp bir sorgu göndermektense hiç göndermemek.

---

## 4. Genel hata taraması

Çizim düzeltmesiyle aynı taramadan çıkanlar (`2517d41`, `e96ba2f`):

- **`/api/findings` sayıları veriyle çelişiyordu.** "F4.5 Bonferroni 14/52"
  yazıyordu; ölçüm dosyası 2 diyordu. 14, bir önceki adımın sayısıydı ve
  Bonferroni bir sayıyı artıramaz. Sayılar artık ölçüm dosyalarından türetiliyor.
- **"Daha Fazla" havuz bittikten sonra da açık kalıyordu**, boş sayfa dönüyordu.
- **Oturum başlığı sessizce düşebiliyordu** → hiç artmayan sayaç, hiç
  görünmeyen Bonferroni uyarısı.
- **ShapeThumb gradient kimliği içerikten türetiliyordu**; aynı uzunlukta ve
  aynı değerle başlayan iki karo çakışıyordu.
- **Tek `[x, y]` noktası, düzensiz liste ve sınırsız yük** artık reddediliyor.
- **`apiClient`'taki tip dönüşümü geçersizdi** (`tsc` reddediyordu);
  `AxiosHeaders.from()` ile kuruldu.
- **Satır sonları** (`f7258fa`): Windows'tan taşınan çalışma kopyasında 98
  dosya "değişmiş" görünüyordu (20.098 ekleme/silme, sıfır içerik farkı).
  `.gitattributes` ile index her iki tarafta LF görüyor.

---

## 5. Açık kaynak araştırması ve ödünç alınanlar

29 Ağustos'ta beş katmanda tarama yapıldı: kural tabanlı dedektörler,
benzerlik arama, DTW motorları, istatistiksel doğrulama ve çizerek sorgulama.

**Sonuç: parçaların hepsi var, bütünü yok.** En popüler dedektör
(`BennyThadikaran/stock-pattern`) formasyonun işe yarayıp yaramadığını
istatistiksel olarak sınamıyor. Kavramsal olarak en yakın rakip
(`chart-library-mcp`) çizimle sorgulamıyor ve baseline'la anlamlılık testi
yapmıyor. Çizerek sorgulama akademide var (SketchQuery, Qetch), bakımlı
açık kaynak uygulaması yok.

**Bağımsız doğrulama:** `honest-signals` (ABD hisseleri, kural dedektörü)
105 hücreden 3'ünde baseline'dan ayrışma buldu ve **hiçbiri Bonferroni'den
geçmedi**. Farklı veri, farklı yöntem, GraphFlow'la aynı sonuç — negatif
bulgunun metodolojik bir kaza olmadığının dışarıdan kanıtı.

**Ödünç alınanlar ve akıbetleri:**

| fikir | kaynak | akıbet |
|---|---|---|
| Kaba kuvvetle ikinci kez yanıtlayıp karşılaştırma | STUMPY / MASS | ✅ `tools/verify_stage1` — bütünlük birebir, stride bedeli ölçüldü (ort. +0,021, en kötü +0,096 kosinüs) |
| Stride bedelini telafi eden ince ayar | (üstteki ölçümden) | ❌ **Bağlanmadı (K-19)** — mesafe ve kosinüs takas ediyor, ikisini birden iyileştiren hedef yok |
| Getiri dağılımı bandı (p10–p90) | chart-library-mcp | ❌ **Söküldü** (`f27d3db`) — 12/12 hücrede bant tam bariyerlerin üstündeydi; bilgi veriden değil bariyer ayarından geliyordu. Bilgi taşıyan yarısı (medyan, artıda kapanma oranı) kaldı: *"OBO 2:1 → beklenti +0,015R ama medyan −1,000R"* |
| Aralık kalibrasyon kontrolü | chart-library-mcp | ✅ `tools/ci_calibration` — ay-bloklu bootstrap %92 kapsıyor, iid gerçek rejimde ~%80–89 (nominal %95 değil) |

---

## 6. Korpus: 4h evreni 80 → 1.097 sembol

`ab58f39`, `166925b` — **"Hâlâ güzel çalışmıyor" şikâyetinin asıl sebebi
buydu.** Arayüzün varsayılanı 4h'ydi ama 4h korpusu 80 sembol / 881K
pencereydi; 1d ise 1.165 / 1,87M. Kullanıcı, motorun kalibre edildiği
korpusun **%7'sinde** arama yapıyordu. Motor kötü sonuç vermiyordu —
bakacak yeri yoktu. F3/F4 ölçümlerinin tamamı 1d'de yapıldığı için fark
ölçüme de yansımamıştı.

Arşivden (data.binance.vision) 1.082 sembol indirildi — REST değil, çünkü
delist edilmiş pariteler REST'te görünmez ve onları atlamak K-13'ün
survivorship düzeltmesini sessizce geri alırdı.

| | önce | sonra |
|---|---|---|
| 4h pencere | 881.091 | **11.600.769** |
| 4h likit pencere | 92K | **1.174.008** |

**Kanıt:** Eski evren referans alınıp ilk sayfalar karşılaştırıldı — ilk 12
sonucun **%86'sı** eski evrende olmayan sembollerden geliyor; fincan-kulpta
eski 73 sembolden ilk 12'ye giren tek sonuç yok.

**Genlik eşiği ölçüldü** (`57e43ab`): config'de "geçici — ölçülmedi" notuyla
√6 ölçeklemesinden tahmin edilmiş %6,0 duruyordu. 4.644.712 likit pencerede
ölçüm aynı değeri verdi — sayı değişmedi ama artık dayanağı var.

---

## 7. İstatistik katmanı düzeltmeleri

### 7.1 F4.6 geçersiz veriyle yayınlanmıştı (`dc0bd67`)

İlk koşum, zaman dilimi başına sembol haritası düzeltilmeden yapılmıştı:
1d koşusu 4h evreninin 73 sembollük haritasını okudu ve **N = 2–7** ile
"sonuç" üretti. Rapor, dayandığı satırların tersini iddia ediyordu
("2 formasyon yapısal alfa kanıtladı"). Yeniden koşuldu (N = 242–509),
Bonferroni eklendi, rapor baştan yazıldı.

### 7.2 İstatistik örneklemi gösterim sabitiyle kırpılıyordu (`53ae97d`)

`SEARCH_CACHE_MATCHES = 600` bir sayfalama sabiti sanılıyordu, ama `/stats`
bu havuzdan hesaplıyor. Kırpma rastgele değil, **en iyileri tutuyor** —
yanlı alt örneklem:

| şablon | beklenti (600) | beklenti (2000) |
|---|---|---|
| çanak dip | +0,0391R | +0,0018R |
| ayı bayrağı | +0,0561R | +0,0106R |

Sınır 2.000'e çıktı, `tests/test_integration.py` nöbet tutuyor.

### 7.3 Oturum sayacı tıklama sayıyordu (`8822789`)

Bonferroni ailesi *ayrı hipotezlerin* sayısıdır; sayaç her isteği sayıyordu.
Açık bırakılmış bir Radar sekmesi, kullanıcı hiçbir şey denemeden α'yı
küçültürdü. Artık hipotezin parmak izi sayılıyor. Radar otomatik
yenilemesinin (`c9ea236`) önündeki asıl engel buydu — performans değil,
muhasebe.

### 7.4 N = 4 ile "+0,80R" normal kart gibi dönüyordu (`6225430`)

Güven aralığı doğruydu ([−0,39; +2,00]) ama ekranın ortasındaki sayı
+0,80R'ydi. `MIN_EVENTS_FOR_CLAIM = 30` altında başlık "yetersiz örnek"
diyor.

### 7.5 Replikasyon ve manşetin iki kez yeniden sınanması

- **F4.7** (`09cc67f`): 4h korpusu büyüyünce aynı 56 test ilk kez 4h'de de
  koşulabildi. İlk koşumda replike eden tek formasyon yükselen takozdu.
- **Sınırdaki bulgu kırılgandır** (`de81408`): 9 yıllık geçmişe 10 günlük
  veri eklemek Bonferroni'yi geçen hücrelerin **kimliğini** değiştirdi. Bu
  oturumda kimlik değişimi dört kez gözlendi (veri tazeleme, yapısal filtre,
  aday havuzu, motor düzeltmeleri).
- **F4.10** (`596d319`): Motor değişince bulgular yeniden üretildi ve F4.6
  vekil testinin iki kusuru bulundu (Bölüm 10.3). Doğru hedeflerle iki
  dilimde:

| | eski motor | yeni motor |
|---|---|---|
| F4.7 replikasyon (%95, iki dilim, aynı yön) | 2 hücre | 4 hücre (2 bağımsız olgu) |
| F4.6, eşleştirilmiş gölgeden sonra, 1d | 0/5 (bayat liste) | 2/4 |
| F4.6, **iki dilimde birden** | ölçülmedi | **0/8** |

1d'de iki şablon (ikili tepe, flama) eşleştirmeden sonra anlamlı kaldı; ikisi
de 4h'de sıfıra düştü (ikili tepe 4h'de 1d'nin ~3 katı örneklemle). Replike
eden tek şey vekil deseninin kendisi: yükselen takozun etkisi iki dilimde de
standart gölgeyle anlamlı (+0,270 / +0,185), momentum eşleştirilince iki
dilimde de eriyor (+0,030 / +0,083).

---

## 8. Formasyon tanıma: asıl şikâyet

> *"Çift tepe çiziyorum ya da omuz baş omuz çiziyorum ama hâlâ sadece benzer
> şeyleri koymaya çalışıyor, çalışacak bir formasyon bulamıyor."*

### 8.1 Önce ölçüldü

`tools/formation_audit` — DTW'den bağımsız, belirginlik tabanlı tepe/dip
denetimi. 4h, ilk 12 sonucun kaçı gerçekten o formasyon:

| | OBO | ters OBO | ikili tepe | ikili dip | genel |
|---|---|---|---|---|---|
| filtresiz | 6/12 | 4/12 | **3/12** | 7/12 | %42 |

Şikâyet haklıydı. Sebebi K-04'te zaten yazılıydı: **DTW noktaları hizalar,
hizalanan noktaların seviyelerinin mantıklı olup olmadığına bakmaz.**
"Yükseliş–tümsek–düşüş" yakalanır, omuz–baş–omuz olup olmadığı sorulmaz.

### 8.2 Üç yol denendi (`b5355c7`)

| yol | sonuç |
|---|---|
| ham (filtresiz) | %42 |
| çapa tabanlı kısıt katmanı (şablon meta-verisinden) | %54 — ama OBO'da **kötüleşti** (6 → 4), ve serbest çizimde meta-veri yok |
| **sorgudan türeyen yapısal imza** | dönüş ailesinde ~%100 |

Yapısal imza, kullanıcının çizdiği şeklin kendisinden türer: kaç belirgin
uç, en uç olanın sırası, uçların benzer seviyede olup olmadığı. Formasyon
başına kod yoktur — K-04 korunur, hatta saflaşır. **Elle çizilmiş OBO'da
ilk 12'nin doğruluğu 1/12'den 12/12'ye çıktı.**

Filtre adayların %70–85'ini elediği için istatistiksel güç düştü (F4.8);
kaybın bir kısmı aday havuzu büyütülerek geri alındı (`28f6dab`, OBO 73 → 169
sonuç). Simetrik üçgen şablonu 3 çevrimden 2'ye indirildi (`7a3fe25`) —
32 noktada 3 tam salınım temsil sınırındaydı ve öğe gerçek veride ölüydü.

### 8.3 Motor çizimi nasıl okuduğunu söylüyor (`1e62dfb`)

*"Motor şeklinizi şöyle okudu: 3 belirgin tepe · ortadaki en yüksek ·
diğerleri benzer seviyede — sonuçlar bu yapıyla sınırlı."* Görünmeyen bir
yorum tartışılamaz; yanlış okunduysa kullanıcı görür ve yeniden çizer.

### 8.4 Eğim tabanlı formasyonlar: K-20 ve K-21

Denetim 4 formasyondan 12'ye genişletildi (Bölüm 9.1) ve yapısal filtrenin
üçgen/takoz/bayrakta işe yaramadığı görüldü: onları tanımlayan şey uç
**sayısı** değil trend çizgilerinin **eğimidir**.

**K-20 — kararlılık kapısı.** Sorguya küçük gürültü eklendiğinde imza
hayatta kalıyor mu? Dönüşlerde %98–100, eğimlilerde çoğunlukla düşük.
Kararsız bir imzayla eleme yapmak gürültüye göre elemektir. Kapı: filtre
yalnız kararlı imzada uygulanır. **Bu karar önce yanlış verildi** (Bölüm
12), ground truth'la düzeltildi:

| | kesinlik | duyarlılık |
|---|---|---|
| kapılı filtre | **202/288 · %70** | **%67** |
| her sorguda filtre | 169/287 · %59 | %57 |

Hiçbir formasyon kötüleşmiyor: flama 4 → 12, simetrik üçgen 10 → 16,
yükselen takoz 11 → 17. Gerçek piyasa zemininde de aynı yönde.

**K-21 — zarf (trend çizgisi) filtresi.** Dokunuş noktalarından üst ve alt
zarfa regresyon; imza = (üst eğim sınıfı, alt eğim sınıfı, yakınsama
sınıfı). Üçüncü bileşen olmadan katman ölüydü: takoz sorgusunda ilk 50'nin
**50'si** ilk iki bileşeni zaten taşıyordu. O da önce "bağlanmadı" diye
kaydedildi, K-20 düzeltilince ölçüm bayatladı, yeniden ölçüldü ve **kapıyla**
bağlandı:

| filtrenin devreye girdiği 5 formasyon, 48 hedef | kesinlik |
|---|---|
| zarf filtresi açık | **103/120 · %86** |
| kapalı | 94/120 · %78 |

Kapı burada da zorunlu: OBO'nun zarf imzası tanımlıdır ama kararlılığı
%41'dir — kapısız zarf filtresi motorun tek güçlü olduğu aileyi yazı-turayla
elerdi. 12 formasyonluk koşuda dokuzu bire bir aynı kalıyor.

### 8.5 Elle çizimle sınama (`2c9f8d8`)

Kullanıcı şablon seçmez, çizer. Titreme imzanın kararlılığını düşürür;
elle çizilmiş bir OBO kapıyı geçemezse asıl şikâyet geri gelirdi. Ölçüldü
(formasyon başına 6 elle çizim):

| | kapı | her sorguda filtre |
|---|---|---|
| sentetik, 12 formasyon | **1169/1728 · %68** | 1098/1697 · %65 |
| — ikili tepe | **102/144** | 87/144 |
| gerçek piyasa, dönüşler | 438/576 | 438/575 |

OBO ve ters OBO bire bir aynı. Elle çizilmiş ikili tepede kapı **yardım
ediyor**: kararsız okumalar gerçekten yanlış okumalardı (titreme fazladan
tepe üretmişti).

---

## 9. Ölçüm altyapısı

### 9.1 `tools/formation_audit` — sonuçların yapısını denetler

- İki bağımsız aile: **uç ailesi** (dönüşler, belirginlik) ve **zarf ailesi**
  (üçgen/takoz/flama/bayrak, eğim). 12 formasyon; fincan-kulp ve çanak dip
  eğrilikle tanımlandığı için **denetimsiz** — uydurma bir denetim yazmak
  yerine öyle olduğu yazıldı.
- **Denetçinin kendisi denetlenir:** `--cross`, 12 denetim × 14 kanonik
  şeklin çapraz tablosunu basar. İlk yazımda köşegen dışında 4 kabul vardı
  (ters OBO ikili tepe sayılıyordu); belirginlik üstünlüğü koşuluyla 0'a
  indi. Her şeye "evet" diyen bir denetçi %100 raporlar ve hiçbir şey ölçmez.
- **Sınırı:** yalnız kesinlik ölçer — elenen doğruyu göremez. K-20'deki
  hatanın kaynağı buydu.

### 9.2 `tools/gt_benchmark` — ground truth

Formasyonu **biz koyarız**: bilinen bar aralığına enjekte edilir, dönen
pencere o aralıkla örtüşüyorsa doğrudur. Ölçüt ne motorun ne denetçinin
mekanizmasına bağlıdır, dolayısıyla zarf eğimine dayanan bir filtreyi
dairesel olmadan ölçebilir.

- Gürültü sembollerine **başka** formasyonlar konur: üçgen ararken bayrak
  bulmak isabet değildir.
- `--real`: hedefler gerçek pariteye enjekte edilir (O/H/L bar başına aynı
  oranla ölçeklenir), dağıtıcılar **dokunulmamış gerçek veridir**.
- `--freehand N`: şablon yerine N elle çizim taklidi.
- `--compare-structure / -gate / -envelope / -metric`: aynı korpusta iki
  konfigürasyon.

**İlk ölçüm teşhisi değiştirdi:** gürültü sembolü 40 → 120 → 300 yapıldığında
duyarlılık sabit (%58), kesinlik %88 → %65 → %58. Motor enjekte edilenleri
her yoğunlukta aynı oranda buluyordu; kaybettiği yer sıralamaydı.

### 9.3 `engine/fingerprint.py` — bulguların kökeni

Bölüm 10.3'e bakın.

### 9.4 `tools/calibrate_metric` — aynı seçicilikle eşik

Yeni bir Aşama 2 metriği için mutlak eşikleri, referans metriğin eşiğinin
her sorgunun null dağılımındaki yüzdeliğine denk getirerek türetir.
Doğrulandı: F3'te bağımsız kalibre edilmiş `dtw` eşiklerini %5 içinde
yeniden üretiyor. Yalnız iki metrik pencereleri benzer sıralıyorsa geçerli.

### 9.5 Diğerleri

`tools/verify_stage1` (kaba kuvvet), `tools/ci_calibration` (GA kapsaması),
`tools/run_outcomes` (F4/F4.5 yeniden üretilebilir — önceden bu dosyaları
üreten araç depoda yoktu), `tools/measure_amplitude`, `tools/template_health`,
`tools/backfill`.

---

## 10. Motorun çekirdeğinde bulunan hatalar

### 10.1 Belirginlik aynaya göre değişiyordu (`c80c1e0`)

Sol taban en **soldaki** (en uzak) yüksek noktayı, sağ taban en yakınını
kullanıyordu. Rastgele pencerelerin **%83'ünde** bir şekil ile aynası farklı
uç kümesi veriyordu. Sebep izole edildi: ham uç tespiti %0, belirginlik
eşiği 0'da %0, eşik 0,5'te %83. Aynı hata denetçide de vardı (bilerek ayrı
yazılmış ikinci uygulama); ikisi de düzeltildi ve bir test ikisinin aynı
sonucu verdiğini tutuyor. Ground truth 195 → 202/288.

### 10.2 Baskın taraf ters çevirmeye göre simetrik değildi (`7eb23fb`)

Değişmezlik taraması (şekil okuyan her fonksiyon, 2.000 pencere):

| fonksiyon | ayna | dikey çevirme |
|---|---|---|
| uç tespiti | %0 | %0 |
| yapısal imza | %0 | **%50,2** → %0 |
| zarf imzası | %0 | %0 |
| Aşama 2 · ham DTW | 3e-16 | 0 |
| Aşama 2 · DDTW | sıra korel. 0,92–0,97 | 0 |

Eşitlikte (tepe sayısı = dip sayısı) her zaman tepeler seçiliyordu.
Yükselen üçgenin dikey çevrilmişi alçalan üçgenin ta kendisidir, ama motor
birini yatay tarafından (%36), ötekini eğimli tarafından (%81) okuyordu.
Artık eşitlikte daha belirgin uç kazanır; tam eşitlikte imza uydurulmaz.
Ground truth'ta bire bir aynı — doğruluğu değil tutarlılığı onarıyor.

### 10.3 Bulgular motorla birlikte sessizce bayatlıyordu (`0cd9143`)

Bulgu dosyaları 8 Eylül 23:18'de üretilmişti; ertesi gün üç motor
değişikliği bağlandı ve üçü de istatistiğe giren pencere kümesini değiştirdi
(yükselen üçgen 1d'de 30 → 97). "Bulgular" sayfası bir gün boyunca başka bir
motorun istatistiğini gösterdi.

`engine/fingerprint.py` — **config değil davranış** parmak izi. Ayna
düzeltmesi hiçbir sabiti değiştirmemişti; filtre katmanları ve Aşama 2 sabit
girdilerde çalıştırılıp çıktı özetlenir. İki yönde doğrulandı:

| | parmak izi | |
|---|---|---|
| ayna düzeltmesinden önce / sonra | `6e2d1c54` ≠ `cb49511d` | yakaladı ✓ |
| vektörizasyondan önce / sonra | aynı | yanlış alarm yok ✓ |

Ölçüm araçları köken yazar; `/api/findings` karşılaştırır ve `stale` taşır;
arayüz uyarı ve köken kartı gösterir. **İlk gerçek kullanımı:** baskın taraf
düzeltmesi (10.2) sabitsiz bir kod değişikliğiydi ve dört tablo
kendiliğinden "farklı motor" olarak işaretlendi.

Aynı turda bulunan üç hata daha:

- **F4.6 hedef listesi elle yazılmıştı.** "F4.5'te short anlamlı çıkanlar"
  diye tanımlanmış, değeri eski motordan kopyalanmıştı. İki dilimde replike
  eden flama vekil testine hiç girmiyordu. Artık ölçümden hesaplanıyor.
- **`apply_bonferroni` şablon listesini ikinci geçişe iletmiyordu.**
- **F4.6 hiç 4h'de koşulmamıştı** — projenin kendi replikasyon kuralına aykırı.
- API'de sabit yazılmış üç metin veriyle çelişiyordu ("replike eden tek
  formasyon yükselen takoz", "beş şablonun beşinde", "Bonferroni m=52" —
  ölçüm 56). Üçü de artık veriden.

### 10.4 DDTW türev tahmincisi — ölçüldü, değiştirilmedi (`c89316c`)

Keogh–Pazzani tahmincisi yarım adım geriye kaymış (x = i² için 2i − 0,5).
Kullanıcı onayıyla merkezi fark (`hybrid_central`) yazıldı, aynı seçicilik
ilkesiyle kalibre edildi, ölçüldü:

| | Keogh | merkezi |
|---|---|---|
| AUC (K-11'in ölçütü) | **0,9059** | 0,9039 — 108 hücrenin 105'inde geride |
| ground truth, 3 korpus | **614/864** | 610/864 |
| gerçek piyasa zemini | **206/288** | 193/288 |

**Keogh kalıyor.** Ayna simetrisi bir özellik; eksikliği burada bir hata
değil — ileri yönde sorgu ve aday aynı kaymayı yer. Yan düzeltme bağlandı:
mutlak akıl sağlığı tavanı artık çağrının metriğinden okunuyor.

---

## 11. Performans ve arayüz

### Performans

| iş | önce | sonra | commit |
|---|---|---|---|
| yapısal imza maskesi (2.500 aday) | 250 ms | **47 ms** | `6aedb20` |
| zarf imzası (2.500 aday) | 160 ms | **4,8 ms** | `864dd7c` |
| sıcak arama, 4h, API | ~505 ms | **294–325 ms** | |
| soğuk şablon sorgusu | 537–595 ms | **364–459 ms** (açılışta null ısıtma) | `05729cb` |
| Radar tekrar çağrısı | 552 ms | **1,2 ms** (önbellek) | `84022da` |

Vektörizasyonların her birinin tekil yolla **birebir** eşdeğerliği testle
tutuluyor: iki yol ayrışırsa filtre sessizce başka bir şey elemeye başlar
ve bunu hiçbir doğruluk ölçümü göstermez.

`bc01aac` — motor logları hiçbir yere gitmiyordu (uvicorn yalnız kendi
logger'larına handler kuruyor); ısıtma hatası, atlanan ince ayar görünmüyordu.

### Arayüz

- **Motorun okuması** (8.3) ve **trend çizgisi okuması:** *"Trend çizgileri:
  yatay direnç · yükselen dipler · daralan — sonuçlar bu düzenle sınırlı."*
  Formasyon adı uydurulmuyor, yalnız okunan düzen söyleniyor.
- **Kararsızlık uyarısı:** okuma kararsızsa neden eleme yapılmadığını ya da
  hangi okumaya göre yapıldığını söylüyor. Bir sürümde bu metin yanlış bilgi
  veriyordu ("daraltılmadı" derken zarf filtresi daraltıyordu) — `294e854`.
- **Bulgular sayfası:** köken kartı (hangi motor, hangi veri, ne zaman) ve
  bayatlık uyarısı; aşama sayıları ve açıklamaları veriden.
- **Radar** 5 dakikada bir kendini yeniliyor; boş olay durumu sessiz
  kalmıyor (`48fef5a`).

---

## 12. Kendi hatalarım

Bu bölüm bilerek ayrı: bir karar kaydı yanlış verilen kararları da tutmalı.

| hata | nasıl yakalandı | ders |
|---|---|---|
| **K-20'yi yanlış verdim.** Kapıyı "filtre eğim ailesinde etkisiz, 400'de 5 fark" diye bağlamadım. `formation_audit` yalnız kesinlik ölçer; filtre gerçek formasyonları eliyordu ve denetçi onları göremiyordu (duyarlılık %57 → %45) | Duyarlılığın %58'de takıldığını fark edip her kaskad kapısını tek tek sorguladım; `TGT021USDT` kosinüs sırası 3, mesafesi eşiğin beşte biri — ve listede yok | **Kesinlik filtreyi aklar, duyarlılık suçlar** (CLAUDE.md) |
| **K-21'i bayat ölçümle kapattım** — ölçerken K-20 hâlâ yanlıştı | K-20 düzeltilince zemin değişti; yeniden ölçtüm | Bir kararı değiştirince ona bağlı ölçümler de bayatlar |
| **n = 12 ile "zarar" okudum** (alçalan üçgen 3'e 7) ve mimari değiştirmek üzereydim | n = 50'de kayboldu | **Bir "zarar" bulgusu bir "kazanç" bulgusu kadar güç ister** |
| **"48/48 = %100" dedim** | Denetçiyi sıkılaştırınca bir kısmının tanım belirsizliği olduğu çıktı (ters OBO ikili tepe sayılıyordu); gerçek 197/200 | Denetçi denetlenir |
| **9 kırık testle push'ladım** (`1e62dfb`) — komutları `&&` yerine `;` ile zincirlemiştim | Sonraki koşumda | Commit artık test sonucuna bağlı |
| **`engine/search/engine.py` 592 satırlık yeniden yazım olarak commit edildi** (satır sonu) | Push'tan önce diff boyutundan | `.gitattributes` |
| **Test eşiğim keyfîydi** (0,99 korelasyon; ölçülen 0,977) | Ortam kurulunca | Sabit eşik yerine asıl iddiayı ölç |
| **Performansı ısıtma sürerken ölçtüm** (388–583 ms) | İkinci çağrının birinciden yavaş olması tuhaftı; log satırı çağrılarımdan sonra düşmüştü | Ölçüm boşta alınır (belgeye yazıldı) |
| **Dilim tabanlı bir düzenleme aradaki fonksiyonları yuttu** | Testler toplanamadı; commit'ten önce `git checkout` ile geri alındı | Hedefli değiştirme, dilim değil |
| **Getiri bandını ölçmeden ekledim** | Kendi kuralımızla sınayınca 12/12 hücrede bariyerlerin üstünde çıktı; söktüm | Ekle, sonra değil — önce ölç |

---

## 13. Açık kalanlar

1. **Bayrak ve düşen takoz en zayıf halka.** Ground truth'ta düşen takoz
   %38–46 (her korpusta en düşük), boğa bayrağı sentetikte %42. Bayrağın
   zarfı direği de kapsadığı için tam pencerede kararsız; gövdeyi direkten
   ayırmak formasyona özel kod demek (K-04). Doğru biçim muhtemelen sorgudan
   türeyen bir **bölütleme**.
2. **Eğim ailesinde kesinlik yoğunlukla düşüyor.** Maske değil, sıralamaya
   giren sürekli bir **tanım uyum skoru** gerekebilir; K-14'ün yüzdelik
   sıralamasına dokunacağı için ayrı bir karar.
3. **Simetrik üçgen kapı eşiğinin hemen altında** (%84, eşik %85). Ölçülen
   etki nötr, ama sınırda duran bir değer.
4. **Fincan-kulp ve çanak dip denetimsiz.** Eğrilikle tanımlılar; bağımsız
   bir denetim ailesi yazılmadı.
5. **Aşama 2 metriği** — merkezi fark ölçüldü ve kaybetti; başka bir türev
   tahmincisi (ör. yumuşatılmış) aynı araçlarla birkaç komutta ölçülebilir.

---

## 14. Yeniden üretme

```bash
# Testler
pytest -q                                            # 320 test

# Denetçiyi denetle (veri gerekmez)
python -m tools.formation_audit --cross

# Ground truth
python -m tools.gt_benchmark --family all --compare-gate
python -m tools.gt_benchmark --family all --real --compare-gate
python -m tools.gt_benchmark --family all --freehand 6 --compare-gate
python -m tools.gt_benchmark --family all --compare-metric

# Bulgular (motor her değiştiğinde, ~4,5 dk)
python -m tools.run_outcomes --timeframe 1d
python -m tools.run_outcomes --timeframe 4h --out-suffix _4h
python -m tools.f46_proxy_test
python -m tools.f46_proxy_test --timeframe 4h --templates <1d hedefleri>

# Metrik kalibrasyonu ve AUC
python -m tools.calibrate_metric --metric hybrid_central
python -m tools.ab_stage2 --skip-recall --metrics ddtw dtw hybrid hybrid_central \
    --out data/f3/ab_stage2_central.json
```

İlgili raporlar: [08](08-zaman-dilimi-caprazlama.md) (F4.7) ·
[09](09-yapisal-filtre-ve-istatistik.md) (F4.8) ·
[10](10-formasyon-denetimi.md) (F4.9) · [11](11-yeniden-olcum.md) (F4.10) ·
karar kaydı [00](00-tasarim-kararlari.md) (K-19, K-20, K-21, K-04 ve K-11 ekleri).

---

## 15. Ek: commit dizini

Bu oturumun commit'leri, eskiden yeniye. Git'ten otomatik üretildi
(`git log --reverse --since=2026-08-24`).

| # | commit | tarih | başlık |
|---|---|---|---|
| 1 | [`2517d41`](https://github.com/7mertyavuz/GraphFlow/commit/2517d41) | 24.08 | fix(çizim): çizilen şekil ile aranan şekil ayrışıyordu |
| 2 | [`f7258fa`](https://github.com/7mertyavuz/GraphFlow/commit/f7258fa) | 24.08 | chore: satır sonlarını depo tarafında sabitle |
| 3 | [`e96ba2f`](https://github.com/7mertyavuz/GraphFlow/commit/e96ba2f) | 24.08 | fix(frontend): oturum başlığı yaması tip denetiminden geçmiyordu |
| 4 | [`ab58f39`](https://github.com/7mertyavuz/GraphFlow/commit/ab58f39) | 29.08 | feat(ingest): zaman dilimi tamamlayıcı — 4h evreni 80 sembolde kalmıştı |
| 5 | [`a08ddc6`](https://github.com/7mertyavuz/GraphFlow/commit/a08ddc6) | 29.08 | feat(outcome): getiri dağılımı bandı — beklentinin gizlediği şey |
| 6 | [`0e6afde`](https://github.com/7mertyavuz/GraphFlow/commit/0e6afde) | 29.08 | feat(tools): Aşama 1 kaba kuvvet doğrulaması — stride bedeli ölçüldü |
| 7 | [`a2c1d6d`](https://github.com/7mertyavuz/GraphFlow/commit/a2c1d6d) | 29.08 | feat(search): bar bazında ince ayar katmanı — ölçüldü, BAĞLANMADI |
| 8 | [`dc0bd67`](https://github.com/7mertyavuz/GraphFlow/commit/dc0bd67) | 29.08 | fix(F4.6): faz geçersiz veriyle yayınlanmıştı — yeniden koşuldu, Bonferroni eklendi |
| 9 | [`05f763f`](https://github.com/7mertyavuz/GraphFlow/commit/05f763f) | 29.08 | feat(tools): güven aralıklarının kapsama sınaması — F4.5 doğrulandı, bir uyarıyla |
| 10 | [`a75d0bb`](https://github.com/7mertyavuz/GraphFlow/commit/a75d0bb) | 29.08 | docs: K-19, kapsama bulgusu ve doğrulama araçları karar kaydına işlendi |
| 11 | [`f27d3db`](https://github.com/7mertyavuz/GraphFlow/commit/f27d3db) | 29.08 | fix(outcome): yüzdelik bant bilgi taşımıyormuş — söküldü, medyan kaldı |
| 12 | [`dcebe58`](https://github.com/7mertyavuz/GraphFlow/commit/dcebe58) | 29.08 | test(tools): doğrulama araçlarının kendisi için nöbetçiler |
| 13 | [`57e43ab`](https://github.com/7mertyavuz/GraphFlow/commit/57e43ab) | 29.08 | feat(tools): genlik eşiğini korpustan ölç — 4h'nin "ölçülmedi" notu için |
| 14 | [`166925b`](https://github.com/7mertyavuz/GraphFlow/commit/166925b) | 29.08 | feat(4h): evren 80 → 1.097 sembol, korpus 881K → 11,6M pencere |
| 15 | [`74fe2e8`](https://github.com/7mertyavuz/GraphFlow/commit/74fe2e8) | 08.09 | feat(tools): F4/F4.5 ölçümü yeniden üretilebilir hâle geldi |
| 16 | [`09cc67f`](https://github.com/7mertyavuz/GraphFlow/commit/09cc67f) | 08.09 | feat(F4.7): zaman dilimi çaprazlaması — yalnız yükselen takoz replike ediyor |
| 17 | [`6225430`](https://github.com/7mertyavuz/GraphFlow/commit/6225430) | 08.09 | fix(outcome): N=4 ile "+0,80R beklenti" normal kart olarak dönüyordu |
| 18 | [`3d7f6af`](https://github.com/7mertyavuz/GraphFlow/commit/3d7f6af) | 08.09 | feat(tools): şablon sağlık raporu — kütüphanede ölü bir öğe var |
| 19 | [`24e3140`](https://github.com/7mertyavuz/GraphFlow/commit/24e3140) | 08.09 | feat(api): Bulgular sayfasına zaman dilimi çaprazlaması aşaması |
| 20 | [`0c81908`](https://github.com/7mertyavuz/GraphFlow/commit/0c81908) | 08.09 | test: gerçek korpus üzerinde uçtan uca nöbetçiler |
| 21 | [`edf3c38`](https://github.com/7mertyavuz/GraphFlow/commit/edf3c38) | 08.09 | docs(mimari): plan sayıları ölçülenle değiştirildi |
| 22 | [`de81408`](https://github.com/7mertyavuz/GraphFlow/commit/de81408) | 08.09 | docs(F4.7): sınırdaki bulguların kırılganlığı ölçüldü |
| 23 | [`84022da`](https://github.com/7mertyavuz/GraphFlow/commit/84022da) | 08.09 | feat(api): Radar önbelleği — belgede vardı, kodda yoktu |
| 24 | [`8822789`](https://github.com/7mertyavuz/GraphFlow/commit/8822789) | 08.09 | fix(session): Bonferroni ailesi isteği değil AYRI HİPOTEZİ saysın |
| 25 | [`c9ea236`](https://github.com/7mertyavuz/GraphFlow/commit/c9ea236) | 08.09 | feat(radar): kendini yenilesin — 5 dakikada bir, sayaç şişmeden |
| 26 | [`53ae97d`](https://github.com/7mertyavuz/GraphFlow/commit/53ae97d) | 08.09 | fix(api): istatistik örneklemi gösterim sabitiyle kırpılıyordu |
| 27 | [`3f66e3b`](https://github.com/7mertyavuz/GraphFlow/commit/3f66e3b) | 08.09 | test+docs: örneklem kırpması için nöbetçi, §6 durumu güncel |
| 28 | [`b5355c7`](https://github.com/7mertyavuz/GraphFlow/commit/b5355c7) | 08.09 | feat(search): yapısal imza filtresi — çizilen formasyon artık bulunuyor |
| 29 | [`a038a97`](https://github.com/7mertyavuz/GraphFlow/commit/a038a97) | 08.09 | docs+tools: elle çizim ölçümü tekrarlanabilir, K-04'e Eylül eki |
| 30 | [`8c4be2f`](https://github.com/7mertyavuz/GraphFlow/commit/8c4be2f) | 08.09 | fix(çizim): ölçülmemiş kapta darbe başlatma |
| 31 | [`c215588`](https://github.com/7mertyavuz/GraphFlow/commit/c215588) | 08.09 | docs(F4.8): yapısal filtre istatistiği nasıl değiştirdi — güç düştü, etki durdu |
| 32 | [`e74ef19`](https://github.com/7mertyavuz/GraphFlow/commit/e74ef19) | 08.09 | docs(F4.6): yapısal filtre açıkken yeniden koşuldu — üçüncü kez |
| 33 | [`48fef5a`](https://github.com/7mertyavuz/GraphFlow/commit/48fef5a) | 08.09 | fix(ui): olay kalmadığında sessizce boş dönmesin |
| 34 | [`28f6dab`](https://github.com/7mertyavuz/GraphFlow/commit/28f6dab) | 08.09 | perf(search): aday havuzu büyütüldü — yapısal filtrenin güç kaybını telafi |
| 35 | [`7a3fe25`](https://github.com/7mertyavuz/GraphFlow/commit/7a3fe25) | 08.09 | fix(şablon): simetrik üçgen 3 çevrimden 2'ye — kütüphanenin ölü öğesi dirildi |
| 36 | [`6c8251b`](https://github.com/7mertyavuz/GraphFlow/commit/6c8251b) | 08.09 | docs: üç karar bağlandı, tablolar son ayarla yeniden üretildi |
| 37 | [`17776ba`](https://github.com/7mertyavuz/GraphFlow/commit/17776ba) | 08.09 | docs(mimari): performans bütçesine soğuk/sıcak ayrımı — ölçülen aşım kaydedildi |
| 38 | [`d4c49b5`](https://github.com/7mertyavuz/GraphFlow/commit/d4c49b5) | 08.09 | test(search): yapısal filtrenin motor entegrasyonu — özellikle geri düşme yolu |
| 39 | [`05729cb`](https://github.com/7mertyavuz/GraphFlow/commit/05729cb) | 08.09 | perf(api): açılışta null ısıtma — soğuk sorgu bütçe aşımı kapandı |
| 40 | [`bc01aac`](https://github.com/7mertyavuz/GraphFlow/commit/bc01aac) | 08.09 | fix(api): motor logları hiçbir yere gitmiyordu |
| 41 | [`1e62dfb`](https://github.com/7mertyavuz/GraphFlow/commit/1e62dfb) | 08.09 | feat(ui): motor çizimi nasıl okuduğunu söylesin |
| 42 | [`58b9ba4`](https://github.com/7mertyavuz/GraphFlow/commit/58b9ba4) | 08.09 | fix(test): sahte motor yeni yanıt alanlarını taşımıyordu |
| 43 | [`7f06419`](https://github.com/7mertyavuz/GraphFlow/commit/7f06419) | 08.09 | feat(tools): denetim 4 formasyondan 12'ye — zarf eğimi ailesi |
| 44 | [`8d65cdb`](https://github.com/7mertyavuz/GraphFlow/commit/8d65cdb) | 08.09 | feat(search): imza kararlılığı — ölçüldü, kapı bağlanmadı, rapora bağlandı |
| 45 | [`2f3bd89`](https://github.com/7mertyavuz/GraphFlow/commit/2f3bd89) | 09.09 | docs: K-20 ve F4.9 denetim raporu karar kaydına işlendi |
| 46 | [`864dd7c`](https://github.com/7mertyavuz/GraphFlow/commit/864dd7c) | 09.09 | feat(tools): ground truth ölçüm zemini — ve teşhis değişti |
| 47 | [`78fe490`](https://github.com/7mertyavuz/GraphFlow/commit/78fe490) | 09.09 | docs: K-21 — zarf filtresi ölçüldü, bağlanmadı; teşhis düzeltildi |
| 48 | [`95ae5f0`](https://github.com/7mertyavuz/GraphFlow/commit/95ae5f0) | 09.09 | fix(search): kararlılık kapısı bağlandı — K-20'deki kendi sonucum yanlıştı |
| 49 | [`57fca41`](https://github.com/7mertyavuz/GraphFlow/commit/57fca41) | 09.09 | docs: K-20 yeniden yazıldı — yanlış kararın kendisi de kayıtta |
| 50 | [`1fb0de6`](https://github.com/7mertyavuz/GraphFlow/commit/1fb0de6) | 09.09 | fix(ui): kararsız okuma uyarısı elemenin yapılmadığını da söylesin |
| 51 | [`504dee9`](https://github.com/7mertyavuz/GraphFlow/commit/504dee9) | 09.09 | feat(search): zarf filtresi kapıyla bağlandı — K-21 yeniden ölçüldü |
| 52 | [`294e854`](https://github.com/7mertyavuz/GraphFlow/commit/294e854) | 09.09 | fix(ui): motor hangi okumaya göre daralttığını söylesin |
| 53 | [`c522be1`](https://github.com/7mertyavuz/GraphFlow/commit/c522be1) | 09.09 | docs: K-21 kapıyla bağlandı — ölçümler ve dairesellik uyarısı kayıtta |
| 54 | [`c80c1e0`](https://github.com/7mertyavuz/GraphFlow/commit/c80c1e0) | 09.09 | fix(search): belirginlik hesabı aynaya göre değişiyordu |
| 55 | [`776276e`](https://github.com/7mertyavuz/GraphFlow/commit/776276e) | 09.09 | docs: K-20 rakamları düzeltme sonrası yenilendi + gerçek zemin replikasyonu |
| 56 | [`f23bb79`](https://github.com/7mertyavuz/GraphFlow/commit/f23bb79) | 09.09 | docs: ayna hatası ve dersi kayıtta |
| 57 | [`6aedb20`](https://github.com/7mertyavuz/GraphFlow/commit/6aedb20) | 09.09 | perf(search): yapısal imza vektörize — 250 ms → 47 ms |
| 58 | [`9b7fd9a`](https://github.com/7mertyavuz/GraphFlow/commit/9b7fd9a) | 09.09 | docs: sıcak arama ölçümü API üzerinden doğrulandı (294-325 ms) |
| 59 | [`0cd9143`](https://github.com/7mertyavuz/GraphFlow/commit/0cd9143) | 10.09 | feat(api): bulgular kökenini taşısın — bayat tablo artık sessiz kalmıyor |
| 60 | [`596d319`](https://github.com/7mertyavuz/GraphFlow/commit/596d319) | 10.09 | docs(F4.10): bulgular yeni motorla yeniden ölçüldü |
| 61 | [`7eb23fb`](https://github.com/7mertyavuz/GraphFlow/commit/7eb23fb) | 10.09 | fix(search): baskın taraf ters çevirmeye göre simetrik — değişmezlik taraması |
| 62 | [`129ffcd`](https://github.com/7mertyavuz/GraphFlow/commit/129ffcd) | 10.09 | docs: değişmezlik taraması, DDTW açık sorusu, bulgular yeniden üretildi |
| 63 | [`c89316c`](https://github.com/7mertyavuz/GraphFlow/commit/c89316c) | 10.09 | feat(search): merkezi fark türevi ölçüldü — Keogh kalır (K-11 Eylül eki) |
| 64 | [`2c9f8d8`](https://github.com/7mertyavuz/GraphFlow/commit/2c9f8d8) | 10.09 | feat(tools): ground truth elle çizimle — kapı asıl şikâyeti geri getirmiyor |

Bu belgenin kendi commit'i dizinin ardından gelir.
