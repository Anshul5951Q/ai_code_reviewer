"""
Tests for VerificationAgent independent auditing and regression detection.
"""
import pytest
from app.agents.verification import VerificationAgent
from app.llm.provider import MockLLMProvider
from app.models.finding import Finding


@pytest.mark.asyncio
async def test_verification_agent_deterministic_syntax_failure():
    agent = VerificationAgent(llm_provider=MockLLMProvider())

    finding = Finding(
        id="f1",
        review_id="r1",
        category="security",
        severity="high",
        title="SQL Injection",
        file_path="app/db.py",
    )

    result = await agent.verify(
        finding=finding,
        file_path="app/db.py",
        original_code="orig",
        modified_code="def broken(:\n",
        unified_diff="--- a\n+++ b",
        static_analysis_signals=[],
        syntax_valid=False,
        syntax_error="invalid syntax at line 1",
    )

    assert result.status == "verification_failed"
    assert "syntax" in result.reason.lower()
    assert len(result.new_findings) == 1


@pytest.mark.asyncio
async def test_verification_agent_resolved_assessment():
    agent = VerificationAgent(llm_provider=MockLLMProvider())

    finding = Finding(
        id="f1",
        review_id="r1",
        category="security",
        severity="high",
        title="SQL Injection",
        file_path="src/api/users.py",
    )

    result = await agent.verify(
        finding=finding,
        file_path="src/api/users.py",
        original_code='cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")',
        modified_code='cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))',
        unified_diff="--- a/src/api/users.py\n+++ b/src/api/users.py\n@@ -1 +1 @@\n-old\n+new",
        static_analysis_signals=[],
        syntax_valid=True,
    )

    assert result.status == "resolved"
    assert result.confidence >= 0.9
