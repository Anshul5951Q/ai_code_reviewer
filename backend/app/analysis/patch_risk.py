"""
Deterministic Remediation Patch Risk Assessment Engine.

Axiom: Zero Blind Trust in LLM Risk Self-Reports.
Calculates objective, deterministic risk levels (LOW, MEDIUM, HIGH, CRITICAL)
based on empirical patch scope, file count, security sensitivity, database/migration impacts,
and interface modifications.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.remediation import PatchRiskAssessment, PatchRiskLevel


# Security sensitive CWE patterns that warrant elevated caution
HIGH_SENSITIVITY_CWES = {
    "CWE-798",  # Hardcoded credentials
    "CWE-287",  # Authentication bypass
    "CWE-306",  # Missing authentication
    "CWE-502",  # Deserialization of untrusted data
    "CWE-78",   # OS Command Injection
    "CWE-89",   # SQL Injection
    "CWE-22",   # Path Traversal
    "CWE-352",  # CSRF
    "CWE-94",   # Code Injection
}

CRITICAL_FILE_PATTERNS = [
    re.compile(r"(?:auth|login|session|jwt|token|crypto|cipher|secret|permission|rbac)", re.IGNORECASE),
    re.compile(r"(?:migration|alembic|schema|db[/\\]schema)", re.IGNORECASE),
    re.compile(r"(?:requirements\.txt|package\.json|pyproject\.toml|pom\.xml|go\.mod)", re.IGNORECASE),
    re.compile(r"(?:settings\.py|config\.py|\.env)", re.IGNORECASE),
]


def calculate_patch_risk(
    files_changed: List[str],
    diff: str,
    category: str = "quality",
    cwe: Optional[str] = None,
    finding_title: str = "",
) -> PatchRiskAssessment:
    """
    Deterministically assess remediation patch risk.
    Scores from 0.0 (minimal risk) to 1.0 (extreme architectural risk).
    """
    score = 0.05
    factors: List[str] = []

    # 1. File Count Impact
    file_count = len(files_changed)
    if file_count > 3:
        score += 0.35
        factors.append(f"Multi-file modification: touches {file_count} distinct files")
    elif file_count > 1:
        score += 0.20
        factors.append(f"Multi-file modification: touches {file_count} files")
    else:
        factors.append("Single-file localized change")

    # 2. Changed Lines Scope
    added_lines = 0
    removed_lines = 0
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added_lines += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed_lines += 1

    total_lines = added_lines + removed_lines
    if total_lines > 80:
        score += 0.30
        factors.append(f"Large diff scope: {total_lines} lines changed (+{added_lines}/-{removed_lines})")
    elif total_lines > 30:
        score += 0.15
        factors.append(f"Moderate diff scope: {total_lines} lines changed (+{added_lines}/-{removed_lines})")
    else:
        factors.append(f"Compact diff scope: {total_lines} lines changed")

    # 3. Security & CWE Sensitivity
    norm_cwe = (cwe or "").upper().strip()
    if norm_cwe in HIGH_SENSITIVITY_CWES:
        score += 0.30
        factors.append(f"High-impact vulnerability class: {norm_cwe}")

    # Check for authentication/crypto/session keywords in diff or title
    combined_text = (diff + " " + finding_title).lower()
    if any(k in combined_text for k in ("jwt", "secret", "password", "crypto", "token", "auth")):
        score += 0.20
        factors.append("Security-sensitive authentication or credential logic affected")

    # 4. Critical File Types
    for file_path in files_changed:
        for pat in CRITICAL_FILE_PATTERNS:
            if pat.search(file_path):
                score += 0.25
                factors.append(f"Modifies critical configuration or schema file: '{file_path}'")
                break

    # 5. Interface or Function Signature Alteration
    # Check if def/function line was modified in diff
    def_removed = [l for l in diff.splitlines() if l.startswith("-") and re.match(r"^-\s*(?:def|async def|function|public|private)\s+", l)]
    def_added = [l for l in diff.splitlines() if l.startswith("+") and re.match(r"^\+\s*(?:def|async def|function|public|private)\s+", l)]
    if def_removed and def_added and def_removed != def_added:
        score += 0.20
        factors.append("Modifies public function or method signature")

    # Clamp score
    final_score = round(min(1.0, max(0.05, score)), 2)

    # Determine risk category
    if final_score >= 0.70:
        level = PatchRiskLevel.CRITICAL.value
        explanation = "Critical risk patch: wide scope, modifies security-sensitive logic or structural interfaces."
    elif final_score >= 0.45:
        level = PatchRiskLevel.HIGH.value
        explanation = "High risk patch: multi-file modifications, significant lines changed, or core security concern."
    elif final_score >= 0.25:
        level = PatchRiskLevel.MEDIUM.value
        explanation = "Medium risk patch: moderate changes requiring targeted regression verification."
    else:
        level = PatchRiskLevel.LOW.value
        explanation = "Low risk patch: minimal, localized bug fix or maintainability improvement."

    return PatchRiskAssessment(
        level=level,
        score=final_score,
        factors=factors,
        explanation=explanation,
    )

