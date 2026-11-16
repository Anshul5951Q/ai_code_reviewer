"""
Regression and verification test suite for Review Routing and Analysis Flow Bug Fix.

Validates:
1. Review creation generates and returns a valid UUID string ID (never undefined / empty).
2. Querying reviews, analysis jobs, agents, and findings with invalid/undefined IDs cleanly returns 404.
3. Querying with valid review IDs returns valid 200 responses.
4. Single analysis entry point (POST /api/reviews/{review_id}/analyze) validates review ID existence
   and starts ingestion/analysis idempotently.
5. End-to-end flow from review creation to analysis triggering and status polling.
"""
from __future__ import annotations

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.repository import Repository
from app.models.review import Review
from app.models.analysis_job import AnalysisJob
from app.schemas.analysis import PipelineStage


@pytest.fixture
async def sample_repo(db_session: AsyncSession) -> Repository:
    """Create a sample repository in test DB."""
    repo = Repository(
        id=str(uuid.uuid4()),
        name="secure-repo",
        full_name="test-org/secure-repo",
        owner="test-org",
        default_branch="main",
        visibility="public",
    )
    db_session.add(repo)
    await db_session.commit()
    await db_session.refresh(repo)
    return repo


@pytest.mark.asyncio
async def test_review_creation_returns_valid_uuid(
    client: AsyncClient,
    sample_repo: Repository,
) -> None:
    """Verify that creating a review returns a non-empty, valid UUID id."""
    payload = {
        "repository_id": sample_repo.id,
        "commit_sha": "a1b2c3d4e5f60718293a4b5c6d7e8f9a0b1c2d3e",
        "branch": "main",
    }
    response = await client.post("/api/reviews", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert "id" in data
    review_id = data["id"]
    assert review_id is not None
    assert isinstance(review_id, str)
    assert review_id != "undefined"
    assert len(review_id) > 0
    # Must parse as valid UUID
    parsed_uuid = uuid.UUID(review_id)
    assert str(parsed_uuid) == review_id
    assert data["repository_id"] == sample_repo.id
    assert data["status"] == "queued"


@pytest.mark.asyncio
async def test_review_endpoints_reject_undefined_and_invalid_ids(
    client: AsyncClient,
) -> None:
    """
    Ensure all review-related endpoints return 404 when given 'undefined'
    or non-existent IDs, preventing downstream cascading errors.
    """
    invalid_ids = ["undefined", "null", "non-existent-uuid-12345"]

    for invalid_id in invalid_ids:
        # GET /api/reviews/{id}
        resp = await client.get(f"/api/reviews/{invalid_id}")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

        # GET /api/reviews/{id}/analysis
        resp_analysis = await client.get(f"/api/reviews/{invalid_id}/analysis")
        assert resp_analysis.status_code == 404

        # GET /api/reviews/{id}/agents
        resp_agents = await client.get(f"/api/reviews/{invalid_id}/agents")
        assert resp_agents.status_code == 404

        # GET /api/reviews/{id}/findings
        resp_findings = await client.get(f"/api/reviews/{invalid_id}/findings")
        assert resp_findings.status_code == 404

        # POST /api/reviews/{id}/analyze
        resp_start = await client.post(f"/api/reviews/{invalid_id}/analyze")
        assert resp_start.status_code == 404


@pytest.mark.asyncio
async def test_single_analysis_trigger_and_status_flow(
    client: AsyncClient,
    sample_repo: Repository,
) -> None:
    """
    Verify complete review creation -> analyze trigger -> status check flow
    with valid IDs.
    """
    # 1. Create review
    create_resp = await client.post(
        "/api/reviews",
        json={
            "repository_id": sample_repo.id,
            "commit_sha": "f0e1d2c3b4a5968778695a4b3c2d1e0f1a2b3c4d",
            "branch": "main",
        },
    )
    assert create_resp.status_code == 201
    review = create_resp.json()
    review_id = review["id"]

    # 2. Query review details
    get_resp = await client.get(f"/api/reviews/{review_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == review_id

    # 3. Trigger unified analysis pipeline
    analyze_resp = await client.post(f"/api/reviews/{review_id}/analyze")
    assert analyze_resp.status_code == 202
    job_data = analyze_resp.json()
    assert job_data["review_id"] == review_id
    assert "job_id" in job_data
    job_id = job_data["job_id"]
    assert job_id is not None
    assert job_id != "undefined"

    # 4. Check analysis status
    status_resp = await client.get(f"/api/reviews/{review_id}/analysis")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["id"] == job_id
    assert status_data["review_id"] == review_id

    # 5. Idempotent re-trigger returns existing active job
    retrigger_resp = await client.post(f"/api/reviews/{review_id}/analyze")
    assert retrigger_resp.status_code == 202
    retrigger_data = retrigger_resp.json()
    assert retrigger_data["job_id"] == job_id
    assert "already in progress" in retrigger_data["message"].lower()

    # 6. Check findings and agents endpoints respond cleanly with valid ID
    findings_resp = await client.get(f"/api/reviews/{review_id}/findings")
    assert findings_resp.status_code == 200
    assert "items" in findings_resp.json()

    agents_resp = await client.get(f"/api/reviews/{review_id}/agents")
    assert agents_resp.status_code == 200
    assert "agents" in agents_resp.json()
