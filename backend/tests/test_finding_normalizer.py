"""
Unit tests for FindingNormalizer, cross-agent deduplication, and scoring.
"""
from app.analysis.finding_normalizer import (
    CanonicalFinding,
    FindingNormalizer,
    are_findings_duplicates,
    merge_duplicates,
    normalize_confidence,
    normalize_severity,
)


def test_normalize_severity():
    assert normalize_severity("CRITICAL") == "critical"
    assert normalize_severity("error") == "high"
    assert normalize_severity("warning") == "medium"
    assert normalize_severity("unknown") == "medium"


def test_normalize_confidence():
    assert normalize_confidence(0.95) == 0.95
    assert normalize_confidence(95) == 0.95  # Handles 0-100 scale
    assert normalize_confidence(1.5) == 1.0   # Clamped
    assert normalize_confidence(-0.5) == 0.0  # Clamped
    assert normalize_confidence("invalid") == 0.8


def test_deduplicate_identical_issues():
    normalizer = FindingNormalizer()

    f1 = {
        "category": "security",
        "type": "sql_injection",
        "severity": "high",
        "title": "Potential SQL Injection",
        "file_path": "src/api/users.py",
        "start_line": 42,
        "end_line": 42,
        "confidence": 0.88,
        "evidence": "db.execute(f'...')",
        "cwe": "CWE-89",
        "source": "security_static",
    }

    f2 = {
        "category": "security",
        "type": "sql_injection",
        "severity": "high",
        "title": "Verified SQL Injection in Query Construction",
        "file_path": "src/api/users.py",
        "start_line": 40,
        "end_line": 45,
        "confidence": 0.95,
        "evidence": "db.execute(f'...')",
        "cwe": "CWE-89",
        "source": "security_agent",
    }

    normalized = normalizer.normalize([f1, f2])
    assert len(normalized) == 2

    deduped = normalizer.deduplicate(normalized)
    assert len(deduped) == 1
    assert deduped[0].confidence == 0.95
    assert deduped[0].cwe == "CWE-89"
    assert "security_agent" in deduped[0].source
    assert "security_static" in deduped[0].source


def test_non_duplicates_preserved():
    normalizer = FindingNormalizer()

    f1 = {
        "category": "security",
        "severity": "high",
        "title": "SQL Injection",
        "file_path": "src/api/users.py",
        "start_line": 42,
    }
    f2 = {
        "category": "security",
        "severity": "high",
        "title": "SQL Injection",
        "file_path": "src/api/posts.py",  # Different file
        "start_line": 42,
    }
    f3 = {
        "category": "security",
        "severity": "high",
        "title": "SQL Injection",
        "file_path": "src/api/users.py",
        "start_line": 150,  # Same file, far away line
    }

    normalized = normalizer.normalize([f1, f2, f3])
    deduped = normalizer.deduplicate(normalized)
    assert len(deduped) == 3


def test_deterministic_scoring():
    normalizer = FindingNormalizer()

    # Empty findings -> perfect score 100
    scores_empty = normalizer.calculate_scores([])
    assert scores_empty["overall_score"] == 100.0
    assert scores_empty["security_score"] == 100.0
    assert scores_empty["quality_score"] == 100.0

    # 1 critical security finding (conf=1.0) -> -25 points from security score
    f_crit = CanonicalFinding(
        category="security",
        severity="critical",
        title="Remote Code Execution",
        description="...",
        confidence=1.0,
    )
    scores_crit = normalizer.calculate_scores([f_crit])
    assert scores_crit["security_score"] == 75.0
    assert scores_crit["quality_score"] == 100.0
    # Overall is 0.45 * 75 + 0.35 * 100 + 0.20 * 100 = 33.75 + 35 + 20 = 88.75 -> 88.8
    assert scores_crit["overall_score"] == 88.8
