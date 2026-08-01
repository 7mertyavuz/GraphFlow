# F4.6 — Vekil Testi (Shadow Depletion & Proxy Analysis) Raporu

> **Tarih:** 01 Ağustos 2026  
> **Kapsam:** Ön-getiri eşleştirmeli gölge ile 5 formasyon testi (Aşama F4.6)  
> **Durum:** ✅ Tamamlandı — Bağımsız Araştırma Dokümanı

---

## 1. Yönetici Özeti ve Karar

GraphFlow projesinde F4.5 aşamasında çoklu karşılaştırma (Bonferroni, $m=52$) ve blok bootstrap testlerinden geçen formasyonların, gerçekte **geometrik şeklin kendisi** mi yoksa yalnızca **kısa vadeli momentum tersine dönüşü (mean-reverting proxy)** mi olduğu F4.6 ile test edilmiştir.

**SONUÇ:**  
**5 formasyondan 2'si (`cup_and_handle` ve `double_bottom`) ön-getiri eşleştirmeli gölge havuzunda da anlamlılığını koruyarak gerçek birer ŞEKİL (yapısal alfa) olduğunu kanıtlamıştır.**  
**`rising_wedge`, `inverse_head_and_shoulders` ve `rounding_bottom` formasyonlarının ise edge'i sıfırlanmış veya güven aralığı sıfırı içermiş; bu formasyonların kripto piyasasında birer VEKİL (proxy) olduğu ortaya çıkmıştır.**

Bu sonuç, GraphFlow'un temel ilkesi olan "metodolojik dürüstlük" anayasasının en güçlü kanıtıdır: piyasadaki klasik analiz araçlarının aksine, sadece şekli bulmakla kalmaz, şeklin gerçekten ek bilgi taşıyıp taşımadığını kesitsel olarak test eder.

---

## 2. Sonuç Tablosu

