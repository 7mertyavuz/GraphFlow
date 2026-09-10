# GraphFlow — F4.5 İstatistiksel Sağlamlaştırma Raporu

> **Belge türü:** Faz raporu
> **Tarih:** 31 Temmuz 2026
> **Önceki:** [05-f4-raporu.md](05-f4-raporu.md)

Bu oturum yeni özellik eklemedi; F4'ün sayılarını sağlamlaştırdı.

---

## ★ Tek cümlelik sonuç

> **Bir formasyonda anlamlı edge ölçüldü: yükselen takoz.** Short yönde
> **+0,331R** `[+0,038; +0,601]`, long yönde **−0,388R** `[−0,730; −0,064]` —
> ay-bloklu bootstrap ve 52 testlik Bonferroni ailesinden sonra. İkisi aynı
> bulgunun iki yüzüdür (aynı olaylar, aynalanmış bariyerler), **iki bağımsız
> kanıt değildir**.

F4'ün tek pozitif sonucu olan **alçalan üçgen anlamlılığını kaybetti** —
tam da beklendiği gibi.

---

## Adım 1 — Ay-bloklu bootstrap

### Problem gerçekti: ölçülen korelasyon 0,384

Gölge havuzu *"aynı ay, farklı sembol"* kuralıyla çekiliyor. Ampirik ölçüm
(250 parite, 37 rastgele ay, ay içi günlük log getirilerin ortalama ikili
korelasyonu):

```
ortalama kesitsel korelasyon = 0,384
```

Yani aynı aydan 20 farklı sembol **20 bağımsız gözlem vermiyor**.

### Uygulama

Blok birimi **takvim ayı**. Aylar yerine koyarak çekilir; seçilen ayın **tüm**
eşleşmeleri ve **tüm** gölgeleri birlikte alınır — ay içi korelasyon bloğun
içinde kalır ve K-12'nin zaman eşleştirmesi bootstrap'ta da korunur.
10.000 tekrar. Yeni altyapı yok: mevcut bootstrap'ın örnekleme birimi değişti.

### Tasarım etkisi = SE_blok / SE_iid

| Ölçüm | Değer |
|---|---|
| Medyan tasarım etkisi | **1,28** |
| Aralık | 0,89 – 2,03 |
| Blok GA / iid GA genişlik oranı (medyan) | **1,29** |

**iid bootstrap belirsizliği ortalama %29 eksik ölçüyormuş.** En yüksek
tasarım etkisi (1,91–2,03) tam da F4'ün pozitif sonuçlarında çıktı —
alçalan üçgen long 2:1 ve çanak dip short 2:1.

> **Not:** Tasarım etkisi 1'in altına da inebiliyor (min 0,89). Sebebi
> yöntemsel: ay etkisi hem eşleşmede hem gölgede ortak olduğunda blok
> çekiminde **birbirini götürür** — eşleştirmenin korunmasının doğrudan
> sonucudur. İki karşıt kuvvet vardır (korelasyon genişletir, eşleştirme
> daraltır) ve net etki formasyona göre değişir.

### `n_months` — kanıt gücünün gizli boyutu

`n = 242`'nin 52 aya yayılması ile 8 aya yayılması aynı kanıt değildir.
Blok bootstrap bunu otomatik cezalandırır; tablo sütun olarak da gösterir.
Ölçülen aralık: **50 – 78 ay** (formasyonlar 4–6,5 yıla yayılmış — bu iyi).

---

## Adım 2 — Ayna (short) yönü

`TP = C₀ − k_tp·ATR`, `SL = C₀ + k_sl·ATR`. Bariyerler çevrildi ama
muhafazakâr aynı-bar kuralı (SL önce — SL artık **yukarıda**), gap kuralı,
komisyon, maliyet tabanı ve delist zorunlu çıkışı **aynen** geçerli.
İkinci bir kod yolu açılmadı: `direction` yalnızca bir işaret çarpanı.

### Null kapısı — short için de geçti ✅

| Konfig | Short başarı | Teorik null | %95 GA |
|---|---|---|---|
| 2:1 | %32,2 | %33,3 | [%29,5 – %35,1] ✅ |
| 1:1 | %48,8 | %50,0 | [%45,9 – %51,8] ✅ |

Fiyat martingale olduğu için short null'ları long ile aynı çıkmalıydı; çıktı.
Bariyer çevirmede hata yok.

### Ayrıştırıcı test — alçalan üçgen

| Yön | Konfig | Edge | Blok GA %95 | Sonuç |
|---|---|---|---|---|
| long | 2:1 | +0,294 | [−0,074; +0,619] | **anlamsız** |
| long | 1:1 | +0,200 | [−0,021; +0,372] | anlamsız |
| short | 2:1 | −0,106 | [−0,308; +0,169] | anlamsız |
| short | 1:1 | −0,175 | [−0,358; +0,041] | anlamsız |

Karar tablosuna göre: short **null**. Yani **long pozitifi büyük olasılıkla
gürültüydü** — ve zaten blok bootstrap'la %95'te bile anlamlılığını kaybetti
(tasarım etkisi 1,91: F4'teki dar GA'nın kaynağı kesitsel korelasyonmuş).

### Bonus soru — beş yükseliş dönüş formasyonu short'ta ne yapıyor?

F4'te gölgesinden anlamlı biçimde **kötü** çıkan beşi, short'ta **iyi**
çıkıyor. %95 blok GA ile:

