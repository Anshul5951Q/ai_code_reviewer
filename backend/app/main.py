from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    agents,
    analysis,
    github,
    health,
    remediations,
    repositories,
    reviews,
    security,
)
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import close_db, init_db
from app.services.github import (
    GitHubAuthError,
    GitHubError,
    GitHubRateLimitError,
    GitHubResourceNotFoundError,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan — startup and shutdown logic."""
    configure_logging()
    await init_db()

    # Connect Redis queue and recover any queued jobs from previous runs
    from app.workers.queue import analysis_queue
    await analysis_queue.connect_redis(settings.redis_url)
    await analysis_queue.recover_from_redis()

    # Start background worker
    from app.db.session import async_session_maker
    from app.workers.review_worker import start_worker, stop_worker
    await start_worker(
        session_maker=async_session_maker,
        max_concurrent=settings.max_concurrent_ingestion_jobs,
    )

    yield

    # Shutdown: stop worker then close Redis
    await stop_worker()
    await analysis_queue.close()
    await close_db()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "AI-powered code review and security analysis platform. "
            "Phase 1: Foundation API."
        ),
        docs_url=f"{settings.api_prefix}/docs",
        redoc_url=f"{settings.api_prefix}/redoc",
        openapi_url=f"{settings.api_prefix}/openapi.json",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(health.router, prefix=settings.api_prefix, tags=["Health"])
    app.include_router(github.router, prefix=settings.api_prefix)
    app.include_router(
        repositories.router,
        prefix=settings.api_prefix,
        tags=["Repositories"],
    )
    app.include_router(reviews.router, prefix=settings.api_prefix, tags=["Reviews"])
    app.include_router(
        analysis.router, prefix=settings.api_prefix, tags=["Analysis"]
    )
    app.include_router(
        agents.router, prefix=settings.api_prefix, tags=["Multi-Agent Analysis"]
    )
    app.include_router(
        remediations.router, prefix=settings.api_prefix, tags=["AI Remediation & Verification"]
    )
    app.include_router(
        security.router, prefix=settings.api_prefix, tags=["Security"]
    )

    # Exception Handlers
    @app.exception_handler(GitHubRateLimitError)
    async def github_rate_limit_handler(request: Request, exc: GitHubRateLimitError):
        return JSONResponse(status_code=429, content={"detail": str(exc)})

    @app.exception_handler(GitHubAuthError)
    async def github_auth_handler(request: Request, exc: GitHubAuthError):
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    @app.exception_handler(GitHubResourceNotFoundError)
    async def github_not_found_handler(request: Request, exc: GitHubResourceNotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(GitHubError)
    async def github_generic_handler(request: Request, exc: GitHubError):
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    return app


app = create_app()
