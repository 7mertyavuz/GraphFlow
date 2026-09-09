# F4.9 — Formasyon denetimi: sonuçlar gerçekten O formasyon mu?

**Tarih:** 8 Eylül 2026 · **Araç:** `tools/formation_audit`
**Korpus:** 4h · 1.097 sembol · 11,6M pencere

---

## Soru

Kullanıcı şikâyeti ölçülebilir bir soruya indirgenebilir: *ilk sayfadaki
sonuçların kaçı gerçekten aranan formasyon?* Bu soru daha önce **4 formasyon
için** yanıtlanmıştı (OBO, ters OBO, ikili tepe, ikili dip). Kütüphanede 14
formasyon var ve yapısal filtre hepsine uygulanıyordu — yani filtrenin
etkisi üçte iki oranında **ölçülmemişti**.

Bu rapor denetimi 12 formasyona çıkarır ve filtreyi açık/kapalı karşılaştırır.

---

## Denetçi

Denetçi motorun mekanizmasını kullanmaz — kullansaydı motoru kendisiyle
sınamış olurduk. İki bağımsız aile:

**Uç ailesi (dönüşler).** 32 noktalık z-score'lu vektörde belirginlik
tabanlı tepe/dip çıkarır, formasyon tanımını doğrudan uygular: OBO = 3
belirgin tepe · ortadaki en yüksek · dış ikisi birbirine yakın.

**Zarf ailesi (üçgen · takoz · flama · bayrak).** Uç *sayısına hiç bakmaz*.
Dokunuş noktalarından üst ve alt zarfa regresyon çeker, eğimleri
karşılaştırır: yükselen üçgen = yatay direnç (|eğim| ≤ 0,6) + yükselen
dipler (eğim ≥ 1,0) + daralan genlik.

### Denetçinin kendisi denetlendi

| | |
|---|---|
| çapraz tablo | 12 denetim × 14 kanonik şekil |
| köşegen | tam — her denetim kendi şeklini kabul eder |
| köşegen dışı kabul | **0** |

`python -m tools.formation_audit --cross` (veri gerekmez)

Her şeye "evet" diyen bir denetçi sonuçların %100'ünü doğru ilan eder ve
hiçbir şey ölçmez. İlk yazımda köşegen dışında **4** kabul vardı ve ikisi
gerçek tanım belirsizliğiydi:

- Ters OBO, "iki yaklaşık eşit tepe + aralarında dip" tanımını harfiyen
  sağlıyor (boyun çizgisinin iki ucu) → ikili tepe sayılıyordu.
- Yükselen üçgen de sağlıyor (yatay dirence iki dokunuş).

Ayrımı **belirginlik üstünlüğü** yaptı: ikili tepede tepeler diplerden
belirgin (2,79 / 2,32), ters OBO'da tersi (0,87 / 3,37), yükselen üçgende
berabere (2,64 / 2,64). Bu koşul eklendikten sonra köşegen dışı sıfırlandı.

> **Düzeltme.** Bu sıkılaştırma, daha önce raporlanmış "48/48 = %100"
> rakamını değiştiriyor. O rakamın bir kısmı tanım belirsizliğiydi: ilk
> 12'de ikili tepe sayılan bazı pencereler aslında yükselen üçgendi.
> Sıkı denetçiyle dönüş ailesi ilk 50'de **197/200 = %99**.

### Zarf dokunuşları pencerenin İÇİNDEN alınır

Uçları saymak simetrik üçgeni **ters** okuyordu:

| | alt zarf eğimi | okuma |
|---|---|---|
| uçlar dahil | −0,47 | düşen dipler ❌ |
| yalnız iç noktalar | **+2,18** | yükselen dipler ✅ |

Pencerenin ilk ve son barı bir dönüş noktası değil, verinin kesildiği yerdir.

---

## Sonuç: ilk 50'nin kaçı gerçekten o formasyon

| şablon | filtre AÇIK | filtre KAPALI |
|---|---|---|
| omuz baş omuz | **50/50** | 10/50 |
| ters omuz baş omuz | **50/50** | 11/50 |
| ikili tepe | **48/50** | 12/50 |
| ikili dip | **49/50** | 23/50 |
| **dönüş ailesi** | **197/200 · %99** | **56/200 · %28** |
| yükselen üçgen | 17/50 | 18/50 |
| alçalan üçgen | 13/50 | 15/50 |
| simetrik üçgen | 33/50 | 32/50 |
| yükselen takoz | 26/50 | 30/50 |
| düşen takoz | 32/50 | 29/50 |
| flama | 5/50 | 7/50 |
| boğa bayrağı | 32/50 | 34/50 |
| ayı bayrağı | 37/50 | 35/50 |
| **eğim ailesi** | **195/400 · %49** | **200/400 · %50** |
| genel | 392/600 · %65 | 256/600 · %43 |

`cup_and_handle` ve `rounding_bottom` **denetimsizdir** — ikisi de eğrilikle
tanımlanır, ne uç düzeni ne zarf eğimi onları ayırt eder. Denetimsiz
olduklarını yazmak, uydurma bir denetim yazmaktan iyidir.

---

## İki bulgu

### 1. Yapısal filtre dönüşlerde belirleyici, eğim tabanlılarda etkisiz

%28 → %99 ile 400'de 5 fark aynı tabloda duruyor. Mekanizma bunu zaten
söylüyordu: imza **uç düzenini** okur. Yükselen üçgeni tanımlayan şey uç
düzeni değil eğimdir; imza o formasyon hakkında bilgi taşımaz, dolayısıyla
ne yardım eder ne zarar.

