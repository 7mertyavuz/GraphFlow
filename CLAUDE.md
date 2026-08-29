# GraphFlow — Claude Code Proje Bağlamı

Grafik formasyonları için görsel arama motoru. Kullanıcı bir desen çizer veya
kütüphaneden seçer; sistem gerçek piyasa verisinde benzer grafikleri bulur ve
tarihsel modda o formasyondan sonra ne olduğunu istatistiksel olarak raporlar.

## Önce bunları oku

| Belge | Ne zaman |
|---|---|
| `docs/00-tasarim-kararlari.md` | **Her mimari soruda.** 18 karar (K-01…K-18), gerekçeleri, reddedilen 19 alternatif. Projenin anayasası. |
| `docs/01-mimari.md` | Kod yazmadan önce. Şemalar, algoritmalar (sözde kod), API, repo yapısı, yol haritası. |

Bir kararı değiştirmen gerektiğini düşünüyorsan **önce ilgili `K-xx` bölümünü
oku**. Orada büyük ihtimalle o alternatif zaten değerlendirilmiş ve
gerekçesiyle reddedilmiştir. Yine de değiştirilmesi gerekiyorsa bana sor;
tek taraflı değiştirme.

---

## Asla yapma (bilinçli olarak reddedilmiş kararlar)

Bunlar unutulmuş eksikler değil, **kasıtlı tercihlerdir**. "İyileştirme" diye
geri getirme:

- ❌ **Kafka, Rust/Go worker, TimescaleDB/InfluxDB, WebSocket akış** — motor
  Python + NumPy. Darboğaz dil değil, veri yapısı (K-01).
- ❌ **`if-else` formasyon kural motoru** — her formasyon 32 noktalık kanonik
  vektör, aynı DTW pipeline'ından geçer (K-04).
- ❌ **Alt-stride hizalama ince ayarı** — yazıldı, ölçüldü, BAĞLANMADI (K-19).
  Mesafe ve kosinüs takas ediyor; net katkı yok. `REFINE_MATCHES=False`.
- ⚠️ **Aşama 2 metriği K-11'de F3 ölçümüyle DEĞİŞTİ.** Artık `hybrid` =
  (normalize DDTW + normalize ham DTW) / 2. Ne yalnız DDTW, ne yalnız ham DTW.
  Ölçüm: AUC hybrid 0,9045 > dtw 0,8956 > ddtw 0,8733 (12/12 hücre). Metrik
  `config.STAGE2_METRIC` ile seçilir; eşikler metrik başına ayrıdır
  (`TOLERANCE_THRESHOLDS_BY_METRIC`) — tek eşik setiyle metrik çevirmek motoru
  sessizce susturur. Gerekçe: docs/03-f3-dogrulama-raporu.md.
- ❌ **Tek geçişli NMS** — pre-NMS (IoU 0.70) *ve* post-NMS (IoU 0.50 +
  max 3/sembol) ayrı ayrı zorunlu (K-09).
- ❌ **Statik yüzde bariyerler** (%5 TP / %3 SL) — daima ATR tabanlı. Statik
  yüzde formasyonu değil volatiliteyi ölçer (K-16).
