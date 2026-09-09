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
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.base import AgentResult, AnalysisContext
from app.agents.code_review import CodeReviewAgent
from app.agents.code_understanding import CodeUnderstandingAgent
from app.agents.security import SecurityAgent
from app.analysis.context_builder import ContextBuilder
from app.analysis.file_filter import FileFilter
from app.analysis.finding_normalizer import CanonicalFinding, FindingNormalizer
from app.analysis.static_analysis import StaticSecurityAnalyzer
from app.llm.client import get_llm_provider
from app.llm.provider import LLMProvider
from app.models.agent_run import AgentRun
from app.models.finding import Finding
from app.models.repository import Repository
from app.models.repository_snapshot import RepositorySnapshot
from app.models.review import Review
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

    async def _fetch_files_if_needed(
        self,
        review: Review,
        provided_files: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """Load file contents either from provided dict or by fetching from GitHub."""
        if provided_files is not None:
            return provided_files

        gh = self.github_service
        repo = review.repository
        if not repo:
            return {}

        try:
            tree_items = await gh.get_file_tree(
                owner=repo.owner, repo=repo.name, tree_sha=review.commit_sha, recursive=True
            )
        except Exception as exc:
            logger.warning(f"Failed to fetch tree from GitHub in orchestrator: {exc}")
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
                except Exception:
                    pass

        await asyncio.gather(*[fetch_one(item.path) for item in includable])
        return file_contents

    async def run(
        self,
        review_id: str,
        session_maker: async_sessionmaker,
        files: Optional[Dict[str, str]] = None,
    ) -> Review:
        """
        Execute full Phase 5 multi-agent analysis for a review.
        """
        start_overall = time.perf_counter()

        # 1. Load Review and Repository Snapshot
        async with session_maker() as db:
            review_res = await db.execute(
                select(Review).where(Review.id == review_id)
            )
            review = review_res.scalar_one_or_none()
            if review is None:
                raise ValueError(f"Review '{review_id}' not found.")

            # Load Repository relationship
            repo_res = await db.execute(
                select(Repository).where(Repository.id == review.repository_id)
            )
            review.repository = repo_res.scalar_one_or_none()

            snap_res = await db.execute(
                select(RepositorySnapshot).where(RepositorySnapshot.review_id == review_id)
            )
            snapshot = snap_res.scalar_one_or_none()
            if snapshot is None:
                raise ValueError(f"Repository snapshot not found for review '{review_id}'. Ingestion must run first.")

            review.status = "running"
            review.started_at = datetime.now(timezone.utc)
            await db.commit()

        # 2. Obtain relevant file contents
        all_files = await self._fetch_files_if_needed(review, files)

        # 3. Deterministic Static Security Analysis (zero network, fast)
        static_start = time.perf_counter()
        static_findings = self.static_analyzer.analyze_repository_files(all_files)
        static_duration_ms = int((time.perf_counter() - static_start) * 1000)

        # Record static run
        async with session_maker() as db:
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

        # 4. Build Agent Contexts
        static_dicts = [sf.to_dict() for sf in static_findings]
        understanding_ctx = self.context_builder.build_understanding_context(
            review=review, snapshot=snapshot, all_files=all_files
        )
        code_review_ctx = self.context_builder.build_code_review_context(
            review=review, snapshot=snapshot, all_files=all_files
        )
        security_ctx = self.context_builder.build_security_context(
            review=review, snapshot=snapshot, all_files=all_files, static_findings=static_dicts
        )

        # 5. Initialize Agents
        understanding_agent = CodeUnderstandingAgent(provider=self.provider)
        code_review_agent = CodeReviewAgent(provider=self.provider)
        security_agent = SecurityAgent(provider=self.provider)

        # 6. Execute Agents Concurrently
        understanding_task = understanding_agent.analyze(understanding_ctx)
        review_task = code_review_agent.analyze(code_review_ctx)
        security_task = security_agent.analyze(security_ctx)

        results: List[Any] = await asyncio.gather(
            understanding_task,
            review_task,
            security_task,
            return_exceptions=True,
        )

        understanding_res: AgentResult = (
            results[0] if isinstance(results[0], AgentResult)
            else AgentResult(agent_type="code_understanding", status="failed", error=str(results[0]))
        )
        review_res: AgentResult = (
            results[1] if isinstance(results[1], AgentResult)
            else AgentResult(agent_type="code_review", status="failed", error=str(results[1]))
        )
        security_res: AgentResult = (
            results[2] if isinstance(results[2], AgentResult)
            else AgentResult(agent_type="security_agent", status="failed", error=str(results[2]))
        )

        # 7. Persist AgentRun records
        async with session_maker() as db:
            for res in (understanding_res, review_res, security_res):
                agent_run = AgentRun(
                    review_id=review_id,
                    agent_type=res.agent_type,
                    status=res.status,
                    started_at=datetime.now(timezone.utc),
                    completed_at=datetime.now(timezone.utc),
                    duration_ms=res.duration_ms,
                    files_analyzed=res.files_analyzed,
                    findings_generated=len(res.findings),
                    error=res.error,
                    metadata_json=json.dumps(res.data) if res.data else None,
                )
                db.add(agent_run)
            await db.commit()

        # 8. Collect Raw Findings
        raw_finding_dicts: List[Dict[str, Any]] = []
        for sf in static_findings:
            raw_finding_dicts.append(sf.to_dict())
        for f in review_res.findings:
            raw_finding_dicts.append(f.to_dict())
        for f in security_res.findings:
            raw_finding_dicts.append(f.to_dict())
        for f in understanding_res.findings:
            raw_finding_dicts.append(f.to_dict())

        # 9. Normalize & Deduplicate Findings
        normalized = self.normalizer.normalize(raw_finding_dicts)
        deduped = self.normalizer.deduplicate(normalized)

        # 10. Calculate Deterministic Scores
        arch_risks = len(understanding_res.data.get("architecture_risks", []))
        scores = self.normalizer.calculate_scores(deduped, architecture_risks_count=arch_risks)

        # 11. Determine Final Review Status
        critical_failures = sum(
            1 for res in (understanding_res, review_res, security_res) if res.status == "failed"
        )
        if critical_failures == 0:
            final_status = "completed"
        elif critical_failures < 3:
            final_status = "completed_with_warnings"
        else:
            final_status = "failed"

        # 12. Persist Findings & Update Review in Database
        async with session_maker() as db:
            # Delete any existing findings for this review to ensure clean idempotent run
            existing_findings_res = await db.execute(
                select(Finding).where(Finding.review_id == review_id)
            )
            for old_f in existing_findings_res.scalars().all():
                await db.delete(old_f)

            # Persist canonical deduplicated findings
            for cf in deduped:
                finding_model = Finding(
                    review_id=review_id,
                    category=cf.category,
                    severity=cf.severity,
                    title=cf.title,
                    description=cf.description,
                    file_path=cf.file_path,
                    line_number=cf.start_line,
                    start_line=cf.start_line,
                    end_line=cf.end_line,
                    confidence=cf.confidence,
                    evidence=cf.evidence,
                    cwe=cf.cwe,
                    type=cf.type,
                    source=cf.source,
                    status=cf.status,
                )
                db.add(finding_model)

            # Update Review
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

        logger.info(
            f"Orchestrator completed for review {review_id[:8]}: "
            f"status={final_status} findings={len(deduped)} overall_score={scores['overall_score']}"
        )
        return final_review
