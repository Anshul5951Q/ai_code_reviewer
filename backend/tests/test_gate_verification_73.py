"""
Comprehensive edge-case and boundary tests for Gate 2 and Gate 3.
Zero Blind Trust: Tests validation against fabricated snippets, path traversal,
prompt injection, generic findings, invalid line bounds, and secret leakage.
"""
from __future__ import annotations

import pytest

from app.agents.verification_gates import (
    QualityVerificationGate,
    SecurityVerificationGate,
)

SAMPLE_FILES = {
    "src/calc.py": (
        "def compute(a, b):\n"
        "    if a > 0:\n"
        "        return a + b\n"
        "    return a - b\n"
    ),
    "src/auth.py": (
        "def authenticate(token):\n"
        "    API_KEY = 'AKIA1234567890SECRETKEY'\n"
        "    return token == API_KEY\n"
    ),
    "src/db.py": (
        "def query_users(user_id):\n"
        "    cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')\n"
        "    return cursor.fetchall()\n"
    ),
}


# ── Gate 2 (QualityVerificationGate) Edge Case Tests ─────────────────────────

def test_gate2_rejects_nonexistent_file():
    gate = QualityVerificationGate()
    valid, err = gate.verify_finding(
        {"file_path": "nonexistent/file.py", "start_line": 1, "end_line": 2, "confidence": 0.85},
        SAMPLE_FILES,
    )
    assert valid is False
    assert "does not exist" in err


def test_gate2_rejects_path_traversal():
    gate = QualityVerificationGate()
    traversal_paths = ["../etc/passwd", "../../secret.txt", "/etc/shadow", "C:\\Windows\\system32"]
    for path in traversal_paths:
        valid, err = gate.verify_finding(
            {"file_path": path, "start_line": 1, "end_line": 2, "confidence": 0.85},
            SAMPLE_FILES,
        )
        assert valid is False
        assert "illegal path traversal" in err or "does not exist" in err


def test_gate2_rejects_out_of_range_lines():
    gate = QualityVerificationGate()
    valid, err = gate.verify_finding(
        {"file_path": "src/calc.py", "start_line": 50, "end_line": 55, "confidence": 0.85},
        SAMPLE_FILES,
    )
    assert valid is False
    assert "out of range" in err


def test_gate2_handles_inverted_lines():
    gate = QualityVerificationGate()
    finding = {"file_path": "src/calc.py", "start_line": 4, "end_line": 1, "confidence": 0.85}
    valid, err = gate.verify_finding(finding, SAMPLE_FILES)
    assert valid is True
    # Start and end should be swapped to valid order
    assert finding["start_line"] == 1
    assert finding["end_line"] == 4


def test_gate2_rejects_fabricated_evidence_snippet():
    gate = QualityVerificationGate()
    valid, err = gate.verify_finding(
        {
            "file_path": "src/calc.py",
            "start_line": 1,
            "end_line": 3,
            "evidence": "completely_fabricated_function_that_does_not_exist()",
            "confidence": 0.85,
        },
        SAMPLE_FILES,
    )
    assert valid is False
    assert "Fabricated or mismatched evidence" in err


def test_gate2_accepts_normalized_whitespace_snippet():
    gate = QualityVerificationGate()
    # Evidence has different leading indentation or formatting
    evidence_with_whitespace = "    if a > 0:   \n   return a + b"
    valid, err = gate.verify_finding(
        {
            "file_path": "src/calc.py",
            "start_line": 2,
            "end_line": 3,
            "evidence": evidence_with_whitespace,
            "confidence": 0.85,
        },
        SAMPLE_FILES,
    )
    assert valid is True
    assert err is None


def test_gate2_rejects_generic_claims():
    gate = QualityVerificationGate()
    generic_titles = [
        "code is not optimized",
        "code smell detected",
        "needs improvement",
        "optimize code",
        "refactor code",
    ]
    for gt in generic_titles:
        valid, err = gate.verify_finding(
            {
                "file_path": "src/calc.py",
                "start_line": 1,
                "end_line": 2,
                "title": gt,
                "confidence": 0.85,
            },
            SAMPLE_FILES,
        )
        assert valid is False
        assert "Generic or non-specific" in err


def test_gate2_rejects_stylistic_preferences():
    gate = QualityVerificationGate()
    valid, err = gate.verify_finding(
        {
            "file_path": "src/calc.py",
            "start_line": 1,
            "end_line": 2,
            "title": "Prefer single quotes across modules",
            "description": "Developer should use single quotes instead of double quotes for style consistency.",
            "confidence": 0.85,
        },
        SAMPLE_FILES,
    )
    assert valid is False
    assert "Subjective styling preference" in err


def test_gate2_rejects_low_confidence():
    gate = QualityVerificationGate()
    valid, err = gate.verify_finding(
        {
            "file_path": "src/calc.py",
            "start_line": 1,
            "end_line": 2,
            "title": "High Cognitive Complexity",
            "confidence": 0.40,  # Below threshold 0.65
        },
        SAMPLE_FILES,
    )
    assert valid is False
    assert "below threshold" in err


