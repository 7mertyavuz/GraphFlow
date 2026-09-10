# GraphFlow — F4.6 Vekil Testi Raporu

> **Belge türü:** Faz raporu · **Son koşum:** 08.09.2026 (yapısal filtre açık, büyütülmüş havuz)
> **Önceki:** [06-f45-raporu.md](06-f45-raporu.md) · **Sonrası:** [09-yapisal-filtre-ve-istatistik.md](09-yapisal-filtre-ve-istatistik.md)

---

## Bu rapor üç kez yeniden üretildi

**1. koşum (2 Ağu) — GEÇERSİZ.** Sembol haritası hatası düzeltilmeden
yapılmıştı: 1d koşusu 4h evreninin haritasını okudu, N = 2–7 ile "sonuç"
üretti. `rising_wedge` short edge −0,562 çıkmıştı; F4.5 aynı testte +0,331
ölçmüştü — işaret bile tersti.

**2. koşum (29 Ağu).** Harita düzeltildi, N = 242–509, F4.5 yeniden üretildi.

**3. koşum (bu belge).** Yapısal imza filtresi açık, aday havuzu büyütülmüş.
Örneklem artık gerçekten aranan formasyonla sınırlı; öncesinde %58'i
formasyon bile değildi. N = 43–430.

---

## ★ Sonuç

> 40 testin **1'i** %95'te anlamlı, **0'i** Bonferroni'den geçiyor.
> Beş şablonun beşinde de edge, gölge ön-getiriye göre eşleştirilince eriyor.

---

## Ayırt edici test: standart gölge → ön-getiri eşleştirmeli gölge

Standart gölge "aynı ay, farklı sembol" der. Ön-getiri eşleştirmeli gölge
buna "**ve benzer ön-getiri**" ekler. Fark buharlaşıyorsa ölçülen şey
formasyonun geometrisi değil, "yakın zamanda çok hareket etti"nin ortalamaya
dönüşüdür.

| Şablon | N | Standart gölge | Ön-getiri eşleştirmeli | Edge kaybı |
|---|---|---|---|---|
| `cup_and_handle` | 174 | +0.025 — | -0.034 — | %237 |
| `double_bottom` | 57 | +0.301 — | +0.118 — | %61 |
| `inverse_head_and_shoulders` | 43 | +0.415 — | +0.410 — | %1 |
| `rising_wedge` | 121 | +0.236 — | +0.049 — | %79 |
| `rounding_bottom` | 430 | +0.171 — | +0.099 — | %42 |

---

## Tam tablo — 40 testin tamamı

