"""Tests for security findings and aggregated summary endpoint."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Finding, Repository, Review


@pytest.mark.anyio
async def test_security_summary_aggregation(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # 1. Empty summary
    initial_summary = await client.get("/api/security/summary")
    assert initial_summary.status_code == 200
    assert initial_summary.json()["critical_count"] == 0
    assert initial_summary.json()["repositories_analyzed"] == 0

    # 2. Setup repo, review, and findings
    repo = Repository(
        name="auth-service",
        full_name="org/auth-service",
        owner="org",
        default_branch="main",
        visibility="private",
    )
    db_session.add(repo)
    await db_session.commit()
    await db_session.refresh(repo)

    review = Review(
        repository_id=repo.id,
        commit_sha="11223344556677889900aabbccddeeff11223344",
        branch="main",
        status="completed",
        security_score=82.4,
    )
    db_session.add(review)
    await db_session.commit()
    await db_session.refresh(review)

    findings = [
        Finding(
            review_id=review.id,
            category="security",
            severity="critical",
            title="Insecure Deserialization",
            status="open",
        ),
        Finding(
            review_id=review.id,
            category="security",
            severity="high",
            title="Weak Password Policy",
            status="open",
        ),
        Finding(
            review_id=review.id,
            category="security",
            severity="medium",
            title="Missing Rate Limiter",
            status="resolved",
        ),
    ]
    db_session.add_all(findings)
    await db_session.commit()

    # 3. Check updated security summary
    summary_res = await client.get("/api/security/summary")
    assert summary_res.status_code == 200
    data = summary_res.json()
    assert data["critical_count"] == 1
    assert data["high_count"] == 1
    assert data["medium_count"] == 0  # Since it's resolved, open count for medium is 0
    assert data["resolved_count"] == 1
    assert data["open_count"] == 2
    assert data["repositories_analyzed"] == 1
    assert data["overall_score"] == 82.4

    # 4. Check global findings endpoint
    all_findings = await client.get("/api/security/findings")
    assert all_findings.status_code == 200
    assert all_findings.json()["total"] == 3

    crit_only = await client.get("/api/security/findings?severity=critical")
    assert crit_only.status_code == 200
    assert crit_only.json()["total"] == 1
