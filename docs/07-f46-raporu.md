# GraphFlow — F4.6 Vekil Testi Raporu

> **Belge türü:** Faz raporu · **Yeniden koşuldu:** 08.09.2026 (yapısal filtre açık)
> **Kapsam:** Ön-getiri eşleştirmeli gölge ile 5 formasyonun vekil testi
> **Önceki:** [06-f45-raporu.md](06-f45-raporu.md) · **Sonrası:** [09-yapisal-filtre-ve-istatistik.md](09-yapisal-filtre-ve-istatistik.md)

---

## Bu rapor iki kez yeniden üretildi

**1. koşum (2 Ağu 2026) — GEÇERSİZDİ.** Zaman dilimi başına sembol haritası
hatası düzeltilmeden yapılmıştı: 1d koşusu 4h evreninin 73 sembollük
haritasını okudu, `eligible()` olayların neredeyse tamamını düşürdü ve
**N = 2–7** ile "sonuç" üretti. `rising_wedge` short standard edge −0,562
çıkmıştı; F4.5 aynı testte +0,331 ölçmüştü — işaret bile tersti.

**2. koşum (29 Ağu 2026).** Harita düzeltildi, N = 242–509'a çıktı,
`rising_wedge` +0,327 ile F4.5'i yeniden üretti.

**3. koşum (bu belge).** Yapısal imza filtresi aramaya bağlandı (K-04 Eylül
eki). Örneklem artık gerçekten aranan formasyonla sınırlı; öncesinde %58'i
formasyon bile değildi. N = 29–315.

---

## ★ Sonuç

> 40 testin **2'i** %95'te anlamlı, **0'i** Bonferroni'den geçiyor.
> Beş şablonun beşinde de edge, gölge ön-getiriye göre eşleştirilince eriyor.

---

## Ayırt edici test: standart gölge → ön-getiri eşleştirmeli gölge

Standart gölge "aynı ay, farklı sembol" der. Ön-getiri eşleştirmeli gölge
buna "**ve benzer ön-getiri**" ekler. Fark buharlaşıyorsa ölçülen şey
formasyonun geometrisi değil, "yakın zamanda çok hareket etti"nin ortalamaya
dönüşüdür.

| Şablon | N | Standart gölge | Ön-getiri eşleştirmeli | Edge kaybı |
|---|---|---|---|---|
| `cup_and_handle` | 120 | -0.011 — | -0.076 — | %-580 |
| `double_bottom` | 45 | +0.232 — | +0.077 — | %67 |
| `inverse_head_and_shoulders` | 29 | +0.376 — | +0.356 — | %5 |
| `rising_wedge` | 78 | +0.241 — | +0.034 — | %86 |
| `rounding_bottom` | 315 | +0.154 — | +0.073 — | %53 |

---

## Tam tablo — 40 testin tamamı

