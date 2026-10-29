"""F5 API sözleşmesi.

İki kural bu dosyanın tamamını yönetir:

* **Çıplak sayı yasak.** Her istatistik ``StatEnvelope`` ile döner: değer,
  güven aralığı, yöntem, null/gölge karşılaştırması, N ve hüküm birlikte.
  Tek başına "%64 başarı" cümlesi kurulamasın diye.
* **Uyarılar veriyle taşınır.** Ayırt edicilik, tazelik ve çoklu karşılaştırma
  uyarıları yanıtın içindedir; arayüzün onları uydurması veya unutması
  mümkün değildir.
"""

from __future__ import annotations

from typing import Annotated, Final, Literal

from pydantic import BaseModel, Field

from engine.config import SOURCE_DEFAULT_BARS, SOURCE_MAX_BARS, SOURCE_MIN_BARS

Timeframe = Literal["4h", "1d"]
Tolerance = Literal["strict", "medium", "flexible"]
Mode = Literal["historical", "live"]


#: Tek istekte kabul edilen en fazla ham çizim noktası. Bir kalem darbesi
#: pratikte birkaç yüz nokta üretir; üst sınır kazara/kötü niyetli dev
#: yüklerin interpolasyonu şişirmesini engeller.
MAX_DRAWING_POINTS: Final[int] = 4_096

#: Kısıt union'ın kendisine değil **üyelerine** takılır: Pydantic v2, bir
#: union şemasına doğrudan uygulanan uzunluk kısıtını reddeder.
DrawingSeries = Annotated[list[float], Field(max_length=MAX_DRAWING_POINTS)]
DrawingPairs = Annotated[list[list[float]], Field(max_length=MAX_DRAWING_POINTS)]


class ChartSource(BaseModel):
    """Gerçek bir grafiğin parçası sorgu olarak (engine/search/source.py)."""

    symbol: str = Field(min_length=1, max_length=40)
    #: Parçanın son barının zamanı (ms, bar açılışı). Yoksa son kapanmış bar.
    end_time: int | None = Field(default=None, ge=0)
    length: int = Field(default=SOURCE_DEFAULT_BARS, ge=SOURCE_MIN_BARS, le=SOURCE_MAX_BARS)


class SourceInfo(BaseModel):
    """Sorgunun hangi parçadan kurulduğu ve motorun ondan ne okuduğu."""

    symbol: str
    start_time: int
    end_time: int
    length: int
    #: Parçanın normalize hâli (32 nokta, z-score) — arayüz motorun gördüğü
    #: şekli kendi normalizasyonunu kurmadan çizebilsin diye.
    query_vector: list[float]
    #: Sorguyla örtüştüğü için dışlanan Aşama 1 adayı. Tarihsel modda aynı
    #: dönem tüm sembollerde, radarda yalnız sorgu sembolünde dışlanır.
    excluded_overlap: int


class SearchRequest(BaseModel):
    #: Serbest çizim. İki biçim kabul edilir:
    #:
    #: * ``[y0, y1, ...]``      — eşit aralıklı varsayılır (geriye dönük)
    #: * ``[[x0, y0], ...]``    — **tercih edilen**: kullanıcının çizim hızı
    #:   düzensizdir, x ızgarasını istemcinin uydurması bilgi kaybıdır
    #:
    #: Her iki durumda da 32 noktaya indirgeme ve z-score sunucudadır: tek
    #: normalizasyon otoritesi motordur (K-02/K-04).
    points: DrawingSeries | DrawingPairs | None = None
    template_id: str | None = None
    source: ChartSource | None = None
    mode: Mode = "historical"
    timeframe: Timeframe = "4h"
    window_lengths: list[int] = Field(default_factory=lambda: [24, 40, 64, 100])
    tolerance: Tolerance = "medium"
    min_amplitude: float | None = None
    limit: int = Field(default=12, ge=1, le=48)


