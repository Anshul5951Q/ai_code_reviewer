"""
Tests for RemediationOrchestrator pipeline execution, sandboxing, and retry handling.
"""
import json
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.llm.provider import MockLLMProvider
from app.models.finding import Finding
from app.models.remediation_run import RemediationRun
from app.models.repository_snapshot import RepositorySnapshot
from app.models.review import Review
from app.remediation.orchestrator import RemediationOrchestrator


@pytest.mark.asyncio
async def test_remediation_orchestrator_successful_resolution(
    db_session: AsyncSession,
):
    review_id = str(uuid.uuid4())
    finding_id = str(uuid.uuid4())
    remediation_id = str(uuid.uuid4())

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
        start_line=25,
        end_line=28,
        cwe="CWE-89",
        evidence='cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")',
        status="open",
    )
    db_session.add(finding)

    snapshot_code = {
        "src/api/users.py": (
            "import db\n"
            "def get_user(user_id):\n"
            "    cursor = db.get_cursor()\n"
            '    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")\n'
            "    return cursor.fetchone()\n"
        )
    }

    snapshot = RepositorySnapshot(
        review_id=review_id,
        commit_sha="123456",
        branch="main",
        languages=json.dumps({"primary": {"name": "Python"}}),
    )
    db_session.add(snapshot)

    run = RemediationRun(
        id=remediation_id,
        review_id=review_id,
        finding_id=finding_id,
        status="queued",
    )
    db_session.add(run)
    await db_session.commit()

    # Session maker for orchestrator
    maker = async_sessionmaker(
        bind=db_session.bind,
        expire_on_commit=False,
        class_=AsyncSession,
    )

    mock_llm = MockLLMProvider()
    orchestrator = RemediationOrchestrator(llm_provider=mock_llm)

    completed_run = await orchestrator.run(
        remediation_id,
        session_maker=maker,
        provided_files=snapshot_code,
    )

    assert completed_run.status == "completed"
    assert completed_run.patch_valid is True
    assert completed_run.verification_status == "resolved"

    # Verify finding status updated
    await db_session.refresh(finding)
    assert finding.status == "resolved"


@pytest.mark.asyncio
async def test_remediation_orchestrator_max_attempts_exhausted(
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

    # Add 3 previous runs
    for i in range(3):
        r = RemediationRun(
            id=str(uuid.uuid4()),
            review_id=review_id,
            finding_id=finding_id,
            status="completed",
            verification_status="still_vulnerable",
        )
        db_session.add(r)

    # 4th run attempt
    run4_id = str(uuid.uuid4())
    run4 = RemediationRun(
        id=run4_id,
        review_id=review_id,
        finding_id=finding_id,
        status="queued",
    )
    db_session.add(run4)
    await db_session.commit()

    maker = async_sessionmaker(
        bind=db_session.bind,
        expire_on_commit=False,
        class_=AsyncSession,
    )

    mock_llm = MockLLMProvider()
    orchestrator = RemediationOrchestrator(llm_provider=mock_llm)

    result = await orchestrator.run(run4_id, session_maker=maker)

    assert result.status == "failed"
    assert "exhausted" in result.error.lower()

    await db_session.refresh(finding)
    assert finding.status == "remediation_exhausted"
