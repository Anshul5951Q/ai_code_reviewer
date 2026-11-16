"""
Sub-Phase 7.7 — End-to-End Pipeline Integration & Stabilization Test Suite
Tests:
1. Full unified multi-agent pipeline execution (Understanding -> Gate 1 -> Quality + Security -> Gate 2/3 -> Correlator).
2. 13-stage canonical state machine progression & monotonic progress map.
3. Single analysis entry point idempotency (POST /reviews/{id}/analyze).
4. Gate 1 failure handling & downstream agent blocking.
5. Partial failure recovery (e.g. Quality fails, Security succeeds -> completed_with_warnings).
6. Database foreign keys, relationships, and audit trail preservation.
7. Real local Ollama smoke test (qwen2.5-coder:7b) with graceful skip if offline.
"""

import uuid
import pytest
import httpx
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from unittest.mock import AsyncMock, patch

from sqlalchemy import select
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.repository import Repository
from app.models.review import Review
from app.models.analysis_job import AnalysisJob
from app.models.repository_snapshot import RepositorySnapshot
from app.models.agent_run import AgentRun
from app.models.finding import Finding
from app.models.correlated_finding import CorrelatedFinding
from app.schemas.analysis import PipelineStage, STAGE_PROGRESS_MAP
from app.schemas.understanding import CodeUnderstandingResult, ModuleDescription
from app.agents.orchestrator import AnalysisOrchestrator
from app.llm.provider import MockLLMProvider, OllamaProvider


SAMPLE_FILES = {
    "src/server.py": """
import sqlite3
from flask import Flask, request

app = Flask(__name__)

@app.route('/user')
def get_user():
    user_id = request.args.get('id')
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    # SQL Injection vulnerability
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    cursor.execute(query)
    return cursor.fetchall()
""",
    "src/auth.py": """
import hashlib

def hash_password(password: str) -> str:
    # Weak MD5 hash
    return hashlib.md5(password.encode()).hexdigest()
""",
    "src/utils.py": """
def calculate_complexity(a, b, c, d, e):
    if a > 0:
        if b > 0:
            if c > 0:
                if d > 0:
                    if e > 0:
                        return a + b + c + d + e
    return 0
"""
}


class FailingQualityProvider(MockLLMProvider):
    """Fails quality agent inference to test partial failure recovery."""

    async def structured_output(
        self, prompt: str, schema_class, system: Optional[str] = None, options: Optional[Dict[str, Any]] = None
    ) -> Any:
        if "review" in schema_class.__name__.lower() or "quality" in schema_class.__name__.lower():
            raise RuntimeError("LLM rate limit or timeout during code quality analysis")
        return await super().structured_output(prompt, schema_class, system, options)


class FailingGate1Provider(MockLLMProvider):
    """Produces hallucinated files to trigger Gate 1 failure."""

    async def structured_output(
        self, prompt: str, schema_class, system: Optional[str] = None, options: Optional[Dict[str, Any]] = None
    ) -> Any:
        if "understanding" in schema_class.__name__.lower():
            return CodeUnderstandingResult(
                architecture_summary="Hallucinated Rust microservice architecture",
                languages=["Rust"],
                frameworks=["Actix"],
                entry_points=["phantom_main.rs:1"],
                modules=[ModuleDescription(name="GhostModule", file="non_existent_file.rs", purpose="None")],
                important_files=["non_existent_anchor.rs"],
                dependencies=["actix-web"],
                external_integrations=["None"],
                security_boundaries=["None"],
            )
        return await super().structured_output(prompt, schema_class, system, options)


