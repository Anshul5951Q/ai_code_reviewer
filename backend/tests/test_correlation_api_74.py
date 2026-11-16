"""
Integration tests for Sub-Phase 7.4 Finding Correlator & Cross-Agent Finding Intelligence.

Tests cover:
1. Deterministic and database persistence:
   - CorrelatedFinding and FindingRelationship records creation and relations.
   - Non-destructive preservation of original Finding records.
2. Full Orchestrator execution with correlation pass:
   - Finding correlator agent run metadata.
   - Auto-generation of correlated findings clusters.
3. Dedicated API endpoints:
   - POST /reviews/{id}/correlate
   - GET /reviews/{id}/correlation/status
   - GET /reviews/{id}/correlated-findings (with category/severity filters)
   - GET /reviews/{id}/correlated-findings/{cid}
   - GET /reviews/{id}/correlated-findings/{cid}/relationships
4. 404 and edge-case handling.
"""
from __future__ import annotations

import json
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import AnalysisOrchestrator
from app.analysis.finding_correlator import FindingCorrelator
from app.llm.provider import MockLLMProvider
from app.models.agent_run import AgentRun
from app.models.correlated_finding import CorrelatedFinding
from app.models.finding import Finding
from app.models.finding_relationship import FindingRelationship
from app.models.repository import Repository
from app.models.repository_snapshot import RepositorySnapshot
from app.models.review import Review
from tests.conftest import test_async_session_maker


@pytest.mark.asyncio
async def test_database_persistence_and_query(db_session: AsyncSession):
    """Verify non-destructive persistence of CorrelatedFinding and FindingRelationship."""
    repo_id = str(uuid.uuid4())
    repo = Repository(
        id=repo_id,
        name="test-repo-p74",
        full_name="org/test-repo-p74",
        owner="org",
        default_branch="main",
        visibility="public",
    )
    db_session.add(repo)

    review_id = str(uuid.uuid4())
    review = Review(
        id=review_id,
        repository_id=repo_id,
        commit_sha="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        branch="main",
        status="in_progress",
    )
    db_session.add(review)

    # Add 2 raw findings
    f1_id = str(uuid.uuid4())
    f1 = Finding(
        id=f1_id,
        review_id=review_id,
        category="security",
        type="sql_injection",
        severity="high",
        title="SQL Injection in Order Query",
        description="Unsanitized order_id interpolated into SQL statement.",
        file_path="src/orders.py",
        start_line=15,
        end_line=18,
        line_number=15,
        confidence=0.95,
        evidence="cursor.execute(f'SELECT * FROM orders WHERE id = {order_id}')",
        cwe="CWE-89",
        source="security_agent",
    )
    f2_id = str(uuid.uuid4())
    f2 = Finding(
        id=f2_id,
        review_id=review_id,
        category="maintainability",
        type="missing_validation",
        severity="medium",
        title="Missing Input Validation",
        description="order_id parameter is not validated.",
        file_path="src/orders.py",
        start_line=12,
        end_line=14,
        line_number=12,
        confidence=0.85,
        evidence="def get_order(order_id):",
        source="code_quality_agent",
    )
    db_session.add(f1)
    db_session.add(f2)
    await db_session.commit()

    # Correlate via FindingCorrelator
    correlator = FindingCorrelator(provider=MockLLMProvider())
    raw_dicts = [
        {
            "id": f1.id,
            "category": f1.category,
            "type": f1.type,
            "severity": f1.severity,
            "title": f1.title,
            "description": f1.description,
            "file_path": f1.file_path,
            "start_line": f1.start_line,
            "end_line": f1.end_line,
            "confidence": f1.confidence,
            "evidence": f1.evidence,
            "cwe": f1.cwe,
            "source": f1.source,
        },
        {
            "id": f2.id,
            "category": f2.category,
            "type": f2.type,
            "severity": f2.severity,
            "title": f2.title,
            "description": f2.description,
            "file_path": f2.file_path,
            "start_line": f2.start_line,
            "end_line": f2.end_line,
            "confidence": f2.confidence,
            "evidence": f2.evidence,
            "source": f2.source,
        },
    ]

    clusters, meta = await correlator.correlate_findings(raw_dicts)
    assert len(clusters) == 1
    assert meta["shared_root_cause_count"] >= 1

    # Persist to DB
    cf_records = await correlator.persist_correlation_results(db_session, review_id, clusters)
    await db_session.commit()

    assert len(cf_records) == 1
    stored_cf = cf_records[0]
    assert stored_cf.review_id == review_id
    assert stored_cf.category == "security"
    assert stored_cf.severity == "high"
    assert stored_cf.root_cause is not None

    # Check relations in DB
    rel_res = await db_session.execute(
        select(FindingRelationship).where(FindingRelationship.correlated_finding_id == stored_cf.id)
    )
    relationships = list(rel_res.scalars().all())
    assert len(relationships) == 2
    rel_types = {r.relationship_type for r in relationships}
    assert "shared_root_cause" in rel_types

    # Ensure original Finding records are still intact (non-destructive)
    f_res = await db_session.execute(select(Finding).where(Finding.review_id == review_id))
    raw_findings = list(f_res.scalars().all())
    assert len(raw_findings) == 2


