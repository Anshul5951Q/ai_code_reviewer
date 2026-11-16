"""
REST API endpoints for AI Remediation, Gate 4 Patch Verification, and Risk Assessment.
"""
from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import async_session_maker, get_db, get_session_maker
from app.models.correlated_finding import CorrelatedFinding
from app.models.finding import Finding
from app.models.remediation_run import RemediationRun
from app.models.review import Review
from app.remediation.orchestrator import MAX_REMEDIATION_ATTEMPTS, RemediationOrchestrator
from app.schemas.remediation import (
    BatchRemediationRequest,
    BatchRemediationResponse,
    Gate4AuditReport,
    Gate4CheckResult,
    PatchRiskAssessment,
    RemediationHistoryResponse,
    RemediationRequest,
    RemediationResultResponse,
    RemediationRunResponse,
    VerificationDetailResponse,
)
from app.models.verification_run import VerificationRun
from app.schemas.verification import (
    Gate5DecisionResult,
    ScannerComparisonResult,
    SourceTransformationSinkAssessment,
    VerificationHistoryResponse,
    VerificationRunResponse,
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
    Trigger automated AI remediation and Gate 4 patch verification for an individual finding.
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


@router.post(
    "/reviews/{review_id}/correlated-findings/{correlated_finding_id}/remediate",
    response_model=RemediationRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def remediate_correlated_finding(
    review_id: str,
    correlated_finding_id: str,
    background_tasks: BackgroundTasks,
    payload: Optional[RemediationRequest] = None,
    wait: bool = Query(False, description="Wait synchronously for completion"),
    db: AsyncSession = Depends(get_db),
    maker: async_sessionmaker[AsyncSession] = Depends(get_session_maker),
) -> RemediationRunResponse:
    """
    Trigger root-cause aware remediation and Gate 4 verification for an aggregated CorrelatedFinding cluster.
    """
    # 1. Validate Review
    rev_res = await db.execute(select(Review).where(Review.id == review_id))
    review = rev_res.scalar_one_or_none()
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review '{review_id}' not found.",
        )

    # 2. Validate Correlated Finding
    corr_res = await db.execute(
        select(CorrelatedFinding).where(
            CorrelatedFinding.id == correlated_finding_id,
            CorrelatedFinding.review_id == review_id,
        )
    )
    correlated = corr_res.scalar_one_or_none()
    if not correlated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Correlated finding '{correlated_finding_id}' not found for review '{review_id}'.",
        )

    # 3. Check active remediation
    active_statuses = ["queued", "generating", "patch_generated", "patch_validated", "verifying"]
    active_res = await db.execute(
        select(RemediationRun).where(
            RemediationRun.correlated_finding_id == correlated_finding_id,
            RemediationRun.status.in_(active_statuses),
        )
    )
    if active_res.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A remediation run is already active for correlated finding '{correlated_finding_id}'.",
        )

    # 4. Check attempts
    attempts_res = await db.execute(
        select(func.count(RemediationRun.id)).where(
            RemediationRun.correlated_finding_id == correlated_finding_id
        )
    )
    attempts = attempts_res.scalar() or 0
    if attempts >= MAX_REMEDIATION_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum remediation attempts ({MAX_REMEDIATION_ATTEMPTS}) reached for this cluster.",
        )

    # 5. Create RemediationRun
    run = RemediationRun(
        review_id=review_id,
        finding_id=correlated.primary_finding_id,
        correlated_finding_id=correlated.id,
        snapshot_id=correlated.snapshot_id,
        status="queued",
        verification_status="not_started",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # 6. Execute
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


@router.post(
    "/reviews/{review_id}/remediate-eligible",
    response_model=BatchRemediationResponse,
    status_code=status.HTTP_200_OK,
)
async def remediate_eligible_findings(
    review_id: str,
    background_tasks: BackgroundTasks,
    payload: Optional[BatchRemediationRequest] = None,
    db: AsyncSession = Depends(get_db),
    maker: async_sessionmaker[AsyncSession] = Depends(get_session_maker),
) -> BatchRemediationResponse:
    """
    Queue automated remediation runs for all eligible validated correlated findings in a review.
    """
    rev_res = await db.execute(select(Review).where(Review.id == review_id))
    review = rev_res.scalar_one_or_none()
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review '{review_id}' not found.",
        )

    min_conf = payload.min_confidence if payload else 0.7
    allowed_categories = payload.categories if (payload and payload.categories) else None

    # Query eligible correlated findings
    cf_query = select(CorrelatedFinding).where(
        CorrelatedFinding.review_id == review_id,
        CorrelatedFinding.severity.in_(["critical", "high", "medium"]),
        CorrelatedFinding.confidence >= min_conf,
    )
    if allowed_categories:
        cf_query = cf_query.where(CorrelatedFinding.category.in_(allowed_categories))

    cf_res = await db.execute(cf_query)
    eligible_cfs = list(cf_res.scalars().all())

    queued_runs: List[RemediationRunResponse] = []
    skipped_reasons: List[str] = []
    active_statuses = ["queued", "generating", "patch_generated", "patch_validated", "verifying"]
    orchestrator = RemediationOrchestrator()

    for cf in eligible_cfs:
        # Check active runs
        act_res = await db.execute(
            select(RemediationRun).where(
                RemediationRun.correlated_finding_id == cf.id,
                RemediationRun.status.in_(active_statuses),
            )
        )
        if act_res.scalar_one_or_none() is not None:
            skipped_reasons.append(f"Cluster '{cf.id[:8]}': already in progress.")
            continue

        # Check attempts
        att_res = await db.execute(
            select(func.count(RemediationRun.id)).where(RemediationRun.correlated_finding_id == cf.id)
        )
        if (att_res.scalar() or 0) >= MAX_REMEDIATION_ATTEMPTS:
            skipped_reasons.append(f"Cluster '{cf.id[:8]}': maximum attempts exhausted.")
            continue

        run = RemediationRun(
            review_id=review_id,
            finding_id=cf.primary_finding_id,
            correlated_finding_id=cf.id,
            snapshot_id=cf.snapshot_id,
            status="queued",
            verification_status="not_started",
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)

        background_tasks.add_task(
            orchestrator.run,
            remediation_id=run.id,
            session_maker=maker,
        )
        queued_runs.append(RemediationRunResponse.model_validate(run))

    return BatchRemediationResponse(
        review_id=review_id,
        queued_runs=queued_runs,
        total_queued=len(queued_runs),
        skipped_count=len(skipped_reasons),
        skipped_reasons=skipped_reasons,
    )


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
    """Return proposed fix, unified diff, Gate 4 audit results, and risk state."""
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

    gate4_checks = [Gate4CheckResult.model_validate(c) for c in meta.get("gate_4_checks", [])]
    risk_assessment = (
        PatchRiskAssessment.model_validate(meta["risk_assessment"])
        if meta.get("risk_assessment")
        else None
    )

    return RemediationResultResponse(
        id=run.id,
        finding_id=run.finding_id,
        correlated_finding_id=run.correlated_finding_id,
        status=run.status,
        strategy=meta.get("strategy"),
        explanation=meta.get("explanation"),
        changed_files=[c.get("file_path", "") for c in meta.get("changes", [])],
        diff=meta.get("diff"),
        patch_version=run.patch_version,
        risk_level=run.risk_level,
        risk_assessment=risk_assessment,
        gate_4_status=run.gate_4_status,
        gate_4_checks=gate4_checks,
        gate_5_decision=run.gate_5_decision,
        gate_5_result=meta.get("gate_5_result"),
        root_cause=meta.get("root_cause"),
        potential_side_effects=meta.get("potential_side_effects"),
        expected_behavior=meta.get("expected_behavior"),
        verification_status=run.verification_status,
        confidence=meta.get("remediation_confidence"),
        verification_explanation=meta.get("verification_reason"),
        attempt_number=meta.get("attempt_number", run.patch_version),
    )


