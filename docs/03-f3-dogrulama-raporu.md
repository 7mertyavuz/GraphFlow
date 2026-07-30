# GraphFlow — F3 Doğrulama Raporu

> **Belge türü:** Doğrulama kapısı raporu (K-18)
> **Tarih:** 30 Temmuz 2026
> **Durum:** Ölçümler tamamlandı — **göz testi kararı insana bırakıldı**
> **İlgili belgeler:** [00-tasarim-kararlari.md](00-tasarim-kararlari.md) · [01-mimari.md](01-mimari.md)

F3 bir kapıdır: amacı kod yazmak değil, **motorun gerçekten ölçüp ölçmediğine
karar vermek**. Bu belge tüm ölçüm sayılarını, K-11 kararını, seçilen eşikleri
ve **geçemeyen testleri** kaydeder.

> Kötü sonuç gizlenmedi. F3'ün varlık sebebi zaten kötü haberi erken bulmaktır.

---

## Özet

| # | Bulgu | Durum |
|---|---|---|
| 1 | Gerçek veri indirildi: 1.165 parite, 1,5M bar, delist edilenler dahil | ✅ |
| 2 | **Sessiz veri kaybı hatası bulundu ve düzeltildi** (19 ay) | 🐞 → ✅ |
| 3 | K-11 karara bağlandı: `hybrid` > `dtw` > `ddtw` | ✅ |
| 4 | K-13 sağlık kontrolü: 2017–2019 çökmüyor | ✅ |
| 5 | Negatif kontrol: white noise / whipsaw / düz çizgi | ✅ |
| 6 | **Rampa ve neredeyse-düz sorgular her kademeyi geçiyor** | ❌ açık soru |
| 7 | **Orta kademede 14 şablonun 7'si ilk sayfayı dolduramıyor** | ❌ açık soru |
| 8 | Aşama 1 geri çağırma tavanı uzunlukla düşüyor (%95 → %80) | ⚠️ |
| 9 | Sonuçların %68'i en kısa pencerede (24 bar) kümeleniyor | ⚠️ |
| 10 | Radar (live) 23 ms — bütçe 10 ms | ⚠️ |
| 11 | Historical arama 51 ms — bütçe 500 ms | ✅ |
| 12 | K-09 doğrulandı: örtüşen çift 0, max 3/sembol tutuyor | ✅ |
| 13 | **Stablecoin eşleşmeleri ilk sayfanın tepesine giriyor** (%4 volatilite) | ❌ açık soru |

---

## ADIM 0 — Gerçek Veri

### 0.1. Kaynak değişikliği: REST yerine arşiv

`api.binance.com` bu ağdan erişilemiyor (bağlantı sıfırlanıyor; `api-gcp`,
`api1` de aynı). `data.binance.vision` CNAME'i de kapalı, ancak bucket'ın
kendisi S3 adı üzerinden yanıt veriyor.

Bu, K-13 açısından **daha iyi bir kaynaktır**: `exchangeInfo` yalnızca yaşayan
pariteleri verir, arşiv ise delist edilmiş olanları da tutar.

| Ölçüm | Değer |
|---|---|
| Arşivdeki toplam parite | 3.637 |
| USDT + BTC bazlı (evren) | 1.168 |
| İndirilen (1d, tam geçmiş) | 1.165 parite / **1.505.471 bar** |
| 4H (F3 alt kümesi: 80 parite) | 708.060 bar |
| Süre | ~60 dk (20 eşzamanlı bağlantı) |

"Hacimce ilk 50 USDT paritesi" seçimi REST `/ticker/24hr` olmadan yapıldı:
her parite için tek bir aylık dosya (~2 KB) indirilip kote hacim toplandı.

### 0.2. 🐞 Sessiz veri kaybı — F3'ün yakaladığı asıl hata

**Belirti:** İndirme hatasız tamamlanıyor, ancak *tüm* semboller 2024-12-31'de
kesiliyor ve son listelenen 18 parite tamamen boş kalıyor.

