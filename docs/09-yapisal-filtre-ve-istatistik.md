# GraphFlow — Yapısal Filtre ve İstatistik (F4.8)

> **Belge türü:** Faz raporu · **Tarih:** 08.09.2026
> **Önceki:** [08-zaman-dilimi-caprazlama.md](08-zaman-dilimi-caprazlama.md)
> **Üretim:** `python -m tools.run_outcomes --timeframe 1d` / `--timeframe 4h --out-suffix _4h`

---

## Neden bu ölçüm gerekti

Yapısal imza filtresi (K-04 Eylül eki) aramaya bağlandı: artık ilk sayfadaki
sonuçların **%100'ü** gerçekten aranan formasyon (öncesi %42, elle çizimde
OBO'da 12'de 1). Ama filtre **arama sonuçlarını** değiştiriyor, istatistik de
o sonuçlardan hesaplanıyor (K-09). Yani tüm F4/F4.5/F4.7 tabloları
yeniden üretilmek zorundaydı.

Ve bu, geriye dönük olarak önemli bir soruyu ortaya çıkardı.

---

## ★ Asıl bulgu: eski tablolar ne ölçüyordu?

Filtre öncesi örneklemin **%58'i aranan formasyon değildi** (bağımsız yapı
denetimi, `tools/formation_audit`). Yani o tablolar

> *"omuz-baş-omuz işe yarıyor mu?"*

sorusunu değil,

> *"omuz-baş-omuza DTW ile benzeyen bir şey işe yarıyor mu?"*

sorusunu ölçüyordu. Filtreli sayılar daha az "anlamlı" ama **doğru soruyu**
yanıtlıyor.

---

## Filtrenin bedeli: güç, etki değil

| | Filtre öncesi | Filtre sonrası |
|---|---|---|
| Ortalama N (1d) | 328 | 141 |
| Ortalama %95 GA genişliği | 0.366 | 0.558 |
| %95'te anlamlı (1d) | 14 / 56 | 6 / 56 |
| Bonferroni (1d) | 2 | 1 |

N **%57 düştü**, aralıklar **%52 genişledi**. Anlamlılık kaybının
büyük kısmı budur — etkinin kaybolması değil:

* edge nokta tahminlerinin korelasyonu (öncesi ↔ sonrası): **0.829**
* ortalama mutlak değişim: **0.067R**
* işaret koruyan hücre: **38/44**

Etkiler yerinde duruyor; onları ayırt edecek çözünürlük kalmadı.

### Şablon başına (1d, long, 2:1)

| Şablon | N öncesi | N sonrası | edge öncesi | edge sonrası |
|---|---|---|---|---|
| `ascending_triangle` | 191 | 13 | +0.097 | -0.307 |
| `bear_flag` | 366 | 227 | -0.023 | -0.120 |
| `bull_flag` | 465 | 369 | -0.067 | -0.115 |
| `cup_and_handle` | 316 | 120 | -0.246 | -0.286 |
| `descending_triangle` | 203 | 33 | +0.310 | +0.283 |
| `double_bottom` | 253 | 45 | -0.302 | -0.405 |
| `double_top` | 201 | 36 | +0.133 | +0.097 |
| `falling_wedge` | 309 | 69 | +0.186 | +0.153 |
| `head_and_shoulders` | 302 | 31 | +0.013 | -0.001 |
| `inverse_head_and_shoulders` | 270 | 29 | -0.352 | -0.646 |
| `pennant` | 388 | 231 | -0.046 | -0.034 |
| `rising_wedge` | 246 | 78 | -0.326 | -0.219 |
| `rounding_bottom` | 555 | 315 | -0.198 | -0.209 |
| `symmetrical_triangle` | 4 | 4 | +0.625 | +0.625 |

---

## Filtreli sonuçlar

| | 1d | 4h |
|---|---|---|
| Ölçülebilen test | 56 | 56 |
| %95'te anlamlı | 6 | 9 |
| Bonferroni'den geçen | 1 | 0 |
| İki dilimde aynı yönde | 0 | |

### En az bir dilimde anlamlı çıkanlar

| Şablon | Yön | Konfig | 1d edge | 4h edge | Replike |
|---|---|---|---|---|---|
| `cup_and_handle` | long | 2:1 | -0.286 ✅ | +0.096 — | — |
| `double_bottom` | long | 2:1 | -0.405 ✅ | +0.087 — | — |
| `double_top` | short | 2:1 | -0.843 ✅ | +0.311 — | — |
| `falling_wedge` | short | 2:1 | +0.110 — | -0.328 ✅ | — |
| `inverse_head_and_shoulders` | long | 2:1 | -0.646 ✅ | +0.048 — | — |
| `inverse_head_and_shoulders` | short | 2:1 | +0.376 — | -0.399 ✅ | — |
| `rising_wedge` | long | 1:1 | +0.018 — | -0.174 ✅ | — |
| `rising_wedge` | long | 2:1 | -0.219 — | -0.258 ✅ | — |
| `rising_wedge` | short | 1:1 | -0.012 — | +0.182 ✅ | — |
| `rounding_bottom` | long | 1:1 | -0.198 ✅ | -0.018 — | — |
| `rounding_bottom` | short | 1:1 | +0.155 ✅ | +0.002 — | — |
| `symmetrical_triangle` | long | 1:1 | +0.562 — | +0.628 ✅ | — |
| `symmetrical_triangle` | long | 2:1 | +0.625 — | +0.855 ✅ | — |
| `symmetrical_triangle` | short | 1:1 | -0.512 — | -0.603 ✅ | — |
| `symmetrical_triangle` | short | 2:1 | -0.364 — | -0.851 ✅ | — |

---

## Hüküm

Üç ölçüm aynı yöne işaret ediyor ve dördüncüsü şimdi eklendi:

1. `tools/ci_calibration`: ay-bloklu bootstrap gerçek rejimde %92 kapsıyor
   (nominal %95) — anlamlılık zaten iyimser.
2. F4.6: edge, ön-getiri eşleştirmeli gölgede kayboluyor.
3. F4.7: 10 günlük veri, Bonferroni'yi geçen hücrelerin kimliğini değiştiriyor.
4. **F4.8: örneklem gerçekten o formasyonla sınırlandığında anlamlılık
   büyük ölçüde kayboluyor — çünkü N düşüyor, etki değil.**

**Bu korpusta, bu yöntemle, şekle atfedilebilecek dayanıklı bir edge
gösterilememiştir.** Ürünün iddiası da bu değil zaten: ölçülmüş ve dürüstçe
raporlanmış geçmiş dağılım.

Yeni ve önemli olan şu: artık en azından **doğru şeyi** ölçüyoruz. Ekranda
gördüğünüz 12 grafik gerçekten çizdiğiniz formasyon, ve altındaki istatistik
de tam o olayların istatistiği.
