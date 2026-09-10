# GraphFlow'a katkı

[English](CONTRIBUTING.md) · [Türkçe](CONTRIBUTING.tr.md)

İlginiz için teşekkürler. GraphFlow'un değeri yalnız arama motoru değil — gösterdiği **her sayının ölçülmüş ve güvenilebilir olması**. Aşağıdaki kuralların çoğu, bir kez çiğnendiğinde ikna edici ama yanlış bir sonuç ürettiği için var. Pull request açmadan önce lütfen okuyun.

## Bir tasarım kararını değiştirmeden önce

Mimari kararlar [docs/00-tasarim-kararlari.md](docs/00-tasarim-kararlari.md) içinde `K-01 … K-21` olarak, değerlendirilip reddedilen alternatifleriyle birlikte kayıtlıdır. Bir kararın değişmesi gerektiğini düşünüyorsanız önce ilgili bölümü okuyun — aklınızdaki alternatif büyük ihtimalle zaten değerlendirilmiştir. Yine de değişmesi gerekiyorsa bir ölçümle issue açın.

## Bilinçli olarak reddedilenler — lütfen geri getirmeyin

Bunlar eksik özellik değil, gerekçesiyle verilmiş kararlardır.

- **Kafka, Rust/Go worker, TimescaleDB/InfluxDB, WebSocket akış.** Motor Python + NumPy; darboğaz dil değil veri yerleşimi (K-01).
- **Formasyon başına `if-else` kural motoru.** Her formasyon aynı boru hattından geçen 32 noktalık kanonik vektördür (K-04). Yapısal ve trend çizgisi filtreleri kuralı *sorgudan* türetir, formasyona özel koddan asla.
- **Kararlılık kapılarını kaldırmak.** Yapısal filtre yalnız sorgunun tepe/dip okuması kararlıyken (K-20), trend çizgisi filtresi yalnız eğim okuması kararlıyken (K-21) çalışır. Kapılar olmadan ground truth doğruluğu %70'ten %59'a düşer; kapısız bir trend çizgisi filtresi omuz-baş-omuz sorgularında yazı-tura atar (kararlılık %41).
- **Alt-stride hizalama ince ayarı** (K-19) ve **merkezi fark türevi** (K-11 eki) — ikisi de yazıldı, ölçüldü, bağlanmadı. Hiçbiri doğruluğu artırmadı.
- **Yeniden kalibre etmeden Aşama 2 metriğini değiştirmek.** Eşikler metrik başınadır (`TOLERANCE_THRESHOLDS_BY_METRIC`); yanlış eşiklerle metrik değiştirmek sonuçları sessizce boşaltır.
- **Tek geçişli NMS.** Pre-NMS (IoU 0,70) ve post-NMS (IoU 0,50, sembol başına en çok 3) ayrı ayrı zorunludur (K-09).
- **Sabit yüzde bariyerler** (ör. %5 TP / %3 SL). Bariyerler ATR tabanlıdır; sabit yüzde formasyonu değil oynaklığı ölçer (K-16).
- **Backtest'te sabit dolar likidite eşiği.** Likidite aylık kesitsel üst %40'tır; sabit eşik 2017–2019'u siler (K-13).
- **Tüm-geçmiş baseline.** Zaman-eşleştirmeli gölge dağılım kullanılır (K-12).
- **Kanvas kütüphaneleri** (Fabric.js, Konva.js) ve **"% benzerlik" kaydırıcısı.** Düz kanvas; tolerans *Katı / Orta / Esnek*'tir çünkü DTW mesafesi yüzde değildir (K-17).
- **Radar ve Backtest için ayrı motorlar.** Tek `SearchEngine`, bir `mode` parametresi (K-15).

## Doğruluk kuralları

### İstatistik

- **Geleceğe bakma yok.** ATR ve her özellik yalnız `t₀`'a kadarki barlardan hesaplanır. Geleceğe bakan tek satır tüm istatistik katmanını geçersiz kılar; her kuralın birim testi vardır.
- **Yarım mum yok.** Oluşmakta olan (kapanmamış) bar iki modda da düşürülür (K-05, K-15).
- **Bağımsız N.** İstatistiğe yalnız post-NMS'ten geçmiş, örtüşmeyen olaylar girer. Örtüşen pencereleri saymak `n`'i şişirir, aralıkları sahte biçimde daraltır (K-09, K-12).
- **Örneklem gösterim sabitiyle kırpılmaz.** `SEARCH_CACHE_MATCHES` sayfa boyutu değil istatistik örneklem sınırıdır; kırpma *en iyi* eşleşmeleri tutar ve beklentiyi şişirir. Bir nöbetçi test bunu korur.
- **Aynı barda TP ve SL → SL önce çarptı varsayılır.**
- **İşlem maliyeti tabanı.** `1×ATR / close < %1` olan pencereler dışlanır (K-16.7).
- **Fiyat sürekliliği.** Bar-bar oranı 10 katı aşan yer fiyat hareketi değil, redenominasyon ya da ticker yeniden kullanımıdır; kaldıraçlı tokenlar evrenden düşer.
- **Güven aralıkları ay-bloklu bootstrap'tır.** iid bootstrap aynı aydan çekilen 20 gölgeyi bağımsız sayar ve belirsizliği ~%29 eksik ölçüyordu (K-12). Kapsamanın kendisi ölçülür (`tools/ci_calibration`): blok ~%92, iid gerçek rejimde ~%80–89 — anlamlılığı ihtiyatlı okuyun.
- **Çoklu karşılaştırma.** Edge iddiaları Bonferroni ile sınanır ve **tüm** şablonlar tek tabloda raporlanır.
- **Replikasyon.** Tek zaman diliminde anlamlı olan bir bulgu, bulgu değildir. Her edge iddiası 1d ve 4h'de — vekil (ön-getiri eşleştirmeli gölge) testi dahil — tutmalıdır.
- **Sınırdaki bulgu kırılgandır.** Dokuz yıllık geçmişe on günlük veri eklemek, Bonferroni'yi *hangi* hücrelerin geçtiğini değiştirdi. Sınırdaki bir sonucu replike edene kadar gürültü sayın.

