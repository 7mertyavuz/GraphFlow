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

---

# Oturum 3.5 — F4.5 Prompt'u (İstatistiksel Sağlamlaştırma)

F4 bitti. İki iş kaldı ve ikisi de **tek pozitif iddianın (alçalan üçgen)
kaderini** belirliyor. Küçük bir oturum; F5'i bloke etmiyor ama yanlış GA
yayınlayıp sonra düzeltmekten iyidir.

```text
GraphFlow F4.5 — istatistiksel sağlamlaştırma. CLAUDE.md yüklendi.
F4 bitti (a5be140, 176 test, null kapısı geçti).

ÖNCE OKU: docs/05-f4-raporu.md (özellikle "bilinen sınırlar"), K-12, K-16.

F4'ün iki açık sınırı var; ikisi de raporun TEK pozitif sonucunu tehdit
ediyor. Bu oturum yeni özellik eklemez, mevcut sayıları sağlamlaştırır.

────────────────────────────────────────────────────────────────────────
ADIM 1 — Ay-bloklu bootstrap (kesitsel korelasyon)
────────────────────────────────────────────────────────────────────────
PROBLEM: Gölge havuzu "aynı ay, farklı sembol" kuralıyla çekiliyor. Ama
kripto sembolleri birbirine yüksek korelasyonlu; aynı aydan 20 farklı
sembol 20 BAĞIMSIZ gözlem vermez. Mevcut bootstrap onları iid varsayıyor
→ gölge varyansı olduğundan küçük → edge GA'sı sahte biçimde dar →
anlamsız bir farkı ANLAMLI ilan etme riski.

ÇÖZÜM — blok bootstrap, blok birimi = TAKVİM AYI:
 • Ayları yerine koyarak (with replacement) yeniden örnekle.
 • Seçilen her ayın TÜM eşleşmelerini ve TÜM gölgelerini birlikte al —
   böylece ay içi korelasyon bloğun içinde kalır ve eşleştirme korunur.
 • Her yeniden örneklemede E_eşleşme − E_gölge hesapla. ≥10.000 tekrar.
 • Yeni altyapı yazma; mevcut bootstrap'ın ÖRNEKLEME BİRİMİNİ değiştir.

ÖLÇ VE RAPORLA:
 • Tasarım etkisi = SE_blok / SE_iid. Tek sayı, korelasyonun anlamlılığı
   ne kadar şişirdiğini doğrudan gösterir. Raporun en açıklayıcı satırı.
 • Evren geneli aylık ortalama ikili getiri korelasyonu (ampirik sayı).
 • ⚠️ Formasyon başına n_events YANINDA n_months yaz. n=112'nin 8 aya
   yayılması ile 60 aya yayılması TAMAMEN farklı kanıt gücüdür; blok
   bootstrap bunu otomatik cezalandıracak ama okuyucu sebebini görmeli.

Tüm 14 şablon × 2 konfigürasyon yeniden çalıştırılır, Bonferroni tekrar
uygulanır.

BEKLENTİM: alçalan üçgen anlamlılığını KAYBEDER (+0,303R [+0,023; +0,590]
alt sınırı zaten sıfıra çok yakın). Kaybederse rapor "hiçbir formasyonda
anlamlı pozitif edge ölçülemedi" olur — bu dürüst ve savunulabilir bir
sonuçtur, kötü bir sonuç değil. Sayıyı kurtarmaya ÇALIŞMA.

────────────────────────────────────────────────────────────────────────
ADIM 2 — Ayna (short) yönü
────────────────────────────────────────────────────────────────────────
Alçalan üçgen bir DÜŞÜŞ formasyonu ama long ölçüldü; pozitif sonuç şu hâlde
yorumlanamıyor. Ayna yönü bunu ayrıştırır.

UYGULAMA (makine hazır, bariyerleri çevir):
 • TP = C₀ − k_tp·ATR   ·   SL = C₀ + k_sl·ATR
 • Aynı-bar kuralı da çevrilir: ikisi de aynı barda vurulduysa yine SL
   önce sayılır (SL artık YUKARIDA).
 • Gap kuralı simetrik uygulanır.
 • Komisyon, maliyet tabanı, delist zorunlu çıkışı aynen geçerli.

NULL KAPISINI SHORT İÇİN DE ÇALIŞTIR: −σ²/2 düzeltmesiyle fiyat martingale
olduğundan short null'ları long ile AYNI olmalı (%33,3 / %50,0). Değilse
bariyer çevirmede hata var. Bu ucuz ve kesin bir kontrol.

AYRIŞTIRICI TEST — alçalan üçgen:
 • short da POZİTİF → ölçüm hatası. Aynı pencerelerde iki yön birden
   kazanamaz. Dur ve sebebini bul.
 • short NEGATİF → long pozitifi tutarlı bir hikâyeye oturur
   (kapitülasyon sonrası ortalamaya dönüş).
 • short NULL → long pozitifi büyük olasılıkla gürültüdür.

AYRICA İLGİNÇ: F4'te gölgesinden anlamlı biçimde KÖTÜ çıkan beş yükseliş
dönüş formasyonu (çanak dip, ters OBO, ikili dip, fincan-kulp, yükselen
takoz) short yönde İYİ çıkıyor mu? Çıkıyorsa bu tersine çevrilmiş ama
gerçek bir bulgudur ve raporun en ilginç kısmı olur. Çıkmıyorsa da yaz.

────────────────────────────────────────────────────────────────────────
ADIM 3 — Çoklu karşılaştırma ailesini güncelle
────────────────────────────────────────────────────────────────────────
Short eklenince test sayısı 28 → 56 olur. Bonferroni ailesi 56 üzerinden
yeniden hesaplanır (α = 0,05/56) ve LONG sonuçlar da bu yeni eşikle tekrar
raporlanır — aile büyüdüğünde eski sonuçlar da sertleşir, bunu gizleme.

simmetrical_triangle N=4 ile kullanılamaz: tablodan çıkarma ama
"ölçülemedi (N yetersiz)" diye işaretle ve test ailesine DAHİL ETME.

────────────────────────────────────────────────────────────────────────
ÇIKTILAR
────────────────────────────────────────────────────────────────────────
1. docs/06-f45-raporu.md — tasarım etkisi, ampirik korelasyon, n_months
   sütunlu tam tablo (14 × 2 konfig × 2 yön), yeni Bonferroni eşiği,
   alçalan üçgen kararı, beş yükseliş formasyonunun short karşılığı.
2. Güncellenmiş K-12 (blok bootstrap artık yöntemin parçası) ve
   docs/fazlar/F4-outcome-engine.md.
3. CLAUDE.md'ye yeni kural: "Gölge dağılımda kesitsel korelasyon —
   GA'lar daima ay-bloklu bootstrap ile; iid bootstrap anlamlılığı şişirir."
4. Sonuç özeti tek cümlede: kaç formasyonda anlamlı pozitif edge var.

SINIR OLARAK YAZ (çözme, kaydet):
 • Tüm ölçüm tek veri kümesi üzerinde (Binance spot, 1d, 2017–2026).
   Örneklem dışı doğrulama yok. 4h matrisleri kurulduğunda kısmî bir
   sağlamlık kontrolü olarak kullanılabilir — aynı varlıklar ama aynı
   sürecin farklı örneklemesi.

KURALLAR
• F5'e geçme. • Sayı kurtarmaya çalışma; ölçüm ne diyorsa o.
• Sihirli sayı yok. • Her adımda commit. • Belirsizlikte sor.
```

