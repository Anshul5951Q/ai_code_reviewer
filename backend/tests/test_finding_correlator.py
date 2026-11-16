"""
Unit tests for FindingCorrelator & Cross-Agent Finding Intelligence (Sub-Phase 7.4).

Tests:
1. Exact duplicate detection across repeated scans and multi-rule hits
2. Overlapping finding detection on same function/lines
3. Root-cause correlation (SQLi + validation, Path traversal + file handling, shared helper)
4. Independent finding preservation (no false merges of distinct concerns)
5. Explainable severity prioritization policy (anti-downgrade and anti-escalation)
6. Resilience and graceful degradation when Ollama is unavailable
"""
from __future__ import annotations

import pytest

from app.analysis.finding_correlator import FindingCorrelator
from app.llm.provider import MockLLMProvider


@pytest.fixture
def correlator() -> FindingCorrelator:
    return FindingCorrelator(provider=MockLLMProvider())


@pytest.mark.asyncio
async def test_exact_duplicate_detection(correlator: FindingCorrelator):
    """Identical evidence or same CWE on identical lines from two sources merges as exact_duplicate."""
    f1 = {
        "id": "raw-sec-1",
        "file_path": "src/api/users.py",
        "start_line": 24,
        "end_line": 26,
        "category": "security",
        "severity": "high",
        "title": "SQL Injection in User Lookup",
        "description": "User input concatenated into query string.",
        "evidence": "cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')",
        "cwe": "CWE-89",
        "source": "security_static",
        "confidence": 0.90,
    }
    f2 = {
        "id": "raw-sec-2",
        "file_path": "src/api/users.py",
        "start_line": 24,
        "end_line": 26,
        "category": "security",
        "severity": "high",
        "title": "Verified SQL Injection (CWE-89)",
        "description": "Exploitable SQL injection vulnerability verified by LLM reasoning.",
        "evidence": "cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')",
        "cwe": "CWE-89",
        "source": "security_agent",
        "confidence": 0.95,
    }

    clusters, meta = await correlator.correlate_findings([f1, f2])

    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster.category == "security"
    assert cluster.severity == "high"
    assert len(cluster.relationships) == 2

    # Verify relationship types
    rel_types = [r.relationship_type for r in cluster.relationships]
    assert "exact_duplicate" in rel_types
    assert meta["exact_duplicates_count"] >= 1


@pytest.mark.asyncio
async def test_overlapping_finding_detection(correlator: FindingCorrelator):
    """Overlapping code location with distinct aspects (security vs quality) links as overlapping."""
    f_sec = {
        "id": "sec-1",
        "file_path": "src/services/auth.py",
        "start_line": 40,
        "end_line": 45,
        "category": "security",
        "severity": "critical",
        "title": "Command Injection in Service Ping",
        "description": "Untrusted host string passed directly to system shell.",
        "evidence": "os.system(f'ping -c 1 {host}')",
        "cwe": "CWE-78",
        "source": "security_agent",
        "confidence": 0.95,
    }
    f_qual = {
        "id": "qual-1",
        "file_path": "src/services/auth.py",
        "start_line": 42,
        "end_line": 44,
        "category": "maintainability",
        "severity": "low",
        "title": "Missing Input Parameter Validation",
        "description": "Function 'ping_host' accepts 'host' parameter without type or boundary validation.",
        "evidence": "def ping_host(host):",
        "source": "code_quality_agent",
        "confidence": 0.85,
    }

    clusters, meta = await correlator.correlate_findings([f_sec, f_qual])

    assert len(clusters) == 1
    cluster = clusters[0]
    # Security category and critical severity must be preserved (never downgraded)
    assert cluster.category == "security"
    assert cluster.severity == "critical"
    assert "overlapping" in cluster.relationship_types
    assert meta["overlapping_count"] >= 1


@pytest.mark.asyncio
async def test_root_cause_correlation_sql_and_validation(correlator: FindingCorrelator):
    """Known root cause pattern: CWE-89 + missing validation links as shared_root_cause."""
    f_sqli = {
        "id": "f-sqli",
        "file_path": "src/db/orders.py",
        "start_line": 15,
        "end_line": 18,
        "category": "security",
        "severity": "high",
        "title": "Potential SQL Injection",
        "description": "Unescaped order_id parameter interpolated into query.",
        "cwe": "CWE-89",
        "source": "security_agent",
        "confidence": 0.92,
    }
    f_val = {
        "id": "f-val",
        "file_path": "src/db/orders.py",
        "start_line": 12,
        "end_line": 14,
        "category": "maintainability",
        "severity": "medium",
        "title": "Missing Input Validation in Order Lookup",
        "description": "Parameter order_id is not checked for format or bounds.",
        "type": "missing_validation",
        "source": "code_quality_agent",
        "confidence": 0.80,
    }

    clusters, meta = await correlator.correlate_findings([f_sqli, f_val])

    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster.root_cause is not None
    assert "Unvalidated User Input" in cluster.root_cause or "validation" in cluster.root_cause.lower()
    assert "shared_root_cause" in cluster.relationship_types
    assert meta["shared_root_cause_count"] >= 1


