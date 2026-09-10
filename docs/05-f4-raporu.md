# GraphFlow — F4 Outcome Engine Raporu

> **Belge türü:** Faz raporu
> **Tarih:** 31 Temmuz 2026
> **Kapsam:** [01-mimari.md](01-mimari.md)
> **Önceki:** [04-f35-raporu.md](04-f35-raporu.md)

Ürünün tacı: *"sonra ne oldu?"*. Sinyal satmıyoruz; **ölçülmüş ve dürüstçe
raporlanmış geçmiş dağılım** sunuyoruz.

---

## Çıkış şartı — geçti ✅

Rastgele pencerelerde (formasyon yok, yalnızca martingale gürültü; 40 sembol ×
600 bar):

| Test | Ölçülen | Teorik null | %95 GA | Sonuç |
|---|---|---|---|---|
| 2:1 başarı | **%34,2** | %33,3 | [%31,4 – %37,0] | null aralık içinde ✅ |
| 1:1 başarı | **%50,6** | %50,0 | [%47,7 – %53,5] | null aralık içinde ✅ |
| Beklenti | **+0,033R** | 0R | [−0,052 – +0,116] | sıfır aralık içinde ✅ |

Bu değerler null'dan anlamlı sapsaydı triple-barrier'da hata olurdu
(lookahead, yanlış ATR penceresi, bar sıralaması). Sapmadı.

> **Not:** Başarı oranı **karara bağlanmış** olaylar (tp veya sl) üzerinden
> ölçülür. Teorik null "hangisine önce çarpılır" sorusunun cevabıdır; zaman
> bariyerinden çıkan olaylar o soruyu yanıtlamaz.

Ayrıca `martingale_ohlc` testinde log getirilerin ortalaması **−σ²/2**'dir:
ortalama 0 olsaydı *fiyat* Itô sürüklenmesiyle yukarı kayar, test null'dan
sapmayı değil o sürüklenmeyi ölçerdi.

---

## 🐞 F4'ün yakaladığı iki veri hatası

İlk koşumda gölge dağılımın beklentisi **+39R** çıktı — imkânsız bir sayı.
Kök sebep aramak, iki ayrı yapısal sorunu ortaya çıkardı:

### 1. Kaldıraçlı tokenlar (47 parite)

`BTCUPUSDT`, `ETHDOWNUSDT`, `SUSHIDOWNUSDT`… Bunlar spot parite değil,
**çürüyen türev ürünlerdir** ve periyodik yeniden fiyatlandırma yaparlar.
Ölçülen tek-bar oranları: `UNIDOWNUSDT` **127.059×**, `LTCDOWNUSDT`
**119.585×**. Evrenden düşürüldü (`is_leveraged_token`).

### 2. Redenominasyon / ticker yeniden kullanımı

Kaldıraçlı token olmayan uç örnek: **`LUNAUSDT`, tek barda 177.400×**. Bu bir
fiyat hareketi değil — Binance ticker'ı **LUNA2 için yeniden kullandı**; aynı
sembol adı altında farklı bir varlık başlıyor.

Ölçülen dağılım (1.146 parite, kaldıraçlı olmayanlar):

| Tek-bar oranı | Sembol | Örnekler |
|---|---|---|
| 3–8× | 38 + 14 | gerçek pump olabilir |
| 8–20× | 6 | STRAX, VIDT, SKY, SNM — hepsi belgelenmiş token swap |
| >20× | 12 | DREP (1:100), COCOS (1:1000), BNX, LUNA |

**Fiyat sürekliliği invariant'ı** eklendi (`PRICE_CONTINUITY_MAX_RATIO = 10`),
zaman sürekliliğiyle aynı muamele:

* **Matris:** sıçrama içeren pencere matrise girmez
* **Outcome:** ileri pencere sıçramada **kesilir** → zorunlu çıkış; sıçramanın
  ötesi ölçülmez

Düzeltme sonrası gölge beklentisi aralığı: **−0,18R … +0,37R** (makul).