@pytest.mark.asyncio
async def test_full_orchestrator_pipeline_with_correlation(db_session: AsyncSession):
    """Verify that full AnalysisOrchestrator run produces both raw and correlated findings."""
    repo_id = str(uuid.uuid4())
    repo = Repository(
        id=repo_id,
        name="orch-corr-repo",
        full_name="org/orch-corr-repo",
        owner="org",
        default_branch="main",
        visibility="public",
    )
    db_session.add(repo)

    review_id = str(uuid.uuid4())
    review = Review(
        id=review_id,
        repository_id=repo_id,
        commit_sha="c1d2e3f4a5b6c1d2e3f4a5b6c1d2e3f4a5b6c1d2",
        branch="main",
        status="ready_for_analysis",
    )
    db_session.add(review)

    snapshot = RepositorySnapshot(
        review_id=review_id,
        commit_sha=review.commit_sha,
        branch="main",
        total_files=2,
        source_files=2,
        languages='{"python": {"files": 2, "percentage": 100.0}}',
        frameworks='["FastAPI"]',
        dependencies='[{"name": "fastapi", "version": "0.100.0"}]',
        structure='{"entry_points": ["app/main.py"]}',
    )
    db_session.add(snapshot)
    await db_session.commit()

    files = {
        "app/main.py": (
            "from fastapi import FastAPI\n"
            "app = FastAPI()\n"
            "@app.get('/items')\n"
            "def read_items(q: str):\n"
            "    cursor.execute(f'SELECT * FROM items WHERE q = {q}')\n"
        ),
    }

    orchestrator = AnalysisOrchestrator(
        provider=MockLLMProvider(),
    )

    final_review = await orchestrator.run(
        review_id=review_id,
        session_maker=test_async_session_maker,
        files=files,
    )

    assert final_review.status == "completed"

    # Check AgentRun for finding_correlator
    runs_res = await db_session.execute(
        select(AgentRun).where(
            AgentRun.review_id == review_id,
            AgentRun.agent_type == "finding_correlator",
        )
    )
    corr_run = runs_res.scalar_one_or_none()
    assert corr_run is not None
    assert corr_run.status == "completed"
    assert corr_run.metadata_json is not None
    assert "correlated_clusters_count" in corr_run.metadata_json

    # Check CorrelatedFinding records exist
    cf_res = await db_session.execute(
        select(CorrelatedFinding).where(CorrelatedFinding.review_id == review_id)
    )
    correlated = list(cf_res.scalars().all())
    assert len(correlated) > 0


