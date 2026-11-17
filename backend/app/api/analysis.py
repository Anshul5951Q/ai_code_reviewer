"""
Analysis API endpoints.

Exposes:
    POST   /reviews/{review_id}/analyze      — start or resume ingestion
    GET    /reviews/{review_id}/analysis     — get current job status
    GET    /reviews/{review_id}/snapshot     — get completed snapshot
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import get_db, get_session_maker
from app.models.analysis_job import AnalysisJob
from app.models.repository_snapshot import RepositorySnapshot
from app.models.review import Review
from app.schemas.analysis import AnalysisJobResponse, StartAnalysisResponse
from app.schemas.snapshot import RepositorySnapshotResponse
from app.workers.queue import analysis_queue

router = APIRouter(tags=["Analysis"])


@router.post(
    "/reviews/{review_id}/analyze",
    response_model=StartAnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_analysis(
    review_id: str,
    wait: bool = Query(False, description="Whether to wait synchronously for analysis completion"),
    force: bool = Query(False, description="Force restart analysis even if existing job is completed or stale"),
    db: AsyncSession = Depends(get_db),
    maker: async_sessionmaker = Depends(get_session_maker),
) -> StartAnalysisResponse:
    """
    Start or resume end-to-end repository ingestion and multi-agent code analysis for a review.

    Idempotent: if an active job already exists for this review,
    returns its status instead of creating a duplicate, unless force=True or job is dead.
    """
    from app.workers.review_worker import is_job_active

    # Verify review exists
    review_res = await db.execute(select(Review).where(Review.id == review_id))
    review = review_res.scalar_one_or_none()
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review '{review_id}' not found.",
        )

    # Check for existing active job
    existing_res = await db.execute(
        select(AnalysisJob)
        .where(AnalysisJob.review_id == review_id)
        .order_by(AnalysisJob.created_at.desc())
    )
    existing_job = existing_res.scalars().first()

    if existing_job is not None and existing_job.is_active:
        if force:
            # Force restart: always mark existing job as superseded
            existing_job.status = "failed"
            existing_job.error = "Superceded by forced restart."
            existing_job.completed_at = datetime.now(timezone.utc)
            await db.commit()
        elif is_job_active(existing_job.id):
            # Job is genuinely active in the worker process
            return StartAnalysisResponse(
                job_id=existing_job.id,
                review_id=review_id,
                status=existing_job.status,
                message="Analysis already in progress.",
            )
        elif existing_job.status == "queued":
            # Queued but not yet picked up by worker — treat as active (idempotent)
            return StartAnalysisResponse(
                job_id=existing_job.id,
                review_id=review_id,
                status=existing_job.status,
                message="Analysis already in progress (queued).",
            )
        else:
            # Job is in analyzing/ingesting state but not registered in worker — zombie
            existing_job.status = "failed"
            existing_job.error = "Analysis interrupted by server restart."
            existing_job.completed_at = datetime.now(timezone.utc)
            await db.commit()

    if existing_job is not None and existing_job.status in ("completed", "partially_completed") and not force:
        return StartAnalysisResponse(
            job_id=existing_job.id,
            review_id=review_id,
            status=existing_job.status,
            message="Analysis already completed. View snapshot and findings for results.",
        )

    # Create new job
    job = AnalysisJob(
        id=str(uuid.uuid4()),
        review_id=review_id,
        status="queued",
        current_stage="PENDING",
        progress=0.0,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # If synchronous execution requested
    if wait:
        try:
            from app.workers.review_worker import resolve_worker_github_service
            from app.analysis.ingestion import IngestionPipeline
            from app.agents.orchestrator import AnalysisOrchestrator

            gh_service = await resolve_worker_github_service(maker, job.id)
            ingested_files = None

            # 1. Ingestion if snapshot not yet present
            snap_res = await db.execute(
                select(RepositorySnapshot).where(RepositorySnapshot.review_id == review_id)
            )
            if snap_res.scalar_one_or_none() is None:
                pipeline = IngestionPipeline(github_service=gh_service)
                ingested_files = await pipeline.run(job_id=job.id, session_maker=maker)

            # 2. Multi-agent review orchestrator
            orchestrator = AnalysisOrchestrator(github_service=gh_service)
            await orchestrator.run(
                review_id=review_id, session_maker=maker, job_id=job.id, files=ingested_files
            )

            await db.refresh(job)
            return StartAnalysisResponse(
                job_id=job.id,
                review_id=review_id,
                status=job.status,
                message="Analysis completed successfully.",
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Analysis orchestrator failed: {str(exc)}",
            )

    # Enqueue for background worker
    await analysis_queue.enqueue(job.id)

    return StartAnalysisResponse(
        job_id=job.id,
        review_id=review_id,
        status="queued",
        message="Analysis job queued. Poll /analysis for progress.",
    )


@router.get(
    "/reviews/{review_id}/analysis",
    response_model=AnalysisJobResponse,
)
async def get_analysis_status(
    review_id: str,
    db: AsyncSession = Depends(get_db),
) -> AnalysisJobResponse:
    """
    Get the current analysis job status for a review.

    Returns the most recent job. Poll this endpoint for progress updates.
    """
    review_res = await db.execute(select(Review).where(Review.id == review_id))
    if review_res.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review '{review_id}' not found.",
        )

    job_res = await db.execute(
        select(AnalysisJob)
        .where(AnalysisJob.review_id == review_id)
        .order_by(AnalysisJob.created_at.desc())
    )
    job = job_res.scalars().first()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No analysis job found for review '{review_id}'. Call POST /analyze first.",
        )

    return AnalysisJobResponse.model_validate(job)


@router.get(
    "/reviews/{review_id}/snapshot",
    response_model=RepositorySnapshotResponse,
)
async def get_review_snapshot(
    review_id: str,
    db: AsyncSession = Depends(get_db),
) -> RepositorySnapshotResponse:
    """
    Get the completed repository snapshot for a review.

    Only available after ingestion completes successfully.
    """
    review_res = await db.execute(select(Review).where(Review.id == review_id))
    if review_res.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review '{review_id}' not found.",
        )

    snap_res = await db.execute(
        select(RepositorySnapshot).where(RepositorySnapshot.review_id == review_id)
    )
    snapshot = snap_res.scalar_one_or_none()
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No snapshot available for review '{review_id}'. "
                "Analysis may not have completed yet."
            ),
        )

    return RepositorySnapshotResponse.model_validate(snapshot)