**Sebep:** Binance arşivi **2025-01'den itibaren zaman damgalarını
mikrosaniye** yazıyor (`1740787200000000`), daha eski dosyalar milisaniye
(`1704067200000`). Milisaniye varsayan okuyucu, bu barların `close_time`'ını
bugünün damgasından ~1000 kat büyük görüyor ve **"henüz kapanmamış mum"**
(K-05) sanarak düşürüyordu.

**Etkisi:** 19 aylık veri, tek bir hata mesajı olmadan yok oluyordu. Bu veriyle
kurulan bir matris, "son 19 ayda hiçbir formasyon oluşmamış" derdi.

**Düzeltme:** `to_epoch_ms()` + `EPOCH_US_THRESHOLD` (config, K-07 referanslı).
Regresyon testi: `tests/test_vision_archive.py::test_microsecond_bars_are_not_dropped_as_unclosed`.

> Bu hata, sentetik veriyle **asla** yakalanamazdı. F3'ün "gerçek veri şart"
> kuralının somut karşılığı budur.

### 0.3. Veri bütünlüğü

| Kontrol | Sonuç |
|---|---|
| Bar sayısı | BTCUSDT/ETHUSDT 3.269 bar, 2017-08-17 → 2026-07-29 |
| Boşluklu sembol | 43 / 1.165 |
| Yarım mum | **Yok** — son bar 2026-07-29, kapanışı 2026-07-30 00:00 UTC |
| Delist edilenler | Var (aşağıda) |

Boşlukların tamamı **gerçek piyasa olayı**, indirme hatası değil:

| Sembol | Boşluk | Açıklama |
|---|---|---|
| FTTUSDT | 311 gün | FTX çöküşü sonrası işlem durdurma |
| TUSD / USDC / USDP | 166 gün | Binance'in stablecoin spot çiftlerini kapatması |
| LUNAUSDT | 18 gün | Terra çöküşü sırasında durdurma |
| CVCUSDT | 154 gün | Uzun süreli durdurma |

Delist doğrulaması (K-13 — son bar = delist tarihi):

```
USTUSDT     141 bar  2021-12-24 -> 2022-05-13   (Terra/UST çöküşü)
SRMUSDT     840 bar  2020-08-11 -> 2022-11-28   (FTX/Serum)
BUSDUSDT   1548 bar  2019-09-20 -> 2023-12-15
MATICUSDT  1965 bar  2019-04-26 -> 2024-09-10   (POL'e geçiş)
FTMUSDT    2044 bar  2019-06-11 -> 2025-01-13   (S'e geçiş)
```

### 0.4. K-13 sağlık kontrolü — likidite filtresi tarihi siliyor mu?

Matris: 1d × {24, 40, 64, 100} = **1.922.776** pencere (≈1,92M).

| Yıl | Toplam pencere | Likit | Oran |
|---|---|---|---|
| 2017 | 3.071 | 1.734 | %56,5 |
| 2018 | 63.232 | 24.248 | %38,3 |
| 2019 | 93.563 | 33.881 | %36,2 |
| 2020 | 146.055 | 55.589 | %38,1 |
| 2021 | 251.427 | 100.875 | %40,1 |
| 2022 | 306.755 | 122.400 | %39,9 |
| 2023 | 302.989 | 120.606 | %39,8 |
| 2024 | 313.695 | 124.540 | %39,7 |
| 2025 | 296.869 | 114.789 | %38,7 |
| 2026 | 145.120 | 58.440 | %40,3 |

**Sonuç: ✅** Oran her yıl ~%36–40 bandında; 2017–2019 çökmüyor. Sabit dolar
eşiği kullanılsaydı bu yıllar tamamen silinirdi (K-13.2). 2017'nin yüksek oranı
o dönemde çok az parite bulunmasından kaynaklanıyor (kesitin kendisi küçük).

---

## ADIM 1 — K-11 A/B: DDTW mi, ham DTW mi, hybrid mi?

### 1.1. Önceki ölçümün iki kusuru giderildi

**(a) Dairesellik.** F2'de pozitif örnekler, sorgu olarak kullanılan kanonik
şablonun gürültülü kopyalarıydı — bu "şablonu geri bulabiliyor mu"yu ölçer.
Artık pozitifler `tools/shape_variants.py` ile üretilen **farklı örneklerdir**:

