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

from app.agents.remediation import RemediationAgent
from app.agents.verification import VerificationAgent
from app.analysis.static_analysis import run_static_analysis
from app.db.session import async_session_maker as default_session_maker
from app.llm.provider import LLMProvider
from app.models.finding import Finding
from app.models.remediation_run import RemediationRun
from app.models.repository_snapshot import RepositorySnapshot
from app.models.review import Review
from app.remediation.context_builder import build_remediation_context
from app.remediation.patch_generator import (
    PatchValidationError,
    apply_code_change,
    generate_unified_diff,
    validate_patch_safety,
)
from app.remediation.workspace import IsolatedWorkspace

logger = logging.getLogger("ai_code_reviewer.remediation_orchestrator")

MAX_REMEDIATION_ATTEMPTS = 3


class RemediationOrchestrator:
    """
    Orchestrates the lifecycle of an AI remediation and verification run.
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

            # Load finding and review
            finding_res = await db.execute(
                select(Finding).where(Finding.id == run.finding_id)
            )
            finding = finding_res.scalar_one_or_none()
            if not finding:
                run.status = "failed"
                run.error = "Associated finding was not found."
                await db.commit()
                return run

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
                    RemediationRun.finding_id == finding.id,
                    RemediationRun.id != run.id,
                )
            )
            past_attempts = attempts_res.scalar() or 0
            attempt_number = past_attempts + 1

            if attempt_number > MAX_REMEDIATION_ATTEMPTS:
                run.status = "failed"
                run.error = f"Maximum remediation attempts ({MAX_REMEDIATION_ATTEMPTS}) exhausted."
                finding.status = "remediation_exhausted"
                await db.commit()
                return run

            # Load previous attempt metadata if available for retry feedback
            prev_attempt_feedback = None
            if past_attempts > 0:
                prev_run_res = await db.execute(
                    select(RemediationRun)
                    .where(
                        RemediationRun.finding_id == finding.id,
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
            finding.status = "remediation_in_progress"
            await db.commit()

            # 2. Retrieve file content from snapshot or provided files
            file_path = finding.file_path or ""
            file_content = ""
            languages = {}
            frameworks = []
            dependencies = []

            snap_res = await db.execute(
                select(RepositorySnapshot).where(RepositorySnapshot.review_id == review.id)
            )
            snapshot = snap_res.scalar_one_or_none()
            if snapshot:
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
                file_content = finding.evidence or "# Content not found in snapshot"

            # 3. Build context & generate fix
            ctx = build_remediation_context(
                finding=finding,
                file_content=file_content,
                repository_name="repository",
                languages=languages,
                frameworks=frameworks,
                dependencies=dependencies,
                previous_attempt=prev_attempt_feedback,
            )

            try:
                plan = await self.remediation_agent.generate_fix(ctx)
            except Exception as exc:
                logger.error(f"RemediationAgent error: {exc}", exc_info=True)
                run.status = "failed"
                run.error = f"Agent failed to generate fix: {str(exc)}"
                finding.status = "remediation_available"
                await db.commit()
                return run

            # 4. Validate patch safety
            target_files = plan.files_changed or ([finding.file_path] if finding.file_path else [])
            unified_diff = plan.unified_diff or ""

            try:
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
                run.error = f"Patch validation rejected: {str(pve)}"
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

                # 6. Hybrid Verification Pipeline
                run.status = "verifying"
                await db.commit()

                # A. Deterministic syntax check
                syntax_valid = True
                syntax_err_msg = None
                if file_path.endswith(".py"):
                    try:
                        compile(modified_content, file_path, "exec")
                    except SyntaxError as syn_err:
                        syntax_valid = False
                        syntax_err_msg = f"Python SyntaxError at line {syn_err.lineno}: {syn_err.msg}"

                # B. Static rule re-analysis on the modified workspace file
                static_signals = run_static_analysis({file_path: modified_content})

                # C. AI Verification Agent
                verification = await self.verification_agent.verify(
                    finding=finding,
                    file_path=file_path,
                    original_code=file_content,
                    modified_code=modified_content,
                    unified_diff=unified_diff,
                    static_analysis_signals=static_signals,
                    syntax_valid=syntax_valid,
                    syntax_error=syntax_err_msg,
                )

                # 7. Persist results
                run.verification_status = verification.status
                run.completed_at = datetime.now(timezone.utc)
                run.duration_ms = int((time.monotonic() - start_time) * 1000)
                run.status = "completed"

                meta = {
                    "strategy": plan.strategy,
                    "explanation": plan.explanation,
                    "diff": unified_diff,
                    "changes": [c.model_dump() for c in plan.changes],
                    "remediation_confidence": plan.confidence,
                    "verification_confidence": verification.confidence,
                    "verification_reason": verification.reason,
                    "remaining_risk": verification.remaining_risk,
                    "new_findings": verification.new_findings,
                    "verification_evidence": verification.evidence,
                    "attempt_number": attempt_number,
                    "prompt_versions": {
                        "remediation": self.remediation_agent.prompt_version,
                        "verification": self.verification_agent.prompt_version,
                    },
                }
                run.metadata_json = json.dumps(meta)

                # Update Finding status based on verification decision
                if verification.status == "resolved":
                    finding.status = "resolved"
                elif verification.status == "still_vulnerable":
                    finding.status = "verification_failed"
                elif verification.status == "partially_resolved":
                    finding.status = "remediation_available"
                elif verification.status == "verification_failed":
                    finding.status = "verification_failed"

                await db.commit()
                return run

            finally:
                # 8. Clean up isolated sandbox workspace
                workspace.cleanup()
