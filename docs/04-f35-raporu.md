# GraphFlow — F3.5 Temizlik Raporu

> **Belge türü:** Faz raporu
> **Tarih:** 31 Temmuz 2026
> **Kapsam:** [01-mimari.md](01-mimari.md)
> **Önceki:** [03-f3-dogrulama-raporu.md](03-f3-dogrulama-raporu.md)

F3'ün açık bıraktığı beş bulgu (S-1…S-5) kapatıldı. Her adımın öncesi/sonrası
sayıları, K-11'in ikinci ölçümü ve **çözülemeyenler** aşağıdadır.

---

## Özet

| Adım | Konu | Sonuç |
|---|---|---|
| 1 | Sorgu-göreli null kalibrasyonu (S-1+S-2+S-3) | ✅ ölçüldü, kapandı |
| 2 | Sabitlenmiş parite + genlik varsayılanı (S-5) | ✅ 19 parite düştü |
| 3 | Zaman sürekliliği + tazelik invariant'ları | ✅ ikisi de gerçek hata yakaladı |
| 4 | K-11'in zaman ekseninde yeniden ölçümü | ✅ hybrid yine kazandı |
| 5 | Ters şekil negatif kontrolü | ✅ geçti — **DDTW tek başına kalırdı** |
| 6 | Blueprint overlay | ✅ üretildi, bükülme ölçülüyor |
| 7 | Geometrik kısıt katmanı | ⚠️ **ölçülen katkı yok → bağlanmadı** |
| 8 | Radar bütçesi 10 → 50 ms | ✅ ölçülen 30 ms |

---

## Adım 1 — Sorgu-göreli null kalibrasyonu