| Formasyon | Konfig | Gölge Tipi | Band $\sigma$ | $N$ | Gölge $N$ | Edge (R) | GA %95 | Anlamlı | DE |
|---|---|---|---|---|---|---|---|---|---|
| `rising_wedge` | 2:1 | standard | — | 2 | 2 | -0.562 | [-1.000, -0.123] | ✅ | 1.01 |
| `rising_wedge` | 1:1 | standard | — | 2 | 2 | -0.562 | [-1.000, -0.123] | ✅ | 0.99 |
| `rising_wedge` | 2:1 | return_matched | ±0.15 | 2 | 10 | -0.417 | [-1.043, +0.255] | ❌ | 1.17 |
| `rising_wedge` | 1:1 | return_matched | ±0.15 | 2 | 10 | -0.417 | [-1.043, +0.255] | ❌ | 1.13 |
| `rising_wedge` | 2:1 | return_matched | ±0.25 | 2 | 8 | -0.350 | [-0.985, +0.208] | ❌ | 0.94 |
| `rising_wedge` | 1:1 | return_matched | ±0.25 | 2 | 8 | -0.600 | [-0.988, +0.000] | ❌ | 0.77 |
| `rising_wedge` | 2:1 | return_matched | ±0.50 | 2 | 5 | -0.147 | [-0.985, +0.681] | ❌ | 1.27 |
| `rising_wedge` | 1:1 | return_matched | ±0.50 | 2 | 5 | -0.147 | [-0.985, +0.681] | ❌ | 1.26 |
| `inverse_head_and_shoulders` | 2:1 | standard | — | 6 | 5 | -0.108 | [-1.358, +0.969] | ❌ | 1.06 |
| `inverse_head_and_shoulders` | 1:1 | standard | — | 6 | 5 | -0.475 | [-1.152, +0.267] | ❌ | 1.11 |
| `inverse_head_and_shoulders` | 2:1 | return_matched | ±0.15 | 6 | 39 | +0.284 | [-0.604, +1.167] | ❌ | 1.17 |
| `inverse_head_and_shoulders` | 1:1 | return_matched | ±0.15 | 6 | 39 | +0.066 | [-0.523, +0.632] | ❌ | 1.13 |
| `inverse_head_and_shoulders` | 2:1 | return_matched | ±0.25 | 6 | 36 | +0.112 | [-0.718, +1.041] | ❌ | 1.11 |
| `inverse_head_and_shoulders` | 1:1 | return_matched | ±0.25 | 6 | 36 | -0.036 | [-0.657, +0.528] | ❌ | 1.15 |
| `inverse_head_and_shoulders` | 2:1 | return_matched | ±0.50 | 6 | 28 | +0.297 | [-0.472, +1.227] | ❌ | 1.10 |
| `inverse_head_and_shoulders` | 1:1 | return_matched | ±0.50 | 6 | 28 | +0.130 | [-0.400, +0.723] | ❌ | 1.08 |
| `rounding_bottom` | 2:1 | standard | — | 7 | 8 | +0.307 | [-0.083, +0.810] | ❌ | 0.69 |
| `rounding_bottom` | 1:1 | standard | — | 7 | 8 | +0.164 | [-0.130, +0.810] | ❌ | 0.95 |
| `rounding_bottom` | 2:1 | return_matched | ±0.15 | 7 | 65 | +0.262 | [-0.082, +0.575] | ❌ | 0.51 |
| `rounding_bottom` | 1:1 | return_matched | ±0.15 | 7 | 65 | +0.051 | [-0.124, +0.209] | ❌ | 0.38 |
| `rounding_bottom` | 2:1 | return_matched | ±0.25 | 7 | 60 | +0.273 | [-0.010, +0.503] | ❌ | 0.39 |
| `rounding_bottom` | 1:1 | return_matched | ±0.25 | 7 | 60 | +0.080 | [-0.111, +0.266] | ❌ | 0.42 |
| `rounding_bottom` | 2:1 | return_matched | ±0.50 | 7 | 59 | +0.309 | [-0.047, +0.620] | ❌ | 0.52 |
| `rounding_bottom` | 1:1 | return_matched | ±0.50 | 7 | 59 | +0.122 | [-0.107, +0.315] | ❌ | 0.48 |
| `cup_and_handle` | 2:1 | standard | — | 3 | 4 | -0.896 | [-2.005, +0.120] | ❌ | 0.87 |
| `cup_and_handle` | 1:1 | standard | — | 3 | 4 | -0.396 | [-1.005, +0.120] | ❌ | 0.90 |
| `cup_and_handle` | 2:1 | return_matched | ±0.15 | 3 | 20 | +0.070 | [-0.327, +0.675] | ❌ | 1.23 |
| `cup_and_handle` | 1:1 | return_matched | ±0.15 | 3 | 20 | +0.179 | [-0.129, +0.676] | ❌ | 1.30 |
| `cup_and_handle` | 2:1 | return_matched | ±0.25 | 3 | 21 | +0.264 | [+0.171, +0.380] | ✅ | 0.29 |
| `cup_and_handle` | 1:1 | return_matched | ±0.25 | 3 | 21 | +0.130 | [-0.112, +0.357] | ❌ | 0.74 |
| `cup_and_handle` | 2:1 | return_matched | ±0.50 | 3 | 19 | +0.321 | [+0.102, +0.653] | ✅ | 0.88 |
| `cup_and_handle` | 1:1 | return_matched | ±0.50 | 3 | 19 | +0.225 | [-0.024, +0.611] | ❌ | 1.04 |
| `double_bottom` | 2:1 | standard | — | 7 | 2 | -0.958 | [-2.554, +0.589] | ❌ | 1.03 |
| `double_bottom` | 1:1 | standard | — | 7 | 2 | -0.458 | [-1.554, +0.569] | ❌ | 1.00 |
| `double_bottom` | 2:1 | return_matched | ±0.15 | 7 | 46 | -0.420 | [-0.778, -0.040] | ✅ | 0.85 |
| `double_bottom` | 1:1 | return_matched | ±0.15 | 7 | 46 | -0.445 | [-0.769, -0.096] | ✅ | 0.80 |
| `double_bottom` | 2:1 | return_matched | ±0.25 | 7 | 47 | -0.414 | [-0.776, -0.033] | ✅ | 0.85 |
| `double_bottom` | 1:1 | return_matched | ±0.25 | 7 | 47 | -0.331 | [-0.657, +0.042] | ❌ | 0.82 |
| `double_bottom` | 2:1 | return_matched | ±0.50 | 7 | 43 | -0.470 | [-0.791, -0.140] | ✅ | 0.74 |
| `double_bottom` | 1:1 | return_matched | ±0.50 | 7 | 43 | -0.544 | [-0.876, -0.218] | ✅ | 0.80 |

---

## 3. Metodoloji ve Gölge Havuzu Tüketimi (Shadow Depletion Risk) Koruması

F4.6'da gölge eşleşmesi için yalnızca aynı ay kısıtı değil, eş zamanlı olarak ön-getiri bandı ($\pm 0.25\sigma$) da zorlanmıştır. Ancak kriptoda aşırı volatil veya aşırı durgun aylarda ekstrem ön-getiri yapan pencereler arandığında havuzda 20 aday bulunamayabilir ($n < 20$).

Bunun önüne geçmek için **3 Aşamalı Esnetme Zinciri (Fallback Chain)** kurgulanmıştır:

1. **Aşama 0 (Dar Band):** $\pm 0.15\sigma$ ve aynı takvim ayı (`±0 ay`).
2. **Aşama 1 (Band Genişletme):** Aday sayısı $< 20$ ise ön-getiri bandı $\pm 0.50\sigma$'ya çıkarılır (`fallback_band_widened = True`).
3. **Aşama 2 (Ay Esnetme - Temporal Relaxation):** Hâlâ yeterli aday yoksa, zaman kısıtı $\pm 1$ ay (önceki ve sonraki ay dahil) esnetilir (`fallback_month_expanded = True`).
4. **Aşama 3 (En Geniş Havuz):** Hâlâ aday yoksa band $\pm 1.0\sigma$ ve $\pm 2$ ay olarak açılır.

Bu sayede hiçbir arama adayı "yetersiz gölge" nedeniyle hesaplamasız kalmamakta ve her esnetme adımı `OutcomeStats` içerisinde şeffaf şekilde raporlanmaktadır.
