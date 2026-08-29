"""F5 — HTTP katmanı (docs/01-mimari.md §12).

Katmanın tek işi motoru dürüstçe sunmaktır:

* **Tek motor.** Radar ve Backtest aynı ``SearchEngine.search`` çağrısıdır,
  yalnızca ``mode`` değişir (K-15).
* **Aynı olaylar.** İstatistik, kullanıcının gördüğü eşleşmelerden hesaplanır;
  ``/stats`` içeride ikinci bir arama çalıştırmaz (K-09).
* **Uyarılar yanıtın içinde.** Ayırt edicilik, tazelik ve çoklu karşılaştırma
  arayüzün hatırlamasına bırakılmaz.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import numpy as np
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from engine.api import freshness, health
from engine.api.cache import OUTCOME_TTL, SEARCH_TTL, get_cache
from engine.api.chart import build_chart
from engine.api.schemas import (
    ChartResponse,
    FindingsResponse,
    FindingStage,
    MatchResponse,
    OutcomeConfigResponse,
    OutcomeResponse,
    RegimeRow,
    ReturnDistribution,
    SearchRequest,
    SearchResponse,
    StatEnvelope,
    TemplateResponse,
)
from engine.api.session import get_session_id, read_session, track_session
from engine.config import (
    DATA_DIR,
    N_POINTS,
    REFINE_MATCHES,
    REFINE_TOP_N,
    SEARCH_CACHE_MATCHES,
    SEARCH_RATE_LIMIT,
    TIMEFRAME_MS,
    WARP_PATH_TOP_N,
    WINDOW_LENGTHS,
)
from engine.normalize.pipeline import normalize_drawing
from engine.outcome.bars import BarStore
from engine.outcome.metrics import OutcomeStats
from engine.outcome.pipeline import TemplateOutcome, load_shadow_pools, run_events
from engine.outcome.shadow import ShadowPool
from engine.outcome.triple_barrier import EVENT_DTYPE
from engine.search.engine import SearchEngine
from engine.search.refine import refine_matches
from engine.templates.loader import load_all as load_all_templates

log = logging.getLogger(__name__)

app = FastAPI(
    title="GraphFlow API",
    version="1.0.0",
    description="Görsel formasyon arama motoru — ölçülmüş geçmiş dağılım, sinyal değil.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")

DISCLAIMER = (
    "Geçmiş dağılım gelecek getirinin garantisi değildir. Burada gösterilen "
    "her sayı ölçülmüş bir geçmiş istatistiktir; işlem tavsiyesi değildir."
)

# ---------------------------------------------------------------------------
# Tembel yüklenen ağır nesneler (matrisler memmap, bar deposu ~yüz MB)
# ---------------------------------------------------------------------------

_engine: SearchEngine | None = None
_stores: dict[str, BarStore] = {}
_pools_by_tf: dict[str, dict[int, ShadowPool]] = {}


def get_engine() -> SearchEngine:
    global _engine
    if _engine is None:
        _engine = SearchEngine()
    return _engine


def get_store(timeframe: str = "4h") -> BarStore:
    if timeframe not in _stores:
        # symbol_id uzayı zaman dilimi başınadır; haritayı karıştırmak bar
        # deposunda başka sembolün fiyatlarını okumak demektir.
        symbols = get_engine().symbols_for(timeframe)
        _stores[timeframe] = BarStore.from_klines(
            symbols=list(symbols.values()),
            timeframe=timeframe,
            ids={name: sid for sid, name in symbols.items()},
        )
    return _stores[timeframe]


def get_pools(timeframe: str = "4h") -> dict[int, ShadowPool]:
    if timeframe not in _pools_by_tf:
        _pools_by_tf[timeframe] = load_shadow_pools(timeframe)
    return _pools_by_tf[timeframe]


# ---------------------------------------------------------------------------
# Zarf yardımcıları
# ---------------------------------------------------------------------------


def wrap_stat(
    val: float | None,
    ci: tuple[float, float] | None,
    ci_method: str,
    null_val: float | None = None,
    shadow_val: float | None = None,
    n_events: int = 0,
    n_months: int = 0,
    significant: bool = False,
    verdict: str = "",
    design_effect: float | None = None,
    unit: str = "R",
) -> StatEnvelope:
    return StatEnvelope(
        value=val if val is not None else float("nan"),
        ci95=list(ci) if ci else [float("nan"), float("nan")],
        ci_method=ci_method,
        null=null_val,
        shadow=shadow_val,
        n_events=n_events,
        n_months=n_months,
        significant=significant,
        verdict=verdict,
        design_effect=design_effect,
        unit=unit,  # type: ignore[arg-type]
    )


def to_outcome_config(stats: OutcomeStats) -> OutcomeConfigResponse:
    expectancy = wrap_stat(
        val=stats.expectancy_r,
        ci=stats.expectancy_ci,
        ci_method="bootstrap",
        null_val=0.0,  # rastgele giriş, maliyet öncesi, 0R beklenir
        n_events=stats.n,
        n_months=stats.n_months,
        significant=bool(stats.expectancy_ci and stats.expectancy_ci[0] > 0),
        verdict="",
        unit="R",
    )

    win_rate = wrap_stat(
        val=stats.win_rate,
        ci=stats.win_rate_ci,
        ci_method="wilson",
        null_val=stats.theoretical_null,
        shadow_val=stats.shadow_win_rate,
        n_events=stats.n,
        n_months=stats.n_months,
        significant=bool(stats.win_rate_ci and stats.win_rate_ci[0] > stats.theoretical_null),
        verdict="",
        unit="ratio",
    )

    edge = None
    if stats.shadow_n > 0:
        edge = wrap_stat(
            val=stats.edge_r,
            ci=stats.edge_ci,
            # Ay-bloklu bootstrap zorunludur; iid aynı aydan çekilen gölgeleri
            # bağımsız sayar ve belirsizliği ~%29 eksik ölçer (K-12).
            ci_method="block_bootstrap" if stats.design_effect else "bootstrap",
            shadow_val=stats.shadow_expectancy_r,
            n_events=stats.n,
            n_months=stats.n_months,
            significant=stats.edge_is_significant,
            verdict=stats.verdict,
            design_effect=stats.design_effect,
            unit="R",
        )

    distribution = ReturnDistribution(
        median=stats.r_median,
        share_positive=stats.share_positive,
        shadow_median=stats.shadow_r_median,
        shadow_share_positive=stats.shadow_share_positive,
    )

    return OutcomeConfigResponse(
        config=stats.config,
        k_tp=stats.k_tp,
        k_sl=stats.k_sl,
        expectancy=expectancy,
        win_rate=win_rate,
        edge=edge,
        distribution=distribution,
        outcomes=stats.outcomes,
        truncated=stats.truncated,
        by_regime=[RegimeRow(**row) for row in stats.by_regime],
    )


def to_outcome_response(outcome: TemplateOutcome) -> OutcomeResponse:
    return OutcomeResponse(
        configs={name: to_outcome_config(s) for name, s in outcome.stats.items()},
        matches=outcome.matches,
        n_events=outcome.events,
        dropped_forward_overlap=outcome.dropped_separation,
        dropped_filters=outcome.dropped_filters,
        direction=outcome.direction,
        shadow=outcome.shadow_report,
        disclaimer=DISCLAIMER,
    )


def resolve_query(request: SearchRequest) -> np.ndarray:
    """İstek → (32,) z-score'lu sorgu vektörü.

    Normalizasyonun tek otoritesi motordur: istemci ham çizim noktalarını
    gönderir, sunucu ``normalize_drawing`` ile 32 noktaya indirger ve
    z-score'lar. Şablon seçmek ile aynı şekli çizmek bu yüzden birebir aynı
    yoldur (K-04); iki farklı normalizasyon iki farklı sonuç listesi üretemez.

    ``points`` hem ``[y, ...]`` hem ``[[x, y], ...]`` kabul eder. İkincisi
    tercih edilir: kullanıcı çizerken hızlanıp yavaşlar, noktalar x ekseninde
    düzgün dağılmaz. x'i istemcide düzgün ızgaraya oturtmak, sunucuya
    "bu noktalar eşit aralıklı" yalanını söylemektir.
    """
    if request.template_id:
        templates = load_all_templates()
        template = templates.get(request.template_id)
        if template is None:
            raise HTTPException(status_code=400, detail="Geçersiz template_id")
        return np.asarray(template.vector, dtype=np.float64)

    if request.points:
        try:
            points = np.asarray(request.points, dtype=np.float64)
        except ValueError:  # düzensiz (ragged) liste
            raise HTTPException(status_code=400, detail="Çizim noktaları düzensiz") from None
        if points.ndim == 2 and points.shape[1] != 2:
            raise HTTPException(status_code=400, detail="Nokta çiftleri [x, y] olmalı")
        if points.ndim not in (1, 2) or len(points) < 2 or not np.all(np.isfinite(points)):
            raise HTTPException(status_code=400, detail="Çizim en az 2 geçerli nokta içermeli")
        # invert_y=False: istemci y eksenini zaten yukarı-pozitif gönderir.
        #
        # smooth=True yalnızca burada: serbest çizim, bar verisinin aksine
        # alçak geçirenden geçmemiş ham bir el hareketidir; 32 noktaya
        # indirgemeden önce filtrelenmezse titreme aliasing ile çizilmemiş
        # yapıya dönüşür. Şablonlar bu bayrağı almaz — F3 eşikleri onların
        # filtrelenmemiş vektörlerinden kalibre edildi.
        vector = normalize_drawing(points, invert_y=False, smooth=True)
        if vector is None:
            raise HTTPException(
                status_code=400,
                detail="Düz çizim: şekil taşımayan bir sorgu aranamaz (σ ≈ 0)",
            )
        return vector

    raise HTTPException(status_code=400, detail="template_id veya points zorunlu")


def match_payload(match, timeframe: str, warp_path: list[list[int]] | None) -> dict[str, Any]:
    step = TIMEFRAME_MS.get(timeframe, TIMEFRAME_MS["4h"])
    data = match.as_dict()
    data["warp_path"] = warp_path
    # Pencerenin başlangıç zamanı: kart üzerinde tarih göstermek için.
    data["start_time"] = int(match.end_time - (match.window_length - 1) * step)
    return data


async def load_search(search_id: str) -> dict[str, Any]:
    data = await get_cache().get(f"search:{search_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Arama bulunamadı veya süresi doldu")
    return json.loads(data)


# ---------------------------------------------------------------------------
# Uçlar
# ---------------------------------------------------------------------------


@app.post("/api/search", response_model=SearchResponse)
async def create_search(request: SearchRequest, session_id: str = Depends(get_session_id)):
    engine = get_engine()
    cache = get_cache()

    # Hız limiti: her arama tam matris taramasıdır (§15 performans bütçesi).
    rl_count = await cache.incr(f"rl:search:{session_id}", 60)
    if rl_count > SEARCH_RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Dakikalık arama limiti aşıldı")

    session_info = await track_session(session_id)
    query_vector = resolve_query(request)

    window_lengths = [int(w) for w in (request.window_lengths or WINDOW_LENGTHS)]
    unknown = [w for w in window_lengths if w not in WINDOW_LENGTHS]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Kalibre edilmemiş pencere: {unknown}")

    result = engine.search(
        query_vector,
        mode=request.mode,
        timeframe=request.timeframe,
        window_lengths=window_lengths,
        tolerance=request.tolerance,
        min_amplitude=request.min_amplitude,
        limit=SEARCH_CACHE_MATCHES,  # sayfalama havuzu; istemciye limit kadarı gider
    )

    # İnce ayar: matris STRIDE=3 ile kurulduğu için gösterilen pencere
    # gerçek en iyi hizadan 1-2 bar kaymış olabilir (ölçüldü: ortalama
    # +0,021, en kötü +0,096 kosinüs). Yalnızca kullanıcının göreceği ilk
    # eşleşmeler düzeltilir; bar verisi gerektirdiği için bedava değildir.
    if REFINE_MATCHES and result.results:
        try:
            head = refine_matches(
                result.results[:REFINE_TOP_N],
                get_store(request.timeframe),
                query_vector,
                request.timeframe,
                null_dist=result.null_dist,
            )
            result.results = head + result.results[REFINE_TOP_N:]
        except Exception:  # ince ayar aramayı düşürmemeli
            log.warning("ince ayar atlandı", exc_info=True)

    # Hizalama yolu yalnızca ilk sayfalar için: aday başına O(32²) Python.
    warp_paths = engine.compute_warp_paths(result.results[:WARP_PATH_TOP_N], query_vector)
    matches = [
        match_payload(m, request.timeframe, warp_paths[i] if i < len(warp_paths) else None)
        for i, m in enumerate(result.results)
    ]

    search_id = str(uuid.uuid4())
    await cache.set(
        f"search:{search_id}",
        json.dumps(
            {
                "total": result.total,
                "elapsed_ms": result.elapsed_ms,
                "mode": request.mode,
                "timeframe": request.timeframe,
                "tolerance": request.tolerance,
                "discriminative": result.discriminative,
                "warning": result.warning,
                "query_vector": [float(v) for v in query_vector],
                "matches": matches,
            }
        ).encode("utf-8"),
        SEARCH_TTL,
    )

    return SearchResponse(
        search_id=search_id,
        total=result.total,
        elapsed_ms=result.elapsed_ms,
        mode=request.mode,
        timeframe=request.timeframe,
        tolerance=request.tolerance,
        data_as_of=freshness.data_as_of(request.timeframe),
        stale_warning=freshness.is_stale(request.timeframe),
        discriminative=result.discriminative,
        warning=result.warning,
        results=[MatchResponse(**m) for m in matches[: request.limit]],
        session=session_info,
    )


@app.get("/api/search/{search_id}", response_model=SearchResponse)
async def get_search(
    search_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=12, ge=1, le=48),
    session_id: str = Depends(get_session_id),
):
    parsed = await load_search(search_id)
    # Sayfalama yeni bir hipotez testi değildir: oturum sayacı artmaz.
    session_info = await read_session(session_id)
    timeframe = parsed.get("timeframe", "4h")

    page = parsed["matches"][offset : offset + limit]
    return SearchResponse(
        search_id=search_id,
        total=parsed["total"],
        elapsed_ms=parsed["elapsed_ms"],
        mode=parsed.get("mode", "historical"),
        timeframe=timeframe,
        tolerance=parsed.get("tolerance", "medium"),
        data_as_of=freshness.data_as_of(timeframe),
        stale_warning=freshness.is_stale(timeframe),
        discriminative=parsed.get("discriminative", True),
        warning=parsed.get("warning"),
        results=[MatchResponse(**m) for m in page],
        session=session_info,
    )


@app.get("/api/search/{search_id}/stats", response_model=OutcomeResponse)
async def get_search_stats(
    search_id: str,
    direction: str = Query(default="long", pattern="^(long|short)$"),
    session_id: str = Depends(get_session_id),
):
    cache = get_cache()
    await read_session(session_id)

    cached = await cache.get(f"search:{search_id}:stats:{direction}")
    if cached:
        return OutcomeResponse(**json.loads(cached))

    parsed = await load_search(search_id)
    timeframe = parsed.get("timeframe", "4h")

    if parsed.get("mode") == "live":
        # Radar eşleşmeleri son bardadır; ileri pencereleri henüz yoktur.
        raise HTTPException(
            status_code=400,
            detail="Canlı radar sonuçlarının ileri penceresi yok; istatistik için tarihsel mod kullanın",
        )

    matches = parsed["matches"]
    events = np.empty(len(matches), dtype=EVENT_DTYPE)
    for i, m in enumerate(matches):
        events[i] = (m["symbol_id"], m["end_idx"], m["window_length"], m["atr"], m["end_time"])

    outcome = run_events(
        events,
        get_store(timeframe),
        get_pools(timeframe),
        template_id="search_query",
        timeframe=timeframe,
        direction=direction,
    )

    response = to_outcome_response(outcome)
    await cache.set(
        f"search:{search_id}:stats:{direction}",
        json.dumps(response.model_dump()).encode("utf-8"),
        OUTCOME_TTL,
    )
    return response


@app.get("/api/templates", response_model=list[TemplateResponse])
async def get_templates():
    return [
        TemplateResponse(
            id=t_id,
            name=t.name_tr,
            name_en=t.name_en,
            category=t.category,
            bias=t.bias,
            description=t.description_tr,
            vector=[float(v) for v in t.vector],
        )
        for t_id, t in load_all_templates().items()
    ]


@app.get("/api/chart/{symbol}", response_model=ChartResponse)
async def get_chart(
    symbol: str,
    start: int = Query(default=0, ge=0),
    end: int = Query(default=0, ge=0),
    timeframe: str = Query(default="4h", pattern="^(4h|1d)$"),
    search_id: str | None = None,
):
    """Tek eşleşmenin mumları + blueprint katmanları.

    ``search_id`` verilirse sorgu vektörü ve hizalama yolu önbellekten
    alınır; karo "aradığın şey" ile "motorun hizaladığı şey"i birlikte gösterir.
    """
    engine = get_engine()
    store = get_store(timeframe)

    symbol_id = engine.symbol_id_of(symbol, timeframe)
    if symbol_id is None:
        raise HTTPException(status_code=404, detail=f"Bilinmeyen sembol: {symbol}")

    query: np.ndarray | None = None
    warp_path = None
    if search_id:
        parsed = await load_search(search_id)
        vector = parsed.get("query_vector") or []
        if len(vector) == N_POINTS:
            query = np.asarray(vector, dtype=np.float64)
        match = next(
            (
                m
                for m in parsed["matches"]
                if m["symbol_id"] == symbol_id and m["start_idx"] == start and m["end_idx"] == end
            ),
            None,
        )
        if match is not None:
            warp_path = match.get("warp_path")

    return build_chart(
        store,
        symbol=engine.symbol_name(symbol_id, timeframe),
        symbol_id=symbol_id,
        timeframe=timeframe,
        start_idx=start,
        end_idx=end,
        query=query,
        warp_path=warp_path,
    )


def _load_findings_file(name: str) -> list[dict]:
    """``data/f3`` altındaki ölçüm dosyası; yoksa boş liste."""
    path = DATA_DIR / "f3" / name
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
    except Exception:  # pragma: no cover - rapor dosyası opsiyonel
        log.warning("%s okunamadı", name, exc_info=True)
    return []


def _finding_stages() -> list[FindingStage]:
    """Eleme zinciri sayıları — **ölçüm dosyalarından**, elle değil.

    Bu sayılar önceden sabit kodluydu ve veriyle çelişiyordu (ör. F4.5
    Bonferroni "14/52" yazıyordu, ``f45_bonferroni.json`` ise 2 diyor —
    üstelik Bonferroni bir sayıyı artıramaz). Dürüstlük sayfasının kendi
    ölçümüne uymaması, sayfanın anlatmaya çalıştığı şeyin tam tersidir.
    """
    f4 = _load_findings_file("f4_bonferroni.json")
    f45_raw = _load_findings_file("f45_raw.json")
    f45_bonf = _load_findings_file("f45_bonferroni.json")
    f46 = _load_findings_file("f46_raw.json")

    def block_significant(row: dict) -> bool:
        lo, hi = row.get("blok_alt"), row.get("blok_ust")
        return lo is not None and hi is not None and (lo > 0.0 or hi < 0.0)

    measurable_45 = [r for r in f45_raw if r.get("olculebilir")]
    bonf_measurable = [r for r in f45_bonf if r.get("olculebilir")]

    return [
        FindingStage(
            stage="F4 — ham triple-barrier",
            significant=sum(1 for r in f4 if r.get("anlamli95")),
            total=len(f4),
            desc="ATR bariyerleri, iid bootstrap, tüm-geçmiş baseline",
        ),
        FindingStage(
            stage="F4.5 — ay-bloklu bootstrap",
            significant=sum(1 for r in measurable_45 if block_significant(r)),
            total=len(measurable_45),
            desc="Kesitsel korelasyon düzeltmesi; iid belirsizliği ~%29 eksik ölçüyordu",
        ),
        FindingStage(
            stage="F4.5 — Bonferroni (long + short)",
            significant=sum(1 for r in bonf_measurable if r.get("bonf_anlamli")),
            total=len(bonf_measurable),
            desc="14 şablon × 2 yön × 2 konfigürasyon, aile bazlı düzeltme",
        ),
        FindingStage(
            stage="F4.6 — ön-getiri eşleştirmeli gölge",
            significant=sum(1 for r in f46 if r.get("edge_is_significant")),
            total=len(f46),
            desc=(
                "Gölge havuzuna 'benzer ön-getiri' kısıtı eklendi: fark "
                "buharlaşıyorsa ölçülen şey şekil değil, momentum tersine "
                "dönüşüdür. Beş şablonun beşinde de edge yarıdan fazla eridi."
            ),
        ),
        FindingStage(
            stage="F4.6 — Bonferroni",
            significant=sum(1 for r in f46 if r.get("edge_significant_bonferroni")),
            total=len(f46),
            desc=(
                "Aynı aile, çoklu karşılaştırma düzeltmesiyle. Geçen tek satır "
                "(yükselen takoz, standart gölge) ön-getiri eşleştirilince "
                "+0,327R'den +0,115R'ye düşüp anlamlılığını kaybediyor."
            ),
        ),
    ]


@app.get("/api/findings", response_model=FindingsResponse)
async def get_findings():
    """F4 → F4.6 elemesi: kaç bulgunun hangi aşamada düştüğü.

    Ürün ilkesi gereği elenen bulgular da raporlanır; "anlamlı 2 sonuç"
    cümlesi, 52 testin 50'sinin elendiği bilgisi olmadan yanıltıcıdır.
    """
    stages = _finding_stages()

    full_table: list[dict] = []
    f46_file = DATA_DIR / "f3" / "f46_raw.json"
    try:
        if f46_file.exists():
            full_table = json.loads(f46_file.read_text(encoding="utf-8"))
    except Exception:  # pragma: no cover - rapor dosyası opsiyonel
        log.warning("f46_raw.json okunamadı", exc_info=True)

    return FindingsResponse(
        stages=stages,
        full_table=full_table,
        methodology=(
            "Aylık kesitsel likidite filtresi (üst %40), takvim ayı bloklu bootstrap, "
            "Bonferroni çoğul test düzeltmesi (m=52) ve ön-getiri eşleştirmeli gölge "
            "dağılım (±0.25σ). Bariyerler ATR tabanlıdır; aynı barda TP ve SL "
            "çarpıldığında SL varsayılır."
        ),
    )