class MatchResponse(BaseModel):
    symbol: str
    symbol_id: int
    timeframe: str
    window_length: int
    start_idx: int
    end_idx: int
    start_time: int
    end_time: int
    #: Pearson korelasyonu (kosinüs) — "%85 benzerlik" değil, tanımlı bir sayı.
    score: float
    #: Normalize DDTW/DTW mesafesi (metrik ölçeğinde).
    distance: float
    #: Sorgu-göreli null dağılımındaki yüzdelik dilim. SIRALAMA BUNA GÖREDİR.
    percentile: float
    amplitude: float
    atr: float
    warp_path: list[list[int]] | None = None


class SessionInfo(BaseModel):
    session_queries: int
    multiple_comparison_warning: bool
    adjusted_alpha: float
    warning_text: str | None = None


class SearchResponse(BaseModel):
    search_id: str
    total: int
    elapsed_ms: float
    mode: str
    timeframe: str
    tolerance: str
    #: Deponun gördüğü en yeni barın açılış zamanı (ms).
    data_as_of: int
    stale_warning: bool
    #: Null dağılımı dar → korpusta aranan yapı yok (S-1). Sonuçlar gösterilir
    #: ama "bu şekle benzeyen bir hareket yok" uyarısıyla birlikte.
    discriminative: bool = True
    warning: str | None = None
    #: Motorun çizimden okuduğu yapı ("3 belirgin tepe · ortadaki en yüksek").
    #: Yanlış okunduysa kullanıcı ancak görürse anlayabilir.
    structure_read: str | None = None
    #: Sonuçlar bu yapıya göre filtrelendi mi.
    structure_filtered: bool = False
    #: Motorun okuduğu trend çizgisi düzeni ("yatay direnç · yükselen dipler
    #: · daralan") ve sonuçların buna göre daraltılıp daraltılmadığı.
    envelope_read: str | None = None
    envelope_filtered: bool = False
    #: Okuma sağlam mı — aynı şekil biraz farklı çizilse aynı okunur muydu?
    #: Eğimle tanımlı formasyonlarda (üçgen, takoz, flama) okuma kararsızdır;
    #: kesinmiş gibi göstermek fazla iddia olur.
    structure_stable: bool = True
    #: Sorgu gerçek bir grafikten kurulduysa: hangi parça ve ne dışlandı.
    source: SourceInfo | None = None
    results: list[MatchResponse]
    session: SessionInfo


class StatEnvelope(BaseModel):
    """Her sayısal istatistik bu zarfla dönülür, yalın float yasaktır."""

    value: float
    ci95: list[float]
    ci_method: str
    #: Teorik null (2:1 bariyerde %33 gibi) — varsa.
    null: float | None
    #: Zaman-eşleştirmeli gölge dağılımın aynı metriği (K-12).
    shadow: float | None
    n_events: int
    n_months: int
    significant: bool
    verdict: str
    #: Ay-bloklu bootstrap tasarım etkisi; 1'den büyükse iid varsayımı
    #: belirsizliği eksik ölçerdi.
    design_effect: float | None
    #: Birim: "R" (beklenti/edge) veya "ratio" (0–1 oran).
    unit: Literal["R", "ratio"] = "R"


class RegimeRow(BaseModel):
    period: str
    n: int
    win_rate: float | None
    expectancy_r: float | None
    #: MIN_REGIME_N altındaki hücre — gösterilir ama "yetersiz örnek" etiketiyle.
    insufficient: bool = False


class ReturnDistribution(BaseModel):
    """Medyan R ve artıda kapanma oranı — ortalamanın gizlediği şey.

    Üçlü bariyerde beklenti (ortalama) dağılımın şeklini tamamen gizler:
    OBO 2:1'de beklenti +0,015R iken medyan **−1,000R**'dir, yani olayların
    yarısından fazlası tam stop yer.

    **StatEnvelope'a sarılmaz, çünkü güven aralığı DEĞİLDİR** — betimleme,
    iddia değil. Yüzdelik bant (p10–p90) da bilerek yok: ölçüldü, 12/12
    hücrede tam bariyerlere oturuyor, yani veriden değil konfigürasyondan
    geliyor. Gölgenin aynı iki sayısı yanında durur.
    """

    median: float
    #: R > 0 ile kapanan olay oranı. Kazanma oranından farklıdır: o yalnız
    #: TP'ye çarpanları sayar, bu zaman bariyerinden artıda çıkanları da sayar.
    share_positive: float
    shadow_median: float | None = None
    shadow_share_positive: float | None = None


