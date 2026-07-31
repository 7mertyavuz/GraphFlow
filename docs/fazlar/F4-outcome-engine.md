# F4 — Outcome Engine ("Sonra Ne Oldu?")

**Durum:** ✅ Tamamlandı (31 Tem 2026) — [rapor](../05-f4-raporu.md)
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

### ⚠️ Gölgeye de ileri pencere NMS'i

Aynı sembolde çekilen gölge pencerelerin `T`-barlık ileri ufukları kesişirse null dağılımı **kendi içinde otokorelasyonlu** olur → gölgenin varyansı olduğundan küçük ölçülür → edge'in GA'sı sahte biçimde daralır → **anlamsız bir farkı anlamlı ilan edersin**.

- Gölge örnekleminde de aynı sembolde ardışık pencereler arasında en az `T` bar ayrım
- Tekilleştirme **ay havuzu genelinde** yapılır — yalnız tek bir eşleşmenin 20'lisi içinde değil; farklı eşleşmelerin gölgeleri de birbirini tekrar edebilir
- Havuz yetersizse `P < 20`'ye düşülür ve kaydedilir; aynı pencere iki kez sayılmaz

> **Kural:** Edge iddiası ekrana **ancak gölge dağılım aşılırsa** yazılır.

**İki referans:** teorik null (%33 / %50) + ölçülmüş gölge dağılım. İkisi birbirini doğruluyorsa metodoloji sağlamdır; ayrışıyorsa bir yerde hata vardır ve **erken görülür**. Kendi kendini denetleyen tasarım.

---

## Uygulama mekaniği

### Vektörizasyon — argmax hilesi

Python `for` döngüsü yok. ~10.000 olay × 20 gölge × 50 bar = 10M kontrol.

```python
tp_mask = High_mat >= TP[:, None]                          # (N, T)
sl_mask = Low_mat  <= SL[:, None]
tp_idx = np.where(tp_mask.any(1), tp_mask.argmax(1), T)    # .any() ZORUNLU:
sl_idx = np.where(sl_mask.any(1), sl_mask.argmax(1), T)    # argmax hiç
first  = np.minimum(tp_idx, sl_idx)                        # çarpmayınca da 0
is_sl  = sl_idx <= tp_idx                                  # eşitse SL (K-16)
```

**İki tuzak:**

| Tuzak | Çözüm |
|---|---|
| `T = 0,5·L` değişken → `T ∈ {12, 20, 32, 50}`; tek bir `(N,T)` matrisi kurulamaz | Olayları **pencere uzunluğuna göre grupla**, her grup kendi matrisi |
| Delist/veri sonunda satırlar `T` bardan kısa | `high` dolgusu **−inf**, `low` dolgusu **+inf** → dolgu asla bariyer tetiklemez. Geçerli bar sayısı ayrı maskede |

### Gap / slipaj gerçekliği

Bariyer 58.000, mum 57.000'den açıldı → 58.000'de satamazdın.

> **Kural:** Bir mumun `Open` fiyatı bariyerin ötesindeyse, çıkış fiyatı bariyer değil **o mumun `Open`'ı**dır.

⚠️ **Her iki yöne de uygulanır.** Yalnız SL'e uygulamak sistematik aşağı yanlılık yaratır ve edge'i olduğundan kötü gösterir. Yukarı gap'te TP çıkışı 2R'den iyi olabilir — bu gerçektir, kırpılmaz.

### Zaman bariyeri çıkış fiyatı

`T` süresince TP/SL vurulmazsa çıkış, `t₀+T` barının **`Close`** fiyatıdır. O barın High/Low'u önemsizdir — süre dolduğu an taker market emri.

### ATR ısınma süresi

`MIN_BARS_SINCE_LISTING = 28` (2 × `ATR_PERIOD`). Coin 8 gündür listeliyse ATR(14) hesaplanamaz; listeleme günlerinin pump/dump oynaklığı hem ATR'yi hem sonucu bozar. Wilder ATR bir EMA özyinelemesidir — 14 barda tohumlanır ama ~2 periyot yakınsamaya devam eder.

