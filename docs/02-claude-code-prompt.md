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

---

# Oturum 2.5 — F3.5 Prompt'u

F3 kapısı **geçti**. Bu oturum, göz testinde ve S-1…S-5'te çıkan sorunları
F4'ten önce kapatır — çünkü arama önyargısı doğrudan outcome istatistiklerine
geçer.

```text
GraphFlow F3.5. CLAUDE.md yüklendi. F3 kapısı GEÇTİ (göz testi onaylandı).

ÖNCE OKU: docs/03-f3-dogrulama-raporu.md (S-1…S-5), K-10, K-12, K-14, K-11.

Bu oturumun amacı yeni özellik değil, F3'te ölçülen çarpıklıkları kapatmak.
F4'e GEÇME.

────────────────────────────────────────────────────────────────────────
ADIM 1 — Skor kalibrasyonu: S-1, S-2 ve S-3 aynı hatanın üç yüzü
────────────────────────────────────────────────────────────────────────
KÖK SEBEP: skor ölçeği sorgunun yapısal karmaşıklığına bağlı. Monoton rampa
uyuşmazlık üretecek yapıya sahip değil → 0.0025 (S-1). Bayrak basit, üçgen
karmaşık → 0.008'e karşı 0.056 (S-2). Uzun pencerede daha çok yapı, daha çok
uyuşmazlık → sonuçların %68'i 24 barda (S-3).

ŞABLON BAŞINA EŞİK YAZMA. Serbest çizimde kalibrasyon verisi yok; ürünün
yarısı orada. Bunun yerine SORGU-GÖRELİ NULL KALİBRASYONU:

  • Arama anında, sorguyu her pencere uzunluğu için ~2000 RASTGELE pencereye
    karşı skorla → o sorgunun, o uzunluktaki null dağılımı.
  • Eşik mutlak mesafe değil, bu null'un YÜZDELİK DİLİMİ olsun.
    Katı/Orta/Esnek = null'un p0.1 / p1 / p5'i gibi (değerleri ölç, uydurma).
  • Sıralama da uzunluk-içi yüzdelik dilime göre yapılsın; ham mesafeye göre
    değil. K-14'ün yol-uzunluğuna bölmesi yetmiyor — ölçülmüş kanıt S-3.
  • Null örneklemi sorgu başına önbelleklenebilir (şablonlar için önceden
    hesapla; serbest çizimde anlık, ~2000 ek DDTW ≈ 16 ms).

Bu, K-12'nin gölge dağılım fikrinin skorlama katmanına uygulanmasıdır.

S-1'in ürün cevabı buradan TÜRESİN: null dağılımı olağandışı darsa kullanıcıya
"bu şekil piyasada çok sık görülüyor, sonuçlar ayırt edici olmayabilir" uyarısı
göster. Elle kodlanmış "düzlük ölçer" YAZMA.

DOĞRULAMA: kalibrasyondan sonra (a) 14 şablonun kaçı orta kademede ilk sayfayı
dolduruyor (hedef: 14/14), (b) sonuçların pencere uzunluğu dağılımı (hedef:
%68'lik 24-bar hâkimiyeti belirgin şekilde düzelsin), (c) rampa sorgusu artık
her kademeyi geçmiyor.

────────────────────────────────────────────────────────────────────────
ADIM 2 — S-5: sabitlenmiş parite + genlik varsayılanı
────────────────────────────────────────────────────────────────────────
config'e eklenmiş PEG_* ve DEFAULT_MIN_AMPLITUDE sabitlerini arama yoluna
gerçekten bağla ve varsayılan olarak AÇ. İki katman birlikte:
yapısal peg filtresi (evrenden düşür) + genlik varsayılanı (aramada).
Doğrulama: OBO ilk sayfasında stablecoin kalmamalı.

────────────────────────────────────────────────────────────────────────
ADIM 3 — Veri boşlukları: TESPİT ET, DOLDURMA
────────────────────────────────────────────────────────────────────────
Binance'te 2017–2019 bakım kesintileri ve işlem durdurmaları nedeniyle eksik
barlar var.

⛔ FORWARD FILL (ffill) KULLANMA. Uydurulmuş bar:
   • True Range = 0 üretir → ATR yapay olarak düşer → K-16 bariyerleri
     daralır → sahte TP/SL çarpmaları. Tüm istatistik katmanını bozar.
   • Şekle yapay düz plato ekler → uydurma formasyon.
   • volume = 0 → aylık likidite sıralamasını (K-13) bozar.

✅ BUNUN YERİNE:
   1. ZAMAN SÜREKLİLİĞİ INVARIANT'ı (asıl çözüm, vektörize ve ucuz):
      bir pencere ancak
          end_time - start_time == (L - 1) * TIMEFRAME_MS
      ise matrise girer. Aksi hâlde pencere DÜŞÜRÜLÜR.
      Boşluk içeren bir pencere bugün 24 bar sanılıp 40 takvim günü kapsıyor
      olabilir — asıl yapısal bozulma bu ve bu kontrol onu tamamen kapatır.
      1,9M pencerede birkaç bin kayıp önemsiz; doğruluk pahalı.
   2. Boşluk raporu: sembol × yıl bazında eksik bar sayısı ve en uzun boşluk.
      notebooks/output/ altına tablo + grafik.
   3. Delist edilmiş paritenin veri SONU boşluk değildir; karıştırma.
   4. Regresyon testi: kasıtlı boşluklu seri → boşluklu pencereler matriste
      görünmemeli.

Ayrıca VERİ TAZELİĞİ invariant'ı ekle (mikrosaniye bug'ının tekrarına karşı):
config.MAX_DATA_STALENESS_DAYS = 4 (hafta sonu payı dahil).

⚠️ KAPSAM TUZAĞI — iki hatayı yapma:
   • Kontrol SEMBOL BAZINDA OLMAZ. Delist edilmiş paritenin max(close_time)'ı
     tanımı gereği eskidir; sembol bazlı assert her delist parite için patlar.
     Doğrusu: (a) evren geneli max(close_time), (b) yalnızca AKTİF semboller
     için sembol bazlı kontrol.
   • Assert INGEST pipeline'ını kırsın, arama motorunu DEĞİL. Motor içinde
     sert assert olursa bayat veri tüm ürünü kullanılamaz hâle getirir;
     oysa doğru davranış "çalış ama uyar". Motor tarafında yalnızca
     SearchResult'a `data_as_of` alanı ve bayat ise uyarı bayrağı ekle.

────────────────────────────────────────────────────────────────────────
ADIM 4 — Zaman ekseni asimetrisi + K-11'in YENİDEN ölçülmesi
────────────────────────────────────────────────────────────────────────
K-11 A/B'si DTW'nin VAROLUŞ SEBEBİ test edilmeden karara bağlandı: zaman
bükülmesi. Bu eksiklik giderilmeli ve A/B yeniden çalıştırılmalı.

DİKKAT — neyin zaten çözüldüğünü karıştırma: her pencere 32 noktaya
resample edildiği için KÜRESEL süre farkı (10 günlük çanak vs 50 günlük çanak)
zaten normalize. Test edilmemiş olan İÇ ZAMANLAMA ASİMETRİSİ:

  tools/variants'a ekle:
   • OBO: sol omuz 5 barda, sağ omuz 15 barda oluşsun (ve tersi)
   • Çanak: iniş hızlı / çıkış yavaş, ve tersi
   • İkili tepe: iki zirve arası mesafe daralsın / genişlesin
   • Baş, pencerenin merkezinden erkene/geçe kaysın
  Bozulma miktarını parametrik yap (hafif / orta / şiddetli) ve AUC'yi
  bozulma seviyesine göre kır.

SONRA K-11 A/B'sini (ddtw / dtw / hybrid) bu yeni pozitiflerle TEKRAR çalıştır.
Kazanan değişirse config varsayılanını ve CLAUDE.md maddesini güncelle,
K-11'e "İkinci ölçüm (F3.5)" bölümü yaz. Değişmezse de yaz — hybrid kararı
artık zaman ekseninde de sınanmış olur.

────────────────────────────────────────────────────────────────────────
ADIM 5 — Negatif kontrole "ters şekil" tuzağı
────────────────────────────────────────────────────────────────────────
Mevcut negatifler (düz çizgi, white noise, testere) rastgeleliği eliyor ama
YÖN hassasiyetini test etmiyor.

Ekle — her biri ayrı bir assert:
   • Çanak sorgusu, ters çanak (∩) pencerelerini eşleştirmemeli
   • İkili dip sorgusu, ikili tepeyi eşleştirmemeli
   • OBO sorgusu, ters OBO'yu eşleştirmemeli
   • Yükselen takoz ↔ düşen takoz

Beklenti: bu çiftlerin mesafesi, pozitiflerden belirgin şekilde kötü olmalı.
GEÇMESİ BEKLENİYOR (z-score korelasyonu yönü korur) — ama geçmezse bir yerde
mutlak değer/kare alınıyor demektir ve bu ölümcül bir hatadır. Ucuz, yüksek
değerli bir assert.
Simetrik üçgen gibi kendine-yakın-simetrik şekillerde beklenti düşük; bunu
test etme, raporla.

────────────────────────────────────────────────────────────────────────
ADIM 6 — Göz testine blueprint overlay
────────────────────────────────────────────────────────────────────────
3×4 grid karolarına İKİ katman bindir:
   A) Kanonik şablon (z-score, pencerenin fiyat aralığına geri ölçeklenmiş),
      soluk kesikli çizgi → "aradığın şey"
   B) DTW hizalama yoluyla BÜKÜLMÜŞ şablon, farklı renk → "motor bunu buna
      hizaladı"

A ile B'nin birbirinden çok ayrıldığı karolar, eşleşmenin ağır bükülmeyle
kurulduğunu gösterir; bunlar şüphelidir. Her karo için BÜKÜLME MİKTARI da
hesapla (hizalama yolunun köşegenden sapması) ve etikete yaz. Şimdilik
yalnızca ölç ve raporla — filtreye çevirme, kanıt biriksin.

Bu aynı zamanda ürünü anlatırken en güçlü görsel olacak.

────────────────────────────────────────────────────────────────────────
ADIM 7 — K-04'ün geometrik kural katmanı (çapa tabanlı)
────────────────────────────────────────────────────────────────────────
DTW yolları hizalar, hizalanan noktaların SEVİYELERİNİN mantıklı olup
olmadığını umursamaz. OBO'da yuvarlak tepelerin sızması bundandır.

⚠️ SIRALAMA ŞARTI — bu adımı ADIM 1'DEN SONRA yap ve İKİ ÖLÇÜM AL:
   (a) yalnızca yüzdelik skorlama sonrası OBO ilk 12'si
   (b) üstüne geometrik filtre eklendikten sonra
Yüzdelik skorlama yuvarlak tepeleri zaten eliyorsa filtre gereksizdir ve
EKLENMEZ. Kural katmanı ancak ölçülmüş bir katkı gösterirse kalır. Bu, bir
mekanizmayı işe yaradığını kanıtlamadan mimariye sokmamak içindir.

MEKANİZMA — tepe/dip arayan ayrı bir sezgisel YAZMA. Elimizde zaten DTW
hizalama yolu var: kanonik şablonun i. noktası, pencerenin hangi barına
hizalandığını biliyoruz. Çapaları bu yoldan oku.

Kuralı ŞABLON META-VERİSİ olarak tanımla, koda gömme (K-04 böyle korunur —
formasyon başına if-else yazmıyoruz, tek bir genel değerlendirici var):

  {
    "id": "head_and_shoulders",
    "points": [...],
    "constraints": [
      { "type": "level_match",  "anchors": [8, 22], "max_diff": 0.25,
        "comment": "boyun çizgisi: iki dip aynı seviyede olmalı" },
      { "type": "level_order",  "anchors": [5, 16, 27],
        "order": ["<", ">"],   "comment": "baş, iki omuzdan da yüksek" }
    ]
  }

  • anchors = KANONİK vektördeki nokta indeksleri; hizalama yolu bunları
    pencere barlarına çevirir.
  • max_diff = z-score birimi cinsinden (pencereden bağımsız, ölçek-değişmez).
  • Değerlendirici tek ve genel: engine/search/constraints.py.
  • constraints alanı OLMAYAN şablon hiçbir ek filtreden geçmez — mevcut
    davranış korunur.

Uygulama noktası: post-NMS'ten HEMEN ÖNCE (elenen aday NMS bütçesini yemesin).

Aynı mekanizmayı ikili tepe/dip için de tanımla (iki zirve aynı seviyede) —
mekanizmanın tek formasyona özel olmadığını kanıtlamak için. Diğerlerine
DOKUNMA.

FİNCAN/KULP — ayrı ve daha basit sorun:
   • cup_and_handle ile rounding_bottom sonuç kümelerinin örtüşme oranını ölç.
   • Kanonik fincan vektöründeki kulbu derinleştir (çanak derinliğinin en az
     %30'u), ölçümü tekrarla.
   • Ayrım hâlâ açılmıyorsa İNATLAŞMA: raporla ve ikisini rounding_bottom
     altında birleştirmeyi öner. Birleştirme kararını ben vereceğim.

────────────────────────────────────────────────────────────────────────
ADIM 8 — Radar bütçesi
────────────────────────────────────────────────────────────────────────
S-4 bir hata değil, bütçe hatası: 10 ms 500 sembol varsayarak yazılmıştı,
evren 1.165'e çıktı ve doğrusal ölçekleniyor.
config.RADAR_LATENCY_BUDGET_MS = 50 ekle, docs/01-mimari.md §15'i güncelle,
gerekçesini yaz. Optimizasyon YAPMA — 1.165 parite için 23 ms iyi bir sayı.

────────────────────────────────────────────────────────────────────────
ÇIKTILAR
────────────────────────────────────────────────────────────────────────
1. docs/04-f35-raporu.md — her adımın öncesi/sonrası sayıları, K-11 ikinci
   ölçümü, boşluk raporu, çözülemeyenler.
2. Güncellenmiş config (null kalibrasyon sabitleri, peg/genlik aktif).
3. Yeniden üretilmiş göz testi PNG'leri (blueprint overlay'li) — en az
   cup_and_handle, head_and_shoulders, ascending_triangle, bir serbest çizim.
4. Güncellenmiş K-11, K-14, CLAUDE.md ve docs/fazlar/F3.5-temizlik.md.

★ ÇIKIŞ ŞARTI — bana şu ikisiyle dön:
   goz_testi_esnek_head_and_shoulders.png
   goz_testi_esnek_cup_and_handle.png
   (yüzdelik skorlama + blueprint overlay ile yeniden üretilmiş)
   Bu iki görsel "pürüzsüz çalışıyor" hissini veriyorsa F4'e geçiyoruz.
   OBO için ADIM 7'deki (a)/(b) karşılaştırmasını da ayrıca göster.

KURALLAR
• F4'e geçme. • Test geçmiyorsa eşiği gevşetme, sor. • Sihirli sayı yok.
• Her adımda commit. • Belirsizlikte sor.
```