- ❌ **Sabit dolar likidite eşiği** (backtest'te) — aylık kesitsel üst %40.
  Sabit eşik 2017–2019 verisini siler (K-13).
- ❌ **Tüm-geçmiş baseline** — zaman-eşleştirmeli gölge dağılım (K-12).
- ❌ **Fabric.js / Konva.js** — düz HTML5 Canvas + pointer events, ~100 satır (K-17).
- ❌ **"%85 benzerlik" slider'ı** — `Katı/Orta/Esnek` toggle. DTW mesafesi
  yüzde değildir (K-17).
- ❌ **İki ayrı motor (Radar / Backtest)** — tek `SearchEngine`, `mode`
  parametresi. Radar = `offset son bar` özel hâli (K-15).

## Asla ihlal etme (doğruluk kuralları)

- 🚫 **Lookahead bias.** ATR yalnızca `t₀`'a kadarki barlardan hesaplanır.
  Outcome hesabında geleceğe bakan tek satır tüm istatistik katmanını
  geçersiz kılar. Bunun birim testi olmalı.
- 🚫 **Yarım mum.** Oluşmakta olan (kapanmamış) son mum her iki modda da
  veriden düşürülür (K-05, K-15).
- 🚫 **Skor kıyaslanabilirliği.** DDTW mesafesi daima hizalama yolu
  uzunluğuna bölünür (K-14) — ama F3'te ölçüldü: bu **yetmiyor**, sonuçların
  %68'i yine 24 barlık pencerede kümeleniyordu. F3.5'ten itibaren sıralama
  **sorgu-göreli null dağılımının uzunluk-içi yüzdelik dilimine** göre yapılır.
  Eşik de yüzdeliktir; yanında MUTLAK akıl sağlığı tavanı bulunur — yalnız
  yüzdelik kalırsa motor her sorguya sonuç döndürür ve "eşleşme yok" diyemez.
- 🚫 **Bağımsız N.** İstatistiğe yalnızca post-NMS'ten geçmiş tekil olaylar
  girer. Örtüşen pencereleri saymak `n`'i şişirir, güven aralığını sahte
  biçimde daraltır (K-09, K-12).
- 🚫 **Aynı barda TP ve SL** → muhafazakâr varsayım: **SL önce çarptı**.
- 🚫 **İşlem maliyeti tabanı.** `1×ATR / close < %1` ise pencere istatistiğe
  girmez (K-16.7).
- 🚫 **Fiyat sürekliliği.** Bar-bar oranı 10x'i aşan yer fiyat hareketi değil,
  **redenominasyon / ticker yeniden kullanımı**dır (LUNAUSDT: 177.400x). O
  pencere matrise girmez, ileri pencere orada kesilir. Kaldıraçlı tokenlar
  (UP/DOWN/BULL/BEAR) evrenden düşer — F4'te gölge beklentisini +39R'ye
  taşıyan sebep buydu.
- 🚫 **Güven aralığı kapsaması ölçülür.** `tools/ci_calibration` ile: ay-bloklu
  bootstrap %92, iid gerçek rejimde ~%80-89 kapsıyor (nominal %95). Blok
  iid'den belirgin iyi ama kusursuz değil — anlamlılık iyimser okunmamalı.
- 🚫 **Gölge dağılımda kesitsel korelasyon.** Güven aralıkları **daima
  ay-bloklu bootstrap** ile hesaplanır; iid bootstrap aynı aydan çekilen 20
  gölgeyi 20 bağımsız gözlem sayar. Ölçülen ay içi korelasyon 0,384, tasarım
  etkisi medyan 1,28 — iid, belirsizliği ~%29 eksik ölçüyordu ve F4'ün tek
  pozitif bulgusu bu yüzden sahte çıktı (K-12).
- 🚫 **Çoklu karşılaştırma.** 14 şablon × 2 konfigürasyon = 28 test; %95 ile
  şans eseri ~1,4 "anlamlı" sonuç beklenir. Edge iddiaları Bonferroni ile de
  sınanır ve **tüm şablonlar** tek tabloda raporlanır.

---

## Mevcut durum

```
✅ docs/00-tasarim-kararlari.md    Karar kaydı
✅ docs/01-mimari.md               Teknik spesifikasyon
✅ engine/config.py                Tüm sabitler (K-xx referanslı)
✅ engine/ingest/                  F0  (binance_client, symbol_universe, store, download)
✅ engine/normalize/               F1  (pipeline, amplitude, atr)
✅ engine/matrix/                  F1  (build, incremental, liquidity, npy_store)
✅ engine/search/                  F2  (stage1_cosine, nms, ddtw, engine)
✅ engine/outcome/                 F4 + F4.5 (short yönü, ay-bloklu bootstrap)
✅ engine/templates/               F2  (14 kanonik JSON + loader)
✅ engine/api/                     F5  (FastAPI, StatEnvelope, chart, freshness, oturum)
✅ tools/                          shapes, variants, gen_synthetic, ab_stage2,
                                  f3_measure, repair_symbol_map, backfill,
                                  verify_stage1, ci_calibration, f46_proxy_test
✅ tests/                          219 test (ingest, arşiv, normalize, matrix, search,
                                  outcome, api, grafik karosu)
✅ notebooks/                      F3 GEÇTİ (kullanıcı onayı, 31 Tem 2026)
✅ F3.5 temizlik                   null kalibrasyonu · peg filtresi · invariantlar
✅ frontend/                       F6 + F7  (Next.js 16, Radar/Backtest/Bulgular)
✅ requirements.txt                doğrulanmış sürümler (Python 3.12)
```

Veri kökü `GRAPHFLOW_DATA_DIR` ile depo dışına taşınabilir.

### Arayüz sözleşmesi (F6/F7)

Arayüz motorun ölçtüğünü gösterir; kendi geometrisini ya da kendi
normalizasyonunu kurmaz:

- **Normalizasyon sunucuda.** İstemci ham çizim noktası gönderir; 32 noktaya
  indirgeme ve z-score `normalize_drawing`'dedir. İki normalizasyon = iki
  farklı sonuç listesi (K-02, K-04).
- **Grafik geometrisi sunucuda.** Blueprint `exp(mu + sigma·z)` ile fiyat
  eksenine taşınır (log uzayının tersi); `highlight_*` indeksleri **dönen bar
  dizisine görelidir**, mutlak bar indeksi değildir.
- **`symbol_id` uzayı zaman dilimi başınadır.** 4h ve 1d evrenleri farklıdır,
  harita `symbols_{tf}.json`'dan okunur. Karıştırmak yalnızca yanlış etiket
  değil, **yanlış sembolün fiyatlarını okumak** demektir.
- **İstatistik ekrandaki eşleşmelerden hesaplanır.** `/stats` ikinci bir arama
  çalıştırmaz (K-09). Radar (live) sonuçları için istatistik üretilmez: son
  bardaki pencerenin ileri penceresi yoktur.
- **Uyarılar yanıtın içindedir.** Ayırt edicilik (S-1), veri tazeliği ve çoklu
  karşılaştırma uyarılarını arayüz uydurmaz ve gizleyemez.

Sabitler `engine/config.py`'de merkezîdir. **Kod içine sihirli sayı yazma** —
oradan import et. Yeni bir sabit gerekirse oraya, `K-xx` referansıyla ekle.

---

## Yol haritası ve F3 kapısı

`F0 veri → F1 matris → F2 arama → 🚦 F3 notebook doğrulaması → F4 outcome
→ F5 API → F6 Radar UI → F7 Backtest UI`

**F3 geçilmeden F5'e geçilmez.** Motor göz testinden ve negatif kontrolden
geçmiyorsa arayüz yazmak yanlış bir ürünü cilalamaktır (K-18).

Negatif kontrol: düz çizgi / white noise / whipsaw verildiğinde sistem
"eşleşme yok" demeli veya en iyi skor ~%40 bandında kalmalı. Her girdiye
%0.94 skor dönüyorsa **metrik ölçmüyor, uyduruyor** demektir.

---

## Kod konvansiyonları

- **Python 3.11+**, `from __future__ import annotations`, tam tip ipuçları.
- Tanımlayıcılar İngilizce, docstring ve yorumlar Türkçe.
- Bir karara dayanan her önemsiz olmayan blok, ilgili `K-xx`'e yorumla
  referans versin. Örnek: `# K-16.4: zaman bariyeri pencere uzunluğuyla orantılı`
- Sıcak yol (matris taraması, DDTW) **vektörize NumPy** olmalı; aday listesi
  üzerinde Python döngüsü yazma.
- Bağımlılıkları minimum tut: `numpy`, `pandas`, `pyarrow`, `scipy`
  (interpolasyon için opsiyonel — `np.interp` yeterli), `fastapi`, `redis`.
  Yeni bir bağımlılık eklemeden önce sor.
- `data/` asla commit edilmez (`.gitignore`'da).

## Test beklentisi

Her motor modülünün `pytest` testi olmalı. Özellikle:

- Normalizasyon: ölçek ve seviye değişmezliği (aynı şekil, farklı fiyat
  seviyesi → aynı vektör).
- DDTW: düz çizgi ile çanak **eşleşmemeli** (K-11 doğrulaması).
- NMS: örtüşen pencereler tekilleşmeli, `max_per_symbol` uygulanmalı.
- Triple-barrier: rastgele pencerelerde 2:1 başarı ≈ %33, 1:1 ≈ %50,
  beklenti ≈ 0R. Sapma varsa lookahead veya bar sıralama hatası vardır.
- F4.6 Vekil Testi: Ön-getiri eşleştirmeli gölge havuzlarında (±0.15σ / ±0.25σ / ±0.50σ) 3 aşamalı fallback zinciri (band genişlet → ay esnet → uyarı).
- F5 API: Çıplak sayı döndürmek yasak (StatEnvelope zorunlu), oturum sayacı ile Bonferroni çoğul test uyarıları, DTW path önbelleği.

## Komutlar

```bash
python -m engine.ingest.download        # F0: Binance klines indir
python -m engine.matrix.build           # F1: vektör matrislerini üret
python -m tools.f46_proxy_test          # F4.6: Vekil testi ve ön-getiri eşleştirmeli gölge analizi
pytest -q                               # testler
uvicorn engine.api.main:app --reload    # F5: API
```

---

## Ürün ilkesi

Sinyal satmıyoruz; **ölçülmüş ve dürüstçe raporlanmış geçmiş dağılım**
sunuyoruz. Hiçbir başarı oranı baseline'sız gösterilmez. Beklenti (R) başrol
metriğidir, kazanma oranı değil — kazanma oranı SL genişleterek manipüle
edilebilir.
