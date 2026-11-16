"""
API endpoints for Phase 5 Multi-Agent Analysis and Review Findings.

Exposes:
    POST /reviews/{review_id}/run       — start multi-agent analysis
    GET  /reviews/{review_id}/agents    — get agent execution runs
    GET  /reviews/{review_id}/findings  — get paginated review findings with filters
"""
from __future__ import annotations

import asyncio
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import AnalysisOrchestrator
from app.db.session import async_session_maker, get_db, get_session_maker
from app.models.agent_run import AgentRun
from app.models.correlated_finding import CorrelatedFinding
from app.models.finding import Finding
from app.models.finding_relationship import FindingRelationship
from app.models.repository_snapshot import RepositorySnapshot
from app.models.review import Review
from app.schemas.agent import (
    AgentRunListResponse,
    AgentRunResponse,
    GateAuditResponse,
    StartPhase5AnalysisResponse,
)
from app.schemas.finding import (
    CorrelatedFindingListResponse,
    CorrelatedFindingResponse,
    CorrelationStatusResponse,
    FindingListResponse,
    FindingRelationshipResponse,
    FindingResponse,
)

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
    Delegates to the unified analysis service to ensure shared execution logic,
    idempotency, and continuous 13-stage AnalysisJob lifecycle tracking.
    """
    from app.api.analysis import start_analysis

    # 1. Verify review exists
    review_res = await db.execute(select(Review).where(Review.id == review_id))
    review = review_res.scalar_one_or_none()
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review '{review_id}' not found.",
        )

    # 2. Verify repository snapshot exists (preserving backward-compatibility contract)
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

    # 4. Delegate to the unified analysis pipeline
    job_resp = await start_analysis(
        review_id=review_id,
        wait=wait,
        db=db,
        maker=maker,
    )

    return StartPhase5AnalysisResponse(
        review_id=review_id,
        status=job_resp.status,
        message=job_resp.message,
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


# ── Sub-Phase 7.3 Dedicated Endpoints & Verification Gates ─────────────────────

@router.get(
    "/{review_id}/agents/code-understanding",
    response_model=AgentRunResponse,
)
async def get_code_understanding_agent_endpoint(
    review_id: str,
    db: AsyncSession = Depends(get_db),
) -> AgentRunResponse:
    """Retrieve latest CodeUnderstandingAgent run for a review."""
    review_res = await db.execute(select(Review).where(Review.id == review_id))
    if review_res.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review '{review_id}' not found.",
        )

    run_res = await db.execute(
        select(AgentRun)
        .where(
            AgentRun.review_id == review_id,
            AgentRun.agent_type == "code_understanding",
        )
        .order_by(AgentRun.created_at.desc())
    )
    run_record = run_res.scalars().first()
    if run_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Code understanding agent run not found for review '{review_id}'.",
        )
    return AgentRunResponse.model_validate(run_record)


@router.post(
    "/{review_id}/agents/code-quality",
    response_model=AgentRunResponse,
    status_code=status.HTTP_200_OK,
)
async def run_code_quality_agent_endpoint(
    review_id: str,
    db: AsyncSession = Depends(get_db),
    maker: async_sessionmaker = Depends(get_session_maker),
) -> AgentRunResponse:
    """Run dedicated CodeQualityAgent and Gate 2 individually for a review."""
    review_res = await db.execute(select(Review).where(Review.id == review_id))
    if review_res.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review '{review_id}' not found.",
        )
    orchestrator = AnalysisOrchestrator()
    try:
        run_record = await orchestrator.run_code_quality(review_id=review_id, session_maker=maker)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Code quality agent execution failed: {exc}",
        )
    return AgentRunResponse.model_validate(run_record)


@router.get(
    "/{review_id}/agents/code-quality",
    response_model=AgentRunResponse,
)
async def get_code_quality_agent_endpoint(
    review_id: str,
    db: AsyncSession = Depends(get_db),
) -> AgentRunResponse:
    """Retrieve the latest CodeQualityAgent run for a review."""
    review_res = await db.execute(select(Review).where(Review.id == review_id))
    if review_res.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review '{review_id}' not found.",
        )

    run_res = await db.execute(
        select(AgentRun)
        .where(
            AgentRun.review_id == review_id,
            AgentRun.agent_type.in_(["code_quality", "code_review"]),
        )
        .order_by(AgentRun.created_at.desc())
    )
    run_record = run_res.scalars().first()
    if run_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Code quality agent run not found for review '{review_id}'.",
        )
    return AgentRunResponse.model_validate(run_record)


@router.post(
    "/{review_id}/agents/security",
    response_model=AgentRunResponse,
    status_code=status.HTTP_200_OK,
)
async def run_security_agent_endpoint(
    review_id: str,
    db: AsyncSession = Depends(get_db),
    maker: async_sessionmaker = Depends(get_session_maker),
) -> AgentRunResponse:
    """Run dedicated SecurityDetectionAgent and Gate 3 individually for a review."""
    review_res = await db.execute(select(Review).where(Review.id == review_id))
    if review_res.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review '{review_id}' not found.",
        )
    orchestrator = AnalysisOrchestrator()
    try:
        run_record = await orchestrator.run_security_detection(review_id=review_id, session_maker=maker)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Security agent execution failed: {exc}",
        )
    return AgentRunResponse.model_validate(run_record)


@router.get(
    "/{review_id}/agents/security",
    response_model=AgentRunResponse,
)
async def get_security_agent_endpoint(
    review_id: str,
    db: AsyncSession = Depends(get_db),
) -> AgentRunResponse:
    """Retrieve the latest SecurityDetectionAgent run for a review."""
    review_res = await db.execute(select(Review).where(Review.id == review_id))
    if review_res.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review '{review_id}' not found.",
        )

    run_res = await db.execute(
        select(AgentRun)
        .where(
            AgentRun.review_id == review_id,
            AgentRun.agent_type == "security_agent",
        )
        .order_by(AgentRun.created_at.desc())
    )
    run_record = run_res.scalars().first()
    if run_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Security agent run not found for review '{review_id}'.",
        )
    return AgentRunResponse.model_validate(run_record)


@router.get(
    "/{review_id}/findings/quality",
    response_model=FindingListResponse,
)
async def get_quality_findings_endpoint(
    review_id: str,
    severity: Optional[str] = Query(None, description="Filter by severity"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> FindingListResponse:
    """Retrieve validated code quality and maintainability findings."""
    review_res = await db.execute(select(Review).where(Review.id == review_id))
    if review_res.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review '{review_id}' not found.",
        )

    query = select(Finding).where(
        Finding.review_id == review_id,
        Finding.category.in_(["quality", "maintainability", "performance", "architecture"]),
    )
    if severity:
        query = query.where(Finding.severity == severity.lower())

    total_res = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_res.scalar() or 0

    query = query.order_by(Finding.start_line.asc()).limit(limit).offset(offset)
    findings_res = await db.execute(query)
    findings = list(findings_res.scalars().all())

    return FindingListResponse(
        items=[FindingResponse.model_validate(f) for f in findings],
        total=total,
    )


@router.get(
    "/{review_id}/findings/security",
    response_model=FindingListResponse,
)
async def get_security_findings_endpoint(
    review_id: str,
    severity: Optional[str] = Query(None, description="Filter by severity"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> FindingListResponse:
    """Retrieve validated security findings."""
    review_res = await db.execute(select(Review).where(Review.id == review_id))
    if review_res.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review '{review_id}' not found.",
        )

    query = select(Finding).where(
        Finding.review_id == review_id,
        Finding.category == "security",
    )
    if severity:
        query = query.where(Finding.severity == severity.lower())

    total_res = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_res.scalar() or 0

    query = query.order_by(Finding.start_line.asc()).limit(limit).offset(offset)
    findings_res = await db.execute(query)
    findings = list(findings_res.scalars().all())

    return FindingListResponse(
        items=[FindingResponse.model_validate(f) for f in findings],
        total=total,
    )


@router.get(
    "/{review_id}/gates",
    response_model=GateAuditResponse,
)
async def get_gates_audit_endpoint(
    review_id: str,
    db: AsyncSession = Depends(get_db),
) -> GateAuditResponse:
    """Retrieve verification gate audit metadata (Gate 1, Gate 2, Gate 3) for a review."""
    review_res = await db.execute(select(Review).where(Review.id == review_id))
    if review_res.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review '{review_id}' not found.",
        )

    runs_res = await db.execute(
        select(AgentRun).where(AgentRun.review_id == review_id)
    )
    runs = list(runs_res.scalars().all())

    gate_1 = None
    gate_2 = None
    gate_3 = None

    import json
    for r in runs:
        if not r.metadata_json:
            continue
        try:
            parsed = json.loads(r.metadata_json)
            if r.agent_type == "code_understanding" and "gate_1" in parsed:
                gate_1 = parsed["gate_1"]
            elif r.agent_type in ("code_quality", "code_review") and "gate_2" in parsed:
                gate_2 = parsed["gate_2"]
            elif r.agent_type == "security_agent" and "gate_3" in parsed:
                gate_3 = parsed["gate_3"]
        except Exception:
            pass

    return GateAuditResponse(
        review_id=review_id,
        gate_1=gate_1,
        gate_2=gate_2,
        gate_3=gate_3,
    )


# ── Sub-Phase 7.4 Finding Correlator Endpoints ─────────────────────────────────

@router.post(
    "/{review_id}/correlate",
    response_model=CorrelationStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def trigger_correlation_endpoint(
    review_id: str,
    db: AsyncSession = Depends(get_db),
    maker: async_sessionmaker = Depends(get_session_maker),
) -> CorrelationStatusResponse:
    """Trigger finding correlation independently on existing review findings."""
    review_res = await db.execute(select(Review).where(Review.id == review_id))
    if review_res.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review '{review_id}' not found.",
        )

    orchestrator = AnalysisOrchestrator()
    try:
        corr_meta = await orchestrator.run_correlation(review_id=review_id, session_maker=maker)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Finding correlation execution failed: {exc}",
        )

    return CorrelationStatusResponse(
        review_id=review_id,
        status=corr_meta.get("status", "completed"),
        total_raw_findings=corr_meta.get("total_input_findings", 0),
        correlated_clusters_count=corr_meta.get("correlated_clusters_count", 0),
        exact_duplicates_count=corr_meta.get("exact_duplicates_count", 0),
        overlapping_count=corr_meta.get("overlapping_count", 0),
        shared_root_cause_count=corr_meta.get("shared_root_cause_count", 0),
        independent_count=corr_meta.get("independent_count", 0),
        semantic_evaluated=corr_meta.get("semantic_evaluated", False),
        correlation_version="1.0",
    )


@router.get(
    "/{review_id}/correlation/status",
    response_model=CorrelationStatusResponse,
)
async def get_correlation_status_endpoint(
    review_id: str,
    db: AsyncSession = Depends(get_db),
) -> CorrelationStatusResponse:
    """Retrieve correlation status and metrics for a review."""
    review_res = await db.execute(select(Review).where(Review.id == review_id))
    if review_res.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review '{review_id}' not found.",
        )

    run_res = await db.execute(
        select(AgentRun)
        .where(
            AgentRun.review_id == review_id,
            AgentRun.agent_type == "finding_correlator",
        )
        .order_by(AgentRun.created_at.desc())
    )
    corr_run = run_res.scalars().first()

    if corr_run is None or not corr_run.metadata_json:
        # Check if raw findings exist
        f_count_res = await db.execute(
            select(func.count()).select_from(select(Finding).where(Finding.review_id == review_id).subquery())
        )
        raw_count = f_count_res.scalar() or 0
        return CorrelationStatusResponse(
            review_id=review_id,
            status="not_started" if raw_count > 0 else "pending",
            total_raw_findings=raw_count,
            correlated_clusters_count=0,
        )

    import json
    try:
        corr_meta = json.loads(corr_run.metadata_json)
    except Exception:
        corr_meta = {}

    return CorrelationStatusResponse(
        review_id=review_id,
        status=corr_run.status,
        total_raw_findings=corr_meta.get("total_input_findings", 0),
        correlated_clusters_count=corr_meta.get("correlated_clusters_count", 0),
        exact_duplicates_count=corr_meta.get("exact_duplicates_count", 0),
        overlapping_count=corr_meta.get("overlapping_count", 0),
        shared_root_cause_count=corr_meta.get("shared_root_cause_count", 0),
        independent_count=corr_meta.get("independent_count", 0),
        semantic_evaluated=corr_meta.get("semantic_evaluated", False),
        correlation_version="1.0",
    )


@router.get(
    "/{review_id}/correlated-findings",
    response_model=CorrelatedFindingListResponse,
)
async def get_correlated_findings_endpoint(
    review_id: str,
    severity: Optional[str] = Query(None, description="Filter by severity"),
    category: Optional[str] = Query(None, description="Filter by category"),
    relationship_type: Optional[str] = Query(None, description="Filter by relationship type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> CorrelatedFindingListResponse:
    """Retrieve paginated unified correlated findings with filters."""
    review_res = await db.execute(select(Review).where(Review.id == review_id))
    if review_res.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review '{review_id}' not found.",
        )

    # Retrieve the latest completed correlation version for this review to surface the active correlation
    version_res = await db.execute(
        select(CorrelatedFinding.correlation_version)
        .where(CorrelatedFinding.review_id == review_id)
        .order_by(CorrelatedFinding.correlation_version.desc(), CorrelatedFinding.created_at.desc())
        .limit(1)
    )
    latest_version = version_res.scalar_one_or_none()

    query = select(CorrelatedFinding).where(CorrelatedFinding.review_id == review_id)
    if latest_version:
        query = query.where(CorrelatedFinding.correlation_version == latest_version)

    if severity:
        query = query.where(CorrelatedFinding.severity == severity.lower())
    if category:
        query = query.where(CorrelatedFinding.category == category.lower())
    if relationship_type:
        query = query.join(
            FindingRelationship,
            FindingRelationship.correlated_finding_id == CorrelatedFinding.id,
        ).where(FindingRelationship.relationship_type == relationship_type.lower())

    total_res = await db.execute(select(func.count()).select_from(query.distinct().subquery()))
    total = total_res.scalar() or 0

    query = query.order_by(CorrelatedFinding.created_at.asc()).limit(limit).offset(offset)
    res = await db.execute(query)
    correlated = list(res.scalars().all())

    return CorrelatedFindingListResponse(
        items=[CorrelatedFindingResponse.model_validate(cf) for cf in correlated],
        total=total,
    )


@router.get(
    "/{review_id}/correlated-findings/{finding_id}",
    response_model=CorrelatedFindingResponse,
)
async def get_single_correlated_finding_endpoint(
    review_id: str,
    finding_id: str,
    db: AsyncSession = Depends(get_db),
) -> CorrelatedFindingResponse:
    """Retrieve an individual correlated finding and its constituent relationships."""
    review_res = await db.execute(select(Review).where(Review.id == review_id))
    if review_res.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review '{review_id}' not found.",
        )

    cf_res = await db.execute(
        select(CorrelatedFinding).where(
            CorrelatedFinding.review_id == review_id,
            CorrelatedFinding.id == finding_id,
        )
    )
    cf = cf_res.scalar_one_or_none()
    if cf is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Correlated finding '{finding_id}' not found.",
        )

    return CorrelatedFindingResponse.model_validate(cf)


@router.get(
    "/{review_id}/correlated-findings/{finding_id}/relationships",
    response_model=List[FindingRelationshipResponse],
)
async def get_correlated_finding_relationships_endpoint(
    review_id: str,
    finding_id: str,
    db: AsyncSession = Depends(get_db),
) -> List[FindingRelationshipResponse]:
    """Retrieve all constituent relationships for a correlated finding."""
    review_res = await db.execute(select(Review).where(Review.id == review_id))
    if review_res.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review '{review_id}' not found.",
        )

    rel_res = await db.execute(
        select(FindingRelationship)
        .where(FindingRelationship.correlated_finding_id == finding_id)
        .order_by(FindingRelationship.created_at.asc())
    )
    relationships = list(rel_res.scalars().all())
    return [FindingRelationshipResponse.model_validate(r) for r in relationships]

