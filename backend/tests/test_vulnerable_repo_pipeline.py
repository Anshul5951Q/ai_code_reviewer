"""
Phase 7 End-to-End Vulnerability Fixture & Verification Pipeline Tests.

Tests deterministic analysis, agent verification gates, secret masking,
anti-CVE rules, patch safety gates, and deterministic decision engine
against an intentionally vulnerable synthetic codebase.
"""
import ast
import uuid
import pytest

from app.agents.verification_gates import (
    DeterministicDecisionEngine,
    PatchValidationGate,
    QualityVerificationGate,
    SecurityVerificationGate,
    UnderstandingVerificationGate,
)
from app.analysis.static_analysis import StaticSecurityAnalyzer
from app.remediation.patch_generator import apply_code_change, generate_unified_diff

# Intentionally vulnerable repository fixture files
VULNERABLE_REPO_FIXTURE = {
    "src/db/users.py": """
import sqlite3

def get_user_by_id(db_conn, user_id: str):
    cursor = db_conn.cursor()
    # Vulnerability: SQL Injection (CWE-89)
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    return cursor.execute(query).fetchone()
""",
    "src/web/views.py": """
from flask import Flask, request
app = Flask(__name__)

@app.route('/greet')
def greet():
    name = request.args.get('name', '')
    # Vulnerability: Reflected XSS (CWE-79)
    return f"<h1>Welcome, {name}!</h1>"
""",
    "src/utils/system.py": """
import os

def ping_host(host: str):
    # Vulnerability: Command Injection (CWE-78)
    return os.system(f"ping -c 1 {host}")
""",
    "src/storage/reader.py": """
import os

def read_user_file(filename: str):
    # Vulnerability: Path Traversal (CWE-22)
    with open(f"/var/data/{filename}", "r") as f:
        return f.read()
""",
    "src/config/keys.py": """
# Vulnerability: Hardcoded AWS Secret (CWE-798)
AWS_SECRET_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
DATABASE_URL = "postgres://admin:password123@localhost/prod"
""",
    "src/core/calc.py": """
def evaluate_metrics(a, b, c, d, e):
    # Quality Issue: High Cyclomatic & Cognitive Complexity
    if a:
        if b:
            if c:
                if d:
                    if e:
                        return a + b + c + d + e
                    return a + b + c + d
                return a + b + c
            return a + b
        return a
    return 0
""",
}


def test_deterministic_scanner_on_fixture():
    """Verify deterministic static security scanner flags vulnerable patterns without LLM."""
    analyzer = StaticSecurityAnalyzer()
    findings = analyzer.analyze_repository_files(VULNERABLE_REPO_FIXTURE)

    cwes = {f.cwe for f in findings if f.cwe}
    assert "CWE-89" in cwes  # SQL Injection
    assert "CWE-78" in cwes  # Command Injection
    assert "CWE-22" in cwes  # Path Traversal
    assert "CWE-798" in cwes  # Hardcoded Secret

    # Verify secrets in static findings are masked
    secret_findings = [f for f in findings if f.cwe == "CWE-798"]
    assert len(secret_findings) >= 1
    assert "AKIAIOSFODNN7EXAMPLE" not in secret_findings[0].evidence
    assert "AKIA****************" in secret_findings[0].evidence


def test_gate1_scrubs_hallucinations_on_fixture():
    """Gate 1 must scrub non-existent files and phantom modules."""
    gate = UnderstandingVerificationGate()
    raw_ai_understanding = {
        "entry_points": ["src/web/views.py", "phantom/entry.py", "non_existent.py"],
        "important_modules": ["src/db", "src/web", "phantom_microservice"],
        "architecture_summary": "Flask-based service with data and storage modules",
    }
    sanitized, meta = gate.verify(raw_ai_understanding, set(VULNERABLE_REPO_FIXTURE.keys()))

    assert sanitized["entry_points"] == ["src/web/views.py"]
    assert "src/db" in sanitized["important_modules"]
    assert "src/web" in sanitized["important_modules"]
    assert "phantom_microservice" not in sanitized["important_modules"]
    assert meta["status"] == "verified_with_scrubbing"
    assert "phantom/entry.py" in meta["expunged_entry_points"]


def test_gate2_quality_verification():
    """Gate 2 validates line boundaries and rejects out-of-range lines."""
    gate = QualityVerificationGate()
    valid_finding = {
        "file_path": "src/core/calc.py",
        "start_line": 2,
        "end_line": 14,
        "confidence": 0.85,
        "title": "Complex nested branching",
    }
    valid, reason = gate.verify_finding(valid_finding, VULNERABLE_REPO_FIXTURE)
    assert valid is True

    # Hallucinated line out of bounds (calc.py is ~17 lines)
    invalid_finding = {
        "file_path": "src/core/calc.py",
        "start_line": 999,
        "end_line": 1050,
        "confidence": 0.90,
    }
    valid, reason = gate.verify_finding(invalid_finding, VULNERABLE_REPO_FIXTURE)
    assert valid is False
    assert "out of range" in reason


