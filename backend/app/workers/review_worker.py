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
from app.services.github import get_github_service
from app.workers.queue import analysis_queue

logger = logging.getLogger("ai_code_reviewer.worker")


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
        async with self._semaphore:
            logger.info(f"Worker processing job: {job_id[:8]}...")
            try:
                github_service = get_github_service()
                pipeline = IngestionPipeline(github_service=github_service)
                await pipeline.run(
                    job_id=job_id,
                    session_maker=self._session_maker,
                )
            except Exception as exc:
                logger.error(
                    f"Worker: unhandled error for job {job_id[:8]}: {exc}",
                    exc_info=True,
                )
            finally:
                analysis_queue.task_done()


# Module-level worker instance (initialized in main.py lifespan)
_worker_instance: Optional[ReviewWorker] = None
_worker_task: Optional[asyncio.Task] = None


async def start_worker(session_maker: async_sessionmaker, max_concurrent: int = 2) -> None:
    """Start the background worker as an asyncio Task."""
    global _worker_instance, _worker_task
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
