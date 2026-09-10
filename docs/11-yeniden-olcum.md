# F4.10 — Motor değişti, bulgular yeniden ölçüldü

**Tarih:** 10 Eylül 2026 · **Araçlar:** `tools/run_outcomes`, `tools/f46_proxy_test`
**Önceki:** [10-formasyon-denetimi.md](10-formasyon-denetimi.md)

---

## Neden

9 Eylül'de üç motor değişikliği bağlandı: kararlılık kapısı (K-20), zarf
filtresi (K-21) ve belirginlik ayna düzeltmesi. Üçü de **istatistiğe giren
pencere kümesini** değiştirir. Bulgu dosyaları (`data/f3/*.json`) ise
8 Eylül 23:18'de, eski motorla üretilmişti. "Bulgular" sayfası bir gün
boyunca başka bir motorun istatistiğini gösterdi ve bunu söyleyecek hiçbir
mekanizma yoktu.

Bu rapor iki şey yapar: bulguları bugünkü motorla yeniden üretir ve bu
sınıf bayatlığın bir daha sessiz kalmamasını sağlar.

> **p-hacking değil.** Üç motor değişikliği de ground truth formasyon
> doğruluğuyla (`tools/gt_benchmark`) seçildi; hiçbiri sonuç istatistiğine
> bakılarak seçilmedi. Aşağıdaki tablolar bir **sonuç**tur, seçim kriteri
> değildir.

---

## Örneklem ne kadar değişti

İstatistiğe giren tekil olay sayısı (long 2:1):

| şablon | 1d eski → yeni | 4h eski → yeni |
|---|---|---|
| yükselen üçgen | 30 → **97** | 89 → **272** |
| alçalan üçgen | 50 → 108 | 119 → 301 |
| flama | 317 → **523** | 543 → **932** |
| yükselen takoz | 121 → 171 | 369 → 536 |
| ikili tepe | 60 → 95 | 152 → 266 |
| ikili dip | 57 → 76 | 143 → 242 |
| simetrik üçgen | 63 → 51 | 128 → 193 |
| düşen takoz | 100 → 73 | 181 → 133 |
| OBO | 49 → 53 | 117 → 105 |
| ters OBO | 43 → 39 | 130 → 125 |
| bayraklar, çanak dip | değişmedi | değişmedi |

Eğim ailesinde örneklem 2–3 katına çıktı — kararlılık kapısı artık gerçek
formasyonları elemiyor (K-20). Dönüş ailesi neredeyse aynı.

---

## F4.5 — ay-bloklu bootstrap, 56 test

| | 1d eski | 1d yeni | 4h eski | 4h yeni |
|---|---|---|---|---|
| %95'te anlamlı | 8 | 9 | 10 | 12 |
| Bonferroni'den geçen | 2 | **1** | 0 | 0 |

**Bonferroni'yi geçen hücrelerin kimliği değişti** — dördüncü kez:

| | 1d Bonferroni |
|---|---|
| eski motor | ikili dip long 2:1 · ters OBO long 2:1 |
| yeni motor | yükselen takoz long 2:1 |

Aynı veri, aynı yöntem; yalnız "hangi pencere o formasyon sayılır"
değişti ve anlamlılık sınırındaki hücreler yer değiştirdi. Bu, F4.7'nin
"sınırdaki bulgu kırılgandır" bulgusunun dördüncü tekrarıdır (önceki üçü:
veri tazeleme, yapısal filtre, aday havuzu).

---

## F4.7 — zaman dilimi replikasyonu

1d ve 4h'de **aynı yönde** %95'te anlamlı hücreler:

| eski motor (2) | yeni motor (4) |
|---|---|
| ikili dip long 2:1 | flama short 2:1 |
| flama short 2:1 | yükselen takoz long 2:1 |
| | yükselen takoz short 2:1 |
| | yükselen takoz short 1:1 |

Dört hücre dört bulgu değildir. Üç yükselen takoz hücresi **tek bir
olgunun** üç yüzüdür: takozdan sonra fiyat düşer (long kaybeder, short
kazanır) — ders kitabının söylediği yön. Bağımsız olarak sayılabilecek iki
aday kalıyor: **yükselen takozun düşüş eğilimi** ve **flama short 2:1**.

Bonferroni'yi iki dilimde birden geçen hücre **yoktur**.

---

## F4.6 — vekil testi, düzeltilmiş

### Test yanlış şeyi sınıyordu

F4.6'nın sorusu: F4.5'te short yönde anlamlı çıkan formasyonların etkisi
şekilden mi, yoksa "yakın zamanda çok yükseldi" momentum tersine
dönüşünden mi geliyor? Hedef listesi bu **tanımla** yazılmıştı ama
**değeri** elle girilmişti:

