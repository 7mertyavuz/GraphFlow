# GraphFlow — Yapısal Filtre ve İstatistik (F4.8)

> **Belge türü:** Faz raporu · **Tarih:** 08.09.2026
> **Önceki:** [08-zaman-dilimi-caprazlama.md](08-zaman-dilimi-caprazlama.md)
> **Üretim:** `python -m tools.run_outcomes --timeframe 1d` / `--timeframe 4h --out-suffix _4h`

---

## Neden bu ölçüm gerekti

Yapısal imza filtresi (K-04 Eylül eki) aramaya bağlandı: ilk sayfadaki
sonuçların **%100'ü** artık gerçekten aranan formasyon (öncesi %42, elle
çizimde OBO'da 12'de 1). Filtre arama sonuçlarını değiştirdiği ve istatistik
o sonuçlardan hesaplandığı için (K-09) tüm tablolar yeniden üretildi.

---

## ★ Asıl bulgu: eski tablolar ne ölçüyordu?

Filtre öncesi örneklemin **%58'i aranan formasyon değildi**. Yani o tablolar

> *"omuz-baş-omuz işe yarıyor mu?"*

sorusunu değil,

> *"omuz-baş-omuza DTW ile benzeyen bir şey işe yarıyor mu?"*

sorusunu ölçüyordu. Filtreli sayılar daha az "anlamlı" ama **doğru soruyu**
yanıtlıyor. Kirli bir örneklem üzerinde daha yüksek çözünürlük, yanlış soruyu
daha hassas ölçmektir.

---

## Filtrenin bedeli: güç, etki değil

| | Filtre öncesi | Filtre sonrası |
|---|---|---|
| Ortalama N (1d) | 313 | 174 |
| Ortalama %95 GA genişliği | 0.367 | 0.524 |
| %95'te anlamlı (1d) | 14 / 56 | 8 / 56 |
| Bonferroni (1d) | 2 | 2 |

Nokta tahminleri yerinde duruyor:

* korelasyon (öncesi ↔ sonrası): **0.815**
* ortalama mutlak değişim: **0.105R**
* işaret koruyan hücre: **47/52**

Etkiler kaybolmadı; onları ayırt edecek çözünürlük azaldı. *"Anlamlı çıkmadı"*
ile *"etki yok"* aynı şey değildir.

Kaybın bir kısmı aday havuzu büyütülerek geri alındı (`STAGE1_TOPK`
5.000 → 12.500, `STAGE2_TOPK` 1.000 → 2.500): 4h'de şablon başına sonuç
224 → 358, en kötü arama 400 ms ile bütçe içinde.

### Şablon başına (1d, long, 2:1)

| Şablon | N öncesi | N sonrası | edge öncesi | edge sonrası |
|---|---|---|---|---|
| `ascending_triangle` | 191 | 30 | +0.097 | -0.271 |
| `bear_flag` | 366 | 333 | -0.023 | -0.100 |
| `bull_flag` | 465 | 499 | -0.067 | -0.088 |
| `cup_and_handle` | 316 | 174 | -0.246 | -0.194 |
| `descending_triangle` | 203 | 50 | +0.310 | +0.449 |
| `double_bottom` | 253 | 57 | -0.302 | -0.516 |
| `double_top` | 201 | 60 | +0.133 | +0.323 |
| `falling_wedge` | 309 | 100 | +0.186 | +0.062 |
| `head_and_shoulders` | 302 | 49 | +0.013 | -0.220 |
| `inverse_head_and_shoulders` | 270 | 43 | -0.352 | -0.604 |
| `pennant` | 388 | 317 | -0.046 | -0.101 |
| `rising_wedge` | 246 | 121 | -0.326 | -0.081 |
| `rounding_bottom` | 555 | 430 | -0.198 | -0.198 |
| `symmetrical_triangle` | 4 | 63 | +0.625 | -0.075 |

---

## Güncel sonuçlar

| | 1d | 4h |
|---|---|---|
| Ölçülebilen test | 56 | 56 |
| %95'te anlamlı | 8 | 10 |
| Bonferroni'den geçen | 2 | 0 |
| İki dilimde aynı yönde | 2 | |

### Bonferroni'den geçenler

| Dilim | Şablon | Yön | Konfig | Edge | Bonferroni GA | N |
|---|---|---|---|---|---|---|
| 1d | `double_bottom` | long | 2:1 | -0.516 | [-1.041; -0.055] | 57 |
| 1d | `inverse_head_and_shoulders` | long | 2:1 | -0.604 | [-1.161; -0.011] | 43 |

---

## ⚠ Kırılganlık — üçüncü kez doğrulandı

F4.7 şunu ölçmüştü: korpusa 10 günlük veri eklemek, Bonferroni'yi geçen
hücrelerin **kimliğini** değiştiriyor. O gözlem bu fazda iki kez daha
tekrarlandı — hiçbirinde bir hata yoktu, yalnız parametre değişti:

| Koşum | Bonferroni'den geçen (1d) |
|---|---|
| tazelenmiş veri, filtre yok | `rising_wedge` short |
| yapısal filtre açık | `double_top` short |
| filtre + büyütülmüş havuz | `double_bottom` long, `inverse_head_and_shoulders` long |

Geçen hücre her seferinde **başka**. Güven aralıkları sıfırı kıl payı
dışladığı için sıralamadaki en ufak oynama kimliği değiştiriyor. Bonferroni
sınırında duran bir bulguya "keşif" muamelesi yapmak, gürültüyü kanıt
sanmaktır.

---

## Hüküm

Dört bağımsız ölçüm aynı yöne işaret ediyor:

1. `tools/ci_calibration`: ay-bloklu bootstrap gerçek rejimde %92 kapsıyor
   (nominal %95) — anlamlılık zaten iyimser okunuyor.
2. F4.6: edge, ön-getiri eşleştirmeli gölgede eriyor.
3. F4.7 + F4.8: geçen hücrelerin kimliği veri ya da parametre değişince
   değişiyor — üç koşumda üç farklı sonuç.
4. F4.8: örneklem gerçekten o formasyonla sınırlandığında anlamlılık
   düşüyor; nokta tahminleri ise duruyor (korelasyon 0.815).

**Bu korpusta, bu yöntemle, şekle atfedilebilecek dayanıklı bir edge
gösterilememiştir.**

Yeni ve önemli olan şu: artık **doğru şeyi** ölçüyoruz. Ekranda görülen 12
grafik gerçekten çizilen formasyon, altındaki istatistik de tam o olayların
istatistiği.

---

> **Devamı:** [10-formasyon-denetimi.md](10-formasyon-denetimi.md) — bu
> rapordaki "%42 → %100" ölçümü 4 formasyonluktu ve denetçi sıkılaştıktan
> sonra 12 formasyona genişletildi. Dönüş ailesi ilk 50'de %99; eğim tabanlı
> formasyonlarda filtrenin **etkisiz** olduğu orada ölçülür (K-20).

> **Güncelleme (10 Eylül 2026).** Bu rapordaki tablolar filtrenin her sorguda açık
> olduğu motorla üretildi. Kararlılık kapısı (K-20) eğim ailesinde örneklemi 2–3 katına
> çıkardı; güncel tablolar [11-yeniden-olcum.md](11-yeniden-olcum.md)'dedir.
