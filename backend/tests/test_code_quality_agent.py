"""
Unit tests for CodeQualityAgent and deterministic AST code quality metrics.
"""
from __future__ import annotations

import pytest

from app.agents.base import AnalysisContext
from app.agents.code_quality import (
    CodeQualityAgent,
    analyze_python_ast_quality,
)
from app.analysis.chunker import FileChunk
from app.llm.provider import MockLLMProvider


# ── Test Fixtures ─────────────────────────────────────────────────────────────

COMPLEX_FUNCTION_CODE = """
def complex_business_logic(a, b, c, mode, flag):
    result = 0
    if a > 0:
        if b > 0:
            if c > 0:
                result = a + b + c
            elif c < -10:
                result = a + b - c
            else:
                result = a + b
        else:
            for i in range(10):
                if mode == "fast" and flag:
                    result += i
                elif mode == "slow" or not flag:
                    result -= i
    else:
        while a < 0:
            try:
                a += 1
                if b == 0:
                    break
            except Exception:
                pass
    return result
"""

DUPLICATE_CODE_FILE = """
def calculate_subtotal(items):
    total = 0.0
    for item in items:
        price = item.get("price", 0.0)
        qty = item.get("qty", 1)
        discount = item.get("discount", 0.0)
        total += (price * qty) - discount
    return total

def calculate_invoice_total(order):
    items = order.get("items", [])
    total = 0.0
    for item in items:
        price = item.get("price", 0.0)
        qty = item.get("qty", 1)
        discount = item.get("discount", 0.0)
        total += (price * qty) - discount
    return total
"""

ERROR_HANDLING_CODE = """
def parse_record(data):
    try:
        val = int(data)
        return val
    except:
        pass

def fetch_resource(url):
    try:
        res = connect(url)
    except Exception:
        pass
"""

RESOURCE_LEAK_CODE = """
def load_data(filepath):
    f = open(filepath, 'r')
    content = f.read()
    return content
"""

LARGE_FUNCTION_CODE = "\n".join([
    "def very_long_procedural_function():",
    "    x = 1",
] + [f"    x += {i}" for i in range(60)] + [
    "    return x",
])


# ── Tests for Deterministic AST Metrics ───────────────────────────────────────

def test_ast_cyclomatic_complexity_detection():
    findings = analyze_python_ast_quality("src/service.py", COMPLEX_FUNCTION_CODE, max_complexity=10)
    complexity_findings = [f for f in findings if f.type == "complexity"]
    assert len(complexity_findings) >= 1
    assert "High Cyclomatic Complexity" in complexity_findings[0].title
    assert complexity_findings[0].severity in ("high", "medium")
    assert complexity_findings[0].file_path == "src/service.py"
    assert complexity_findings[0].confidence >= 0.90
    assert complexity_findings[0].why_problematic is not None
    assert complexity_findings[0].recommended_improvement is not None


def test_ast_duplicate_code_detection():
    findings = analyze_python_ast_quality("src/billing.py", DUPLICATE_CODE_FILE)
    duplicate_findings = [f for f in findings if f.type == "duplicate_code"]
    assert len(duplicate_findings) >= 1
    assert "Duplicate Code Block" in duplicate_findings[0].title
    assert duplicate_findings[0].start_line is not None


def test_ast_error_handling_detection():
    findings = analyze_python_ast_quality("src/parser.py", ERROR_HANDLING_CODE)
    error_findings = [f for f in findings if f.type == "error_handling"]
    assert len(error_findings) >= 1
    assert any("Silent Exception Suppression" in f.title for f in error_findings)


def test_ast_resource_leak_detection():
    findings = analyze_python_ast_quality("src/loader.py", RESOURCE_LEAK_CODE)
    leak_findings = [f for f in findings if f.type == "resource_leak"]
    assert len(leak_findings) >= 1
    assert "Unmanaged File Descriptor" in leak_findings[0].title
    assert "with open" in leak_findings[0].recommended_improvement


def test_ast_large_function_detection():
    findings = analyze_python_ast_quality("src/proc.py", LARGE_FUNCTION_CODE, max_function_lines=50)
    large_findings = [f for f in findings if f.type == "large_function"]
    assert len(large_findings) >= 1
    assert "Oversized Function" in large_findings[0].title


# ── Tests for CodeQualityAgent ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_code_quality_agent_execution():
    provider = MockLLMProvider()
    agent = CodeQualityAgent(provider=provider)

    chunk = FileChunk(
        file_path="src/service.py",
        start_line=1,
        end_line=30,
        chunk_index=0,
        content=COMPLEX_FUNCTION_CODE,
        total_lines=30,
    )
    context = AnalysisContext(
        review_id="rev-q1",
        repository_id="repo-1",
        repository_name="test-org/quality-repo",
        commit_sha="abcdef123456",
        branch="main",
        agent_type="code_quality",
        languages={"python": {"files": 1, "percentage": 100.0}},
        frameworks=["FastAPI"],
        dependencies=[],
        structure={"entry_points": []},
        statistics={"total_files": 1, "total_lines": 30},
        file_tree=["src/service.py"],
        selected_files={"src/service.py": COMPLEX_FUNCTION_CODE},
        chunks=[chunk],
    )

    result = await agent.analyze(context)
    assert result.status == "completed"
    assert result.agent_type == "code_quality"
    assert len(result.findings) >= 1
    assert result.data["total_quality_findings"] >= 1
    # Check that findings contain required fields
    finding = result.findings[0]
    assert finding.category in ("quality", "maintainability", "performance", "architecture")
    assert finding.title is not None
    assert finding.confidence >= 0.65
    assert finding.file_path == "src/service.py"


@pytest.mark.asyncio
async def test_code_quality_agent_resilience():
    class FailingProvider(MockLLMProvider):
        async def structured_output(self, prompt, schema_class, system=None, options=None):
            raise ConnectionError("Ollama connection refused at http://localhost:11434")

    agent = CodeQualityAgent(provider=FailingProvider())
    chunk = FileChunk(
        file_path="src/service.py",
        start_line=1,
        end_line=30,
        chunk_index=0,
        content=COMPLEX_FUNCTION_CODE,
        total_lines=30,
    )
    context = AnalysisContext(
        review_id="rev-q2",
        repository_id="repo-1",
        repository_name="test-org/quality-repo",
        commit_sha="abcdef123456",
        branch="main",
        agent_type="code_quality",
        languages={"python": {"files": 1, "percentage": 100.0}},
        frameworks=["FastAPI"],
        dependencies=[],
        structure={"entry_points": []},
        statistics={"total_files": 1, "total_lines": 30},
        file_tree=["src/service.py"],
        selected_files={"src/service.py": COMPLEX_FUNCTION_CODE},
        chunks=[chunk],
    )

    # Must fall back gracefully to deterministic findings even if Ollama is offline
    result = await agent.analyze(context)
    assert result.status == "completed"
    assert len(result.findings) >= 1  # Deterministic AST findings still returned!

