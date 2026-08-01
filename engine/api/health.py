from __future__ import annotations

import json
import os
import time
from typing import Any

from fastapi import APIRouter
from engine.config import INGEST_STATE_FILE, MATRIX_DIR

router = APIRouter()

def _get_staleness() -> dict[str, Any]:
    try:
        if INGEST_STATE_FILE.exists():
            with open(INGEST_STATE_FILE, "r") as f:
                state = json.load(f)
            
            return {
                "freshness": state.get("last_update", 0),
                "stale_warning": False, # Would be calculated based on MAX_STALENESS_BARS
            }
    except Exception:
        pass
    
    return {
        "freshness": 0,
        "stale_warning": True
    }


@router.get("/health")
async def health_check() -> dict[str, Any]:
    staleness = _get_staleness()
    
    return {
        "status": "ok",
        "data_freshness": staleness["freshness"],
        "matrix_version": "v1", # Adjust as needed
        "last_cron_time": 0,
        "stale_warning": staleness["stale_warning"]
    }