### Ölçüm

- **Bir "zarar" bulgusu bir "kazanç" bulgusu kadar güç ister.** 12'de 3'lük bir fark gürültüdür (standart hata ≈ 1,7). Mimari değiştirmeden önce yeterli örneklemle ölçün.
- **Kesinlik filtreyi aklar, duyarlılık suçlar.** `tools/formation_audit` yalnız motorun *döndürdüğüne* bakar — bir filtrenin sildiği gerçek formasyonları göremez. Her filtrenin bedelini, enjekte edilmiş ground truth'a karşı duyarlılığı da ölçen `tools/gt_benchmark` ile ölçün.
- **Filtreyi kendi ölçütüyle ölçmeyin.** Eğime dayanan bir filtre, eğime dayanan bir denetimde her zaman iyi görünür. Ground truth kullanın.
- **Denetçi denetlenir.** `tools/formation_audit --cross` sıfır köşegen dışı kabul raporlamalıdır; her şeye evet diyen denetçi %100 raporlar ve hiçbir şey ölçmez.
- **Değişmezlik testi yazın.** Şekil okuyan her fonksiyonun ayna / çevirme / ölçek / seviye değişmezliği testi olmalı. Şekilleri ve aynalarını farklı okutan bir belirginlik hatası (pencerelerin %83'ü) çekirdekte aylarca durdu, çünkü hiçbir doğruluk ölçümü "aynı girdi aynı cevabı veriyor mu" diye sormuyordu.
- **Ölçüm tabloları motorla birlikte bayatlar.** `data/f3` altındaki dosyalar kendilerini üreten motorun davranış parmak izini taşır ve `/api/findings` uyuşmazlığı bildirir. Motoru değiştiren her değişiklikten sonra `tools/run_outcomes` (1d ve 4h) ve `tools/f46_proxy_test` (1d ve 4h) yeniden koşulur — yaklaşık 4–5 dakika. Bir seçim listesini (ör. "F4.5'te anlamlı çıkan şablonlar") asla elle yazmayın; tanımı kodlayın, değeri hesaplatın.

### Ürün

- **Çıplak sayı yok.** API `StatEnvelope` döndürür (değer, aralık, birim); arayüz birime göre biçimlendirir.
- **Başrol metrik beklentidir (R), kazanma oranı değil** — kazanma oranı stop genişletilerek manipüle edilebilir.
- **Baseline'sız oran yok.** Gölge dağılım yoksa sayı yerine neden gösterilemediği yazılır.
- **Uyarılar yanıtın içindedir.** Ayırt edicilik, veri tazeliği ve çoklu karşılaştırma uyarılarını motor üretir; arayüz uydurmaz ve gizlemez.
- **Normalizasyon yalnız sunucuda.** İstemci ham çizim noktası gönderir; tek bir normalizasyon olmalıdır.

## Kod kuralları

- Python 3.11+, `from __future__ import annotations`, tam tip ipuçları.
- Tanımlayıcılar İngilizce; docstring ve yorumlar şu an Türkçe — yeni kodda iki dil de olur, ama bir dosya kendi içinde tutarlı kalsın.
- Kayıtlı bir kararı uygulayan önemsiz olmayan her blok ona atıf yapar: `# K-16.4: zaman bariyeri pencere uzunluğuyla orantılı`.
- **Sihirli sayı yok.** Sabitler gerekçeleri ve ölçümleriyle `engine/config.py`'dedir.
- **Sıcak yol vektörize NumPy'dir.** Aday listesi üzerinde Python döngüsü yok; vektörize ve tekil uygulamaların eşdeğerliği testle tutulur.
- Bağımlılıkları asgari tutun (`numpy`, `pandas`, `pyarrow`, `fastapi`). Yenisini eklemeden önce issue açın.
- `data/` asla commit edilmez.

## Testler

```bash
pytest -q
```

Her motor modülünün testi vardır. Özellikle: normalizasyon değişmezliği, DDTW düz çizgiyle çanağı eşleştirmemeli, NMS tekilleştirmesi ve rastgele pencerelerde triple-barrier sağlaması (2:1 başarı ≈ %33, 1:1 ≈ %50, beklenti ≈ 0R — sapma, geleceğe bakma ya da bar sıralama hatası demektir). Gerçek korpus gerektiren testler `data/` yoksa atlanır.

Arayüz:

```bash
cd frontend
npx tsc --noEmit
npx eslint src
```

`frontend/src/types/api.ts` üretilir, elle düzenlenmez:

```bash
python -c "import json, engine.api.main; open('frontend/openapi.json','w',encoding='utf-8').write(json.dumps(engine.api.main.app.openapi(), indent=2, ensure_ascii=False))"
cd frontend && npx openapi-typescript openapi.json -o src/types/api.ts
```

## Pull request'ler

- PR başına tek mantıksal değişiklik; açıklamada onu gerekçelendiren ölçüm.
- Değişikliğiniz motorun hangi pencereleri döndürdüğünü etkiliyorsa bir `tools/gt_benchmark` karşılaştırması (kesinlik **ve** duyarlılık) ekleyin ve bulguları yeniden üretin.
- Negatif sonuçlar memnuniyetle karşılanır: sayılarıyla ölçülmüş bir "bu işe yaramıyor" bir katkıdır — yukarıdaki kararların birkaçı tam olarak budur.