| Formasyon | Konfig | Long edge | Short edge | Short GA %95 |
|---|---|---|---|---|
| rising_wedge | 2:1 | −0,388 ✅kötü | **+0,331** ✅iyi | [+0,151; +0,496] |
| inverse_head_and_shoulders | 2:1 | −0,308 ✅kötü | **+0,240** ✅iyi | [+0,035; +0,453] |
| inverse_head_and_shoulders | 1:1 | −0,188 ✅kötü | **+0,185** ✅iyi | [+0,037; +0,321] |
| rising_wedge | 1:1 | −0,218 ✅kötü | **+0,177** ✅iyi | [+0,032; +0,311] |
| rounding_bottom | 1:1 | −0,189 ✅kötü | **+0,150** ✅iyi | [+0,009; +0,281] |
| cup_and_handle | 2:1 | −0,254 ✅kötü | +0,106 | [−0,046; +0,278] |
| double_bottom | 2:1 | −0,312 | +0,157 | [−0,101; +0,408] |

Ayna simetrisi tutarlı: long'da kötü olan short'ta iyi. **Ama bu iki
bağımsız bulgu değildir** — aynı olayların aynalanmış ölçümüdür. Bir
formasyonun long'da −0,3R vermesi ile short'ta +0,3R vermesi, mekanik olarak
büyük ölçüde aynı ifadedir (gap ve aynı-bar asimetrisi nedeniyle tam ayna
değil, ama yakın).

---

## Adım 3 — Çoklu karşılaştırma ailesi 28 → 52

14 şablon × 2 konfigürasyon × 2 yön = 56 test. `symmetrical_triangle`
(N = 4) **ölçülemedi (N yetersiz)** olarak işaretlendi ve aileye dahil
edilmedi → **aile = 52**, düzeltilmiş güven düzeyi **%99,904**.

Aile büyüdüğü için long sonuçlar da bu yeni eşikle yeniden raporlandı.

### Bonferroni'den sağ çıkanlar: 2 / 52

| Yön | Formasyon | Konfig | N | Edge | Bonferroni GA %99,904 |
|---|---|---|---|---|---|
| **short** | rising_wedge | 2:1 | 252 | **+0,331** | [+0,038; +0,601] |
| **long** | rising_wedge | 2:1 | 252 | **−0,388** | [−0,730; −0,064] |

En yakın kaçıranlar: `rising_wedge 1:1` (short +0,177 `[−0,054; +0,396]`),
`inverse_head_and_shoulders 2:1` (short +0,240 `[−0,068; +0,574]`),
`rounding_bottom 1:1` (long −0,189 `[−0,371; +0,067]`).

### Aşamalı sıkılaşma — tek tabloda

| Yöntem | Anlamlı test sayısı |
|---|---|
| F4: iid bootstrap, %95, aile 28 | 13 / 26 |
| F4: iid bootstrap, Bonferroni %99,82 | 8 / 26 |
| **F4.5: blok bootstrap, %95, aile 52** | **14 / 52** |
| **F4.5: blok bootstrap, Bonferroni %99,904** | **2 / 52** |

---

## Yorum

**Yükselen takoz gerçekten düşüş formasyonu gibi davranıyor.** Şablon
meta-verisinde `bias: bearish` yazıyor; ölçüm bunu doğruluyor: long'da
sistematik olarak gölgesinden kötü, short'ta iyi, ikisi de en katı düzeltmeden
sağ çıkıyor. N = 252, 64 farklı aya yayılmış.

**Ama bu tek bir bulgudur, iki değil.** Aynı 252 olayın aynalanmış ölçümü.
Ürün iddiası olarak yazılacaksa: *"yükselen takoz, 2R hedef / 1R stop
senaryosunda short yönde ölçülmüş +0,33R beklenti üretmiş (n=252, 64 ay,
%95 GA [+0,15; +0,50], 52 testlik ailede Bonferroni'den sağ çıkıyor)"*.

**Alçalan üçgen düştü.** F4'ün tek pozitif sonucu, kesitsel korelasyon hesaba
katılınca anlamlılığını kaybetti. Tasarım etkisi 1,91 — GA'sı gerçekte
neredeyse iki katı genişmiş. Bu, F4.5'in var oluş sebebinin somut karşılığı.

**Geri kalan 50 testte anlamlı fark yok.** OBO, bayrak, fincan-kulp, ikili
tepe/dip dahil. Bu bir başarısızlık değil, ölçümün kendisidir.

---

## Kaydedilen sınır (çözülmedi)

Tüm ölçüm **tek veri kümesi** üzerinde: Binance spot, 1d, 2017–2026.
**Örneklem dışı doğrulama yok.**

4h matrisleri kurulduğunda kısmî bir sağlamlık kontrolü olarak kullanılabilir —
aynı varlıklar, aynı sürecin farklı örneklemesi. **Tam bağımsız bir test
değildir** ve öyle sunulmamalıdır.

Ek sınırlar:

1. `symmetrical_triangle` N = 4 → ölçülemedi.
2. Gölge havuzu aynı ay + farklı sembol; **sektör/tema** eşleştirmesi yok.
   Blok bootstrap kesitsel korelasyonu artık hesaba katıyor, ama gölgenin
   *seçimi* hâlâ tema-kör.
3. Long ve short aynı olay kümesinin iki ölçümü — aile büyüklüğü 52 sayılıyor
   ama testler tam bağımsız değil, yani Bonferroni burada **muhafazakârdan da
   öte** olabilir (gerçek aile etkin olarak daha küçük).

---

## Ölçüm dosyaları

```
data/f3/f45_raw.json          52 test × (blok GA, iid GA, tasarım etkisi, n_months)
data/f3/f45_bonferroni.json   Bonferroni düzeyinde blok GA'lar
data/f3/f45_meta.json         ampirik korelasyon, aile büyüklüğü, düzeltilmiş düzey
```
