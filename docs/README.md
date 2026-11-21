# Documentation · Belgeler

The documents in this folder are written in **Turkish**. This index describes each one in English and Turkish.

Bu klasördeki belgeler **Türkçe** yazılmıştır. Bu dizin her birini İngilizce ve Türkçe tanıtır.

---

## Design · Tasarım

| Document | English | Türkçe |
|---|---|---|
| [00-tasarim-kararlari.md](00-tasarim-kararlari.md) | **Design decision record.** 26 architectural decisions (`K-01 … K-26`), each with its rationale and the alternatives that were rejected. Start here before changing anything structural. | **Tasarım karar kaydı.** 26 mimari karar (`K-01 … K-26`), gerekçeleri ve reddedilen alternatifleriyle. Yapısal bir şeyi değiştirmeden önce buradan başlayın. |
| [01-mimari.md](01-mimari.md) | **Architecture.** Data layer, normalization, the search cascade, outcome engine, API contract, repository layout and performance budget. | **Mimari.** Veri katmanı, normalizasyon, arama kaskadı, sonuç motoru, API sözleşmesi, depo yapısı ve performans bütçesi. |

## Measurement reports · Ölçüm raporları

Each report records one validation step: what was asked, how it was measured, what was found — including findings that were later overturned.

Her rapor bir doğrulama adımını kaydeder: ne soruldu, nasıl ölçüldü, ne bulundu — sonradan çürütülen bulgular dahil.

| Report | English | Türkçe |
|---|---|---|
| [03 · Validation](03-f3-dogrulama-raporu.md) | Eye test, negative controls (noise and whipsaw must not match), threshold calibration on real data, and the Stage 2 metric A/B that selected hybrid DTW. | Göz testi, negatif kontroller (gürültü ve testere dişi eşleşmemeli), gerçek veriyle eşik kalibrasyonu ve hibrit DTW'yi seçen Aşama 2 A/B'si. |
| [04 · Cleanup](04-f35-raporu.md) | Query-relative percentile scoring, pegged-pair filter, data-freshness and continuity invariants. | Sorgu-göreli yüzdelik skorlama, sabitlenmiş parite filtresi, veri tazeliği ve süreklilik invariantları. |
| [05 · Outcome engine](05-f4-raporu.md) | Triple-barrier outcomes with ATR barriers and the time-matched shadow baseline. | ATR bariyerli triple-barrier sonuçları ve zaman-eşleştirmeli gölge baseline. |
| [06 · Statistical hardening](06-f45-raporu.md) | Month-block bootstrap (i.i.d. understated uncertainty by ~29%), short direction, Bonferroni. | Ay-bloklu bootstrap (iid belirsizliği ~%29 eksik ölçüyordu), short yönü, Bonferroni. |
| [07 · Proxy test](07-f46-raporu.md) | Is a pattern's edge about its shape, or a proxy for momentum reversal? Return-matched shadow baseline. | Formasyonun edge'i şeklinden mi, yoksa momentum tersine dönüşünün vekili mi? Ön-getiri eşleştirmeli gölge. |
| [08 · Timeframe replication](08-zaman-dilimi-caprazlama.md) | The same 56 tests on 1d and 4h; how fragile findings at the significance boundary are. | Aynı 56 test 1d ve 4h'de; anlamlılık sınırındaki bulguların ne kadar kırılgan olduğu. |
| [09 · Structural filter](09-yapisal-filtre-ve-istatistik.md) | What the peak/trough filter did to the statistics: power dropped, the effect held. | Tepe/dip filtresinin istatistiğe etkisi: güç düştü, etki durdu. |
| [10 · Formation audit](10-formasyon-denetimi.md) | Are results really the requested pattern? Independent audit of 12 formations, ground-truth benchmark, the stability gates (K-20) and trend-line filter (K-21). | Sonuçlar gerçekten istenen formasyon mu? 12 formasyonun bağımsız denetimi, ground truth ölçümü, kararlılık kapıları (K-20) ve trend çizgisi filtresi (K-21). |
| [11 · Re-measurement](11-yeniden-olcum.md) | The engine changed, so every finding was regenerated; engine fingerprinting so stale tables are detected; invariance sweep. | Motor değişti, bulgular yeniden üretildi; bayat tabloları yakalayan motor parmak izi; değişmezlik taraması. |
| [12 · Null sample](12-null-orneklemi.md) | Part of the findings' fragility was the engine's own noise: the percentile threshold rested on ~5 order statistics of a 2,000-window null. Seed-only variation moved the 1d significant-cell count between 3 and 12. Null raised to 20,000 (DTW kernel made 3.7× faster, bit-identical); the one cell robust across seeds and timeframes is rising wedge long 2:1. | Bulguların kırılganlığının bir kısmı motorun kendi gürültüsüydü: yüzdelik eşik 2.000'lik null'un ~5 sıra istatistiğine dayanıyordu. Yalnız tohum değişince 1d'de anlamlı hücre sayısı 3 ile 12 arasında oynuyordu. Null 20.000'e çıktı (DTW çekirdeği ×3,7, bit düzeyinde aynı); tohumlar ve dilimler boyunca sağlam tek hücre yükselen takoz long 2:1. |
| [13 · Emerging patterns](13-olusan-formasyon.md) | Does the first 75% of a pattern tell you the rest? The real continuation is no closer to the full pattern than a same-month random continuation; an apparent signal in flags and pennants was volatility decay and vanished once size was equalized. The "emerging pattern alert" was not built. | Formasyonun ilk %75'i kalanı söylüyor mu? Gerçek devam, aynı ayın rastgele devamından tam şablona daha yakın değil; bayrak ve flamada görünen sinyal oynaklık düşüşüydü, büyüklük eşitlenince kayboldu. "Oluşan formasyon uyarısı" yapılmadı. |

## Figures · Şekiller

README showcase charts and K-26 visual benchmarks (generated by [../tools/generate_readme_assets.py](../tools/generate_readme_assets.py)) live in [assets/](assets/). Figures from the original validation notebooks are in [../notebooks/output](../notebooks/output).

README vitrin grafikleri ve K-26 görsel doğrulamaları ([../tools/generate_readme_assets.py](../tools/generate_readme_assets.py) tarafından üretilir) [assets/](assets/) klasöründedir. İlk doğrulama notebook'larının şekilleri [../notebooks/output](../notebooks/output) klasöründedir.