@router.get(
    "/remediations/{remediation_id}/gate-4",
    response_model=Gate4AuditReport,
)
async def get_remediation_gate_4(
    remediation_id: str,
    db: AsyncSession = Depends(get_db),
) -> Gate4AuditReport:
    """Return detailed Gate 4 deterministic verification checks for a patch."""
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

    gate4_checks = [Gate4CheckResult.model_validate(c) for c in meta.get("gate_4_checks", [])]
    return Gate4AuditReport(
        gate_status=run.gate_4_status,
        checks=gate4_checks,
        syntax_valid=meta.get("syntax_valid", False),
        static_finding_cleared=meta.get("static_finding_cleared", False),
        new_issues_detected=meta.get("new_issues_detected", []),
    )


@router.get(
    "/remediations/{remediation_id}/risk",
    response_model=PatchRiskAssessment,
)
async def get_remediation_risk(
    remediation_id: str,
    db: AsyncSession = Depends(get_db),
) -> PatchRiskAssessment:
    """Return deterministic patch risk assessment and contributing factors."""
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

    if meta.get("risk_assessment"):
        return PatchRiskAssessment.model_validate(meta["risk_assessment"])

    return PatchRiskAssessment(
        level=run.risk_level,
        score=0.1,
        factors=["Standard patch assessment"],
        explanation="Default risk level assigned from run state.",
    )