---

# Oturum 4 — F4.6 + F5 (Vekil Testi + API)

F4.5 bitti. Elimizde **tek bir iddia** var: yükselen takoz, short +0,331R.
Bu oturum önce o iddianın gerçek olup olmadığını sınar, sonra API'yi kurar.

```text
GraphFlow F4.6 + F5. CLAUDE.md yüklendi. F4.5 bitti.

ÖNCE OKU: docs/06-f45-raporu.md · docs/01-mimari.md §9-§10 · K-06, K-08,
K-12, K-15 · docs/fazlar/F5-api.md

Bu oturum iki parçalı. BÖLÜM A'yı bitirmeden BÖLÜM B'ye geçme — A'nın
sonucu API'nin servis edeceği manşeti değiştirebilir.

════════════════════════════════════════════════════════════════════════
BÖLÜM A — F4.6: Yükselen takoz gerçek mi, vekil mi?
════════════════════════════════════════════════════════════════════════

ŞÜPHE: F4.5'te short yönde iyi çıkan formasyonların HEPSİ (yükselen takoz,
ters OBO, çanak dip, fincan-kulp, ikili dip) ortak bir özelliği paylaşıyor:
yükselen bir hareketin sonunda, yerel bir tepede bitiyorlar. Üstüne
min_amplitude=%15 filtresi var. Yani her eşleşme "en az %15 yükselmiş ve
tepede bitmiş" bir pencere.

Ölçtüğümüz şey formasyonun ŞEKLİ olmayabilir — "yakın zamanda çok yükseldi"
nin kısa vadeli ortalamaya dönüşü olabilir. O zaman 6 ayrı formasyon bulgusu
değil, TEK bir momentum-tersine-dönüş bulgusu vardır.

Mevcut gölge bunu ayıramıyor: aynı AYDAN çekiyor, aynı ÖN-GETİRİDEN değil.

■ ADIM A1 — Genlik/yön eşleştirmeli gölge
  Gölge örnekleme kriterine bir koşul daha ekle:
    aynı ay  VE  farklı sembol  VE  benzer ön-getiri
  Ön-getiri = pencerenin kendi içindeki toplam log getirisi.
  Eşleştirme bandı: ±0,25σ (evren geneli pencere getirisi dağılımının σ'sı).
  Bandı config'e koy, seçimini gerekçelendir, duyarlılık için ±0,15 ve
  ±0,50 ile de çalıştır — sonuç banda duyarlıysa bu başlı başına bir bulgu.

  Diğer her şey aynı kalır: ay-bloklu bootstrap, ileri pencere NMS, gölge
  içi NMS, maliyet tabanı, delist çıkışı.

■ ADIM A2 — Karar
  Yükselen takoz (short) bu gölgeye karşı:
   • Edge SAĞ KALIRSA  → bulgu şekille ilgili. Manşet: "yükselen takoz,
     benzer büyüklükte yükselmiş pencerelere göre de daha kötü performans
     veriyor." Bu güçlü bir iddia.
   • Edge KAYBOLURSA   → formasyon bir VEKİL. Manşet değişir: "kriptoda
     kısa vadeli momentum tersine dönüşü ölçtük; klasik formasyonlar bunu
     seçiyor ama şekil ek bilgi taşımıyor." Bu da değerli ve dürüst bir
     bulgudur — gizleme, ÖNE ÇIKAR.
  Aynı testi diğer dört formasyona da uygula; hepsi birlikte kaybolursa
  tek-etki hipotezi doğrulanmış olur.

■ ADIM A3 — Eksik sayıyı raporla
  Yükselen takozun n_months değeri raporda yok. 252 olayın kaç aya yayıldığı
  kanıt gücünü belirliyor. Tüm formasyonlar için n_months tablosunu ver.

■ ADIM A4 — 4h ile kısmî örneklem dışı kontrol
  4h matrisleri henüz kurulmadıysa kur (F1 pipeline hazır). Yükselen takozu
  4h'de de çalıştır. Tam bağımsız değil (aynı varlıklar, aynı dönemler) —
  raporda BÖYLE yaz, "örneklem dışı doğrulandı" deme.

  ÇIKTI: docs/07-f46-raporu.md + güncellenmiş K-12.

════════════════════════════════════════════════════════════════════════
BÖLÜM B — F5: API katmanı
════════════════════════════════════════════════════════════════════════

Mimari docs/01-mimari.md §10'da. Aşağıdakiler ONA EK ve zorunlu.

■ B1 — ÇIPLAK SAYI DÖNDÜRMEK YASAK
  Ürünün tek iddiası metodolojik dürüstlük. API bunu ŞEMA DÜZEYİNDE
  garanti etmeli: arayüzün bağlamsız bir sayı gösterebilmesi mümkün
  OLMAMALI. Oran/beklenti alanları hep şu zarfla döner:

    { "value": 0.41, "ci95": [0.324, 0.503], "ci_method": "month_block",
      "null": 0.333, "shadow": 0.34,
      "n_events": 112, "n_months": 37,
      "significant": false,
      "verdict": "anlamlı fark ölçülemedi",
      "design_effect": 1.28 }

  `significant` ve `verdict` SUNUCUDA hesaplanır, istemciye bırakılmaz.
  Bare float döndüren hiçbir istatistik alanı olmayacak — testle zorla.

■ B2 — KULLANICI DA P-HACKING YAPABİLİR
  İçeride 52 testlik Bonferroni uyguladık. Ama serbest çizim yapan bir
  kullanıcı 50 şekil deneyip "anlamlı" birini bulursa, aynı problemi
  kendisi üretmiş olur — ve bizim düzeltmemiz onu kapsamaz.

  ZORUNLU: oturum başına sorgu sayacı. Yanıtta
    { "session_queries": 17,
      "multiple_comparison_warning": true,
      "adjusted_alpha": 0.0029 }
  ve outcome kartında görünür uyarı: "Bu oturumda 17 farklı şekil denediniz;
  şans eseri 'anlamlı' sonuç görme olasılığınız arttı."
  Bu, piyasada hiçbir aracın yapmadığı şey ve ürünün karakteri.

■ B3 — Uç noktalar
  POST /api/search                → §10 şeması + data_as_of + bayatlık bayrağı
  GET  /api/search/{id}?offset=   → cache'ten dilim, YENİDEN HESAPLAMA YOK
  GET  /api/search/{id}/stats     → outcome kartı (B1 zarfıyla)
  GET  /api/templates             → şablon kütüphanesi
  GET  /api/chart/{symbol}        → OHLCV + vurgu sınırları + blueprint
                                    overlay noktaları + bükülme miktarı
  GET  /api/findings              → YENİ. F4/F4.5/F4.6 çalışma sonuçları:
                                    aşamalı sıkılaşma tablosu (13/26 → 8/26
                                    → 14/52 → 2/52), tam 14×2×2 tablo,
                                    yöntem notları. Bu bir iç rapor değil,
                                    BİRİNCİ SINIF ÜRÜN SAYFASIDIR.

■ B4 — Outcome maliyeti ve önbellekleme
  10.000 tekrarlı blok bootstrap etkileşimli değil (~2 sn+).
   • 14 şablon için outcome ÖNCEDEN hesaplanır, Redis'te tutulur.
   • Serbest çizim için outcome ASENKRON iş: POST → job_id → poll.
     Bootstrap tekrar sayısını DÜŞÜRME; aynı 10.000 kalsın, kullanıcı
     beklesin. Farklı tekrar sayısı farklı GA üretir ve iki farklı
     kalitede sayıyı aynı arayüzde göstermek dürüstlük sorunudur.
   • Radar sonuçları Cron ile 5 dk'da bir önceden hesaplanır.

■ B5 — Cache ve sayfalama (K-08)
  search:{id} → sıralı tam liste, TTL 1 saat. İkinci sayfa < 5 ms.
  En iyi 12'yi bulmak için zaten hepsi skorlanıyor; tembel tarama YOK.

■ B6 — Sağlık ve gözlemlenebilirlik
  GET /health → veri tazeliği (evren geneli + aktif semboller ayrı),
  matris sürümü, son cron zamanı. Bayat veri API'yi KIRMAZ, uyarır (F3.5).
  Arama ve outcome için ayrı rate limit — biri 51 ms, diğeri 2 sn.

■ B7 — Testler
  • Şema testi: hiçbir istatistik alanı bare float dönmüyor
  • significant/verdict sunucuda hesaplanıyor, GA sıfırı içeriyorsa
    significant=false
  • Sayfalama cache'ten geliyor (ikinci istekte motor çağrılmıyor — mock'la)
  • Bayat veride API 200 dönüyor + uyarı bayrağı
  • Oturum sayacı artıyor, adjusted_alpha doğru

════════════════════════════════════════════════════════════════════════
KURALLAR
• F6'ya (UI) geçme.
• BÖLÜM A bitmeden B'ye başlama; A manşeti değiştirebilir.
• A'da sayı kurtarmaya çalışma. Vekil çıkarsa vekil yaz.
• Sihirli sayı yok. • Her bölüm sonunda commit. • Belirsizlikte sor.
```
