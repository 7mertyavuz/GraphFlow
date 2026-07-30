# F4 — Outcome Engine ("Sonra Ne Oldu?")

**Durum:** ⬜ Planlı — F3.5 onayından sonra
**Modül:** `engine/outcome/`
**İlgili kararlar:** [K-06](../00-tasarim-kararlari.md#k-06--öldürücü-özellik-sonra-ne-oldu) · [K-09](../00-tasarim-kararlari.md#k-09--çift-aşamalı-nms-deduplication) · [K-12](../00-tasarim-kararlari.md#k-12--zaman-eşleştirmeli-baseline-gölge-dağılım) · [K-16](../00-tasarim-kararlari.md#k-16--triple-barrier-atr-tabanlı-göreli-bariyerler)

---

## Amaç

**Projenin tacı.** Bu özellik olmadan GraphFlow şık bir grafik görüntüleyicidir. Bu özellikle birlikte **ölçülmüş bir edge iddiası** taşıyan araştırma aracına dönüşür.

> Sinyal satmıyoruz; ölçülmüş ve dürüstçe raporlanmış geçmiş dağılım sunuyoruz.

---

## Triple-Barrier (K-16)

Formasyonun bittiği bar `t₀`, kapanış `C₀`, `ATR = ATR(14)` — **yalnızca `t₀`'a kadarki barlardan**.

| Bariyer | Değer |
|---|---|
| Kâr Al (TP) | `C₀ + k_tp × ATR` |
| Zarar Kes (SL) | `C₀ − k_sl × ATR` |
| Süre | `T = round(0,5 × L)` bar |

**Zaman bariyeri pencere uzunluğuyla orantılıdır** — sabit 10 bar değil. 100 barlık bir çanak 10 barda yargılanırsa neredeyse tümü zaman bariyerinden çıkar.

### İki konfigürasyon birlikte hesaplanır

| Konfig | `k_tp` | `k_sl` | Teorik null | Amaç |
|---|---|---|---|---|
| **2:1** | 2 | 1 | **%33,3** | İşlem edilebilir senaryo |
| **1:1** | 1 | 1 | **%50,0** | Saf yön testi — akademik savunması olan sayı |

Null formülü: driftsiz rastgele yürüyüşte `P(üst) = k_sl / (k_tp + k_sl)`.

**ATR'nin asıl kazandırdığı budur:** analitik olarak bilinen bir null hipotezi. Statik yüzde bariyerde bu sayı her parite ve dönem için farklıdır, hiçbir şeyle kıyaslanamaz.

### Zorunlu kurallar

- 🚫 **Aynı barda TP ve SL** → muhafazakâr varsayım: **SL önce çarptı**. Bar içi sıralama bilinmediği için sonuçlar kasıtlı olarak kötümser yönde eğilir ve bu raporlanır.
- 🚫 **İşlem maliyeti tabanı:** `1×ATR / C₀ < %1` ise pencere istatistiğe **girmez**. Binance taker gidiş-dönüş ~%0,1 + slipaj. Bu taban olmadan binlerce sahte "başarı" toplanır ve edge'in tamamı komisyona gider.
- 🚫 **Lookahead bias:** ATR yalnızca `t₀`'a kadarki barlardan. Birim testi zorunlu.

---

## Gölge dağılım (K-12)

Her eşleşme için:

1. Pencerenin **bitiş tarihini** al
2. **Aynı aydan**, **farklı sembollerden**, aynı likidite filtresini geçen **P = 20** rastgele pencere çek
3. Aynı triple-barrier ölçümünü uygula

Kontrol grubunun zaman dağılımı, eşleşmelerin zaman dağılımını **birebir taklit eder**. Bir formasyonun 60 örneği Mart 2021'deyse, gölge dağılımın da 60 örneği Mart 2021'dendir.

> **Kural:** Edge iddiası ekrana **ancak gölge dağılım aşılırsa** yazılır.

**İki referans:** teorik null (%33 / %50) + ölçülmüş gölge dağılım. İkisi birbirini doğruluyorsa metodoloji sağlamdır; ayrışıyorsa bir yerde hata vardır ve **erken görülür**. Kendi kendini denetleyen tasarım.

---

## Bağımsız N (K-09)

İstatistiğe **yalnızca post-NMS'ten geçmiş tekil olaylar** girer.

47 "eşleşme" aslında 6 gerçek olayın 8'er kopyasıysa, `n=47` yalandır ve güven aralığı 3 kat dar çıkar.

---

## Raporlanan metrikler

| Metrik | Not |
|---|---|
| **Beklenti (R)** | `E = p_TP × k_tp − p_SL × k_sl + p_time × R̄_time` — **başrol** |
| Kazanma oranı | Yanında gösterilir, başrole konmaz |
| Teorik null | `k_sl / (k_tp + k_sl)` |
| Gölge dağılım | Ölçülmüş kontrol grubu |
| Edge | `E_formasyon − E_gölge` |
| N | Dedupe edilmiş bağımsız olay sayısı |
| Rejim kırılımı | Yıl/dönem bazında ayrı tablo |

> **Neden beklenti başrolde:** SL 5×ATR yapılırsa kazanma oranı %85'e çıkar ama beklenti negatiftir. Kazanma oranı tek başına manipüle edilebilir bir metriktir.

### Kart tasarımı

```
Hedef: 2R (bu parite için ≈ %7,4)  ·  Stop: 1R (≈ %3,7)
Beklenti: +0,18R
Başarı:   %41   (teorik null: %33  ·  gölge dağılım: %34)
N = 112 bağımsız olay

── Rejim kırılımı ──
2021: %55 (n=38)    2022: %29 (n=24)

ⓘ Bu veriler geçmiş dağılımlardır, kesin bir işlem sinyali değildir.
```

Kullanıcı ATR bilmez: içeride ATR ile hesaplanır, ekranda **hem R hem yüzde** gösterilir.

---

## Doğrulama (çıkış şartı)

| Test | Beklenti |
|---|---|
| Rastgele pencerelerde 2:1 başarı | ≈ **%33** |
| Rastgele pencerelerde 1:1 başarı | ≈ **%50** |
| Rastgele pencerelerde beklenti | ≈ **0R** |

Bu değerler teorik null'dan anlamlı şekilde sapıyorsa triple-barrier uygulamasında hata vardır (lookahead, yanlış ATR penceresi, bar sıralaması) ve **erken yakalanır**.

Ayrıca: lookahead bias birim testi.

> Bu testler arama kalitesinden **bağımsızdır** — F3.5 ile paralel başlatılabilir. Rapor üreten kısım F3.5'i beklemelidir.

---

## Ertelenen kapsam

- Short (düşüş) yönü için ayna triple-barrier
- Hacim teyidi eklentisi
