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
(+13). Not: ground truth korpusları uzunluk başına ~19.000 pencere (64
sembol × 900 bar / adım 3); n = 20.000'de null **tüm havuzdur**. Kıyas bu
yüzden "2.000'lik örneklem vs tüm havuz"dur — ve pencere kimliğiyle çekiliş
bu korpuslarda sonucu değiştirmez (ölçüldü: 214 / 199 / 211, aynı). Tek tek hiçbiri anlamlı değil (288 denemede standart hata ~11).
Dikkat: n = 2.000 sütunu önceki kayıttaki değerlerden (203 / 209 / 209, K-21
eki) 10–20 sonuç sapıyor — aynı gürültü, ground truth ölçümünün kendisinde.
Motor ayarları arasındaki "kazanç/kayıp" kıyasları bundan sonra
n = 20.000'le yapılmalı; n = 2.000'le ölçülen küçük farklar bu gürültünün
içindeydi.

## Açık kalan

- ~~**Sınırdaki hücreler hâlâ oynuyor.**~~ **Bağlandı:** Bulgular sayfasında
  "tohum kararlılığı" tablosu — 56 testin her biri için 1d ve 4h'de kaç
  çekilişte %95'te / Bonferroni'de anlamlı ve kaç çekilişte replike ettiği,
  yayımlanan edge ve GA'nın yanında. F4.7 aşamasının metni tek-çekiliş
  sayısının yanına her çekilişte replike edenleri ekler. Ölçüm
  `python -m tools.null_sensitivity` ile üretilir; köken motor parmak
  iziyle denetlenir, motor değişirse tablo "bayat" işaretlenir.
- **Katı toleransta yapısal filtre uçurumu.** OBO katı toleransta tohumların
  bazılarında 12–20, bazılarında 110+ sonuç: hayatta kalan aday
  `STRUCTURE_MIN_SURVIVORS`'ın altına düşünce filtre tümden gevşiyor
  (tasarım gereği, uyarıyla). Daha kesin eşik bunu seyrekleştiriyor ama
  kaldırmıyor.
- ~~**İndeks tabanlı çekiliş.**~~ **Çözüldü:** null artık pencere
  kimliğiyle çekiliyor (`engine/search/null_sample.py`, alt-k örneklemesi:
  her pencereye `(symbol_id, end_time, uzunluk, tohum)`'dan sabit bir
  anahtar, örneklem en küçük k anahtar). Ölçüm — havuzdan rastgele 4
  sembol çıkarılınca:

  | | null örnekleminden kalan | öteki sembollerin eşleşme sayısı değişimi |
  |---|---|---|
  | 1d, satır indeksi (eski) | **%11,4** | medyan %3,3 · en çok **%18** |
  | 1d, pencere kimliği (yeni) | **%100** | medyan %0,0 · en çok %1,0 |
  | 4h, satır indeksi (eski) | **%1,6** | medyan %2,4 · en çok %3,5 |
  | 4h, pencere kimliği (yeni) | **%100** | medyan %0,3 · en çok %0,4 |

  Eski yöntem 4 sembol düşünce örneklemin neredeyse tamamını yeniden
  çekiyordu. İkizler düştüğünde bulguların değişmesinin mekanizması buydu;
  artık bir sembolü evrenden çıkarmak ya da veri eklemek null'u yalnız
  değişen pencereler kadar oynatır. Çekiliş yöntemi motor parmak izine de
  girdi — girmeseydi bu değişiklik bütün sonuçları değiştirip bulguları
  "güncel motor" diye göstermeye devam ederdi (üçüncü kapsama deliği).

  Yeni çekilişle bulgular yeniden üretildi (başka çekilişler, aynı
  büyüklük): 1d'de 6 hücre %95'te, 1'i Bonferroni'de (yükselen takoz long
  2:1, edge −0,404R [−0,824; −0,006]); 4h'de 7 / 1 (flama short 2:1). Beş
  tohumda: 1d 4–12, 4h 7–11 anlamlı hücre; yükselen takoz long 2:1 **5/5**
  tohumda iki dilimde replike ediyor, 1d'de 4/5 tohumda Bonferroni'yi
  geçiyor; flama short 2:1 3/5 tohumda replike ediyor. Beş tohum da bir
  örneklemdir — aralıkların kendisi kaba.
