# Claude Code Başlangıç Prompt'u

`CLAUDE.md` her oturumda otomatik yüklenir, bu yüzden mimariyi tekrar
anlatmaya gerek yok. Aşağıdaki metni Claude Code'a olduğu gibi yapıştır.

---

## Prompt (kopyala)

```text
GraphFlow üzerinde çalışıyoruz. Depoda CLAUDE.md var, otomatik yüklendi.

BAŞLAMADAN ÖNCE ŞUNLARI OKU (sırayla, tamamını):
1. docs/00-tasarim-kararlari.md  — 18 mimari karar (K-01…K-18) ve reddedilen
   19 alternatif. Bu projenin anayasası.
2. docs/01-mimari.md             — teknik spesifikasyon: veri şemaları,
   normalizasyon pipeline'ı, kaskad arama motoru, outcome engine, API,
   repo yapısı, performans bütçesi.
3. engine/config.py              — tüm sabitler, her biri K-xx referanslı.

Okuduktan sonra bana 10 satırlık bir özet ver: kaskadın 4 aşaması, F3
kapısının ne olduğu ve "asla yapma" listesinden 3 madde. Bunu doğrulamadan
kod yazmaya başlama.

────────────────────────────────────────────────────────────────────────
GÖREV: F0 + F1 + F2'yi uygula (veri → matris → arama motoru).
F3, F4 ve sonrasına BU OTURUMDA GEÇME.
────────────────────────────────────────────────────────────────────────

F0 — engine/ingest/
  • binance_client.py     Binance REST /api/v3/klines indirici. Sayfalama
                          (1000 bar limiti), rate-limit'e saygılı (weight
                          takibi + backoff), kesintiden devam edebilir
                          (resume), ağ hatasında yeniden dene.
  • symbol_universe.py    Sembol evreni. exchangeInfo yalnızca YAŞAYAN
                          pariteleri verir; delist edilenler K-13 gereği
                          ZORUNLU. data.binance.vision arşivinden veya
                          saklanan exchangeInfo anlık görüntülerinden
                          tarihsel evreni türet. USDT + BTC bazlı.
  • store.py              Parquet okuma/yazma (docs/01-mimari.md §2.2
                          şeması). Atomik yazım, artımlı append.
  • download.py           CLI giriş noktası: python -m engine.ingest.download

F1 — engine/normalize/ + engine/matrix/
  • normalize/pipeline.py log fiyat → np.interp ile 32 noktaya resample →
                          z-score. Sıra önemli. sigma < FLAT_EPS ise pencereyi
                          düşür. Toplu (batch) versiyon vektörize olmalı.
  • normalize/pipeline.py normalize_drawing(): kanvas noktaları için; y ekseni
                          ters çevrilir, log adımı UYGULANMAZ (çizim zaten
                          lineer uzayda), resample + z-score aynı.
  • normalize/amplitude.py  genlik = (max-min)/min*100, ham fiyatlardan,
                          normalizasyondan ÖNCE.
  • normalize/atr.py      Wilder ATR(14). Yalnızca t0'a kadarki barlar —
                          lookahead yasak, bunun testi olsun.
  • matrix/liquidity.py   Aylık kesitsel hacim sıralaması, üst %40 maskesi.
  • matrix/build.py       Kayan pencere (STRIDE=3), vectors.npy (K,32) float32
                          + meta.npy (META_DTYPE). 8 matris: 2 timeframe ×
                          4 pencere uzunluğu. Bellek verimli olsun; tüm
                          pencereleri aynı anda RAM'e almadan chunk'lar hâlinde
                          yaz.
  • matrix/incremental.py Yeni kapanan mumlar için append.

F2 — engine/search/ + engine/templates/
  • search/stage1_cosine.py  (V @ q)/32, memmap üzerinde, likidite ve genlik
                          maskeleriyle, np.argpartition ile top-K.
  • search/nms.py         1D-IoU. nms_1d(candidates, iou_threshold,
                          max_per_symbol=None). Pre ve post için tek fonksiyon.
  • search/ddtw.py        Keogh-Pazzani türev tahmini + Sakoe-Chiba bandı
                          (r=5) ile banded DTW. ADAY LİSTESİ ÜZERİNDE PYTHON
                          DÖNGÜSÜ YAZMA — DP'yi tüm adaylar üzerinde
                          vektörize et (numpy, (n_cand, band) şeklinde).
                          Çıktı: dtw_distance / path_length.
  • search/engine.py      SearchEngine.search(query, mode, timeframe,
                          window_lengths, tolerance, min_amplitude, limit).
                          mode='live' → yalnızca son pencere maskesi.
                          Tek kod yolu, iki mod (K-15).
  • templates/            En az 8 kanonik formasyon JSON'u (docs/01-mimari.md
                          §7 şeması): OBO, ters OBO, ikili tepe, ikili dip,
                          fincan-kulp, boğa bayrağı, yükselen takoz, düşen
                          takoz. Vektörleri elle uydurma — matematiksel
                          olarak üret (gauss toplamları / parçalı eğriler),
                          üretici script'i tools/ altına koy.
  • templates/loader.py   JSON yükle, aynı z-score normalizasyonundan geçir.

────────────────────────────────────────────────────────────────────────
DOĞRULAMA (bu oturumun çıkış şartı)
────────────────────────────────────────────────────────────────────────

Binance indirmesinin bitmesini bekleme. tools/gen_synthetic.py yaz:
bilinen formasyonların (OBO, çanak, bayrak) rastgele ölçek/uzunluk/gürültüyle
enjekte edildiği geometrik brownian hareket temelli sentetik OHLCV üretsin.
Ground truth bilindiği için bu, gerçek veriden daha güçlü bir doğrulamadır.

pytest ile şunlar geçmeli:
  1. Normalizasyon değişmezliği: aynı şekil, 100x farklı fiyat seviyesinde
     → aynı vektör (atol=1e-6).
  2. DDTW ayırt ediciliği: düz çizgi ile çanak şablonu EŞLEŞMEMELİ. Ham DTW
     ile karşılaştır ve DDTW'nin gerçekten ayırdığını sayısal olarak göster
     (K-11'in doğrulaması).
  3. NMS: örtüşen pencereler tekilleşiyor, max_per_symbol uygulanıyor.
  4. Uçtan uca: sentetik veriye enjekte edilen 20 OBO'nun en az 15'i ilk 12
     sonuçta çıkmalı.
  5. Negatif kontrol: white noise ve düz çizgi sorgusunda en iyi normalize
     skor, pozitif sorguların skorundan belirgin şekilde kötü olmalı.
  6. Performans: 1M satırlık sentetik matriste Aşama 1 < 300 ms.

────────────────────────────────────────────────────────────────────────
ÇALIŞMA BİÇİMİ
────────────────────────────────────────────────────────────────────────

• Sırayla git: F0 → test → F1 → test → F2 → test. Hepsini birden yazıp
  sonunda test etme.
• Sihirli sayı yazma; engine/config.py'den import et. Yeni sabit gerekirse
  oraya K-xx referansıyla ekle.
• Mimariden sapman gerektiğini düşünürsen ÖNCE ilgili K-xx'i oku. Orada
  büyük ihtimalle o alternatif zaten reddedilmiştir. Yine de gerekiyorsa
  bana sor, tek taraflı değiştirme.
• Her fazın sonunda anlamlı bir commit at (docs/ içindeki üsluba uygun,
  Türkçe, ne + neden).
• Bir şey belirsizse varsayım yapıp devam etme — sor.
```

