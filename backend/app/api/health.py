from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """Service health check endpoint."""
    return {
        "status": "ok",
        "version": settings.app_version,
        "environment": settings.app_env,
    }
