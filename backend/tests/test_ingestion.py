"""Tests for IngestionPipeline with mocked GitHub service."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.ingestion import IngestionPipeline, _safe_error_message
from app.models.analysis_job import AnalysisJob
from app.models.repository import Repository
from app.models.repository_snapshot import RepositorySnapshot
from app.models.review import Review
from app.schemas.github import GitHubFileContent, GitHubTreeItem
from app.services.github import (
    GitHubAuthError,
    GitHubRateLimitError,
    GitHubResourceNotFoundError,
)


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def make_tree_item(path: str, type_: str = "blob", size: int = 1024) -> GitHubTreeItem:
    return GitHubTreeItem(path=path, mode="100644", type=type_, sha="deadbeef", size=size)


def make_file_content(path: str, content: str = "print('hello')\n") -> GitHubFileContent:
    return GitHubFileContent(path=path, sha="abc", size=len(content), encoding="utf-8", content=content)


def make_mock_github(
    tree_items=None,
    file_contents=None,
    tree_error=None,
    content_error=None,
):
    """Build a mock GitHub service with configurable behaviors."""
    service = MagicMock()

    if tree_error:
        service.get_file_tree = AsyncMock(side_effect=tree_error)
    else:
        service.get_file_tree = AsyncMock(return_value=tree_items or [])

    if content_error:
        service.get_file_content = AsyncMock(side_effect=content_error)
    elif file_contents is not None:
        # Return a different file content for each path
        contents_by_path = {fc.path: fc for fc in file_contents}

        async def get_content(owner, repo, path, ref=None):
            if path in contents_by_path:
                return contents_by_path[path]
            return make_file_content(path)

        service.get_file_content = get_content
    else:
        service.get_file_content = AsyncMock(return_value=make_file_content("default.py"))

    return service


async def run_pipeline(db_session, repo, review, github_service):
    """Helper to run the ingestion pipeline and return the job."""
    # Create job
    job = AnalysisJob(
        id=str(uuid.uuid4()),
        review_id=review.id,
        status="queued",
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    from app.db.session import async_session_maker as real_session_maker
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    # Use test DB session_maker
    from tests.conftest import test_async_session_maker

    pipeline = IngestionPipeline(github_service=github_service)
    await pipeline.run(job_id=job.id, session_maker=test_async_session_maker)
    return job.id


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def repo_and_review(db_session: AsyncSession):
    """Create a repository and review in the test DB."""
    repo = Repository(
        id=str(uuid.uuid4()),
        name="test-repo",
        full_name="owner/test-repo",
        owner="owner",
        default_branch="main",
        visibility="public",
    )
    db_session.add(repo)
    await db_session.flush()

    review = Review(
        id=str(uuid.uuid4()),
        repository_id=repo.id,
        commit_sha="abc1234567890123456789012345678901234567",
        branch="main",
        status="queued",
    )
    db_session.add(review)
    await db_session.commit()
    await db_session.refresh(repo)
    await db_session.refresh(review)
    return repo, review


# ---------------------------------------------------------------------------
# Pipeline tests
# ---------------------------------------------------------------------------

class TestIngestionPipeline:
    async def test_empty_repository_completes(self, db_session: AsyncSession, repo_and_review):
        """An empty repository (no files) should complete successfully."""
        repo, review = repo_and_review
        github = make_mock_github(tree_items=[])
        job_id = await run_pipeline(db_session, repo, review, github)

        from sqlalchemy import select
        from tests.conftest import test_async_session_maker
        async with test_async_session_maker() as s:
            from sqlalchemy import select
            job_res = await s.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
            job = job_res.scalar_one()
            assert job.status == "completed"
            assert job.progress == 100.0

    async def test_empty_repo_creates_snapshot(self, db_session: AsyncSession, repo_and_review):
        """Even an empty repo should create a snapshot record."""
        repo, review = repo_and_review
        github = make_mock_github(tree_items=[])
        job_id = await run_pipeline(db_session, repo, review, github)

        from sqlalchemy import select
        from tests.conftest import test_async_session_maker
        async with test_async_session_maker() as s:
            snap_res = await s.execute(
                select(RepositorySnapshot).where(RepositorySnapshot.review_id == review.id)
            )
            snap = snap_res.scalar_one()
            assert snap is not None
            assert snap.total_files == 0

    async def test_python_files_ingested(self, db_session: AsyncSession, repo_and_review):
        """Python source files should be processed and counted."""
        repo, review = repo_and_review
        tree = [
            make_tree_item("app/main.py"),
            make_tree_item("app/utils.py"),
            make_tree_item("tests/test_main.py"),
            make_tree_item("requirements.txt", size=200),
        ]
        file_contents = [
            make_file_content("app/main.py", "from fastapi import FastAPI\napp = FastAPI()\n"),
            make_file_content("app/utils.py", "def helper(): pass\n"),
            make_file_content("tests/test_main.py", "import pytest\ndef test_x(): pass\n"),
            make_file_content("requirements.txt", "fastapi==0.115.0\npytest\n"),
        ]
        github = make_mock_github(tree_items=tree, file_contents=file_contents)
        job_id = await run_pipeline(db_session, repo, review, github)

        from sqlalchemy import select
        from tests.conftest import test_async_session_maker
        async with test_async_session_maker() as s:
            snap_res = await s.execute(
                select(RepositorySnapshot).where(RepositorySnapshot.review_id == review.id)
            )
            snap = snap_res.scalar_one()
            assert snap.total_files == 4
            assert snap.total_lines > 0
            # Verify language detection ran
            import json
            langs = json.loads(snap.languages)
            assert "Python" in langs

    async def test_directory_tree_items_excluded(self, db_session: AsyncSession, repo_and_review):
        """Tree items of type 'tree' (directories) should not be fetched as files."""
        repo, review = repo_and_review
        tree = [
            make_tree_item("src", type_="tree"),      # directory → skip
            make_tree_item("src/main.py", type_="blob"),
        ]
        github = make_mock_github(tree_items=tree)
        job_id = await run_pipeline(db_session, repo, review, github)

        from sqlalchemy import select
        from tests.conftest import test_async_session_maker
        async with test_async_session_maker() as s:
            snap_res = await s.execute(
                select(RepositorySnapshot).where(RepositorySnapshot.review_id == review.id)
            )
            snap = snap_res.scalar_one()
            assert snap.total_files == 1  # only blob

    async def test_binary_files_excluded(self, db_session: AsyncSession, repo_and_review):
        """Binary files should be excluded by the file filter."""
        repo, review = repo_and_review
        tree = [
            make_tree_item("src/main.py"),
            make_tree_item("assets/logo.png"),
            make_tree_item("dist/bundle.js"),  # in excluded dir
        ]
        github = make_mock_github(tree_items=tree)
        job_id = await run_pipeline(db_session, repo, review, github)

        from sqlalchemy import select
        from tests.conftest import test_async_session_maker
        async with test_async_session_maker() as s:
            snap_res = await s.execute(
                select(RepositorySnapshot).where(RepositorySnapshot.review_id == review.id)
            )
            snap = snap_res.scalar_one()
            # Only main.py should pass the filter
            assert snap.total_files == 1

    async def test_github_auth_error_fails_job(self, db_session: AsyncSession, repo_and_review):
        """A GitHub auth error should mark the job as failed with a safe message."""
        repo, review = repo_and_review
        github = make_mock_github(tree_error=GitHubAuthError())
        job_id = await run_pipeline(db_session, repo, review, github)

        from sqlalchemy import select
        from tests.conftest import test_async_session_maker
        async with test_async_session_maker() as s:
            job_res = await s.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
            job = job_res.scalar_one()
            assert job.status == "failed"
            assert "authentication" in job.error.lower()

    async def test_github_rate_limit_fails_job(self, db_session: AsyncSession, repo_and_review):
        """A GitHub rate limit error should fail with appropriate message."""
        repo, review = repo_and_review
        github = make_mock_github(tree_error=GitHubRateLimitError())
        job_id = await run_pipeline(db_session, repo, review, github)

        from sqlalchemy import select
        from tests.conftest import test_async_session_maker
        async with test_async_session_maker() as s:
            job_res = await s.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
            job = job_res.scalar_one()
            assert job.status == "failed"
            assert "rate limit" in job.error.lower()

    async def test_failed_content_fetch_handled_gracefully(self, db_session: AsyncSession, repo_and_review):
        """Individual file content fetch failures should not crash the pipeline."""
        repo, review = repo_and_review
        tree = [make_tree_item("src/main.py"), make_tree_item("src/broken.py")]

        async def flaky_content(owner, repo_name, path, ref=None):
            if "broken" in path:
                raise GitHubResourceNotFoundError()
            return make_file_content(path)

        github = MagicMock()
        github.get_file_tree = AsyncMock(return_value=tree)
        github.get_file_content = flaky_content

        job_id = await run_pipeline(db_session, repo, review, github)

        from sqlalchemy import select
        from tests.conftest import test_async_session_maker
        async with test_async_session_maker() as s:
            job_res = await s.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
            job = job_res.scalar_one()
            # Should still complete despite partial failures
            assert job.status == "completed"
            snap_res = await s.execute(
                select(RepositorySnapshot).where(RepositorySnapshot.review_id == review.id)
            )
            snap = snap_res.scalar_one()
            assert snap.total_files == 2  # Both files counted


# Async functions to match module-level pytestmark
async def test_safe_error_rate_limit():
    msg = _safe_error_message(GitHubRateLimitError())
    assert "rate limit" in msg.lower()


async def test_safe_error_auth():
    msg = _safe_error_message(GitHubAuthError())
    assert "authentication" in msg.lower()


async def test_safe_error_not_found():
    msg = _safe_error_message(GitHubResourceNotFoundError())
    assert "not found" in msg.lower()


async def test_safe_error_generic():
    msg = _safe_error_message(RuntimeError("some internal error"))
    assert "unexpected error" in msg.lower()
    assert "internal error" not in msg.lower()  # Safe — no internal details