@router.post(
    "/remediations/{remediation_id}/retry",
    response_model=RemediationRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def retry_remediation(
    remediation_id: str,
    background_tasks: BackgroundTasks,
    wait: bool = Query(False, description="Wait synchronously for completion"),
    db: AsyncSession = Depends(get_db),
    maker: async_sessionmaker[AsyncSession] = Depends(get_session_maker),
) -> RemediationRunResponse:
    """Retry a failed remediation attempt with feedback from the previous run."""
    run_res = await db.execute(
        select(RemediationRun).where(RemediationRun.id == remediation_id)
    )
    old_run = run_res.scalar_one_or_none()
    if not old_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Remediation run '{remediation_id}' not found.",
        )

    # Check total attempts for this target
    target_finding = old_run.finding_id
    target_correlated = old_run.correlated_finding_id
    attempts_res = await db.execute(
        select(func.count(RemediationRun.id)).where(
            RemediationRun.review_id == old_run.review_id,
            (RemediationRun.finding_id == target_finding) | (RemediationRun.correlated_finding_id == target_correlated),
        )
    )
    attempts = attempts_res.scalar() or 0
    if attempts >= MAX_REMEDIATION_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum remediation attempts ({MAX_REMEDIATION_ATTEMPTS}) reached for this issue.",
        )

    new_run = RemediationRun(
        review_id=old_run.review_id,
        finding_id=old_run.finding_id,
        correlated_finding_id=old_run.correlated_finding_id,
        snapshot_id=old_run.snapshot_id,
        patch_version=attempts + 1,
        status="queued",
        verification_status="not_started",
    )
    db.add(new_run)
    await db.commit()
    await db.refresh(new_run)

    orchestrator = RemediationOrchestrator()
    if wait:
        await orchestrator.run(remediation_id=new_run.id, session_maker=maker)
        await db.refresh(new_run)
    else:
        background_tasks.add_task(
            orchestrator.run,
            remediation_id=new_run.id,
            session_maker=maker,
        )

    return RemediationRunResponse.model_validate(new_run)


