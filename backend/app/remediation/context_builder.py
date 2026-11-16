"""
Remediation context builder.

Constructs bounded, redacted, and relevant source code context for
the RemediationAgent and VerificationAgent.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.analysis.static_analysis import mask_secret


@dataclass
class RemediationContext:
    """Bounded, safe context provided to the remediation agent."""

    finding_id: str
    review_id: str
    repository_name: str
    category: str
    type: Optional[str]
    severity: str
    title: str
    description: str
    file_path: str
    start_line: int
    end_line: int
    evidence: Optional[str]
    cwe: Optional[str]

    # Source code context
    file_content: str
    surrounding_code: str  # Formatted snippet with line numbers

    # Repository intelligence
    language: str
    frameworks: List[str] = field(default_factory=list)
    dependencies: List[Dict[str, Any]] = field(default_factory=list)

    # Sub-Phase 7.5 Correlated Finding & Root Cause Intelligence
    correlated_finding_id: Optional[str] = None
    root_cause: Optional[str] = None
    constituent_findings: List[Dict[str, Any]] = field(default_factory=list)

    # Optional feedback from previous failed attempt
    previous_attempt: Optional[Dict[str, Any]] = None

    def to_dict(self) -> dict:
        return {
            "finding_id": self.finding_id,
            "review_id": self.review_id,
            "category": self.category,
            "type": self.type,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "cwe": self.cwe,
            "language": self.language,
            "frameworks": self.frameworks,
            "evidence": self.evidence,
            "surrounding_code": self.surrounding_code,
            "correlated_finding_id": self.correlated_finding_id,
            "root_cause": self.root_cause,
            "constituent_count": len(self.constituent_findings),
            "has_previous_attempt": self.previous_attempt is not None,
        }


def extract_surrounding_code(
    file_content: str,
    start_line: int,
    end_line: int,
    context_lines: int = 25,
) -> str:
    """
    Extract code snippet surrounding the target lines with 1-indexed line numbers.
    """
    lines = file_content.replace("\r\n", "\n").split("\n")
    total_lines = len(lines)

    start_idx = max(1, start_line - context_lines)
    end_idx = min(total_lines, end_line + context_lines)

    snippet_lines = []
    for i in range(start_idx, end_idx + 1):
        line_num = i
        prefix = " > " if start_line <= line_num <= end_line else "   "
        line_text = lines[line_num - 1]
        snippet_lines.append(f"{prefix}{line_num:4d} | {line_text}")

    return "\n".join(snippet_lines)


def redact_secrets_in_text(text: str) -> str:
    """
    Strictly redact sensitive tokens and credentials from text before prompting.
    """
    if not text:
        return text

    # Common secret patterns
    patterns = [
        r"(AKIA[0-9A-Z]{16})",
        r"(ghp_[0-9a-zA-Z]{36})",
        r"(github_pat_[0-9a-zA-Z_]{82})",
        r"(xox[baprs]-[0-9a-zA-Z]{10,48})",
        r"(-----BEGIN [A-Z ]+PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+PRIVATE KEY-----)",
        r"(eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})",
    ]

    redacted = text
    for pat in patterns:
        for match in re.finditer(pat, redacted):
            matched_val = match.group(0)
            redacted = redacted.replace(matched_val, mask_secret(matched_val))

    # Also replace explicit password/api_key assignment values
    cred_assign = re.compile(
        r"""(?i)(password|secret|api_key|token|access_key)\s*[:=]\s*["']([^"']{8,})["']"""
    )
    redacted = cred_assign.sub(r'\1 = "SECRET_VALUE_REDACTED"', redacted)

    return redacted


def build_remediation_context(
    finding: Any,
    file_content: str,
    repository_name: str,
    languages: Optional[Dict[str, Any]] = None,
    frameworks: Optional[List[str]] = None,
    dependencies: Optional[List[Dict[str, Any]]] = None,
    previous_attempt: Optional[Dict[str, Any]] = None,
    correlated_finding: Optional[Any] = None,
    constituent_findings: Optional[List[Dict[str, Any]]] = None,
    root_cause: Optional[str] = None,
) -> RemediationContext:
    """
    Build a safe, bounded RemediationContext instance for a finding or correlated cluster.
    """
    start_line = finding.start_line or getattr(finding, "line_number", None) or 1
    end_line = finding.end_line or start_line

    # Primary language
    lang = "plaintext"
    if languages:
        primary = languages.get("primary")
        if primary and isinstance(primary, dict):
            lang = primary.get("name", "plaintext")
        elif isinstance(primary, str):
            lang = primary

    # Redact secret values in file content and evidence
    safe_content = redact_secrets_in_text(file_content)
    safe_evidence = redact_secrets_in_text(getattr(finding, "evidence", None) or "")

    surrounding = extract_surrounding_code(
        safe_content,
        start_line=start_line,
        end_line=end_line,
        context_lines=20,
    )

    corr_id = getattr(correlated_finding, "id", None) if correlated_finding else None
    rc = root_cause or (getattr(correlated_finding, "root_cause", None) if correlated_finding else None)

    return RemediationContext(
        finding_id=finding.id,
        review_id=finding.review_id,
        repository_name=repository_name,
        category=finding.category,
        type=getattr(finding, "type", None),
        severity=finding.severity,
        title=finding.title,
        description=finding.description or "",
        file_path=finding.file_path or "",
        start_line=start_line,
        end_line=end_line,
        evidence=safe_evidence,
        cwe=getattr(finding, "cwe", None),
        file_content=safe_content,
        surrounding_code=surrounding,
        language=lang,
        frameworks=frameworks or [],
        dependencies=dependencies or [],
        correlated_finding_id=corr_id,
        root_cause=rc,
        constituent_findings=constituent_findings or [],
        previous_attempt=previous_attempt,
    )