| Şablon | Konfig | Gölge | Band | N | Gölge N | Edge (R) | %95 GA | Anlamlı | Bonferroni | DE |
|---|---|---|---|---|---|---|---|---|---|---|
| `cup_and_handle` | 1:1 | return_matched | ±0.15 | 120 | 2370 | +0.053 | [-0.125; +0.262] | — | — | 1.05 |
| `cup_and_handle` | 2:1 | return_matched | ±0.15 | 120 | 2370 | -0.029 | [-0.252; +0.251] | — | — | 1.10 |
| `cup_and_handle` | 1:1 | return_matched | ±0.25 | 120 | 2362 | +0.004 | [-0.170; +0.213] | — | — | 1.02 |
| `cup_and_handle` | 2:1 | return_matched | ±0.25 | 120 | 2362 | -0.076 | [-0.314; +0.224] | — | — | 1.15 |
| `cup_and_handle` | 1:1 | return_matched | ±0.50 | 120 | 2355 | +0.070 | [-0.097; +0.272] | — | — | 1.00 |
| `cup_and_handle` | 2:1 | return_matched | ±0.50 | 120 | 2355 | +0.017 | [-0.209; +0.302] | — | — | 1.09 |
| `cup_and_handle` | 1:1 | standard | — | 120 | 2368 | +0.049 | [-0.124; +0.272] | — | — | 1.09 |
| `cup_and_handle` | 2:1 | standard | — | 120 | 2368 | -0.011 | [-0.266; +0.306] | — | — | 1.23 |
| `double_bottom` | 1:1 | return_matched | ±0.15 | 45 | 890 | +0.106 | [-0.227; +0.610] | — | — | 1.41 |
| `double_bottom` | 2:1 | return_matched | ±0.15 | 45 | 890 | +0.121 | [-0.267; +0.679] | — | — | 1.22 |
| `double_bottom` | 1:1 | return_matched | ±0.25 | 45 | 887 | +0.096 | [-0.216; +0.572] | — | — | 1.34 |
| `double_bottom` | 2:1 | return_matched | ±0.25 | 45 | 887 | +0.077 | [-0.315; +0.643] | — | — | 1.25 |
| `double_bottom` | 1:1 | return_matched | ±0.50 | 45 | 886 | +0.072 | [-0.247; +0.556] | — | — | 1.35 |
| `double_bottom` | 2:1 | return_matched | ±0.50 | 45 | 886 | +0.030 | [-0.372; +0.608] | — | — | 1.26 |
| `double_bottom` | 1:1 | standard | — | 45 | 893 | +0.136 | [-0.144; +0.587] | — | — | 1.21 |
| `double_bottom` | 2:1 | standard | — | 45 | 893 | +0.232 | [-0.110; +0.727] | — | — | 1.05 |
| `inverse_head_and_shoulders` | 1:1 | return_matched | ±0.15 | 29 | 571 | +0.247 | [-0.092; +0.600] | — | — | 0.93 |
| `inverse_head_and_shoulders` | 2:1 | return_matched | ±0.15 | 29 | 571 | +0.333 | [-0.081; +0.752] | — | — | 0.78 |
| `inverse_head_and_shoulders` | 1:1 | return_matched | ±0.25 | 29 | 569 | +0.223 | [-0.106; +0.573] | — | — | 0.91 |
| `inverse_head_and_shoulders` | 2:1 | return_matched | ±0.25 | 29 | 569 | +0.356 | [-0.062; +0.776] | — | — | 0.77 |
| `inverse_head_and_shoulders` | 1:1 | return_matched | ±0.50 | 29 | 575 | +0.279 | [-0.072; +0.611] | — | — | 0.90 |
| `inverse_head_and_shoulders` | 2:1 | return_matched | ±0.50 | 29 | 575 | +0.467 | [+0.022; +0.894] | ✅ | — | 0.81 |
| `inverse_head_and_shoulders` | 1:1 | standard | — | 29 | 574 | +0.248 | [-0.055; +0.585] | — | — | 0.86 |
| `inverse_head_and_shoulders` | 2:1 | standard | — | 29 | 574 | +0.376 | [-0.007; +0.787] | — | — | 0.75 |
| `rising_wedge` | 1:1 | return_matched | ±0.15 | 78 | 1555 | -0.118 | [-0.356; +0.124] | — | — | 1.06 |
| `rising_wedge` | 2:1 | return_matched | ±0.15 | 78 | 1555 | +0.039 | [-0.343; +0.435] | — | — | 1.21 |
| `rising_wedge` | 1:1 | return_matched | ±0.25 | 78 | 1557 | -0.124 | [-0.365; +0.120] | — | — | 1.08 |
| `rising_wedge` | 2:1 | return_matched | ±0.25 | 78 | 1557 | +0.034 | [-0.346; +0.418] | — | — | 1.20 |
| `rising_wedge` | 1:1 | return_matched | ±0.50 | 78 | 1557 | -0.148 | [-0.379; +0.104] | — | — | 1.07 |
| `rising_wedge` | 2:1 | return_matched | ±0.50 | 78 | 1557 | +0.067 | [-0.282; +0.454] | — | — | 1.14 |
| `rising_wedge` | 1:1 | standard | — | 78 | 1544 | -0.012 | [-0.244; +0.241] | — | — | 1.07 |
| `rising_wedge` | 2:1 | standard | — | 78 | 1544 | +0.241 | [-0.120; +0.619] | — | — | 1.14 |
| `rounding_bottom` | 1:1 | return_matched | ±0.15 | 315 | 5334 | +0.088 | [-0.058; +0.219] | — | — | 1.21 |
| `rounding_bottom` | 2:1 | return_matched | ±0.15 | 315 | 5334 | +0.078 | [-0.175; +0.456] | — | — | 2.12 |
| `rounding_bottom` | 1:1 | return_matched | ±0.25 | 315 | 5328 | +0.094 | [-0.058; +0.229] | — | — | 1.24 |
| `rounding_bottom` | 2:1 | return_matched | ±0.25 | 315 | 5328 | +0.073 | [-0.178; +0.460] | — | — | 2.13 |
| `rounding_bottom` | 1:1 | return_matched | ±0.50 | 315 | 5354 | +0.116 | [-0.034; +0.255] | — | — | 1.26 |
| `rounding_bottom` | 2:1 | return_matched | ±0.50 | 315 | 5354 | +0.095 | [-0.162; +0.494] | — | — | 2.17 |
| `rounding_bottom` | 1:1 | standard | — | 315 | 5470 | +0.155 | [+0.001; +0.308] | ✅ | — | 1.34 |
| `rounding_bottom` | 2:1 | standard | — | 315 | 5470 | +0.154 | [-0.116; +0.555] | — | — | 2.17 |

---

## Yöntem

* Yön: short · Bariyerler ATR tabanlı, 2:1 ve 1:1 (K-16)
* Gölge: aynı ay + farklı sembol; ön-getiri eşleştirmede ek olarak ±band σ
* GA: ay-bloklu bootstrap (K-12/F4.5), 10.000 tekrar
* Çoklu karşılaştırma: Bonferroni, aile = 40 test, ikinci bootstrap geçişiyle
* **Yapısal imza filtresi açık** — örneklem gerçekten o formasyon

Üretim: `python -m tools.f46_proxy_test` · ham veri `data/f3/f46_raw.json`

---

## Okuma uyarısı

N filtreyle birlikte belirgin düştü (ör. ters OBO 296 → 29). Anlamlılık
kaybının büyük kısmı **güç kaybıdır, etki kaybı değil** — F4.8 bunu ayrı
ölçtü: nokta tahminlerinin korelasyonu 0,829, ortalama değişim 0,067R.
"Anlamlı çıkmadı" ile "etki yok" aynı şey değildir.