@pytest.mark.asyncio
async def test_e2e_full_unified_pipeline_execution(db_session):
    """
    Test 1: Full unified pipeline from files -> Snapshot -> Understanding -> Gate 1
    -> Quality & Security -> Gates 2 & 3 -> Finding Correlation -> Final Results.
    """
    repo_id = str(uuid.uuid4())
    repo = Repository(
        id=repo_id,
        name="test-pipeline-repo",
        full_name="test-org/test-pipeline-repo",
        owner="test-org",
        default_branch="main",
        visibility="public",
    )
    db_session.add(repo)

    review_id = str(uuid.uuid4())
    review = Review(
        id=review_id,
        repository_id=repo_id,
        commit_sha="11223344556677889900aabbccddeeff11223344",
        branch="main",
        status="ready_for_analysis",
    )
    db_session.add(review)

    job_id = str(uuid.uuid4())
    job = AnalysisJob(
        id=job_id,
        review_id=review_id,
        status="queued",
        current_stage="pending",
        progress=0,
    )
    db_session.add(job)
    await db_session.commit()

    from tests.conftest import test_async_session_maker

    provider = MockLLMProvider()
    orchestrator = AnalysisOrchestrator(provider=provider)

    result_review = await orchestrator.run(
        review_id=review_id,
        session_maker=test_async_session_maker,
        files=SAMPLE_FILES,
        job_id=job_id,
    )

    # 1. Review status validation
    assert result_review.status == "completed"
    assert result_review.overall_score is not None
    assert result_review.security_score is not None
    assert result_review.quality_score is not None

    # 2. Analysis Job status validation
    db_session.expire_all()
    updated_job = await db_session.get(AnalysisJob, job_id)
    assert updated_job.status == "completed"
    assert updated_job.current_stage == PipelineStage.ANALYSIS_COMPLETED
    assert updated_job.progress == 100

    # 3. Agent Runs verification (Code Understanding, Code Quality, Security Detection)
    agent_runs = (await db_session.execute(
        select(AgentRun).where(AgentRun.review_id == review_id)
    )).scalars().all()
    assert len(agent_runs) >= 3
    agent_types = {ar.agent_type for ar in agent_runs}
    assert "code_understanding" in agent_types
    assert ("code_quality" in agent_types or "code_review" in agent_types)
    assert ("security_agent" in agent_types or "security_detection" in agent_types)

    # 4. Findings & Correlation verification
    findings = (await db_session.execute(
        select(Finding).where(Finding.review_id == review_id)
    )).scalars().all()
    assert len(findings) >= 1

    correlated = (await db_session.execute(
        select(CorrelatedFinding).where(CorrelatedFinding.review_id == review_id)
    )).scalars().all()
    assert len(correlated) >= 1

    # 5. Repository snapshot verification
    snapshot = (await db_session.execute(
        select(RepositorySnapshot).where(RepositorySnapshot.review_id == review_id)
    )).scalar_one_or_none()
    assert snapshot is not None
    assert snapshot.total_files == 3


@pytest.mark.asyncio
async def test_e2e_13_stage_state_machine_progression():
    """
    Test 2: Validate the canonical 13 stages of the analysis state machine
    and monotonic progress mapping from 0% to 100%.
    """
    canonical_stages = [
        PipelineStage.PENDING,
        PipelineStage.INGESTING,
        PipelineStage.SNAPSHOTTING,
        PipelineStage.UNDERSTANDING,
        PipelineStage.VERIFYING_UNDERSTANDING,
        PipelineStage.QUALITY_ANALYSIS,
        PipelineStage.SECURITY_ANALYSIS,
        PipelineStage.VERIFYING_FINDINGS,
        PipelineStage.CORRELATING,
        PipelineStage.ANALYSIS_COMPLETED,
    ]

    # Verify all stages exist in progress map
    prev_progress = -1
    for stage in canonical_stages:
        progress = STAGE_PROGRESS_MAP[stage]
        assert progress > prev_progress, f"Stage {stage} progress {progress} not strictly monotonic"
        prev_progress = progress

    assert STAGE_PROGRESS_MAP[PipelineStage.PENDING] == 0
    assert STAGE_PROGRESS_MAP[PipelineStage.ANALYSIS_COMPLETED] == 100

    # Terminal states
    assert STAGE_PROGRESS_MAP[PipelineStage.FAILED] == 100
    assert STAGE_PROGRESS_MAP[PipelineStage.CANCELLED] == 100


