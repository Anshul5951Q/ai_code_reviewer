"""Tests for review CRUD and findings relationships."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finding import Finding


@pytest.mark.anyio
async def test_review_lifecycle_and_findings(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # 1. Create a repository first
    repo_res = await client.post(
        "/api/repositories",
        json={
            "name": "core-api",
            "full_name": "company/core-api",
            "owner": "company",
            "default_branch": "main",
            "visibility": "private",
        },
    )
    assert repo_res.status_code == 201
    repo_id = repo_res.json()["id"]

    # 2. Create review with invalid repository -> 404
    bad_res = await client.post(
        "/api/reviews",
        json={
            "repository_id": "non-existent-repo-id",
            "commit_sha": "abc1234567890abcdef1234567890abcdef1234",
            "branch": "main",
        },
    )
    assert bad_res.status_code == 404

    # 3. Create real review
    rev_res = await client.post(
        "/api/reviews",
        json={
            "repository_id": repo_id,
            "commit_sha": "abc1234567890abcdef1234567890abcdef1234",
            "branch": "feature/auth",
        },
    )
    assert rev_res.status_code == 201
    review = rev_res.json()
    assert review["repository_id"] == repo_id
    assert review["status"] == "queued"
    assert review["commit_sha"] == "abc1234567890abcdef1234567890abcdef1234"
    review_id = review["id"]

    # 4. Get review by ID
    get_rev = await client.get(f"/api/reviews/{review_id}")
    assert get_rev.status_code == 200
    assert get_rev.json()["id"] == review_id

    # 5. List reviews by repository_id and status
    filtered_list = await client.get(
        f"/api/reviews?repository_id={repo_id}&status=queued"
    )
    assert filtered_list.status_code == 200
    assert filtered_list.json()["total"] == 1
    assert filtered_list.json()["items"][0]["id"] == review_id

    # 6. Add findings directly to database to verify findings endpoint
    finding1 = Finding(
        review_id=review_id,
        category="security",
        severity="critical",
        title="SQL Injection Vulnerability",
        description="Raw string formatting in SQL statement",
        file_path="app/db/query.py",
        line_number=54,
        confidence=95.0,
        status="open",
    )
    finding2 = Finding(
        review_id=review_id,
        category="quality",
        severity="medium",
        title="High Cyclomatic Complexity",
        description="Function has complexity 24",
        file_path="app/core/utils.py",
        line_number=110,
        confidence=80.0,
        status="open",
    )
    db_session.add_all([finding1, finding2])
    await db_session.commit()

    # 7. Get findings for review
    findings_res = await client.get(f"/api/reviews/{review_id}/findings")
    assert findings_res.status_code == 200
    fdata = findings_res.json()
    assert fdata["total"] == 2
    assert len(fdata["items"]) == 2

    # 8. Filter findings by severity
    crit_res = await client.get(
        f"/api/reviews/{review_id}/findings?severity=critical"
    )
    assert crit_res.status_code == 200
    assert crit_res.json()["total"] == 1
    assert crit_res.json()["items"][0]["severity"] == "critical"


@pytest.mark.anyio
async def test_review_not_found(client: AsyncClient) -> None:
    res = await client.get("/api/reviews/non-existent-id")
    assert res.status_code == 404

    f_res = await client.get("/api/reviews/non-existent-id/findings")
    assert f_res.status_code == 404
