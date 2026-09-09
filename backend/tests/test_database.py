"""Tests for SQLAlchemy async models, constraints, and relationships."""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Finding, Repository, Review


@pytest.mark.anyio
async def test_database_create_and_query_repository(db_session: AsyncSession) -> None:
    repo = Repository(
        name="ai-code-reviewer",
        full_name="org/ai-code-reviewer",
        owner="org",
        default_branch="main",
        visibility="public",
        language="TypeScript",
        github_id=12345,
    )
    db_session.add(repo)
    await db_session.commit()

    result = await db_session.execute(
        select(Repository).where(Repository.full_name == "org/ai-code-reviewer")
    )
    fetched = result.scalar_one_or_none()
    assert fetched is not None
    assert fetched.name == "ai-code-reviewer"
    assert fetched.owner == "org"
    assert fetched.visibility == "public"
    assert fetched.github_id == 12345


@pytest.mark.anyio
async def test_database_relationships_and_cascade_delete(
    db_session: AsyncSession,
) -> None:
    # 1. Create Repository
    repo = Repository(
        name="backend-service",
        full_name="company/backend-service",
        owner="company",
        default_branch="main",
        visibility="private",
    )
    db_session.add(repo)
    await db_session.commit()
    await db_session.refresh(repo)

    # 2. Create Review linked to Repository
    review = Review(
        repository_id=repo.id,
        commit_sha="a1b2c3d4e5f60718293a4b5c6d7e8f9012345678",
        branch="main",
        status="completed",
        overall_score=88.5,
        security_score=92.0,
        quality_score=85.0,
    )
    db_session.add(review)
    await db_session.commit()
    await db_session.refresh(review)

    # 3. Create Finding linked to Review
    finding = Finding(
        review_id=review.id,
        category="security",
        severity="critical",
        title="Hardcoded Secret Detected",
        description="AWS access key in settings file",
        file_path="src/config.py",
        line_number=42,
        confidence=98.5,
        status="open",
    )
    db_session.add(finding)
    await db_session.commit()
    await db_session.refresh(finding)

    # Verify relationships
    review_query = await db_session.execute(
        select(Review).where(Review.id == review.id)
    )
    retrieved_review = review_query.scalar_one_or_none()
    assert retrieved_review is not None
    assert retrieved_review.repository_id == repo.id

    finding_query = await db_session.execute(
        select(Finding).where(Finding.id == finding.id)
    )
    retrieved_finding = finding_query.scalar_one_or_none()
    assert retrieved_finding is not None
    assert retrieved_finding.review_id == review.id

    # Cascade delete test: Deleting repository should cascade delete review and findings
    await db_session.delete(repo)
    await db_session.commit()

    rev_check = await db_session.execute(
        select(Review).where(Review.id == review.id)
    )
    assert rev_check.scalar_one_or_none() is None

    finding_check = await db_session.execute(
        select(Finding).where(Finding.id == finding.id)
    )
    assert finding_check.scalar_one_or_none() is None
