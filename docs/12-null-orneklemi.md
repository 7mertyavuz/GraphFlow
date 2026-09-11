# F4.11 — Null örneklemi: bulguların bir kısmı zar atışıymış

**Tarih:** 11 Eylül 2026 · **Araçlar:** `tools/null_sensitivity`, `tools/gt_benchmark`, `tools/run_outcomes`
**Önceki:** [11-yeniden-olcum.md](11-yeniden-olcum.md)

---

## Nasıl fark edildi

Evrenden 4 ikiz sembol düşürüldü (K-13.3 — WBTCUSDT, WBETHUSDT, BETHUSDT,
BNSOLUSDT). Beklenen etki küçüktü: 28 hücrede 9.981 eşleşmenin 40'ı ikiz
sembolde. Matris yeniden kurulup bulgular yeniden üretildiğinde ise:

| | önce | sonra |
|---|---|---|
| F4.5 %95'te anlamlı (1d / 4h) | 9 / 12 | **5 / 14** |
| F4.7 replikasyon | 4 hücre | **1 hücre** |
| flama 1d eşleşme sayısı | 569 | **438** |

Dört sembolün 40 eşleşmesi flamadan 131 eşleşme götüremez. Kalan
pencerelerin birebir aynı olduğu doğrulandı (yalnız ikizlerin satırları
düştü). Değişen başka bir şeydi.

## Mekanizma

Arama eşiği sorgunun null dağılımının yüzdeliğidir (F3.5, K-14): "orta"
tolerans %0,25, "katı" %0,05. Null, uzunluk başına **2.000** rastgele
pencereden kuruluyordu — yani "orta" eşik ~5. en küçük değer, "katı" eşik
tek bir değerdi. Bu derinlikte bir sıra istatistiği gürültülüdür.

Hangi 2.000 pencerenin çekildiğini sabit bir tohum, **satır indeksleri**
üzerinden belirler. Matristen ~1.000 satır düşünce indeksler kaydı, aynı
tohum başka pencereler çekti, eşik oynadı ve eşleşme kümesi — dolayısıyla
istatistik — onunla birlikte oynadı. İkizler yalnız tetikleyiciydi.

## Ölçüm 1 — eşleşme sayısı yalnız tohuma ne kadar bağlı

Veri ve motor sabit, **yalnız `NULL_SEED` değişiyor** (6 şablon × 6 tohum);
orta toleransta eşleşme sayısının değişim katsayısı (medyan):

| null örneklemi | 1d | 4h | soğuk arama 1d / 4h |
|---|---|---|---|
| **2.000** (eski) | **0,124** | **0,087** | 234 / 369 ms |
| 10.000 | 0,078 | 0,038 | 384 / 549 ms |
| **20.000** (yeni) | **0,048** | **0,021** | 613 / 770 ms |
| 40.000 | 0,028 | 0,017 | 976 / 1.149 ms |

En uç örnek flama 1d: n = 2.000'de 334 ile 552 eşleşme arasında — aynı
veri, aynı sorgu. Katı toleransta değişim katsayısı 0,24'e çıkıyordu.

## Ölçüm 2 — bulgular yalnız tohuma ne kadar bağlı

`tools/null_sensitivity`: F4.5'in 56 testi, beş farklı null tohumuyla, iki
dilimde. Başka hiçbir şey değişmiyor.

| | n = 2.000 | n = 20.000 |
|---|---|---|
| 1d — %95'te anlamlı hücre | **3 – 12** | 5 – 9 |
| 4h — %95'te anlamlı hücre | **7 – 14** | 8 – 11 |
| 1d — her tohumda anlamlı / yalnız bazılarında | 2 / 14 | 3 / 11 |
| 4h — her tohumda anlamlı / yalnız bazılarında | 4 / 11 | 6 / 7 |
| replikasyon (1d ∩ 4h aynı yön) | 1 – 4 hücre | 1 – 4 hücre |
| **her tohumda replike eden** | `yükselen takoz long 2:1` | `yükselen takoz long 2:1` |
| o hücre 1d'de Bonferroni'yi geçiyor | 4/5 tohum | **5/5 tohum** |

**Okuma.**

- n = 2.000'de "1d'de kaç hücre anlamlı" sorusunun cevabı 3 ile 12
  arasında bir zar atışıydı. Belgelerde dört kez kayda geçen "anlamlı
  hücrelerin kimliği değişti" (veri tazeleme, yapısal filtre, aday havuzu,
  motor değişikliği) gözleminin bir kısmı verinin ya da motorun değil, bu
  gürültünün eseriydi.