@router.get(
    "/reviews/{review_id}/correlated-findings/{correlated_finding_id}/remediations",
    response_model=RemediationHistoryResponse,
)
async def get_correlated_finding_remediations(
    review_id: str,
    correlated_finding_id: str,
    db: AsyncSession = Depends(get_db),
) -> RemediationHistoryResponse:
    """Return historical remediation attempts for a correlated finding cluster."""
    runs_res = await db.execute(
        select(RemediationRun)
        .where(
            RemediationRun.review_id == review_id,
            RemediationRun.correlated_finding_id == correlated_finding_id,
        )
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
    "/remediations/{remediation_id}/gate-5",
    response_model=Gate5DecisionResult,
)
async def get_remediation_gate_5(
    remediation_id: str,
    db: AsyncSession = Depends(get_db),
) -> Gate5DecisionResult:
    """Return Gate 5 deterministic decision result and itemized conditions audit."""
    run_res = await db.execute(
        select(RemediationRun).where(RemediationRun.id == remediation_id)
    )
    run = run_res.scalar_one_or_none()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Remediation run '{remediation_id}' not found.",
        )

    # Fetch latest verification run if available
    v_res = await db.execute(
        select(VerificationRun)
        .where(VerificationRun.remediation_run_id == remediation_id)
        .order_by(VerificationRun.created_at.desc())
        .limit(1)
    )
    v_run = v_res.scalar_one_or_none()

    if v_run and v_run.decision_reasons_json:
        try:
            reasons = json.loads(v_run.decision_reasons_json)
        except Exception:
            reasons = [v_run.reason or "No decision reasons recorded."]
        try:
            failed_conds = json.loads(v_run.failed_conditions_json or "[]")
        except Exception:
            failed_conds = []

        is_resolved = (v_run.gate_5_decision == "RESOLVED")
        return Gate5DecisionResult(
            decision=v_run.gate_5_decision,
            passed_conditions=["Verified against Gate 5 mandatory rules"] if is_resolved else [],
            failed_conditions=failed_conds,
            reasons=reasons,
            patch_version=v_run.patch_version,
            snapshot_id=v_run.snapshot_id,
            is_resolved=is_resolved,
            limitations=v_run.limitations,
        )

    # Fallback to metadata
    meta = {}
    if run.metadata_json:
        try:
            meta = json.loads(run.metadata_json)
        except Exception:
            pass

    if meta.get("gate_5_result"):
        return Gate5DecisionResult.model_validate(meta["gate_5_result"])

    is_res = (run.gate_5_decision == "RESOLVED")
    return Gate5DecisionResult(
        decision=run.gate_5_decision,
        passed_conditions=["Evaluation completed"] if is_res else [],
        failed_conditions=[] if is_res else [f"Resolution blocked: {run.verification_status}"],
        reasons=[f"Gate 5 status: {run.gate_5_decision}"],
        patch_version=run.patch_version,
        snapshot_id=run.snapshot_id,
        is_resolved=is_res,
    )


@router.get(
    "/remediations/{remediation_id}/verification-history",
    response_model=VerificationHistoryResponse,
)
async def get_remediation_verification_history(
    remediation_id: str,
    db: AsyncSession = Depends(get_db),
) -> VerificationHistoryResponse:
    """Return all historical verification attempts for a remediation run."""
    run_res = await db.execute(
        select(RemediationRun).where(RemediationRun.id == remediation_id)
    )
    run = run_res.scalar_one_or_none()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Remediation run '{remediation_id}' not found.",
        )

    v_res = await db.execute(
        select(VerificationRun)
        .where(VerificationRun.remediation_run_id == remediation_id)
        .order_by(VerificationRun.created_at.asc())
    )
    v_runs = list(v_res.scalars().all())

    items: List[VerificationRunResponse] = []
    for vr in v_runs:
        s_t_s = None
        if vr.source_transformation_sink_json:
            try:
                s_t_s = SourceTransformationSinkAssessment.model_validate(json.loads(vr.source_transformation_sink_json))
            except Exception:
                pass
        scanner_comp = None
        if vr.scanner_comparison_json:
            try:
                scanner_comp = ScannerComparisonResult.model_validate(json.loads(vr.scanner_comparison_json))
            except Exception:
                pass

        try:
            dec_reasons = json.loads(vr.decision_reasons_json or "[]")
        except Exception:
            dec_reasons = []
        try:
            failed_conds = json.loads(vr.failed_conditions_json or "[]")
        except Exception:
            failed_conds = []
        try:
            new_issues = json.loads(vr.new_issues_json or "[]")
        except Exception:
            new_issues = []

        items.append(
            VerificationRunResponse(
                id=vr.id,
                review_id=vr.review_id,
                remediation_run_id=vr.remediation_run_id,
                finding_id=vr.finding_id,
                correlated_finding_id=vr.correlated_finding_id,
                snapshot_id=vr.snapshot_id,
                patch_version=vr.patch_version,
                agent_run_id=vr.agent_run_id,
                status=vr.status,
                outcome=vr.outcome,
                gate_5_decision=vr.gate_5_decision,
                confidence=vr.confidence,
                methodology=vr.methodology,
                reason=vr.reason,
                source_transformation_sink=s_t_s,
                scanner_comparison=scanner_comp,
                test_results=[],
                regression_results=[],
                remaining_evidence=vr.remaining_evidence,
                new_issues_detected=new_issues,
                decision_reasons=dec_reasons,
                failed_conditions=failed_conds,
                limitations=vr.limitations,
                duration_ms=vr.duration_ms,
                created_at=vr.created_at,
            )
        )

    return VerificationHistoryResponse(
        remediation_run_id=remediation_id,
        finding_id=run.finding_id,
        total_runs=len(items),
        runs=items,
    )


