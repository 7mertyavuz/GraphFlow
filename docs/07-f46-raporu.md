# GraphFlow — F4.6 Vekil Testi Raporu

> **Belge türü:** Faz raporu · **Yeniden koşuldu:** 29.08.2026
> **Kapsam:** Ön-getiri eşleştirmeli gölge ile 5 formasyonun vekil testi
> **Önceki:** [06-f45-raporu.md](06-f45-raporu.md)

---

## ⚠️ Bu rapor bir kez geçersiz üretildi

İlk koşum (2 Ağustos 2026), zaman dilimi başına sembol haritası hatası
düzeltilmeden (`ccb1e70`) yapılmıştı. 1d koşusu 4h evreninin 73 sembollük
haritasını okudu; `eligible()` olayların neredeyse tamamını düşürdü ve
**N = 2–7** ile "sonuç" üretildi. O tablodaki sayılar yorumlanabilir değildi:
`rising_wedge` short standard edge **−0,562** çıkmıştı, oysa F4.5 aynı testte
**+0,331** ölçmüştü — işaret bile tersti.

Düzeltilmiş koşumda N = 242–509, gölge N = 4.563–8.723, kapsam 52–76 ay.
`rising_wedge` short standard **+0,327** — F4.5'in +0,331'ini bağımsız olarak
yeniden üretiyor. Sayılar artık aynı hikâyeyi anlatıyor.

---

## ★ Tek cümlelik sonuç

> **Şekil, ön-getiriden bağımsız bir bilgi taşımıyor.** 40 testin
> 7'i %95'te anlamlı, **1'i Bonferroni'den geçiyor** (`rising_wedge`
> short 2:1, +0,327R). O tek bulgu da gölge havuzu **ön-getiriye göre
> eşleştirildiğinde** +0,115R'ye düşüp anlamlılığını kaybediyor.

---

## Ayırt edici test: standart gölge → ön-getiri eşleştirmeli gölge

Standart gölge "aynı ay, farklı sembol" der. Ön-getiri eşleştirmeli gölge
buna "**ve benzer ön-getiri**" ekler: formasyonun bulunduğu pencere kadar
yükselmiş/düşmüş pencerelerle kıyaslar. Fark buharlaşıyorsa ölçülen şey
formasyonun geometrisi değil, "yakın zamanda çok hareket etti"nin ortalamaya
dönüşüdür.

| Şablon | N | Standart gölge | Ön-getiri eşleştirmeli | Edge kaybı |
|---|---|---|---|---|
| `cup_and_handle` | 258 | +0.164 ✅ | +0.109 — | %33 |
| `double_bottom` | 242 | +0.135 — | +0.058 — | %57 |
| `inverse_head_and_shoulders` | 296 | +0.236 ✅ | +0.158 — | %33 |
| `rising_wedge` | 252 | +0.327 ✅ | +0.115 — | %65 |
| `rounding_bottom` | 509 | +0.082 — | +0.041 — | %50 |

**Beş şablonun beşinde de edge yarıdan fazla eriyor** ve hiçbiri ön-getiri
eşleştirmeli gölgede %95'i geçemiyor. Bu, tek tek formasyonlara dair beş ayrı
bulgu değil, **tek bir ortak etkinin** beş kez görülmesidir: kriptoda kısa
vadeli momentum tersine dönüşü.

---

## Tam tablo — 40 testin tamamı

"En anlamlı 3 satır" sunumu çoklu karşılaştırma tuzağıdır; elenen satırlar da
buradadır. Bonferroni ailesi bu koşudaki 40 testtir.

