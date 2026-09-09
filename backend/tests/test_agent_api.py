"""
Integration tests for Phase 5 API endpoints (/reviews/{id}/run, /agents, /findings).
"""
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_run import AgentRun
from app.models.finding import Finding
from app.models.repository import Repository
from app.models.repository_snapshot import RepositorySnapshot
from app.models.review import Review


@pytest.mark.asyncio
async def test_run_review_analysis_api(client: AsyncClient, db_session: AsyncSession):
    # Setup test data
    repo_id = str(uuid.uuid4())
    repo = Repository(
        id=repo_id,
        name="api-repo",
        full_name="org/api-repo",
        owner="org",
        default_branch="main",
        visibility="public",
    )
    db_session.add(repo)

    review_id = str(uuid.uuid4())
    review = Review(
        id=review_id,
        repository_id=repo_id,
        commit_sha="abcdef1234567890abcdef1234567890abcdef12",
        branch="main",
        status="ready_for_analysis",
    )
    db_session.add(review)

    snapshot = RepositorySnapshot(
        review_id=review_id,
        commit_sha=review.commit_sha,
        branch="main",
        total_files=2,
    )
    db_session.add(snapshot)
    await db_session.commit()

    # Trigger analysis with wait=true for synchronous test verification
    resp = await client.post(f"/api/reviews/{review_id}/run?wait=true")
    assert resp.status_code == 202, resp.text
    data = resp.json()
    assert data["review_id"] == review_id
    assert data["status"] == "completed"

    # Query agents
    agents_resp = await client.get(f"/api/reviews/{review_id}/agents")
    assert agents_resp.status_code == 200
    agents_data = agents_resp.json()
    assert "agents" in agents_data
    assert len(agents_data["agents"]) >= 3

    # Query findings
    findings_resp = await client.get(f"/api/reviews/{review_id}/findings")
    assert findings_resp.status_code == 200
    findings_data = findings_resp.json()
    assert "items" in findings_data
    assert "total" in findings_data


@pytest.mark.asyncio
async def test_run_review_analysis_404(client: AsyncClient):
    resp = await client.post(f"/api/reviews/{uuid.uuid4()}/run")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_run_review_analysis_missing_snapshot(client: AsyncClient, db_session: AsyncSession):
    review_id = str(uuid.uuid4())
    review = Review(
        id=review_id,
        repository_id="fake",
        commit_sha="123",
        branch="main",
        status="queued",
    )
    db_session.add(review)
    await db_session.commit()

    resp = await client.post(f"/api/reviews/{review_id}/run")
    assert resp.status_code == 400
    assert "Repository snapshot not found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_run_review_analysis_conflict(client: AsyncClient, db_session: AsyncSession):
    review_id = str(uuid.uuid4())
    review = Review(
        id=review_id,
        repository_id="fake",
        commit_sha="123",
        branch="main",
        status="running",  # Already running
    )
    db_session.add(review)

    snapshot = RepositorySnapshot(
        review_id=review_id,
        commit_sha="123",
        branch="main",
    )
    db_session.add(snapshot)
    await db_session.commit()

    resp = await client.post(f"/api/reviews/{review_id}/run")
    assert resp.status_code == 409
    assert "already in progress" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_review_findings_filters(client: AsyncClient, db_session: AsyncSession):
    review_id = str(uuid.uuid4())
    review = Review(
        id=review_id,
        repository_id="fake",
        commit_sha="123",
        branch="main",
        status="completed",
    )
    db_session.add(review)

    f1 = Finding(
        id=str(uuid.uuid4()),
        review_id=review_id,
        category="security",
        severity="critical",
        title="Critical Vulnerability",
        file_path="src/auth.py",
        start_line=10,
        confidence=0.95,
        status="open",
    )
    f2 = Finding(
        id=str(uuid.uuid4()),
        review_id=review_id,
        category="quality",
        severity="low",
        title="Minor Code Smell",
        file_path="src/util.py",
        start_line=50,
        confidence=0.7,
        status="open",
    )
    db_session.add_all([f1, f2])
    await db_session.commit()

    # Filter by severity
    resp_crit = await client.get(f"/api/reviews/{review_id}/findings?severity=critical")
    assert resp_crit.status_code == 200
    assert resp_crit.json()["total"] == 1
    assert resp_crit.json()["items"][0]["title"] == "Critical Vulnerability"

    # Filter by category
    resp_qual = await client.get(f"/api/reviews/{review_id}/findings?category=quality")
    assert resp_qual.status_code == 200
    assert resp_qual.json()["total"] == 1
    assert resp_qual.json()["items"][0]["title"] == "Minor Code Smell"

    # Filter by file path
    resp_file = await client.get(f"/api/reviews/{review_id}/findings?file_path=auth")
    assert resp_file.status_code == 200
    assert resp_file.json()["total"] == 1