Filtre eğim tabanlılarda **zararlı değil**. İlk ölçüm ilk 12 sonuçla
yapıldığında alçalan üçgende 3'e 7'lik bir "zarar" görünüyordu; hücre başına
12 denemede beklenen gürültü buydu ve n = 50'de kayboldu. Bu yüzden
**kararlılık kapısı bağlanmadı** (K-19 emsali: ölçülmüş, net katkısı yok,
bağlanmıyor).

### 2. Eğim tabanlı formasyonlarda motor ~%50'de — ama sebebi sanılan değil

Bu rapor bir başarı ilanı değil. Dönüş formasyonları çözüldü; üçgen, takoz
ve özellikle **flama (5/50)** çözülmedi.

İlk açıklama "DTW'nin trend çizgisi diye bir kavramı yok, o hâlde zarf
eğimlerini elemede kullanalım"dı. Ölçüldü ve **yanlış çıktı** — aşağıdaki
bölüm.

---

## İmza kararlılığı — ölçüldü, filtre olarak bağlanmadı, rapora bağlandı

Sorguya σ = 0,10 gürültü eklendiğinde imzanın hayatta kalma oranı (128 çekim):

| | |
|---|---|
| yuvarlak dip 100 · OBO 97 · ikili tepe 97 · ters OBO 96 | **sağlam** |
| boğa bayrağı 94 · ayı bayrağı 92 · ikili dip 91 · fincan 91 | **sağlam** |
| düşen takoz 80 · alçalan üçgen 70 · simetrik üçgen 61 | kararsız |
| yükselen takoz 59 · yükselen üçgen 33 · flama 23 | kararsız |

İki küme arasındaki %80–%91 bandı boştur; eşik (0,85) oraya konur, kenarına
değil. Kararlılık, ölçülen doğrulukla birebir örtüşür: sağlam okunan aile
%99, kararsız okunan aile %49.

Bağlı olan tek kullanımı raporlamadır. Kararsız bir okumayı kesinmiş gibi
göstermek fazla iddiadır; arayüz bu durumda okumanın yanına *"bu okuma
kararsız — aynı şekli biraz farklı çizerseniz farklı okunabilir"* yazar.
Maliyet 11 ms.

---

## Yeniden üretme

```bash
python -m tools.formation_audit --cross                          # denetçiyi denetle
python -m tools.formation_audit --timeframe 4h --compare --top 50
python -m tools.formation_audit --family envelope --freehand     # elle çizim
```

---

## Ek: teşhis değişti — sorun eşleştirmede değil, sıralamada

`tools/formation_audit` sonuçların yapısını **zarf eğimleriyle** denetler.
Zarf eğimlerine dayanan bir filtreyi onunla ölçmek dairesel olurdu: filtre
kendi ölçütünü optimize eder, tablo iyileşir, ürün iyileşmez.

`tools/gt_benchmark` daireden tek bilinen yolla çıkar: **formasyonu biz
koyarız.** Sentetik seriye bilinen bir bar aralığına enjekte edilir; dönen
pencere o aralıkla örtüşüyorsa doğrudur. Gürültü sembollerine *başka*
formasyonlar konur — üçgen ararken bayrak bulmak isabet değildir.

### Yoğunluk deneyi

24 hedef sabit, gürültü sembolü sayısı değişken:

| gürültü sembolü | kesinlik | duyarlılık |
|---|---|---|
| 40 | %88 | %58 |
| 120 | %65 | %58 |
| 300 | %58 | %58 |

**Duyarlılık sabit.** Motor enjekte edilen üçgenleri her yoğunlukta aynı
oranda buluyor — eşleştirme bozuk değil. Kaybettiği yer sıralama: havuz
büyüdükçe "DTW'ye yakın ama üçgen değil" pencereler gerçek olanların üstüne
çıkıyor. Yukarıdaki %34, gerçek korpusun yoğunluğunda bu eğrinin devamıdır.

### Kategorik filtre neden çözemedi

İlk 50 sonucun kaçı sorgunun trend çizgisi imzasını **zaten** taşıyor:

| sorgu | imzayı taşıyan | tanımı geçen |
|---|---|---|
| yükselen takoz | **50/50** | 26/50 |
| düşen takoz | 46/50 | 32/50 |
| simetrik üçgen | 34/50 | 33/50 |
| yükselen üçgen | 24/50 | 17/50 |

Takozlarda elenecek bir şey yok. Ayırt edici bilgi *bağıl* eğimde: takoz
yakınsar, bayrağın kanalı paraleldir. Yakınsama bileşeni eklendi, takozları
iyileştirdi (10→11, 8→9), **bayrakları bozdu** (16→14, 18→15) — bayrağın
zarfı direği de kapsadığı için tam pencerede kararsız. Net sonuç:

| | kesinlik | duyarlılık |
|---|---|---|
| zarf filtresi KAPALI | 94/192 · %49 | %48 |
| iki bileşenli | 92/192 · %48 | %47 |
| üç bileşenli | 91/191 · %48 | %47 |

Bağlanmadı (K-21).

### Bir sonraki hipotez

Sorun maskeyle çözülmüyor çünkü sahtekârlar kategorik imzayı taşıyor. Ayırt
edici bilgi süreklidir (*ne kadar* yakınsıyor, *ne kadar* yatay). Doğru biçim
muhtemelen bir filtre değil, sıralamaya giren **sürekli bir tanım uyum
skoru**dur — K-14'ün yüzdelik sıralamasına dokunacağı için ayrı bir karar.

```bash
python -m tools.gt_benchmark --family slope --noise 300 --compare-envelope
```