> Bu hata sınıfı, F3'ün mikrosaniye hatasıyla aynı ailedendir: hiçbir hata
> mesajı yok, yalnızca sayılar sessizce saçmalıyor. Fark, bu kez saçmalığın
> **görülebilir büyüklükte** olmasıydı.

---

## Gerçek veri sonuçları (1d, 1.067–1.095 parite, 2017-08 → 2026-07)

Tolerans kademesi `medium`'da **sabit** (p-hacking kilidi). **14 şablonun
tamamı** aşağıdadır — "en iyi 3 formasyon" sunumu çoklu karşılaştırma
tuzağıdır.

### 2:1 konfigürasyonu (teorik null %33,3)

| Şablon | N | Beklenti | Net | Başarı | Gölge | Edge | %95 GA | Anlamlı |
|---|---|---|---|---|---|---|---|---|
| descending_triangle | 242 | **+0,295R** | +0,283 | %39,7 | +0,026 | **+0,269** | [+0,086; +0,450] | ✅ |
| falling_wedge | 348 | +0,196R | +0,184 | %35,6 | −0,020 | +0,215 | [+0,070; +0,366] | ✅ |
| ascending_triangle | 132 | +0,179R | +0,165 | %38,6 | +0,170 | +0,009 | [−0,241; +0,267] | — |
| cup_and_handle | 258 | +0,093R | +0,079 | %34,9 | +0,335 | −0,242 | [−0,422; −0,065] | ❌ aleyhte |
| rounding_bottom | 509 | +0,083R | +0,070 | %35,4 | +0,263 | −0,180 | [−0,308; −0,050] | ❌ aleyhte |
| pennant | 397 | +0,083R | +0,073 | %33,8 | +0,167 | −0,084 | [−0,226; +0,054] | — |
| bull_flag | 385 | +0,070R | +0,060 | %32,5 | +0,062 | +0,008 | [−0,137; +0,156] | — |
| bear_flag | 316 | +0,040R | +0,028 | %32,9 | +0,109 | −0,069 | [−0,226; +0,089] | — |
| head_and_shoulders | 228 | +0,015R | +0,005 | %29,8 | −0,054 | +0,069 | [−0,111; +0,249] | — |
| double_bottom | 242 | +0,001R | −0,013 | %31,8 | +0,366 | −0,365 | [−0,545; −0,183] | ❌ aleyhte |
| inverse_head_and_shoulders | 296 | −0,052R | −0,065 | %29,7 | +0,275 | −0,327 | [−0,486; −0,162] | ❌ aleyhte |
| double_top | 251 | −0,066R | −0,075 | %25,1 | −0,176 | +0,111 | [−0,051; +0,277] | — |
| rising_wedge | 252 | −0,100R | −0,113 | %29,8 | +0,249 | −0,349 | [−0,523; −0,178] | ❌ aleyhte |
| symmetrical_triangle | 4 | +0,803R | +0,789 | %50,0 | +0,222 | +0,581 | [−0,720; +1,817] | yetersiz N |

### 1:1 konfigürasyonu (teorik null %50,0)