* asimetrik omuz yükseklikleri (`left_h ≠ right_h`)
* eğimli boyun çizgisi (iki yöne de)
* farklı kulp derinliği/uzunluğu (`cup_frac`, `handle_depth`)
* tepe/dip zamanlama kayması (monoton zaman bükmesi: `t' = t^γ + a·sin(2πt)/2π`)

Etiket güvenilirliği **yapısal doğrulayıcıyla** garanti edildi: üretilen eğri
beklenen tepe/dip yapısını taşımıyorsa (OBO için 3 tepe / 2 dip) örnek
reddedilip yeniden çekilir. Doğrulama başarı oranı: **%100**.

Varyantların kanonik şablonla korelasyonu — artık "aynı eğrinin kopyası" değil:

| Formasyon | Kanonikle korelasyon (medyan) | En düşük | Varyantlar arası |
|---|---|---|---|
| head_and_shoulders | 0,775 | 0,072 | 0,597 |
| double_top | 0,766 | 0,047 | 0,589 |
| cup_and_handle | 0,960 | 0,727 | 0,894 |
| bull_flag | 0,964 | 0,623 | 0,913 |
| rising_wedge | 0,890 | 0,545 | 0,801 |

**(b) Uzunluk kırılımı.** AUC artık pencere uzunluğuna göre ayrı hesaplanıyor.

### 1.2. Sonuç — 3 metrik × 4 uzunluk × 3 gürültü

Formasyon başına 300 örnek, 9 formasyon. Pozitif = formasyon varyantı + GBM
gürültüsü; negatif = saf GBM penceresi. Ölçüm **yalnızca Aşama 2'yi** izole
eder (Aşama 1 devrede değil).

| Gürültü | Uzunluk | ddtw | dtw | hybrid | Kazanan |
|---|---|---|---|---|---|
| %1 | 24 | 0,985 | 0,989 | **0,992** | hybrid |
| %1 | 40 | 0,979 | 0,980 | **0,985** | hybrid |
| %1 | 64 | 0,961 | 0,970 | **0,976** | hybrid |
| %1 | 100 | 0,949 | 0,956 | **0,965** | hybrid |
| %2 | 24 | 0,948 | 0,957 | **0,963** | hybrid |
| %2 | 40 | 0,920 | 0,926 | **0,936** | hybrid |
| %2 | 64 | 0,872 | 0,901 | **0,913** | hybrid |
| %2 | 100 | 0,843 | 0,863 | **0,877** | hybrid |
| %4 | 24 | 0,860 | 0,860 | **0,871** | hybrid |
| %4 | 40 | 0,791 | 0,824 | **0,835** | hybrid |
| %4 | 64 | 0,735 | 0,776 | **0,788** | hybrid |
| %4 | 100 | 0,637 | 0,746 | **0,753** | hybrid |

**Genel ortalama: hybrid 0,9045 · dtw 0,8956 · ddtw 0,8733**

Sağlamlık:

* hybrid **12/12 hücrede** ve **9/9 formasyonda** kazandı
* Eşli hücre karşılaştırması (108 hücre): hybrid, dtw'den %99'unda; ddtw'den
  %80'inde iyi
* DDTW'nin kaybı gürültü ve uzunlukla **büyüyor** (100 bar / %4 gürültüde
  0,637'ye karşı 0,746) — türevin yüksek geçiren filtre olmasıyla tutarlı

### 1.3. Karar

**`STAGE2_METRIC = "hybrid"`** (= iki normalize mesafenin ortalaması).
Kaybeden metrikler silinmedi, anahtarda kaldı.

Uyarı (rapora yazılması gereken bir asimetri): ham DTW mesafeleri DDTW'ninkinden
~2–4x büyük olduğu için düz ortalama pratikte **ham DTW ağırlıklıdır**. Buna
rağmen hybrid, dtw'yi tutarlı biçimde geçiyor — yani DDTW bileşeni küçük
ağırlığına rağmen bilgi katıyor. Ağırlıklı/ölçek-eşitlenmiş bir harman
(`z-skor blend`) denenmedi; ileride ölçülebilir.

