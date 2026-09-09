"""
Tests for RemediationAgent fix generation, context assembly, and secret protection.
"""
import pytest
from app.agents.remediation import RemediationAgent
from app.llm.provider import MockLLMProvider
from app.models.finding import Finding
from app.remediation.context_builder import build_remediation_context, redact_secrets_in_text


def test_secret_redaction_in_context():
    raw_text = 'AWS_KEY = "AKIA1234567890ABCDEF"\nSECRET = "super_secret_password_123"\n'
    redacted = redact_secrets_in_text(raw_text)

    assert "AKIA1234567890ABCDEF" not in redacted
    assert "AKIA****************" in redacted
    assert "super_secret_password_123" not in redacted


@pytest.mark.asyncio
async def test_remediation_agent_generates_valid_plan():
    finding = Finding(
        id="find-123",
        review_id="rev-456",
        category="security",
        severity="high",
        title="SQL Injection",
        file_path="src/api/users.py",
        start_line=25,
        end_line=28,
        cwe="CWE-89",
        evidence='cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")',
        description="Dynamic SQL query allows injection.",
    )

    file_content = (
        "import db\n\n"
        "def get_user(user_id):\n"
        "    cursor = db.get_cursor()\n"
        '    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")\n'
        "    return cursor.fetchone()\n"
    )

    ctx = build_remediation_context(
        finding=finding,
        file_content=file_content,
        repository_name="test-repo",
        languages={"primary": {"name": "Python"}},
        frameworks=["FastAPI"],
    )

    mock_llm = MockLLMProvider()
    agent = RemediationAgent(llm_provider=mock_llm)

    plan = await agent.generate_fix(ctx)

    assert plan.strategy is not None
    assert len(plan.files_changed) >= 1
    assert len(plan.changes) >= 1
    assert plan.unified_diff is not None
    assert "--- a/src/api/users.py" in plan.unified_diff
    assert plan.confidence >= 0.8
