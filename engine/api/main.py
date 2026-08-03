from __future__ import annotations

import json
import logging
import uuid
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from engine.api.cache import get_cache, SEARCH_TTL, OUTCOME_TTL
from engine.api.session import get_session_id, track_session, get_warning_text
from engine.api.schemas import (
    SearchRequest,
    SearchResponse,
    MatchResponse,
    StatEnvelope,
    OutcomeConfigResponse,
    OutcomeResponse,
    ChartResponse,
    TemplateResponse,
    FindingsResponse,
    SessionInfo
)
from engine.api import health
from engine.search.engine import SearchEngine
from engine.outcome.bars import BarStore
from engine.config import DATA_DIR, MATRIX_DIR, WINDOW_LENGTHS
from engine.templates.loader import load_all as load_all_templates
from engine.outcome.pipeline import load_shadow_pools, run_template
from engine.outcome.shadow import ShadowPool
from engine.outcome.metrics import OutcomeStats

log = logging.getLogger(__name__)

app = FastAPI(title="GraphFlow F5 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")

# Lazy globals
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
        engine = get_engine()
        _stores[timeframe] = BarStore.from_klines(
            symbols=list(engine.symbols.values()),
            timeframe=timeframe,
            ids={v: k for k, v in engine.symbols.items()}
        )
    return _stores[timeframe]

def get_pools(timeframe: str = "4h") -> dict[int, ShadowPool]:
    if timeframe not in _pools_by_tf:
        _pools_by_tf[timeframe] = load_shadow_pools(timeframe)
    return _pools_by_tf[timeframe]

def wrap_stat(
    val: float | None,
    ci: tuple[float, float],
    ci_method: str,
    null_val: float | None = None,
    shadow_val: float | None = None,
    n_events: int = 0,
    n_months: int = 0,
    significant: bool = False,
    verdict: str = "",
    design_effect: float | None = None
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
        design_effect=design_effect
    )

def to_outcome_config(stats: OutcomeStats) -> OutcomeConfigResponse:
    expectancy = wrap_stat(
        val=stats.expectancy_r,
        ci=stats.expectancy_ci,
        ci_method="bootstrap",
        null_val=0.0,
        n_events=stats.n,
        n_months=stats.n_months,
        significant=stats.expectancy_ci[0] > 0 if stats.expectancy_ci else False,
        verdict=""
    )
    
    win_rate = wrap_stat(
        val=stats.win_rate,
        ci=stats.win_rate_ci,
        ci_method="wilson",
        null_val=stats.theoretical_null,
        n_events=stats.n,
        n_months=stats.n_months,
        significant=stats.win_rate_ci[0] > stats.theoretical_null if stats.win_rate_ci else False,
        verdict=""
    )
    
    edge = None
    if stats.shadow_n > 0:
        edge = wrap_stat(
            val=stats.edge_r,
            ci=stats.edge_ci if stats.edge_ci else (float("nan"), float("nan")),
            ci_method="block_bootstrap" if stats.design_effect else "bootstrap",
            shadow_val=stats.shadow_expectancy_r,
            n_events=stats.n,
            n_months=stats.n_months,
            significant=stats.edge_is_significant,
            verdict=stats.verdict,
            design_effect=stats.design_effect
        )
        
    return OutcomeConfigResponse(
        config=stats.config,
        expectancy=expectancy,
        win_rate=win_rate,
        edge=edge,
        outcomes=stats.outcomes,
        truncated=stats.truncated,
        by_regime=stats.by_regime
    )


@app.post("/api/search", response_model=SearchResponse)
async def create_search(
    request: SearchRequest,
    session_id: str = Depends(get_session_id)
):
    import numpy as np
    
    engine = get_engine()
    cache = get_cache()
    session_info = await track_session(session_id)
    
    # Check rate limit (simple implementation)
    rl_key = f"rl:search:{session_id}"
    rl_count = await cache.incr(rl_key)
    if rl_count == 1:
        await cache.set(rl_key, b"1", 60)
    elif rl_count > 10:
        raise HTTPException(status_code=429, detail="Too many searches per minute")
        
    query_vector = None
    if request.template_id:
        templates = load_all_templates()
        if request.template_id not in templates:
            raise HTTPException(status_code=400, detail="Invalid template_id")
        query_vector = np.array(templates[request.template_id].vector)
    elif request.points:
        query_vector = np.array(request.points)
    else:
        raise HTTPException(status_code=400, detail="Must provide template_id or points")
        
    search_id = str(uuid.uuid4())
    
    result = engine.search(
        query_vector,
        mode=request.mode,
        timeframe=request.timeframe,
        window_lengths=request.window_lengths,
        tolerance=request.tolerance,
        min_amplitude=request.min_amplitude,
        limit=1000 # get a bunch to cache
    )
    
    matches = [MatchResponse(**m.as_dict()) for m in result.results]
    
    # Generate warp paths for top 50 matches (DTW path caching)
    top_n = min(len(result.results), 50)
    warp_paths = engine.compute_warp_paths(result.results[:top_n], query_vector)

    matches_data = []
    for idx, m in enumerate(result.results):
        m_dict = m.as_dict()
        if idx < len(warp_paths):
            m_dict["warp_path"] = warp_paths[idx]
        matches_data.append(m_dict)

    matches = [MatchResponse(**m) for m in matches_data]

    cached_data = {
        "total": result.total,
        "elapsed_ms": result.elapsed_ms,
        "mode": request.mode,
        "timeframe": request.timeframe,
        "query_vector": query_vector.tolist() if hasattr(query_vector, "tolist") else list(query_vector),
        "matches": [m.model_dump() for m in matches],
    }

    await cache.set(f"search:{search_id}", json.dumps(cached_data).encode("utf-8"), SEARCH_TTL)

    return SearchResponse(
        search_id=search_id,
        total=result.total,
        elapsed_ms=result.elapsed_ms,
        data_as_of=int(time.time()),
        stale_warning=False,
        results=matches[: request.limit],
        session=session_info,
    )