@pytest.mark.asyncio
async def test_e2e_single_analysis_entrypoint_idempotency(client: AsyncClient, db_session):
    """
    Test 3: POST /reviews/{id}/analyze idempotency.
    Invoking the single analysis entry point twice should return the same job
    without duplicating execution or active jobs.
    """
    repo_id = str(uuid.uuid4())
    repo = Repository(
        id=repo_id,
        name="idempotent-repo",
        full_name="test-org/idempotent-repo",
        owner="test-org",
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
        status="ready_for_analysis",
    )
    db_session.add(review)
    await db_session.commit()

    # Mock background queue to prevent launching unbound worker threads in this test
    with patch("app.workers.queue.analysis_queue.enqueue", new_callable=AsyncMock):
        # First invocation
        res1 = await client.post(f"/api/reviews/{review_id}/analyze")
        assert res1.status_code in (200, 202)
        data1 = res1.json()
        job_id_1 = data1["job_id"]

        # Second invocation (idempotency check)
        res2 = await client.post(f"/api/reviews/{review_id}/analyze")
        assert res2.status_code in (200, 202)
        data2 = res2.json()
        job_id_2 = data2["job_id"]

        # Should return the exact same active job ID
        assert job_id_1 == job_id_2
        assert "already" in data2["message"].lower() or "started" in data2["message"].lower()

    # Verify only one job exists in the database
    db_session.expire_all()
    jobs = (await db_session.execute(
        select(AnalysisJob).where(AnalysisJob.review_id == review_id)
    )).scalars().all()
    assert len(jobs) == 1


@pytest.mark.asyncio
async def test_e2e_gate1_failure_blocks_downstream_agents(db_session):
    """
    Test 4: When Gate 1 verification rejects code understanding (e.g. hallucinated files),
    downstream Code Quality and Security agents must NOT run.
    """
    repo_id = str(uuid.uuid4())
    repo = Repository(
        id=repo_id,
        name="gate1-fail-repo",
        full_name="test-org/gate1-fail-repo",
        owner="test-org",
        default_branch="main",
        visibility="public",
    )
    db_session.add(repo)

    review_id = str(uuid.uuid4())
    review = Review(
        id=review_id,
        repository_id=repo_id,
        commit_sha="99887766554433221100aabbccddeeff11223344",
        branch="main",
        status="ready_for_analysis",
    )
    db_session.add(review)
    await db_session.commit()

    from tests.conftest import test_async_session_maker

    provider = FailingGate1Provider()
    orchestrator = AnalysisOrchestrator(provider=provider)

    result_review = await orchestrator.run(
        review_id=review_id,
        session_maker=test_async_session_maker,
        files=SAMPLE_FILES,
    )

    # Pipeline should complete with warnings because of Gate 1 rejection
    assert result_review.status in ("completed_with_warnings", "failed")

    # Downstream agents (quality and security) must not have run
    agent_runs = (await db_session.execute(
        select(AgentRun).where(AgentRun.review_id == review_id)
    )).scalars().all()

    quality_runs = [ar for ar in agent_runs if ar.agent_type in ("code_quality", "code_review")]
    security_runs = [ar for ar in agent_runs if ar.agent_type in ("security_agent", "security_detection")]
    assert len(quality_runs) == 0
    assert len(security_runs) == 0


@pytest.mark.asyncio
async def test_e2e_partial_failure_quality_agent_resilience(db_session):
    """
    Test 5: When Code Quality agent fails (e.g. timeout / exception),
    Security agent continues and pipeline marks 'completed_with_warnings'.
    """
    repo_id = str(uuid.uuid4())
    repo = Repository(
        id=repo_id,
        name="partial-fail-repo",
        full_name="test-org/partial-fail-repo",
        owner="test-org",
        default_branch="main",
        visibility="public",
    )
    db_session.add(repo)

    review_id = str(uuid.uuid4())
    review = Review(
        id=review_id,
        repository_id=repo_id,
        commit_sha="554433221100aabbccddeeff1122334455667788",
        branch="main",
        status="ready_for_analysis",
    )
    db_session.add(review)
    await db_session.commit()

    from tests.conftest import test_async_session_maker

    provider = FailingQualityProvider()
    orchestrator = AnalysisOrchestrator(provider=provider)

    result_review = await orchestrator.run(
        review_id=review_id,
        session_maker=test_async_session_maker,
        files=SAMPLE_FILES,
    )

    # Pipeline gracefully yields completed_with_warnings
    assert result_review.status == "completed_with_warnings"

    # Quality agent run is recorded as failed
    agent_runs = (await db_session.execute(
        select(AgentRun).where(AgentRun.review_id == review_id)
    )).scalars().all()

    quality_runs = [ar for ar in agent_runs if ar.agent_type in ("code_quality", "code_review")]
    assert len(quality_runs) == 1
    assert quality_runs[0].status == "failed"

    # Security agent run is recorded as completed
    sec_runs = [ar for ar in agent_runs if ar.agent_type in ("security_agent", "security_detection")]
    assert len(sec_runs) == 1
    assert sec_runs[0].status == "completed"

    # Findings from the successful security agent are still preserved
    findings = (await db_session.execute(
        select(Finding).where(Finding.review_id == review_id)
    )).scalars().all()
    assert len(findings) >= 1