Pencere zaten `L ≥ 24` istediği için bağlayıcı kısım dardır; yine de düşen olay sayısı raporlanır (hafif seçim etkisi).

---

## Delist tuzağı — survivorship bias'ın arka kapısı

Bir eşleşme, delist edilmiş bir paritenin sonuna yakınsa ileri pencere kesiktir.

**⛔ Bu pencereleri eleme.** Elersen, ölmek üzere olan coinlerin en kötü sonuçlarını sistematik olarak atmış olursun — K-13'te evren düzeyinde önlenen survivorship bias, outcome katmanından geri girer.

**✅ Doğrusu:** delist = **zorunlu çıkış**. Son mevcut kapanıştan çıkılır, sonuç `delist_exit` olarak etiketlenir ve dökümde ayrı satır olarak görünür.

---

## Komisyon

```
R_net = R_brüt − (roundtrip_fee_pct / atr_pct)
```

`ROUNDTRIP_FEE_PCT = 0,001` (Binance taker ~%0,05 × 2). Hem brüt hem net raporlanır.

Bu, `MIN_ATR_PCT` tabanına **ek**tir: taban patolojik pencereleri eler, komisyon düzeltmesi kalanların getirisini gerçekçileştirir.

---

## Bağımsız N (K-09) — iki katman

**1. Post-NMS tekilleştirme.** İstatistiğe yalnızca post-NMS'ten geçmiş tekil olaylar girer. 47 "eşleşme" aslında 6 gerçek olayın 8'er kopyasıysa, `n=47` yalandır ve güven aralığı 3 kat dar çıkar.

**2. ⚠️ İleri pencere örtüşmesi.** NMS, *formasyon* pencerelerinin örtüşmediğini garanti eder — ama **sonuç** pencerelerini denetlemez. Aynı sembolde 5 bar arayla iki eşleşme, `T=12` ile 7 bar örtüşen ileri pencerelere sahiptir → sonuçlar korelasyonludur → `N` yine şişer.

Aynı sembolde ardışık eşleşmeler arasında **en az `T` bar** ayrım zorunludur. Bu yüzden düşen olay sayısı raporlanır.

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

---

## ⚠️ Güven aralığı — hiçbir sayı GA'sız yayınlanmaz

Örnek hesap: `n = 112`, `p = 0,41` → %95 GA ≈ **±9 puan** → `[%32, %50]`.

Teorik null **%33 bu aralığın içinde**. Yani "+6 puan edge" istatistiksel olarak **anlamsız** olurdu.

| Metrik | Yöntem |
|---|---|
| Beklenti (R) | **Bootstrap** GA, ≥10.000 yeniden örnekleme (R sürekli değişken; binom GA'sı uygun değil) |
| Başarı oranı | Wilson skor aralığı |
| Edge (`E_formasyon − E_gölge`) | İki bağımsız örneklemin farkı için bootstrap |

**Karar kuralı:** Edge'in %95 GA'sı sıfırı içeriyorsa çıktı *"anlamlı fark ölçülemedi"* olur. `+6 puan` diye yazılmaz.

---

## p-hacking kilitleri

| Kilit | Kural |
|---|---|
| **Tolerans kademesi** | `OUTCOME_TOLERANCE = "medium"` sabittir. Skorlar yüzdelik olduğu için kademe değişince `N` ve beklenti de değişir; kademe oynatarak sayı güzelleştirmek yasak |
| **Şablon seçimi** | 14 şablonun **tamamı** tek tabloda. "En iyi 3 formasyon" sunumu = çoklu karşılaştırma problemi |
| **Anlamsız sonuçlar** | Anlamlı çıkmayan formasyonlar da raporlanır — asıl bilimsel değer orada |

---

## Rejim kırılımı

Yıl bazında kırmak hücre başına ~14 olay bırakır — kullanılamaz. **3 kaba rejim:**

`2017–2020` · `2021–2022` · `2023–bugün`

Hücrede `n < 30` ise sayı gösterilir ama **"yetersiz örnek"** işaretlenir.

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
