"""
Multi-agent analysis orchestrator.

Coordinates execution across:
1. Deterministic Static Security Analysis
2. Code Understanding Agent
3. Code Review Agent
4. Security Agent
5. Finding Normalization & Cross-Agent Deduplication
6. Deterministic Score Calculation
7. Database Persistence (AgentRuns, Findings, Review Scores & Status)
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.base import AgentFinding, AgentResult, AnalysisContext
from app.agents.code_quality import CodeQualityAgent
from app.agents.code_review import CodeReviewAgent
from app.agents.code_understanding import CodeUnderstandingAgent
from app.agents.security import SecurityAgent
from app.agents.security_detection import SecurityDetectionAgent
from app.agents.verification_gates import (
    QualityVerificationGate,
    SecurityVerificationGate,
    UnderstandingVerificationGate,
)
from app.analysis.context_builder import ContextBuilder
from app.analysis.file_filter import FileFilter
from app.analysis.finding_correlator import FindingCorrelator
from app.analysis.finding_normalizer import CanonicalFinding, FindingNormalizer
from app.analysis.inventory import FileInventory
from app.analysis.static_analysis import StaticSecurityAnalyzer
from app.analysis.workspace import AnalysisWorkspace
from app.llm.client import get_llm_provider
from app.llm.provider import LLMProvider
from app.models.agent_run import AgentRun
from app.models.correlated_finding import CorrelatedFinding
from app.models.analysis_job import AnalysisJob
from app.models.finding import Finding
from app.models.finding_relationship import FindingRelationship
from app.models.repository import Repository
from app.models.repository_snapshot import RepositorySnapshot
from app.models.review import Review
from app.schemas.analysis import PipelineStage, STAGE_PROGRESS_MAP
from app.core.config import settings
from app.github.service import BaseGitHubService, GitHubService

logger = logging.getLogger("ai_code_reviewer.orchestrator")


class AnalysisOrchestrator:
    """Orchestrates multi-agent review analysis and persistence."""

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        github_service: Optional[BaseGitHubService] = None,
    ) -> None:
        self.provider = provider or get_llm_provider()
        self.github_service = github_service or GitHubService(token=settings.github_token)
        self.context_builder = ContextBuilder()
        self.normalizer = FindingNormalizer()
        self.static_analyzer = StaticSecurityAnalyzer()
        self.file_filter = FileFilter()
        self.understanding_gate = UnderstandingVerificationGate()
        self.quality_gate = QualityVerificationGate()
        self.security_gate = SecurityVerificationGate()
        self.correlator = FindingCorrelator(provider=self.provider)

    async def _update_job(
        self,
        session_maker: async_sessionmaker,
        job_id: Optional[str],
        *,
        stage: PipelineStage,
        status: Optional[str] = None,
        error: Optional[str] = None,
        progress: Optional[float] = None,
    ) -> None:
        """Update AnalysisJob stage and progress in database."""
        if not job_id:
            return
        try:
            async with session_maker() as db:
                job_res = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
                job = job_res.scalar_one_or_none()
                if job:
                    job.current_stage = stage.value
                    job.progress = progress if progress is not None else STAGE_PROGRESS_MAP.get(stage.value, job.progress)
                    if status:
                        job.status = status
                    if error:
                        job.error = error
                    if stage in (
                        PipelineStage.ANALYSIS_COMPLETED,
                        PipelineStage.PARTIALLY_COMPLETED,
                        PipelineStage.FAILED,
                        PipelineStage.CANCELLED,
                    ):
                        job.completed_at = datetime.now(timezone.utc)
                    await db.commit()
        except Exception as exc:
            logger.warning(f"Failed to update analysis job {job_id} stage: {exc}")

    async def _fetch_files_if_needed(
        self,
        review: Review,
        provided_files: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """Load file contents either from provided dict, from AnalysisWorkspace cache, or by fetching from GitHub."""
        if provided_files is not None:
            # Also persist provided files to workspace cache for future resilience
            try:
                AnalysisWorkspace(review.id).save_files(provided_files)
            except Exception as e:
                logger.debug(f"Could not save provided files to workspace: {e}")
            return provided_files

        # 1. Try loading from AnalysisWorkspace local cache
        try:
            workspace = AnalysisWorkspace(review.id)
            cached_files = workspace.load_files()
            if cached_files:
                logger.info(f"Loaded {len(cached_files)} cached files from AnalysisWorkspace for review {review.id[:8]}")
                return cached_files
        except Exception as exc:
            logger.warning(f"Failed to load from AnalysisWorkspace for review {review.id[:8]}: {exc}")

        # 2. Fetch from GitHub if not cached
        gh = self.github_service
        repo = review.repository
        if not repo:
            return {}

        try:
            tree_items = await gh.get_file_tree(
                owner=repo.owner, repo=repo.name, tree_sha=review.commit_sha, recursive=True
            )
        except Exception as exc:
            logger.error(f"Failed to fetch tree from GitHub in orchestrator for {repo.owner}/{repo.name}@{review.commit_sha}: {exc}")
            return {}

        blob_items = [item for item in tree_items if item.type == "blob"]
        includable = [
            item for item in blob_items
            if self.file_filter.should_include(item.path, item.size)
        ][:100]  # Bounded fetch for analysis

        file_contents: Dict[str, str] = {}
        semaphore = asyncio.Semaphore(5)

        async def fetch_one(path: str) -> None:
            async with semaphore:
                try:
                    res = await gh.get_file_content(
                        owner=repo.owner, repo=repo.name, path=path, ref=review.commit_sha
                    )
                    if res.content is not None:
                        file_contents[path] = res.content
                except Exception as exc:
                    logger.warning(f"Failed to fetch file '{path}' in orchestrator: {exc}")

        await asyncio.gather(*[fetch_one(item.path) for item in includable])

        # Cache newly fetched files in workspace
        if file_contents:
            try:
                AnalysisWorkspace(review.id).save_files(file_contents)
            except Exception as exc:
                logger.debug(f"Could not cache fetched files to workspace: {exc}")

        return file_contents

    async def run(
        self,
        review_id: str,
        session_maker: async_sessionmaker,
        files: Optional[Dict[str, str]] = None,
        job_id: Optional[str] = None,
    ) -> Review:
        """
        Execute full Phase 7 multi-agent analysis for a review with live pipeline state tracking.
        """
        start_overall = time.perf_counter()

        # 1. Load Review and Repository Snapshot
        async with session_maker() as db:
            review_res = await db.execute(
                select(Review).options(selectinload(Review.repository)).where(Review.id == review_id)
            )
            review = review_res.scalar_one_or_none()
            if review is None:
                raise ValueError(f"Review '{review_id}' not found.")

            # Load Repository relationship
            repo_res = await db.execute(
                select(Repository).where(Repository.id == review.repository_id)
            )
            repo = repo_res.scalar_one_or_none()
            if repo is not None:
                review.repository = repo

            # Locate active job if job_id was not explicitly passed
            if not job_id:
                job_res = await db.execute(
                    select(AnalysisJob)
                    .where(AnalysisJob.review_id == review_id)
                    .order_by(AnalysisJob.created_at.desc())
                )
                j = job_res.scalars().first()
                if j and j.is_active:
                    job_id = j.id

            snap_res = await db.execute(
                select(RepositorySnapshot).where(RepositorySnapshot.review_id == review_id)
            )
            snapshot = snap_res.scalar_one_or_none()

            review.status = "running"
            review.started_at = datetime.now(timezone.utc)
            await db.commit()

        # If snapshot not present, create it from provided files or live ingestion
        if snapshot is None:
            await self._update_job(session_maker, job_id, stage=PipelineStage.INGESTING, status="ingesting")
            if files is not None:
                from app.analysis.snapshot import build_snapshot
                from app.analysis.language_detector import detect_languages
                from app.analysis.dependency_analyzer import analyze_dependencies
                from app.analysis.repository_intelligence import analyze_repository
                langs = detect_languages(files)
                deps = analyze_dependencies(files)
                intel = analyze_repository(files, langs, deps)
                snap_data = build_snapshot(
                    review_id=review_id,
                    commit_sha=review.commit_sha,
                    branch=review.branch,
                    intelligence=intel,
                    dependencies=deps,
                )
                async with session_maker() as db:
                    snapshot = RepositorySnapshot(**snap_data.to_db_kwargs())
                    db.add(snapshot)
                    await db.commit()
                    await db.refresh(snapshot)
            elif job_id:
                from app.analysis.ingestion import IngestionPipeline
                from app.services.github import get_default_github_service
                ingestion_service = self.github_service or get_default_github_service()
                pipeline = IngestionPipeline(github_service=ingestion_service)
                await pipeline.run(job_id=job_id, session_maker=session_maker)
                async with session_maker() as db:
                    snap_res = await db.execute(
                        select(RepositorySnapshot).where(RepositorySnapshot.review_id == review_id)
                    )
                    snapshot = snap_res.scalar_one_or_none()
            else:
                raise ValueError(f"Repository snapshot not found for review '{review_id}'.")

            if snapshot is None:
                raise ValueError(f"Repository snapshot not found for review '{review_id}'.")

            await self._update_job(session_maker, job_id, stage=PipelineStage.SNAPSHOTTING, status="indexing")

        # 2. Obtain relevant file contents
        all_files = await self._fetch_files_if_needed(review, files)

        # Track file inventory across agents
        file_inventory: Optional[FileInventory] = None
        if snapshot and snapshot.structure:
            try:
                struct_data = json.loads(snapshot.structure) if isinstance(snapshot.structure, str) else dict(snapshot.structure)
                inv_dict = struct_data.get("file_inventory")
                if inv_dict:
                    file_inventory = FileInventory.from_dict(inv_dict)
            except Exception as exc:
                logger.warning(f"Could not load file_inventory from snapshot: {exc}")

        if file_inventory is None and all_files:
            file_inventory = FileInventory(
                review_id=review.id,
                commit_sha=review.commit_sha,
                snapshot_id=snapshot.id if snapshot else None,
            )
            for path, content in all_files.items():
                file_inventory.record_downloaded(path, len(content.encode("utf-8", errors="replace")))
                file_inventory.record_decoded(path, content)

        if file_inventory:
            for path in all_files.keys():
                file_inventory.record_analyzed(path, "security_static")

        # 3. Deterministic Static Security Analysis (zero network, fast)
        static_start = time.perf_counter()
        static_findings = self.static_analyzer.analyze_repository_files(all_files)
        static_duration_ms = int((time.perf_counter() - static_start) * 1000)

        # Record static run and persist static findings immediately so findings are visible early
        async with session_maker() as db:
            # Delete old static findings for this review to prevent duplicates on re-run
            old_static_f = await db.execute(
                select(Finding).where(
                    Finding.review_id == review_id,
                    Finding.source == "security_static",
                )
            )
            for f in old_static_f.scalars().all():
                await db.delete(f)

            for sf in static_findings:
                db.add(
                    Finding(
                        review_id=review_id,
                        category=sf.category,
                        severity=sf.severity,
                        title=sf.title,
                        description=sf.description,
                        file_path=sf.file_path,
                        line_number=sf.start_line,
                        start_line=sf.start_line,
                        end_line=sf.end_line,
                        confidence=sf.confidence,
                        evidence=sf.evidence,
                        cwe=sf.cwe,
                        type=sf.type,
                        source="security_static",
                        status="open",
                    )
                )

            # Delete old static runs
            old_static_runs = await db.execute(
                select(AgentRun).where(
                    AgentRun.review_id == review_id,
                    AgentRun.agent_type == "security_static",
                )
            )
            for old_r in old_static_runs.scalars().all():
                await db.delete(old_r)

            static_run = AgentRun(
                review_id=review_id,
                agent_type="security_static",
                status="completed",
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                duration_ms=static_duration_ms,
                files_analyzed=len(all_files),
                findings_generated=len(static_findings),
            )
            db.add(static_run)
            await db.commit()

        # 4. Agent #1: Code Understanding
        await self._update_job(session_maker, job_id, stage=PipelineStage.UNDERSTANDING, status="analyzing")
        understanding_ctx = self.context_builder.build_understanding_context(
            review=review, snapshot=snapshot, all_files=all_files
        )
        if file_inventory and understanding_ctx.selected_files:
            for path in understanding_ctx.selected_files.keys():
                file_inventory.record_analyzed(path, "code_understanding")
        understanding_agent = CodeUnderstandingAgent(provider=self.provider)
        try:
            understanding_res = await understanding_agent.analyze(understanding_ctx)
        except Exception as exc:
            understanding_res = AgentResult(
                agent_type="code_understanding", status="failed", error=str(exc)
            )

        # Gate 1: Understanding Verification Gate
        await self._update_job(session_maker, job_id, stage=PipelineStage.VERIFYING_UNDERSTANDING)
        gate1_meta: Dict[str, Any] = {"status": "skipped"}
        gate1_passed = False
        if understanding_res.status == "completed" and understanding_res.data:
            deterministic_langs = self.context_builder._parse_snapshot_json(snapshot.languages, {})
            deterministic_fws = set(self.context_builder._parse_snapshot_json(snapshot.frameworks, []))
            deterministic_deps = self.context_builder._parse_snapshot_json(snapshot.dependencies, [])
            sanitized_data, gate1_meta = self.understanding_gate.verify(
                raw_output=understanding_res.data,
                known_file_paths=set(all_files.keys()),
                deterministic_frameworks=deterministic_fws,
                file_contents=all_files,
                deterministic_languages=deterministic_langs,
                deterministic_dependencies=deterministic_deps,
                repository_id=review.repository_id,
                snapshot_id=snapshot.id,
            )
            understanding_res.data = sanitized_data
            if gate1_meta.get("status") in ("verified", "verified_with_scrubbing"):
                gate1_passed = True

        # Persist Understanding Run
        async with session_maker() as db:
            model_name = getattr(self.provider, "model", None) or "ollama"
            agent_conf = understanding_res.data.get("confidence", 0.85) if understanding_res.data else 0.0
            verif_status = gate1_meta.get("status", "unverified") if understanding_res.status == "completed" else "failed"

            under_meta = {
                "model_name": model_name,
                "agent_confidence": agent_conf,
                "verification_status": verif_status,
                "gate_1": gate1_meta,
            }
            if understanding_res.data:
                under_meta["architecture_summary"] = understanding_res.data.get("architecture_summary", "")
                under_meta["frameworks"] = understanding_res.data.get("frameworks", [])
                under_meta["languages"] = understanding_res.data.get("languages", [])
                under_meta["entry_points"] = understanding_res.data.get("entry_points", [])
                under_meta["modules"] = understanding_res.data.get("modules", [])
                under_meta["important_files"] = understanding_res.data.get("important_files", [])

            # Delete previous understanding run for this review to prevent duplicates
            old_runs = await db.execute(
                select(AgentRun).where(
                    AgentRun.review_id == review_id,
                    AgentRun.agent_type == understanding_res.agent_type,
                )
            )
            for old_r in old_runs.scalars().all():
                await db.delete(old_r)

            db.add(
                AgentRun(
                    review_id=review_id,
                    agent_type=understanding_res.agent_type,
                    status=understanding_res.status,
                    started_at=datetime.now(timezone.utc),
                    completed_at=datetime.now(timezone.utc),
                    duration_ms=understanding_res.duration_ms,
                    files_analyzed=understanding_res.files_analyzed,
                    findings_generated=len(understanding_res.findings),
                    error=understanding_res.error,
                    metadata_json=json.dumps(under_meta),
                )
            )
            await db.commit()

        # RULE: Quality and Security agents must NOT run before Gate 1 passes
        if not gate1_passed:
            logger.warning(
                f"Gate 1 failed for review {review_id[:8]} (status={gate1_meta.get('status')}). "
                "Aborting Quality and Security agents as required by pipeline safety rules."
            )
            await self._update_job(
                session_maker,
                job_id,
                stage=PipelineStage.FAILED,
                status="failed",
                error=f"Gate 1 failed: {gate1_meta.get('status', 'unverified')}",
            )
            async with session_maker() as db:
                rev_res = await db.execute(select(Review).where(Review.id == review_id))
                final_review = rev_res.scalar_one()
                final_review.status = "failed"
                final_review.completed_at = datetime.now(timezone.utc)
                await db.commit()
                await db.refresh(final_review)
            return final_review

        # 5. Agent #2 (Code Quality) & Agent #3 (Security Detection) - Bounded Concurrency
        await self._update_job(session_maker, job_id, stage=PipelineStage.QUALITY_ANALYSIS, status="analyzing")
        static_dicts = [sf.to_dict() for sf in static_findings]
        code_quality_ctx = self.context_builder.build_code_quality_context(
            review=review, snapshot=snapshot, all_files=all_files
        )
        security_ctx = self.context_builder.build_security_detection_context(
            review=review, snapshot=snapshot, all_files=all_files, static_findings=static_dicts
        )

        if file_inventory and code_quality_ctx.selected_files:
            for path in code_quality_ctx.selected_files.keys():
                file_inventory.record_analyzed(path, "code_quality")

        if file_inventory and security_ctx.selected_files:
            for path in security_ctx.selected_files.keys():
                file_inventory.record_analyzed(path, "security_agent")

        # 5. Agent #2 (Code Quality) - Gate 2
        code_quality_agent = CodeQualityAgent(provider=self.provider)
        try:
            quality_res = await code_quality_agent.analyze(code_quality_ctx)
        except Exception as exc:
            quality_res = AgentResult(agent_type="code_quality", status="failed", error=str(exc))

        # 6. Agent #3 (Security Detection) - Gate 3
        await self._update_job(session_maker, job_id, stage=PipelineStage.SECURITY_ANALYSIS, status="analyzing")
        security_agent = SecurityDetectionAgent(provider=self.provider)
        try:
            security_res = await security_agent.analyze(security_ctx)
        except Exception as exc:
            security_res = AgentResult(agent_type="security_agent", status="failed", error=str(exc))

        await self._update_job(session_maker, job_id, stage=PipelineStage.VERIFYING_FINDINGS)

        # Gate 2: Quality Verification Gate
        validated_review_findings = []
        gate2_meta: Dict[str, Any] = {"status": "skipped", "validated_count": 0, "rejected_count": 0, "rejections": []}
        if quality_res.status == "completed":
            f_dicts = [f.to_dict() for f in quality_res.findings]
            val_dicts, gate2_meta = self.quality_gate.verify_findings(f_dicts, all_files)
            for vd in val_dicts:
                validated_review_findings.append(
                    AgentFinding(
                        category=vd.get("category", "maintainability"),
                        title=vd.get("title", ""),
                        description=vd.get("description", ""),
                        severity=vd.get("severity", "medium"),
                        file_path=vd.get("file_path"),
                        start_line=vd.get("start_line"),
                        end_line=vd.get("end_line"),
                        confidence=float(vd.get("confidence", 0.85)),
                        evidence=vd.get("evidence"),
                        type=vd.get("type"),
                        source="code_quality_agent",
                    )
                )

        # Gate 3: Security Verification Gate
        validated_security_findings = []
        gate3_meta: Dict[str, Any] = {"status": "skipped", "validated_count": 0, "rejected_count": 0, "rejections": []}
        if security_res.status == "completed":
            f_dicts = [f.to_dict() for f in security_res.findings]
            val_dicts, gate3_meta = self.security_gate.verify_findings(f_dicts, all_files)
            for vd in val_dicts:
                validated_security_findings.append(
                    AgentFinding(
                        category="security",
                        title=vd.get("title", ""),
                        description=vd.get("description", ""),
                        severity=vd.get("severity", "high"),
                        file_path=vd.get("file_path"),
                        start_line=vd.get("start_line"),
                        end_line=vd.get("end_line"),
                        confidence=float(vd.get("confidence", 0.90)),
                        evidence=vd.get("evidence"),
                        cwe=vd.get("cwe"),
                        type=vd.get("type"),
                        source="security_agent",
                    )
                )

        # 6. Persist AgentRun records with verification metrics
        async with session_maker() as db:
            # Delete old code_quality / code_review and security_agent runs to prevent duplicates
            old_runs = await db.execute(
                select(AgentRun).where(
                    AgentRun.review_id == review_id,
                    AgentRun.agent_type.in_(["code_quality", "code_review", "security_agent"]),
                )
            )
            for old_r in old_runs.scalars().all():
                await db.delete(old_r)

            # Code Quality Run
            review_meta = {
                "gate_2": gate2_meta,
            }
            db.add(
                AgentRun(
                    review_id=review_id,
                    agent_type=quality_res.agent_type,
                    status=quality_res.status,
                    started_at=datetime.now(timezone.utc),
                    completed_at=datetime.now(timezone.utc),
                    duration_ms=quality_res.duration_ms,
                    files_analyzed=quality_res.files_analyzed,
                    findings_generated=len(validated_review_findings),
                    error=quality_res.error,
                    metadata_json=json.dumps(review_meta),
                )
            )

            # Security Agent Run
            sec_meta = {
                "gate_3": gate3_meta,
            }
            db.add(
                AgentRun(
                    review_id=review_id,
                    agent_type=security_res.agent_type,
                    status=security_res.status,
                    started_at=datetime.now(timezone.utc),
                    completed_at=datetime.now(timezone.utc),
                    duration_ms=security_res.duration_ms,
                    files_analyzed=security_res.files_analyzed,
                    findings_generated=len(validated_security_findings),
                    error=security_res.error,
                    metadata_json=json.dumps(sec_meta),
                )
            )
            await db.commit()

        # 7. Collect and Persist Raw Validated Findings
        # All original findings from static scanning, Code Quality (Gate 2), Security Detection (Gate 3),
        # and Code Understanding are saved with their persistent IDs so that traceability is never broken.
        persisted_raw_findings: List[Finding] = []
        async with session_maker() as db:
            # Delete previous findings for this review to ensure clean idempotent run
            existing_findings_res = await db.execute(
                select(Finding).where(Finding.review_id == review_id)
            )
            for old_f in existing_findings_res.scalars().all():
                await db.delete(old_f)

            # A. Static findings
            for sf in static_findings:
                f_model = Finding(
                    review_id=review_id,
                    category=sf.category,
                    severity=sf.severity,
                    title=sf.title,
                    description=sf.description,
                    file_path=sf.file_path,
                    line_number=sf.start_line,
                    start_line=sf.start_line,
                    end_line=sf.end_line,
                    confidence=sf.confidence,
                    evidence=sf.evidence,
                    cwe=sf.cwe,
                    type=sf.type,
                    source="security_static",
                    status="open",
                )
                db.add(f_model)
                persisted_raw_findings.append(f_model)

            # B. Gate 2 Validated Quality Findings
            for f in validated_review_findings:
                f_model = Finding(
                    review_id=review_id,
                    category=f.category,
                    severity=f.severity,
                    title=f.title,
                    description=f.description,
                    file_path=f.file_path,
                    line_number=f.start_line,
                    start_line=f.start_line,
                    end_line=f.end_line,
                    confidence=f.confidence,
                    evidence=f.evidence,
                    cwe=f.cwe,
                    type=f.type,
                    source="code_quality_agent",
                    status="open",
                )
                db.add(f_model)
                persisted_raw_findings.append(f_model)

            # C. Gate 3 Validated Security Findings
            for f in validated_security_findings:
                f_model = Finding(
                    review_id=review_id,
                    category="security",
                    severity=f.severity,
                    title=f.title,
                    description=f.description,
                    file_path=f.file_path,
                    line_number=f.start_line,
                    start_line=f.start_line,
                    end_line=f.end_line,
                    confidence=f.confidence,
                    evidence=f.evidence,
                    cwe=f.cwe,
                    type=f.type,
                    source="security_agent",
                    status="open",
                )
                db.add(f_model)
                persisted_raw_findings.append(f_model)

            # D. Understanding architecture findings if any
            for f in understanding_res.findings:
                f_model = Finding(
                    review_id=review_id,
                    category=f.category,
                    severity=f.severity,
                    title=f.title,
                    description=f.description,
                    file_path=f.file_path,
                    line_number=f.start_line,
                    start_line=f.start_line,
                    end_line=f.end_line,
                    confidence=f.confidence,
                    evidence=f.evidence,
                    type=f.type,
                    source="code_understanding",
                    status="open",
                )
                db.add(f_model)
                persisted_raw_findings.append(f_model)

            await db.commit()
            for pf in persisted_raw_findings:
                await db.refresh(pf)

        # 8. Cross-Agent Finding Correlator Pass
        await self._update_job(session_maker, job_id, stage=PipelineStage.CORRELATING, status="analyzing")
        raw_dicts = [
            {
                "id": f.id,
                "review_id": f.review_id,
                "category": f.category,
                "severity": f.severity,
                "title": f.title,
                "description": f.description,
                "file_path": f.file_path,
                "line_number": f.line_number,
                "start_line": f.start_line,
                "end_line": f.end_line,
                "confidence": f.confidence,
                "evidence": f.evidence,
                "cwe": f.cwe,
                "type": f.type,
                "source": f.source,
                "status": f.status,
            }
            for f in persisted_raw_findings
        ]

        correlated_clusters, corr_meta = await self.correlator.correlate_findings(
            findings=raw_dicts,
            repository_intelligence=understanding_res.data,
            use_semantic_fallback=True,
        )

        # 9. Persist Correlated Findings and Relationships
        async with session_maker() as db:
            await self.correlator.persist_correlation_results(
                db=db,
                review_id=review_id,
                snapshot_id=snapshot.id if snapshot else None,
                clusters=correlated_clusters,
            )

            # Persist Correlator AgentRun
            corr_run = AgentRun(
                review_id=review_id,
                agent_type="finding_correlator",
                status="completed",
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                duration_ms=0,
                files_analyzed=len(all_files),
                findings_generated=len(correlated_clusters),
                metadata_json=json.dumps(corr_meta),
            )
            db.add(corr_run)
            await db.commit()

        # 10. Calculate Deterministic Scores from Correlated Clusters
        canonical_cluster_findings = [
            CanonicalFinding(
                category=c.category,
                severity=c.severity,
                title=c.title,
                description=c.description,
                file_path=c.file_path,
                start_line=c.start_line,
                end_line=c.end_line,
                confidence=c.confidence,
                evidence=c.evidence,
                cwe=c.cwe,
                source="finding_correlator",
                status="open",
            )
            for c in correlated_clusters
        ]
        arch_risks = len(understanding_res.data.get("architecture_risks", [])) if understanding_res.data else 0
        total_eligible_source = snapshot.source_files if snapshot and snapshot.source_files else len(all_files)
        scores = self.normalizer.calculate_scores(
            canonical_cluster_findings,
            architecture_risks_count=arch_risks,
            files_analyzed_count=len(all_files),
            total_eligible_source_files=total_eligible_source,
        )

        # Update snapshot structure with final inventory & coverage metrics
        if file_inventory and snapshot:
            try:
                struct_data = json.loads(snapshot.structure) if isinstance(snapshot.structure, str) else dict(snapshot.structure or {})
                struct_data["file_inventory"] = file_inventory.model_dump() if hasattr(file_inventory, "model_dump") else file_inventory.to_dict()
                _cov = file_inventory.calculate_coverage(total_eligible_source)
                struct_data["coverage"] = _cov.model_dump() if hasattr(_cov, "model_dump") else _cov.to_dict()
                async with session_maker() as db:
                    s_res = await db.execute(select(RepositorySnapshot).where(RepositorySnapshot.id == snapshot.id))
                    s_rec = s_res.scalar_one_or_none()
                    if s_rec:
                        s_rec.structure = json.dumps(struct_data)
                        await db.commit()
            except Exception as exc:
                logger.warning(f"Could not update snapshot with analysis inventory: {exc}")

        # 11. Determine Final Review Status
        critical_failures = sum(
            1 for res in (understanding_res, quality_res, security_res) if res.status == "failed"
        )
        if len(all_files) == 0:
            final_status = "completed_with_warnings" if critical_failures < 3 else "failed"
        elif critical_failures == 0:
            final_status = "completed"
        elif critical_failures < 3:
            final_status = "completed_with_warnings"
        else:
            final_status = "failed"

        # 12. Update Review in Database
        async with session_maker() as db:
            rev_res = await db.execute(select(Review).where(Review.id == review_id))
            final_review = rev_res.scalar_one()
            final_review.status = final_status
            final_review.overall_score = scores["overall_score"]
            final_review.security_score = scores["security_score"]
            final_review.quality_score = scores["quality_score"]
            final_review.architecture_score = scores["architecture_score"]
            final_review.completed_at = datetime.now(timezone.utc)
            await db.commit()
            await db.refresh(final_review)

        # 13. Update Final Job Status
        if final_status == "completed":
            await self._update_job(
                session_maker, job_id, stage=PipelineStage.ANALYSIS_COMPLETED, status="completed"
            )
        elif final_status == "completed_with_warnings":
            await self._update_job(
                session_maker, job_id, stage=PipelineStage.PARTIALLY_COMPLETED, status="completed"
            )
        else:
            await self._update_job(
                session_maker, job_id, stage=PipelineStage.FAILED, status="failed", error="Analysis failed due to multiple agent failures."
            )

        logger.info(
            f"Orchestrator completed for review {review_id[:8]}: "
            f"status={final_status} raw_findings={len(persisted_raw_findings)} correlated_clusters={len(correlated_clusters)} overall_score={scores['overall_score']}"
        )
        return final_review

    async def run_code_quality(
        self,
        review_id: str,
        session_maker: async_sessionmaker,
        files: Optional[Dict[str, str]] = None,
    ) -> AgentRun:
        """Run dedicated CodeQualityAgent and Gate 2 individually for a review."""
        async with session_maker() as db:
            review_res = await db.execute(select(Review).where(Review.id == review_id))
            review = review_res.scalar_one_or_none()
            if review is None:
                raise ValueError(f"Review '{review_id}' not found.")
            repo_res = await db.execute(select(Repository).where(Repository.id == review.repository_id))
            review.repository = repo_res.scalar_one_or_none()

            snap_res = await db.execute(select(RepositorySnapshot).where(RepositorySnapshot.review_id == review_id))
            snapshot = snap_res.scalar_one_or_none()
            if snapshot is None:
                raise ValueError("Repository snapshot not found. Ingestion must run first.")

        all_files = await self._fetch_files_if_needed(review, files)
        ctx = self.context_builder.build_code_quality_context(
            review=review, snapshot=snapshot, all_files=all_files
        )
        agent = CodeQualityAgent(provider=self.provider)
        agent_res = await agent.analyze(ctx)

        validated_findings: List[AgentFinding] = []
        gate2_meta: Dict[str, Any] = {"status": "skipped", "validated_count": 0, "rejected_count": 0, "rejections": []}
        if agent_res.status == "completed":
            f_dicts = [f.to_dict() for f in agent_res.findings]
            val_dicts, gate2_meta = self.quality_gate.verify_findings(f_dicts, all_files)
            for vd in val_dicts:
                validated_findings.append(
                    AgentFinding(
                        category=vd.get("category", "maintainability"),
                        title=vd.get("title", ""),
                        description=vd.get("description", ""),
                        severity=vd.get("severity", "medium"),
                        file_path=vd.get("file_path"),
                        start_line=vd.get("start_line"),
                        end_line=vd.get("end_line"),
                        confidence=float(vd.get("confidence", 0.85)),
                        evidence=vd.get("evidence"),
                        type=vd.get("type"),
                        source="code_quality_agent",
                    )
                )

        async with session_maker() as db:
            old_runs = await db.execute(
                select(AgentRun).where(
                    AgentRun.review_id == review_id,
                    AgentRun.agent_type.in_(["code_quality", "code_review"]),
                )
            )
            for old_r in old_runs.scalars().all():
                await db.delete(old_r)

            run_record = AgentRun(
                review_id=review_id,
                agent_type="code_quality",
                status=agent_res.status,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                duration_ms=agent_res.duration_ms,
                files_analyzed=agent_res.files_analyzed,
                findings_generated=len(validated_findings),
                error=agent_res.error,
                metadata_json=json.dumps({"gate_2": gate2_meta}),
            )
            db.add(run_record)

            # Persist validated findings for this agent
            for vf in validated_findings:
                db.add(
                    Finding(
                        review_id=review_id,
                        category=vf.category,
                        severity=vf.severity,
                        title=vf.title,
                        description=vf.description,
                        file_path=vf.file_path,
                        line_number=vf.start_line,
                        start_line=vf.start_line,
                        end_line=vf.end_line,
                        confidence=vf.confidence,
                        evidence=vf.evidence,
                        type=vf.type,
                        source="code_quality_agent",
                        status="open",
                    )
                )
            await db.commit()
            await db.refresh(run_record)

        return run_record


    async def run_security_detection(
        self,
        review_id: str,
        session_maker: async_sessionmaker,
        files: Optional[Dict[str, str]] = None,
    ) -> AgentRun:
        """Run dedicated SecurityDetectionAgent and Gate 3 individually for a review."""
        async with session_maker() as db:
            review_res = await db.execute(select(Review).where(Review.id == review_id))
            review = review_res.scalar_one_or_none()
            if review is None:
                raise ValueError(f"Review '{review_id}' not found.")
            repo_res = await db.execute(select(Repository).where(Repository.id == review.repository_id))
            review.repository = repo_res.scalar_one_or_none()

            snap_res = await db.execute(select(RepositorySnapshot).where(RepositorySnapshot.review_id == review_id))
            snapshot = snap_res.scalar_one_or_none()
            if snapshot is None:
                raise ValueError("Repository snapshot not found. Ingestion must run first.")

        all_files = await self._fetch_files_if_needed(review, files)
        static_findings = self.static_analyzer.analyze_repository_files(all_files)
        static_dicts = [sf.to_dict() for sf in static_findings]

        ctx = self.context_builder.build_security_detection_context(
            review=review, snapshot=snapshot, all_files=all_files, static_findings=static_dicts
        )
        agent = SecurityDetectionAgent(provider=self.provider)
        agent_res = await agent.analyze(ctx)

        validated_findings: List[AgentFinding] = []
        gate3_meta: Dict[str, Any] = {"status": "skipped", "validated_count": 0, "rejected_count": 0, "rejections": []}
        if agent_res.status == "completed":
            f_dicts = [f.to_dict() for f in agent_res.findings]
            val_dicts, gate3_meta = self.security_gate.verify_findings(f_dicts, all_files)
            for vd in val_dicts:
                validated_findings.append(
                    AgentFinding(
                        category="security",
                        title=vd.get("title", ""),
                        description=vd.get("description", ""),
                        severity=vd.get("severity", "high"),
                        file_path=vd.get("file_path"),
                        start_line=vd.get("start_line"),
                        end_line=vd.get("end_line"),
                        confidence=float(vd.get("confidence", 0.90)),
                        evidence=vd.get("evidence"),
                        cwe=vd.get("cwe"),
                        type=vd.get("type"),
                        source="security_agent",
                    )
                )

        async with session_maker() as db:
            old_runs = await db.execute(
                select(AgentRun).where(
                    AgentRun.review_id == review_id,
                    AgentRun.agent_type == "security_agent",
                )
            )
            for old_r in old_runs.scalars().all():
                await db.delete(old_r)

            run_record = AgentRun(
                review_id=review_id,
                agent_type="security_agent",
                status=agent_res.status,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                duration_ms=agent_res.duration_ms,
                files_analyzed=agent_res.files_analyzed,
                findings_generated=len(validated_findings),
                error=agent_res.error,
                metadata_json=json.dumps({"gate_3": gate3_meta}),
            )
            db.add(run_record)

            # Persist validated findings for this agent
            for vf in validated_findings:
                db.add(
                    Finding(
                        review_id=review_id,
                        category=vf.category,
                        severity=vf.severity,
                        title=vf.title,
                        description=vf.description,
                        file_path=vf.file_path,
                        line_number=vf.start_line,
                        start_line=vf.start_line,
                        end_line=vf.end_line,
                        confidence=vf.confidence,
                        evidence=vf.evidence,
                        cwe=vf.cwe,
                        type=vf.type,
                        source="security_agent",
                        status="open",
                    )
                )
            await db.commit()
            await db.refresh(run_record)

        return run_record

    async def run_correlation(
        self,
        review_id: str,
        session_maker: async_sessionmaker,
    ) -> Dict[str, Any]:
        """
        Run finding correlation independently on existing validated findings for a review.
        Does not re-run upstream code understanding or security/quality agents.
        """
        async with session_maker() as db:
            review_res = await db.execute(select(Review).where(Review.id == review_id))
            review = review_res.scalar_one_or_none()
            if not review:
                raise ValueError(f"Review '{review_id}' not found.")

            snapshot_res = await db.execute(
                select(RepositorySnapshot).where(RepositorySnapshot.review_id == review_id)
            )
            snapshot = snapshot_res.scalar_one_or_none()

            # Retrieve existing findings
            findings_res = await db.execute(
                select(Finding).where(Finding.review_id == review_id)
            )
            existing_findings = list(findings_res.scalars().all())

            # Retrieve Gate 1 metadata if available from code_understanding agent run
            under_res = await db.execute(
                select(AgentRun).where(
                    AgentRun.review_id == review_id,
                    AgentRun.agent_type == "code_understanding",
                ).order_by(AgentRun.created_at.desc())
            )
            under_run = under_res.scalars().first()
            repo_intel = None
            if under_run and under_run.metadata_json:
                try:
                    meta = json.loads(under_run.metadata_json)
                    repo_intel = meta.get("gate_1") or meta
                except Exception:
                    pass

        raw_dicts = [
            {
                "id": f.id,
                "review_id": f.review_id,
                "category": f.category,
                "severity": f.severity,
                "title": f.title,
                "description": f.description,
                "file_path": f.file_path,
                "line_number": f.line_number,
                "start_line": f.start_line,
                "end_line": f.end_line,
                "confidence": f.confidence,
                "evidence": f.evidence,
                "cwe": f.cwe,
                "type": f.type,
                "source": f.source,
                "status": f.status,
            }
            for f in existing_findings
        ]

        correlated_clusters, corr_meta = await self.correlator.correlate_findings(
            findings=raw_dicts,
            repository_intelligence=repo_intel,
            use_semantic_fallback=True,
        )

        async with session_maker() as db:
            await self.correlator.persist_correlation_results(
                db=db,
                review_id=review_id,
                snapshot_id=snapshot.id if snapshot else None,
                clusters=correlated_clusters,
            )

            # Persist / update AgentRun for finding_correlator
            old_run = await db.execute(
                select(AgentRun).where(
                    AgentRun.review_id == review_id,
                    AgentRun.agent_type == "finding_correlator",
                )
            )
            for r in old_run.scalars().all():
                await db.delete(r)

            corr_run = AgentRun(
                review_id=review_id,
                agent_type="finding_correlator",
                status="completed",
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                duration_ms=0,
                files_analyzed=snapshot.total_files if snapshot else 0,
                findings_generated=len(correlated_clusters),
                metadata_json=json.dumps(corr_meta),
            )
            db.add(corr_run)

            # Update review scores based on correlated clusters
            canonical_cluster_findings = [
                CanonicalFinding(
                    category=c.category,
                    severity=c.severity,
                    title=c.title,
                    description=c.description,
                    file_path=c.file_path,
                    start_line=c.start_line,
                    end_line=c.end_line,
                    confidence=c.confidence,
                    evidence=c.evidence,
                    cwe=c.cwe,
                    source="finding_correlator",
                    status="open",
                )
                for c in correlated_clusters
            ]
            arch_risks = 0
            if repo_intel and isinstance(repo_intel, dict):
                arch_risks = len(repo_intel.get("architecture_risks", []))
            scores = self.normalizer.calculate_scores(canonical_cluster_findings, architecture_risks_count=arch_risks)
            rev_res = await db.execute(select(Review).where(Review.id == review_id))
            rev = rev_res.scalar_one()
            rev.overall_score = scores["overall_score"]
            rev.security_score = scores["security_score"]
            rev.quality_score = scores["quality_score"]
            await db.commit()

        return corr_meta