```python
TARGET_TEMPLATES = ["rising_wedge", "inverse_head_and_shoulders",
                    "rounding_bottom", "cup_and_handle", "double_bottom"]
```

Motor değişince F4.5'in anlamlı kümesi değişti, liste değişmedi. Sonuç:
**iki dilimde replike eden flama short 2:1 vekil testine hiç girmedi.**
Liste artık güncel F4.5 ölçümünden hesaplanıyor; bugünkü değeri:
ikili tepe · OBO · flama · yükselen takoz.

İki gizli hata daha:

- `apply_bonferroni` şablon listesini ikinci geçişe **iletmiyordu**. Liste
  sabitken zararsızdı; türetilince ikinci geçiş başka bir listeyle
  koşabilirdi.
- F4.6 **hiç 4h'de koşulmamıştı** — projenin kendi replikasyon kuralına
  aykırı. Artık `--timeframe` var.

### 1d sonucu (birincil bant ±0,25σ, 2:1)

| şablon | standart gölge | eşleştirilmiş gölge | %95 | Bonferroni |
|---|---|---|---|---|
| yükselen takoz | +0,270 [+0,059; +0,539] ✓ | +0,030 [−0,218; +0,316] | · | · |
| OBO | +0,165 [−0,340; +0,654] | +0,054 [−0,378; +0,453] | · | · |
| ikili tepe | −0,452 | **−0,461** [−0,805; −0,089] | ✓ | · |
| flama | +0,140 | **−0,128** [−0,239; −0,015] | ✓ | · |

1d'de iki şablon eşleştirmeden sonra %95'te anlamlı kalıyor. Eski
sonucun manşeti — *"tüm bulgular momentum vekilidir"* — bu tabloyla
**söylenemez**. Ama ikisinin de tuhaflığı var: ikili tepede etki
eşleştirmeyle hiç değişmiyor (−0,452 → −0,461, yani hiçbir zaman momentum
vekili değildi) ve **ders kitabının tersi yönde**; flamada işaret dönüyor.
Birincil bantta hiçbiri Bonferroni'yi geçmiyor.

### 4h replikasyonu

| şablon | 1d eşleştirilmiş | 4h eşleştirilmiş | 4h N |
|---|---|---|---|
| ikili tepe | −0,461 ✓ | **−0,006** [−0,255; +0,270] | 266 |
| flama | −0,128 ✓ | **+0,017** [−0,090; +0,133] | 932 |
| yükselen takoz | +0,030 | +0,083 | 536 |