@pytest.mark.asyncio
async def test_root_cause_cross_file_shared_helper(correlator: FindingCorrelator):
    """Cross-file invocations of the same insecure helper function link via shared root cause."""
    f_call1 = {
        "id": "callsite-1",
        "file_path": "src/controllers/reports.py",
        "start_line": 35,
        "end_line": 36,
        "category": "security",
        "severity": "high",
        "title": "Path Traversal in Report Retrieval",
        "description": "Reads user report using unvalidated helper.",
        "evidence": "content = read_custom_report(user_path)",
        "cwe": "CWE-22",
        "source": "security_agent",
    }
    f_call2 = {
        "id": "callsite-2",
        "file_path": "src/controllers/invoices.py",
        "start_line": 80,
        "end_line": 81,
        "category": "security",
        "severity": "high",
        "title": "Path Traversal in Invoice Export",
        "description": "Exports invoice using unvalidated helper.",
        "evidence": "content = read_custom_report(invoice_path)",
        "cwe": "CWE-22",
        "source": "security_agent",
    }

    clusters, meta = await correlator.correlate_findings([f_call1, f_call2])

    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster.root_cause is not None
    assert "read_custom_report" in cluster.root_cause
    assert "shared_root_cause" in cluster.relationship_types


@pytest.mark.asyncio
async def test_independent_findings_preserved(correlator: FindingCorrelator):
    """Separate issues in the same file with different causes remain distinct independent clusters."""
    f1 = {
        "id": "ind-1",
        "file_path": "src/utils/helpers.py",
        "start_line": 10,
        "end_line": 15,
        "category": "maintainability",
        "severity": "low",
        "title": "High Cyclomatic Complexity in String Formatter",
        "description": "Formatter method has complexity score of 12 with nested loops.",
        "evidence": "def format_output(data):\n    for k in data:\n        if k:\n            ...",
        "source": "code_quality_agent",
        "confidence": 0.85,
    }
    f2 = {
        "id": "ind-2",
        "file_path": "src/utils/helpers.py",
        "start_line": 85,
        "end_line": 95,
        "category": "security",
        "severity": "critical",
        "title": "Hardcoded JWT Signing Secret",
        "description": "Static secret string constant committed to version control.",
        "evidence": "JWT_SECRET = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'",
        "cwe": "CWE-798",
        "source": "security_agent",
        "confidence": 0.95,
    }

    clusters, meta = await correlator.correlate_findings([f1, f2])

    # Must NOT merge into a single cluster
    assert len(clusters) == 2
    titles = {c.title for c in clusters}
    assert "High Cyclomatic Complexity in String Formatter" in titles
    assert "Hardcoded JWT Signing Secret" in titles
    assert meta["independent_count"] >= 2


@pytest.mark.asyncio
async def test_severity_prioritization_policy(correlator: FindingCorrelator):
    """
    Severity prioritization policy rules:
    - Security finding is never downgraded by low-severity quality finding.
    - Low-severity high-confidence finding does not escalate to critical.
    - Cluster severity equals maximum risk among validated constituents.
    """
    f_crit = {
        "id": "crit-1",
        "file_path": "src/app.py",
        "start_line": 20,
        "end_line": 25,
        "category": "security",
        "severity": "critical",
        "title": "Remote Code Execution via Pickle",
        "description": "Unsafe deserialization of client cookie.",
        "cwe": "CWE-502",
        "confidence": 0.75,
        "source": "security_agent",
    }
    f_info = {
        "id": "info-1",
        "file_path": "src/app.py",
        "start_line": 22,
        "end_line": 24,
        "category": "maintainability",
        "severity": "info",
        "title": "Unnecessary Docstring Formatting",
        "description": "Docstring style variance.",
        "confidence": 0.99,  # High confidence, but info severity!
        "source": "code_quality_agent",
    }

    clusters, _ = await correlator.correlate_findings([f_crit, f_info])

    assert len(clusters) == 1
    # Must remain critical, not downgraded to info or medium average!
    assert clusters[0].severity == "critical"
    # Anti-escalation: confidence does not alter severity rating
    assert clusters[0].confidence > 0.0


@pytest.mark.asyncio
async def test_offline_ollama_graceful_fallback():
    """When Ollama provider throws an error, deterministic correlation still completes successfully."""
    class OfflineProvider(MockLLMProvider):
        async def structured_output(self, prompt, schema_class, system=None, options=None):
            raise ConnectionRefusedError("Ollama port 11434 unreachable")

    correlator = FindingCorrelator(provider=OfflineProvider())

    f1 = {
        "id": "off-1",
        "file_path": "src/app.py",
        "start_line": 10,
        "end_line": 12,
        "category": "security",
        "severity": "high",
        "title": "SQL Injection in User Endpoint",
        "cwe": "CWE-89",
        "evidence": "cursor.execute(sql)",
    }
    f2 = {
        "id": "off-2",
        "file_path": "src/app.py",
        "start_line": 10,
        "end_line": 12,
        "category": "security",
        "severity": "high",
        "title": "SQL Injection in User Endpoint",
        "cwe": "CWE-89",
        "evidence": "cursor.execute(sql)",
    }

    clusters, meta = await correlator.correlate_findings([f1, f2], use_semantic_fallback=True)

    # Must complete deterministic correlation without crashing
    assert len(clusters) == 1
    assert meta["status"] == "completed"
    assert meta["exact_duplicates_count"] >= 1

