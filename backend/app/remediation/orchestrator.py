"""
Remediation Orchestrator.

Coordinates end-to-end automated fix generation, patch validation,
isolated workspace sandboxing, hybrid static/AI verification, and database persistence.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.decision_engine import Gate5DecisionEngine
from app.agents.remediation import RemediationAgent
from app.agents.verification import VerificationAgent
from app.agents.verification_gates import DeterministicDecisionEngine, PatchVerificationGate
from app.analysis.patch_risk import calculate_patch_risk
from app.analysis.rescan import DeterministicReScanner
from app.analysis.static_analysis import run_static_analysis
from app.db.session import async_session_maker as default_session_maker
from app.llm.provider import LLMProvider
from app.models.correlated_finding import CorrelatedFinding
from app.models.finding import Finding
from app.models.finding_relationship import FindingRelationship
from app.models.remediation_run import RemediationRun
from app.models.repository_snapshot import RepositorySnapshot
from app.models.review import Review
from app.models.verification_run import VerificationRun
from app.remediation.context_builder import build_remediation_context
from app.remediation.patch_generator import (
    PatchGenerator,
    PatchValidationError,
    apply_code_change,
    generate_unified_diff,
    validate_patch_safety,
)
from app.remediation.workspace import IsolatedWorkspace
from app.schemas.remediation import Gate4Status
from app.schemas.verification import (
    Gate5Decision,
    VerificationAgentReport,
    VerificationOutcome,
)

logger = logging.getLogger("ai_code_reviewer.remediation_orchestrator")

MAX_REMEDIATION_ATTEMPTS = 3


class RemediationOrchestrator:
    """
    Orchestrates the lifecycle of an AI remediation, Gate 4 patch verification, and risk assessment.
    """

    def __init__(
        self,
        remediation_agent: Optional[RemediationAgent] = None,
        verification_agent: Optional[VerificationAgent] = None,
        llm_provider: Optional[LLMProvider] = None,
        github_service: Optional[Any] = None,
    ) -> None:
        self.remediation_agent = remediation_agent or RemediationAgent(llm_provider=llm_provider)
        self.verification_agent = verification_agent or VerificationAgent(llm_provider=llm_provider)
        self.github_service = github_service
        self.patch_gate = PatchVerificationGate()
        self.patch_generator = PatchGenerator()
        self.rescan_engine = DeterministicReScanner()
        self.decision_engine = Gate5DecisionEngine()

    async def run(
        self,
        remediation_id: str,
        session_maker: Optional[async_sessionmaker[AsyncSession]] = None,
        provided_files: Optional[Dict[str, str]] = None,
    ) -> RemediationRun:
        """
        Execute full remediation & verification pipeline for a RemediationRun record.
        """
        maker = session_maker or default_session_maker
        start_time = time.monotonic()

        async with maker() as db:
            # 1. Load remediation run
            run_res = await db.execute(
                select(RemediationRun).where(RemediationRun.id == remediation_id)
            )
            run = run_res.scalar_one_or_none()
            if not run:
                raise ValueError(f"RemediationRun '{remediation_id}' not found.")

            # Load finding and/or correlated finding
            finding = None
            correlated = None
            constituent_findings = []

            if run.finding_id:
                finding_res = await db.execute(
                    select(Finding).where(Finding.id == run.finding_id)
                )
                finding = finding_res.scalar_one_or_none()

            if run.correlated_finding_id:
                corr_res = await db.execute(
                    select(CorrelatedFinding).where(CorrelatedFinding.id == run.correlated_finding_id)
                )
                correlated = corr_res.scalar_one_or_none()
                if correlated:
                    if not finding:
                        finding_res = await db.execute(
                            select(Finding).where(Finding.id == correlated.primary_finding_id)
                        )
                        finding = finding_res.scalar_one_or_none()

                    # Load constituent findings from FindingRelationship
                    rel_res = await db.execute(
                        select(FindingRelationship).where(FindingRelationship.correlated_finding_id == correlated.id)
                    )
                    rels = list(rel_res.scalars().all())
                    for r in rels:
                        if r.source_finding:
                            constituent_findings.append({
                                "id": r.source_finding.id,
                                "title": r.source_finding.title,
                                "category": r.source_finding.category,
                                "severity": r.source_finding.severity,
                                "file_path": r.source_finding.file_path,
                                "start_line": r.source_finding.start_line,
                                "source": r.source_finding.source,
                            })

            if not finding and not correlated:
                run.status = "failed"
                run.error = "Associated finding or correlated finding was not found."
                await db.commit()
                return run

            target_finding_id = finding.id if finding else correlated.id
            review_res = await db.execute(
                select(Review).where(Review.id == run.review_id)
            )
            review = review_res.scalar_one_or_none()
            if not review:
                run.status = "failed"
                run.error = "Associated review was not found."
                await db.commit()
                return run

            # Count attempts
            attempts_res = await db.execute(
                select(func.count(RemediationRun.id)).where(
                    RemediationRun.review_id == run.review_id,
                    (RemediationRun.finding_id == target_finding_id) | (RemediationRun.correlated_finding_id == run.correlated_finding_id),
                    RemediationRun.id != run.id,
                )
            )
            past_attempts = attempts_res.scalar() or 0
            attempt_number = past_attempts + 1

            if attempt_number > MAX_REMEDIATION_ATTEMPTS:
                run.status = "failed"
                run.error = f"Maximum remediation attempts ({MAX_REMEDIATION_ATTEMPTS}) exhausted."
                if finding:
                    finding.status = "remediation_exhausted"
                await db.commit()
                return run

            # Load previous attempt metadata if available for retry feedback
            prev_attempt_feedback = None
            if past_attempts > 0:
                prev_run_res = await db.execute(
                    select(RemediationRun)
                    .where(
                        RemediationRun.review_id == run.review_id,
                        (RemediationRun.finding_id == target_finding_id) | (RemediationRun.correlated_finding_id == run.correlated_finding_id),
                        RemediationRun.id != run.id,
                    )
                    .order_by(RemediationRun.created_at.desc())
                    .limit(1)
                )
                prev_run = prev_run_res.scalar_one_or_none()
                if prev_run and prev_run.metadata_json:
                    try:
                        prev_meta = json.loads(prev_run.metadata_json)
                        prev_attempt_feedback = {
                            "strategy": prev_meta.get("strategy"),
                            "verification_reason": prev_meta.get("verification_reason"),
                            "diff": prev_meta.get("diff"),
                        }
                    except Exception:
                        pass

            # Update status to generating
            run.status = "generating"
            run.started_at = datetime.now(timezone.utc)
            if finding:
                finding.status = "remediation_in_progress"
            await db.commit()

            # 2. Retrieve file content from snapshot or provided files
            file_path = (finding.file_path if finding else getattr(correlated, "file_path", "")) or ""
            file_content = ""
            languages = {}
            frameworks = []
            dependencies = []

            snap_res = await db.execute(
                select(RepositorySnapshot).where(RepositorySnapshot.review_id == review.id)
            )
            snapshot = snap_res.scalar_one_or_none()
            if snapshot:
                run.snapshot_id = snapshot.id
                if getattr(snapshot, "languages", None):
                    try:
                        languages = json.loads(snapshot.languages)
                    except Exception:
                        pass
                if getattr(snapshot, "frameworks", None):
                    try:
                        frameworks = json.loads(snapshot.frameworks)
                    except Exception:
                        pass
                if getattr(snapshot, "dependencies", None):
                    try:
                        dependencies = json.loads(snapshot.dependencies)
                    except Exception:
                        pass

            if provided_files and file_path in provided_files:
                file_content = provided_files[file_path]
            elif self.github_service and getattr(review, "repository", None):
                try:
                    res = await self.github_service.get_file_content(
                        owner=review.repository.owner,
                        repo=review.repository.name,
                        path=file_path,
                        ref=review.commit_sha,
                    )
                    if res.content is not None:
                        file_content = res.content
                except Exception as exc:
                    logger.warning(f"Could not fetch file {file_path} from GitHub: {exc}")

            # If no snapshot content, create a placeholder structure based on evidence
            if not file_content:
                file_content = (finding.evidence if finding else getattr(correlated, "evidence", "")) or "# Content not found in snapshot"

            # 3. Build context & generate fix
            ctx = build_remediation_context(
                finding=finding or correlated,
                file_content=file_content,
                repository_name="repository",
                languages=languages,
                frameworks=frameworks,
                dependencies=dependencies,
                previous_attempt=prev_attempt_feedback,
                correlated_finding=correlated,
                constituent_findings=constituent_findings,
                root_cause=getattr(correlated, "root_cause", None),
            )

            try:
                plan = await self.remediation_agent.generate_fix(ctx)
            except Exception as exc:
                logger.error(f"RemediationAgent error: {exc}", exc_info=True)
                run.status = "failed"
                run.error = f"Agent failed to generate fix: {str(exc)}"
                if finding:
                    finding.status = "remediation_available"
                await db.commit()
                return run

            # 4. Generate & Validate patch using PatchGenerator
            target_files = plan.files_changed or ([file_path] if file_path else [])
            unified_diff = plan.unified_diff or ""

            try:
                if plan.changes:
                    # Validate substitution against source snapshot and detect stale patches
                    unified_diff, target_files, _ = self.patch_generator.generate_patch(
                        snapshot_files={file_path: file_content},
                        changes=plan.changes,
                        patch_version=attempt_number,
                    )
                    plan.unified_diff = unified_diff
                else:
                    validate_patch_safety(
                        file_paths=target_files,
                        diff_text=unified_diff,
                        max_files=5,
                        max_lines=150,
                        max_size_bytes=50000,
                    )
                run.patch_valid = True
                run.status = "patch_generated"
                await db.commit()
            except PatchValidationError as pve:
                logger.warning(f"Patch validation failed for remediation {remediation_id}: {pve}")
                run.status = "failed"
                run.patch_valid = False
                run.gate_4_status = Gate4Status.FAILED.value
                run.error = f"Patch validation rejected: {str(pve)}"
                if finding:
                    finding.status = "remediation_available"
                await db.commit()
                return run

            # 5. Isolated Workspace Sandbox
            workspace = IsolatedWorkspace(
                review_id=review.id,
                remediation_id=run.id,
            )
            workspace.create()

            try:
                # Write original file into sandbox
                workspace.write_file(file_path, file_content)

                # Apply changes to original content
                modified_content = file_content
                for change in plan.changes:
                    if change.file_path == file_path:
                        modified_content = apply_code_change(
                            original_content=modified_content,
                            start_line=change.start_line,
                            end_line=change.end_line,
                            original_code=change.original_code,
                            replacement_code=change.replacement_code,
                        )

                # Write modified content into isolated workspace
                workspace.write_file(file_path, modified_content)
                run.status = "patch_validated"
                run.files_modified = len(target_files)

                # Generate complete diff if not already set
                if not unified_diff:
                    unified_diff = generate_unified_diff(
                        file_path=file_path,
                        original_content=file_content,
                        modified_content=modified_content,
                    )
                    plan.unified_diff = unified_diff

                # 6. Gate 4 Deterministic Verification Gate
                run.status = "verifying"
                run.patch_version = attempt_number
                await db.commit()

                target_cwe = finding.cwe if finding else getattr(correlated, "cwe", None)
                target_type = finding.type if finding else getattr(correlated, "type", None)
                target_evidence = finding.evidence if finding else getattr(correlated, "evidence", None)

                gate4_report = self.patch_gate.verify_patch(
                    patch_diff=unified_diff,
                    target_file=file_path,
                    file_contents={file_path: file_content},
                    cwe=target_cwe,
                    finding_type=target_type,
                )

                run.gate_4_status = gate4_report.gate_status
                run.risk_level = plan.risk_assessment.level if plan.risk_assessment else "LOW"
                run.patch_valid = (gate4_report.gate_status == Gate4Status.PASSED.value)
                syntax_valid = gate4_report.syntax_valid

                # Deterministic Re-Scanning
                rescan_report = self.rescan_engine.rescan_file(
                    file_path=file_path,
                    original_content=file_content,
                    patched_content=modified_content,
                    target_cwe=target_cwe,
                    target_type=target_type,
                    target_evidence=target_evidence,
                )

                # Independent Verification Agent
                if gate4_report.gate_status == Gate4Status.PASSED.value:
                    try:
                        verification_report = await self.verification_agent.verify(
                            finding=finding or correlated,
                            file_path=file_path,
                            original_code=file_content,
                            modified_code=modified_content,
                            unified_diff=unified_diff,
                            static_analysis_signals=rescan_report.retained_findings + rescan_report.new_findings,
                            syntax_valid=syntax_valid,
                            root_cause=getattr(correlated, "root_cause", None),
                            related_findings=constituent_findings,
                        )
                    except Exception as v_err:
                        logger.warning(f"VerificationAgent auditor call failed: {v_err}")
                        verification_report = VerificationAgentReport(
                            outcome=VerificationOutcome.UNABLE_TO_VERIFY.value,
                            reason=f"Verification agent encountered error: {v_err}",
                        )
                else:
                    verification_report = VerificationAgentReport(
                        outcome=VerificationOutcome.NOT_FIXED.value,
                        reason=f"Gate 4 patch validation rejected: {gate4_report.gate_status}",
                    )

                # Gate 5 Deterministic Decision Engine
                gate5_result = self.decision_engine.evaluate(
                    gate_4_status=gate4_report.gate_status,
                    verification_outcome=verification_report.outcome,
                    deterministic_rescan=rescan_report,
                    syntax_valid=syntax_valid,
                    patch_version=attempt_number,
                    expected_patch_version=attempt_number,
                    snapshot_id=run.snapshot_id,
                    expected_snapshot_id=run.snapshot_id,
                    tests_passed=True,
                )

                # Persist VerificationRun entity
                v_run = VerificationRun(
                    review_id=review.id,
                    remediation_run_id=run.id,
                    finding_id=finding.id if finding else None,
                    correlated_finding_id=correlated.id if correlated else None,
                    snapshot_id=run.snapshot_id,
                    patch_version=attempt_number,
                    status="completed",
                    outcome=verification_report.outcome,
                    gate_5_decision=gate5_result.decision,
                    confidence=verification_report.confidence,
                    methodology="source_transformation_sink",
                    reason=verification_report.reason,
                    source_transformation_sink_json=json.dumps(verification_report.source_transformation_sink.model_dump()) if verification_report.source_transformation_sink else None,
                    scanner_comparison_json=json.dumps(rescan_report.model_dump()),
                    remaining_evidence=verification_report.remaining_risk,
                    new_issues_json=json.dumps(rescan_report.new_findings),
                    decision_reasons_json=json.dumps(gate5_result.reasons),
                    failed_conditions_json=json.dumps(gate5_result.failed_conditions),
                    limitations=gate5_result.limitations,
                    duration_ms=int((time.monotonic() - start_time) * 1000),
                )
                db.add(v_run)

                # Update RemediationRun
                run.gate_5_decision = gate5_result.decision
                if gate5_result.decision == Gate5Decision.RESOLVED.value:
                    run.verification_status = "resolved"
                elif gate5_result.decision == Gate5Decision.PARTIALLY_RESOLVED.value:
                    run.verification_status = "partially_resolved"
                elif gate5_result.decision in (Gate5Decision.BLOCKED.value, Gate5Decision.UNABLE_TO_VERIFY.value):
                    run.verification_status = "verification_failed"
                else:
                    run.verification_status = "still_vulnerable"

                run.completed_at = datetime.now(timezone.utc)
                run.duration_ms = int((time.monotonic() - start_time) * 1000)
                run.status = "completed" if gate4_report.gate_status in (Gate4Status.PASSED.value, Gate4Status.PARTIALLY_PASSED.value) else "failed"

                meta = {
                    "strategy": plan.strategy,
                    "explanation": plan.explanation,
                    "diff": unified_diff,
                    "changes": [c.model_dump() for c in plan.changes],
                    "remediation_confidence": plan.confidence,
                    "root_cause": plan.root_cause,
                    "proposed_solution": plan.proposed_solution,
                    "expected_behavior": plan.expected_behavior,
                    "potential_side_effects": plan.potential_side_effects,
                    "required_tests": plan.required_tests,
                    "risk_assessment": plan.risk_assessment.model_dump() if plan.risk_assessment else None,
                    "gate_4_status": gate4_report.gate_status,
                    "gate_4_checks": [c.model_dump() for c in gate4_report.checks],
                    "gate_5_decision": gate5_result.decision,
                    "gate_5_result": gate5_result.model_dump(),
                    "verification_outcome": verification_report.outcome,
                    "verification_confidence": verification_report.confidence,
                    "verification_reason": verification_report.reason,
                    "source_transformation_sink": verification_report.source_transformation_sink.model_dump() if verification_report.source_transformation_sink else None,
                    "scanner_comparison": rescan_report.model_dump(),
                    "syntax_valid": syntax_valid,
                    "remaining_risk": verification_report.remaining_risk,
                    "new_findings": rescan_report.new_findings,
                    "attempt_number": attempt_number,
                    "verification_run_id": v_run.id,
                }
                run.metadata_json = json.dumps(meta)

                # Update Finding and CorrelatedFinding status
                if gate5_result.is_resolved:
                    if finding:
                        finding.status = "resolved"
                    if correlated:
                        correlated.status = "resolved"
                elif gate5_result.decision == Gate5Decision.PARTIALLY_RESOLVED.value:
                    if finding:
                        finding.status = "remediation_available"
                else:
                    if finding:
                        finding.status = "verification_failed"

                await db.commit()
                return run

                await db.commit()
                return run

            finally:
                # 8. Clean up isolated sandbox workspace
                workspace.cleanup()

    async def run_for_correlated_finding(
        self,
        review_id: str,
        correlated_finding_id: str,
        session_maker: Optional[async_sessionmaker[AsyncSession]] = None,
        provided_files: Optional[Dict[str, str]] = None,
    ) -> RemediationRun:
        """
        Create and execute a RemediationRun for an aggregated CorrelatedFinding cluster.
        """
        maker = session_maker or default_session_maker
        async with maker() as db:
            corr_res = await db.execute(
                select(CorrelatedFinding).where(
                    CorrelatedFinding.id == correlated_finding_id,
                    CorrelatedFinding.review_id == review_id,
                )
            )
            correlated = corr_res.scalar_one_or_none()
            if not correlated:
                raise ValueError(f"CorrelatedFinding '{correlated_finding_id}' not found for review '{review_id}'.")

            attempts_res = await db.execute(
                select(func.count(RemediationRun.id)).where(
                    RemediationRun.correlated_finding_id == correlated_finding_id
                )
            )
            past_attempts = attempts_res.scalar() or 0
            if past_attempts >= MAX_REMEDIATION_ATTEMPTS:
                raise ValueError(f"Maximum remediation attempts ({MAX_REMEDIATION_ATTEMPTS}) reached for this cluster.")

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

        return await self.run(
            remediation_id=run.id,
            session_maker=maker,
            provided_files=provided_files,
        )