---

# Oturum 3 — F4 Prompt'u (Outcome Engine)

F3.5 **geçti** (göz testi onaylandı, 31 Tem 2026). Bu, ürünün tacı — ve
istatistiksel dürüstlüğün sınandığı yer.

```text
GraphFlow F4 — Outcome Engine. CLAUDE.md yüklendi. F3.5 GEÇTİ.

ÖNCE OKU: K-06, K-09, K-12, K-16 (tüm alt bölümleriyle) ve
docs/fazlar/F4-outcome-engine.md.

Bu faz "sonra ne oldu?" kartını üretir. Ürünün tek satılabilir iddiası bu
sayıların DÜRÜST olmasıdır. Bir edge'i olduğundan büyük göstermek, hiç
edge bulamamaktan daha kötüdür.

────────────────────────────────────────────────────────────────────────
ADIM 0 — Kapsam ve p-hacking kilidi
────────────────────────────────────────────────────────────────────────
Skorlar artık yüzdelik olduğu için istatistiğe giren eşleşme kümesi
tolerans kademesine göre DEĞİŞİR — dolayısıyla N ve beklenti de değişir.

• config.OUTCOME_TOLERANCE = "medium" SABİTLE ve rapora yaz.
• Kademe oynatarak sayı güzelleştirme YASAK. Başka kademe merak
  ediliyorsa hepsi birlikte raporlanır, biri seçilip sunulmaz.
• Aynı kural şablon seçimi için de geçerli: 14 şablonun TAMAMI tek
  tabloda raporlanır. "En iyi 3 formasyon" diye sunum yapma — bu,
  çoklu karşılaştırma probleminin ta kendisi.

────────────────────────────────────────────────────────────────────────
ADIM 1 — Triple-barrier çekirdeği (K-16)
────────────────────────────────────────────────────────────────────────
t₀ = formasyonun bittiği bar · C₀ = kapanış · ATR = ATR(14)

🚫 ATR YALNIZCA t₀'A KADARKİ BARLARDAN. Geleceğe bakan tek satır tüm
   katmanı geçersiz kılar. Birim testi ZORUNLU.

Bariyerler:  TP = C₀ + k_tp·ATR   SL = C₀ − k_sl·ATR   T = round(0,5·L)
Konfigürasyonlar: 2:1 (null %33,3) ve 1:1 (null %50) — İKİSİ BİRDEN.

Zorunlu kurallar:
 • Aynı barda hem TP hem SL → SL ÖNCE ÇARPTI (muhafazakâr). Raporla.
 • 1×ATR / C₀ < %1 ise pencere istatistiğe GİRMEZ (K-16.7).
 • Komisyon: R_net = R_brüt − (gidiş_dönüş_ücret / atr_pct).
   config.ROUNDTRIP_FEE_PCT = 0.001 (Binance taker ~%0,05 ×2).
   Hem brüt hem net raporla.

⚠️ DELİST TUZAĞI — bunu yanlış yaparsan K-13'ün tüm emeği çöpe gider:
   Bir eşleşme, delist edilmiş bir paritenin sonuna yakınsa ileri pencere
   kesiktir. Bu pencereleri ELEME — elersen ölmek üzere olan coinlerin
   en kötü sonuçlarını sistematik olarak atmış olursun ve survivorship
   bias arka kapıdan geri girer.
   DOĞRUSU: delist = zorunlu çıkış. Son mevcut kapanıştan çık, sonucu
   "delist_exit" olarak etiketle ve döküme ayrı satır olarak yaz.

────────────────────────────────────────────────────────────────────────
ADIM 1B — Uygulama mekaniği (bunlar olmadan motor ya yavaş ya yanlış)
────────────────────────────────────────────────────────────────────────

■ VEKTÖRİZASYON — argmax hilesi
  Python for döngüsü yazma. ~10.000 olay × 20 gölge × 50 bar = 10M kontrol.

    tp_mask = High_mat >= TP[:, None]          # (N, T)
    sl_mask = Low_mat  <= SL[:, None]
    tp_idx = np.where(tp_mask.any(1), tp_mask.argmax(1), T)   # ⚠️ argmax
    sl_idx = np.where(sl_mask.any(1), sl_mask.argmax(1), T)   #    hiç
    # çarpmadığında da 0 döner — .any() maskesi ZORUNLU
    first = np.minimum(tp_idx, sl_idx)
    is_sl = sl_idx <= tp_idx                   # eşitse SL kazanır (K-16)

  ⚠️ İKİ TUZAK:
  1) T DEĞİŞKEN: T = 0,5·L ve L ∈ {24,40,64,100} → T ∈ {12,20,32,50}.
     Tek bir (N,T) matrisi kurulamaz. Olayları PENCERE UZUNLUĞUNA GÖRE
     GRUPLA, her grubu kendi matrisi olarak işle.
  2) KISA İLERİ PENCERE (delist / veri sonu): satırlar T bardan kısa olur.
     Dolgu yaparken high'ı −inf, low'u +inf ile doldur — böylece dolgu
     hücreleri hiçbir zaman bariyer tetikleyemez. Geçerli bar sayısını
     ayrı bir maskede tut, delist çıkışı son GEÇERLİ kapanıştan al.

■ GAP / SLİPAJ GERÇEKLİĞİ
  Bariyer 58.000, mum 57.000'den AÇILDI → 58.000'de satamazdın.
  KURAL: Bir mumun Open fiyatı bariyerin ötesindeyse, çıkış fiyatı bariyer
  değil o mumun OPEN fiyatıdır.

    exit_px = where(gap_beyond_barrier, Open[first], barrier_px)

  ⚠️ BU KURAL HER İKİ YÖNE DE UYGULANIR — yalnız SL'e uygularsan sistematik
  aşağı yanlılık yaratırsın ve edge'i olduğundan kötü gösterirsin. Yukarı
  gap'te TP çıkışı 2R'den İYİ olabilir; bu gerçektir, kırpma.
  Kripto 1D'de gap seyrektir ama bakım/delist/flash-crash anlarında olur.

■ ZAMAN BARİYERİ ÇIKIŞ FİYATI
  T süresince TP/SL vurulmazsa çıkış, t₀+T barının KAPANIŞ (Close) fiyatıdır.
  O barın High/Low'u önemsizdir — süre dolduğu an taker market emri.

■ ATR ISINMA SÜRESİ
  Coin 8 gündür listeliyse ATR(14) hesaplanamaz; listeleme günlerinin
  pump/dump oynaklığı hem ATR'yi hem sonucu bozar.
  config.MIN_BARS_SINCE_LISTING = 28  (2 × ATR_PERIOD)
  Wilder ATR bir EMA özyinelemesidir; 14 barda tohumlanır ama ~2 periyot
  boyunca yakınsamaya devam eder. t₀ bu eşiğin altındaysa olay DÜŞER.
  Not: pencere zaten L ≥ 24 bar istediği için bağlayıcı olan kısım dar;
  yine de kaç olayın düştüğünü raporla — bu hafif bir seçim etkisidir.

────────────────────────────────────────────────────────────────────────
ADIM 2 — 🚦 NULL KAPISI (her şeyden önce bu geçmeli)
────────────────────────────────────────────────────────────────────────
GERÇEK SONUÇ ÜRETMEDEN ÖNCE motoru rastgele pencerelerde çalıştır
(n ≥ 5.000, aynı likidite ve maliyet filtreleriyle):

    2:1 başarı  ≈ %33,3   (±%2)
    1:1 başarı  ≈ %50,0   (±%2)
    beklenti    ≈ 0R      (net R'de hafif negatif olmalı — komisyon)

Sapma varsa DURDUR ve sebebini bul. Olası sebepler: lookahead, bar
sıralama hatası, ATR penceresi kayması, aynı-bar kuralının yanlış
uygulanması, delist kesintisinin yanlış ele alınması.

Bu test, mimarinin kendi kendini denetleme mekanizmasıdır ve arama
kalitesinden BAĞIMSIZDIR. Geçmeden ADIM 3'e geçme.

Not: kripto uzun vadede yukarı eğilimli olduğu için 1:1'de %50'nin biraz
üstü beklenebilir. Ölçtüğün sapmayı raporla, gizleme — bu sapma zaten
gölge dağılımın var olma sebebidir.

⚠️ GAP KURALI NULL KAPISINI ETKİLER: Gap çıkışları ödemeleri tam ±k·ATR
olmaktan çıkarır, dolayısıyla teorik null yalnızca ÇARPMA ORANI için
geçerlidir; beklenti gap etkisiyle biraz kayar.
  • Kapı kriteri = çarpma oranı (%33,3 / %50,0 ± %2) — sert.
  • Beklenti için tolerans daha geniş tut ve sapmayı gap istatistiğiyle
    birlikte raporla (kaç çıkış gap'ten oldu, ortalama gap büyüklüğü).
  • Ek doğrulama: gap kuralını KAPATIP çalıştır — o zaman beklenti 0R'ye
    çok daha yakın çıkmalı. Çıkmıyorsa hata gap'te değil, başka yerde.

────────────────────────────────────────────────────────────────────────
ADIM 3 — Zaman-eşleştirmeli gölge dağılım (K-12)
────────────────────────────────────────────────────────────────────────
Her eşleşme için: bitiş ayını al → AYNI AYDAN, FARKLI SEMBOLLERDEN,
aynı likidite + genlik + maliyet filtrelerini geçen P=20 rastgele pencere
çek → aynı triple-barrier'ı uygula.

• F3.5'te kurduğun rastgele pencere örnekleme ve önbellekleme tesisatını
  YENİDEN YAZMA, üstüne bindir. (Örnekleme kuralı farklı, tesisat aynı.)
• Gölge havuzu eşleşmelerin zaman dağılımını BİREBİR taklit etmeli;
  doğrula ve raporla (ay bazında eşleşme sayısı vs gölge sayısı).

⚠️ GÖLGEYE DE İLERİ PENCERE NMS'i UYGULA — atlanması çok kolay ve
   doğrudan dürüstlük garantisini hedef alır:
   Aynı sembolde çekilen gölge pencerelerin T-barlık ileri ufukları
   kesişirse null dağılımı KENDİ İÇİNDE otokorelasyonlu olur → gölgenin
   varyansı olduğundan küçük ölçülür → edge'in GA'sı sahte biçimde daralır
   → anlamsız bir farkı ANLAMLI ilan edersin.
   Kural: gölge örnekleminde de aynı sembolde ardışık pencereler arasında
   en az T bar ayrım. Ayrıca tekilleştirme AY HAVUZU GENELİNDE yapılsın —
   yalnız tek bir eşleşmenin 20'lisi içinde değil; farklı eşleşmelerin
   gölgeleri de birbirini tekrar edebilir.
   Reddedilen örnek sayısını raporla; havuz yetersiz kalırsa P<20'ye düş
   ve bunu kaydet, aynı pencereyi iki kez sayma.

────────────────────────────────────────────────────────────────────────
ADIM 4 — İstatistik: güven aralığı olmadan sayı yayınlama
────────────────────────────────────────────────────────────────────────
⚠️ EN KRİTİK ADIM. Örnek hesap: n=112, p=0,41 → %95 GA ≈ ±9 puan →
   [%32, %50]. Teorik null %33 bu aralığın İÇİNDE. Yani "+6 puan edge"
   istatistiksel olarak ANLAMSIZ olurdu.

Zorunlular:
 • Beklenti (R) için BOOTSTRAP güven aralığı (≥10.000 yeniden örnekleme).
   R sürekli bir değişken; binom GA'sı yerine bootstrap kullan.
 • Başarı oranı için Wilson skor aralığı.
 • Edge = E_formasyon − E_gölge için de GA. İki dağılımın farkını
   bootstrap'la (eşleştirilmiş değil, bağımsız iki örneklem).
 • KARAR KURALI: Edge'in %95 GA'sı sıfırı içeriyorsa çıktı
   "anlamlı fark ölçülemedi" olur. "+6 puan" diye yazılmaz.

BAĞIMSIZ N — iki katman:
 1. Post-NMS'ten geçmiş tekil olaylar (K-09) — zaten var.
 2. ⚠️ İLERİ PENCERE ÖRTÜŞMESİ — bu YENİ ve atlanması kolay:
    NMS formasyon pencerelerinin örtüşmediğini garanti eder, ama iki
    eşleşme aynı sembolde 5 bar arayla ise T=12'lik SONUÇ pencereleri
    7 bar örtüşür → sonuçlar korelasyonlu → N yine şişer.
    Aynı sembolde ardışık eşleşmeler arasında en az T bar ayrım zorunlu
    kıl. Kaç olayın bu yüzden düştüğünü raporla.

REJİM KIRILIMI:
 • Yıl bazında kırarsan hücre başına ~14 olay kalır — kullanılamaz.
 • 3 kaba rejim kullan: 2017-2020 · 2021-2022 · 2023-bugün.
 • Her hücrede n < 30 ise sayıyı göster ama "yetersiz örnek" işaretle.

────────────────────────────────────────────────────────────────────────
ADIM 5 — Rapor ve kart
────────────────────────────────────────────────────────────────────────
14 şablon × 2 konfigürasyon için tam tablo: n, başarı, GA, beklenti (brüt
ve net), GA, teorik null, gölge, edge, edge GA, sonuç dökümü
(tp/sl/time/delist_exit).

Kart formatı (K-06):
    Hedef: 2R (≈ %7,4)  ·  Stop: 1R (≈ %3,7)
    Beklenti: +0,18R  [%95 GA: −0,04 … +0,41]
    Başarı:   %41 [%32–%50]  (null %33 · gölge %34)
    N = 112 bağımsız olay
    ⓘ Bu veriler geçmiş dağılımlardır, kesin bir işlem sinyali değildir.

GA sıfırı içeriyorsa kart bunu AÇIKÇA söylesin. Ürünün itibarı buna bağlı.

────────────────────────────────────────────────────────────────────────
ÇIKTILAR
────────────────────────────────────────────────────────────────────────
1. engine/outcome/ (triple_barrier, shadow, metrics)
2. docs/05-f4-raporu.md — null kapısı sonuçları, tam şablon tablosu,
   rejim kırılımı, anlamlı çıkmayan formasyonlar DAHİL
3. notebooks/06_outcome.ipynb — dağılım grafikleri, GA görselleri
4. Güncellenmiş docs/fazlar/F4-outcome-engine.md ve CLAUDE.md

KURALLAR
• F5'e (API) geçme.
• Hiçbir sayı baseline ve GA olmadan yayınlanmaz.
• Anlamlı çıkmayan formasyonlar da raporlanır — asıl değer orada.
• Sihirli sayı yok, her şey config'den. • Her adımda commit.
• Null kapısı geçmeden ilerleme. • Belirsizlikte sor.
```