### 1.4. İkincil bulgu — Aşama 1 geri çağırma tavanı ⚠️

Aşama 2 metriği ne olursa olsun, **Aşama 1'in elediği pencere geri gelmez**.
Kosinüs top-K'sine girebilen pozitif oranı:

| Pencere uzunluğu | Geri çağırma |
|---|---|
| 24 | %94,9 |
| 40 | %90,7 |
| 64 | %87,0 |
| 100 | **%79,9** |

En düşükler: `rising_wedge@100 %62`, `falling_wedge@100 %67`,
`inverse_head_and_shoulders@100 %76`.

Yani uzun pencerelerde kaskadın tavanı %80'e iniyor ve bu, metrik seçiminden
**bağımsız** bir sınır. Takoz gibi salınımlı formasyonlarda kosinüs (nokta
bazlı korelasyon) faz kaymasına duyarlı olduğu için eleme daha sert.

---

## ADIM 2 — Negatif Kontrol (gerçek veri)

Sorgular gerçek veriye (1,92M pencere) karşı çalıştırıldı; ölçülen değer
**en iyi normalize mesafedir** (küçük = benzer).

| Sorgu türü | En iyi skor (taban) | Medyan | Davranış |
|---|---|---|---|
| Düz yatay çizgi | — | — | **Pipeline reddediyor** (σ < FLAT_EPS, K-02) |
| Whipsaw (testere) | 0,4840 | 0,4949 | ✅ hiçbir kademeyi geçmiyor |
| White noise | 0,1897 | 0,2927 | ✅ hiçbir kademeyi geçmiyor |
| **Tek yönlü rampa** | **0,0025** | 0,0031 | ❌ **her kademeyi geçiyor** |
| **Neredeyse düz** | **0,0080** | 0,0182 | ❌ her kademeyi geçiyor |

Karşılaştırma için şablon sorgularının en iyi skorları: **0,0084 – 0,0557**.

### 2.1. ✅ Geçen kısım

White noise ve whipsaw, en gevşek kademenin (0,0836) **2,3–5,8 katı** kötü
skor alıyor. Motor bunlara "eşleşme yok" diyebiliyor — K-18'in şartı sağlandı.
Düz yatay çizgi motora hiç ulaşmıyor; normalizasyon onu zaten düşürüyor.

### 2.2. ❌ Geçemeyen kısım — rampa ve neredeyse-düz sorgular

Rampa sorgusu **tüm sorguların en iyi skorunu** alıyor (0,0025). İnceleme,
motorun **doğru** cevap verdiğini gösteriyor:

```
ETHUSDT   L=40  mesafe 0,0030  genlik %77   artan adım oranı %87
ADAUSDT   L=24  mesafe 0,0040  genlik %59   artan adım oranı %87
SOLUSDT   L=40  mesafe 0,0045  genlik %460  artan adım oranı %81
```

Dönen pencereler gerçekten monoton ve yüksek genlikli. Yani "düz eğimli çizgi"
gerçek bir şekildir (trend) ve gerçek veride bolca karşılığı vardır. Aynı
şekilde "neredeyse düz" bir çizim, düşük oynaklıklı pencerelerle eşleşir.

**Bu bir metrik hatası değil, ürün tanımı sorusudur:** trend bir "formasyon"
sayılacak mı? Motor şu an evet diyor.