@router.post(
    "/remediations/{remediation_id}/verify",
    response_model=VerificationRunResponse,
    status_code=status.HTTP_200_OK,
)
async def trigger_independent_verification(
    remediation_id: str,
    db: AsyncSession = Depends(get_db),
    maker: async_sessionmaker[AsyncSession] = Depends(get_session_maker),
) -> VerificationRunResponse:
    """Manually trigger an independent verification audit on an existing remediation patch."""
    run_res = await db.execute(
        select(RemediationRun).where(RemediationRun.id == remediation_id)
    )
    run = run_res.scalar_one_or_none()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Remediation run '{remediation_id}' not found.",
        )

    if run.gate_4_status != "PASSED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot independently verify patch: Gate 4 status is '{run.gate_4_status}' (must be 'PASSED').",
        )

    orchestrator = RemediationOrchestrator()
    await orchestrator.run(remediation_id=run.id, session_maker=maker)
    await db.refresh(run)

    v_res = await db.execute(
        select(VerificationRun)
        .where(VerificationRun.remediation_run_id == remediation_id)
        .order_by(VerificationRun.created_at.desc())
        .limit(1)
    )
    v_run = v_res.scalar_one()

    return VerificationRunResponse(
        id=v_run.id,
        review_id=v_run.review_id,
        remediation_run_id=v_run.remediation_run_id,
        finding_id=v_run.finding_id,
        correlated_finding_id=v_run.correlated_finding_id,
        snapshot_id=v_run.snapshot_id,
        patch_version=v_run.patch_version,
        status=v_run.status,
        outcome=v_run.outcome,
        gate_5_decision=v_run.gate_5_decision,
        confidence=v_run.confidence,
        methodology=v_run.methodology,
        reason=v_run.reason,
        created_at=v_run.created_at,
    )


@router.get(
    "/findings/{finding_id}/resolution-status",
)
async def get_finding_resolution_status(
    finding_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Return final defect resolution state, gate 5 decision, and latest patch audit."""
    f_res = await db.execute(select(Finding).where(Finding.id == finding_id))
    finding = f_res.scalar_one_or_none()
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finding '{finding_id}' not found.",
        )

    run_res = await db.execute(
        select(RemediationRun)
        .where(RemediationRun.finding_id == finding_id)
        .order_by(RemediationRun.created_at.desc())
        .limit(1)
    )
    latest_run = run_res.scalar_one_or_none()

    return {
        "finding_id": finding.id,
        "review_id": finding.review_id,
        "title": finding.title,
        "category": finding.category,
        "severity": finding.severity,
        "finding_status": finding.status,
        "is_resolved": finding.status == "resolved",
        "latest_remediation_id": latest_run.id if latest_run else None,
        "gate_4_status": latest_run.gate_4_status if latest_run else None,
        "gate_5_decision": latest_run.gate_5_decision if latest_run else "UNRESOLVED",
        "patch_version": latest_run.patch_version if latest_run else None,
    }

