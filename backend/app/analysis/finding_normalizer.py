"""
Finding normalization, deduplication, and deterministic scoring engine.

Normalizes raw findings from static analysis, code review agents, and security agents
into canonical finding records. Deduplicates overlapping findings across agents.
Calculates deterministic review scores based on findings count, severity, and confidence.
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

VALID_SEVERITIES = {"critical", "high", "medium", "low", "info"}
VALID_CATEGORIES = {"security", "quality", "maintainability", "architecture", "performance", "dependency"}


@dataclass
class CanonicalFinding:
    """Normalized, deduplicated finding ready for persistence."""

    category: str
    severity: str
    title: str
    description: str
    file_path: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    confidence: float = 0.8
    evidence: Optional[str] = None
    cwe: Optional[str] = None
    type: Optional[str] = None
    source: str = "code_review_agent"
    status: str = "open"

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "confidence": round(self.confidence, 2),
            "evidence": self.evidence,
            "cwe": self.cwe,
            "type": self.type,
            "source": self.source,
            "status": self.status,
        }


def normalize_severity(severity: str) -> str:
    """Ensure severity is one of critical | high | medium | low | info."""
    s = (severity or "medium").strip().lower()
    if s in VALID_SEVERITIES:
        return s
    # Map common synonyms
    mapping = {
        "error": "high",
        "warn": "medium",
        "warning": "medium",
        "notice": "low",
        "suggestion": "info",
        "informational": "info",
        "blocker": "critical",
    }
    return mapping.get(s, "medium")


def normalize_confidence(confidence: Any) -> float:
    """Clamp confidence to 0.0 <= confidence <= 1.0."""
    try:
        val = float(confidence)
        if val >= 10.0 and val <= 100.0:
            # Handle percentage scale 10-100 (e.g. 85 -> 0.85, 95 -> 0.95)
            val = val / 100.0
        return round(max(0.0, min(1.0, val)), 2)
    except (TypeError, ValueError):
        return 0.8


def normalize_category(category: str) -> str:
    c = (category or "quality").strip().lower()
    return c if c in VALID_CATEGORIES else "quality"


def are_findings_duplicates(f1: CanonicalFinding, f2: CanonicalFinding) -> bool:
    """
    Determine if two findings from different sources represent the same issue.

    Conditions:
    1. Same file (or both have no file)
    2. Overlapping or close line numbers (within 5 lines)
    3. Either:
       a) Same category and similar title (> 65% token/char similarity)
       b) One is a security static rule and the other is security agent on the same line
       c) Same CWE identifier
    """
    if f1.file_path != f2.file_path:
        return False

    # Check line proximity
    lines_match = False
    if f1.start_line is not None and f2.start_line is not None:
        l1_start = f1.start_line
        l1_end = f1.end_line or l1_start
        l2_start = f2.start_line
        l2_end = f2.end_line or l2_start

        # Overlapping or within 5 lines
        if max(l1_start, l2_start) <= min(l1_end, l2_end) + 5:
            lines_match = True
    elif f1.start_line is None and f2.start_line is None:
        lines_match = True

    if not lines_match:
        return False

    # CWE match
    if f1.cwe and f2.cwe and f1.cwe == f2.cwe:
        return True

    # Same security type (e.g. sql_injection)
    if f1.type and f2.type and f1.type == f2.type:
        return True

    # Title string similarity
    similarity = difflib.SequenceMatcher(
        None, f1.title.lower(), f2.title.lower()
    ).ratio()
    if similarity >= 0.65:
        return True

    # Security cross-agent match on same line (e.g. static rule + LLM security assessment)
    if f1.category == "security" and f2.category == "security":
        return True

    return False


def merge_duplicates(f1: CanonicalFinding, f2: CanonicalFinding) -> CanonicalFinding:
    """Merge two duplicate findings into a single high-fidelity finding."""
    # Priority for severity: critical > high > medium > low > info
    sev_order = {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}
    best_sev = f1.severity if sev_order.get(f1.severity, 0) >= sev_order.get(f2.severity, 0) else f2.severity

    # Higher confidence
    best_conf = max(f1.confidence, f2.confidence)

    # Prefer agent title if descriptive, or longest
    title = f1.title if len(f1.title) >= len(f2.title) else f2.title
    description = f1.description if len(f1.description) >= len(f2.description) else f2.description
    evidence = f1.evidence or f2.evidence

    # Prefer valid CWE
    cwe = f1.cwe or f2.cwe
    finding_type = f1.type or f2.type

    # Track combined source
    sources = set(f1.source.split(" + ") + f2.source.split(" + "))
    combined_source = " + ".join(sorted(sources))

    # Bounded lines
    s_line = min(f1.start_line or 999999, f2.start_line or 999999)
    if s_line == 999999:
        s_line = None
    e_line = max(f1.end_line or 0, f2.end_line or 0)
    if e_line == 0:
        e_line = None

    return CanonicalFinding(
        category=f1.category if f1.category == "security" else f2.category,
        severity=best_sev,
        title=title,
        description=description,
        file_path=f1.file_path or f2.file_path,
        start_line=s_line,
        end_line=e_line,
        confidence=best_conf,
        evidence=evidence,
        cwe=cwe,
        type=finding_type,
        source=combined_source,
        status="open",
    )


class FindingNormalizer:
    """Normalizes and deduplicates findings, and computes deterministic scores."""

    def normalize(self, raw_findings: List[Dict[str, Any]]) -> List[CanonicalFinding]:
        """Convert heterogeneous dictionary findings into CanonicalFinding items."""
        normalized: List[CanonicalFinding] = []
        for raw in raw_findings:
            start_l = raw.get("start_line")
            end_l = raw.get("end_line")
            # If line_number was passed instead of start_line
            if start_l is None and raw.get("line_number") is not None:
                start_l = raw.get("line_number")
                end_l = raw.get("line_number")

            nf = CanonicalFinding(
                category=normalize_category(raw.get("category", "quality")),
                severity=normalize_severity(raw.get("severity", "medium")),
                title=str(raw.get("title", "Untitled Finding")).strip(),
                description=str(raw.get("description", "")).strip(),
                file_path=raw.get("file_path"),
                start_line=int(start_l) if start_l is not None else None,
                end_line=int(end_l) if end_l is not None else None,
                confidence=normalize_confidence(raw.get("confidence", 0.8)),
                evidence=raw.get("evidence"),
                cwe=raw.get("cwe"),
                type=raw.get("type"),
                source=raw.get("source", "code_review_agent"),
                status=raw.get("status", "open"),
            )
            normalized.append(nf)
        return normalized

    def deduplicate(self, findings: List[CanonicalFinding]) -> List[CanonicalFinding]:
        """Merge duplicate findings referencing the same problem in the same file."""
        if not findings:
            return []

        deduped: List[CanonicalFinding] = []
        for candidate in findings:
            merged = False
            for i, existing in enumerate(deduped):
                if are_findings_duplicates(existing, candidate):
                    deduped[i] = merge_duplicates(existing, candidate)
                    merged = True
                    break
            if not merged:
                deduped.append(candidate)

        return deduped

    def calculate_scores(
        self,
        findings: List[CanonicalFinding],
        architecture_risks_count: int = 0,
    ) -> Dict[str, float]:
        """
        Calculate deterministic scores from 0.0 to 100.0 based on findings.

        Formula: 100.0 - severity-weighted deductions scaled by confidence.
        """
        sec_deductions = {
            "critical": 25.0,
            "high": 15.0,
            "medium": 7.0,
            "low": 2.0,
            "info": 0.5,
        }
        qual_deductions = {
            "critical": 20.0,
            "high": 10.0,
            "medium": 5.0,
            "low": 2.0,
            "info": 0.5,
        }

        sec_penalty = 0.0
        qual_penalty = 0.0

        for f in findings:
            if f.category == "security":
                sec_penalty += sec_deductions.get(f.severity, 3.0) * f.confidence
            else:
                qual_penalty += qual_deductions.get(f.severity, 2.0) * f.confidence

        arch_penalty = architecture_risks_count * 5.0

        security_score = round(max(0.0, min(100.0, 100.0 - sec_penalty)), 1)
        quality_score = round(max(0.0, min(100.0, 100.0 - qual_penalty)), 1)
        architecture_score = round(max(0.0, min(100.0, 100.0 - arch_penalty)), 1)

        # Overall weighted score
        overall = (
            0.45 * security_score
            + 0.35 * quality_score
            + 0.20 * architecture_score
        )
        overall_score = round(max(0.0, min(100.0, overall)), 1)

        return {
            "overall_score": overall_score,
            "security_score": security_score,
            "quality_score": quality_score,
            "architecture_score": architecture_score,
        }
