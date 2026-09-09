"""
Repository ingestion pipeline.

Orchestrates the full ingestion workflow:
1. Fetch repository file tree from GitHub
2. Filter files (exclude binary, vendor, oversized)
3. Fetch file contents (in batches)
4. Detect languages
5. Analyze dependencies
6. Build repository intelligence
7. Create and persist snapshot
8. Update job and review status

Each stage updates the AnalysisJob record with current_stage and progress.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.analysis.dependency_analyzer import analyze_dependencies
from app.analysis.file_filter import FileFilter
from app.analysis.language_detector import detect_languages
from app.analysis.repository_intelligence import analyze_repository
from app.analysis.snapshot import build_snapshot
from app.models.analysis_job import AnalysisJob
from app.models.repository import Repository
from app.models.repository_snapshot import RepositorySnapshot
from app.models.review import Review
from app.services.github import BaseGitHubService, GitHubError

logger = logging.getLogger("ai_code_reviewer.ingestion")

# Maximum concurrent file content fetches (stay within GitHub rate limits)
MAX_CONCURRENT_FETCHES = 5

# Maximum number of files to fetch content for
MAX_FILES_TO_FETCH = 500


async def _update_job(
    db: AsyncSession,
    job: AnalysisJob,
    *,
    status: Optional[str] = None,
    stage: Optional[str] = None,
    progress: Optional[float] = None,
    files_total: Optional[int] = None,
    files_processed: Optional[int] = None,
    error: Optional[str] = None,
    started_at: Optional[datetime] = None,
    completed_at: Optional[datetime] = None,
) -> None:
    """Update job fields and commit."""
    if status is not None:
        job.status = status
    if stage is not None:
        job.current_stage = stage
    if progress is not None:
        job.progress = progress
    if files_total is not None:
        job.files_total = files_total
    if files_processed is not None:
        job.files_processed = files_processed
    if error is not None:
        job.error = error
    if started_at is not None:
        job.started_at = started_at
    if completed_at is not None:
        job.completed_at = completed_at
    await db.commit()


class IngestionPipeline:
    """
    Orchestrates repository ingestion for a single AnalysisJob.
    """

    def __init__(self, github_service: BaseGitHubService) -> None:
        self.github = github_service
        self.file_filter = FileFilter()

    async def run(
        self,
        job_id: str,
        session_maker: async_sessionmaker,
    ) -> None:
        """
        Execute the full ingestion pipeline for job_id.

        Opens its own database sessions to avoid transaction conflicts with
        the background worker. All errors are caught and stored on the job.
        """
        async with session_maker() as db:
            # Load job + review + repository
            job_res = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
            job = job_res.scalar_one_or_none()
            if job is None:
                logger.error(f"Ingestion: job {job_id!r} not found")
                return

            review_res = await db.execute(select(Review).where(Review.id == job.review_id))
            review = review_res.scalar_one_or_none()
            if review is None:
                await _update_job(
                    db, job,
                    status="failed",
                    stage="repository_fetch",
                    error="Associated review not found.",
                    completed_at=datetime.now(timezone.utc),
                )
                return

            repo_res = await db.execute(
                select(Repository).where(Repository.id == review.repository_id)
            )
            repo = repo_res.scalar_one_or_none()
            if repo is None:
                await _update_job(
                    db, job,
                    status="failed",
                    stage="repository_fetch",
                    error="Associated repository not found.",
                    completed_at=datetime.now(timezone.utc),
                )
                return

            # Mark started
            await _update_job(
                db, job,
                status="ingesting",
                stage="repository_fetch",
                progress=5.0,
                started_at=datetime.now(timezone.utc),
            )
            review.status = "ingesting"
            await db.commit()

        # Run the pipeline in a new session per stage for clean state
        try:
            await self._run_stages(job_id, session_maker, repo, review)
        except Exception as exc:
            logger.error(f"Ingestion pipeline error for job {job_id!r}: {exc}", exc_info=True)
            # Store safe error message
            safe_msg = _safe_error_message(exc)
            async with session_maker() as db:
                job_res = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
                job = job_res.scalar_one_or_none()
                if job:
                    await _update_job(
                        db, job,
                        status="failed",
                        error=safe_msg,
                        completed_at=datetime.now(timezone.utc),
                    )
                review_res = await db.execute(select(Review).where(Review.id == job.review_id))
                rev = review_res.scalar_one_or_none()
                if rev:
                    rev.status = "failed"
                    await db.commit()

    async def _run_stages(
        self,
        job_id: str,
        session_maker: async_sessionmaker,
        repo: Repository,
        review: Review,
    ) -> None:
        """Execute pipeline stages, updating job progress at each step."""
        owner, name = repo.owner, repo.name
        commit_sha = review.commit_sha
        branch = review.branch

        # ── Stage 1: Fetch repository tree ──────────────────────────────────
        logger.info(f"[Job {job_id[:8]}] Stage: repository_fetch  owner={owner} repo={name}")
        try:
            tree_items = await self.github.get_file_tree(
                owner=owner, repo=name, tree_sha=commit_sha, recursive=True
            )
        except GitHubError as exc:
            raise IngestionError(_safe_error_message(exc)) from exc

        # ── Stage 2: File filtering ──────────────────────────────────────────
        async with session_maker() as db:
            job = await _get_job(db, job_id)
            if job:
                await _update_job(db, job, stage="file_filtering", progress=15.0)

        logger.info(f"[Job {job_id[:8]}] Stage: file_filtering  tree_size={len(tree_items)}")

        # Only process blob (file) entries; skip tree (directory) entries
        blob_items = [item for item in tree_items if item.type == "blob"]
        includable = [
            item for item in blob_items
            if self.file_filter.should_include(item.path, item.size)
        ]
        # Limit number of files
        if len(includable) > MAX_FILES_TO_FETCH:
            logger.warning(
                f"[Job {job_id[:8]}] Capping files from {len(includable)} to {MAX_FILES_TO_FETCH}"
            )
            includable = includable[:MAX_FILES_TO_FETCH]

        total_files = len(includable)
        logger.info(f"[Job {job_id[:8]}] Files to fetch: {total_files}")

        async with session_maker() as db:
            job = await _get_job(db, job_id)
            if job:
                await _update_job(
                    db, job,
                    stage="content_fetch",
                    progress=25.0,
                    files_total=total_files,
                    files_processed=0,
                )

        # ── Stage 3: Fetch file contents ─────────────────────────────────────
        logger.info(f"[Job {job_id[:8]}] Stage: content_fetch")
        file_contents: Dict[str, Optional[str]] = {}
        processed = 0

        # Fetch in batches with concurrency limit
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)

        async def fetch_one(path: str) -> None:
            nonlocal processed
            async with semaphore:
                try:
                    result = await self.github.get_file_content(
                        owner=owner, repo=name, path=path, ref=commit_sha
                    )
                    file_contents[path] = result.content
                except GitHubError:
                    file_contents[path] = None
                except Exception:
                    file_contents[path] = None
                processed += 1

                # Update progress every 10 files
                if processed % 10 == 0 or processed == total_files:
                    fetch_progress = 25.0 + (processed / max(total_files, 1)) * 40.0
                    async with session_maker() as db2:
                        job2 = await _get_job(db2, job_id)
                        if job2:
                            await _update_job(
                                db2, job2,
                                progress=fetch_progress,
                                files_processed=processed,
                            )

        if includable:
            await asyncio.gather(*[fetch_one(item.path) for item in includable])
        else:
            # Empty repository
            file_contents = {}

        # ── Stage 4: Language detection ──────────────────────────────────────
        logger.info(f"[Job {job_id[:8]}] Stage: language_detection")
        async with session_maker() as db:
            job = await _get_job(db, job_id)
            if job:
                await _update_job(db, job, stage="language_detection", progress=67.0)

        all_file_paths = list(file_contents.keys())
        languages = detect_languages(all_file_paths)

        # ── Stage 5: Dependency analysis ─────────────────────────────────────
        logger.info(f"[Job {job_id[:8]}] Stage: dependency_analysis")
        async with session_maker() as db:
            job = await _get_job(db, job_id)
            if job:
                await _update_job(db, job, stage="dependency_analysis", progress=75.0)

        # Only pass files with content
        content_map = {p: c for p, c in file_contents.items() if c is not None}
        dependencies = analyze_dependencies(content_map)

        # ── Stage 6: Repository intelligence ─────────────────────────────────
        logger.info(f"[Job {job_id[:8]}] Stage: repository_intelligence")
        async with session_maker() as db:
            job = await _get_job(db, job_id)
            if job:
                await _update_job(db, job, stage="repository_intelligence", progress=85.0)

        intelligence = analyze_repository(
            filtered_files=file_contents,
            languages=languages,
            dependencies=dependencies,
        )

        # ── Stage 7: Snapshot creation ────────────────────────────────────────
        logger.info(f"[Job {job_id[:8]}] Stage: snapshot_creation")
        async with session_maker() as db:
            job = await _get_job(db, job_id)
            if job:
                await _update_job(db, job, stage="snapshot_creation", progress=92.0)

        snapshot_data = build_snapshot(
            review_id=review.id,
            commit_sha=commit_sha,
            branch=branch,
            intelligence=intelligence,
            dependencies=dependencies,
        )

        # ── Persist snapshot and complete ─────────────────────────────────────
        async with session_maker() as db:
            # Check if snapshot already exists (idempotency)
            existing_snap = await db.execute(
                select(RepositorySnapshot).where(RepositorySnapshot.review_id == review.id)
            )
            if existing_snap.scalar_one_or_none() is None:
                snap = RepositorySnapshot(**snapshot_data.to_db_kwargs())
                db.add(snap)

            job = await _get_job(db, job_id)
            review_obj = await db.execute(select(Review).where(Review.id == review.id))
            rev = review_obj.scalar_one_or_none()

            if job:
                await _update_job(
                    db, job,
                    status="completed",
                    stage="completed",
                    progress=100.0,
                    files_processed=total_files,
                    completed_at=datetime.now(timezone.utc),
                )
            if rev:
                rev.status = "ready_for_analysis"
            await db.commit()

        logger.info(
            f"[Job {job_id[:8]}] Completed: "
            f"files={total_files} languages={len(languages)} deps={len(dependencies)}"
        )


async def _get_job(db: AsyncSession, job_id: str) -> Optional[AnalysisJob]:
    """Fetch AnalysisJob by ID within a session."""
    res = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    return res.scalar_one_or_none()


def _safe_error_message(exc: Exception) -> str:
    """Convert an exception to a safe, user-facing error message."""
    from app.services.github import (
        GitHubAuthError,
        GitHubRateLimitError,
        GitHubResourceNotFoundError,
    )
    if isinstance(exc, GitHubRateLimitError):
        return "GitHub API rate limit exceeded. Please try again later."
    if isinstance(exc, GitHubAuthError):
        return "GitHub authentication failed. Please check your GITHUB_TOKEN."
    if isinstance(exc, GitHubResourceNotFoundError):
        return "Repository or commit not found on GitHub."
    if isinstance(exc, GitHubError):
        return f"GitHub API error: {exc.message}"
    if isinstance(exc, IngestionError):
        return str(exc)
    return "Repository ingestion failed due to an unexpected error."


class IngestionError(Exception):
    """Raised for pipeline-level errors with a safe user-facing message."""
