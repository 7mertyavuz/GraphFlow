/**
 * Arayüz metinleri — Türkçe ve İngilizce.
 *
 * `en`, `typeof tr` ile tiplenir: İngilizce'de eksik bir anahtar ya da
 * farklı imzalı bir işlev derleme hatasıdır. Sunucunun ürettiği metinler
 * (motorun okuması, uyarılar, hükümler, bulgular) burada değil, sunucudaki
 * `engine/i18n.py` kataloğundadır ve `Accept-Language` başlığıyla gelir.
 */

export const tr = {
  meta: {
    title: "GraphFlow — görsel formasyon arama motoru",
  },
  nav: {
    radar: "Radar",
    backtest: "Backtest",
    findings: "Bulgular",
  },
  lang: {
    aria: "Arayüz dili",
  },
  status: {
    apiDown: "API kapalı",
    connecting: "bağlanıyor",
    data: (rel: string) => `veri ${rel}`,
    staleTitle:
      "Depodaki en yeni bar tazelik sınırının gerisinde — sonuçlar güncel piyasayı yansıtmayabilir.",
    freshTitle: "Depodaki en yeni bar",
  },
  footer: {
    body:
      "GraphFlow sinyal satmaz; ölçülmüş ve dürüstçe raporlanmış geçmiş dağılım sunar. Hiçbir başarı oranı baseline olmadan gösterilmez. Burada yer alan hiçbir sayı yatırım tavsiyesi değildir.",
    link: "Yöntem ve bulgular →",
  },
  home: {
    badge: "Görsel formasyon arama motoru",
    headlineStart: "Bir şekil çizin,",
    headlineHighlight: "piyasa onu nerede yaşadıysa",
    headlineEnd: "gösterelim.",
    leadStart:
      "GraphFlow, 2017'den bugüne tüm Binance geçmişinde çizdiğiniz formasyonun benzerlerini bulur ve o formasyondan sonra",
    leadHighlight: "gerçekte ne olduğunu",
    leadEnd: "güven aralıklarıyla raporlar.",
    radarCta: "Canlı radar",
    backtestCta: "Tarihsel analiz",
    shapes: ["Omuz-Baş-Omuz", "Çift dip", "Fincan-kulp", "Yükselen takoz"],
    steps: [
      {
        title: "Şekli tarif edin",
        body: "Formasyonu çizin ya da 14 kanonik şablondan birini seçin. İkisi de aynı 32 noktalık vektöre iner — kural motoru yoktur.",
      },
      {
        title: "Motor ölçer",
        body: "Kosinüs ön elemesi, ardından DDTW + ham DTW karması. Eşik, sorgunun kendi null dağılımından türetilir; motor 'eşleşme yok' diyebilir.",
      },
      {
        title: "Sonrası raporlanır",
        body: "ATR tabanlı üçlü bariyer, ay-bloklu bootstrap ve zaman-eşleştirmeli gölge dağılım. Baseline'sız hiçbir oran gösterilmez.",
      },
    ],
    notSignalTitle: "Bu bir sinyal ürünü değildir",
    notSignalBody:
      "Bulguların neredeyse tamamı eleme aşamalarında düştü; iki zaman diliminde de momentumdan bağımsız sağ çıkan bir şekil etkisi yok. Hangi bulgunun hangi aşamada düştüğünü olduğu gibi yayınlıyoruz — asıl bilimsel değer orada.",
    findingsCta: "Bulgular",
  },
  workspace: {
    radar: {
      title: "Canlı radar",
      description:
        "Her sembolün en son penceresi taranır. Oluşmakta olan (kapanmamış) mum veriden düşülür.",
      submit: "Piyasayı tara",
    },
    backtest: {
      title: "Tarihsel analiz",
      description:
        "2017'den bugüne tüm kayan pencereler taranır; yalnızca bağımsız olaylar istatistiğe girer.",
      submit: "Geçmişte tara",
    },
    searchFailed: "Arama başarısız oldu.",
    staleTitle: "Veri bayat",
    staleBody:
      "Depodaki en yeni bar tazelik sınırının gerisinde. Sonuçlar güncel piyasayı yansıtmayabilir; yeni veri indirmek için",
    noStructureTitle: "Yapısal benzerlik bulunamadı",
  },
  query: {
    title: "Sorgu şekli",
    sourceAria: "Sorgu kaynağı",
    draw: "Çiz",
    library: "Kütüphane",
    flatTitle: "Düz çizim",
    flatBody: "Şekil taşımayan bir sorgu aranamaz (σ ≈ 0). Yükseliş, düşüş veya bir dönüş çizin.",
    filters: "Filtreler",
    timeframe: "Zaman dilimi",
    tf4h: "4 saat",
    tf1d: "1 gün",
    tf4hHint: "Kısa vadeli formasyonlar",
    tf1dHint: "Uzun vadeli formasyonlar",
    tolerance: "Tolerans",
    toleranceHint: "Eşik, sorgunun kendi null dağılımından türetilir — yüzdelik dilim.",
    strict: "Katı",
    medium: "Orta",
    flexible: "Esnek",
    strictHint: "Yalnızca çok yakın eşleşmeler",
    mediumHint: "Dengeli",
    flexibleHint: "Daha fazla, daha gevşek eşleşme",
    minAmplitude: "Min. genlik",
    minAmplitudeHint: "Pencere içindeki toplam hareket. Düşük genlikli gürültüyü eler.",
    scanning: "Taranıyor…",
    drawToSearch: "Aramak için bir şekil çizin.",
    pickToSearch: "Aramak için kütüphaneden bir formasyon seçin.",
    chart: "Grafik",
    pickChartToSearch: "Aramak için bir sembol seçin.",
  },
  chartSource: {
    symbol: "Sembol",
    symbolHint: (n: string) => `${n} sembol — evren zaman dilimi başınadır.`,
    unknownSymbol: "Bu zaman diliminde böyle bir sembol yok.",
    length: "Parça uzunluğu",
    lengthValue: (n: number) => `${n} bar`,
    lengthHint:
      "Şekil ölçekten bağımsız aranır: 64 barlık bir parça 24 ya da 100 barlık pencerelerle de eşleşebilir.",
    end: "Bitiş tarihi",
    endHint: "Boş bırakılırsa son kapanmış bar. Geçmiş bir tarih, grafiğin o gün neye benzediğini sorar.",
    endLive: "Radar'da parça daima son kapanmış barda biter.",
    clearEnd: "Son bar",
    read: "Motorun okuduğu parça",
    range: (symbol: string, from: string, to: string, n: number) =>
      `${symbol} · ${from} – ${to} · ${n} bar`,
    excludedHistorical: (n: string) =>
      `${n} aday dışlandı: bu dönemle örtüşen pencereler, hangi sembolde olursa olsun. Aynı piyasa hareketi tarihsel bir benzer değildir.`,
    excludedLive: (n: string) => `${n} aday dışlandı: sorgunun kendi penceresi ve kaymış kopyaları.`,
  },
  drawpad: {
    placeholderTitle: "Formasyonu buraya çizin",
    placeholderStart: "Soldan sağa tek hamlede çizin. Fiyat seviyesi değil,",
    placeholderHighlight: "şeklin kendisi",
    placeholderEnd: "aranır.",
    waiting: "Çizim bekleniyor",
    points: (n: number) => `${n} nokta`,
    clear: "Temizle",
  },
  templates: {
    reversal: "Dönüş formasyonları",
    continuation: "Devam formasyonları",
    loadFailed: "Şablonlar alınamadı",
    apiRunning: "API çalışıyor mu?",
    empty: "Şablon kütüphanesi boş.",
    loading: "Şablonlar yükleniyor…",
  },
  results: {
    engineRead: "Motor şeklinizi şöyle okudu:",
    limitedByStructure: " — sonuçlar bu yapıyla sınırlı",
    trendLines: "Trend çizgileri:",
    limitedByTrend: " — sonuçlar bu düzenle sınırlı",
    unstableStart:
      "Tepe/dip okuması kararsız: aynı şeklin biraz farklı bir hâli farklı okunabilir. Üçgen, takoz ve flama gibi formasyonları tanımlayan şey tepe sayısı değil trend çizgilerinin eğimidir.",
    unstableByTrend:
      "Bu yüzden eleme tepe/dip düzenine göre değil, yukarıdaki trend çizgilerine göre yapıldı",
    unstableNoNarrow: "Bu yüzden sonuçlar bu okumaya göre daraltılmadı",
    unstableEnd:
      "— kararsız bir okumayla eleme yapmak gerçek formasyonları da siliyordu (ölçüldü: yakalama oranı %45 → %57).",
    matches: (n: string) => `${n} eşleşme`,
    scanned: (rel: string) => `${rel} tarandı`,
    showing: (n: string) => `${n} gösteriliyor`,
    dataAsOfTitle: "Deponun gördüğü en yeni bar",
  },
  grid: {
    notYetTitle: "Henüz arama yapılmadı",
    notYetBody: "Soldan bir formasyon çizin veya kütüphaneden seçin, ardından taramayı başlatın.",
    noneTitle: "Eşleşme bulunamadı",
    noneBody:
      "Motor 'eşleşme yok' diyebilir — bu bir hata değil, kalibre edilmiş bir cevaptır. Toleransı esnetin, min. genliği düşürün veya daha belirgin bir formasyon deneyin.",
    more: "Daha fazla göster",
  },
  card: {
    percentileTitle: "Sorgunun null dağılımındaki yüzdelik dilim",
    bars: (n: number) => `${n} bar`,
    chartFailed: "Grafik yüklenemedi",
    amplitudeTitle: "Pencere içi toplam hareket",
    correlationTitle: "Pearson korelasyonu (Aşama 1 skoru)",
    warpTitle: "Yüksek bükülme: eşleşme ağır zaman esnetmesiyle kuruldu",
  },
  outcome: {
    computing: "İleri pencereler hesaplanıyor, gölge dağılım örnekleniyor…",
    errorTitle: "İstatistik hesaplanamadı",
    errorBody: "Bu arama için ileri pencere istatistiği üretilemedi.",
    noEventsTitle: "İstatistik üretilemedi",
    noEventsBody:
      "Bu aramada bağımsız olay kalmadı: eşleşmeler ya ileri pencere ayrımına ya da işlem maliyeti tabanına takıldı. Baseline'sız bir sayı gösterilmez.",
    title: "Sonra ne oldu?",
    subtitle: (tp: number, sl: number) =>
      `Üçlü bariyer · hedef ${tp}×ATR · stop ${sl}×ATR · zaman bariyeri pencere uzunluğunun yarısı`,
    directionAria: "Yön",
    configAria: "Bariyer konfigürasyonu",
    long: "Long",
    short: "Short",
    longHint: "Yukarı bariyer hedef",
    shortHint: "Aşağı bariyer hedef",
    zeroTitle: "İstatistiğe giren olay yok",
    zeroBody:
      "Eşleşmeler ileri pencere ayrımı ve işlem maliyeti tabanı filtrelerinden geçemedi. Bağımsız olay olmadan dağılım raporlanmaz.",
    insufficientTitle: (n: number) => `Yetersiz örnek — ${n} bağımsız olay`,
    insufficientStart: "Aşağıdaki sayılar hesaplandı ama",
    insufficientStrong: "iddia olarak okunmamalıdır",
    insufficientEnd:
      ". Bu örneklem büyüklüğünde güven aralığı neredeyse her değeri kapsar; bir formasyonun işe yarayıp yaramadığı buradan anlaşılamaz.",
    expectancy: "Beklenti",
    expectancyHint: "Olay başına ortalama R — başrol metrik",
    winRate: "Başarı oranı",
    winRateHint: "Teorik null ile birlikte okunur",
    edge: "Edge",
    edgeHint: "Zaman-eşleştirmeli gölge dağılıma karşı fark",
    edgeNaTitle: "Edge ölçülemedi",
    edgeNaBody: "Gölge dağılım örneklenemedi; baseline'sız bir başarı oranı gösterilmez.",
    distribution: (n: string) => `Sonuç dağılımı (${n} olay)`,
    truncatedTitle: "İleri penceresi fiyat sıçraması veya veri sonu nedeniyle kesilen olaylar",
    truncated: "kesilen:",
    regime: "Rejim kırılımı",
    outcomes: { tp: "Hedef", sl: "Stop", time: "Zaman aşımı", forced: "Veri sonu" },
    ledger: {
      matches: "eşleşme",
      overlap: "örtüşme elendi",
      filtered: "filtre elendi",
      independent: "bağımsız olay",
    },
    onlyIndependent: "yalnızca bağımsız olaylar sayılır",
    onlyIndependentTitle: "Örtüşen pencereler N'i şişirir, güven aralığını sahte biçimde daraltır",
  },
  stat: {
    shadow: "Gölge dağılım",
    theoreticalNull: "Teorik null",
    significant: "anlamlı",
    notSignificant: "anlamsız",
    ci95: "%95 GA",
    method: "Yöntem",
    independentN: "Bağımsız N",
    months: (n: number) => `${n} ay`,
    designEffect: "Tasarım etkisi",
    designEffectTitle:
      "Ay içi korelasyon düzeltmesi; 1'den büyükse iid bootstrap belirsizliği eksik ölçerdi",
    reference: (v: string) => `karşılaştırma tabanı: ${v}`,
    ciMethods: { bootstrap: "bootstrap", wilson: "Wilson", block_bootstrap: "ay-bloklu bootstrap" } as Record<string, string>,
  },
  regime: {
    none: "Rejim kırılımı için yeterli olay yok.",
    period: "Dönem",
    n: "N",
    winRate: "Başarı",
    expectancy: "Beklenti",
    insufficient: "yetersiz örnek",
    insufficientTitle: "MIN_REGIME_N altında: hücre yorumlanamaz",
  },
  band: {
    title: "Ortalamanın gizlediği",
    median: "Medyan sonuç",
    medianHint: "Olayların yarısı bunun altında kapandı",
    positive: "Artıda kapanan",
    positiveHint: "Kazanma oranından farklı: zaman bariyerinden yeşil çıkanlar da dahil",
    shadow: "Gölge dağılım",
  },
  fan: {
    title: "Fiyat ne yaptı",
    subtitle:
      "Eşleşmelerden sonraki fiyat yolları, zaman bariyerine kadar. ATR cinsinden ve bariyersiz: yol TP'ye ya da SL'ye değse de sürer.",
    matches: "Eşleşmeler",
    shadow: "Gölge (aynı aylar)",
    band80: "%10–%90",
    band50: "%25–%75",
    median: "Medyan",
    tp: "TP",
    sl: "SL",
    xStart: "t₀",
    xMid: "bariyerin yarısı",
    xEnd: "zaman bariyeri",
    at: (position: string) => `Bariyerin ${position} noktasında`,
    matchesAt: (median: string, lo: string, hi: string) =>
      `eşleşme medyanı ${median} (%25–%75: ${lo} … ${hi})`,
    shadowAt: (median: string) => `gölge medyanı ${median}`,
    counts: (start: number, end: number) =>
      end === start ? `${start} yol` : `${start} yol · bariyer sonunda ölçülebilen ${end}`,
    note:
      "Geçmiş örneklemin dağılımıdır, tahmin değildir. Gölge, aynı aylarda rastgele pencerelerin izlediği yoldur; iki fan ayrışmıyorsa formasyon, piyasanın o dönemde zaten yaptığından fazlasını söylemiyor.",
    aria: "İleri yol fanı: eşleşmeler ve gölge dağılım",
  },
  session: {
    tried: (n: number) => `Bu oturumda ${n} şekil denendi.`,
    triedTitle: (n: number) => `Bu oturumda ${n} şekil denendi`,
    alpha: (a: string) => `Bonferroni düzeltilmiş α = ${a}.`,
    warning: (n: number, a: string) =>
      `Bu oturumda ${n} farklı şekil denendi. Bonferroni düzeltilmiş anlamlılık eşiği α = ${a}; bu eşiği geçmeyen bulgular şans eseri ortaya çıkmış olabilir.`,
  },
  findings: {
    title: "Bulgular ve eleme zinciri",
    lead:
      "Her doğrulama aşaması bir öncekinin bulgularını sınadı. Elenen bulgular da raporlanır: bir sonucun hangi aşamada düştüğü, kalan sonucun ne kadar güvenilir olduğunu belirler.",
    loading: "Bulgular yükleniyor…",
    failed: "Bulgular alınamadı",
    apiRunning: "API çalışıyor mu?",
    staleTitle: "Bu tablolar bugünkü motorla ölçülmedi",
    staleBody:
      "Aşağıdaki sayıların en az bir kısmı, istatistiğe giren pencere kümesini belirleyen filtreler değişmeden önce üretildi. Motor değişince örneklem değişir; bayat bir tabloyu güncelmiş gibi göstermek bu sayfanın anlattığı şeyin tersidir. Yenilemek için",
    stages: "Aşamalar",
    significantOf: (s: number, total: number) => `${s} / ${total} anlamlı ·`,
    provenance: "Köken",
    data: (d: string) => `veri: ${d}`,
    measured: (d: string) => `· ölçüm: ${d}`,
    currentEngine: "bugünkü motor",
    differentEngine: "farklı motor",
    unknownOrigin: "köken bilinmiyor",
    methodology: "Yöntem",
    fullTable: (n: number) => `Tam tablo (${n} satır)`,
    yes: "evet",
    no: "hayır",
  },
  errors: {
    network: "API'ye ulaşılamıyor. Sunucu çalışıyor mu? (uvicorn engine.api.main:app)",
  },
};