- 20.000 gürültüyü yarıya indiriyor ama **sınırdaki hücreleri
  sabitlemiyor**: eşleşme kümesindeki %5'lik oynama, güven aralığı sıfırı kıl
  payı dışlayan bir hücreyi çevirmeye yetiyor. Bu, F4.7'nin "sınırdaki
  bulgu kırılgandır" bulgusunun kendisi — artık motorun kendi gürültüsünden
  ayrılmış hâliyle.
- Her tohumda, iki dilimde ayakta kalan tek şey `yükselen takoz long 2:1`:
  F4.7'nin ilk kez bulduğu hücre. "Replike eden 4 hücre" (F4.10) tek tohumun
  şanslı bir çekilişiydi; replike eden **olgu** tektir.

## Karar

`NULL_SAMPLE_SIZE`: 2.000 → **20.000** (K-14.3).

Bedeli karşılamak için Aşama 2'nin banded DTW çekirdeği yeniden yazıldı
(yerleşim `(band, n)`, argmin yerine karşılaştırma zinciri): 20.000 adayda
167 → 46 ms, çıktı bit düzeyinde aynı — motor parmak izi değişmedi. Böylece
20.000'lik null, eski çekirdekle 2.000'liğin maliyetine yakın. Sıcak arama
değişmez (null önbellekte); kütüphane şablonları açılışta ısıtılır. Serbest
çizimin ilk sorgusu 1d ~0,6 sn, 4h ~0,8 sn.

40.000 değerlendirildi: 1d değişim katsayısını 0,048 → 0,028'e indiriyor,
soğuk aramayı ~1 sn'nin üstüne taşıyor. Getirisi azalan bölgede.

**Reddedilen alternatif — kaskadlı null.** Null'un yalnız alt kuyruğu
gerekiyor; motor zaten kosinüs → DTW kaskadı. Büyük bir örneklemde yalnız
kosinüste en üsttekilere DTW uygulamak ucuz olurdu. Ölçüldü, olmuyor: 20.000
pencerede DTW'nin en küçük 50 değerini kapsamak için kosinüs sırasında
11.067'ye kadar inmek gerekiyor. Kosinüs, DTW'nin alt kuyruğunu
yoğunlaştırmıyor.

## Doğruluk etkisi (ground truth, `tools/gt_benchmark --family all`)

Aynı kod, yalnız null örneklemi farklı:

| zemin | n = 2.000 | n = 20.000 |
|---|---|---|
| sentetik, tohum 2026 | 219/288 | 214/288 |
| sentetik, tohum 7 | 189/288 | 199/288 |
| gerçek piyasa | 198/288 | 211/288 |
| **toplam** | 606/864 | **624/864** |

Doğruluk kötüleşmiyor: toplamda +18 (+2,1 puan), en çok en gerçekçi zeminde
(+13). Tek tek hiçbiri anlamlı değil (288 denemede standart hata ~11).
Dikkat: n = 2.000 sütunu önceki kayıttaki değerlerden (203 / 209 / 209, K-21
eki) 10–20 sonuç sapıyor — aynı gürültü, ground truth ölçümünün kendisinde.
Motor ayarları arasındaki "kazanç/kayıp" kıyasları bundan sonra
n = 20.000'le yapılmalı; n = 2.000'le ölçülen küçük farklar bu gürültünün
içindeydi.

## Açık kalan

- **Sınırdaki hücreler hâlâ oynuyor.** Bulgular sayfası her hücreyi tek bir
  null çekilişiyle gösteriyor. Dürüst gösterim, anlamlılığı tohumlar
  arasında sayan bir kararlılık sütunudur (`tools/null_sensitivity` bu
  ölçümü üretiyor; sayfaya bağlanmadı).
- **Katı toleransta yapısal filtre uçurumu.** OBO katı toleransta tohumların
  bazılarında 12–20, bazılarında 110+ sonuç: hayatta kalan aday
  `STRUCTURE_MIN_SURVIVORS`'ın altına düşünce filtre tümden gevşiyor
  (tasarım gereği, uyarıyla). Daha kesin eşik bunu seyrekleştiriyor ama
  kaldırmıyor.
- **İndeks tabanlı çekiliş.** Null hâlâ satır indeksiyle çekiliyor; veri
  değişince örneklem yeniden karılıyor. 20.000'de bunun etkisi küçük (eşik
  gürültüsü %2–5), ama pencere kimliğiyle (sembol, zaman) çekmek veri
  eklemeyi null'dan bağımsız kılardı.
