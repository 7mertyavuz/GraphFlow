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
import os
import threading
import uuid
from contextlib import asynccontextmanager
from typing import Any

import numpy as np
from fastapi import Depends, FastAPI, HTTPException, Query, Header
from fastapi.middleware.cors import CORSMiddleware

from engine.api import freshness, health
from engine.api.cache import OUTCOME_TTL, RADAR_TTL, SEARCH_TTL, get_cache
from engine.api.chart import build_chart
from engine.api.schemas import (
    ChartResponse,
    FindingProvenance,
    FindingsResponse,
    FindingStage,
    MatchResponse,
    OutcomeConfigResponse,
    OutcomeResponse,
    RegimeRow,
    ReturnDistribution,
    SearchRequest,
    SearchResponse,
    SeedStability,
    StabilityCell,
    StabilityRow,
    StatEnvelope,
    TemplateResponse,
)
from engine.api.session import get_session_id, read_session, track_session
from engine.i18n import resolve_lang, t
from engine.search.constraints import describe_envelope, describe_signature
from engine.config import (
    DATA_DIR,
    RETURN_MATCH_BAND_SIGMA,
    TIMEFRAMES,
    N_POINTS,
    NULL_SAMPLE_SIZE,
    REFINE_MATCHES,
    REFINE_TOP_N,
    SEARCH_CACHE_MATCHES,
    SEARCH_RATE_LIMIT,
    SOURCE_MAX_BARS,
    SOURCE_MIN_BARS,
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
from engine.search.source import ChartWindow, SourceError, chart_window
from engine.templates.loader import load_all as load_all_templates

log = logging.getLogger(__name__)

#: Açılışta kütüphane şablonlarının null dağılımını önden hesapla.
#: Kapalı varsayılan: testler `app`'i içe aktarır ve 14 şablon × 2 dilimlik
#: bir ısıtma onları dakikalarca yavaşlatırdı. Sunucu bunu açıkça ister.
WARMUP_ENV = "GRAPHFLOW_WARMUP"

#: Isıtma sorguları arasında beklenecek süre (saniye).
WARMUP_PAUSE_SEC = 0.4


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Soğuk ilk sorguyu arka planda ısıtır (§15 ölçülen aşım).

    F3.5'in sorgu-göreli null kalibrasyonu her YENİ şekil için uzunluk başına
    2.000 rastgele pencereyi Aşama 2'den geçirir; bu ilk çağrıya ~180 ms
    ekliyor ve 4h'de toplam süreyi 500 ms bütçesinin üstüne taşıyordu
    (ölçüldü: soğuk 537-595 ms, sıcak 365-417 ms).

    Kütüphane şablonları sabit ve sayılı olduğu için dağılımları açılışta
    hesaplanabilir. Serbest çizim ısıtılamaz — sonsuz uzay.

    Arka plan iş parçacığında: ısıtma sunucunun ayağa kalkmasını geciktirmez,
    hata verirse aramayı düşürmez.
    """
    _attach_engine_logging()
    if os.environ.get(WARMUP_ENV):
        threading.Thread(target=_warm_template_nulls, daemon=True).start()
    yield


app = FastAPI(
    title="GraphFlow API",
    version="1.0.0",
    description="Görsel formasyon arama motoru — ölçülmüş geçmiş dağılım, sinyal değil.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")

def get_lang(accept_language: str | None = Header(default=None)) -> str:
    """İsteğin dili — ``Accept-Language`` (engine.i18n)."""
    return resolve_lang(accept_language)


def _jsonable(sig: tuple | None) -> list | None:
    """İmza demeti → JSON listesi (numpy skalerleri düz Python'a)."""
    if sig is None:
        return None
    return [bool(v) if isinstance(v, (bool,)) or type(v).__name__ == "bool_" else int(v) for v in sig]


def _texts(src: dict, lang: str) -> dict[str, str | None]:
    """Önbellekteki dilden bağımsız veriden kullanıcı metinleri.

    Önbelleğe metin değil imza ve uyarı kodu yazılır: Radar önbelleğini bir
    Türkçe istemci doldurduysa İngilizce istemci Türkçe metin almamalı.
    """
    sig = src.get("structure_signature")
    env = src.get("envelope_signature")
    code = src.get("warning_code")
    return {
        "warning": t(f"warn.{code}", lang) if code else None,  # type: ignore[arg-type]
        "structure_read": describe_signature(tuple(sig), lang) if sig else None,
        "envelope_read": describe_envelope(tuple(env), lang) if env else None,
    }


# ---------------------------------------------------------------------------
# Tembel yüklenen ağır nesneler (matrisler memmap, bar deposu ~yüz MB)
# ---------------------------------------------------------------------------

_engine: SearchEngine | None = None
_stores: dict[str, BarStore] = {}
_pools_by_tf: dict[str, dict[int, ShadowPool]] = {}


def _attach_engine_logging() -> None:
    """Motor loglarını uvicorn'un akışına bağlar.

    uvicorn yalnız kendi ("uvicorn*") logger'larına handler kurar; kök
    logger'da handler olmadığı için motorun ``log.info`` çağrıları hiçbir yere
    gitmiyordu. Görünmeyen tek şey gürültü değildi — atlanan ince ayar,
    okunamayan ölçüm dosyası, ısıtma hatası da sessizce kayboluyordu.
    ``lastResort`` yalnız WARNING ve üstünü, o da biçimsiz basıyor.
    """
    handlers = logging.getLogger("uvicorn").handlers
    if not handlers:
        return
    engine_log = logging.getLogger("engine")
    if engine_log.handlers:
        return
    for handler in handlers:
        engine_log.addHandler(handler)
    engine_log.setLevel(logging.INFO)


def _warm_template_nulls() -> None:
    """Her şablon için bir kez arama koşarak null önbelleğini doldurur."""
    import time

    started = time.time()
    engine = get_engine()
    warmed = 0
    for timeframe in TIMEFRAMES:
        for template_id, template in load_all_templates().items():
            try:
                engine.search(
                    np.asarray(template.vector, dtype=np.float64),
                    timeframe=timeframe,
                    limit=1,
                )
                warmed += 1
            except Exception:  # matris yoksa ya da bozuksa arama yine çalışır
                log.warning("ısıtma atlandı: %s/%s", timeframe, template_id, exc_info=True)
            # Nefes payı: NumPy GIL'i bıraktığı için ısıtma gerçek CPU
            # rekabeti yaratıyor. Ölçüldü — ısıtma sürerken gelen bir istek
            # 1.444 ms'ye çıkabiliyordu. Ara vermek ısıtmayı birkaç saniye
            # uzatır, öndeki kullanıcıyı bekletmez.
            time.sleep(WARMUP_PAUSE_SEC)
    log.info("null önbelleği ısıtıldı: %d sorgu, %.0f sn", warmed, time.time() - started)


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


def to_outcome_config(stats: OutcomeStats, lang: str = "tr") -> OutcomeConfigResponse:
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
            verdict=stats.verdict_text(lang),
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
        insufficient=stats.insufficient,
        outcomes=stats.outcomes,
        truncated=stats.truncated,
        by_regime=[RegimeRow(**row) for row in stats.by_regime],
    )


def to_outcome_response(outcome: TemplateOutcome, lang: str = "tr") -> OutcomeResponse:
    return OutcomeResponse(
        configs={name: to_outcome_config(s, lang) for name, s in outcome.stats.items()},
        matches=outcome.matches,
        n_events=outcome.events,
        dropped_forward_overlap=outcome.dropped_separation,
        dropped_filters=outcome.dropped_filters,
        direction=outcome.direction,
        shadow=outcome.shadow_report,
        paths=outcome.paths,
        ledger=outcome.ledger or [],
        disclaimer=t("disclaimer", lang),  # type: ignore[arg-type]
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

    raise HTTPException(status_code=400, detail="template_id, points veya source zorunlu")


def resolve_source(request: SearchRequest, lang: str = "tr") -> ChartWindow:
    """``source`` → sorgunun kurulduğu gerçek grafik parçası.

    Parça matris pencereleriyle aynı normalizasyondan geçer
    (engine/search/source.py); motor, dönen pencereyi aramada kendisiyle
    eşleşmemesi için dışlama bilgisi olarak da kullanır.
    """
    src = request.source
    assert src is not None
    symbol = src.symbol.strip().upper()
    kwargs = {"symbol": symbol, "length": src.length, "min": SOURCE_MIN_BARS, "max": SOURCE_MAX_BARS}
    symbol_id = get_engine().symbol_id_of(symbol, request.timeframe)
    if symbol_id is None:
        raise HTTPException(status_code=400, detail=t("source.unknown_symbol", lang, **kwargs))  # type: ignore[arg-type]
    try:
        return chart_window(get_store(request.timeframe), symbol_id, src.length, src.end_time)
    except SourceError as err:
        raise HTTPException(
            status_code=400, detail=t(f"source.{err.code}", lang, **kwargs)  # type: ignore[arg-type]
        ) from None


def source_payload(window: ChartWindow, timeframe: str, excluded_overlap: int) -> dict[str, Any]:
    return {
        "symbol": get_engine().symbol_name(window.symbol_id, timeframe),
        "start_time": window.start_time,
        "end_time": window.end_time,
        "length": window.length,
        "query_vector": [round(float(v), 6) for v in window.vector],
        "excluded_overlap": int(excluded_overlap),
    }


def match_payload(match, timeframe: str, warp_path: list[list[int]] | None) -> dict[str, Any]:
    step = TIMEFRAME_MS.get(timeframe, TIMEFRAME_MS["4h"])
    data = match.as_dict()
    data["warp_path"] = warp_path
    # Pencerenin başlangıç zamanı: kart üzerinde tarih göstermek için.
    data["start_time"] = int(match.end_time - (match.window_length - 1) * step)
    return data


def query_fingerprint(request: SearchRequest, query_vector: np.ndarray, window_lengths: list[int]) -> str:
    """Sorgunun kimliği — Bonferroni ailesi bunu sayar, isteği değil.

    Aynı şekli aynı parametrelerle yeniden sormak (kullanıcı tekrar tıkladı,
    Radar kendini yeniledi) **yeni bir hipotez değildir**. Parmak izi
    şeklin kendisinden türetilir: serbest çizimde vektörün hash'i, kütüphanede
    şablon kimliği.
    """
    import hashlib

    if request.template_id:
        shape = f"t:{request.template_id}"
    else:
        digest = hashlib.sha1(np.asarray(query_vector, dtype=np.float32).tobytes()).hexdigest()
        shape = f"d:{digest[:16]}"

    return (
        f"{shape}:{request.mode}:{request.timeframe}:{request.tolerance}"
        f":{request.min_amplitude}:{'-'.join(str(w) for w in sorted(window_lengths))}"
    )


def radar_key(request: SearchRequest, window_lengths: list[int]) -> str | None:
    """Radar önbelleği anahtarı — yalnız **kütüphane şablonu** sorguları için.

    docs/01-mimari.md §6: kütüphanedeki şablonların canlı sonuçları 5 dakikada
    bir önceden hesaplanır ki kullanıcı "OBO" tıkladığında sonuç anında gelsin.
    Serbest çizim önbelleğe alınmaz: her çizim farklıdır, anahtar uzayı
    sınırsızdır ve isabet oranı sıfıra yakındır.

    TTL, cron döngüsüyle aynı (``RADAR_TTL`` = 300 sn). Bu aynı zamanda
    tazelik sınırıdır: 4h barı 4 saatte kapanır, 5 dakikalık bayatlık
    görünmez — ama daha uzun bir TTL, kapanmış bir barı geç göstermeye başlar.
    """
    if request.mode != "live" or not request.template_id:
        return None
    return (
        f"radar:{request.template_id}:{request.timeframe}:{request.tolerance}"
        f":{request.min_amplitude}:{'-'.join(str(w) for w in sorted(window_lengths))}"
    )


async def load_search(search_id: str) -> dict[str, Any]:
    data = await get_cache().get(f"search:{search_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Arama bulunamadı veya süresi doldu")
    return json.loads(data)


# ---------------------------------------------------------------------------
# Uçlar
# ---------------------------------------------------------------------------


@app.post("/api/search", response_model=SearchResponse)
async def create_search(
    request: SearchRequest,
    session_id: str = Depends(get_session_id),
    lang: str = Depends(get_lang),
):
    engine = get_engine()
    cache = get_cache()

    # Hız limiti: her arama tam matris taramasıdır (§15 performans bütçesi).
    rl_count = await cache.incr(f"rl:search:{session_id}", 60)
    if rl_count > SEARCH_RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Dakikalık arama limiti aşıldı")

    # Gerçek grafikten sorgu yalnız başka bir şekil verilmediyse: çizim ya da
    # şablon açıkça seçildiyse onlar kazanır (arayüz bir anda tek kaynak yollar).
    source_window = (
        resolve_source(request, lang)
        if request.source is not None and not request.template_id and not request.points
        else None
    )
    query_vector = source_window.vector if source_window is not None else resolve_query(request)

    window_lengths = [int(w) for w in (request.window_lengths or WINDOW_LENGTHS)]
    unknown = [w for w in window_lengths if w not in WINDOW_LENGTHS]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Kalibre edilmemiş pencere: {unknown}")

    # Sayaç ayrı hipotez sayar: aynı şekil aynı parametrelerle tekrar
    # sorulduğunda artmaz (Radar'ın kendini yenilemesi dahil).
    session_info = await track_session(
        session_id, query_fingerprint(request, query_vector, window_lengths), lang
    )

    # Radar önbelleği (§6): aynı şablon 5 dakika içinde yeniden sorulursa
    # matris yeniden taranmaz.
    rkey = radar_key(request, window_lengths)
    if rkey is not None:
        cached_id = await cache.get(rkey)
        if cached_id:
            hit_id = cached_id.decode("utf-8")
            parsed = await cache.get(f"search:{hit_id}")
            if parsed:
                stored = json.loads(parsed)
                page = stored["matches"][: request.limit]
                return SearchResponse(
                    search_id=hit_id,
                    total=stored["total"],
                    elapsed_ms=stored["elapsed_ms"],
                    mode=stored.get("mode", "live"),
                    timeframe=stored.get("timeframe", request.timeframe),
                    tolerance=stored.get("tolerance", request.tolerance),
                    # Tazelik ÖNBELLEKTEN GELMEZ: depo bu 5 dakika içinde
                    # bayatlamış olabilir ve uyarı yanıtın içinde taşınır.
                    data_as_of=freshness.data_as_of(request.timeframe),
                    stale_warning=freshness.is_stale(request.timeframe),
                    discriminative=stored.get("discriminative", True),
                    **_texts(stored, lang),
                    structure_filtered=stored.get("structure_filtered", False),
                    structure_stable=stored.get("structure_stable", True),
                    envelope_filtered=stored.get("envelope_filtered", False),
                    results=[MatchResponse(**m) for m in page],
                    session=session_info,
                )

    result = engine.search(
        query_vector,
        mode=request.mode,
        timeframe=request.timeframe,
        window_lengths=window_lengths,
        tolerance=request.tolerance,
        min_amplitude=request.min_amplitude,
        limit=SEARCH_CACHE_MATCHES,  # sayfalama havuzu; istemciye limit kadarı gider
        exclude=source_window,
    )
    source = (
        source_payload(source_window, request.timeframe, result.excluded_overlap)
        if source_window is not None
        else None
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
                # Metin değil veri (engine.i18n): metin yanıt anında dile göre.
                "warning_code": result.warning_code,
                "structure_signature": _jsonable(result.structure_signature),
                "structure_filtered": result.structure_filtered,
                "structure_stable": result.structure_stable,
                "envelope_signature": _jsonable(result.envelope_signature),
                "envelope_filtered": result.envelope_filtered,
                "query_vector": [float(v) for v in query_vector],
                "source": source,
                "matches": matches,
            }
        ).encode("utf-8"),
        SEARCH_TTL,
    )
    if rkey is not None:
        await cache.set(rkey, search_id.encode("utf-8"), RADAR_TTL)

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
        **_texts(
            {
                "warning_code": result.warning_code,
                "structure_signature": result.structure_signature,
                "envelope_signature": result.envelope_signature,
            },
            lang,
        ),
        structure_filtered=result.structure_filtered,
        structure_stable=result.structure_stable,
        envelope_filtered=result.envelope_filtered,
        source=source,
        results=[MatchResponse(**m) for m in matches[: request.limit]],
        session=session_info,
    )


