from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

class SearchRequest(BaseModel):
    points: list[float] | None = None
    template_id: str | None = None
    mode: Literal["historical", "live"] = "historical"
    timeframe: Literal["4h", "1d"] = "4h"
    window_lengths: list[int] = Field(default_factory=lambda: [24, 40, 64, 100])
    tolerance: Literal["strict", "medium", "flexible"] = "medium"
    min_amplitude: float | None = None
    limit: int = 12

class MatchResponse(BaseModel):
    symbol: str
    symbol_id: int
    timeframe: str
    window_length: int
    start_idx: int
    end_idx: int
    end_time: int
    score: float
    distance: float
    amplitude: float
    atr: float
    percentile: float
    warp_path: list[list[int]] | None = None

class SessionInfo(BaseModel):
    session_queries: int
    multiple_comparison_warning: bool
    adjusted_alpha: float

class SearchResponse(BaseModel):
    search_id: str
    total: int
    elapsed_ms: float
    data_as_of: int
    stale_warning: bool
    results: list[MatchResponse]
    session: SessionInfo

class StatEnvelope(BaseModel):
    """Her sayısal istatistik bu zarfla dönülür, yalın float yasaktır."""
    value: float
    ci95: list[float]
    ci_method: str
    null: float | None
    shadow: float | None
    n_events: int
    n_months: int
    significant: bool
    verdict: str
    design_effect: float | None

class OutcomeConfigResponse(BaseModel):
    config: str
    expectancy: StatEnvelope
    win_rate: StatEnvelope
    edge: StatEnvelope | None
    outcomes: dict[str, int]
    truncated: int
    by_regime: list[dict]

class OutcomeResponse(BaseModel):
    configs: dict[str, OutcomeConfigResponse]
    disclaimer: str
    direction: str

class ChartResponse(BaseModel):
    ohlcv: list[dict]
    highlight_start: int
    highlight_end: int
    blueprint_overlay: list[dict]
    warp_amount: float | None

class TemplateResponse(BaseModel):
    id: str
    name: str
    category: str
    vector: list[float]
    bias: str | None

class FindingsResponse(BaseModel):
    stages: list[dict]
    full_table: list[dict]
    methodology: str