def test_gate2_batch_verify_status_reporting():
    gate = QualityVerificationGate()
    findings = [
        {
            "file_path": "src/calc.py",
            "start_line": 1,
            "end_line": 2,
            "title": "High Complexity in compute",
            "confidence": 0.85,
            "evidence": "def compute(a, b):",
        },
        {
            "file_path": "fake/missing.py",
            "start_line": 1,
            "end_line": 2,
            "title": "Hallucinated file",
            "confidence": 0.85,
        },
    ]

    val, meta = gate.verify_findings(findings, SAMPLE_FILES)
    assert len(val) == 1
    assert meta["validated_count"] == 1
    assert meta["rejected_count"] == 1
    assert meta["status"] == "verified_with_scrubbing"


# ── Gate 3 (SecurityVerificationGate) Edge Case Tests ─────────────────────────

def test_gate3_rejects_nonexistent_file():
    gate = SecurityVerificationGate()
    valid, err = gate.verify_finding(
        {"file_path": "fake/sec.py", "start_line": 1, "end_line": 2, "confidence": 0.90},
        SAMPLE_FILES,
    )
    assert valid is False
    assert "does not exist" in err


def test_gate3_rejects_path_traversal():
    gate = SecurityVerificationGate()
    valid, err = gate.verify_finding(
        {"file_path": "../../etc/shadow", "start_line": 1, "end_line": 2, "confidence": 0.90},
        SAMPLE_FILES,
    )
    assert valid is False
    assert "illegal path traversal" in err or "does not exist" in err


def test_gate3_rejects_fabricated_snippet():
    gate = SecurityVerificationGate()
    valid, err = gate.verify_finding(
        {
            "file_path": "src/db.py",
            "start_line": 1,
            "end_line": 2,
            "evidence": "SELECT * FROM credit_cards WHERE secret = 123",
            "confidence": 0.90,
        },
        SAMPLE_FILES,
    )
    assert valid is False
    assert "Fabricated or mismatched security snippet" in err


def test_gate3_anti_cve_invention_scrubbing():
    gate = SecurityVerificationGate()
    finding = {
        "file_path": "src/db.py",
        "start_line": 2,
        "end_line": 2,
        "title": "Severe CVE-2025-13370 Database Exploit",
        "description": "Allows command execution via CVE-2025-13370.",
        "evidence": "cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')",
        "cwe": "CWE-89",
        "confidence": 0.95,
    }
    valid, err = gate.verify_finding(finding, SAMPLE_FILES)
    assert valid is True
    assert "CVE-2025-13370" not in finding["title"]
    assert "CVE-2025-13370" not in finding["description"]


def test_gate3_secret_masking():
    gate = SecurityVerificationGate()
    finding = {
        "file_path": "src/auth.py",
        "start_line": 2,
        "end_line": 2,
        "title": "Hardcoded Secret Token AKIA1234567890SECRETKEY",
        "description": "Leaked credential AKIA1234567890SECRETKEY found in source.",
        "evidence": "API_KEY = 'AKIA1234567890SECRETKEY'",
        "cwe": "CWE-798",
        "confidence": 0.95,
    }
    valid, err = gate.verify_finding(finding, SAMPLE_FILES)
    assert valid is True
    assert "AKIA1234567890SECRETKEY" not in finding["title"]
    assert "AKIA1234567890SECRETKEY" not in finding["description"]
    assert "AKIA1234567890SECRETKEY" not in finding["evidence"]
    assert "*" in finding["evidence"]


def test_gate3_cwe_formatting():
    gate = SecurityVerificationGate()
    finding = {
        "file_path": "src/db.py",
        "start_line": 2,
        "end_line": 2,
        "title": "SQL Injection",
        "description": "Unsanitized user_id parameter reaches query execution.",
        "evidence": "cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')",
        "cwe": "89",
        "confidence": 0.90,
    }
    valid, err = gate.verify_finding(finding, SAMPLE_FILES)
    assert valid is True
    assert finding["cwe"] == "CWE-89"


def test_gate3_batch_verify_status_reporting():
    gate = SecurityVerificationGate()
    findings = [
        {
            "file_path": "src/db.py",
            "start_line": 2,
            "end_line": 2,
            "title": "SQL Injection",
            "evidence": "cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')",
            "cwe": "CWE-89",
            "confidence": 0.90,
        },
        {
            "file_path": "src/auth.py",
            "start_line": 100,  # Invalid line
            "end_line": 105,
            "title": "Invalid coordinates",
            "confidence": 0.90,
        },
    ]

    val, meta = gate.verify_findings(findings, SAMPLE_FILES)
    assert len(val) == 1
    assert meta["validated_count"] == 1
    assert meta["rejected_count"] == 1
    assert meta["status"] == "verified_with_scrubbing"