def test_gate3_security_anti_cve_and_secret_redaction():
    """Gate 3 strips invented CVEs, enforces CWE formatting, and redacts secrets."""
    gate = SecurityVerificationGate()
    raw_ai_finding = {
        "file_path": "src/config/keys.py",
        "start_line": 2,
        "end_line": 3,
        "confidence": 0.92,
        "cwe": "798",
        "title": "Critical vulnerability CVE-2024-99999 discovered in keys.py",
        "description": "Exposed AWS credential AKIAIOSFODNN7EXAMPLE matching CVE-2024-99999 pattern",
        "evidence": 'AWS_SECRET_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"',
    }
    valid, reason = gate.verify_finding(raw_ai_finding, VULNERABLE_REPO_FIXTURE)
    assert valid is True
    # CWE formatted
    assert raw_ai_finding["cwe"] == "CWE-798"
    # CVE invented by LLM expunged
    assert "CVE-2024-99999" not in raw_ai_finding["title"]
    assert "CVE-2024-99999" not in raw_ai_finding["description"]
    # Secret redacted
    assert "AKIAIOSFODNN7EXAMPLE" not in raw_ai_finding["evidence"]
    assert "AKIAIOSFODNN7EXAMPLE" not in raw_ai_finding["description"]
    assert "******" in raw_ai_finding["evidence"]


def test_gate4_patch_validation_and_safety():
    """Gate 4 prevents path traversal, malformed diffs, and broken syntax."""
    gate = PatchValidationGate()
    target = "src/db/users.py"
    orig_code = VULNERABLE_REPO_FIXTURE[target]

    # Valid clean patch
    modified_code = orig_code.replace(
        "query = f\"SELECT * FROM users WHERE id = '{user_id}'\"\n    return cursor.execute(query).fetchone()",
        "query = \"SELECT * FROM users WHERE id = ?\"\n    return cursor.execute(query, (user_id,)).fetchone()",
    )
    clean_diff = generate_unified_diff(
        file_path=target,
        original_content=orig_code,
        modified_content=modified_code,
    )
    valid, reason = gate.validate_patch(clean_diff, target, VULNERABLE_REPO_FIXTURE)
    assert valid is True
    assert reason is None

    # Malicious patch attempting path traversal
    evil_diff = (
        "--- a/src/db/users.py\n"
        "+++ b/src/db/../../etc/passwd\n"
        "@@ -1,1 +1,1 @@\n"
        "-# test\n"
        "+# test\n"
    )
    valid, reason = gate.validate_patch(evil_diff, target, VULNERABLE_REPO_FIXTURE)
    assert valid is False
    assert "traversal" in reason.lower()

    # Broken Python syntax patch
    syntax_error_diff = (
        "--- a/src/db/users.py\n"
        "+++ b/src/db/users.py\n"
        "@@ -6,1 +6,1 @@\n"
        "-    query = f\"SELECT * FROM users WHERE id = '{user_id}'\"\n"
        "+    query = (broken syntax def class %%\n"
    )
    valid, reason = gate.validate_patch(syntax_error_diff, target, VULNERABLE_REPO_FIXTURE)
    assert valid is False
    assert "syntax error" in reason.lower()


def test_gate5_deterministic_decision_engine_rules():
    """Gate 5 enforces Zero Blind Trust: cannot resolve if static scanner flags or syntax fails."""
    engine = DeterministicDecisionEngine()

    # Case 1: All passed -> resolved
    verdict, reason = engine.evaluate(
        patch_valid=True,
        syntax_valid=True,
        static_finding_cleared=True,
        auditor_verdict="resolved",
    )
    assert verdict == "resolved"

    # Case 2: LLM claimed "resolved", but static security scanner still flagged the issue!
    # Engine MUST override and declare still_vulnerable!
    verdict, reason = engine.evaluate(
        patch_valid=True,
        syntax_valid=True,
        static_finding_cleared=False,  # Still triggers!
        auditor_verdict="resolved",
    )
    assert verdict == "still_vulnerable"
    assert "static security rule" in reason

    # Case 3: Syntax error in patch
    verdict, reason = engine.evaluate(
        patch_valid=True,
        syntax_valid=False,  # Broken syntax!
        static_finding_cleared=True,
        auditor_verdict="resolved",
    )
    assert verdict == "verification_failed"

    # Case 4: Regressions introduced
    verdict, reason = engine.evaluate(
        patch_valid=True,
        syntax_valid=True,
        static_finding_cleared=True,
        auditor_verdict="regression_detected",
        introduced_issues=[{"title": "Buffer overflow"}],
    )
    assert verdict == "verification_failed"
    assert "regressions" in reason
