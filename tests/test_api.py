from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from engine.api.main import app, wrap_stat
from engine.api.schemas import StatEnvelope, OutcomeConfigResponse
from engine.api.cache import InMemoryCache

client = TestClient(app)

@pytest.fixture(autouse=True)
def mock_cache():
    cache = InMemoryCache()
    with patch("engine.api.cache.get_cache", return_value=cache):
        yield cache

def test_stat_envelope_completeness():
    envelope = wrap_stat(
        val=1.5,
        ci=(1.0, 2.0),
        ci_method="bootstrap",
        null_val=0.0,
        n_events=100,
        n_months=12,
        significant=True,
        verdict="significant difference",
        design_effect=1.2
    )
    assert envelope.value == 1.5
    assert envelope.ci95 == [1.0, 2.0]
    assert envelope.ci_method == "bootstrap"
    assert envelope.null == 0.0
    assert envelope.n_events == 100
    assert envelope.n_months == 12
    assert envelope.significant is True
    assert envelope.verdict == "significant difference"
    assert envelope.design_effect == 1.2
    assert envelope.shadow is None

def test_stale_data_health():
    with patch("engine.api.health._get_staleness", return_value={"freshness": 100, "stale_warning": True}):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["stale_warning"] is True
        assert response.json()["data_freshness"] == 100

def test_session_counter():
    headers = {"X-Session-ID": "test-session-123"}
    
    # Needs a real engine mock to return SearchResult
    mock_result = MagicMock()
    mock_result.results = []
    mock_result.total = 0
    mock_result.elapsed_ms = 10.0
    
    with patch("engine.api.main.get_engine") as mock_engine:
        mock_engine.return_value.search.return_value = mock_result
        
        # Call 1
        resp1 = client.post("/api/search", json={"points": [1.0, 2.0]}, headers=headers)
        assert resp1.status_code == 200
        sess1 = resp1.json()["session"]
        assert sess1["session_queries"] == 1
        assert sess1["multiple_comparison_warning"] is False
        assert sess1["adjusted_alpha"] == 0.05
        
        # Call 2
        resp2 = client.post("/api/search", json={"points": [1.0, 2.0]}, headers=headers)
        assert resp2.status_code == 200
        sess2 = resp2.json()["session"]
        assert sess2["session_queries"] == 2
        assert sess2["multiple_comparison_warning"] is True
        assert sess2["adjusted_alpha"] == 0.025

def test_pagination_cache():
    headers = {"X-Session-ID": "test-session-pagi"}
    mock_result = MagicMock()
    # Create 20 mock matches
    mock_matches = []
    for i in range(20):
        m = MagicMock()
        m.as_dict.return_value = {
            "symbol": f"SYM{i}", "symbol_id": i, "timeframe": "4h",
            "window_length": 24, "start_idx": 0, "end_idx": 10,
            "end_time": 1000, "score": 0.9, "distance": 0.1,
            "amplitude": 10.0, "atr": 1.0, "percentile": 0.01,
            "warp_path": None
        }
        mock_matches.append(m)
        
    mock_result.results = mock_matches
    mock_result.total = 20
    mock_result.elapsed_ms = 5.0
    
    with patch("engine.api.main.get_engine") as mock_engine:
        mock_engine.return_value.search.return_value = mock_result
        
        # First request (creates search)
        resp1 = client.post("/api/search", json={"points": [1.0, 2.0]}, headers=headers)
        assert resp1.status_code == 200
        search_id = resp1.json()["search_id"]
        assert len(resp1.json()["results"]) == 12  # default limit
        
        # Second request (gets page 2)
        mock_engine.return_value.search.assert_called_once() # Reset call count checking
        mock_engine.return_value.search.reset_mock()
        
        resp2 = client.get(f"/api/search/{search_id}?offset=12&limit=12", headers=headers)
        assert resp2.status_code == 200
        assert len(resp2.json()["results"]) == 8
        assert resp2.json()["results"][0]["symbol"] == "SYM12"
        
        # Engine should NOT have been called again
        mock_engine.return_value.search.assert_not_called()

def test_significant_verdict():
    # CI contains zero
    env1 = wrap_stat(0.01, (-0.05, 0.07), "bootstrap", significant=False)
    assert env1.significant is False
    
    # CI strictly positive
    env2 = wrap_stat(0.05, (0.01, 0.09), "bootstrap", significant=True)
    assert env2.significant is True