> **Karar gerekiyor** (bkz. [Açık Sorular](#açık-sorular), S-1).

Not: K-10 genlik filtresi bu iki durumu **çözmüyor**, çünkü dönen pencerelerin
genliği zaten yüksek (%59–460). Genlik filtresinin çalıştığı ayrıca doğrulandı
(`min_amplitude` 50 → 200 → 1000 için sonuç sayısı 133 → 115 → 22).

### 2.3. Skor dağılımı sağlık kontrolü

Tüm sorgular aynı bandı verse metrik ayırt etmiyor demekti. Vermiyor:

* Şablonlar: 0,0084 – 0,0557 (6,6 kat aralık)
* Anlamsız sorgular: 0,1897 – 0,4949
* İki grup **örtüşmüyor**

Histogram: `notebooks/output/negatif_kontrol_histogram.png`

---

## ADIM 3 — Eşik Kalibrasyonu

**Metodolojik ayrım (K-18):** Gerçek veride etiket yoktur → AUC hesaplanamaz.
Bu yüzden:

* **AUC / ROC ve K-11 kararı** → bozulmalı sentetik (etiket biliniyor)
* **Eşik değerleri** → gerçek veri skor dağılımları

Türetme kuralı (`tools/f3_measure.py::calibrate_thresholds`):

| Kademe | Kaynak |
|---|---|
| Katı | Şablonların "12. sonuç" skorunun alt çeyreği |
| Orta | Şablonların "12. sonuç" skorunun medyanı |
| Esnek | Şablon skorlarının %95'lik diliminin üst çeyreği |
| *Üst sınır* | Hiçbiri anlamsız sorgu tabanının %90'ını aşamaz |

Sonuç (1.165 parite, 1d, 1,92M pencere):

| Metrik | Katı | Orta | Esnek | Anlamsız sorgu tabanı |
|---|---|---|---|---|
| ddtw | 0,0118 | 0,0162 | 0,0456 | 0,1726 |
| dtw | 0,0184 | 0,0337 | 0,1097 | 0,2026 |
| **hybrid (aktif)** | **0,0172** | **0,0273** | **0,0836** | **0,1897** |

Üst sınır kuralı hiçbir kademeyi kırpmadı: en gevşek kademe bile tabanın
%44'ünde kalıyor.

**Rampa ve neredeyse-düz sorgular kalibrasyon tabanına dahil edilmedi.**
Edilseydi taban 0,0025'e inerdi ve üç kademe de pozitiflerin altına düşüp
motoru tamamen susturur. Gerekçe §2.2'de.

### 3.1. ❌ Geçemeyen test — orta kademe yarım kütüphaneyi boşaltıyor

Nihai eşiklerle, şablon başına dönen sonuç sayısı:

| Şablon | Katı | Orta | Esnek | En iyi skor |
|---|---|---|---|---|
| falling_wedge | 65 | 485 | 843 | 0,0106 |
| bull_flag | 42 | 257 | 666 | 0,0097 |
| bear_flag | 35 | 249 | 821 | 0,0084 |
| pennant | 12 | 165 | 644 | 0,0099 |
| cup_and_handle | 5 | 87 | 789 | 0,0140 |
| rising_wedge | 2 | 62 | 758 | 0,0149 |
| rounding_bottom | 2 | 43 | 782 | 0,0137 |
| **head_and_shoulders** | 0 | **1** | 659 | 0,0261 |
| inverse_head_and_shoulders | 0 | **0** | 646 | 0,0283 |
| double_top | 0 | **0** | 285 | 0,0360 |
| double_bottom | 0 | **0** | 284 | 0,0280 |
| ascending_triangle | 0 | **0** | 192 | 0,0426 |
| descending_triangle | 0 | **0** | 264 | 0,0337 |
| symmetrical_triangle | 0 | **0** | 6 | 0,0557 |

İlk 12'yi dolduran şablon sayısı: **Katı 4/14 · Orta 7/14 · Esnek 13/14**

**Teşhis:** Formasyonların "eşleşilebilirliği" çok farklı. Bayrak ve takoz gibi
basit geometriler 0,008–0,015 bandında eşleşirken, OBO ve ikili tepe gibi çok
tepeli yapılar en iyi ihtimalle 0,026–0,036 alıyor. **Tek bir global eşik ikisine
birden hizmet edemiyor:** kolay formasyonlara göre ayarlanan orta kademe, zor
formasyonların ilk sayfasını boşaltıyor.

Bu, eşik gevşetilerek "geçirilmedi". Seçenekler ve öneri §Açık Sorular S-2'de.

---

## ADIM 4 — Göz Testi (karar insana ait)

20 sorgu (14 kanonik şablon + 6 serbest çizim) × ilk 12 sonuç, 3×4 grid PNG:
`notebooks/output/goz_testi_*.png`

> Serbest çizimler gerçek fare çizimi değil, kanvas koordinat sistemiyle
> (y aşağı artar) yazılmış polyline'lardır — dosyada açıkça belirtildi. Gerçek
> kullanıcı çizimi F6'da test edilecek.

### 4.1. K-09 doğrulaması — 12 karo 12 farklı olay mı?

| Ölçüm | Sonuç |
|---|---|
| Örtüşen pencere çifti (aynı sembol) | **0** |
| `max_results_per_symbol` ihlali | **0** |
| Ortalama farklı sembol / 12 karo | 12,0 (sonuç dönen sorgularda) |

Post-NMS çalışıyor: hiçbir sorguda aynı grafiğin kaydırılmış kopyası yok.
80 sembollük ilk ölçümde 4 "örtüşen çift" görünmüştü; bunların hepsi IoU < 0,50
olan **farklı** olaylardı (ölçüm eşiği yanlış seçilmişti), tam evrende sıfıra
indi.

### 4.2. Sembol çeşitliliği ve likidite

En sık geçen semboller: WLDUSDT (3), ZECUSDT (3), AVAXUSDT (3), SCUSDT (3),
sonra 2'şer. Tek bir coin'in fraktallarına dönüşme yok. Sonuçlarda delist
edilmiş pariteler de var (MATICUSDT) — likidite filtresi tarihi silmiyor.

### 4.3. ⚠️ Uzunluk dengesi

| Pencere uzunluğu | Sonuç sayısı | Pay |
|---|---|---|
| 24 | 97 | %68 |
| 40 | 31 | %22 |
| 64 | 12 | %8 |
| 100 | 5 | %3 |

K-14 yol-uzunluğu normalizasyonu **uygulanıyor** (kod ve testle doğrulandı),
ama sonuçlar yine de kısa pencerelere kayıyor. İki mekanizma birlikte çalışıyor:

1. Aşama 1 geri çağırma tavanı uzunlukla düşüyor (§1.4: %95 → %80)
2. Kısa pencere daha az nokta içerdiği için 32'ye yukarı örneklenirken
   yumuşuyor ve ideal eğriye daha kolay oturuyor

Bu, "kullanıcı hiçbir zaman uzun formasyon göremez" riskinin (K-14'ün
gerekçesi) tamamen ortadan kalkmadığını gösteriyor. Ölçülen pay %3 (100 bar) —
sıfır değil ama düşük.

### 4.4. Boş dönen sorgular

Orta kademede 20 sorgunun **7'si** hiç sonuç döndürmedi. Bu, §3.1'deki eşik
sorununun göz testindeki karşılığıdır.

### 4.5. Görsel gözlemler (esnek kademe)

Orta kademede 7 sorgu boş döndüğü için göz testi **esnek kademede de** render
edildi: `notebooks/output/goz_testi_esnek_*.png`. Bu kademede 20 sorgunun
20'si de dolu sayfa veriyor (symmetrical_triangle hariç: 6 sonuç), örtüşen
çift 0, sembol çeşitliliği 11–12/12.

**Fincan-kulp (`goz_testi_esnek_cup_and_handle.png`)** — 12 karonun 12'si de
gerçek çanak: dip yuvarlak, sonda kırılım var, hepsi farklı sembol ve farklı
dönem (2021–2026), volatilite %29–150. Bu sayfa "evet, çalışıyor" izlenimi
veriyor.

**OBO (`goz_testi_esnek_head_and_shoulders.png`)** — 12 karonun ~9'u belirgin
omuz-baş-omuz; 3'ü (XLMUSDT, XMRUSDT, MATICUSDT) daha çok "yuvarlak tepe".
Ancak **ilk iki sıra sorunlu**: PAXUSDT (%4 volatilite) ve TUSDUSDT (%5) —
ikisi de **stablecoin**. Z-score, sabitlenmiş bir paritenin %4'lük dalgalanmasını
mükemmel bir OBO'ya dönüştürüyor.

### 4.6. ❌ Stablecoin kirliliği — az ama en görünür yerde

| Ölçüm | Değer |
|---|---|
| İlk-12'lerde stablecoin sonuç | 5 / 240 (%2) |
| Genliği %10'un altında sonuç | 6 / 240 |
| Etkilenen sorgu | 4 / 20 |
| En uç örnek | symmetrical_triangle → %0,1 genlikli eşleşme |

Oran düşük ama **sıralamanın tepesine** yerleşiyor (OBO'da 1. ve 2. sıra),
yani kullanıcının ilk gördüğü şey oluyor. K-10 bunu öngörmüştü; çözüm zaten
mimaride var (`min_amplitude`), sadece **varsayılan olarak kapalı**.

> **Karar gerekiyor:** S-5.

### 4.7. Karar

Görseller üretildi, gözlemler yazıldı. **"Evet, bu çalışıyor" kararı bu
belgede verilmemiştir** — K-18 gereği karar insana aittir.

---

## ADIM 5 — Radar Duman Testi

`mode='live'`, tüm evren (1.165 parite × 4 pencere uzunluğu):

| Şablon | Süre | Sonuç | En iyi skor |
|---|---|---|---|
| head_and_shoulders | 24,3 ms | 12 | 0,0600 |
| cup_and_handle | 23,4 ms | 13 | 0,0389 |
| bull_flag | 23,2 ms | 11 | 0,0224 |

Doğruluk kontrolü ✅: dönen her eşleşmenin `end_idx`'i, o sembolün matristeki
**son penceresine** eşit (K-15 / K-05).

⚠️ **Süre bütçeyi aşıyor: 23 ms, hedef < 10 ms.** Sebep, live modda aday
havuzunun 4 × 1.165 ≈ 4.660 olması ve pre-NMS'in Python döngüsü olması. 80
sembollük ölçekte 3,1 ms'ydi. Seçenekler §Açık Sorular S-4'te.

---

## Performans (gerçek ölçek, 1,92M pencere)

| İşlem | Ölçülen | Bütçe (§15) | Durum |
|---|---|---|---|
| Historical arama (uçtan uca) | **51 ms** (medyan) | < 500 ms | ✅ |
| Aşama 1 (kosinüs, 1M satır) | 40 ms | < 300 ms | ✅ |
| Aşama 2 (DDTW, 1.000 aday) | 8 ms | < 100 ms | ✅ |
| Radar (live) | **23 ms** | < 10 ms | ⚠️ |
| Matris inşası (1d, tam evren) | ~7 dk | dakikalar–saatler | ✅ |

Not: `STAGE1_TOPK`'yi 5.000'den 20.000'e çıkarmak gecikmeyi 51 → 242 ms'ye
çıkarıyor ve `ascending_triangle` için yalnızca 1 sonuç ekliyor — aday havuzunu
büyütmek bu veride kazanç getirmiyor.

---

## Açık Sorular (karar bekliyor)

### S-1 — Trend bir formasyon mu?

Rampa ve neredeyse-düz sorgular her kademeyi geçiyor ve döndürdükleri pencereler
gerçekten monoton. Seçenekler:

1. **Kabul et** — "trend" meşru bir şekildir, kullanıcı düz çizgi çizerse trend
   görsün. (Değişiklik yok.)
2. **Şekil bilgilendiriciliği filtresi** — sorgunun "düzlük"ünü ölç (ör. ikinci
   fark enerjisi) ve eşiğin altındaysa kullanıcıyı uyar: *"Bu çizim bir trend;
   formasyon araması için en az bir dönüş noktası çizin."*
3. **Genlik değil, şekil karmaşıklığı eşiği** — sonuçları değil sorguyu ele.

**Öneri: (2).** Motoru bozmadan, kullanıcıya dürüst uyarı verir; K-18'in
"metrik ölçmüyor, uyduruyor" testine takılmaz çünkü metrik burada doğru ölçüyor.

### S-2 — Tek global eşik yeterli mi?

Orta kademede 14 şablonun 7'si ilk sayfayı dolduramıyor (OBO dahil).
Seçenekler:

1. **Şablon başına eşik** — her şablonun kendi skor dağılımından üç kademe
   türet, JSON'a yaz. Kullanıcı "Katı/Orta/Esnek" görmeye devam eder.
2. **Global eşiği gevşet** (ör. orta = 0,05) — kolay formasyonlarda ilk sayfa
   zayıflar.
3. **Karma** — global eşik + şablon başına ölçek katsayısı.

**Öneri: (1).** Eşiğin şablona bağlı olması K-04'ü ihlal etmez (kural motoru
değil, kalibrasyon verisi); ve zaten her şablonun dağılımı ölçüldü.

### S-3 — Uzun pencere kaybı kabul edilebilir mi?

Aşama 1 geri çağırması 100 barda %80'e, takozlarda %62'ye düşüyor; sonuçların
yalnızca %3'ü 100 barlık. Seçenekler: uzunluk başına ayrı top-K kotası
(ör. her matristen en az N aday), veya kabul.

### S-4 — Radar 23 ms

Seçenekler: (a) live modda pre-NMS'i atla (her sembolde uzunluk başına tek
pencere var, örtüşme yalnızca uzunluklar arası), (b) NMS'i vektörize et,
(c) live için `stage2_topk`'yi düşür, (d) 23 ms'yi kabul et (kullanıcı için
fark edilmez).

**Öneri: (d) şimdilik, (b) F5'te.** 23 ms hâlâ "anında" hissettirir.

### S-5 — Stablecoin ve düşük genlikli sonuçlar

İlk sayfaların tepesine %4–5 volatiliteli stablecoin eşleşmeleri giriyor
(§4.6). Seçenekler:

1. **Varsayılan `min_amplitude`** (ör. %10) — K-10 zaten bu filtreyi tanımlıyor,
   yalnızca varsayılanı kapalı. Tek satırlık değişiklik.
2. **Stablecoin pariteleri evrenden çıkar** — `USDCUSDT`, `TUSDUSDT`,
   `PAXUSDT`, `FDUSDUSDT`, `USD1USDT`, `XAUTUSDT`… Sabit listeye bağlı, bakım
   gerektirir.
3. **Genlik bazlı skor cezası** — K-10'un "açık soru"su (genlik bonusu) buraya
   bağlanır.

**Öneri: (1).** Mimaride zaten var, kullanıcı arayüzde değiştirebilir, hiçbir
kararı ihlal etmez. (2) ayrıca yapılabilir ama tek başına yetmez: düşük
oynaklıklı ölü altcoin'ler de aynı sorunu üretir.

---

## Üretilen çıktılar

```
notebooks/
  01_veri_kontrol.ipynb          bar/boşluk/delist/yarım mum + K-13 sağlık
  02_normalizasyon_gorsel.ipynb  ölçek ve uzunluk değişmezliği, çizim yolu
  03_goz_testi.ipynb             20 sorgu × 12 sonuç grid  🚦
  04_negatif_kontrol.ipynb       skor dağılımı + rampa incelemesi  🚦
  05_esik_kalibrasyon.ipynb      gerçek veri eşikleri + K-11 A/B
  06_radar_duman_testi.ipynb     live mod süre + son pencere doğrulaması
  output/                        50 PNG (orta + esnek kademe)

data/f3/
  ab_stage2.json                 K-11 A/B ham sonuçları
  score_distribution*.json       metrik başına skor dağılımı
  thresholds_all.json            üç metriğin kalibrasyonu
  negative_floors_full.json      anlamsız sorgu tabanları

tools/
  shape_variants.py              formasyon varyantları (dairesellik çözümü)
  ab_stage2.py                   K-11 A/B koşum takımı
  f3_measure.py                  ölçüm kütüphanesi
  build_notebooks.py             notebook üretici/çalıştırıcı
```

---

## Kapı durumu

| Şart | Durum |
|---|---|
| Gerçek veri indirildi ve doğrulandı | ✅ |
| K-11 ölçümle karara bağlandı | ✅ |
| Negatif kontrol (white noise, whipsaw, düz çizgi) | ✅ |
| Eşikler gerçek veriden kalibre edildi | ✅ |
| Göz testi görselleri üretildi | ✅ |
| **"Evet, bu çalışıyor" kararı** | ⏳ **insan onayı bekliyor** |
| Açık sorular S-1…S-4 | ⏳ karar bekliyor |

**F4'e (Outcome Engine) geçilmedi.**