| Şablon | Konfig | Gölge | Band | N | Gölge N | Edge (R) | %95 GA | Anlamlı | Bonferroni | DE |
|---|---|---|---|---|---|---|---|---|---|---|
| `cup_and_handle` | 1:1 | return_matched | ±0.15 | 174 | 3425 | +0.020 | [-0.118; +0.191] | — | — | 1.02 |
| `cup_and_handle` | 2:1 | return_matched | ±0.15 | 174 | 3425 | -0.027 | [-0.227; +0.219] | — | — | 1.14 |
| `cup_and_handle` | 1:1 | return_matched | ±0.25 | 174 | 3416 | +0.015 | [-0.124; +0.187] | — | — | 1.04 |
| `cup_and_handle` | 2:1 | return_matched | ±0.25 | 174 | 3416 | -0.034 | [-0.227; +0.210] | — | — | 1.13 |
| `cup_and_handle` | 1:1 | return_matched | ±0.50 | 174 | 3424 | +0.050 | [-0.079; +0.208] | — | — | 0.97 |
| `cup_and_handle` | 2:1 | return_matched | ±0.50 | 174 | 3424 | +0.005 | [-0.182; +0.241] | — | — | 1.10 |
| `cup_and_handle` | 1:1 | standard | — | 174 | 3446 | +0.053 | [-0.082; +0.228] | — | — | 1.02 |
| `cup_and_handle` | 2:1 | standard | — | 174 | 3446 | +0.025 | [-0.167; +0.264] | — | — | 1.13 |
| `double_bottom` | 1:1 | return_matched | ±0.15 | 57 | 1122 | +0.138 | [-0.153; +0.526] | — | — | 1.29 |
| `double_bottom` | 2:1 | return_matched | ±0.15 | 57 | 1122 | +0.175 | [-0.205; +0.647] | — | — | 1.20 |
| `double_bottom` | 1:1 | return_matched | ±0.25 | 57 | 1126 | +0.126 | [-0.169; +0.518] | — | — | 1.29 |
| `double_bottom` | 2:1 | return_matched | ±0.25 | 57 | 1126 | +0.118 | [-0.268; +0.597] | — | — | 1.21 |
| `double_bottom` | 1:1 | return_matched | ±0.50 | 57 | 1123 | +0.126 | [-0.177; +0.513] | — | — | 1.31 |
| `double_bottom` | 2:1 | return_matched | ±0.50 | 57 | 1123 | +0.162 | [-0.211; +0.615] | — | — | 1.17 |
| `double_bottom` | 1:1 | standard | — | 57 | 1127 | +0.247 | [-0.026; +0.612] | — | — | 1.21 |
| `double_bottom` | 2:1 | standard | — | 57 | 1127 | +0.301 | [-0.035; +0.719] | — | — | 1.07 |
| `inverse_head_and_shoulders` | 1:1 | return_matched | ±0.15 | 43 | 848 | +0.274 | [-0.053; +0.612] | — | — | 1.08 |
| `inverse_head_and_shoulders` | 2:1 | return_matched | ±0.15 | 43 | 848 | +0.387 | [-0.024; +0.787] | — | — | 0.92 |
| `inverse_head_and_shoulders` | 1:1 | return_matched | ±0.25 | 43 | 848 | +0.302 | [+0.009; +0.612] | ✅ | — | 1.00 |
| `inverse_head_and_shoulders` | 2:1 | return_matched | ±0.25 | 43 | 848 | +0.410 | [-0.016; +0.809] | — | — | 0.92 |
| `inverse_head_and_shoulders` | 1:1 | return_matched | ±0.50 | 43 | 854 | +0.304 | [-0.026; +0.607] | — | — | 1.03 |
| `inverse_head_and_shoulders` | 2:1 | return_matched | ±0.50 | 43 | 854 | +0.417 | [-0.055; +0.855] | — | — | 1.03 |
| `inverse_head_and_shoulders` | 1:1 | standard | — | 43 | 853 | +0.299 | [-0.001; +0.584] | — | — | 0.97 |
| `inverse_head_and_shoulders` | 2:1 | standard | — | 43 | 853 | +0.415 | [-0.024; +0.825] | — | — | 0.94 |
| `rising_wedge` | 1:1 | return_matched | ±0.15 | 121 | 2397 | -0.093 | [-0.280; +0.090] | — | — | 1.03 |
| `rising_wedge` | 2:1 | return_matched | ±0.15 | 121 | 2397 | +0.006 | [-0.277; +0.298] | — | — | 1.15 |
| `rising_wedge` | 1:1 | return_matched | ±0.25 | 121 | 2393 | -0.110 | [-0.306; +0.080] | — | — | 1.09 |
| `rising_wedge` | 2:1 | return_matched | ±0.25 | 121 | 2393 | +0.049 | [-0.250; +0.355] | — | — | 1.22 |
| `rising_wedge` | 1:1 | return_matched | ±0.50 | 121 | 2398 | -0.134 | [-0.319; +0.053] | — | — | 1.05 |
| `rising_wedge` | 2:1 | return_matched | ±0.50 | 121 | 2398 | +0.039 | [-0.256; +0.354] | — | — | 1.19 |
| `rising_wedge` | 1:1 | standard | — | 121 | 2401 | +0.033 | [-0.155; +0.223] | — | — | 1.04 |
| `rising_wedge` | 2:1 | standard | — | 121 | 2401 | +0.236 | [-0.050; +0.531] | — | — | 1.13 |
| `rounding_bottom` | 1:1 | return_matched | ±0.15 | 430 | 7417 | +0.097 | [-0.060; +0.243] | — | — | 1.57 |
| `rounding_bottom` | 2:1 | return_matched | ±0.15 | 430 | 7417 | +0.101 | [-0.196; +0.465] | — | — | 2.54 |
| `rounding_bottom` | 1:1 | return_matched | ±0.25 | 430 | 7402 | +0.105 | [-0.056; +0.252] | — | — | 1.59 |
| `rounding_bottom` | 2:1 | return_matched | ±0.25 | 430 | 7402 | +0.099 | [-0.187; +0.460] | — | — | 2.50 |
| `rounding_bottom` | 1:1 | return_matched | ±0.50 | 430 | 7416 | +0.081 | [-0.081; +0.235] | — | — | 1.63 |
| `rounding_bottom` | 2:1 | return_matched | ±0.50 | 430 | 7416 | +0.089 | [-0.203; +0.460] | — | — | 2.52 |
| `rounding_bottom` | 1:1 | standard | — | 430 | 7557 | +0.124 | [-0.035; +0.293] | — | — | 1.70 |
| `rounding_bottom` | 2:1 | standard | — | 430 | 7557 | +0.171 | [-0.127; +0.542] | — | — | 2.59 |

---

## Yöntem

* Yön: short · Bariyerler ATR tabanlı, 2:1 ve 1:1 (K-16)
* Gölge: aynı ay + farklı sembol; ön-getiri eşleştirmede ek olarak ±band σ
* GA: ay-bloklu bootstrap (K-12/F4.5), 10.000 tekrar
* Bonferroni: aile = 40 test, ikinci bootstrap geçişiyle
* **Yapısal imza filtresi açık** — örneklem gerçekten o formasyon

Üretim: `python -m tools.f46_proxy_test` · ham veri `data/f3/f46_raw.json`

---

## Okuma uyarısı

Anlamlılık kaybının büyük kısmı **güç kaybıdır, etki kaybı değil** — F4.8
bunu ayrı ölçtü: nokta tahminlerinin korelasyonu 0,83 mertebesinde, ortalama
değişim 0,07R civarında. *"Anlamlı çıkmadı"* ile *"etki yok"* aynı şey
değildir.

---

> **Güncelleme (10 Eylül 2026).** Bu rapor bayat bir hedef listesiyle ve yalnız 1d'de
> koşulmuştu. Motor değiştikten sonra hedefler güncel F4.5'ten türetilerek ve 4h'de de
> yeniden sınandı: 1d'de iki şablon eşleştirmeden sonra %95'te anlamlı kalıyor, **hiçbiri
> 4h'de replike etmiyor**. Manşet ayakta ama gerekçesi değişti — bkz.
> [11-yeniden-olcum.md](11-yeniden-olcum.md).