@app.get("/api/search/{search_id}", response_model=SearchResponse)
async def get_search(
    search_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=12, ge=1, le=48),
    session_id: str = Depends(get_session_id),
    lang: str = Depends(get_lang),
):
    parsed = await load_search(search_id)
    # Sayfalama yeni bir hipotez testi değildir: oturum sayacı artmaz.
    session_info = await read_session(session_id, lang)
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
        **_texts(parsed, lang),
        structure_filtered=parsed.get("structure_filtered", False),
        structure_stable=parsed.get("structure_stable", True),
        envelope_filtered=parsed.get("envelope_filtered", False),
        source=parsed.get("source"),
        results=[MatchResponse(**m) for m in page],
        session=session_info,
    )


@app.get("/api/search/{search_id}/stats", response_model=OutcomeResponse)
async def get_search_stats(
    search_id: str,
    direction: str = Query(default="long", pattern="^(long|short)$"),
    session_id: str = Depends(get_session_id),
    lang: str = Depends(get_lang),
):
    cache = get_cache()
    await read_session(session_id, lang)

    # Anahtar dili de içerir: yanıtta hüküm ve sorumluluk reddi metni var.
    stats_key = f"search:{search_id}:stats:{direction}:{lang}"
    cached = await cache.get(stats_key)
    if cached:
        return OutcomeResponse(**json.loads(cached))

    parsed = await load_search(search_id)
    timeframe = parsed.get("timeframe", "4h")

    if parsed.get("mode") == "live":
        # Radar eşleşmeleri son bardadır; ileri pencereleri henüz yoktur.
        raise HTTPException(
            status_code=400,
            detail=t("live_no_stats", lang),  # type: ignore[arg-type]
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
        with_paths=True,
        with_ledger=True,
    )

    response = to_outcome_response(outcome, lang)
    await cache.set(
        stats_key,
        json.dumps(response.model_dump()).encode("utf-8"),
        OUTCOME_TTL,
    )
    return response


