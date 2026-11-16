from __future__ import annotations

import time
from typing import Any, Dict, Optional
from fastapi import APIRouter

from app.core.config import settings
from app.llm.client import get_llm_provider

router = APIRouter()

_LLM_HEALTH_CACHE: Optional[Dict[str, Any]] = None
_LLM_HEALTH_TIMESTAMP: float = 0.0
_LLM_HEALTH_TTL_SECONDS: float = 10.0


@router.get("/health")
async def health_check() -> dict:
    """Service health check endpoint including local LLM provider status with TTL caching."""
    global _LLM_HEALTH_CACHE, _LLM_HEALTH_TIMESTAMP

    now = time.monotonic()
    if _LLM_HEALTH_CACHE is not None and (now - _LLM_HEALTH_TIMESTAMP) < _LLM_HEALTH_TTL_SECONDS:
        llm_health = _LLM_HEALTH_CACHE
    else:
        llm = get_llm_provider()
        llm_health = await llm.health_check()
        _LLM_HEALTH_CACHE = llm_health
        _LLM_HEALTH_TIMESTAMP = now

    from app.workers.queue import analysis_queue
    return {
        "status": "ok",
        "version": settings.app_version,
        "environment": settings.app_env,
        "llm": llm_health,
        "queue": analysis_queue.get_status(),
    }