@app.get("/api/search/{search_id}", response_model=SearchResponse)
async def get_search(
    search_id: str,
    offset: int = 0,
    limit: int = 12,
    session_id: str = Depends(get_session_id),
):
    cache = get_cache()
    session_info = await track_session(session_id)

    data = await cache.get(f"search:{search_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Search not found or expired")

    parsed = json.loads(data)
    matches = [MatchResponse(**m) for m in parsed["matches"][offset : offset + limit]]

    return SearchResponse(
        search_id=search_id,
        total=parsed["total"],
        elapsed_ms=parsed["elapsed_ms"],
        data_as_of=int(time.time()),
        stale_warning=False,
        results=matches,
        session=session_info,
    )


@app.get("/api/search/{search_id}/stats", response_model=OutcomeResponse)
async def get_search_stats(
    search_id: str,
    session_id: str = Depends(get_session_id),
):
    import numpy as np
    cache = get_cache()
    await track_session(session_id)

    cached_stats = await cache.get(f"search:{search_id}:stats")
    if cached_stats:
        return OutcomeResponse(**json.loads(cached_stats))

    data = await cache.get(f"search:{search_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Search not found or expired")

    parsed = json.loads(data)
    timeframe = parsed.get("timeframe", "4h")
    query_vector = np.array(parsed.get("query_vector", []))
    if query_vector.size == 0:
        raise HTTPException(status_code=400, detail="Cached query vector missing")

    engine = get_engine()
    store = get_store(timeframe)
    pools = get_pools(timeframe)

    direction = "long"
    outcome = run_template(
        engine,
        "search_query",
        query_vector,
        store,
        pools,
        timeframe=timeframe,
        direction=direction,
        limit=1000,
    )

    configs_resp = {}
    for cfg_name, stats in outcome.stats.items():
        configs_resp[cfg_name] = to_outcome_config(stats)

    res = OutcomeResponse(
        configs=configs_resp,
        disclaimer="Geçmiş performans gelecekteki sonuçların garantisi değildir. İstatistiksel bulgular yalnızca bilgilendirme amaçlıdır.",
        direction=direction,
    )
    await cache.set(f"search:{search_id}:stats", json.dumps(res.model_dump()).encode("utf-8"), OUTCOME_TTL)
    return res


@app.get("/api/templates", response_model=list[TemplateResponse])
async def get_templates():
    templates = load_all_templates()
    return [
        TemplateResponse(
            id=t_id,
            name=t.name_tr,
            category=t.category,
            vector=t.vector.tolist() if hasattr(t.vector, "tolist") else t.vector,
            bias=t.bias,
        )
        for t_id, t in templates.items()
    ]


@app.get("/api/chart/{symbol}", response_model=ChartResponse)
async def get_chart(symbol: str, start: int = 0, end: int = 0, timeframe: str = "4h"):
    store = get_store(timeframe)
    sid = None
    for sym_id, name in get_engine().symbols.items():
        if name.upper() == symbol.upper():
            sid = sym_id
            break

    if sid is None or sid not in store.offset:
        return ChartResponse(
            ohlcv=[],
            highlight_start=start,
            highlight_end=end,
            blueprint_overlay=[],
            warp_amount=None,
        )

    s_idx = max(0, start)
    e_idx = min(store.close.size - 1, end) if end > 0 else min(store.close.size - 1, start + 100)

    ohlcv = []
    for i in range(s_idx, e_idx + 1):
        ohlcv.append(
            {
                "time": int(store.time[i]) if hasattr(store, "time") else i * 86400000,
                "open": float(store.open[i]),
                "high": float(store.high[i]),
                "low": float(store.low[i]),
                "close": float(store.close[i]),
                "volume": 0.0,
            }
        )

    return ChartResponse(
        ohlcv=ohlcv,
        highlight_start=start,
        highlight_end=end,
        blueprint_overlay=[],
        warp_amount=None,
    )


@app.get("/api/findings", response_model=FindingsResponse)
async def get_findings():
    stages = [
        {"stage": "F4 (Ham Triple-Barrier)", "significant": 13, "total": 26, "desc": "Zaman aşımı ve fiyat bariyerleri"},
        {
            "stage": "F4.5 (Aylık Blok Bootstrap)",
            "significant": 8,
            "total": 26,
            "desc": "Korelasyonlu bar çakışmalarının düzeltilmesi",
        },
        {
            "stage": "F4.5 (Bonferroni Çoğul Test)",
            "significant": 14,
            "total": 52,
            "desc": "Long ve short yönde aile bazlı düzeltme",
        },
        {
            "stage": "F4.6 (Ön-Getiri Eşleştirmeli Gölge)",
            "significant": 2,
            "total": 52,
            "desc": "Momentum tersine dönüşü vekillerinin elenmesi",
        },
    ]
    full_table = []
    try:
        f46_file = DATA_DIR / "f3" / "f46_raw.json"
        if f46_file.exists():
            with open(f46_file, "r", encoding="utf-8") as f:
                full_table = json.load(f)
    except Exception:
        pass

    return FindingsResponse(
        stages=stages,
        full_table=full_table,
        methodology="F4.5/F4.6 — Aylık kesitsel likidite filtresi, blok bootstrap (takvim ayı), Bonferroni çoğul test düzeltmesi (m=52) ve F4.6 ön-getiri eşleştirmeli gölge dağılımı (±0.25σ).",
    )