@app.get("/api/symbols", response_model=list[str])
async def get_symbols(timeframe: str = Query(default="4h", pattern="^(4h|1d)$")):
    """Zaman diliminin sembol evreni — grafikten sorgu için.

    ``symbol_id`` uzayı zaman dilimi başınadır; liste de öyle. Delist olmuş
    semboller de listededir: geçmiş bir tarihteki parçaları hâlâ sorulabilir.
    """
    return sorted(set(get_engine().symbols_for(timeframe).values()))


@app.get("/api/templates", response_model=list[TemplateResponse])
async def get_templates(lang: str = Depends(get_lang)):
    return [
        TemplateResponse(
            id=t_id,
            name=tpl.name_en if lang == "en" else tpl.name_tr,
            name_en=tpl.name_en,
            category=tpl.category,
            bias=tpl.bias,
            description=(tpl.description_en or tpl.description_tr) if lang == "en" else tpl.description_tr,
            vector=[float(v) for v in tpl.vector],
        )
        for t_id, tpl in load_all_templates().items()
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


def _block_significant(row: dict) -> bool:
    lo, hi = row.get("blok_alt"), row.get("blok_ust")
    return lo is not None and hi is not None and (lo > 0.0 or hi < 0.0)


def _replicated_cells() -> list[tuple[str, str, str]]:
    """1d ve 4h'de **aynı yönde** anlamlı çıkan hücreler (F4.7).

    Bir bulgu tek zaman diliminde anlamlıysa bulgu değildir. İki dilim
    bağımsız veri kümesi olmasa da (aynı piyasa, aynı semboller) farklı
    pencereleme ve toplulaştırma kullanır; replikasyon bir sağlamlık
    kontrolüdür.
    """
    one_day = _load_findings_file("f45_raw.json")
    four_hour = _load_findings_file("f45_raw_4h.json")
    if not one_day or not four_hour:
        return []

    def key(row: dict) -> tuple:
        return (row.get("sablon"), row.get("yon"), row.get("konf"))

    by_4h = {key(r): r for r in four_hour}
    cells: list[tuple[str, str, str]] = []
    for row in one_day:
        other = by_4h.get(key(row))
        if other is None or not (_block_significant(row) and _block_significant(other)):
            continue
        # Aynı yön şartı: işaret dönüyorsa replikasyon değil, çelişkidir.
        if (row.get("edge") or 0.0) * (other.get("edge") or 0.0) > 0:
            cells.append(key(row))
    return sorted(cells)


def _replicated() -> int:
    return len(_replicated_cells())


def _f46_primary(rows: list[dict]) -> list[dict]:
    """Ön-getiri eşleştirmeli gölge, BİRİNCİL bant (duyarlılık bantları hariç).

    Eskiden sayım tüm satırlar üzerindendi — standart gölge satırları da
    dahil. Standart gölge vekil testinin kontrol koludur; "eşleştirmeli
    gölgeden sonra anlamlı kalan" sayısına onu katmak soruyu bulandırıyordu.
    """
    return [
        r for r in rows
        if r.get("shadow_type") == "return_matched"
        and abs((r.get("band_sigma") or 0.0) - RETURN_MATCH_BAND_SIGMA) < 1e-6
    ]


def _f46_replicated() -> list[tuple[str, str]]:
    """Eşleştirmeli gölgeden sonra 1d VE 4h'de aynı yönde anlamlı kalanlar."""
    four_hour = {
        (r["template_id"], r["config"]): r
        for r in _f46_primary(_load_findings_file("f46_raw_4h.json"))
    }
    survivors: list[tuple[str, str]] = []
    for r in _f46_primary(_load_findings_file("f46_raw.json")):
        other = four_hour.get((r["template_id"], r["config"]))
        if not (r.get("edge_is_significant") and other and other.get("edge_is_significant")):
            continue
        if (r.get("edge_r") or 0.0) * (other.get("edge_r") or 0.0) > 0:
            survivors.append((r["template_id"], r["config"]))
    return sorted(survivors)


def _template_name(template_id: str, lang: str) -> str:
    """Şablonun adı istenen dilde — şablon dosyasından, elle yazılmış sözlükten değil."""
    tpl = load_all_templates().get(template_id)
    if tpl is None:
        return template_id
    return tpl.name_en if lang == "en" else tpl.name_tr


def _describe_cells(cells: list[tuple], lang: str = "tr") -> str:
    """Hücre listesini okunur metne çevirir — açıklamalar veriden gelir."""
    if not cells:
        return t("cells.none", lang)  # type: ignore[arg-type]
    return ", ".join(
        " ".join([_template_name(c[0], lang), *(str(x) for x in c[1:])]) for c in cells
    )


def _finding_stages(lang: str = "tr", stability: SeedStability | None = None) -> list[FindingStage]:
    """Eleme zinciri sayıları — **ölçüm dosyalarından**, elle değil.

    Bu sayılar önceden sabit kodluydu ve veriyle çelişiyordu (ör. F4.5
    Bonferroni "14/52" yazıyordu, ``f45_bonferroni.json`` ise 2 diyor —
    üstelik Bonferroni bir sayıyı artıramaz). Dürüstlük sayfasının kendi
    ölçümüne uymaması, sayfanın anlatmaya çalıştığı şeyin tam tersidir.
    Metinler ``engine.i18n`` kataloğundandır.
    """
    L = lang
    f4 = _load_findings_file("f4_bonferroni.json")
    f45_raw = _load_findings_file("f45_raw.json")
    f45_bonf = _load_findings_file("f45_bonferroni.json")
    f46 = _load_findings_file("f46_raw.json")

    measurable_45 = [r for r in f45_raw if r.get("olculebilir")]
    f46_primary = _f46_primary(f46)
    f46_survivors = _f46_replicated()
    replicated = _replicated_cells()
    bonf_measurable = [r for r in f45_bonf if r.get("olculebilir")]
    tested = _describe_cells(sorted({(r["template_id"],) for r in f46_primary}), L)

    def stage(key: str, significant: int, total: int, **kw) -> FindingStage:
        return FindingStage(
            stage=t(f"stage.{key}", L),  # type: ignore[arg-type]
            significant=significant,
            total=total,
            desc=t(f"stage.{key}.desc", L, **kw),  # type: ignore[arg-type]
        )

    return [
        stage("f4", sum(1 for r in f4 if r.get("anlamli95")), len(f4)),
        stage("f45", sum(1 for r in measurable_45 if _block_significant(r)), len(measurable_45)),
        stage("f45b", sum(1 for r in bonf_measurable if r.get("bonf_anlamli")), len(bonf_measurable)),
        stage("f46", sum(1 for r in f46_primary if r.get("edge_is_significant")), len(f46_primary), cells=tested),
        stage("f46b", sum(1 for r in f46_primary if r.get("edge_significant_bonferroni")), len(f46_primary)),
        stage("f46r", len(f46_survivors), len(f46_primary), cells=_describe_cells(f46_survivors, L)),
        _with_robust(
            stage("f47", len(replicated), len(f45_raw), cells=_describe_cells(replicated, L)),
            stability,
            L,
        ),
    ]


def _with_robust(stage: FindingStage, stability: SeedStability | None, lang: str) -> FindingStage:
    """F4.7'nin tek-çekiliş sayısının yanına her çekilişte replike edenleri ekler.

    Yayımlanan replikasyon sayısı tek bir null çekilişinindir (docs/12);
    yalnız o sayıyı göstermek, şanslı bir çekilişi bulgu gibi sunmaktır.
    """
    if stability is None or stability.engine_match is not True or not stability.rows:
        return stage
    robust = [
        (r.template_id, r.direction, r.config)
        for r in stability.rows
        if r.seeds_replicated == stability.seeds
    ]
    extra = t("stage.f47.robust", lang, seeds=stability.seeds, cells=_describe_cells(robust, lang))  # type: ignore[arg-type]
    return stage.model_copy(update={"desc": stage.desc + extra})


#: Ölçüm tabloları ve köken dosyaları. f4/f45 tabloları kökenlerini
#: ``f45_meta*.json``'da taşır (tablolar liste olduğu için).
_PROVENANCE_FILES: tuple[tuple[str, str, str], ...] = (
    ("f45_raw.json", "f45_meta.json", "F4/F4.5 · 1d"),
    ("f45_raw_4h.json", "f45_meta_4h.json", "F4/F4.5 · 4h"),
    ("f46_raw.json", "f46_meta.json", "F4.6 · 1d"),
    ("f46_raw_4h.json", "f46_meta_4h.json", "F4.6 · 4h"),
)


def _bonferroni_family() -> int | str:
    """F4.5 ailesinin boyutu — ölçüm dosyasından.

    Metinde "m=52" sabit yazılıydı; ölçüm 56 test sayıyordu. Yöntem metni
    de bir sayıdır ve veriden gelmelidir.
    """
    path = DATA_DIR / "f3" / "f45_meta.json"
    try:
        meta = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        return int(meta.get("family_size")) if meta.get("family_size") else "?"
    except Exception:  # pragma: no cover - rapor dosyası opsiyonel
        return "?"


def _findings_provenance(lang: str = "tr") -> list[FindingProvenance]:
    """Her ölçüm tablosunu bugünkü motorla karşılaştırır.

    Bu kontrol yokken tablolar motor değiştikçe sessizce bayatlıyordu:
    Eylül 2026'da üç filtre değişikliği aynı gün bağlandı, "Bulgular"
    sayfası bir önceki günün motorunun istatistiğini göstermeye devam etti.

    Anahtar TABLONUN varlığıdır, köken dosyasının değil: tablo var ama köken
    yoksa durum "bilinmiyor"dur ve öyle raporlanır — atlanması, kökensiz bir
    tabloyu sessizce güncel saymak olurdu.
    """
    from engine.fingerprint import compare

    out: list[FindingProvenance] = []
    for table, meta_name, label in _PROVENANCE_FILES:
        if not (DATA_DIR / "f3" / table).exists():
            continue
        meta: dict = {}
        path = DATA_DIR / "f3" / meta_name
        try:
            if path.exists():
                loaded = json.loads(path.read_text(encoding="utf-8"))
                meta = loaded if isinstance(loaded, dict) else {}
        except Exception:  # pragma: no cover - rapor dosyası opsiyonel
            log.warning("%s okunamadı", meta_name, exc_info=True)
        match, reason = compare(meta.get("fingerprint"), lang)
        out.append(FindingProvenance(
            file=label,
            timeframe=meta.get("timeframe"),
            generated_at=meta.get("generated_at"),
            data_as_of=meta.get("data_as_of"),
            engine_match=match,
            reason=reason,
        ))
    return out


def _seed_stability(lang: str = "tr") -> SeedStability | None:
    """Tohum kararlılığı tablosu — ``tools/null_sensitivity`` çıktısından.

    Yalnız motorun GÜNCEL null büyüklüğündeki koşular sayılır; başka bir
    büyüklükle yapılmış bir koşu bugünkü motorun kararlılığını anlatmaz.
    Köken motor parmak iziyle denetlenir, tıpkı öteki tablolar gibi.
    Satırlar yayımlanan tablodan (varsayılan tohum) edge ve GA taşır;
    kararlılık sayıları onların yanında durur, yerine geçmez.
    """
    from engine.fingerprint import compare

    path = DATA_DIR / "f3" / "null_sensitivity.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    except Exception:  # pragma: no cover - rapor dosyası opsiyonel
        log.warning("null_sensitivity.json okunamadı", exc_info=True)
        data = None
    if not isinstance(data, dict):
        return None
    runs = [r for r in data.get("runs", []) if r.get("null_sample") == NULL_SAMPLE_SIZE]
    if not runs:
        return None

    timeframes = [tf for tf in ("1d", "4h") if all(tf in r for r in runs)]
    published = {
        "1d": {(r["sablon"], r["yon"], r["konf"]): r for r in _load_findings_file("f45_raw.json")},
        "4h": {(r["sablon"], r["yon"], r["konf"]): r for r in _load_findings_file("f45_raw_4h.json")},
    }
    matches = [compare((data.get("provenance") or {}).get(tf, {}).get("fingerprint"), lang) for tf in timeframes]
    engine_match: bool | None = True
    reason = None
    for match, why in matches:
        if match is not True:
            engine_match, reason = match, why
            break

    keys = sorted({tuple(k.split("|")) for r in runs for tf in timeframes for k in r[tf].get("tested", [])})
    rows: list[StabilityRow] = []
    for direction, template_id, config in keys:
        key = "|".join((direction, template_id, config))
        cells = []
        for tf in timeframes:
            pub = published.get(tf, {}).get((template_id, direction, config), {})
            lo, hi = pub.get("blok_alt"), pub.get("blok_ust")
            cells.append(StabilityCell(
                timeframe=tf,
                edge=pub.get("edge"),
                ci95=[lo, hi] if lo is not None and hi is not None else None,
                n_events=int(pub.get("N") or 0),
                significant=_block_significant(pub) if pub else False,
                seeds_significant=sum(1 for r in runs if key in r[tf].get("sig95", {})),
                seeds_bonferroni=sum(1 for r in runs if key in r[tf].get("bonferroni", [])),
            ))
        rows.append(StabilityRow(
            template_id=template_id,
            template=_template_name(template_id, lang),
            direction=direction,
            config=config,
            cells=cells,
            seeds_replicated=sum(1 for r in runs if key in r.get("replicated", [])),
        ))
    # Sağlam olan üstte: replikasyon, sonra en kararlı dilim.
    rows.sort(key=lambda r: (-r.seeds_replicated, -max((c.seeds_significant for c in r.cells), default=0),
                             r.template_id, r.direction, r.config))
    return SeedStability(
        seeds=len(runs),
        null_sample=NULL_SAMPLE_SIZE,
        engine_match=engine_match,
        reason=reason,
        rows=rows,
    )


@app.get("/api/findings", response_model=FindingsResponse)
def get_findings(lang: str = Depends(get_lang)):
    """F4 → F4.6 elemesi: kaç bulgunun hangi aşamada düştüğü.

    Ürün ilkesi gereği elenen bulgular da raporlanır; "anlamlı 2 sonuç"
    cümlesi, 52 testin 50'sinin elendiği bilgisi olmadan yanıltıcıdır.
    """
    stability = _seed_stability(lang)
    stages = _finding_stages(lang, stability)

    full_table: list[dict] = []
    f46_file = DATA_DIR / "f3" / "f46_raw.json"
    try:
        if f46_file.exists():
            full_table = json.loads(f46_file.read_text(encoding="utf-8"))
    except Exception:  # pragma: no cover - rapor dosyası opsiyonel
        log.warning("f46_raw.json okunamadı", exc_info=True)

    provenance = _findings_provenance(lang)
    return FindingsResponse(
        stages=stages,
        full_table=full_table,
        provenance=provenance,
        stability=stability,
        stale=any(p.engine_match is not True for p in provenance)
        or (stability is not None and stability.engine_match is not True),
        methodology=t(
            "methodology",
            lang,  # type: ignore[arg-type]
            m=_bonferroni_family(),
            band=f"{RETURN_MATCH_BAND_SIGMA:.2f}",
        ),
    )