class OutcomeConfigResponse(BaseModel):
    config: str
    #: Bariyer oranları (TP, SL) — ATR katı cinsinden (K-16).
    k_tp: float
    k_sl: float
    expectancy: StatEnvelope
    win_rate: StatEnvelope
    edge: StatEnvelope | None
    #: F4.6 ön-getiri (momentum) eşleştirmeli gölge dağılıma karşı edge.
    return_matched_edge: StatEnvelope | None = None
    distribution: ReturnDistribution
    #: MIN_EVENTS_FOR_CLAIM altındaki örneklem. Sayılar yine döner (gizlemek
    #: de bir tür yalan olurdu) ama arayüz onları iddia gibi sunmamalıdır.
    insufficient: bool = False
    outcomes: dict[str, int]
    truncated: int
    by_regime: list[RegimeRow]


class FanBands(BaseModel):
    """Izgara noktası başına yüzdelikler (ATR cinsinden).

    ``u`` zaman bariyerine göre konumdur (0 = t0, 1 = t0 + T, K-16.4);
    ``n`` o noktada ölçülebilen yol sayısıdır (veri sonu ve fiyat sıçraması
    yolu keser). Ölçülemeyen noktalar ``None``'dır — uydurulmaz.
    """

    u: list[float]
    n: list[int]
    p10: list[float | None]
    p25: list[float | None]
    p50: list[float | None]
    p75: list[float | None]
    p90: list[float | None]


class FanReport(BaseModel):
    matches: FanBands
    shadow: FanBands


class LedgerOutcome(BaseModel):
    #: tp · sl · time · forced — istatistik panelindeki ``outcomes`` anahtarları.
    outcome: str
    #: Brüt R — beklentiyle aynı büyüklük. Tek bir olayın GÖZLEMİdir, tahmin
    #: değil; StatEnvelope kuralı tahminler içindir ve güven aralığı
    #: istatistik panelindedir.
    r: float
    #: Çıkışın t0'dan kaç bar sonra olduğu.
    exit_bar: int


class LedgerRow(BaseModel):
    """Bir eşleşmenin istatistikteki yeri — eşleşme kartında gösterilir."""

    symbol_id: int
    end_idx: int
    window_length: int
    #: counted · overlap (önceki bir olayın ileri penceresiyle örtüşüyor,
    #: K-09) · cost_floor (K-16.7) · listing (ATR ısınmadı) · no_data ·
    #: no_forward (ileri pencere yok)
    status: Literal[
        "counted", "overlap", "cost_floor", "listing", "no_data", "no_forward", "condition"
    ]
    #: Konfigürasyon başına sonuç; yalnız ``counted`` satırlarda dolu.
    outcomes: dict[str, LedgerOutcome] = Field(default_factory=dict)


class OutcomeResponse(BaseModel):
    configs: dict[str, OutcomeConfigResponse]
    #: Post-NMS'ten geçen eşleşme sayısı (bağımlı olabilir).
    matches: int
    #: İstatistiğe giren bağımsız olay sayısı (K-09).
    n_events: int
    dropped_forward_overlap: int
    dropped_filters: int
    direction: str
    shadow: dict = Field(default_factory=dict)
    #: İleri yol fanı — eşleşmeler ve gölge, daima birlikte (K-12).
    #: Olay yoksa None.
    paths: FanReport | None = None
    #: Eşleşme başına defter, arama sonuç sırasıyla.
    ledger: list[LedgerRow] = Field(default_factory=list)
    disclaimer: str


class Candle(BaseModel):
    #: Saniye cinsinden (lightweight-charts sözleşmesi).
    time: int
    open: float
    high: float
    low: float
    close: float


class OverlayPoint(BaseModel):
    time: int
    value: float


