"""
Analysis job queue backed by Redis via asyncio.Queue with Redis persistence.

Architecture:
- Job IDs are enqueued to an in-process asyncio.Queue for the background worker.
- Redis is used to persist job IDs so that on restart, queued jobs are recovered.
- The worker reads from the asyncio.Queue; Redis just provides durability.

If Redis is unavailable, the queue falls back to in-process only mode
(jobs are lost on restart but still process within a single server run).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

logger = logging.getLogger("ai_code_reviewer.queue")

REDIS_QUEUE_KEY = "ai_code_reviewer:analysis_queue"


class AnalysisQueue:
    """
    Thread-safe async job queue for analysis job IDs.

    Uses asyncio.Queue as the primary in-process transport.
    Redis provides optional persistence across restarts.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._redis: Optional[object] = None  # redis.asyncio.Redis instance if available

    async def connect_redis(self, redis_url: str) -> None:
        """Attempt to connect to Redis. Silently falls back if unavailable."""
        try:
            import redis.asyncio as aioredis  # type: ignore[import-untyped]
            client = aioredis.from_url(redis_url, decode_responses=True)
            await client.ping()
            self._redis = client
            logger.info(f"Analysis queue connected to Redis at {redis_url}")
        except Exception as exc:
            logger.warning(
                f"Redis unavailable ({exc}). Using in-process queue only. "
                "Jobs will not persist across restarts."
            )
            self._redis = None

    async def enqueue(self, job_id: str) -> None:
        """
        Add a job ID to the queue.

        Persists to Redis (if connected) and puts it into the asyncio.Queue
        so the worker picks it up immediately.
        """
        if self._redis is not None:
            try:
                await self._redis.rpush(REDIS_QUEUE_KEY, job_id)  # type: ignore[union-attr]
            except Exception as exc:
                logger.warning(f"Redis enqueue failed for job {job_id}: {exc}")
        await self._queue.put(job_id)
        logger.debug(f"Enqueued analysis job: {job_id}")

    async def dequeue(self) -> str:
        """
        Block until a job ID is available and return it.
        """
        job_id = await self._queue.get()
        logger.debug(f"Dequeued analysis job: {job_id}")
        return job_id

    def task_done(self) -> None:
        """Signal that a previously dequeued job has been processed."""
        self._queue.task_done()

    async def recover_from_redis(self) -> int:
        """
        On startup, re-enqueue any job IDs that were left in Redis
        from a previous server run. Returns number of recovered jobs.
        """
        if self._redis is None:
            return 0
        try:
            recovered = 0
            while True:
                job_id = await self._redis.lpop(REDIS_QUEUE_KEY)  # type: ignore[union-attr]
                if job_id is None:
                    break
                await self._queue.put(job_id)
                recovered += 1
            if recovered:
                logger.info(f"Recovered {recovered} analysis jobs from Redis")
            return recovered
        except Exception as exc:
            logger.warning(f"Redis recovery failed: {exc}")
            return 0

    async def close(self) -> None:
        """Close Redis connection if open."""
        if self._redis is not None:
            try:
                await self._redis.aclose()  # type: ignore[union-attr]
            except Exception:
                pass
            self._redis = None


# Singleton queue instance
analysis_queue = AnalysisQueue()
