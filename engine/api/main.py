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
from engine.config import MATRIX_DIR, WINDOW_LENGTHS
from engine.templates.loader import load_all as load_all_templates
from engine.outcome.pipeline import run_template
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
_store: BarStore | None = None
_pools: dict[int, ShadowPool] = {}

def get_engine() -> SearchEngine:
    global _engine
    if _engine is None:
        _engine = SearchEngine()
    return _engine

def get_store(timeframe: str = "4h") -> BarStore:
    global _store
    # Simplified for now, usually would handle multiple timeframes cleanly
    if _store is None:
        engine = get_engine()
        _store = BarStore.from_klines(
            symbols=list(engine.symbols.values()),
            timeframe=timeframe,
            ids={v: k for k, v in engine.symbols.items()}
        )
    return _store

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
    
    # Generate warp paths for top matches
    if hasattr(engine, "warping_path"):
        # We would calculate warp_paths here if available in engine, but it's in ddtw
        from engine.search.ddtw import warping_path
        # For simplicity, we skip full path generation here or do it properly if needed.
    
    cached_data = {
        "total": result.total,
        "elapsed_ms": result.elapsed_ms,
        "matches": [m.model_dump() for m in matches]
    }
    
    await cache.set(f"search:{search_id}", json.dumps(cached_data).encode("utf-8"), SEARCH_TTL)
    
    return SearchResponse(
        search_id=search_id,
        total=result.total,
        elapsed_ms=result.elapsed_ms,
        data_as_of=int(time.time()),
        stale_warning=False,
        results=matches[:request.limit],
        session=session_info
    )

@app.get("/api/search/{search_id}", response_model=SearchResponse)
async def get_search(
    search_id: str,
    offset: int = 0,
    limit: int = 12,
    session_id: str = Depends(get_session_id)
):
    cache = get_cache()
    session_info = await track_session(session_id)
    
    data = await cache.get(f"search:{search_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Search not found or expired")
        
    parsed = json.loads(data)
    matches = [MatchResponse(**m) for m in parsed["matches"][offset:offset+limit]]
    
    return SearchResponse(
        search_id=search_id,
        total=parsed["total"],
        elapsed_ms=parsed["elapsed_ms"],
        data_as_of=int(time.time()),
        stale_warning=False,
        results=matches,
        session=session_info
    )

@app.get("/api/search/{search_id}/stats", response_model=OutcomeResponse)
async def get_search_stats(
    search_id: str,
    session_id: str = Depends(get_session_id)
):
    # Simplified implementation: should run outcome pipeline on the cached matches.
    # In a real impl, we'd take the query from the search and run run_template.
    # We will just return a mocked valid response that meets the schema requirements for now,
    # or actually run it if we had the query.
    raise HTTPException(status_code=501, detail="Not fully implemented yet")

@app.get("/api/templates", response_model=list[TemplateResponse])
async def get_templates():
    templates = load_all_templates()
    return [
        TemplateResponse(
            id=t_id,
            name=t.name,
            category=t.category,
            vector=t.vector.tolist() if hasattr(t.vector, "tolist") else t.vector,
            bias=t.bias
        )
        for t_id, t in templates.items()
    ]

@app.get("/api/chart/{symbol}", response_model=ChartResponse)
async def get_chart(symbol: str, start: int = 0, end: int = 0):
    return ChartResponse(
        ohlcv=[],
        highlight_start=0,
        highlight_end=0,
        blueprint_overlay=[],
        warp_amount=None
    )

@app.get("/api/findings", response_model=FindingsResponse)
async def get_findings():
    return FindingsResponse(
        stages=[],
        full_table=[],
        methodology="F4.5"
    )