| Şablon | N | Beklenti | Başarı | Gölge | Edge | %95 GA | Anlamlı |
|---|---|---|---|---|---|---|---|
| descending_triangle | 242 | +0,164R | %57,0 | −0,004 | **+0,169** | [+0,042; +0,293] | ✅ |
| ascending_triangle | 132 | +0,173R | %58,3 | +0,096 | +0,077 | [−0,097; +0,250] | — |
| falling_wedge | 348 | +0,048R | %51,1 | −0,034 | +0,082 | [−0,024; +0,186] | — |
| pennant | 397 | +0,038R | %51,1 | +0,085 | −0,047 | [−0,149; +0,053] | — |
| double_bottom | 242 | +0,003R | %50,0 | +0,170 | −0,167 | [−0,295; −0,039] | ❌ aleyhte |
| cup_and_handle | 258 | −0,006R | %49,6 | +0,171 | −0,177 | [−0,304; −0,051] | ❌ aleyhte |
| bull_flag | 385 | −0,020R | %48,6 | +0,006 | −0,026 | [−0,137; +0,081] | — |
| rounding_bottom | 509 | −0,031R | %48,1 | +0,134 | −0,165 | [−0,254; −0,077] | ❌ aleyhte |
| rising_wedge | 252 | −0,036R | %48,0 | +0,139 | −0,176 | [−0,304; −0,050] | ❌ aleyhte |
| bear_flag | 316 | −0,042R | %47,1 | +0,050 | −0,092 | [−0,207; +0,016] | — |
| double_top | 251 | −0,053R | %45,8 | −0,121 | +0,068 | [−0,057; +0,190] | — |
| inverse_head_and_shoulders | 296 | −0,067R | %46,3 | +0,129 | −0,196 | [−0,312; −0,077] | ❌ aleyhte |
| head_and_shoulders | 228 | −0,088R | %45,2 | −0,055 | −0,033 | [−0,163; +0,098] | — |
| symmetrical_triangle | 4 | +0,500R | %75,0 | +0,087 | +0,413 | [−0,596; +1,069] | yetersiz N |

---

## ⚠️ Çoklu karşılaştırma düzeltmesi

14 şablon × 2 konfigürasyon = **28 test**. %95 ile 28 test yapılırsa şans eseri
~1,4 "anlamlı" sonuç beklenir. Bonferroni düzeltmesiyle (güven düzeyi %99,82):

| Sonuç | %95 | Bonferroni %99,82 |
|---|---|---|
| Anlamlı edge sayısı | 13 / 26 | **8 / 26** |

**Düzeltmeden sağ çıkanlar:**

| Şablon | Konfig | Edge | Bonferroni GA | Yön |
|---|---|---|---|---|
| descending_triangle | 2:1 | +0,303 | [+0,023; +0,590] | **lehte** |
| descending_triangle | 1:1 | +0,190 | [+0,000; +0,378] | **lehte** (sınırda) |
| rounding_bottom | 2:1 | −0,206 | [−0,406; −0,007] | aleyhte |
| rounding_bottom | 1:1 | −0,172 | [−0,316; −0,038] | aleyhte |
| inverse_head_and_shoulders | 2:1 | −0,349 | [−0,584; −0,077] | aleyhte |
| inverse_head_and_shoulders | 1:1 | −0,207 | [−0,378; −0,029] | aleyhte |
| double_bottom | 2:1 | −0,360 | [−0,627; −0,077] | aleyhte |
| rising_wedge | 2:1 | −0,378 | [−0,667; −0,118] | aleyhte |

`falling_wedge` düzeltmeden **sağ çıkamadı** (2:1 edge +0,228, Bonferroni GA
[−0,016; +0,476] sıfırı içeriyor).

---

## Bulgunun dürüst okunuşu

**Tek pozitif iddia: alçalan üçgen.** Her iki konfigürasyonda da, çoklu
karşılaştırma düzeltmesinden sonra bile gölge dağılımı aşıyor (2:1'de
+0,30R). 1:1'de sınırda (alt sınır 0,000) — yani "yön bilgisi var" iddiası
zayıf, "işlem edilebilir senaryoda getiri var" iddiası daha güçlü.

**Beş formasyon gölgesinden anlamlı biçimde KÖTÜ.** Hepsi yükseliş dönüş
formasyonu: çanak dip, ters OBO, ikili dip, fincan-kulp, yükselen takoz.
Gölge beklentileri +0,13 … +0,37R — yani bu formasyonların çıktığı aylarda
**rastgele bir pencere iyi getiri sağlamış**, formasyonun kendisi daha kötü
performans göstermiş.

Bu tam olarak K-12'nin varlık sebebidir. Tüm-geçmiş baseline kullanılsaydı,
çanak dip için "+0,08R beklenti, %35 başarı" yazılır ve **boğa piyasası
formasyonun başarısı sanılırdı**. Zaman-eşleştirmeli gölge, bunun tersini
gösteriyor.

**Kalan sekiz formasyon için ölçülebilir fark yok.** OBO dahil. Bu bir
başarısızlık değil, ölçümün kendisidir; asıl bilimsel değer buradadır.

