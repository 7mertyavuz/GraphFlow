# GraphFlow — Zaman Dilimi Çaprazlaması (F4.7)

> ⚠️ **Bu rapordaki sayılar yapısal imza filtresinden ÖNCEki korpusa aittir.**
> Filtre bağlandıktan sonra örneklem değişti; güncel tablolar ve filtrenin
> istatistiğe etkisi için bkz. [09-yapisal-filtre-ve-istatistik.md](09-yapisal-filtre-ve-istatistik.md).
> Buradaki yöntem ve çıkarımlar (replikasyon, kırılganlık) geçerliliğini
> koruyor — değişen, hangi pencerelerin örnekleme girdiği.
>
> **Belge türü:** Faz raporu · **Tarih:** 08.09.2026
> **Önceki:** [07-f46-raporu.md](07-f46-raporu.md)
> **Üretim:** `python -m tools.run_outcomes --timeframe 1d` ve `--timeframe 4h --out-suffix _4h`

---

## Neden bu ölçüm mümkün oldu

F4–F4.6'nın tamamı **yalnız 1d**'de yapılmıştı; 4h korpusu 80 sembol / 881K
pencereydi ve istatistik üretmeye yetmiyordu. Arayüzün varsayılanı ise 4h'ydi —
kullanıcı, hakkında doğrulanmış hiçbir istatistik bulunmayan bir zaman
diliminde arama yapıyordu.

4h evreni 1.097 sembole (11,6M pencere) çıkarıldıktan sonra ölçüm ilk kez
anlamlı hâle geldi: şablon başına **N = 300–800**, kapsam 83–105 ay.

---

## ★ İki cümlelik sonuç

> **Replike eden tek hücre var:** yükselen takoz, long, 2:1 — 1d'de
> -0.326R, 4h'de -0.280R.
>
> **Ama Bonferroni sınırındaki bulgular kırılgan.** Korpusa 10 günlük veri
> eklemek, geçen hücrelerin kimliğini değiştirdi (aşağıda).

| | 1d | 4h |
|---|---|---|
| Ölçülebilen test | 56 | 56 |
| %95'te anlamlı | 14 | 11 |
| Bonferroni'den geçen | 1 | 3 |
| **İki dilimde aynı yönde** | **1** | |

---

## Replikasyon tablosu

En az bir dilimde anlamlı çıkan tüm hücreler.

| Şablon | Yön | Konfig | 1d edge | 4h edge | Replike |
|---|---|---|---|---|---|
| `ascending_triangle` | long | 1:1 | +0.112 — | +0.144 ✅ | — |
| `ascending_triangle` | short | 1:1 | -0.107 — | -0.156 ✅ | — |
| `cup_and_handle` | long | 1:1 | -0.165 ✅ | -0.073 — | — |
| `cup_and_handle` | long | 2:1 | -0.246 ✅ | -0.106 — | — |
| `cup_and_handle` | short | 2:1 | +0.168 ✅ | +0.061 — | — |
| `double_top` | short | 2:1 | -0.264 ✅ | +0.035 — | — |
| `inverse_head_and_shoulders` | long | 1:1 | -0.222 ✅ | -0.032 — | — |
| `inverse_head_and_shoulders` | long | 2:1 | -0.352 ✅ | -0.018 — | — |
| `inverse_head_and_shoulders` | short | 1:1 | +0.201 ✅ | +0.027 — | — |
| `inverse_head_and_shoulders` | short | 2:1 | +0.232 ✅ | -0.006 — | — |
| `pennant` | long | 1:1 | -0.010 — | -0.144 ✅ | — |
| `pennant` | long | 2:1 | -0.046 — | -0.217 ✅ | — |
| `pennant` | short | 1:1 | +0.023 — | +0.158 ✅ | — |
| `pennant` | short | 2:1 | +0.099 — | +0.246 ✅ | — |
| `rising_wedge` | long | 1:1 | -0.148 ✅ | -0.102 — | — |
| `rising_wedge` | long | 2:1 | -0.326 ✅ | -0.280 ✅ | **✅** |
| `rising_wedge` | short | 1:1 | +0.145 ✅ | +0.115 — | — |
| `rising_wedge` | short | 2:1 | +0.265 ✅ | +0.027 — | — |
| `rounding_bottom` | long | 1:1 | -0.146 ✅ | -0.024 — | — |
| `rounding_bottom` | long | 2:1 | -0.198 ✅ | -0.062 — | — |
| `symmetrical_triangle` | long | 1:1 | +0.562 — | +0.628 ✅ | — |
| `symmetrical_triangle` | long | 2:1 | +0.625 — | +0.855 ✅ | — |
| `symmetrical_triangle` | short | 1:1 | -0.512 — | -0.603 ✅ | — |
| `symmetrical_triangle` | short | 2:1 | -0.364 — | -0.851 ✅ | — |

