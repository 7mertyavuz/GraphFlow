# GraphFlow — Zaman Dilimi Çaprazlaması (F4.7)

> **Belge türü:** Faz raporu · **Tarih:** 08.09.2026
> **Önceki:** [07-f46-raporu.md](07-f46-raporu.md)
> **Üretim:** `python -m tools.run_outcomes --timeframe 1d` ve `--timeframe 4h --out-suffix _4h`

---

## Neden bu ölçüm mümkün oldu

F4–F4.6'nın tamamı **yalnız 1d**'de yapılmıştı; 4h korpusu 80 sembol / 881K
pencereydi ve istatistik üretmeye yetmiyordu. Arayüzün varsayılanı ise 4h'ydi —
yani kullanıcı, hakkında hiçbir doğrulanmış istatistik bulunmayan bir zaman
diliminde arama yapıyordu.

4h evreni 1.097 sembole (11,6M pencere) çıkarıldıktan sonra ölçüm ilk kez
anlamlı hâle geldi: şablon başına **N = 302–796**, kapsam **83–105 ay**,
gölge havuzu 5.926–15.640.

---

## ★ Tek cümlelik sonuç

> **Yükselen takoz, iki zaman diliminde de aynı yönde anlamlı çıkan tek
> formasyon.** Diğer bütün bulgular replikasyonda düşüyor — bir dilimde
> anlamlı olan, diğerinde değil.

| | 1d | 4h |
|---|---|---|
| Ölçülebilen test | 56 | 56 |
| %95'te anlamlı | 14 | 13 |
| Bonferroni'den geçen | 2 | 2 |

---

## Replikasyon tablosu

En az bir dilimde anlamlı çıkan tüm hücreler. Son sütun, **iki dilimde de
aynı işaretle** anlamlı olanları işaretler.

| Şablon | Yön | Konfig | 1d edge | 4h edge | Replike |
|---|---|---|---|---|---|
| `ascending_triangle` | long | 1:1 | +0.130 — | +0.138 ✅ | — |
| `ascending_triangle` | short | 1:1 | -0.125 — | -0.150 ✅ | — |
| `cup_and_handle` | long | 1:1 | -0.151 ✅ | -0.074 — | — |
| `cup_and_handle` | long | 2:1 | -0.220 ✅ | -0.098 — | — |
| `cup_and_handle` | short | 2:1 | +0.191 ✅ | -0.010 — | — |
| `descending_triangle` | long | 1:1 | +0.240 ✅ | -0.021 — | — |
| `descending_triangle` | short | 1:1 | -0.231 ✅ | +0.034 — | — |
| `double_bottom` | long | 2:1 | -0.367 ✅ | -0.053 — | — |
| `double_top` | short | 2:1 | -0.282 ✅ | +0.007 — | — |
| `falling_wedge` | long | 2:1 | +0.208 ✅ | +0.084 — | — |
| `inverse_head_and_shoulders` | long | 1:1 | -0.166 ✅ | -0.062 — | — |
| `inverse_head_and_shoulders` | long | 2:1 | -0.272 ✅ | -0.109 — | — |
| `pennant` | long | 1:1 | -0.023 — | -0.143 ✅ | — |
| `pennant` | long | 2:1 | -0.045 — | -0.191 ✅ | — |
| `pennant` | short | 1:1 | +0.034 — | +0.151 ✅ | — |
| `pennant` | short | 2:1 | +0.117 — | +0.248 ✅ | — |
| `rising_wedge` | long | 1:1 | -0.161 ✅ | -0.145 ✅ | **✅ aynı yön** |
| `rising_wedge` | long | 2:1 | -0.259 ✅ | -0.318 ✅ | **✅ aynı yön** |
| `rising_wedge` | short | 1:1 | +0.137 ✅ | +0.152 ✅ | **✅ aynı yön** |
| `rising_wedge` | short | 2:1 | +0.273 ✅ | +0.127 — | — |
| `symmetrical_triangle` | long | 1:1 | +0.562 — | +0.628 ✅ | — |
| `symmetrical_triangle` | long | 2:1 | +0.625 — | +0.855 ✅ | — |
| `symmetrical_triangle` | short | 1:1 | -0.512 — | -0.603 ✅ | — |
| `symmetrical_triangle` | short | 2:1 | -0.364 — | -0.851 ✅ | — |

**Replike eden: yalnız `rising_wedge`** (3 hücre).

| Yön | Konfig | 1d edge | 1d %95 GA | 1d N | 4h edge | 4h %95 GA | 4h N | Bonferroni 1d / 4h |
|---|---|---|---|---|---|---|---|---|
| long | 1:1 | -0.161 | [-0.288; -0.038] | 307 | -0.145 | [-0.260; -0.029] | 477 | — / — |
| long | 2:1 | -0.259 | [-0.441; -0.091] | 307 | -0.318 | [-0.475; -0.156] | 477 | ✅ / ✅ |
| short | 1:1 | +0.137 | [+0.018; +0.260] | 307 | +0.152 | [+0.036; +0.267] | 477 | — / — |

---

## Nasıl okunmalı

**Replikasyon güçlü bir kanıt ama bağımsız kanıt DEĞİL.** 4h ve 1d aynı
piyasanın, aynı sembollerin, aynı dönemlerin iki farklı örneklemesidir;
bağımsız iki veri kümesi değil. Farklı olan şey pencereleme ve toplulaştırma
— bu, sağlamlık kontrolü olarak anlamlıdır, tekrar eden bir deney olarak
değil.

**Replike ETMEYEN bulgular daha öğretici.** `cup_and_handle`, `double_bottom`,
`descending_triangle`, `inverse_head_and_shoulders` 1d'de anlamlı, 4h'de
değil; `pennant` ve `ascending_triangle` tam tersi. İşaretleri de dönüyor
(ör. `descending_triangle/long/1:1` 1d'de +0,240, 4h'de −0,021). Bu, gürültünün
klasik imzasıdır: bir örneklemde anlamlı, diğerinde yok.

**`symmetrical_triangle` uyarısı.** Devasa edge'ler gösteriyor (4h long 2:1
+0,855) ama N = 16 (1d'de yalnız 4 eşleşme). Bonferroni ikisini de eliyor —
tam da bu yüzden var. Şablonun ayırt ediciliği ayrıca incelenmeli.

**Ve en önemlisi:** F4.6, `rising_wedge`'in edge'inin **ön-getiri
eşleştirmeli gölgede kaybolduğunu** ölçtü (+0,327 → +0,115, anlamsız).
Yani burada replike eden şey büyük olasılıkla şeklin kendisi değil,
formasyonun seçtiği **momentum durumu**. Çaprazlama bulgunun *gerçek*
olduğunu gösteriyor; *şekle ait* olduğunu göstermiyor.

---

## Yöntem

* Tolerans `OUTCOME_TOLERANCE = medium`'da sabit (p-hacking kilidi)
* Bariyerler ATR tabanlı, 2:1 ve 1:1 (K-16)
* Gölge: zaman-eşleştirmeli, aynı ay + farklı sembol (K-12)
* GA: ay-bloklu bootstrap, 10.000 tekrar; iid karşılaştırma için saklanır
* Bonferroni: aile = ölçülebilen test sayısı (56), ikinci bir bootstrap
  geçişiyle — aralık analitik olarak genişletilmez

Ham veri: `data/f3/f45_raw.json` (1d) ve `data/f3/f45_raw_4h.json` (4h).
