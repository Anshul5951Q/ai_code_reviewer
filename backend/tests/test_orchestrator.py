"""
Integration tests for AnalysisOrchestrator pipeline execution.
"""
import uuid
import pytest
from sqlalchemy import select

from app.agents.base import AgentResult
from app.agents.orchestrator import AnalysisOrchestrator
from app.llm.provider import MockLLMProvider
from app.models.agent_run import AgentRun
from app.models.finding import Finding
from app.models.repository import Repository
from app.models.repository_snapshot import RepositorySnapshot
from app.models.review import Review


@pytest.mark.asyncio
async def test_orchestrator_full_run_with_mock(db_session):
    # 1. Create Repository, Review, and Snapshot
    repo_id = str(uuid.uuid4())
    repo = Repository(
        id=repo_id,
        name="test-repo",
        full_name="test-org/test-repo",
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

    snapshot = RepositorySnapshot(
        review_id=review_id,
        commit_sha=review.commit_sha,
        branch="main",
        total_files=3,
        source_files=2,
        languages='{"python": {"files": 2, "percentage": 100.0}}',
        frameworks='["FastAPI"]',
        dependencies='[{"name": "fastapi", "version": "0.100.0"}]',
        structure='{"entry_points": ["app/main.py"]}',
    )
    db_session.add(snapshot)
    await db_session.commit()

    # 2. File fixtures with intentional static security pattern and code smells
    files = {
        "app/main.py": """
from fastapi import FastAPI
app = FastAPI()

@app.get('/users')
def get_users(user_id: str):
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    return db.execute(query)
""",
        "app/service.py": """
def complex_business_flow(a, b, c):
    if a:
        if b:
            if c:
                return 1
    return 0
""",
        "package.json": '{"name": "app", "version": "1.0.0"}',
    }

    # 3. Execute Orchestrator
    orchestrator = AnalysisOrchestrator(provider=MockLLMProvider())
    from tests.conftest import test_async_session_maker

    final_review = await orchestrator.run(
        review_id=review_id,
        session_maker=test_async_session_maker,
        files=files,
    )

    # 4. Verify Review Status and Scores
    assert final_review.status == "completed"
    assert final_review.overall_score is not None
    assert final_review.security_score is not None
    assert final_review.quality_score is not None
    assert final_review.architecture_score is not None
    assert 0.0 <= final_review.overall_score <= 100.0

    # 5. Verify Agent Runs
    runs_res = await db_session.execute(
        select(AgentRun).where(AgentRun.review_id == review_id)
    )
    runs = list(runs_res.scalars().all())
    assert len(runs) >= 3
    run_types = {r.agent_type for r in runs}
    assert "security_static" in run_types
    assert "code_understanding" in run_types
    assert "code_review" in run_types
    assert "security_agent" in run_types
    assert all(r.status == "completed" for r in runs)

    # 6. Verify Findings Persisted
    findings_res = await db_session.execute(
        select(Finding).where(Finding.review_id == review_id)
    )
    findings = list(findings_res.scalars().all())
    assert len(findings) > 0
    # SQL injection should be normalized and deduplicated
    sqli = [f for f in findings if f.category == "security"]
    assert len(sqli) >= 1
    assert sqli[0].cwe == "CWE-89"
    assert sqli[0].confidence > 0.0


@pytest.mark.asyncio
async def test_orchestrator_partial_failure(db_session):
    repo_id = str(uuid.uuid4())
    repo = Repository(
        id=repo_id,
        name="test-repo-2",
        full_name="test-org/test-repo-2",
        owner="test-org",
        default_branch="main",
        visibility="public",
    )
    db_session.add(repo)

    review_id = str(uuid.uuid4())
    review = Review(
        id=review_id,
        repository_id=repo_id,
        commit_sha="aabbccddeeff11223344556677889900aabbccdd",
        branch="main",
        status="ready_for_analysis",
    )
    db_session.add(review)

    snapshot = RepositorySnapshot(
        review_id=review_id,
        commit_sha=review.commit_sha,
        branch="main",
        total_files=1,
    )
    db_session.add(snapshot)
    await db_session.commit()

    class FailingReviewProvider(MockLLMProvider):
        async def structured_output(self, prompt, schema_class, system=None):
            if "review" in schema_class.__name__.lower():
                raise RuntimeError("LLM rate limit exceeded")
            return await super().structured_output(prompt, schema_class, system)

    orchestrator = AnalysisOrchestrator(provider=FailingReviewProvider())
    from tests.conftest import test_async_session_maker

    final_review = await orchestrator.run(
        review_id=review_id,
        session_maker=test_async_session_maker,
        files={"src/app.py": "x = 1\n"},
    )

    # Partial failure should yield completed_with_warnings, not total crash!
    assert final_review.status == "completed_with_warnings"

    # Check agent run reflects failed status
    failed_run = await db_session.execute(
        select(AgentRun)
        .where(AgentRun.review_id == review_id, AgentRun.agent_type == "code_review")
    )
    fr = failed_run.scalar_one()
    assert fr.status == "failed"
    assert "rate limit" in fr.error


@pytest.mark.asyncio
async def test_orchestrator_missing_snapshot(db_session):
    review_id = str(uuid.uuid4())
    review = Review(
        id=review_id,
        repository_id="fake-repo",
        commit_sha="12345",
        branch="main",
    )
    db_session.add(review)
    await db_session.commit()

    orchestrator = AnalysisOrchestrator()
    from tests.conftest import test_async_session_maker

    with pytest.raises(ValueError, match="Repository snapshot not found"):
        await orchestrator.run(review_id=review_id, session_maker=test_async_session_maker)
