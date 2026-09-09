"""
Tests for Phase 6 Remediation REST API endpoints.
"""
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finding import Finding
from app.models.remediation_run import RemediationRun
from app.models.review import Review


@pytest.mark.asyncio
async def test_remediate_finding_api_404(client: AsyncClient):
    resp = await client.post(f"/api/findings/{uuid.uuid4()}/remediate")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_remediate_finding_api_success(
    client: AsyncClient,
    db_session: AsyncSession,
):
    review_id = str(uuid.uuid4())
    finding_id = str(uuid.uuid4())

    review = Review(
        id=review_id,
        repository_id="fake-repo",
        commit_sha="123456",
        branch="main",
        status="completed",
    )
    db_session.add(review)

    finding = Finding(
        id=finding_id,
        review_id=review_id,
        category="security",
        severity="high",
        title="SQL Injection",
        file_path="src/api/users.py",
        status="open",
    )
    db_session.add(finding)
    await db_session.commit()

    resp = await client.post(f"/api/findings/{finding_id}/remediate?wait=true")
    assert resp.status_code == 201
    data = resp.json()
    assert data["finding_id"] == finding_id
    assert data["status"] in ["queued", "completed"]


@pytest.mark.asyncio
async def test_remediate_finding_conflict_if_already_running(
    client: AsyncClient,
    db_session: AsyncSession,
):
    review_id = str(uuid.uuid4())
    finding_id = str(uuid.uuid4())

    review = Review(
        id=review_id,
        repository_id="fake-repo",
        commit_sha="123456",
        branch="main",
        status="completed",
    )
    db_session.add(review)

    finding = Finding(
        id=finding_id,
        review_id=review_id,
        category="security",
        severity="high",
        title="SQL Injection",
        file_path="src/api/users.py",
        status="remediation_in_progress",
    )
    db_session.add(finding)

    active_run = RemediationRun(
        id=str(uuid.uuid4()),
        review_id=review_id,
        finding_id=finding_id,
        status="generating",
    )
    db_session.add(active_run)
    await db_session.commit()

    resp = await client.post(f"/api/findings/{finding_id}/remediate")
    assert resp.status_code == 409
    assert "already in progress" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_remediation_result_and_history_api(
    client: AsyncClient,
    db_session: AsyncSession,
):
    review_id = str(uuid.uuid4())
    finding_id = str(uuid.uuid4())
    rem_id = str(uuid.uuid4())

    review = Review(
        id=review_id,
        repository_id="fake-repo",
        commit_sha="123456",
        branch="main",
        status="completed",
    )
    db_session.add(review)

    finding = Finding(
        id=finding_id,
        review_id=review_id,
        category="security",
        severity="high",
        title="SQL Injection",
        file_path="src/api/users.py",
        status="resolved",
    )
    db_session.add(finding)

    meta_json = (
        '{"strategy": "Parameterized query", "explanation": "Binds parameter", '
        '"diff": "--- a\\n+++ b", "changes": [], "remediation_confidence": 0.95, '
        '"verification_confidence": 0.96, "verification_reason": "Secure", "attempt_number": 1}'
    )

    run = RemediationRun(
        id=rem_id,
        review_id=review_id,
        finding_id=finding_id,
        status="completed",
        verification_status="resolved",
        metadata_json=meta_json,
    )
    db_session.add(run)
    await db_session.commit()

    # 1. Get status
    resp_status = await client.get(f"/api/remediations/{rem_id}")
    assert resp_status.status_code == 200
    assert resp_status.json()["status"] == "completed"

    # 2. Get result
    resp_result = await client.get(f"/api/remediations/{rem_id}/result")
    assert resp_result.status_code == 200
    res_data = resp_result.json()
    assert res_data["strategy"] == "Parameterized query"
    assert res_data["verification_status"] == "resolved"

    # 3. Get verification
    resp_ver = await client.get(f"/api/remediations/{rem_id}/verification")
    assert resp_ver.status_code == 200
    assert resp_ver.json()["status"] == "resolved"

    # 4. Get history
    resp_hist = await client.get(f"/api/findings/{finding_id}/remediations")
    assert resp_hist.status_code == 200
    hist_data = resp_hist.json()
    assert hist_data["total_attempts"] == 1
    assert hist_data["can_retry"] is True
