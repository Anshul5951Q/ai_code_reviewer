"""
Unit tests for specialized analysis agents (Understanding, Review, Security).
"""
import pytest

from app.agents.base import AnalysisContext
from app.agents.code_review import CodeReviewAgent
from app.agents.code_understanding import CodeUnderstandingAgent
from app.agents.security import SecurityAgent
from app.analysis.chunker import FileChunk
from app.llm.provider import MockLLMProvider


def make_test_context(agent_type: str = "code_review") -> AnalysisContext:
    chunk = FileChunk(
        file_path="src/service.py",
        start_line=1,
        end_line=50,
        chunk_index=0,
        content="def process_data(items):\n    # complex processing\n    pass\n",
        total_lines=50,
    )
    return AnalysisContext(
        review_id="rev-123",
        repository_id="repo-123",
        repository_name="test-org/test-repo",
        commit_sha="abcd1234efgh5678",
        branch="main",
        agent_type=agent_type,
        languages={"python": {"files": 5, "percentage": 100.0}},
        frameworks=["FastAPI"],
        dependencies=[{"name": "fastapi", "version": "0.100.0"}],
        structure={"entry_points": ["app/main.py"]},
        statistics={"total_files": 5, "total_lines": 500},
        file_tree=["src/service.py", "app/main.py"],
        selected_files={"src/service.py": chunk.content},
        chunks=[chunk],
        static_findings=[{
            "category": "security",
            "type": "sql_injection",
            "severity": "high",
            "title": "Potential SQL Injection",
            "file_path": "src/service.py",
            "start_line": 25,
            "cwe": "CWE-89",
        }],
    )


@pytest.mark.asyncio
async def test_code_understanding_agent():
    provider = MockLLMProvider()
    agent = CodeUnderstandingAgent(provider=provider)
    ctx = make_test_context(agent_type="code_understanding")

    result = await agent.analyze(ctx)
    assert result.status == "completed"
    assert result.agent_type == "code_understanding"
    assert "architecture_summary" in result.data
    assert len(result.data["important_modules"]) > 0


@pytest.mark.asyncio
async def test_code_review_agent():
    provider = MockLLMProvider()
    agent = CodeReviewAgent(provider=provider)
    ctx = make_test_context(agent_type="code_review")

    result = await agent.analyze(ctx)
    assert result.status == "completed"
    assert result.agent_type == "code_review"
    assert len(result.findings) >= 1
    assert result.findings[0].category in ("quality", "maintainability", "performance", "architecture")
    assert result.findings[0].file_path is not None


@pytest.mark.asyncio
async def test_security_agent():
    provider = MockLLMProvider()
    agent = SecurityAgent(provider=provider)
    ctx = make_test_context(agent_type="security_agent")

    result = await agent.analyze(ctx)
    assert result.status == "completed"
    assert result.agent_type == "security_agent"
    assert len(result.findings) >= 1
    assert result.findings[0].category == "security"
    assert result.findings[0].cwe == "CWE-89"


@pytest.mark.asyncio
async def test_agent_error_resilience():
    class FailingProvider(MockLLMProvider):
        async def structured_output(self, prompt, schema_class, system=None):
            raise ConnectionError("LLM API network timeout")

    agent = CodeReviewAgent(provider=FailingProvider())
    ctx = make_test_context(agent_type="code_review")

    result = await agent.analyze(ctx)
    # Must not raise an exception; must return failed status
    assert result.status == "failed"
    assert "network timeout" in result.error
