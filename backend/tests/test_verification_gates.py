"""Unit tests for Phase 7 Verification Gates."""
from __future__ import annotations

import pytest

from app.agents.verification_gates import (
    DeterministicDecisionEngine,
    PatchValidationGate,
    QualityVerificationGate,
    SecurityVerificationGate,
    UnderstandingVerificationGate,
)


def test_understanding_gate_scrubs_hallucinations():
    gate = UnderstandingVerificationGate()
    raw_output = {
        "architecture_summary": "Test web app",
        "entry_points": ["backend/app/main.py", "frontend/src/index.ts", "fake/nonexistent/script.py"],
        "important_modules": ["backend/app", "completely_fake_dir"],
    }
    known_files = {"backend/app/main.py", "backend/app/api.py", "frontend/src/index.ts"}

    sanitized, meta = gate.verify(raw_output, known_files)

    assert "backend/app/main.py" in sanitized["entry_points"]
    assert "frontend/src/index.ts" in sanitized["entry_points"]
    assert "fake/nonexistent/script.py" not in sanitized["entry_points"]
    assert "fake/nonexistent/script.py" in meta["expunged_entry_points"]
    assert "completely_fake_dir" in meta["expunged_modules"]


def test_quality_gate_validates_lines_and_confidence():
    gate = QualityVerificationGate()
    files = {"src/app.py": "def foo():\n    return 1\n"}

    # Valid finding
    valid, err = gate.verify_finding(
        {"file_path": "src/app.py", "start_line": 1, "end_line": 2, "confidence": 0.85},
        files,
    )
    assert valid is True
    assert err is None

    # Invalid line number out of range
    valid, err = gate.verify_finding(
        {"file_path": "src/app.py", "start_line": 50, "end_line": 60, "confidence": 0.85},
        files,
    )
    assert valid is False
    assert "out of range" in err

    # Non-existent file
    valid, err = gate.verify_finding(
        {"file_path": "src/missing.py", "start_line": 1, "end_line": 1, "confidence": 0.85},
        files,
    )
    assert valid is False
    assert "does not exist" in err

    # Low confidence
    valid, err = gate.verify_finding(
        {"file_path": "src/app.py", "start_line": 1, "end_line": 2, "confidence": 0.40},
        files,
    )
    assert valid is False
    assert "below threshold" in err


def test_security_gate_anti_cve_and_secret_redaction():
    gate = SecurityVerificationGate()
    files = {"src/auth.py": "API_KEY = 'AKIA1234567890ABCDEF'\n"}

    finding = {
        "file_path": "src/auth.py",
        "start_line": 1,
        "end_line": 1,
        "title": "Critical CVE-2024-99999 Vulnerability",
        "description": "Exposes API_KEY = 'AKIA1234567890ABCDEF' in plaintext",
        "cwe": "89",
        "evidence": "AKIA1234567890ABCDEF",
        "confidence": 0.95,
    }

    valid, err = gate.verify_finding(finding, files)
    assert valid is True
    assert err is None
    # CVE must be scrubbed
    assert "CVE-2024-99999" not in finding["title"]
    # Secret must be redacted
    assert "AKIA1234567890ABCDEF" not in finding["evidence"]
    assert "*" in finding["evidence"]
    # CWE formatted
    assert finding["cwe"] == "CWE-89"


def test_patch_validation_gate():
    gate = PatchValidationGate()
    files = {"app/calc.py": "def add(a, b):\n    return a - b\n"}

    # 1. Path traversal rejected
    valid, err = gate.validate_patch("--- a/../etc/passwd\n+++ b/../etc/passwd\n", "../etc/passwd", files)
    assert valid is False
    assert "path traversal" in err

    # 2. Malformed diff header rejected
    valid, err = gate.validate_patch("Just some random text without diff header", "app/calc.py", files)
    assert valid is False
    assert "Malformed patch diff" in err

    # 3. Python syntax error rejected
    bad_syntax_diff = (
        "--- a/app/calc.py\n"
        "+++ b/app/calc.py\n"
        "@@ -1,2 +1,2 @@\n"
        " def add(a, b):\n"
        "-    return a - b\n"
        "+    return a + (invalid syntax here\n"
    )
    valid, err = gate.validate_patch(bad_syntax_diff, "app/calc.py", files)
    assert valid is False
    assert "syntax error" in err.lower()

    # 4. Valid patch passes
    good_diff = (
        "--- a/app/calc.py\n"
        "+++ b/app/calc.py\n"
        "@@ -1,2 +1,2 @@\n"
        " def add(a, b):\n"
        "-    return a - b\n"
        "+    return a + b\n"
    )
    valid, err = gate.validate_patch(good_diff, "app/calc.py", files)
    assert valid is True
    assert err is None


def test_deterministic_decision_engine():
    # 1. Patch invalid
    status, reason = DeterministicDecisionEngine.evaluate(
        patch_valid=False,
        syntax_valid=True,
        static_finding_cleared=True,
        auditor_verdict="fixed",
    )
    assert status == "verification_failed"

    # 2. Syntax invalid
    status, reason = DeterministicDecisionEngine.evaluate(
        patch_valid=True,
        syntax_valid=False,
        static_finding_cleared=True,
        auditor_verdict="fixed",
    )
    assert status == "verification_failed"

    # 3. Static rule still fires even though auditor said fixed
    status, reason = DeterministicDecisionEngine.evaluate(
        patch_valid=True,
        syntax_valid=True,
        static_finding_cleared=False,
        auditor_verdict="fixed",
    )
    assert status == "still_vulnerable"

    # 4. Both static cleared and auditor says fixed -> RESOLVED
    status, reason = DeterministicDecisionEngine.evaluate(
        patch_valid=True,
        syntax_valid=True,
        static_finding_cleared=True,
        auditor_verdict="fixed",
    )
    assert status == "resolved"

    # 5. Regression detected
    status, reason = DeterministicDecisionEngine.evaluate(
        patch_valid=True,
        syntax_valid=True,
        static_finding_cleared=True,
        auditor_verdict="regression_detected",
    )
    assert status == "verification_failed"