**Kök sebep (F3'te teşhis edildi):** Skor ölçeği sorgunun yapısal
karmaşıklığına ve pencere uzunluğuna bağlıydı. Rampa 0,0025 · bayrak 0,008 ·
üçgen 0,056 alıyordu; uzun pencerede daha çok yapı → daha çok uyuşmazlık →
sistematik ceza.

**Uygulama:** Arama anında sorgu, **her pencere uzunluğu için** 2.000 rastgele
pencereye karşı skorlanır → o sorgunun, o uzunluktaki null dağılımı. Eşik
mutlak mesafe değil, bu dağılımın yüzdelik dilimidir; **sıralama da**
uzunluk-içi yüzdelik dilime göredir.

| Kademe | Yüzdelik |
|---|---|
| Katı | %0,05 |
| Orta | %0,25 |
| Esnek | %1,5 |

### Sonuçlar (1.165 parite, 1d, ~1,9M pencere)

| Ölçüm | F3 (mutlak eşik) | F3.5 (yüzdelik) |
|---|---|---|
| Orta kademede ilk sayfayı dolduran şablon | **7/14** | **13/14** |
| Sonuçların pencere uzunluğu dağılımı | 24:%68 · 40:%22 · 64:%8 · 100:%3 | **24:%34 · 40:%22 · 64:%30 · 100:%13** |
| OBO'nun orta kademedeki sonuç sayısı | 1 | 355 |
| Historical arama süresi | 51 ms | 67 ms (ilk) / 52 ms (önbellekli) |

**S-2 ve S-3 kapandı.** Şablon başına eşik yazılmadı — serbest çizimde
kalibrasyon verisi olmadığı için o yol ürünün yarısında çalışmazdı.

### ⚠️ Saf yüzdelik eşiğin öldürdüğü şey (ölçülüp düzeltildi)

Yüzdelik eşik **tanımı gereği her sorguya sonuç döndürür**: "en iyi %0,25" her
zaman vardır. Ölçüm: white noise sorguları 40–100, whipsaw 53–68 sonuç dönmeye
başladı. Bu, motorun *"iyi eşleşme yok"* diyebilme yetisini yok eder (§5.5).

**Düzeltme:** İki koşul **birlikte** aranır — aday hem null'un yüzdelik
diliminde olmalı, hem mutlak mesafesi **akıl sağlığı tavanının** (F3'te gerçek
veriden kalibre edilen esnek eşik, hybrid için 0,0836) altında. Sonuç:

| Sorgu | F3.5 sonuç sayısı (orta) |
|---|---|
| white noise | **0, 0, 0, 0** |
| whipsaw | **0, 0, 0, 0** |
| rampa | 339–368 |
| neredeyse düz | 17–492 |

### S-1'in ürün cevabı

Yüzdelik sistem rampanın **sahte üstünlüğünü** zaten kaldırdı: artık rampa,
şablonlarla kıyaslanabilir sayıda (339–368 vs 215–486) sonuç döndüren normal
bir sorgudur. "Trend bir formasyon mudur" sorusu ürün kararı olarak açık
kalıyor, ama ölçüm anomalisi ortadan kalktı.

Uyarı sinyali de ölçümden çıkarıldı — ve **beklenenin tersi yönde** çıktı.
Varsayım "yaygın şekil → dar null" idi; ölçüm bunu çürüttü:

| Sorgu | null medyan/p01 |
|---|---|
| whipsaw | 1,3 |
| white noise | 1,4–1,5 |
| simetrik üçgen | 2,4 |
| OBO | 8,1 |
| bayrak | 15,1 |
| **rampa** | **55,6** |

Dar null "bu şekil çok yaygın" değil, **"korpusta buna benzeyen hiçbir yapı
yok"** demek. Uyarı buna göre yeniden yazıldı (`SearchResult.warning`).

**Maliyet:** Null, (sorgu, uzunluk, metrik, maske) başına sabit → önbelleklendi.
Radar cron'u aynı şablonları 5 dakikada bir çalıştırdığı için ilk çağrı dışında
maliyet yok: live **244 ms → 30 ms**.

---

## Adım 2 — Sabitlenmiş parite + genlik (S-5)

**Yapısal filtre:** Fiyatı geçmişinin ≥%80'inde 1,0 ± %2 içinde kalan parite
evrenden düşer. Gerçek veride **19 parite**: BUSD, USDC, TUSD, PAX, FDUSD,
USDP, USD1, USDE, XUSD, SUSD, UST… ve sarmalanmış varlıklar (**WBTCBTC**,
**RENBTCBTC**, **BTCBBTC** — kendi dayanağına sabitli).

Ayrım keskin: oranı 0,96'nın üstünde 19 sembol var, **0,30 ile 0,96 arasında
hiç yok**. Eşik geniş bir boşluğun ortasında; seçim hassas değil.

**Genlik varsayılanı:** 1d için %15 (ölçüldü: likit pencerelerin %95,2'sini
korur), 4h için %6 (geçici — 4h matrisleri kurulunca ölçülmeli).

**Sonuç:** OBO ilk sayfasında stablecoin kalmadı (F3'te 1. ve 2. sıradaydılar).

---

## Adım 3 — İnvariant'lar: tespit et, doldurma

### 3.1. Zaman sürekliliği

```
pencere matrise girer ⟺ end_time − start_time == (L − 1) × TIMEFRAME_MS
```

Boşluk **ffill ile doldurulmadı**: uydurma bar `True Range = 0` üretir → ATR
yapay olarak düşer → K-16 bariyerleri daralır → sahte TP/SL çarpmaları; ayrıca
şekle düz plato ekler ve `volume = 0` ile K-13 likidite sıralamasını bozar.

Düşen pencere sayısı (1,9M içinde):

| Matris | Düşen |
|---|---|
| 1d_24 | 200 |
| 1d_40 | 317 |
| 1d_64 | 491 |
| 1d_100 | 731 |

Uzunlukla artması beklenen davranış: uzun pencere bir boşluğu yakalama olasılığı
daha yüksek. Toplam kayıp **%0,09** — önemsiz.

### 3.2. Veri tazeliği

`max(open_time)` bugünden `MAX_STALENESS_BARS` bardan fazla geride olamaz.
Ölçüt **evren geneli maksimum**dur; delist edilmiş paritenin son barı tanımı
gereği eskidir (K-13).

**İnvariant hemen gerçek bir şey yakaladı:** 4h verisi 6,5 bar geride. Sebep
yapısal — arşiv günlük dosyaları ~1 gün gecikmeyle yayımlıyor. Eşik zaman
dilimi başına ayrıldı (`1d: 3`, `4h: 12`) ve bunun bir **kaynak kısıtı**
olduğu, tasarım tercihi olmadığı config'e yazıldı: REST erişimi olan bir
ortamda 4h için de 3 hedeflenmelidir.

---

## Adım 4 — K-11'in zaman ekseninde yeniden ölçümü

F3 A/B'sindeki varyantlar zaten monoton zaman bükmesi içeriyordu
(`t' = t^γ + a·sin(2πt)/2π`), ama **bozulma şiddetine göre kırılım yoktu**.
Şimdi var — 64 bar, %2 gürültü, 9 formasyon × 200 örnek:

| Bozulma şiddeti | ddtw | dtw | hybrid | Kazanan |
|---|---|---|---|---|
| 0,5 (hafif) | 0,8960 | 0,9073 | **0,9200** | hybrid |
| 1,0 (orta) | 0,8716 | 0,8951 | **0,9070** | hybrid |
| 1,6 (şiddetli) | 0,8104 | 0,8721 | **0,8816** | hybrid |

En ağır bozulmada **9/9 formasyonda** hybrid kazandı. DDTW'nin açığı şiddetle
**büyüyor** (0,896 → 0,810), en çok takozlarda çöküyor (0,686 / 0,692).

**Sonuç: K-11 kararı değişmedi**, artık zaman ekseninde de sınanmış durumda.

---

## Adım 5 — Ters şekil tuzağı

Beş çift test edildi (çanak↔OBO, ikili dip↔ikili tepe, OBO↔ters OBO,
düşen↔yükselen takoz, boğa↔ayı bayrağı). Aktif metrikle (hybrid) **hepsi
geçti**.

### 🔎 Beklenmeyen bulgu — DDTW tek başına takoz yönünü ayırt edemiyor

| Metrik | düşen ↔ yükselen takoz | Esnek eşik | Sonuç |
|---|---|---|---|
| **ddtw** | **0,0146** | 0,0456 | **eşleşme sayar** ❌ |
| dtw | 2,2841 | 0,1097 | eler ✅ |
| hybrid | 1,1494 | 0,0836 | eler ✅ |

Türev, iki şekli ayıran şeyi — trend bileşenini — sabite indirger; geriye kalan
salınım her iki takozda neredeyse aynıdır. Bu, **yön hatası** üretir: motor
yükseliş formasyonu ararken düşüş formasyonu döndürür.

K-11 için Adım 4'ten bağımsız ikinci bir kanıt. Test
(`test_ddtw_alone_confuses_wedge_direction`) varsayılan DDTW'ye çevrilirse
bedelin ne olduğunu kayıt altında tutar.

---

## Adım 6 — Blueprint overlay

Her göz testi karosuna iki katman bindirildi:

* **soluk kesikli** — kanonik şablon (*"aradığın şey"*)
* **kırmızı** — DTW hizalama yoluyla bükülmüş şablon (*"motor bunu buna hizaladı"*)

Bükülme miktarı (yolun köşegenden ortalama sapması) etikete yazılıyor.
OBO ilk 12'sinde ölçülen: **0,6 – 1,4 bar** — düşük, yani eşleşmeler ağır
zaman bükmesiyle kurulmuş değil.

**Filtreye çevrilmedi** (kanıt biriksin). Çıktılar:
`notebooks/output/goz_testi_blueprint_head_and_shoulders.png`,
`…_cup_and_handle.png`

---

## Adım 7 — Geometrik kısıt katmanı: ⚠️ bağlanmadı

Mekanizma **uygulandı**: kural koda değil şablon meta-verisine yazılır
(`constraints` alanı), tek genel değerlendirici `engine/search/constraints.py`,
çapalar DTW hizalama yolundan okunur. Böylece K-04 korunur — formasyon başına
`if-else` yok. Kısıtsız şablon hiçbir ek filtreden geçmez.

OBO ve ikili tepe/dip için çapalar kanonik şeklin dönüş noktalarından türetildi
(OBO: tepeler 7/16/24, dipler 10/21).

**Ama karar kuralı uygulandı:** *"Yüzdelik skorlama yuvarlak tepeleri zaten
eliyorsa filtre eklenmez."*

| Sorgu | (a) yalnız yüzdelik | (b) ilk kısıt kümesi | (b') + belirginlik kuralları |
|---|---|---|---|
| head_and_shoulders | 5/12 yapısal geçerli | 5/12 | **6/12** (aday havuzunun %40'ı kaldı) |
| double_top | 1/12 | 2/12 | **2/12** (%30 kaldı) |

İlk kısıt kümesi **eksikti** ve ölçüm bunu ortaya çıkardı: "orta nokta iki
yandan yüksek + iki ara nokta eşit seviyede" kuralını **parabol de sağlıyor**.
OBO'yu yuvarlak tepeden ayıran şey omuz **belirginliği**dir — omuzların komşu
diplerin üstünde durması. Kural eklendi (`level_order [10,7] "<"` ve
`[21,24] "<"`), ölçüm tekrarlandı: katkı 5/12 → 6/12.

**+1/12 kazanç için aday havuzunun %60'ını atmak yeterli gerekçe değil.**
Katman motora **bağlanmadı**; modül, şablon meta-verisi ve testleri yerinde
duruyor, kanıt gelirse tek satırla devreye alınabilir.

> **Dürüstlük notu:** Bu ölçümün *aleti* şüpheli. Otomatik yapısal ölçüt
> OBO sayfasına 5/12 verirken görsel okuma ~10/12 diyor; gürültülü gerçek
> pencerelerde "en yüksek 3 tepe" seçimi yanlış tepeleri seçebiliyor.
> Yani sonuç "kısıt katmanı işe yaramaz" değil, **"bu ölçütle katkı
> gösterilemedi"**. Yeniden açılacaksa önce ölçüt düzeltilmeli.

Yuvarlak tepe sızıntısı (XMRUSDT, XLMUSDT) **devam ediyor** — F3'te
işaretlenen boyun çizgisi sorunu kapanmadı.

### Fincan-kulp

Ayrı ve daha basit sorun, çözüldü:

| Ölçüm | Değer |
|---|---|
| Fincan ↔ çanak sonuç kümesi örtüşmesi | Jaccard **0,03** (zaten ayrık) |
| İlk 12'de kulp taşıyan pencere (derinlik 0,30) | 4/12 |
| Derinlik 0,45 / **0,60** / 0,80 | 5/12 / **9/12** / 12/12 |

Sığ kulp 32 noktada gerçek gürültünün altında kalıyordu. Kanonik derinlik
**0,30 → 0,60**. Komşulara çarpmıyor: çanak mesafesi 0,0188 → 0,0405, ikili dip
0,1510 → 0,1791 (ikisi de **uzaklaşıyor**). Birleştirme gerekmedi.

---

## Adım 8 — Radar bütçesi

Bütçe 500 sembol varsayılarak yazılmıştı; evren 1.165'e çıktı ve doğrusal
ölçekleniyor. **10 ms → 50 ms** (docs/01-mimari.md §15). Ölçülen: **30 ms**
(önbellekli), 244 ms (ilk çağrı, null hesabı). Radar sonuçları cron ile
önceden hesaplandığı için kullanıcı önbellekli yolu görür.

Optimizasyon yapılmadı — kullanıcının algılayamayacağı gecikme için
optimizasyon, K-01'de reddedilen hatanın aynısı.

---

## Çözülemeyenler

1. **Yuvarlak tepe sızıntısı** (OBO ilk 12'sinde 2 karo). Geometrik kısıt
   katmanı hazır ama ölçülen katkı gösteremedi; ölçüm aleti düzeltilmeden
   bağlanması "kanıtsız kural" olur.
2. **Trend bir formasyon mu?** (S-1) Ölçüm anomalisi kapandı, ürün kararı açık.
3. **4h zaman dilimi** ölçülmedi: matrisleri kurulmadı, genlik varsayılanı
   (%6) hesaplanmış değil tahmindir, veri arşiv gecikmesi yüzünden bayat.
4. **Ölçek-eşitlenmiş hybrid** (z-skor harmanı) denenmedi; düz ortalama ham
   DTW ağırlıklı çalışıyor.

---

## Çıkış şartı

Yüzdelik skorlama + blueprint overlay ile üretilmiş iki görsel:

```
notebooks/output/goz_testi_blueprint_head_and_shoulders.png
notebooks/output/goz_testi_blueprint_cup_and_handle.png
```

**Karar (insan):** _______________
