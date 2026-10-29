<div align="center">

# GraphFlow

**Grafik formasyonları için görsel arama motoru — bir şekil çiz, piyasanın onu nerede çizdiğini bul ve sonra ne olduğunu dürüstçe gör.**

[English](README.md) · [Türkçe](README.tr.md)

[![CI](https://github.com/7mertyavuz/GraphFlow/actions/workflows/ci.yml/badge.svg)](https://github.com/7mertyavuz/GraphFlow/actions/workflows/ci.yml)
[![Lisans: MIT](https://img.shields.io/badge/lisans-MIT-blue.svg)](LICENSE)

</div>

---

![GraphFlow'un gerçek veride bulduğu on iki omuz-baş-omuz, kanonik şekil üstüne bindirilmiş](notebooks/output/goz_testi_blueprint_head_and_shoulders.png)

<sub>GraphFlow'un gerçek Binance günlük verisinde bulduğu on iki omuz-baş-omuz. Koyu çizgi: fiyat. Kırmızı: eşleşmeye bükülmüş kanonik şekil. Gölgeli alan: eşleşen pencere.</sub>

---

## Ne yapar

Fareyle bir desen çizersiniz — 14 klasik formasyondan birini seçersiniz ya da gerçek bir grafiğin bir parçasını gösterirsiniz (*"BTCUSDT'nin son 64 barı neye benziyor?"*) — ve GraphFlow gerçek kripto fiyat verisinin **11,6 milyon** tarihsel penceresinde piyasanın aynı şekli çizdiği yerleri arar. Tarihsel modda o formasyonlardan *sonra* ne olduğunu, piyasanın zaten yaptığı şeyin baseline'ı ile yan yana raporlar.

| Mod | Yanıtladığı soru |
|---|---|
| **Radar** (canlı) | *Şu an hangi coin'ler bu şekli yapıyor?* |
| **Backtest** (tarihsel) | *Geçmişte bu şekil oluştuğunda ne olmuş — ve bu şanstan farklı mıymış?* |

İki mod da aynı motorda çalışır; Radar, son kapanmış bara sabitlenmiş tarihsel aramadır.

## Farkı ne

Açık kaynaktaki formasyon araçlarının çoğu, bir formasyonun *var olduğunu* söyleyen kural tabanlı dedektörlerdir. Neredeyse hiçbiri *işe yarayıp yaramadığını* söylemez. GraphFlow ikinci soru üzerine kuruludur:

- **Sorguyu siz çizersiniz.** Serbest çizim sunucuda normalize edilir (ölçek ve seviye değişmez) ve motor çiziminizi nasıl okuduğunu söyler: *"3 belirgin tepe · ortadaki en yüksek · diğerleri benzer seviyede"*.
- **Her istatistiğin bir baseline'ı vardır.** Sonuçlar sıfırla değil, aynı aylardan çekilmiş rastgele pencerelerden oluşan zaman-eşleştirmeli bir gölge örneklemle karşılaştırılır.
- **Dürüst belirsizlik.** Ay-bloklu bootstrap güven aralıkları, 56 testin tamamı üzerinde Bonferroni düzeltmesi ve iyi görünenler değil **tüm** şablonlar için sonuç.
- **Survivorship bias yok.** Evren, Binance arşivinden delist edilmiş pariteleri de içerir. Stablecoin'ler, kaldıraçlı tokenlar ve *ikizler* (WBTC gibi aslıyla aynı fiyat serisi olan sarmalanmış tokenlar) ölçülmüş kurallarla düşer; aynı fiyat hareketi iki kez sayılmaz.
- **Varsayılmaz, ölçülür.** Motordaki her filtre, açılmadan önce enjekte edilmiş ground truth'a karşı A/B testinden geçti — birkaçı reddedildi.

## Dürüst bulgu

Her test iki zaman diliminde (1d ve 4h) ve ön-getiriye göre eşleştirilmiş bir baseline'a karşı tekrarlandıktan sonra:

> **Hiçbir grafik formasyonunun şekli, kısa vadeli momentum tersine dönüşünün ötesinde bilgi taşımıyor.**

Replike eden tek etki — yükselen takozdan sonra fiyat düşme eğiliminde — baseline, fiyatın zaten ne kadar yükselmiş olduğuna göre eşleştirildiğinde kayboluyor. Formasyon bağımsız bir sinyal değil, momentumun vekili. GraphFlow bunu gizlemek yerine raporlar; aracın varlık sebebi de bu.

## Nasıl çalışır

```
 çizim / şablon
        │   log fiyat → 32 noktaya yeniden örnekleme → z-score
        ▼
 Aşama 1   tüm pencerelerde kosinüs benzerliği (tek matris çarpımı)   11,6M → 12.500
 Pre-NMS   1B IoU 0,70 — örtüşen pencereleri tekilleştir
 Aşama 2   hibrit DTW (türev + ham, Sakoe–Chiba bandı)                 → 2.500 skorlanmış
 Eşik      sorgu-göreli null yüzdeliği (p01 kuyruk çapalı) + akıl sağlığı tavanı
 Filtreler yapısal imza (tepe/dip)                ┐ her biri yalnız sorgunun
           trend çizgisi zarfı (eğim/yakınsama)   │ okuması kararlıysa uygulanır
           iki rejimli direk + gövde zarfı (K-22) ┘
 Sıralama  ayna/çevirme değişmez yapısal + eğrisellik uyum cezası (K-23, K-24)
 Post-NMS  1B IoU 0,50, sembol başına en çok 3 → bağımsız olaylar
        │
        ▼
 sonuç ızgarası  +  "sonra ne oldu": triple-barrier sonuçları vs. zaman ve getiri eşleştirmeli baseline'lar
```

11,6 milyon pencerede ısınmış bir arama dizüstü bilgisayarda yaklaşık **300 ms** sürer. Kafka, Rust ya da zaman serisi veritabanı yoktur — darboğaz hiçbir zaman dil değildi, veri yerleşimiydi.

| Ölçüm | Sonuç |
|---|---|
| `formation_audit --cross` (14×14 kanonik çapraz denetim) | **14/14 köşegen · 0 köşegen dışı kabul** |
| `formation_audit --top 12` (gerçek 4h korpus, 14 formasyonun tamamı) | **168/168 (%100,0)** |
| `formation_audit --top 50` (gerçek 4h korpus, 14 formasyonun tamamı) | **697/700 (%99,6)** |
| `gt_benchmark --family all` (enjekte edilmiş ground truth, 14 formasyon) | **%88,7 kesinlik · %87,5 duyarlılık** (298/336) |
| `gt_benchmark --family all --real` (gerçek piyasa zemini, 14 formasyon) | **%88,1 kesinlik · %84,2 duyarlılık** (296/336) |
| `gt_benchmark --family all --freehand 8` (2.688 gürültülü el çizimi) | **%85,3 kesinlik · %84,0 duyarlılık** (2292/2688) |

## Hızlı başlangıç

**Gereksinimler:** Python 3.11+ (3.12 ile sınandı), Node.js 20+, tam veri için ~3 GB disk (veya 5 saniyelik demo korpusu için ~25 MB).

### Seçenek A — 10 saniyede deneyin (sentetik demo korpusu)

```bash
git clone https://github.com/7mertyavuz/GraphFlow.git
cd GraphFlow

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 24 sembollük 1d + 4h demo korpusu ve 8 arama matrisini üret (~5 sn)
python -m tools.generate_demo_corpus --out data/demo

GRAPHFLOW_DATA_DIR=data/demo uvicorn engine.api.main:app --port 8000
cd frontend && npm install && npm run dev   # arayüz → http://localhost:3000
```

### Seçenek B — Tam Binance tarihsel korpusu (11,6M pencere)

```bash
# 1. Python ortamı
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Veri — ücretsiz, API anahtarı gerekmez (Binance açık arşivi, delist edilenler dahil)
python -m engine.ingest.download --timeframes 1d 4h
python -m tools.backfill --timeframe 4h     # 4h'yi tüm evrene tamamla

# 3. Arama matrislerini kur (~2 GB memory-mapped vektör)
python -m engine.matrix.build

# 4. Çalıştır
uvicorn engine.api.main:app --port 8000     # API
cd frontend && npm install && npm run dev   # arayüz → http://localhost:3000
```

Hızlıca gerçek bir alt kümeyle denemek için indirme adımına `--limit-symbols 50` ekleyin. Veri dizini `GRAPHFLOW_DATA_DIR` ile herhangi bir yere taşınabilir.

## Kullanım kılavuzu

Arayüz **Türkçe ve İngilizce**'dir — başlıktaki **TR / EN** düğmesiyle değiştirilir (ilk ziyarette tarayıcı dilini izler).

1. **Çiz** sekmesinde kanvasa **Serbest** ya da noktadan noktaya **Kırık Çizgi** modunda (canlı tepe/dip ve üst/alt trend çizgisi önizlemesiyle) bir şekil çizin, ya da **Kütüphane**'den bir formasyon seçin, ya da **Grafik** sekmesinde bir sembol, parça uzunluğu ve (Backtest'te) bitiş tarihi seçin. Ayrıca herhangi bir sonuç kartındaki **Benzeri** düğmesine tıklayarak o eşleşen pencereyi bir sonraki aramanızın sorgusu yapabilir veya büyütme düğmesiyle etkileşimli büyük mum grafiğini inceleyebilirsiniz.
2. **Zaman dilimini** (4 saat / 1 gün) ve **toleransı** (Katı · Orta · Esnek) seçin. Tolerans, sorgunun kendi null dağılımının sürekli `p01`-çapalı bir yüzdeliğidir; sahte bir "%85 benzerlik" değildir.
3. Sonuçların üstünde **motorun çiziminizi nasıl okuduğunu** okuyun. Okuma kararsız olarak işaretlenmişse motor, sonuçları ona göre daraltmadığını söyler — yanlış okuduysa daha net çizin.
4. **Backtest**'te **Sonra ne oldu?** paneli R cinsinden beklentiyi (başrol metrik), teorik null'ı yanında kazanma oranını, zaman-eşleştirmeli **Edge**'i ve ön-getiriye göre eşleştirilmiş **Momentumdan Arındırılmış Edge**'i (getiri-eşleştirmeli gölge baseline) ay-bloklu bootstrap güven aralıklarıyla gösterir. Altında bir **ileri yol fanı**, eşleşmelerden sonra fiyatın ne yaptığını (medyan, %25–%75 ve %10–%90 bantları, ATR cinsinden, zaman bariyerine kadar) gölge örneklemin fanıyla aynı eksende gösterir. Her eşleşme kartı da seçili konfigürasyon ve yönde **o olayın kendi sonucunu** gösterir (hedef / stop / zaman aşımı, R, çıkış barı) — ya da neden *sayılmadığını*. Başlıktaki beklenti, sayılan kartların tam ortalamasıdır.
5. **Bulgular** sayfası her testi, her hücrenin kaç bağımsız null çekilişinde ayakta kaldığını (yalnız bazı çekilişlerde anlamlı olan hücre bulgu değil zar atışı olarak işaretlenir), her bulgunun hangi aşamada elendiğini ve sayıları hangi motor sürümünün ürettiğini listeler.

## Motoru kendiniz doğrulayın

GraphFlow, doğrulanırken kullanılan araçlarla birlikte gelir:

```bash
pytest -q                                              # 300+ test
python -m tools.formation_audit --cross                # denetçiyi denetle (veri gerekmez)
python -m tools.gt_benchmark --family all              # ground truth: enjekte edilmiş formasyonlar
python -m tools.gt_benchmark --family all --real       # …gerçek piyasa zemininde
python -m tools.gt_benchmark --family all --freehand 6 # …elle çizim taklidiyle
python -m tools.verify_stage1 --timeframe 1d           # matris vs. kaba kuvvet
python -m tools.ci_calibration                         # %95 GA gerçekten %95 kapsıyor mu?
python -m tools.run_outcomes --timeframe 1d            # istatistikleri yeniden üret
python -m tools.f46_proxy_test                         # şekil mi, momentum vekili mi?
```

Ölçüm dosyaları kendilerini hangi motorun ürettiğini (davranış parmak izi) kaydeder. Motoru değiştirip ölçümleri yeniden koşmazsanız Bulgular sayfası bunu söyler.

## Proje yapısı

```
engine/
  ingest/      Binance indirici (REST + arşiv), kaldığı yerden devam, hız sınırlı
  normalize/   log → yeniden örnekleme → z-score, ATR, genlik
  matrix/      memory-mapped pencere vektörleri, likidite filtresi
  search/      kosinüs aşaması, DTW/DDTW, NMS, yapısal ve zarf filtreleri
  outcome/     triple-barrier, gölge baseline, blok bootstrap
  api/         FastAPI: arama, istatistik, grafik, bulgular, tazelik
  templates/   32 noktalık vektör olarak 14 kanonik formasyon
frontend/      Next.js 16 · Tailwind v4 · TanStack Query · Lightweight Charts
tools/         doğrulama ve ölçüm araçları (yukarıda)
tests/         pytest takımı, gerçek korpus nöbetçileri dahil
notebooks/     ilk doğrulama notebook'ları ve şekilleri
docs/          tasarım kararları ve ölçüm raporları
```

## Belgeler

[docs/README.md](docs/README.md) tüm belgelerin dizinidir.

- [Tasarım kararları](docs/00-tasarim-kararlari.md) — 24 mimari karar; her biri reddedilen alternatifleri ve gerekçesiyle
- [Mimari](docs/01-mimari.md) — veri katmanı, algoritmalar, API, performans bütçesi
- Ölçüm raporları — doğrulama, sonuç istatistikleri, vekil testi, zaman dilimi replikasyonu, formasyon denetimi

## Katkı

Katkılar memnuniyetle karşılanır. GraphFlow'un pazarlığa kapalı birkaç doğruluk kuralı var (geleceğe bakmama, bağımsız örneklem, her oran için baseline, zaman dilimleri arası replikasyon) — lütfen önce [CONTRIBUTING.tr.md](CONTRIBUTING.tr.md) dosyasını okuyun.

## Teknoloji

**Motor:** Python · NumPy · pandas · PyArrow · FastAPI
**Veri:** Binance açık klines · Parquet · `.npy` memory-mapped matrisler
**Arayüz:** Next.js 16 · React 19 · Tailwind CSS v4 · TanStack Query · TradingView Lightweight Charts · düz HTML5 Canvas

## Lisans

[MIT](LICENSE)

## Sorumluluk reddi

GraphFlow bir **araştırma aracıdır**, yatırım tavsiyesi değildir. Ürettiği her istatistik geçmiş fiyat davranışını tanımlar ve gelecekteki performansın göstergesi değildir.