### Replike eden

| Yön | Konfig | 1d edge | 1d %95 GA | 1d N | 4h edge | 4h %95 GA | 4h N |
|---|---|---|---|---|---|---|---|
| long | 2:1 | -0.326 | [-0.531; -0.123] | 246 | -0.280 | [-0.434; -0.114] | 505 |

### Bonferroni'den geçenler

| Dilim | Şablon | Yön | Edge | Bonferroni GA |
|---|---|---|---|---|
| 1d | `rising_wedge` | short | +0.265 | [+0.013; +0.603] |
| 4h | `pennant` | long | -0.217 | [-0.407; -0.012] |
| 4h | `pennant` | short | +0.246 | [+0.030; +0.503] |
| 4h | `rising_wedge` | long | -0.280 | [-0.541; -0.010] |

---

## ⚠ Sınırdaki bulgular kırılgan — ölçüldü

Aynı ölçüm iki kez yapıldı: biri **28 Ağustos**, diğeri **8 Eylül** verisiyle.
Aradaki fark 9 yıllık korpusa eklenen **10 gün**. Sonuç:

| | 28 Ağu verisi | 8 Eyl verisi |
|---|---|---|
| 1d Bonferroni | `rising_wedge` long **ve** short | yalnız `rising_wedge` short |
| 4h Bonferroni | `pennant` short, `rising_wedge` long | `pennant` long **ve** short, `rising_wedge` long |
| Replike eden hücre | 3 | 1 |

Hiçbir kod değişmedi; yalnız veri tazelendi. Geçen hücrelerin **kimliği**
değişti çünkü güven aralıkları sıfırı kıl payı dışlıyor:
`[+0,013; +0,603]`, `[−0,541; −0,010]`, `[−0,407; −0,012]`.

Bu bir hata değil, **ölçüm çözünürlüğünün sınırı**. Bonferroni sınırında
duran bir bulguya "keşif" muamelesi yapmak, gürültüyü kanıt sanmaktır. Aynı
sonucu üç bağımsız yoldan alıyoruz:

1. `tools/ci_calibration`: ay-bloklu bootstrap gerçek rejimde **%92** kapsıyor
   (nominal %95) — anlamlılık zaten bir miktar iyimser okunuyor.
2. F4.6: `rising_wedge`'in edge'i ön-getiri eşleştirmeli gölgede kayboluyor
   (+0,327 → +0,115).
3. Burada: 10 günlük veri geçen hücrelerin kimliğini değiştiriyor.

**Hüküm:** Bu korpusta, bu yöntemle, şekle atfedilebilecek dayanıklı bir edge
gösterilememiştir.

---

## Nasıl okunmalı

**Replikasyon güçlü kanıt ama bağımsız kanıt değil.** 4h ve 1d aynı piyasanın,
aynı sembollerin, aynı dönemlerin iki farklı örneklemesidir. Farklı olan
pencereleme ve toplulaştırma — sağlamlık kontrolü olarak anlamlı, tekrar eden
deney olarak değil.

**Replike ETMEYENLER öğretici.** Bir dilimde anlamlı olup diğerinde olmayan,
hatta işareti dönen hücreler var. Gürültünün klasik imzası.

**`symmetrical_triangle` uyarısı.** Devasa edge'ler gösteriyor ama N çok
küçük (1d'de 4 eşleşme). Bonferroni eliyor. Sebebi kanonik vektörün temsil
sınırına dayanması — bkz. `docs/00` Açık Sorular #7 ve `tools/template_health`.

---

## Yöntem

* Tolerans `OUTCOME_TOLERANCE = medium`'da sabit (p-hacking kilidi)
* Bariyerler ATR tabanlı, 2:1 ve 1:1 (K-16)
* Gölge: zaman-eşleştirmeli, aynı ay + farklı sembol (K-12)
* GA: ay-bloklu bootstrap, 10.000 tekrar
* Bonferroni: aile = 56 test, **ikinci bir bootstrap geçişiyle** — aralık
  analitik olarak genişletilmez

Ham veri: `data/f3/f45_raw.json` (1d) ve `f45_raw_4h.json` (4h).
