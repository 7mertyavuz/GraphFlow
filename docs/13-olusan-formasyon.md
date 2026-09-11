# F4.12 — Oluşan formasyon: ilk %75 kalanı söylüyor mu?

**Tarih:** 11 Eylül 2026 · **Araç:** `tools/emerging_test`
**Önceki:** [12-null-orneklemi.md](12-null-orneklemi.md)

---

## Soru

Piyasadaki araçların bir kısmı (ChartScout, altFINS "Emerging") formasyon
%75–80 olgunluktayken uyarı verir. İma edilen şey, kalanın geleceğidir.
Bu özelliği GraphFlow'a eklemeden önce iddianın kendisi ölçüldü:

> Bir formasyonun ilk %75'ine benzeyen pencerelerde, **gerçek** devam
> formasyonu tamamlamaya, aynı aydan çekilmiş **rastgele** bir devamdan daha
> mı yakın?

Bilgi yoksa, "%75'te uyarı" kullanıcıya bir şey söylemez — yalnız bir
şeklin yarısını gösterip bütününü vaat eder.

## Yöntem

1. **Önek sorgusu:** şablonun ilk %75'i, 32 noktaya yeniden örneklenip
   z-score'lanır (K-02). Motor tarihsel aramayı orta toleransla koşar.
2. Önek uzunluğu `L` olan eşleşmenin tam formasyonu `L / 0,75` bar sürer;
   kalan `R = L/3` bar (24 → 8 · 40 → 13 · 64 → 21 · 100 → 33).
3. **Gerçek:** önek + gerçek devam; tam şablona Aşama 2 mesafesi.
4. **Kontrol:** aynı önek + başka bir sembolün **aynı aydaki** `R` barlık
   getirileri (K-12'nin zaman eşleştirmesi), olay başına 20 kontrol.
5. Olay skoru: gerçeğin kontrollerin kaçından şablona yakın olduğu
   (eşitlik ½); ortalaması bir AUC — bilgi yoksa **0,5**. Güven aralığı
   ay-bloklu bootstrap; Bonferroni; bulgu iki dilimde aranır (F4.7).

Kontrol devamının **büyüklüğü** iki biçimde ayarlanır:

| ölçek | kontrol getirisi neye ölçeklenir | ne sınanır |
|---|---|---|
| `prefix` | önekin oynaklığına | "rastgele bir devam" — büyüklük + yön + şekil |
| `shape` (**birincil**) | gerçek devamın oynaklığına | yalnız yön ve şekil |

**Araç önce kendi üzerinde denetlendi** (`tests/test_emerging.py`):
devam şablonun kendisiyse AUC > 0,9 (pozitif kontrol); devam kontrollerle
aynı süreçtense iki ölçekte de 0,5 ± 0,04 (negatif kontrol). Üçüncü test
bir karıştırıcıyı belgeler: devam önekten daha oynak ama yönü rastgele
olduğunda `prefix` ölçeği 0,5'ten uzaklaşıyor, `shape` 0,5'te kalıyor.
Bu yüzden birincil ölçü `shape`'tir.

## Sonuç

**Birincil (`shape`), 14 şablon × 2 dilim:**

| | 1d | 4h |
|---|---|---|
| %95'te 0,5'ten farklı | 2 / 14 | 4 / 14 |
| bunlardan 0,5'in **üstünde** | 1 | 1 |
| Bonferroni'yi geçen | 0 | 0 |
| iki dilimde aynı yönde | **hiçbiri** |

28 testte şans eseri ~1,4 "anlamlı" beklenir; bulunanların çoğu 0,5'in
**altında** (gerçek devam şablondan rastgele devamdan *daha uzak*) ve
simetrik üçgen iki dilimde zıt yönde (1d 0,573 · 4h 0,451).

**Tamamlanma oranı** (tam şablona mesafesi F3'ün mutlak "orta" eşiğinin
altında kalan pencere) — gerçek devam ile rastgele devam aynı:

| | gerçek | rastgele devam |
|---|---|---|
| boğa bayrağı 1d | 0,20 | 0,20 |
| düşen takoz 1d | 0,36 | 0,37 |
| flama 4h | 0,14 | 0,15 |
| boğa bayrağı 4h | 0,19 | 0,19 |
| ayı bayrağı 4h | 0,21 | 0,18 |

Dönüş formasyonlarında (OBO, ikili tepe/dip, çanak) tamamlanma iki kolda da
~0: mutlak eşik tam formasyon penceresi için katı; bu yüzden birincil ölçü
eşiksiz AUC'dir.

## Tuzak: `prefix` ölçeğinde "sinyal" var

| | 1d | 4h |
|---|---|---|
| boğa bayrağı | **0,590** (Bonferroni) | 0,545 |
| flama | 0,577 | **0,579** (Bonferroni) |
| simetrik üçgen | **0,633** (Bonferroni) | 0,550 |

Boğa bayrağı ve flama iki dilimde de aynı yönde — tek başına okunsa "oluşan
bayrak uyarısı çalışıyor" denirdi. **Büyüklük eşitlenince (`shape`) hepsi
kayboluyor:** boğa bayrağı 0,522 / 0,487, flama 0,493 / 0,479.

Sebep ölçüldü: devamın oynaklığı önekinkinin medyan **~0,8 katı** (iki
dilimde, dört şablonda 0,80–0,91). Bayrakta önek direği (büyük hareket)
içerir, şablonun kalanı sakin bir konsolidasyondur. Önekin oynaklığına
ölçeklenen kontrol devamı fazla büyük hareket eder; daha sakin olan gerçek
devam şablona "daha yakın" görünür. Bu bir şekil bilgisi değil, **büyük bir
hareketten sonra oynaklığın düşmesidir** — bilinen bir piyasa özelliği,
formasyona ait değil.

Bu, F4.6'nın momentum vekili bulgusunun ikizidir: görünen etki şeklin değil,
şeklin taşıdığı başka bir şeyin (orada ön-getiri, burada oynaklık) etkisi.

## Karar

**"Oluşan formasyon" uyarısı eklenmedi** (reddedilenler #27). %75
olgunlukta bir formasyonun kalanının gelme olasılığı, aynı ayın rastgele bir
devamının onu tamamlama olasılığından ayırt edilemiyor. Böyle bir uyarı
kullanıcıya bilgi değil, bir vaat satar.

Kullanıcı yine de oluşum hâlindeki şekilleri arayabilir: bir formasyonun
yalnız başını çizmek ya da grafikten sorgu, bugün de mümkün — ve ekrana
gelen istatistik o şeklin kendisininkidir, tamamlanacağı varsayılmaz.

## Sınırlar

- Önek oranı yalnız %75 ölçüldü; %50'de önek daha belirsizdir, bilgi
  beklentisi daha düşük.
- Kontrol, aynı aydan rastgele bir sembol ve an; sektör ya da kapitalizasyon
  eşleştirmesi yok.
- Ölçü "şablona yakınlık"tır, getiri değil. Sonrasının getirisi zaten
  istatistik panelinin ve Bulgular sayfasının konusu.
