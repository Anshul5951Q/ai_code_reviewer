"""
API endpoints for Phase 5 Multi-Agent Analysis and Review Findings.

Exposes:
    POST /reviews/{review_id}/run       — start multi-agent analysis
    GET  /reviews/{review_id}/agents    — get agent execution runs
    GET  /reviews/{review_id}/findings  — get paginated review findings with filters
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import AnalysisOrchestrator
from app.db.session import async_session_maker, get_db, get_session_maker
from app.models.agent_run import AgentRun
from app.models.finding import Finding
from app.models.repository_snapshot import RepositorySnapshot
from app.models.review import Review
from app.schemas.agent import (
    AgentRunListResponse,
    AgentRunResponse,
    StartPhase5AnalysisResponse,
)
from app.schemas.finding import FindingListResponse, FindingResponse

router = APIRouter(prefix="/reviews", tags=["Multi-Agent Analysis"])


@router.post(
    "/{review_id}/run",
    response_model=StartPhase5AnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_review_analysis(
    review_id: str,
    background_tasks: BackgroundTasks,
    wait: bool = Query(False, description="Whether to await analysis completion synchronously"),
    db: AsyncSession = Depends(get_db),
    maker: async_sessionmaker = Depends(get_session_maker),
) -> StartPhase5AnalysisResponse:
    """
    Start multi-agent code analysis (Understanding, Code Review, Security) on a review.
    Requires an existing repository snapshot from Phase 3 ingestion.
    """
    # 1. Verify review exists
    review_res = await db.execute(select(Review).where(Review.id == review_id))
    review = review_res.scalar_one_or_none()
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review '{review_id}' not found.",
        )

    # 2. Verify repository snapshot exists
    snap_res = await db.execute(
        select(RepositorySnapshot).where(RepositorySnapshot.review_id == review_id)
    )
    snapshot = snap_res.scalar_one_or_none()
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository snapshot not found for this review. Ingestion must run first.",
        )

    # 3. Check if analysis is already running
    if review.status == "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Analysis is already in progress for this review.",
        )

    # Mark as running immediately
    review.status = "running"
    await db.commit()

    orchestrator = AnalysisOrchestrator()

    if wait:
        try:
            await orchestrator.run(review_id=review_id, session_maker=maker)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Analysis orchestrator failed: {exc}",
            )
        return StartPhase5AnalysisResponse(
            review_id=review_id,
            status="completed",
            message="Multi-agent analysis completed successfully.",
        )
    else:
        # Run asynchronously in background
        background_tasks.add_task(
            orchestrator.run,
            review_id=review_id,
            session_maker=maker,
        )
        return StartPhase5AnalysisResponse(
            review_id=review_id,
            status="running",
            message="Multi-agent analysis started in background. Poll /agents for status.",
        )


@router.get(
    "/{review_id}/agents",
    response_model=AgentRunListResponse,
)
async def get_review_agents(
    review_id: str,
    db: AsyncSession = Depends(get_db),
) -> AgentRunListResponse:
    """Return execution status of all analysis agents for a review."""
    review_res = await db.execute(select(Review).where(Review.id == review_id))
    if review_res.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review '{review_id}' not found.",
        )

    runs_res = await db.execute(
        select(AgentRun)
        .where(AgentRun.review_id == review_id)
        .order_by(AgentRun.created_at.asc())
    )
    runs = list(runs_res.scalars().all())

    return AgentRunListResponse(
        agents=[AgentRunResponse.model_validate(r) for r in runs]
    )