**Hiçbiri replike etmiyor.** İkili tepe 4h'de sıfır — ve 4h örneklemi 1d'nin
~3 katı (266'ya karşı 95). Flama 4h'de standart gölgeyle anlamlı (+0,169),
eşleştirince eriyor (+0,017): momentum vekilinin ders kitabı örneği.

Replike eden tek şey vekil **deseninin kendisi**: yükselen takozun short
etkisi standart gölgeyle iki dilimde de anlamlı (1d +0,270 · 4h +0,185),
eşleştirilmiş gölgeyle iki dilimde de eriyor (1d +0,030 · 4h +0,083).
F4.7'nin replike eden olgusu şekil değil, momentumdur — ve bunu iki dilimde
gösteren ilk ölçüm budur.

---

## Sonuç

| aşama | eski motor | yeni motor |
|---|---|---|
| F4.5 %95 (1d / 4h) | 8 / 10 | 9 / 12 |
| F4.5 Bonferroni (1d / 4h) | 2 / 0 | 1 / 0 |
| F4.7 replikasyon | 2 hücre | 4 hücre (2 bağımsız olgu) |
| F4.6 eşleştirmeden sonra, 1d · 2:1 | 0/5 (bayat liste) | 2/4 (%95) · 0/4 (Bonferroni) |
| F4.6 eşleştirmeden sonra, 1d · 1:1 | 1/5 (bayat liste) | 1/4 (%95) · 0/4 (Bonferroni) |
| F4.6 eşleştirmeden sonra, **iki dilimde** | ölçülmedi | **0/8** |

**Projenin manşeti ayakta: iki zaman diliminde de ön-getiri eşleştirmeli
gölgeden sağ çıkan bir şekil etkisi yok.** Değişen şey, bu cümlenin artık
doğru hedef kümesiyle ve iki dilimde **sınanmış** olması. Eski hâli bayat
bir listeyi, tek dilimde sınıyordu ve aynı cümleyi kurmak için yeterli
değildi.

---

## Bir daha sessiz kalmasın: köken kaydı

`engine/fingerprint.py`, örneklemi belirleyen motor davranışının parmak
izini üretir. **Config değil davranış**: ayna düzeltmesi hiçbir sabiti
değiştirmemişti, yalnız bir fonksiyonun gövdesini; sabitlerin anlık
görüntüsü onu göremezdi. Filtre katmanları ve Aşama 2 sabit girdilerde
çalıştırılıp çıktı özetlenir.

İki yönde doğrulandı:

| karşılaştırma | parmak izi | beklenen |
|---|---|---|
| ayna düzeltmesinden önce / sonra | `6e2d1c54…` ≠ `cb49511d…` | yakalamalı ✓ |
| vektörizasyondan önce / sonra | `cb49511d…` = `cb49511d…` | susmalı ✓ |

İkinci satır birincisi kadar önemli: yanlış alarm veren bir bayatlık
kontrolü ilk hafta içinde görmezden gelinmeye başlanır.

Ölçüm araçları artık her tablonun yanına köken yazar (parmak izi,
`data_as_of`, üretim zamanı). `/api/findings` her tabloyu bugünkü motorla
karşılaştırır ve `stale` bayrağı taşır; tablo var ama köken yoksa durum
**"bilinmiyor"**dur, asla "güncel" değil. Arayüz uyarıyı ve köken kartını
gösterir.

Korpusun büyümesi parmak izine **girmez** — o "başka bir motor" değil "daha
yeni veri" demektir ve `data_as_of` olarak ayrıca raporlanır.

### Veriden türetilen metinler

API'de sabit yazılmış üç açıklama veriyle çelişiyordu ve düzeltildi:

| metin | gerçek |
|---|---|
| "Replike eden tek formasyon yükselen takoz" | flama da replike ediyor |
| "Beş şablonun beşinde de edge eriyor" | hedef kümesi değişti |
| "Bonferroni çoğul test düzeltmesi (m=52)" | ölçüm 56 test sayıyor |

Üçü de artık ölçüm dosyasından üretiliyor. Yöntem metni de bir sayıdır.

---

## Yeniden üretme

```bash
python -m tools.run_outcomes --timeframe 1d
python -m tools.run_outcomes --timeframe 4h --out-suffix _4h
python -m tools.f46_proxy_test                       # 1d, hedefler F4.5'ten
python -m tools.f46_proxy_test --timeframe 4h \
    --templates double_top head_and_shoulders pennant rising_wedge
```

Toplam süre ~4 dakika. Motor her değiştiğinde koşulmalıdır; koşulmazsa
"Bulgular" sayfası bunu söyler.

---

## Ek: değişmezlik taraması ve köken mekanizmasının ilk gerçek kullanımı

CONTRIBUTING.md'deki "şekil okuyan her fonksiyonun değişmezlik testi olmalı"
kuralı, ayna hatasından sonra yalnız belirginlik için uygulanmıştı. Tüm
fonksiyonlara uygulandı (2.000 rastgele pencere):

| fonksiyon | ayna | dikey çevirme |
|---|---|---|
| `prominent_extrema` | %0 | %0 |
| `structural_signature` | %0 | **%50,2** |
| `envelope_signature` | %0 | %0 |
| Aşama 2 · ham DTW | 3e-16 | 0 |
| Aşama 2 · DDTW | sıra korel. 0,92–0,97 | 0 |

**Yapısal imza — hata, düzeltildi.** Baskın taraf eşitlikte (tepe sayısı =
dip sayısı) her zaman tepeleri seçiyordu; tutarsızlıkların 1004/1004'ü
eşitlikteydi. Yükselen üçgenin dikey çevrilmişi alçalan üçgenin ta
kendisidir, ama motor birini yatay tarafından (%36), ötekini eğimli
tarafından (%81) okuyordu. Artık eşitlikte daha belirgin uç kazanır;
belirginlikler de eşitse baskın taraf yoktur ve imza uydurulmaz.

Ground truth'ta bire bir aynı (202/288). Bulgulara etkisi yalnız simetrik
üçgende: kararlılığı %95 → %84, kapı kapandı, örneklem 1d 51 → 119, 4h
193 → 450. Anlamlı hücre kümeleri **iki dilimde de değişmedi**; bütün
aşama sayıları aynı.

**DDTW — özellik, değiştirilmedi.** Keogh–Pazzani türev tahmincisi yarım
adım geriye kaymış. K-11'e açık soru olarak yazıldı; metrik ve eşik
kalibrasyonunu değiştireceği için karar ölçümle ve onayla verilecek.

**Köken mekanizması ilk kez gerçekten çalıştı.** Düzeltme hiçbir sabiti
değiştirmedi; parmak izi yine de değişti (`cb49511d` → `21d4d9ba`) ve
dört tablo kendiliğinden *"Motor değişti (sabitler aynı — bir filtre ya da
metrik kodu değişmiş)"* olarak işaretlendi. Yeniden üretildiler (~4,5 dk);
köken dört tabloda da "bugünkü motor".