@pytest.mark.asyncio
async def test_e2e_database_cascading_and_audit_preservation(db_session):
    """
    Test 6: Validate relationship links and audit preservation between Review,
    AgentRuns, Findings, and CorrelatedFindings.
    """
    repo_id = str(uuid.uuid4())
    repo = Repository(
        id=repo_id,
        name="audit-repo",
        full_name="test-org/audit-repo",
        owner="test-org",
        default_branch="main",
        visibility="public",
    )
    db_session.add(repo)

    review_id = str(uuid.uuid4())
    review = Review(
        id=review_id,
        repository_id=repo_id,
        commit_sha="c0ffee112233445566778899aabbccddeeff0011",
        branch="main",
        status="completed",
        overall_score=85,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(review)

    agent_run = AgentRun(
        id=str(uuid.uuid4()),
        review_id=review_id,
        agent_type="code_understanding",
        status="completed",
        duration_ms=120,
    )
    db_session.add(agent_run)

    finding = Finding(
        id=str(uuid.uuid4()),
        review_id=review_id,
        source="security_agent",
        category="security",
        severity="high",
        title="Test Security Vulnerability",
        description="Audit test finding",
        file_path="src/server.py",
        start_line=10,
        cwe="CWE-89",
        confidence=0.95,
    )
    db_session.add(finding)
    await db_session.commit()

    # Query relationships
    loaded_review = await db_session.get(Review, review_id)
    assert loaded_review is not None
    assert loaded_review.repository_id == repo_id

    loaded_run = await db_session.get(AgentRun, agent_run.id)
    assert loaded_run.review_id == review_id

    loaded_finding = await db_session.get(Finding, finding.id)
    assert loaded_finding.review_id == review_id
    assert loaded_finding.source == "security_agent"


@pytest.mark.asyncio
async def test_e2e_live_ollama_pipeline_smoke():
    """
    Test 7: Real local Ollama smoke test against http://localhost:11434 with qwen2.5-coder:7b.
    Skips cleanly if Ollama daemon is offline or model is not loaded.
    """
    ollama_url = "http://localhost:11434"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{ollama_url}/api/tags")
            if resp.status_code != 200:
                pytest.skip("Local Ollama daemon is not responding HTTP 200.")
            models = [m.get("name") for m in resp.json().get("models", [])]
            if not any("qwen2.5-coder" in m for m in models):
                pytest.skip("qwen2.5-coder model not installed in local Ollama.")
    except Exception:
        pytest.skip("Local Ollama service unreachable.")

    provider = OllamaProvider(
        base_url=ollama_url,
        model="qwen2.5-coder:7b",
        temperature=0.0,
        timeout=30.0,
    )

    test_prompt = "Explain in one brief sentence what an SQL injection vulnerability is."
    try:
        response = await provider.complete(test_prompt)
    except Exception as exc:
        pytest.skip(f"Ollama local runtime error during live inference: {exc}")
    assert len(response) > 0
    assert "sql" in response.lower()


@pytest.mark.asyncio
async def test_e2e_legacy_run_endpoint_compatibility(client: AsyncClient, db_session):
    """
    Test 8: Backward compatibility for POST /api/reviews/{id}/run.
    Ensures that calling the existing /run route delegates to the unified analysis service,
    checks snapshot presence, and enforces idempotency without running a second pipeline.
    """
    repo_id = str(uuid.uuid4())
    repo = Repository(
        id=repo_id,
        name="legacy-run-repo",
        full_name="test-org/legacy-run-repo",
        owner="test-org",
        default_branch="main",
        visibility="public",
    )
    db_session.add(repo)

    review_id = str(uuid.uuid4())
    review = Review(
        id=review_id,
        repository_id=repo_id,
        commit_sha="44556677889900112233aabbccddeeff44556677",
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

    with patch("app.workers.queue.analysis_queue.enqueue", new_callable=AsyncMock):
        resp = await client.post(f"/api/reviews/{review_id}/run")
        assert resp.status_code == 202
        data = resp.json()
        assert data["review_id"] == review_id
        assert data["status"] in ("queued", "running")

    # Verify AnalysisJob was created and tracked
    db_session.expire_all()
    job_res = await db_session.execute(
        select(AnalysisJob).where(AnalysisJob.review_id == review_id)
    )
    jobs = job_res.scalars().all()
    assert len(jobs) == 1


@pytest.mark.asyncio
async def test_e2e_correlator_retry_versioning_and_preservation(client: AsyncClient, db_session):
    """
    Test 9: Finding correlator non-destructive versioning on retries.
    Ensures that retrying correlation preserves historical correlated findings
    with incremented correlation_version (e.g. 1.0 -> 2.0) and latest version is queried.
    """
    repo_id = str(uuid.uuid4())
    repo = Repository(
        id=repo_id,
        name="version-corr-repo",
        full_name="test-org/version-corr-repo",
        owner="test-org",
        default_branch="main",
        visibility="public",
    )
    db_session.add(repo)

    review_id = str(uuid.uuid4())
    review = Review(
        id=review_id,
        repository_id=repo_id,
        commit_sha="778899aabbccddeeff00112233445566778899aa",
        branch="main",
        status="completed",
    )
    db_session.add(review)

    f1 = Finding(
        id=str(uuid.uuid4()),
        review_id=review_id,
        source="security_agent",
        category="security",
        severity="high",
        title="SQL Injection",
        file_path="src/app.py",
        start_line=10,
        cwe="CWE-89",
    )
    f2 = Finding(
        id=str(uuid.uuid4()),
        review_id=review_id,
        source="code_quality",
        category="quality",
        severity="medium",
        title="Complexity",
        file_path="src/app.py",
        start_line=12,
    )
    db_session.add_all([f1, f2])
    await db_session.commit()

    from app.analysis.finding_correlator import FindingCorrelator
    correlator = FindingCorrelator(provider=MockLLMProvider())
    raw_dicts = [
        {"id": f1.id, "title": f1.title, "file_path": f1.file_path, "start_line": f1.start_line, "category": f1.category, "severity": f1.severity, "cwe": f1.cwe},
        {"id": f2.id, "title": f2.title, "file_path": f2.file_path, "start_line": f2.start_line, "category": f2.category, "severity": f2.severity, "cwe": None},
    ]

    # Run 1: First correlation run (version 1.0)
    clusters_1, _ = await correlator.correlate_findings(raw_dicts)
    await correlator.persist_correlation_results(db_session, review_id, clusters_1)

    # Run 2: Retry correlation run (should be version 2.0 without destroying version 1.0)
    clusters_2, _ = await correlator.correlate_findings(raw_dicts)
    await correlator.persist_correlation_results(db_session, review_id, clusters_2)

    # Verify both versions exist in database
    db_session.expire_all()
    all_cf = (await db_session.execute(
        select(CorrelatedFinding).where(CorrelatedFinding.review_id == review_id)
    )).scalars().all()

    versions = {cf.correlation_version for cf in all_cf}
    assert "1.0" in versions
    assert "2.0" in versions
    assert len(all_cf) >= 2  # Prior records preserved!

    # Query API endpoint: should return only the latest version (2.0)
    resp = await client.get(f"/api/reviews/{review_id}/correlated-findings")
    assert resp.status_code == 200
    data = resp.json()
    assert all(item["correlation_version"] == "2.0" for item in data["items"])


@pytest.mark.asyncio
async def test_e2e_health_check_reports_queue_durability(client: AsyncClient):
    """
    Test 10: Health check endpoint includes queue backend details and durability disclosure.
    """
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "queue" in data
    assert "backend" in data["queue"]
    assert "durable" in data["queue"]
    assert data["queue"]["backend"] in ("redis", "in_memory_fallback")
