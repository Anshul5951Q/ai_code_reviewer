"""
REST API endpoints for Phase 6 AI Remediation and Independent Verification.
"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import async_session_maker, get_db, get_session_maker
from app.models.finding import Finding
from app.models.remediation_run import RemediationRun
from app.models.review import Review
from app.remediation.orchestrator import MAX_REMEDIATION_ATTEMPTS, RemediationOrchestrator
from app.schemas.remediation import (
    RemediationHistoryResponse,
    RemediationRequest,
    RemediationResultResponse,
    RemediationRunResponse,
    VerificationDetailResponse,
)

router = APIRouter(prefix="", tags=["AI Remediation & Verification"])


@router.post(
    "/findings/{finding_id}/remediate",
    response_model=RemediationRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def remediate_finding(
    finding_id: str,
    background_tasks: BackgroundTasks,
    payload: Optional[RemediationRequest] = None,
    wait: bool = Query(False, description="Wait synchronously for completion (primarily for tests)"),
    db: AsyncSession = Depends(get_db),
    maker: async_sessionmaker[AsyncSession] = Depends(get_session_maker),
) -> RemediationRunResponse:
    """
    Trigger automated AI remediation and independent verification for a finding.
    """
    # 1. Validate finding exists
    f_res = await db.execute(select(Finding).where(Finding.id == finding_id))
    finding = f_res.scalar_one_or_none()
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finding '{finding_id}' not found.",
        )

    # 2. Validate associated review
    rev_res = await db.execute(select(Review).where(Review.id == finding.review_id))
    review = rev_res.scalar_one_or_none()
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review for finding '{finding_id}' not found.",
        )

    # 3. Check if remediation already running for this finding
    active_statuses = ["queued", "generating", "patch_generated", "patch_validated", "verifying"]
    active_res = await db.execute(
        select(RemediationRun).where(
            RemediationRun.finding_id == finding_id,
            RemediationRun.status.in_(active_statuses),
        )
    )
    if active_res.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A remediation run is already in progress for finding '{finding_id}'.",
        )

    # 4. Check attempt count
    attempts_res = await db.execute(
        select(func.count(RemediationRun.id)).where(RemediationRun.finding_id == finding_id)
    )
    attempts = attempts_res.scalar() or 0
    if attempts >= MAX_REMEDIATION_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum remediation attempts ({MAX_REMEDIATION_ATTEMPTS}) reached for this finding.",
        )

    # 5. Create new RemediationRun
    run = RemediationRun(
        review_id=finding.review_id,
        finding_id=finding.id,
        status="queued",
        verification_status="not_started",
    )
    db.add(run)
    finding.status = "remediation_in_progress"
    await db.commit()
    await db.refresh(run)

    # 6. Execute via orchestrator
    orchestrator = RemediationOrchestrator()
    if wait:
        await orchestrator.run(remediation_id=run.id, session_maker=maker)
        await db.refresh(run)
    else:
        background_tasks.add_task(
            orchestrator.run,
            remediation_id=run.id,
            session_maker=maker,
        )

    return RemediationRunResponse.model_validate(run)


@router.get(
    "/remediations/{remediation_id}",
    response_model=RemediationRunResponse,
)
async def get_remediation(
    remediation_id: str,
    db: AsyncSession = Depends(get_db),
) -> RemediationRunResponse:
    """Return status and execution metrics for a remediation run."""
    run_res = await db.execute(
        select(RemediationRun).where(RemediationRun.id == remediation_id)
    )
    run = run_res.scalar_one_or_none()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Remediation run '{remediation_id}' not found.",
        )
    return RemediationRunResponse.model_validate(run)


@router.get(
    "/remediations/{remediation_id}/result",
    response_model=RemediationResultResponse,
)
async def get_remediation_result(
    remediation_id: str,
    db: AsyncSession = Depends(get_db),
) -> RemediationResultResponse:
    """Return proposed fix, unified diff, explanation, and verification state."""
    run_res = await db.execute(
        select(RemediationRun).where(RemediationRun.id == remediation_id)
    )
    run = run_res.scalar_one_or_none()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Remediation run '{remediation_id}' not found.",
        )

    meta = {}
    if run.metadata_json:
        try:
            meta = json.loads(run.metadata_json)
        except Exception:
            pass

    return RemediationResultResponse(
        id=run.id,
        finding_id=run.finding_id,
        status=run.status,
        strategy=meta.get("strategy"),
        explanation=meta.get("explanation"),
        changed_files=[c.get("file_path", "") for c in meta.get("changes", [])],
        diff=meta.get("diff"),
        verification_status=run.verification_status,
        confidence=meta.get("remediation_confidence"),
        verification_explanation=meta.get("verification_reason"),
        attempt_number=meta.get("attempt_number", 1),
    )


@router.get(
    "/remediations/{remediation_id}/verification",
    response_model=VerificationDetailResponse,
)
async def get_remediation_verification(
    remediation_id: str,
    db: AsyncSession = Depends(get_db),
) -> VerificationDetailResponse:
    """Return independent verification results for a remediation run."""
    run_res = await db.execute(
        select(RemediationRun).where(RemediationRun.id == remediation_id)
    )
    run = run_res.scalar_one_or_none()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Remediation run '{remediation_id}' not found.",
        )

    meta = {}
    if run.metadata_json:
        try:
            meta = json.loads(run.metadata_json)
        except Exception:
            pass

    return VerificationDetailResponse(
        status=run.verification_status,
        confidence=meta.get("verification_confidence", 0.9),
        reason=meta.get("verification_reason", "No verification details recorded."),
        remaining_risk=meta.get("remaining_risk"),
        new_findings=meta.get("new_findings", []),
        evidence=meta.get("verification_evidence", []),
    )


@router.get(
    "/findings/{finding_id}/remediations",
    response_model=RemediationHistoryResponse,
)
async def get_finding_remediations(
    finding_id: str,
    db: AsyncSession = Depends(get_db),
) -> RemediationHistoryResponse:
    """Return historical remediation attempts for a finding."""
    f_res = await db.execute(select(Finding).where(Finding.id == finding_id))
    if f_res.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finding '{finding_id}' not found.",
        )

    runs_res = await db.execute(
        select(RemediationRun)
        .where(RemediationRun.finding_id == finding_id)
        .order_by(RemediationRun.created_at.asc())
    )
    runs = list(runs_res.scalars().all())
    total_attempts = len(runs)
    can_retry = total_attempts < MAX_REMEDIATION_ATTEMPTS

    return RemediationHistoryResponse(
        runs=[RemediationRunResponse.model_validate(r) for r in runs],
        total_attempts=total_attempts,
        can_retry=can_retry,
    )