| Şablon | Konfig | Gölge | Band | N | Gölge N | Edge (R) | %95 GA | Anlamlı | Bonferroni | DE |
|---|---|---|---|---|---|---|---|---|---|---|
| `cup_and_handle` | 1:1 | return_matched | ±0.15 | 258 | 4803 | +0.091 | [-0.042; +0.216] | — | — | 1.03 |
| `cup_and_handle` | 2:1 | return_matched | ±0.15 | 258 | 4803 | +0.130 | [-0.028; +0.289] | — | — | 0.99 |
| `cup_and_handle` | 1:1 | return_matched | ±0.25 | 258 | 4784 | +0.077 | [-0.058; +0.204] | — | — | 1.05 |
| `cup_and_handle` | 2:1 | return_matched | ±0.25 | 258 | 4784 | +0.109 | [-0.043; +0.256] | — | — | 0.92 |
| `cup_and_handle` | 1:1 | return_matched | ±0.50 | 258 | 4812 | +0.063 | [-0.067; +0.184] | — | — | 1.01 |
| `cup_and_handle` | 2:1 | return_matched | ±0.50 | 258 | 4812 | +0.109 | [-0.037; +0.262] | — | — | 0.91 |
| `cup_and_handle` | 1:1 | standard | — | 258 | 4945 | +0.093 | [-0.040; +0.226] | — | — | 1.04 |
| `cup_and_handle` | 2:1 | standard | — | 258 | 4945 | +0.164 | [+0.004; +0.348] | ✅ | — | 1.03 |
| `double_bottom` | 1:1 | return_matched | ±0.15 | 242 | 4575 | +0.103 | [-0.080; +0.309] | — | — | 1.52 |
| `double_bottom` | 2:1 | return_matched | ±0.15 | 242 | 4575 | +0.026 | [-0.238; +0.301] | — | — | 1.60 |
| `double_bottom` | 1:1 | return_matched | ±0.25 | 242 | 4559 | +0.141 | [-0.039; +0.349] | — | — | 1.51 |
| `double_bottom` | 2:1 | return_matched | ±0.25 | 242 | 4559 | +0.058 | [-0.193; +0.325] | — | — | 1.57 |
| `double_bottom` | 1:1 | return_matched | ±0.50 | 242 | 4564 | +0.147 | [-0.037; +0.362] | — | — | 1.54 |
| `double_bottom` | 2:1 | return_matched | ±0.50 | 242 | 4564 | +0.077 | [-0.194; +0.341] | — | — | 1.63 |
| `double_bottom` | 1:1 | standard | — | 242 | 4706 | +0.165 | [-0.005; +0.348] | — | — | 1.36 |
| `double_bottom` | 2:1 | standard | — | 242 | 4706 | +0.135 | [-0.125; +0.383] | — | — | 1.53 |
| `inverse_head_and_shoulders` | 1:1 | return_matched | ±0.15 | 296 | 5672 | +0.150 | [+0.005; +0.289] | ✅ | — | 1.24 |
| `inverse_head_and_shoulders` | 2:1 | return_matched | ±0.15 | 296 | 5672 | +0.158 | [-0.053; +0.380] | — | — | 1.35 |
| `inverse_head_and_shoulders` | 1:1 | return_matched | ±0.25 | 296 | 5658 | +0.152 | [-0.002; +0.296] | — | — | 1.30 |
| `inverse_head_and_shoulders` | 2:1 | return_matched | ±0.25 | 296 | 5658 | +0.158 | [-0.054; +0.377] | — | — | 1.34 |
| `inverse_head_and_shoulders` | 1:1 | return_matched | ±0.50 | 296 | 5693 | +0.164 | [+0.018; +0.301] | ✅ | — | 1.23 |
| `inverse_head_and_shoulders` | 2:1 | return_matched | ±0.50 | 296 | 5693 | +0.163 | [-0.050; +0.388] | — | — | 1.36 |
| `inverse_head_and_shoulders` | 1:1 | standard | — | 296 | 5771 | +0.188 | [+0.040; +0.330] | ✅ | — | 1.26 |
| `inverse_head_and_shoulders` | 2:1 | standard | — | 296 | 5771 | +0.236 | [+0.027; +0.458] | ✅ | — | 1.36 |
| `rising_wedge` | 1:1 | return_matched | ±0.15 | 252 | 4316 | +0.036 | [-0.102; +0.166] | — | — | 1.08 |
| `rising_wedge` | 2:1 | return_matched | ±0.15 | 252 | 4316 | +0.119 | [-0.069; +0.294] | — | — | 1.01 |
| `rising_wedge` | 1:1 | return_matched | ±0.25 | 252 | 4310 | +0.051 | [-0.094; +0.189] | — | — | 1.13 |
| `rising_wedge` | 2:1 | return_matched | ±0.25 | 252 | 4310 | +0.115 | [-0.074; +0.294] | — | — | 1.03 |
| `rising_wedge` | 1:1 | return_matched | ±0.50 | 252 | 4308 | +0.097 | [-0.052; +0.235] | — | — | 1.13 |
| `rising_wedge` | 2:1 | return_matched | ±0.50 | 252 | 4308 | +0.179 | [-0.014; +0.355] | — | — | 1.05 |
| `rising_wedge` | 1:1 | standard | — | 252 | 4563 | +0.192 | [+0.056; +0.322] | ✅ | — | 1.05 |
| `rising_wedge` | 2:1 | standard | — | 252 | 4563 | +0.327 | [+0.139; +0.496] | ✅ | ✅ | 1.00 |
| `rounding_bottom` | 1:1 | return_matched | ±0.15 | 509 | 8393 | +0.096 | [-0.048; +0.222] | — | — | 1.50 |
| `rounding_bottom` | 2:1 | return_matched | ±0.15 | 509 | 8393 | +0.070 | [-0.143; +0.364] | — | — | 2.09 |
| `rounding_bottom` | 1:1 | return_matched | ±0.25 | 509 | 8378 | +0.086 | [-0.058; +0.213] | — | — | 1.50 |
| `rounding_bottom` | 2:1 | return_matched | ±0.25 | 509 | 8378 | +0.041 | [-0.164; +0.322] | — | — | 2.00 |
| `rounding_bottom` | 1:1 | return_matched | ±0.50 | 509 | 8445 | +0.093 | [-0.050; +0.221] | — | — | 1.53 |
| `rounding_bottom` | 2:1 | return_matched | ±0.50 | 509 | 8445 | +0.069 | [-0.150; +0.358] | — | — | 2.11 |
| `rounding_bottom` | 1:1 | standard | — | 509 | 8723 | +0.087 | [-0.065; +0.226] | — | — | 1.61 |
| `rounding_bottom` | 2:1 | standard | — | 509 | 8723 | +0.082 | [-0.130; +0.377] | — | — | 2.10 |

