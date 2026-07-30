# F3 — Doğrulama Kapısı 🚦

**Durum:** ✅ **GEÇTİ** (göz testi onaylandı, 30 Temmuz 2026)
**Çıktılar:** `notebooks/` · `notebooks/output/` (50 PNG) · [`../03-f3-dogrulama-raporu.md`](../03-f3-dogrulama-raporu.md)
**İlgili kararlar:** [K-11](../00-tasarim-kararlari.md#k-11--dtw-yerine-ddtw-türev-dtw) · [K-13](../00-tasarim-kararlari.md#k-13--survivorship-bias-ve-göreli-likidite-filtresi) · [K-18](../00-tasarim-kararlari.md#k-18--doğrulama-protokolü-notebook-kapısı)

---

## Amaç

F3 kod yazma fazı değil, **karar fazıdır**: motor gerçekten ölçüyor mu, yoksa uyduruyor mu?

> Arayüze bir satır yazılmadan önce geçilmesi zorunlu kapı (K-18). Motor göz testinden geçmiyorsa arayüz yazmak, yanlış bir ürünü cilalamaktır.

---

## Ölçek

| | |
|---|---|
| Parite | 1.165 (delist dahil) |
| Zaman dilimi | 1d |
| Aralık | 2017-08 → 2026-07 |
| Bar | 1.505.471 |
| Pencere | 1.922.776 |

---

## 🐞 F3'ün varlık sebebi: sessiz veri kaybı

Binance arşivi 2025-01'den itibaren zaman damgalarını mikrosaniye yazıyor. ms varsayan okuyucu bu barları "kapanmamış mum" sanıp düşürüyordu.

**Sonuç: 19 aylık veri, tek bir hata mesajı olmadan kayboldu.** İndirme hatasız bitiyor, tüm semboller 2024-12-31'de kesiliyor, 18 yeni parite tamamen boş.

Düzeltildi + regresyon testi. **Sentetik veriyle asla yakalanamazdı** — bu tek bulgu kapının maliyetini karşıladı.

Ayrıntı: [F0](F0-veri-ingest.md#-kritik-bug-mikrosaniye-zaman-damgaları)

---

## K-11 karara bağlandı: `hybrid`

F2'de K-11'in gerekçesi doğrulanmamıştı (bkz. karar kaydı). F3'te iki metodolojik kusur giderilerek yeniden ölçüldü:

**(a) Dairesellik giderildi.** Pozitifler artık kanonik şablonun gürültülü kopyası değil, **yapısal doğrulamadan geçmiş varyantlar**: asimetrik omuz, eğimli boyun çizgisi, kaymış zamanlama. Kanonikle korelasyon medyanı OBO'da 0,78 — **en düşük 0,07**.

**(b) Uzunluk kırılımı eklendi.** AUC 3 metrik × 4 pencere uzunluğu × 3 gürültü seviyesinde ayrı ayrı.

### Sonuç

| Metrik | Genel AUC |
|---|---|
| **hybrid** | **0,9045** ✅ |
| dtw | 0,8956 |
| ddtw | 0,8733 |

`hybrid` **12/12 hücrede**, **9/9 formasyonda**, 108 eşli hücrenin **%99**'unda kazandı.

DDTW'nin kaybı gürültü ve uzunlukla büyüyor (100 bar / %4 gürültü: 0,637'ye karşı 0,746) — **türevin yüksek geçiren filtre etkisiyle birebir tutarlı**.

Varsayılan `hybrid` oldu, kaybedenler `config.STAGE2_METRIC` anahtarında kaldı. Eşikler metrik başına ayrı (`TOLERANCE_THRESHOLDS_BY_METRIC`) — tek eşik setiyle metrik çevirmek motoru sessizce susturur.

> **Açık kalan:** DTW'nin varoluş sebebi olan **zaman ekseni bükülmesi** hâlâ test edilmedi. F3.5 Adım 4'te A/B yeniden çalıştırılacak; `hybrid` kazanan kalmayabilir.

---

## Geçen testler

| Test | Sonuç |
|---|---|
| **K-13 sağlık kontrolü** | Likit oran her yıl **%36–40** — 2017–2019 çökmüyor ✅ |
| **Negatif kontrol** | white noise 0,19 · whipsaw 0,48 — esnek kademenin **2,3–5,8 katı kötü**; düz çizgi pipeline'da düşüyor ✅ |
| **K-09 dedupe** | Örtüşen çift **0**, `max 3/sembol` tutuyor ✅ |
| **Performans** | `historical` 51 ms (bütçe 500) ✅ |
| **Radar doğruluğu** | ✅ |

---

## Göz testi — karar: GEÇTİ

50 PNG üretildi (`notebooks/output/`). Orta kademede 7 sorgu boş döndüğü için esnek kademede de render alındı; orada 20/20 sorgu dolu sayfa veriyor.

### Fincan-Kulp ✅ *"evet, bu çalışıyor"*

12 karonun **12'si gerçek çanak**, 12 farklı sembol, 2021–2026'ya yayılmış, volatilite %29–150. Hiçbiri diğerinin kaydırılmış kopyası değil.

**Ama kulp yok.** SUI, CVX, EGLD, AR, OG neredeyse saf U; kulp yalnızca MANA ve BLZ'de. Motor `cup_and_handle` değil **rounding bottom** buluyor. İki şablonun sonuç kümeleri büyük ölçüde çakışıyor olmalı.

### OBO ⚠️ geçer ama sınırda

- **7–8 ikna edici** (TOMO, ILV, BCH, XEC, FXS, BADGER, kısmen NEO)
- **3 tanesi OBO değil, yuvarlak tepe** (XLM, XMR, MATIC — tek zirve, ayrık omuz yok)
- **2 tanesi stablecoin** (PAXUSDT %4 vol, TUSDUSDT %5 — üstelik 1. ve 2. sırada)

**Kök sebep: boyun çizgisi denetlenmiyor.** Gerçek OBO, omuz–baş arası iki dibin birbirine yakın olmasını gerektirir. Z-score sonrası saf şekil korelasyonu "yükseliş–tümsek–daha büyük tümsek–düşüş"ü yakalıyor ama diplerin hizalı olup olmadığına bakmıyor. Yuvarlak tepeler bu yüzden sızıyor.

K-04 bunu öngörmüştü ("kural mantığı yalnızca geometriye indirgenemeyen ek filtreler için"). Artık teorik bir ihtimal değil, **ölçülmüş bir ihtiyaç** → F3.5 Adım 7.

### Karar gerekçesi

Negatif kontrol 2,3–5,8 kat farkla geçiyor, K-09 ve K-13 temiz, fincan sayfası ürünün "evet bu o" anını üretiyor, OBO'daki hatalar çöp değil **komşu şekil**. **Motor ölçüyor, uydurmuyor.** → Kapı geçildi, F3.5 ile temizliğe.

---

## Geçemeyen testler (eşik gevşetilmedi)

| # | Sorun | Bulgu | Plan |
|---|---|---|---|
| **S-1** | Rampa/neredeyse-düz sorgular her kademeyi geçiyor | Skor 0,0025 — tüm sorguların en iyisi. Motor doğru cevap veriyor; dönen pencereler gerçekten monoton (%81–87 artan adım) ve yüksek genlikli (+%77, +%460) | F3.5 Adım 1 |
| **S-2** | 14 şablonun 7'si orta kademede ilk sayfayı dolduramıyor (OBO'da 1 sonuç) | Tek global eşik, bayrak (0,008) ile üçgeni (0,056) aynı anda idare edemiyor | F3.5 Adım 1 |
| **S-3** | Aşama 1 tavanı uzunlukla düşüyor (%95 → %80, takozlarda %62); sonuçların %68'i 24 barlık pencerede | Uzun pencerede daha çok yapı → daha çok uyuşmazlık | F3.5 Adım 1 |
| **S-4** | Radar 23 ms (bütçe 10) | Bütçe 500 sembol varsayarak yazılmıştı, evren 1.165 | F3.5 Adım 8 — **bütçe güncellenir, optimizasyon yapılmaz** |
| **S-5** | Stablecoin kirliliği: OBO'nun 1. ve 2. sırası PAXUSDT/TUSDUSDT | Oran düşük (240'ta 5) ama en görünür yerde. K-10 öngörmüş, çözüm mimaride var, `min_amplitude` varsayılanı kapalıydı | F3.5 Adım 2 |

> **S-1, S-2 ve S-3 aynı hatanın üç yüzü:** skor ölçeği sorgunun yapısal karmaşıklığına bağlı. Üçü tek mekanizmayla çözülür → F3.5 Adım 1.

---

## Çıkış şartı ✅

Göz testi onaylandı · negatif kontrol geçti · K-11 karara bağlandı · 5 açık sorun **eşik gevşetilmeden** raporlandı.

**127 test geçiyor · `main` push'lu (`b841a7b`)**
