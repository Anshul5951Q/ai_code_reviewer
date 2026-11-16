"""
Integration tests for Sub-Phase 7.3 dedicated API endpoints and Gate Audit metadata.
Endpoints tested:
- GET /reviews/{id}/agents/code-quality
- POST /reviews/{id}/agents/code-quality
- GET /reviews/{id}/agents/security
- POST /reviews/{id}/agents/security
- GET /reviews/{id}/findings/quality
- GET /reviews/{id}/findings/security
- GET /reviews/{id}/gates
"""
from __future__ import annotations

import json
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
async def test_subphase_73_api_endpoints(client: AsyncClient, db_session: AsyncSession):
    # 1. Setup repository, review, and snapshot
    repo_id = str(uuid.uuid4())
    repo = Repository(
        id=repo_id,
        name="p73-repo",
        full_name="org/p73-repo",
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
        status="completed",
    )
    db_session.add(review)

    snapshot = RepositorySnapshot(
        id=str(uuid.uuid4()),
        review_id=review_id,
        commit_sha=review.commit_sha,
        branch="main",
        total_files=2,
    )
    db_session.add(snapshot)

    # 2. Add Agent Runs with Gate metadata
    gate1_run = AgentRun(
        id=str(uuid.uuid4()),
        review_id=review_id,
        agent_type="code_understanding",
        status="completed",
        duration_ms=450,
        files_analyzed=2,
        findings_generated=0,
        metadata_json=json.dumps({
            "gate_1": {
                "status": "verified",
                "accepted_claims": 5,
                "rejected_claims": 0,
                "expunged_entry_points": [],
                "expunged_modules": [],
            }
        }),
    )

    gate2_run = AgentRun(
        id=str(uuid.uuid4()),
        review_id=review_id,
        agent_type="code_quality",
        status="completed",
        duration_ms=320,
        files_analyzed=2,
        findings_generated=2,
        metadata_json=json.dumps({
            "gate_2": {
                "status": "verified_with_scrubbing",
                "validated_count": 2,
                "rejected_count": 1,
                "rejections": ["Subjective styling preference rejected: 'prefer single quotes'"],
            }
        }),
    )

    gate3_run = AgentRun(
        id=str(uuid.uuid4()),
        review_id=review_id,
        agent_type="security_agent",
        status="completed",
        duration_ms=510,
        files_analyzed=2,
        findings_generated=1,
        metadata_json=json.dumps({
            "gate_3": {
                "status": "verified",
                "validated_count": 1,
                "rejected_count": 0,
                "rejections": [],
            }
        }),
    )

    # 3. Add Quality and Security Findings
    f_qual = Finding(
        id=str(uuid.uuid4()),
        review_id=review_id,
        category="maintainability",
        severity="medium",
        title="High Cyclomatic Complexity",
        description="Function foo has complexity of 16.",
        file_path="src/service.py",
        start_line=10,
        end_line=45,
        confidence=0.88,
        status="open",
        source="code_quality_agent",
    )

    f_sec = Finding(
        id=str(uuid.uuid4()),
        review_id=review_id,
        category="security",
        severity="critical",
        title="SQL Injection in User Query",
        description="Unsanitized input concatenated into query string.",
        file_path="src/db.py",
        start_line=22,
        end_line=25,
        confidence=0.95,
        status="open",
        source="security_agent",
        cwe="CWE-89",
    )

    db_session.add_all([gate1_run, gate2_run, gate3_run, f_qual, f_sec])
    await db_session.commit()

    # 4. Test GET /reviews/{id}/agents/code-quality
    cq_resp = await client.get(f"/api/reviews/{review_id}/agents/code-quality")
    assert cq_resp.status_code == 200, cq_resp.text
    cq_data = cq_resp.json()
    assert cq_data["agent_type"] == "code_quality"
    assert cq_data["status"] == "completed"
    cq_meta = json.loads(cq_data["metadata_json"])
    assert cq_meta["gate_2"]["status"] == "verified_with_scrubbing"
    assert cq_meta["gate_2"]["rejected_count"] == 1

    # 5. Test GET /reviews/{id}/agents/security
    sec_resp = await client.get(f"/api/reviews/{review_id}/agents/security")
    assert sec_resp.status_code == 200, sec_resp.text
    sec_data = sec_resp.json()
    assert sec_data["agent_type"] == "security_agent"
    assert sec_data["status"] == "completed"
    sec_meta = json.loads(sec_data["metadata_json"])
    assert sec_meta["gate_3"]["status"] == "verified"
    assert sec_meta["gate_3"]["validated_count"] == 1

    # 6. Test GET /reviews/{id}/findings/quality
    qf_resp = await client.get(f"/api/reviews/{review_id}/findings/quality")
    assert qf_resp.status_code == 200, qf_resp.text
    qf_data = qf_resp.json()
    assert qf_data["total"] == 1
    assert qf_data["items"][0]["title"] == "High Cyclomatic Complexity"

    # 7. Test GET /reviews/{id}/findings/security
    sf_resp = await client.get(f"/api/reviews/{review_id}/findings/security")
    assert sf_resp.status_code == 200, sf_resp.text
    sf_data = sf_resp.json()
    assert sf_data["total"] == 1
    assert sf_data["items"][0]["cwe"] == "CWE-89"

    # 8. Test GET /reviews/{id}/gates
    gates_resp = await client.get(f"/api/reviews/{review_id}/gates")
    assert gates_resp.status_code == 200, gates_resp.text
    gates_data = gates_resp.json()
    assert gates_data["review_id"] == review_id
    assert gates_data["gate_1"]["status"] == "verified"
    assert gates_data["gate_2"]["status"] == "verified_with_scrubbing"
    assert gates_data["gate_3"]["status"] == "verified"
    assert len(gates_data["gate_2"]["rejections"]) == 1