export type Messages = typeof tr;

export const en: Messages = {
  meta: {
    title: "GraphFlow — visual chart pattern search",
  },
  nav: {
    radar: "Radar",
    backtest: "Backtest",
    findings: "Findings",
  },
  lang: {
    aria: "Interface language",
  },
  status: {
    apiDown: "API offline",
    connecting: "connecting",
    data: (rel: string) => `data ${rel}`,
    staleTitle:
      "The newest stored bar is behind the freshness limit — results may not reflect the current market.",
    freshTitle: "Newest stored bar",
  },
  footer: {
    body:
      "GraphFlow does not sell signals; it shows a measured, honestly reported historical distribution. No success rate is shown without a baseline. Nothing here is investment advice.",
    link: "Methodology and findings →",
  },
  home: {
    badge: "Visual chart pattern search",
    headlineStart: "Draw a shape,",
    headlineHighlight: "we'll show you where the market",
    headlineEnd: "already drew it.",
    leadStart:
      "GraphFlow searches the full Binance history since 2017 for patterns like the one you draw, and reports what",
    leadHighlight: "actually happened next",
    leadEnd: "— with confidence intervals.",
    radarCta: "Live radar",
    backtestCta: "Historical analysis",
    shapes: ["Head and shoulders", "Double bottom", "Cup and handle", "Rising wedge"],
    steps: [
      {
        title: "Describe the shape",
        body: "Draw the pattern or pick one of 14 canonical templates. Both reduce to the same 32-point vector — there is no rule engine.",
      },
      {
        title: "The engine measures",
        body: "A cosine pre-filter, then a blend of derivative and raw DTW. The threshold comes from the query's own null distribution, so the engine can say 'no match'.",
      },
      {
        title: "What came after is reported",
        body: "ATR-based triple barrier, month-block bootstrap and a time-matched shadow distribution. No rate is shown without a baseline.",
      },
    ],
    notSignalTitle: "This is not a signal product",
    notSignalBody:
      "Almost every finding was eliminated along the way; no pattern shape survives as independent of momentum on both timeframes. We publish which finding fell at which stage, as it is — that is where the scientific value is.",
    findingsCta: "Findings",
  },
  workspace: {
    radar: {
      title: "Live radar",
      description:
        "The latest window of every symbol is scanned. The forming (unclosed) candle is dropped.",
      submit: "Scan the market",
    },
    backtest: {
      title: "Historical analysis",
      description:
        "Every sliding window since 2017 is scanned; only independent events enter the statistics.",
      submit: "Scan history",
    },
    searchFailed: "The search failed.",
    staleTitle: "Stale data",
    staleBody:
      "The newest stored bar is behind the freshness limit. Results may not reflect the current market; to download new data run",
    noStructureTitle: "No structural similarity found",
  },
  query: {
    title: "Query shape",
    sourceAria: "Query source",
    draw: "Draw",
    library: "Library",
    flatTitle: "Flat drawing",
    flatBody: "A query without a shape cannot be searched (σ ≈ 0). Draw a rise, a fall or a reversal.",
    filters: "Filters",
    timeframe: "Timeframe",
    tf4h: "4 hours",
    tf1d: "1 day",
    tf4hHint: "Short-term patterns",
    tf1dHint: "Long-term patterns",
    tolerance: "Tolerance",
    toleranceHint: "The threshold comes from the query's own null distribution — a percentile.",
    strict: "Strict",
    medium: "Medium",
    flexible: "Flexible",
    strictHint: "Only very close matches",
    mediumHint: "Balanced",
    flexibleHint: "More, looser matches",
    minAmplitude: "Min. amplitude",
    minAmplitudeHint: "Total movement within the window. Filters out low-amplitude noise.",
    scanning: "Scanning…",
    drawToSearch: "Draw a shape to search.",
    pickToSearch: "Pick a pattern from the library to search.",
    chart: "Chart",
    pickChartToSearch: "Pick a symbol to search.",
  },
  chartSource: {
    symbol: "Symbol",
    symbolHint: (n: string) => `${n} symbols — the universe is per timeframe.`,
    unknownSymbol: "No such symbol in this timeframe.",
    length: "Segment length",
    lengthValue: (n: number) => `${n} bars`,
    lengthHint:
      "Shapes are searched scale-free: a 64-bar segment can also match 24- or 100-bar windows.",
    end: "End date",
    endHint: "Leave empty for the last closed bar. A past date asks what the chart looked like that day.",
    endLive: "In Radar the segment always ends at the last closed bar.",
    clearEnd: "Last bar",
    read: "Segment the engine read",
    range: (symbol: string, from: string, to: string, n: number) =>
      `${symbol} · ${from} – ${to} · ${n} bars`,
    excludedHistorical: (n: string) =>
      `${n} candidates excluded: windows overlapping this period, in any symbol. The same market move is not a historical analog.`,
    excludedLive: (n: string) => `${n} candidates excluded: the query's own window and its shifted copies.`,
  },
  drawpad: {
    placeholderTitle: "Draw the pattern here",
    placeholderStart: "Draw left to right in one stroke. Not the price level —",
    placeholderHighlight: "the shape itself",
    placeholderEnd: "is what's searched.",
    waiting: "Waiting for a drawing",
    points: (n: number) => `${n} points`,
    clear: "Clear",
  },
  templates: {
    reversal: "Reversal patterns",
    continuation: "Continuation patterns",
    loadFailed: "Could not load templates",
    apiRunning: "Is the API running?",
    empty: "The template library is empty.",
    loading: "Loading templates…",
  },
  results: {
    engineRead: "How the engine read your shape:",
    limitedByStructure: " — results are limited to this structure",
    trendLines: "Trend lines:",
    limitedByTrend: " — results are limited to this layout",
    unstableStart:
      "The peak/trough reading is unstable: a slightly different version of the same shape could read differently. Triangles, wedges and pennants are defined by the slope of their trend lines, not by a peak count.",
    unstableByTrend:
      "So results were narrowed by the trend lines above, not by the peak/trough pattern",
    unstableNoNarrow: "So results were not narrowed by this reading",
    unstableEnd:
      "— filtering on an unstable reading was also removing real patterns (measured: recall 45% → 57%).",
    matches: (n: string) => `${n} matches`,
    scanned: (rel: string) => `scanned ${rel}`,
    showing: (n: string) => `showing ${n}`,
    dataAsOfTitle: "Newest bar seen by the store",
  },
  grid: {
    notYetTitle: "No search yet",
    notYetBody: "Draw a pattern on the left or pick one from the library, then start the scan.",
    noneTitle: "No matches found",
    noneBody:
      "The engine can say 'no match' — that is not an error, it is a calibrated answer. Loosen the tolerance, lower the minimum amplitude or try a more distinct pattern.",
    more: "Show more",
  },
  card: {
    percentileTitle: "Percentile within the query's null distribution",
    bars: (n: number) => `${n} bars`,
    chartFailed: "Could not load the chart",
    amplitudeTitle: "Total movement within the window",
    correlationTitle: "Pearson correlation (Stage 1 score)",
    warpTitle: "High warping: the match needed heavy time stretching",
  },
  outcome: {
    computing: "Computing forward windows, sampling the shadow distribution…",
    errorTitle: "Statistics could not be computed",
    errorBody: "No forward-window statistics could be produced for this search.",
    noEventsTitle: "No statistics produced",
    noEventsBody:
      "No independent events remain in this search: the matches were removed by forward-window separation or by the transaction-cost floor. No number is shown without a baseline.",
    title: "What happened next?",
    subtitle: (tp: number, sl: number) =>
      `Triple barrier · target ${tp}×ATR · stop ${sl}×ATR · time barrier at half the window length`,
    directionAria: "Direction",
    configAria: "Barrier configuration",
    long: "Long",
    short: "Short",
    longHint: "Upper barrier is the target",
    shortHint: "Lower barrier is the target",
    zeroTitle: "No events entered the statistics",
    zeroBody:
      "The matches did not pass forward-window separation and the transaction-cost floor. No distribution is reported without independent events.",
    insufficientTitle: (n: number) => `Insufficient sample — ${n} independent events`,
    insufficientStart: "The numbers below were computed but",
    insufficientStrong: "must not be read as a claim",
    insufficientEnd:
      ". At this sample size the confidence interval covers almost any value; whether a pattern works cannot be judged from it.",
    expectancy: "Expectancy",
    expectancyHint: "Average R per event — the headline metric",
    winRate: "Win rate",
    winRateHint: "Read together with the theoretical null",
    edge: "Edge",
    edgeHint: "Difference against the time-matched shadow distribution",
    edgeNaTitle: "Edge could not be measured",
    edgeNaBody: "The shadow distribution could not be sampled; no success rate is shown without a baseline.",
    distribution: (n: string) => `Outcome distribution (${n} events)`,
    truncatedTitle: "Events whose forward window was cut by a price jump or the end of data",
    truncated: "truncated:",
    regime: "Regime breakdown",
    outcomes: { tp: "Target", sl: "Stop", time: "Time-out", forced: "End of data" },
    ledger: {
      matches: "matches",
      overlap: "overlap removed",
      filtered: "filtered out",
      independent: "independent events",
    },
    onlyIndependent: "only independent events are counted",
    onlyIndependentTitle: "Overlapping windows inflate N and fake a narrow confidence interval",
  },
  stat: {
    shadow: "Shadow distribution",
    theoreticalNull: "Theoretical null",
    significant: "significant",
    notSignificant: "not significant",
    ci95: "95% CI",
    method: "Method",
    independentN: "Independent N",
    months: (n: number) => `${n} months`,
    designEffect: "Design effect",
    designEffectTitle:
      "Within-month correlation correction; above 1 means an i.i.d. bootstrap would understate uncertainty",
    reference: (v: string) => `reference: ${v}`,
    ciMethods: { bootstrap: "bootstrap", wilson: "Wilson", block_bootstrap: "month-block bootstrap" } as Record<string, string>,
  },
  regime: {
    none: "Not enough events for a regime breakdown.",
    period: "Period",
    n: "N",
    winRate: "Win",
    expectancy: "Expectancy",
    insufficient: "insufficient sample",
    insufficientTitle: "Below MIN_REGIME_N: the cell cannot be interpreted",
  },
  band: {
    title: "What the average hides",
    median: "Median outcome",
    medianHint: "Half of the events closed below this",
    positive: "Closed in profit",
    positiveHint: "Not the win rate: includes events that exited green at the time barrier",
    shadow: "Shadow distribution",
  },
  fan: {
    title: "What price did",
    subtitle:
      "Price paths after the matches, up to the time barrier. In ATR units and barrier-free: a path keeps going after touching TP or SL.",
    matches: "Matches",
    shadow: "Shadow (same months)",
    band80: "10–90%",
    band50: "25–75%",
    median: "Median",
    tp: "TP",
    sl: "SL",
    xStart: "t₀",
    xMid: "half the barrier",
    xEnd: "time barrier",
    at: (position: string) => `At ${position} of the barrier`,
    matchesAt: (median: string, lo: string, hi: string) =>
      `match median ${median} (25–75%: ${lo} … ${hi})`,
    shadowAt: (median: string) => `shadow median ${median}`,
    counts: (start: number, end: number) =>
      end === start ? `${start} paths` : `${start} paths · ${end} measurable at the barrier`,
    note:
      "A distribution of the historical sample, not a forecast. The shadow is the path random windows took in the same months; if the two fans do not separate, the pattern says nothing beyond what the market was already doing then.",
    aria: "Forward path fan: matches and shadow distribution",
  },
  session: {
    tried: (n: number) => `${n} shapes tried in this session.`,
    triedTitle: (n: number) => `${n} shapes tried in this session`,
    alpha: (a: string) => `Bonferroni-corrected α = ${a}.`,
    warning: (n: number, a: string) =>
      `${n} different shapes were tried in this session. The Bonferroni-corrected significance threshold is α = ${a}; findings that do not clear it may have appeared by chance.`,
  },
  findings: {
    title: "Findings and the elimination chain",
    lead:
      "Each validation stage tested the findings of the previous one. Eliminated findings are reported too: the stage at which a result fell tells you how far to trust what remains.",
    loading: "Loading findings…",
    failed: "Could not load findings",
    apiRunning: "Is the API running?",
    staleTitle: "These tables were not measured with the current engine",
    staleBody:
      "At least some of the numbers below were produced before the filters that decide which windows enter the statistics changed. When the engine changes, the sample changes; showing a stale table as current would contradict what this page is about. To refresh, run",
    stages: "Stages",
    significantOf: (s: number, total: number) => `${s} / ${total} significant ·`,
    provenance: "Provenance",
    data: (d: string) => `data: ${d}`,
    measured: (d: string) => `· measured: ${d}`,
    currentEngine: "current engine",
    differentEngine: "different engine",
    unknownOrigin: "unknown origin",
    methodology: "Methodology",
    fullTable: (n: number) => `Full table (${n} rows)`,
    yes: "yes",
    no: "no",
  },
  errors: {
    network: "Cannot reach the API. Is the server running? (uvicorn engine.api.main:app)",
  },
};

export const messages = { tr, en } as const;
export type Lang = keyof typeof messages;
export const LANGS: Lang[] = ["tr", "en"];