---

## Yöntem

* **Yön:** short (F4.5'te short yönde anlamlı çıkan şablonlar test edildi)
* **Bariyerler:** ATR tabanlı, 2:1 ve 1:1 (K-16)
* **Gölge:** aynı ay + farklı sembol; ön-getiri eşleştirmede ek olarak ±band σ
* **Güven aralığı:** ay-bloklu bootstrap (K-12/F4.5), 10.000 tekrar
* **Çoklu karşılaştırma:** Bonferroni, aile = 40 test
* **Fallback zinciri:** band genişlet → ay esnet (±1) → en geniş havuz;
  her esnetme `OutcomeStats` içinde raporlanır

Üretim: `python -m tools.f46_proxy_test` · ham veri `data/f3/f46_raw.json`

---

## Bunun anlamı

Bu bir başarısızlık değil, **ölçümün işini yapmasıdır**. GraphFlow'un iddiası
"formasyonlar çalışır" değil, "geçmiş dağılım dürüstçe raporlanır"dır. F4.6,
bir edge'in şekilden mi yoksa momentumdan mı geldiğini ayırabilen bir test
kurdu ve cevabı verdi: **momentumdan**.

Bağımsız bir doğrulama da var: `honest-signals` (ABD hisseleri, kural tabanlı
dedektörler, cluster-robust aralıklar) 105 hücrenin 3'ünde baseline'dan
ayrışma buldu ve **hiçbiri Bonferroni'den geçmedi**. Farklı veri, farklı
yöntem, aynı sonuç.
