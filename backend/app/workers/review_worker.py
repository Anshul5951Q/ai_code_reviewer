"""
Background review worker.

Continuously dequeues analysis job IDs and runs the IngestionPipeline
for each one. Designed for long-running operation as an asyncio Task
started during FastAPI app lifespan.

Concurrency is controlled by a semaphore to limit parallel GitHub API calls.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.analysis.ingestion import IngestionPipeline
from app.github.service import GitHubService, get_default_github_service
from app.workers.queue import analysis_queue

logger = logging.getLogger("ai_code_reviewer.worker")


async def resolve_worker_github_service(session_maker: async_sessionmaker, job_id: str):
    """
    Resolve authenticated GitHubService using server token or user's stored OAuth token.
    Prevents unauthenticated rate limits during background ingestion.
    """
    from app.core.config import settings
    if settings.github_token:
        return GitHubService(token=settings.github_token)

    try:
        from sqlalchemy import select
        from app.models.analysis_job import AnalysisJob
        from app.models.review import Review
        from app.models.repository import Repository
        from app.models.github_connection import GitHubConnection
        from app.core.encryption import decrypt_token

        async with session_maker() as db:
            job_res = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
            job = job_res.scalar_one_or_none()
            if job:
                rev_res = await db.execute(select(Review).where(Review.id == job.review_id))
                rev = rev_res.scalar_one_or_none()
                if rev:
                    repo_res = await db.execute(select(Repository).where(Repository.id == rev.repository_id))
                    repo = repo_res.scalar_one_or_none()
                    owner = repo.owner if repo else None
                    if owner:
                        conn_res = await db.execute(
                            select(GitHubConnection)
                            .where(GitHubConnection.github_login == owner)
                            .order_by(GitHubConnection.updated_at.desc())
                        )
                        conn = conn_res.scalar_one_or_none()
                        if conn and conn.access_token_encrypted:
                            tok = decrypt_token(conn.access_token_encrypted)
                            return GitHubService(token=tok)

                    # Fallback to any active connection
                    any_conn_res = await db.execute(
                        select(GitHubConnection).order_by(GitHubConnection.updated_at.desc())
                    )
                    any_conn = any_conn_res.scalar_one_or_none()
                    if any_conn and any_conn.access_token_encrypted:
                        tok = decrypt_token(any_conn.access_token_encrypted)
                        return GitHubService(token=tok)
    except Exception as exc:
        logger.warning(f"Could not resolve worker GitHub OAuth token: {exc}")

    return get_default_github_service()


class ReviewWorker:
    """
    Background worker that processes analysis jobs from the queue.

    Usage:
        worker = ReviewWorker(session_maker, max_concurrent=2)
        task = asyncio.create_task(worker.start())
        ...
        await worker.stop()
        await task
    """

    def __init__(
        self,
        session_maker: async_sessionmaker,
        max_concurrent: int = 2,
    ) -> None:
        self._session_maker = session_maker
        self._max_concurrent = max_concurrent
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(max_concurrent)
        self._running: bool = False
        self._current_tasks: set[asyncio.Task] = set()
        self._active_job_ids: set[str] = set()

    async def start(self) -> None:
        """
        Main worker loop. Runs until stop() is called.
        """
        self._running = True
        logger.info(
            f"ReviewWorker started (max_concurrent={self._max_concurrent})"
        )
        while self._running:
            try:
                # Wait for next job with a timeout so we can check _running
                job_id = await asyncio.wait_for(
                    analysis_queue.dequeue(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Worker queue error: {exc}")
                await asyncio.sleep(1.0)
                continue

            # Run job under semaphore (respects max_concurrent)
            task = asyncio.create_task(self._process_job(job_id))
            self._current_tasks.add(task)
            task.add_done_callback(self._current_tasks.discard)

        # Wait for all in-flight tasks to complete
        if self._current_tasks:
            logger.info(f"Worker shutting down — waiting for {len(self._current_tasks)} in-flight jobs")
            await asyncio.gather(*self._current_tasks, return_exceptions=True)

        logger.info("ReviewWorker stopped")

    async def stop(self) -> None:
        """Signal the worker to stop after finishing current jobs."""
        self._running = False

    async def _process_job(self, job_id: str) -> None:
        """Process a single job under the concurrency semaphore."""
        self._active_job_ids.add(job_id)
        async with self._semaphore:
            logger.info(f"Worker processing job: {job_id[:8]}...")
            try:
                github_service = await resolve_worker_github_service(self._session_maker, job_id)
                pipeline = IngestionPipeline(github_service=github_service)
                ingested_files = await pipeline.run(
                    job_id=job_id,
                    session_maker=self._session_maker,
                )

                # Seamlessly transition into multi-agent analysis for complete end-to-end review
                from sqlalchemy import select
                from app.models.analysis_job import AnalysisJob
                from app.models.review import Review
                from app.agents.orchestrator import AnalysisOrchestrator

                review_id = None
                job_status = None
                async with self._session_maker() as db:
                    job_res = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
                    job = job_res.scalar_one_or_none()
                    if job:
                        review_id = job.review_id
                        job_status = job.status

                if review_id and job_status != "failed":
                    logger.info(f"Worker advancing job {job_id[:8]} to Multi-Agent Analysis...")
                    orchestrator = AnalysisOrchestrator(github_service=github_service)
                    await orchestrator.run(
                        review_id=review_id,
                        session_maker=self._session_maker,
                        job_id=job_id,
                        files=ingested_files,
                    )
            except Exception as exc:
                logger.error(
                    f"Worker: unhandled error for job {job_id[:8]}: {exc}",
                    exc_info=True,
                )
                try:
                    from datetime import datetime, timezone
                    from app.schemas.analysis import PipelineStage
                    async with self._session_maker() as db:
                        job_res = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
                        job = job_res.scalar_one_or_none()
                        if job and not job.is_terminal:
                            job.status = "failed"
                            job.error = str(exc)
                            job.completed_at = datetime.now(timezone.utc)
                            job.current_stage = PipelineStage.FAILED
                            job.progress = 100.0

                            review_res = await db.execute(select(Review).where(Review.id == job.review_id))
                            review = review_res.scalar_one_or_none()
                            if review and review.status in ("queued", "ingesting", "running"):
                                review.status = "failed"
                            await db.commit()
                except Exception as inner_exc:
                    logger.error(f"Worker: failed to update job/review failure state: {inner_exc}")
            finally:
                self._active_job_ids.discard(job_id)
                analysis_queue.task_done()


# Module-level worker instance (initialized in main.py lifespan)
_worker_instance: Optional[ReviewWorker] = None
_worker_task: Optional[asyncio.Task] = None


def is_job_active(job_id: str) -> bool:
    """Check if a job is currently active and being processed by the worker."""
    if _worker_instance and _worker_instance._running:
        return job_id in _worker_instance._active_job_ids
    return False


async def cleanup_orphaned_jobs(session_maker: async_sessionmaker) -> int:
    """Mark any stranded jobs from previous process lifetimes as failed on startup."""
    from datetime import datetime, timezone
    from sqlalchemy import select
    from app.models.analysis_job import AnalysisJob
    from app.models.review import Review

    cleaned = 0
    try:
        async with session_maker() as db:
            res = await db.execute(
                select(AnalysisJob).where(
                    AnalysisJob.status.in_(["queued", "ingesting", "analyzing"])
                )
            )
            jobs = res.scalars().all()
            for job in jobs:
                job.status = "failed"
                job.error = "Analysis interrupted by server restart."
                job.current_stage = "FAILED"
                job.completed_at = datetime.now(timezone.utc)
                cleaned += 1

                rev_res = await db.execute(select(Review).where(Review.id == job.review_id))
                rev = rev_res.scalar_one_or_none()
                if rev and rev.status in ("queued", "ingesting", "running"):
                    rev.status = "failed"
                    rev.completed_at = datetime.now(timezone.utc)
            await db.commit()
        if cleaned:
            logger.info(f"Cleaned up {cleaned} orphaned jobs from prior server runs.")
    except Exception as exc:
        logger.warning(f"Error cleaning up orphaned jobs: {exc}")
    return cleaned


async def start_worker(session_maker: async_sessionmaker, max_concurrent: int = 2) -> None:
    """Start the background worker as an asyncio Task after cleaning stale jobs."""
    global _worker_instance, _worker_task
    await cleanup_orphaned_jobs(session_maker)
    _worker_instance = ReviewWorker(session_maker=session_maker, max_concurrent=max_concurrent)
    _worker_task = asyncio.create_task(_worker_instance.start(), name="review_worker")
    logger.info("ReviewWorker task created")


async def stop_worker() -> None:
    """Gracefully stop the background worker."""
    global _worker_instance, _worker_task
    if _worker_instance:
        await _worker_instance.stop()
    if _worker_task and not _worker_task.done():
        try:
            await asyncio.wait_for(_worker_task, timeout=10.0)
        except asyncio.TimeoutError:
            logger.warning("Worker task did not stop within timeout; cancelling")
            _worker_task.cancel()
    _worker_instance = None
    _worker_task = None
