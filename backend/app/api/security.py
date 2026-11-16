from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.finding import Finding
from app.models.remediation_run import RemediationRun
from app.models.repository import Repository
from app.models.review import Review
from app.schemas.finding import FindingListResponse, FindingResponse, SecuritySummaryResponse

router = APIRouter(tags=["security"])


@router.get("/security/summary", response_model=SecuritySummaryResponse)
async def get_security_summary(
    db: AsyncSession = Depends(get_db),
) -> SecuritySummaryResponse:
    """Return an aggregated security overview calculated from database records."""
    # Count open findings by severity
    crit_q = select(func.count()).select_from(Finding).where(Finding.severity == "critical", Finding.status == "open")
    high_q = select(func.count()).select_from(Finding).where(Finding.severity == "high", Finding.status == "open")
    med_q = select(func.count()).select_from(Finding).where(Finding.severity == "medium", Finding.status == "open")
    low_q = select(func.count()).select_from(Finding).where(Finding.severity == "low", Finding.status == "open")
    open_q = select(func.count()).select_from(Finding).where(Finding.status == "open")
    resolved_q = select(func.count()).select_from(Finding).where(Finding.status == "resolved")

    # Repositories count
    repos_q = select(func.count()).select_from(Repository)

    # Average security score from completed reviews
    score_q = select(func.avg(Review.security_score)).where(Review.security_score.isnot(None))

    crit_count = (await db.execute(crit_q)).scalar() or 0
    high_count = (await db.execute(high_q)).scalar() or 0
    med_count = (await db.execute(med_q)).scalar() or 0
    low_count = (await db.execute(low_q)).scalar() or 0
    open_count = (await db.execute(open_q)).scalar() or 0
    resolved_count = (await db.execute(resolved_q)).scalar() or 0
    repos_count = (await db.execute(repos_q)).scalar() or 0
    avg_score = (await db.execute(score_q)).scalar()

    overall_score = round(float(avg_score), 1) if avg_score is not None else None

    # Remediation stats
    remediation_runs_count = 0
    verification_success_rate = None
    try:
        total_rem_q = select(func.count()).select_from(RemediationRun)
        remediation_runs_count = (await db.execute(total_rem_q)).scalar() or 0

        if remediation_runs_count > 0:
            verified_q = select(func.count()).select_from(RemediationRun).where(
                (RemediationRun.gate_5_decision == "RESOLVED") | (RemediationRun.verification_status == "resolved")
            )
            verified_count = (await db.execute(verified_q)).scalar() or 0
            verification_success_rate = round((verified_count / remediation_runs_count) * 100, 1)
    except Exception:
        pass

    return SecuritySummaryResponse(
        overall_score=overall_score,
        critical_count=crit_count,
        high_count=high_count,
        medium_count=med_count,
        low_count=low_count,
        resolved_count=resolved_count,
        open_count=open_count,
        repositories_analyzed=repos_count,
        remediation_runs_count=remediation_runs_count,
        verification_success_rate=verification_success_rate,
    )


@router.get("/security/findings", response_model=FindingListResponse)
async def list_findings(
    severity: Optional[str] = Query(None, description="Filter by severity"),
    category: Optional[str] = Query(None, description="Filter by category"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> FindingListResponse:
    """Return paginated findings from database."""
    query = select(Finding)
    count_query = select(func.count()).select_from(Finding)

    if severity:
        query = query.where(Finding.severity == severity)
        count_query = count_query.where(Finding.severity == severity)
    if category:
        query = query.where(Finding.category == category)
        count_query = count_query.where(Finding.category == category)
    if status:
        query = query.where(Finding.status == status)
        count_query = count_query.where(Finding.status == status)

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(Finding.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    items = list(result.scalars().all())

    return FindingListResponse(
        items=[FindingResponse.model_validate(f) for f in items],
        total=total,
    )