@pytest.mark.asyncio
async def test_subphase_74_api_endpoints(client: AsyncClient, db_session: AsyncSession):
    """Test all Sub-Phase 7.4 API endpoints with mock data and filters."""
    repo_id = str(uuid.uuid4())
    repo = Repository(
        id=repo_id,
        name="api-p74-repo",
        full_name="org/api-p74-repo",
        owner="org",
        default_branch="main",
        visibility="public",
    )
    db_session.add(repo)

    review_id = str(uuid.uuid4())
    review = Review(
        id=review_id,
        repository_id=repo_id,
        commit_sha="fedcba9876543210fedcba9876543210fedcba98",
        branch="main",
        status="completed",
    )
    db_session.add(review)

    # Add raw finding
    f_id = str(uuid.uuid4())
    f = Finding(
        id=f_id,
        review_id=review_id,
        category="security",
        type="injection",
        severity="critical",
        title="Command Injection in Worker",
        description="Shell execution with unescaped arguments.",
        file_path="src/worker.py",
        start_line=50,
        end_line=55,
        line_number=50,
        confidence=0.98,
        source="security_agent",
    )
    db_session.add(f)

    # Add Correlated Finding
    cf_id = str(uuid.uuid4())
    cf = CorrelatedFinding(
        id=cf_id,
        review_id=review_id,
        primary_finding_id=f_id,
        category="security",
        severity="critical",
        title="Command Injection in Worker",
        description="Shell execution with unescaped arguments.",
        file_path="src/worker.py",
        start_line=50,
        end_line=55,
        confidence=0.98,
        correlation_score=0.98,
        correlation_explanation="Cluster severity maintained at 'critical' from primary finding.",
    )
    db_session.add(cf)

    # Add Finding Relationship
    rel_id = str(uuid.uuid4())
    rel = FindingRelationship(
        id=rel_id,
        correlated_finding_id=cf_id,
        source_finding_id=f_id,
        relationship_type="independent",
        confidence=1.0,
        rationale="Independent critical issue.",
    )
    db_session.add(rel)

    # Add Agent Run for Correlator
    run = AgentRun(
        id=str(uuid.uuid4()),
        review_id=review_id,
        agent_type="finding_correlator",
        status="completed",
        findings_generated=1,
        duration_ms=120,
        metadata_json=json.dumps({
            "total_input_findings": 1,
            "correlated_clusters_count": 1,
            "exact_duplicates_count": 0,
            "overlapping_count": 0,
            "shared_root_cause_count": 0,
            "independent_count": 1,
            "semantic_evaluated": False,
        }),
    )
    db_session.add(run)
    await db_session.commit()

    # 1. GET /reviews/{id}/correlation/status
    res_status = await client.get(f"/api/reviews/{review_id}/correlation/status")
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert status_data["status"] == "completed"
    assert status_data["correlated_clusters_count"] == 1
    assert status_data["independent_count"] == 1

    # 2. GET /reviews/{id}/correlated-findings
    res_list = await client.get(f"/api/reviews/{review_id}/correlated-findings")
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert list_data["total"] == 1
    assert len(list_data["items"]) == 1
    assert list_data["items"][0]["id"] == cf_id
    assert list_data["items"][0]["severity"] == "critical"

    # 3. GET /reviews/{id}/correlated-findings with filters
    res_filtered = await client.get(f"/api/reviews/{review_id}/correlated-findings?category=security&severity=critical")
    assert res_filtered.status_code == 200
    assert res_filtered.json()["total"] == 1

    res_empty_filter = await client.get(f"/api/reviews/{review_id}/correlated-findings?severity=low")
    assert res_empty_filter.status_code == 200
    assert res_empty_filter.json()["total"] == 0

    # 4. GET /reviews/{id}/correlated-findings/{cid}
    res_single = await client.get(f"/api/reviews/{review_id}/correlated-findings/{cf_id}")
    assert res_single.status_code == 200
    single_data = res_single.json()
    assert single_data["id"] == cf_id
    assert single_data["title"] == "Command Injection in Worker"
    assert len(single_data["relationships"]) == 1
    assert single_data["relationships"][0]["source_finding_id"] == f_id
    assert single_data["relationships"][0]["source_finding"]["id"] == f_id

    # 5. GET /reviews/{id}/correlated-findings/{cid}/relationships
    res_rels = await client.get(f"/api/reviews/{review_id}/correlated-findings/{cf_id}/relationships")
    assert res_rels.status_code == 200
    rels_data = res_rels.json()
    assert len(rels_data) == 1
    assert rels_data[0]["source_finding_id"] == f_id
    assert rels_data[0]["relationship_type"] == "independent"

    # 6. POST /reviews/{id}/correlate (trigger on existing review)
    res_trigger = await client.post(f"/api/reviews/{review_id}/correlate")
    assert res_trigger.status_code == 200
    trigger_data = res_trigger.json()
    assert trigger_data["status"] == "completed"
    assert trigger_data["correlated_clusters_count"] >= 1

    # 7. 404 on nonexistent review / finding
    bad_id = str(uuid.uuid4())
    res_404_status = await client.get(f"/api/reviews/{bad_id}/correlation/status")
    assert res_404_status.status_code == 404

    res_404_cf = await client.get(f"/api/reviews/{review_id}/correlated-findings/{bad_id}")
    assert res_404_cf.status_code == 404