### Sınırlar

1. Yalnızca **1d** ve yalnızca **long** yönü. Düşüş formasyonları (OBO,
   alçalan üçgen, ayı bayrağı) long varsayımıyla ölçüldü — ayna triple-barrier
   ertelenmiş kapsamda. Alçalan üçgenin pozitif çıkması bu yüzden **ilginç ama
   yorumlanması zor**: düşüş formasyonu sayılan bir şeklin long getirisi.
2. `symmetrical_triangle` N=4 — kullanılamaz (F3.5'te de 5-6 sonuç dönüyordu).
3. Gölge havuzu aynı aydan ve farklı sembolden çekiliyor; **aynı sektör /
   korelasyon** kontrolü yok. Kripto piyasası yüksek korelasyonludur, bu
   gölgenin varyansını olduğundan küçük gösterebilir.

---

## Uygulama notları

### Vektörizasyon

Python döngüsü yok. Olaylar `T = round(0,5 × L)`'ye göre gruplanır, her grup
kendi `(N, T)` matrisini kurar. Bariyer çarpması `argmax` ile bulunur —
`argmax` hiç çarpmayınca da 0 döndüğü için `any()` maskesi zorunludur.
14 şablon × ~300 olay × 20 gölge, uçtan uca **13 saniye**.

### Ele alınan tuzaklar

| Tuzak | Çözüm | Test |
|---|---|---|
| Aynı barda TP+SL | SL önce (muhafazakâr) | ✅ |
| Bariyerin ötesinde açılış (gap) | Çıkış = o mumun `Open`'ı, **her iki yönde** | ✅ ✅ |
| Kısa satır dolgusu | high → −inf, low → +inf | ✅ |
| Delist / veri sonu | **Zorunlu çıkış**, eleme değil (survivorship arka kapısı) | ✅ |
| İleri pencere örtüşmesi | Aynı sembolde ≥ T bar ayrım | ✅ |
| Gölgede otokorelasyon | Ay havuzu **genelinde** tekilleştirme + ayrım | ✅ |
| ATR ısınması | `t₀ ≥ 2 × ATR_PERIOD` | ✅ |
| İşlem maliyeti tabanı | `1×ATR / C₀ ≥ %1` | ✅ |
| Komisyon | `R_net = R_brüt − %0,1 / atr_pct` | ✅ |

Düşen olay sayıları raporlanır (örn. `bull_flag`: 447 eşleşme → 416 bağımsız
olay; 31'i ileri pencere örtüşmesinden düştü).

### Güven aralıkları

Hiçbir sayı GA'sız yayınlanmaz. Beklenti → bootstrap (10.000 yeniden
örnekleme; R sürekli değişkendir, binom GA'sı uygun değil). Başarı oranı →
Wilson. Doğrulama: `n=112, p=%41` → **[%32,4; %50,3]** — belgedeki örnekle
birebir aynı, teorik null %33 aralığın içinde.

---

## Çözülemeyenler / ertelenenler

1. **Short yönü** — ayna triple-barrier yok; düşüş formasyonları long
   varsayımıyla ölçülüyor.
2. **4h** — matrisleri kurulmadı.
3. **Gölge havuzunda korelasyon kontrolü** yok (aynı ay, farklı sembol —
   ama kripto sembolleri birbirine yüksek korelasyonlu).
4. **Kart render'ı** (UI) F5/F6'ya ait; bu fazda yalnızca veri üretildi.

---

## Kart verisi (örnek — descending_triangle, 2:1)

```
Hedef: 2R  ·  Stop: 1R
Beklenti: +0,295R   (net +0,283R, komisyon sonrası)
Başarı:   %39,7     (teorik null: %33,3  ·  gölge dağılım: %2,6 beklenti)
Edge:     +0,269R   %95 GA [+0,086; +0,450]  ·  Bonferroni [+0,023; +0,590]
N = 242 bağımsız olay

ⓘ Bu veriler geçmiş dağılımlardır, kesin bir işlem sinyali değildir.
```