class ChartResponse(BaseModel):
    symbol: str
    timeframe: str
    ohlcv: list[Candle]
    #: ``ohlcv`` dizisine göre **göreli** indeksler — mutlak bar indeksi değil.
    highlight_start: int
    highlight_end: int
    #: Kanonik şablonun eşleşme penceresinin fiyat ölçeğine taşınmış hâli.
    blueprint_overlay: list[OverlayPoint]
    #: DTW yoluyla bükülmüş şablon: "motor bunu buna hizaladı".
    warped_overlay: list[OverlayPoint]
    #: Bükülme miktarı; kanonik ile bükülmüş katman ayrışıyorsa eşleşme
    #: ağır esnetmeyle kurulmuştur.
    warp_amount: float | None


class TemplateResponse(BaseModel):
    id: str
    name: str
    name_en: str
    category: str
    bias: str | None
    description: str
    #: 32 noktalık z-score'lu vektör (motora giden).
    vector: list[float]


class FindingStage(BaseModel):
    stage: str
    significant: int
    total: int
    desc: str


class FindingProvenance(BaseModel):
    """Bir ölçüm tablosunun kökeni: hangi motor, hangi veri, ne zaman."""

    file: str
    timeframe: str | None = None
    generated_at: str | None = None
    #: Ölçümün gördüğü en yeni bar (ms). Korpus büyüdükçe geride kalır —
    #: bu "başka motor" değil "daha eski veri" demektir.
    data_as_of: int | None = None
    #: True = bugünkü motorla ölçüldü · False = farklı motor ·
    #: None = dosya parmak izi taşımıyor (bilinmiyor, "uyuşuyor" denemez).
    engine_match: bool | None = None
    reason: str | None = None


class StabilityCell(BaseModel):
    """Bir hücrenin tek zaman dilimindeki sonucu ve tohumlar arası kararlılığı."""

    timeframe: str
    #: Yayımlanan tablodaki (varsayılan tohum) edge ve %95 ay-bloklu GA.
    edge: float | None = None
    ci95: list[float] | None = None
    n_events: int = 0
    significant: bool = False
    #: Kaç null tohumunda %95'te / Bonferroni'de anlamlı (``seeds`` üzerinden).
    seeds_significant: int = 0
    seeds_bonferroni: int = 0


class StabilityRow(BaseModel):
    template_id: str
    template: str
    direction: str
    config: str
    cells: list[StabilityCell]
    #: Kaç tohumda 1d ve 4h'de aynı yönde anlamlı (F4.7 replikasyonu).
    seeds_replicated: int = 0


class SeedStability(BaseModel):
    """F4.5'in 56 testi, null tohumu değiştirilerek (docs/12).

    Arama eşiği rastgele bir null örnekleminin derin yüzdeliğidir; tek bir
    çekilişle "anlamlı" görünen hücre başka bir çekilişte düşebilir. Tek
    tohumla gösterilen bir tablo bunu gizler.
    """

    seeds: int
    null_sample: int
    engine_match: bool | None = None
    reason: str | None = None
    rows: list[StabilityRow]


class FindingsResponse(BaseModel):
    stages: list[FindingStage]
    full_table: list[dict]
    methodology: str
    provenance: list[FindingProvenance] = []
    #: Tablolardan en az biri bugünkü motorla ölçülmemişse True. Arayüz bunu
    #: gizleyemez: bayat bir istatistiği güncelmiş gibi göstermek, dürüstlük
    #: sayfasının anlatmaya çalıştığı şeyin tam tersidir.
    stale: bool = False
    #: Tohum kararlılığı; ölçüm dosyası yoksa ya da güncel null büyüklüğünde
    #: koşu içermiyorsa None (arayüz nedenini yazar, tabloyu uydurmaz).
    stability: SeedStability | None = None


class HealthResponse(BaseModel):
    status: str
    #: Zaman dilimi başına en yeni bar (ms) ve bayatlık raporu.
    timeframes: dict[str, dict]
    stale_warning: bool
    data_as_of: int
    matrix_ready: bool