---

## Sonraki oturumlar

| Oturum | Görev |
|---|---|
| 2 | **F3 — notebook doğrulaması** 🚦 (prompt aşağıda) |
| 3 | F4 — Outcome engine (triple-barrier, gölge dağılım, R beklentisi, rejim kırılımı) |
| 4 | F5 — FastAPI + Redis (docs/01-mimari.md §10 spesifikasyonu) |
| 5 | F6 — Next.js Radar arayüzü (MVP 1) |
| 6 | F7 — Backtest sekmesi + outcome kartı (MVP 2) |

---

# Oturum 2 — F3 Prompt'u 🚦

```text
GraphFlow F3. CLAUDE.md yüklendi. F0/F1/F2 bitti, 112 test geçiyor.

ÖNCE OKU:
1. docs/00-tasarim-kararlari.md → K-18 (doğrulama protokolü) ve K-11
   (⚠️ YENİDEN AÇILDI bölümü dahil — bu oturumda karara bağlanacak)
2. docs/01-mimari.md §16 (doğrulama protokolü)
3. engine/search/ ve tools/gen_synthetic.py — mevcut kodu tanı

F3 bir "kapı"dır. Amacı kod yazmak değil, motorun gerçekten ölçüp ölçmediğine
KARAR VERMEK. Çıktısı: notebook'lar, ölçüm sayıları ve yazılı bir rapor.

────────────────────────────────────────────────────────────────────────
ADIM 0 — GERÇEK VERİ (önkoşul)
────────────────────────────────────────────────────────────────────────
F3 sentetik veriyle yapılamaz; sentetik zaten F2'de geçti. Gerçek Binance
verisi şart.

• Önce KÜÇÜK bir evrenle indir: 1d, hacimce ilk 50 USDT paritesi, tam geçmiş.
  Doğrula (bar sayıları, boşluklar, delist edilenlerin varlığı), sonra
  büyüt: 4h + 1d, tam evren. Büyük indirme uzun sürer — küçük evrenle
  ilerlemeye başla, büyüğü arka planda çalışsın.
• Matrisleri üret, ardından K-13 SAĞLIK KONTROLÜ: likidite filtresinden
  sonra yıl bazında kalan pencere sayısını yazdır. 2017–2019 çökmüş
  görünüyorsa aylık kesitsel filtre yanlış uygulanmıştır — düzelt.
• Yarım mum diske yazılmamış olmalı; son barın kapanmış olduğunu doğrula.

────────────────────────────────────────────────────────────────────────
ADIM 1 — K-11 A/B: DDTW mi, ham DTW mi?
────────────────────────────────────────────────────────────────────────
K-11'in gerekçesi F2'de doğrulanmadı (bkz. karar kaydındaki ölçüm tablosu).
Bu oturumda kapatılacak.

• engine/config.py'ye ekle:
  STAGE2_METRIC: Literal["ddtw", "dtw", "hybrid"] = "ddtw"   # K-11
  search/ddtw.py bu anahtarı okusun. "hybrid" = iki normalize mesafenin
  ortalaması. Varsayılanı DEĞİŞTİRME; karar ölçümden sonra.

• Mevcut A/B'nin iki metodolojik kusuru var, ikisini de düzelt:
  (a) DAİRESELLİK: Pozitifler şu an sorgu şablonunun gürültülü kopyası.
      tools/gen_synthetic.py'ye ŞEKİL BOZULMASI ekle: asimetrik omuz
      yükseklikleri, eğimli boyun çizgisi, farklı kulp derinliği/uzunluğu,
      tepe-dip zamanlama kayması. Pozitif = "aynı formasyonun FARKLI bir
      örneği", "aynı eğrinin gürültülüsü" değil. DDTW'nin iddiası tam olarak
      bu varyasyonda test edilmeli.
  (b) UZUNLUK KIRILIMI YOK: 100 bar → 32 nokta yumuşatır, 24 bar → 32 nokta
      yukarı örnekler (interpolasyon artefaktı). AUC'yi pencere uzunluğuna
      göre AYRI AYRI hesapla; tek bir ortalama bunu gizliyor.

• AUC'yi 3 metrik × 4 pencere uzunluğu × 3 gürültü seviyesi için raporla.
• Kazananı config varsayılanı yap. Kaybeden metrik silinmesin, anahtarda
  kalsın. Sonucu K-11'e "Karara bağlandı (F3)" bölümü olarak yaz — ham DTW
  kazanırsa CLAUDE.md'deki "asla yapma" maddesini de güncelle.

────────────────────────────────────────────────────────────────────────
ADIM 2 — NEGATİF KONTROL (gerçek veride)
────────────────────────────────────────────────────────────────────────
Sorgular: düz yatay çizgi, white noise, whipsaw testere, tek yönlü rampa.
Beklenen: "eşleşme yok" ya da en gevşek kademede bile belirgin şekilde kötü
skor. Bunlara iyi skor dönüyorsa metrik ölçmüyor, uyduruyor — motoru düzelt.

Ayrıca SKOR DAĞILIMI SAĞLIK KONTROLÜ: 14 şablonun her biri + 4 negatif için
en iyi skorların histogramını çiz. Tüm sorgular aynı bandı veriyorsa metrik
ayırt etmiyor demektir; bu tek başına F3'ü düşürür.

────────────────────────────────────────────────────────────────────────
ADIM 3 — EŞİK KALİBRASYONU
────────────────────────────────────────────────────────────────────────
DİKKAT — metodolojik tuzak: gerçek veride ETİKET YOK, dolayısıyla gerçek
veriden AUC hesaplanamaz. İş bölümü şöyle:
  • AUC / ROC ve K-11 kararı  → bozulmalı sentetik (etiket biliniyor)
  • Eşik değerleri            → GERÇEK veri skor dağılımları:
      Katı  = negatif kontrollerin pratikte hiç geçemediği nokta
      Orta  = şablon sorgularının ilk 12'sinin rahat geçtiği nokta
      Esnek = pozitif kuyruğun tükendiği nokta
Üç değeri config.TOLERANCE_THRESHOLDS'a yaz, her birinin yanına hangi
ölçümden geldiğini yorum olarak ekle.

────────────────────────────────────────────────────────────────────────
ADIM 4 — GÖZ TESTİ (bu adımı SEN ONAYLAYAMAZSIN)
────────────────────────────────────────────────────────────────────────
notebooks/03_goz_testi.ipynb: 20 sorgu (14 şablon + 6 elle çizilmiş serbest
şekil) için ilk 12 sonucu 3×4 grid PNG olarak render et. Her karo: sembol,
tarih, normalize skor, volatilite etiketi, eşleşen pencere vurgulu.
Çıktıları notebooks/output/ altına kaydet.

Kontrol edilecekler ve raporda yazılı olacaklar:
  • K-09 doğrulaması: 12 karo 12 FARKLI olay mı, yoksa aynı grafiğin
    kaydırılmış kopyaları mı? Kopya varsa post-NMS bozuk.
  • Sembol çeşitliliği: max 3/sembol tutuyor mu?
  • Likidite: ölü pariteler listeyi kirletiyor mu?
  • Uzunluk dengesi: sonuçlar tek bir pencere uzunluğunda mı kümeleniyor?
    Kümeleniyorsa K-14 yol-uzunluğu normalizasyonu eksik/yanlış.

"Evet, bu çalışıyor" kararını BEN vereceğim. Kendi kendine geçti deme;
görselleri üret, gözlemlerini yaz, kararı bana bırak.

────────────────────────────────────────────────────────────────────────
ADIM 5 — RADAR DUMAN TESTİ
────────────────────────────────────────────────────────────────────────
mode='live' ile tüm evrende 3 şablon çalıştır. Süre < 10 ms olmalı.
Dönen sonuçların grafiklerini de render et — canlı modda gelen şeyin
makul görünüp görünmediği erken anlaşılsın.

────────────────────────────────────────────────────────────────────────
ÇIKTILAR
────────────────────────────────────────────────────────────────────────
1. notebooks/  01_veri_kontrol · 02_normalizasyon_gorsel · 03_goz_testi ·
   04_negatif_kontrol · 05_esik_kalibrasyon
2. docs/03-f3-dogrulama-raporu.md — tüm ölçüm tabloları, K-11 kararı ve
   gerekçesi, seçilen eşikler ve nereden geldikleri, GEÇEMEYEN testler.
   Kötü sonucu gizleme; F3'ün amacı zaten kötü haberi erken bulmak.
3. Güncellenmiş engine/config.py (STAGE2_METRIC + gerçek eşikler)
4. Güncellenmiş docs/00-tasarim-kararlari.md → K-11 kapanışı
5. Güncellenmiş CLAUDE.md → durum tablosu (+ K-11 değiştiyse "asla yapma")

KURALLAR
• F4'e (outcome engine) GEÇME. F3 bir kapı; onayı ben vereceğim.
• Bir test geçmiyorsa eşiği gevşetip geçirme — raporla ve bana sor.
• Sihirli sayı yok; her şey config.py'den.
• Her adımın sonunda commit.
• Belirsizlik varsa varsayım yapma, sor.
```
