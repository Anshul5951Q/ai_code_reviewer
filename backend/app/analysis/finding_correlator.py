"""
Finding Correlator & Cross-Agent Finding Intelligence Engine.

Synthesizes validated findings from Code Quality Agent (Gate 2), Security Detection Agent (Gate 3),
and Code Understanding Agent (Gate 1) into unified, traceable, prioritized correlated findings.

Core Capabilities:
1. Exact Duplicate Detection (multi-rule / repeated scan matches)
2. Overlapping Finding Detection (same function/lines, different consequences)
3. Root-Cause Correlation (e.g., missing validation -> SQLi + business logic error)
4. Independent Finding Preservation (guarantees separate concerns are never merged)
5. Explainable Severity Prioritization Policy (strict anti-downgrade and anti-escalation rules)
6. Traceability: Original Finding records, severities, confidence, and evidence are never lost.
7. Hybrid: Deterministic matching first; Ollama semantic evaluation when inconclusive;
   graceful deterministic fallback if Ollama is unavailable.
"""
from __future__ import annotations

import difflib
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import get_llm_provider
from app.llm.prompts import FINDING_CORRELATION_SYSTEM_PROMPT
from app.llm.provider import LLMProvider
from app.models.correlated_finding import CorrelatedFinding
from app.models.finding import Finding
from app.models.finding_relationship import FindingRelationship

logger = logging.getLogger("ai_code_reviewer.analysis.finding_correlator")

# Severity order: highest priority to lowest
SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]
SEVERITY_SCORES = {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}

# Known root-cause signature patterns (Deterministic matching)
ROOT_CAUSE_SIGNATURES: List[Dict[str, Any]] = [
    {
        "name": "Unvalidated User Input reaching Database Query Sink",
        "cwe": "CWE-89",
        "quality_types": {"missing_validation", "input_validation", "poor_error_handling", "cyclomatic_complexity"},
        "shared_cause": "Missing boundary validation allows unsanitized external input to be passed to database layer",
    },
    {
        "name": "Unsanitized Path Parameter reaching Filesystem Sink",
        "cwe": "CWE-22",
        "quality_types": {"missing_validation", "insecure_file_handling", "resource_leak"},
        "shared_cause": "Filesystem path constructed from external parameter without path traversal sanitization",
    },
    {
        "name": "Unvalidated Parameter in Subprocess / Command Execution",
        "cwe": "CWE-78",
        "quality_types": {"missing_validation", "poor_error_handling"},
        "shared_cause": "External input concatenated directly into shell execution command",
    },
    {
        "name": "Exception Swallowing Masking Security or Integrity Failure",
        "cwe": "CWE-200",
        "quality_types": {"bare_except", "error_handling", "silent_failure"},
        "shared_cause": "Generic exception handler swallows critical errors, obscuring security or state corruption",
    },
]


# ── Pydantic Schemas for Semantic Correlation ─────────────────────────────────

class RawSemanticRelation(BaseModel):
    """Semantic relationship output from LLM."""

    finding_id_1: str = Field(description="First finding ID")
    finding_id_2: str = Field(description="Second finding ID")
    relationship_type: str = Field(
        description="exact_duplicate | overlapping | shared_root_cause | related | independent"
    )
    shared_root_cause: Optional[str] = Field(default=None, description="Identified root cause")
    rationale: str = Field(description="Justification based strictly on code evidence")
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)


class SemanticCorrelationOutput(BaseModel):
    """Container for semantic correlation results."""

    relationships: List[RawSemanticRelation] = Field(default_factory=list)


# ── Internal Correlation Data Structures ──────────────────────────────────────

@dataclass
class RelationshipData:
    """Relationship between a CorrelatedFinding and an original source Finding."""

    source_finding_id: str
    relationship_type: str  # exact_duplicate | overlapping | shared_root_cause | related | independent
    confidence: float = 0.85
    rationale: Optional[str] = None


@dataclass
class CorrelatedCluster:
    """Unified clustered finding with primary finding and constituent links."""

    cluster_id: str
    primary_finding: Dict[str, Any]
    category: str
    severity: str
    title: str
    description: str
    root_cause: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    confidence: float = 0.85
    evidence: Optional[str] = None
    cwe: Optional[str] = None
    correlation_score: float = 1.0
    correlation_explanation: str = ""
    relationships: List[RelationshipData] = field(default_factory=list)
    detection_sources: List[str] = field(default_factory=list)
    relationship_types: List[str] = field(default_factory=list)


# ── Finding Correlator Engine ─────────────────────────────────────────────────

class FindingCorrelator:
    """
    Dedicated Finding Correlator & Cross-Agent Finding Intelligence Engine.

    Responsibilities:
    - Receives validated findings from Gate 2, Gate 3, Gate 1, and static scanners.
    - Classifies pairs as: exact_duplicate, overlapping, shared_root_cause, related, or independent.
    - Prioritizes severity without destructive merging or loss of original evidence.
    - Persists CorrelatedFinding and FindingRelationship records while preserving raw Finding rows.
    """

    def __init__(self, provider: Optional[LLMProvider] = None) -> None:
        self.provider = provider or get_llm_provider()

    # ── Deterministic Match Helpers ───────────────────────────────────────────

    def _normalize_text(self, s: Optional[str]) -> str:
        if not s:
            return ""
        return re.sub(r"\s+", " ", s).strip().lower()

    def _is_exact_duplicate(self, f1: Dict[str, Any], f2: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Check if two findings represent the exact same underlying issue.
        Never merges different files or distant lines.
        """
        p1 = f1.get("file_path") or ""
        p2 = f2.get("file_path") or ""
        if p1 != p2 or not p1:
            return False, None

        s1 = f1.get("start_line") or f1.get("line_number")
        s2 = f2.get("start_line") or f2.get("line_number")
        e1 = f1.get("end_line") or s1
        e2 = f2.get("end_line") or s2

        if s1 is None or s2 is None:
            return False, None

        # Line ranges must overlap or be within 2 lines
        overlap = max(s1, s2) <= min(e1, e2) + 2
        if not overlap:
            return False, None

        ev1 = self._normalize_text(f1.get("evidence"))
        ev2 = self._normalize_text(f2.get("evidence"))

        # Exact or normalized evidence snippet match
        if ev1 and ev2 and (ev1 == ev2 or ev1 in ev2 or ev2 in ev1):
            return True, f"Identical code evidence in '{p1}' at lines {s1}-{e1}."

        # Identical CWE identifier
        cwe1 = f1.get("cwe")
        cwe2 = f2.get("cwe")
        if cwe1 and cwe2 and cwe1 == cwe2:
            return True, f"Matching vulnerability standard {cwe1} on identical lines {s1}-{e1}."

        # Same security type on same line (e.g. static scanner candidate + LLM verified security finding)
        t1 = f1.get("type")
        t2 = f2.get("type")
        if t1 and t2 and t1 == t2 and f1.get("category") == "security" and f2.get("category") == "security":
            return True, f"Static scanner and security agent confirmed identical defect type '{t1}'."

        # High title similarity on identical lines
        title_sim = difflib.SequenceMatcher(
            None, self._normalize_text(f1.get("title")), self._normalize_text(f2.get("title"))
        ).ratio()
        if title_sim >= 0.85:
            return True, f"High title similarity ({title_sim:.2f}) on identical code lines {s1}-{e1}."

        return False, None

    def _is_overlapping(self, f1: Dict[str, Any], f2: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Check if two findings overlap in location but address different concerns.
        Example: Security Agent reports SQLi, Quality Agent reports missing input validation.
        """
        p1 = f1.get("file_path") or ""
        p2 = f2.get("file_path") or ""
        if p1 != p2 or not p1:
            return False, None

        s1 = f1.get("start_line") or f1.get("line_number")
        s2 = f2.get("start_line") or f2.get("line_number")
        e1 = f1.get("end_line") or s1
        e2 = f2.get("end_line") or s2

        if s1 is None or s2 is None:
            return False, None

        # Check for line proximity within 6 lines or overlapping span
        in_proximity = max(s1, s2) <= min(e1, e2) + 6
        if not in_proximity:
            return False, None

        # If categories differ (e.g. security vs quality/maintainability), it's overlapping
        cat1 = f1.get("category")
        cat2 = f2.get("category")
        if cat1 != cat2:
            return True, f"Overlapping location ({p1}:{s1}-{e1}): security and quality agents report distinct concerns."

        # Different CWE or different issue types in the same block
        cwe1 = f1.get("cwe")
        cwe2 = f2.get("cwe")
        if cwe1 and cwe2 and cwe1 != cwe2:
            return True, f"Overlapping location with distinct vulnerability classes: {cwe1} and {cwe2}."

        return False, None

    def _is_shared_root_cause(self, f1: Dict[str, Any], f2: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Check if two findings originate from a common implementation weakness.
        Returns (is_match, shared_root_cause_description, rationale).
        """
        p1 = f1.get("file_path") or ""
        p2 = f2.get("file_path") or ""

        # Same file proximity check or cross-file insecure helper usage
        s1 = f1.get("start_line") or 0
        s2 = f2.get("start_line") or 0

        cwe1 = f1.get("cwe") or ""
        cwe2 = f2.get("cwe") or ""
        type1 = (f1.get("type") or "").lower()
        type2 = (f2.get("type") or "").lower()

        # Check known signatures
        for sig in ROOT_CAUSE_SIGNATURES:
            sig_cwe = sig["cwe"]
            sig_types = sig["quality_types"]

            # Scenario: f1 has CWE, f2 has related quality type in same file
            if p1 == p2 and abs(s1 - s2) <= 15:
                if (cwe1 == sig_cwe and any(t in type2 for t in sig_types)) or (
                    cwe2 == sig_cwe and any(t in type1 for t in sig_types)
                ):
                    return (
                        True,
                        sig["name"],
                        f"Root-cause linkage: {sig['shared_cause']} at '{p1}' lines {s1} & {s2}.",
                    )

        # Cross-file shared helper: check if evidence references the exact same vulnerable function call
        ev1 = f1.get("evidence") or ""
        ev2 = f2.get("evidence") or ""
        if ev1 and ev2 and len(ev1) >= 15:
            # Extract function call token if both call the same function e.g. "format_query(" or "read_user_file("
            m1 = re.search(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", ev1)
            m2 = re.search(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", ev2)
            if m1 and m2 and m1.group(1) == m2.group(1) and m1.group(1) not in {"open", "str", "print", "len", "get"}:
                shared_fn = m1.group(1)
                return (
                    True,
                    f"Shared Insecure Helper: '{shared_fn}' called across multiple sites",
                    f"Findings in '{p1}' and '{p2}' invoke the same unvalidated helper function '{shared_fn}()'.",
                )

        return False, None, None

    # ── Severity Prioritization Policy ────────────────────────────────────────

    def _prioritize_cluster_severity(
        self,
        primary: Dict[str, Any],
        related_findings: List[Dict[str, Any]],
    ) -> Tuple[str, str]:
        """
        Deterministic severity prioritization policy.
        Rules:
        1. Severity and confidence are separate.
        2. High-confidence low-severity findings are never escalated to critical.
        3. Security findings are never downgraded solely because a quality finding has lower severity.
        4. Do not average severity values.
        5. Priority ordering: critical > high > medium > low > info.
        6. Explain consolidated priority adjustment.
        """
        all_findings = [primary] + related_findings
        best_score = 0
        best_sev = primary.get("severity", "medium").lower()
        has_security = False

        for f in all_findings:
            sev = (f.get("severity") or "medium").lower()
            score = SEVERITY_SCORES.get(sev, 2)
            if f.get("category") == "security":
                has_security = True
                # Security findings retain priority
                if score > best_score:
                    best_score = score
                    best_sev = sev
            else:
                if not has_security and score > best_score:
                    best_score = score
                    best_sev = sev

        # If primary wasn't highest, explain the prioritization
        orig_sev = (primary.get("severity") or "medium").lower()
        if best_sev != orig_sev:
            explanation = (
                f"Cluster severity set to '{best_sev}' to reflect maximum validated risk among constituent findings "
                f"(primary originally '{orig_sev}')."
            )
        else:
            explanation = f"Cluster severity maintained at '{best_sev}' from primary finding."

        return best_sev, explanation

    def _select_primary_finding(self, members: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Select the primary finding deterministically among members.
        Order of precedence:
        1. Security Agent / verified finding with exploitability explanation
        2. Quality Agent AST finding
        3. Static rule finding
        4. Highest severity
        5. Highest confidence
        6. Most detailed description
        """
        def ranking_key(f: Dict[str, Any]) -> Tuple[int, int, float, int]:
            source = (f.get("source") or "").lower()
            # Source score
            if "security_agent" in source:
                src_score = 4
            elif "code_quality" in source:
                src_score = 3
            elif "security_static" in source:
                src_score = 2
            else:
                src_score = 1

            # Severity score
            sev_score = SEVERITY_SCORES.get((f.get("severity") or "medium").lower(), 2)
            conf = float(f.get("confidence") or 0.8)
            desc_len = len(f.get("description") or "")

            return (src_score, sev_score, conf, desc_len)

        return max(members, key=ranking_key)

    # ── Semantic Correlation (Ollama) ─────────────────────────────────────────

    async def _evaluate_semantic_relationships(
        self,
        unlinked_candidates: List[Tuple[Dict[str, Any], Dict[str, Any]]],
        repository_intelligence: Optional[Dict[str, Any]] = None,
    ) -> List[RawSemanticRelation]:
        """
        Perform semantic correlation with Ollama when deterministic rules cannot resolve relationships.
        Gracefully returns empty list if Ollama is unavailable.
        """
        if not unlinked_candidates:
            return []

        # Build prompt
        prompt_lines = [
            "<correlation_task>",
            "Analyze the following candidate pairs of code review findings and determine whether and how they are related.",
            "If evidence is insufficient to establish a shared root cause or overlapping concern, classify as 'independent'.",
            "</correlation_task>",
        ]

        if repository_intelligence:
            summary = repository_intelligence.get("architecture_summary", "")
            fws = repository_intelligence.get("frameworks", [])
            prompt_lines.append(f"<repository_context>\nArchitecture: {summary}\nFrameworks: {fws}\n</repository_context>")

        prompt_lines.append("<candidate_finding_pairs>")
        for i, (f1, f2) in enumerate(unlinked_candidates[:5], start=1):
            prompt_lines.append(
                f"Pair #{i}:\n"
                f"  Finding 1: [{f1.get('id', 'f1')}] '{f1.get('title')}' in '{f1.get('file_path')}' lines {f1.get('start_line')}-{f1.get('end_line')}\n"
                f"    Category: {f1.get('category')} | Severity: {f1.get('severity')}\n"
                f"    Evidence: {f1.get('evidence', '')[:120]}\n"
                f"  Finding 2: [{f2.get('id', 'f2')}] '{f2.get('title')}' in '{f2.get('file_path')}' lines {f2.get('start_line')}-{f2.get('end_line')}\n"
                f"    Category: {f2.get('category')} | Severity: {f2.get('severity')}\n"
                f"    Evidence: {f2.get('evidence', '')[:120]}\n"
            )
        prompt_lines.append("</candidate_finding_pairs>")

        prompt_str = "\n".join(prompt_lines)

        try:
            output: SemanticCorrelationOutput = await self.provider.structured_output(
                prompt=prompt_str,
                schema_class=SemanticCorrelationOutput,
                system=FINDING_CORRELATION_SYSTEM_PROMPT,
            )
            return output.relationships
        except Exception as exc:
            logger.warning(
                f"Ollama semantic correlation call failed, falling back to deterministic matching: {exc}"
            )
            return []

    # ── Main Correlation Orchestration ────────────────────────────────────────

    async def correlate_findings(
        self,
        findings: List[Dict[str, Any]],
        repository_intelligence: Optional[Dict[str, Any]] = None,
        use_semantic_fallback: bool = True,
    ) -> Tuple[List[CorrelatedCluster], Dict[str, Any]]:
        """
        Correlate a list of validated findings into unified clusters.

        Returns:
            Tuple of (correlated_clusters, correlation_metadata).
        """
        if not findings:
            return [], {
                "status": "completed",
                "total_input_findings": 0,
                "correlated_clusters_count": 0,
                "exact_duplicates_count": 0,
                "overlapping_count": 0,
                "shared_root_cause_count": 0,
                "independent_count": 0,
                "semantic_evaluated": False,
            }

        # Step 1: Assign stable synthetic IDs if missing
        processed_findings: List[Dict[str, Any]] = []
        for i, f in enumerate(findings):
            fd = dict(f)
            if not fd.get("id"):
                fd["id"] = f"finding-{i+1}-{uuid.uuid4().hex[:8]}"
            processed_findings.append(fd)

        # Step 2: Deterministic Correlation Pass
        # clusters: List[List[Dict[str, Any]]] with matching relationships
        # Each cluster has: list of member finding dicts, and list of RelationshipData
        clusters_members: List[List[Dict[str, Any]]] = []
        clusters_relationships: List[List[RelationshipData]] = []

        unlinked_candidates: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []

        for candidate in processed_findings:
            matched_cluster_idx: Optional[int] = None
            detected_rel: Optional[RelationshipData] = None

            for c_idx, members in enumerate(clusters_members):
                # Check against primary or any member
                for member in members:
                    # Check A: Exact Duplicate
                    is_dup, dup_reason = self._is_exact_duplicate(member, candidate)
                    if is_dup:
                        matched_cluster_idx = c_idx
                        detected_rel = RelationshipData(
                            source_finding_id=candidate["id"],
                            relationship_type="exact_duplicate",
                            confidence=0.95,
                            rationale=dup_reason,
                        )
                        break

                    # Check B: Shared Root Cause (checked BEFORE generic overlapping)
                    is_rc, rc_name, rc_reason = self._is_shared_root_cause(member, candidate)
                    if is_rc:
                        matched_cluster_idx = c_idx
                        detected_rel = RelationshipData(
                            source_finding_id=candidate["id"],
                            relationship_type="shared_root_cause",
                            confidence=0.90,
                            rationale=f"{rc_name}: {rc_reason}" if rc_name else rc_reason,
                        )
                        break

                    # Check C: Overlapping Finding
                    is_ovl, ovl_reason = self._is_overlapping(member, candidate)
                    if is_ovl:
                        matched_cluster_idx = c_idx
                        detected_rel = RelationshipData(
                            source_finding_id=candidate["id"],
                            relationship_type="overlapping",
                            confidence=0.88,
                            rationale=ovl_reason,
                        )
                        break

                if matched_cluster_idx is not None:
                    break

            if matched_cluster_idx is not None and detected_rel is not None:
                clusters_members[matched_cluster_idx].append(candidate)
                clusters_relationships[matched_cluster_idx].append(detected_rel)
            else:
                # Potential candidate for semantic matching if in adjacent code blocks or sharing identifiers
                cand_s = candidate.get("start_line") or candidate.get("line_number") or 0
                for members in clusters_members:
                    for m in members:
                        if m.get("file_path") == candidate.get("file_path") and m.get("file_path"):
                            m_s = m.get("start_line") or m.get("line_number") or 0
                            line_dist = abs(cand_s - m_s) if (cand_s and m_s) else 999
                            m_tokens = set(re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]{3,}\b", (m.get("evidence") or "") + " " + (m.get("description") or "")))
                            c_tokens = set(re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]{3,}\b", (candidate.get("evidence") or "") + " " + (candidate.get("description") or "")))
                            common = m_tokens.intersection(c_tokens) - {"def", "class", "return", "self", "none", "true", "false", "data", "file", "line"}
                            if line_dist <= 25 or len(common) >= 2:
                                unlinked_candidates.append((m, candidate))
                                break

                # Start a new cluster with candidate as its initial finding
                clusters_members.append([candidate])
                clusters_relationships.append([
                    RelationshipData(
                        source_finding_id=candidate["id"],
                        relationship_type="independent",
                        confidence=1.0,
                        rationale="Independent finding with distinct location or cause.",
                    )
                ])

        # Step 3: Semantic Correlation Pass (when inconclusive pairs exist and enabled)
        semantic_evaluated = False
        if use_semantic_fallback and unlinked_candidates:
            semantic_evaluated = True
            semantic_rels = await self._evaluate_semantic_relationships(
                unlinked_candidates, repository_intelligence
            )

            for s_rel in semantic_rels:
                if s_rel.confidence >= 0.70 and s_rel.relationship_type in ("shared_root_cause", "overlapping", "related"):
                    # Find clusters containing finding_id_1 and finding_id_2
                    c1_idx = None
                    c2_idx = None
                    for idx, members in enumerate(clusters_members):
                        ids = {m["id"] for m in members}
                        if s_rel.finding_id_1 in ids:
                            c1_idx = idx
                        if s_rel.finding_id_2 in ids:
                            c2_idx = idx

                    # If in different clusters, merge c2 into c1
                    if c1_idx is not None and c2_idx is not None and c1_idx != c2_idx:
                        c2_members = clusters_members.pop(c2_idx)
                        c2_rels = clusters_relationships.pop(c2_idx)

                        clusters_members[c1_idx].extend(c2_members)
                        clusters_relationships[c1_idx].extend(c2_rels)
                        clusters_relationships[c1_idx].append(
                            RelationshipData(
                                source_finding_id=s_rel.finding_id_2,
                                relationship_type=s_rel.relationship_type,
                                confidence=s_rel.confidence,
                                rationale=s_rel.rationale or f"Semantic correlation identified {s_rel.relationship_type}.",
                            )
                        )

        # Step 4: Build CorrelatedCluster Output Objects
        correlated_clusters: List[CorrelatedCluster] = []
        dup_count = 0
        ovl_count = 0
        rc_count = 0
        ind_count = 0

        for members, relationships in zip(clusters_members, clusters_relationships):
            primary = self._select_primary_finding(members)
            related_findings = [m for m in members if m["id"] != primary["id"]]

            # Determine prioritized severity and explanation
            prioritized_sev, sev_explanation = self._prioritize_cluster_severity(primary, related_findings)

            # Consolidated root cause
            root_cause = None
            rc_rels = [r for r in relationships if r.relationship_type == "shared_root_cause"]
            if rc_rels and rc_rels[0].rationale:
                root_cause = rc_rels[0].rationale

            # Track relationship counts
            for r in relationships:
                if r.relationship_type == "exact_duplicate":
                    dup_count += 1
                elif r.relationship_type == "overlapping":
                    ovl_count += 1
                elif r.relationship_type == "shared_root_cause":
                    rc_count += 1
                elif r.relationship_type == "independent":
                    ind_count += 1

            sources = sorted(list({m.get("source") or "code_review_agent" for m in members}))
            rel_types = sorted(list({r.relationship_type for r in relationships}))

            # Consolidated description
            if len(members) > 1:
                desc_parts = [primary.get("description", "")]
                desc_parts.append(f"\n[Cross-Agent Correlation: {len(members)} findings unified across {', '.join(sources)}]")
                for rf in related_findings:
                    desc_parts.append(f"- {rf.get('source', 'agent')}: {rf.get('title')}")
                full_desc = "\n".join(desc_parts)
            else:
                full_desc = primary.get("description", "")

            # Consolidated explanation
            explanation_parts = [sev_explanation]
            if len(members) > 1:
                explanation_parts.append(
                    f"Correlated {len(members)} findings ({', '.join(rel_types)}) across sources {', '.join(sources)}."
                )

            # Weighted confidence
            conf_avg = round(sum(float(m.get("confidence") or 0.8) for m in members) / len(members), 2)

            cluster = CorrelatedCluster(
                cluster_id=str(uuid.uuid4()),
                primary_finding=primary,
                category=primary.get("category", "quality") if primary.get("category") == "security" else (
                    "security" if any(m.get("category") == "security" for m in members) else primary.get("category", "quality")
                ),
                severity=prioritized_sev,
                title=primary.get("title", "Correlated Finding"),
                description=full_desc,
                root_cause=root_cause,
                file_path=primary.get("file_path"),
                line_number=primary.get("line_number") or primary.get("start_line"),
                start_line=primary.get("start_line"),
                end_line=primary.get("end_line"),
                confidence=conf_avg,
                evidence=primary.get("evidence"),
                cwe=primary.get("cwe") or next((m.get("cwe") for m in members if m.get("cwe")), None),
                correlation_score=conf_avg,
                correlation_explanation=" ".join(explanation_parts),
                relationships=relationships,
                detection_sources=sources,
                relationship_types=rel_types,
            )
            correlated_clusters.append(cluster)

        metadata = {
            "status": "completed",
            "total_input_findings": len(findings),
            "correlated_clusters_count": len(correlated_clusters),
            "exact_duplicates_count": dup_count,
            "overlapping_count": ovl_count,
            "shared_root_cause_count": rc_count,
            "independent_count": ind_count,
            "semantic_evaluated": semantic_evaluated,
        }

        return correlated_clusters, metadata

    # ── Idempotent Persistence ────────────────────────────────────────────────

    async def persist_correlation_results(
        self,
        db: AsyncSession,
        review_id: str,
        clusters: List[CorrelatedCluster],
        snapshot_id: Optional[str] = None,
    ) -> List[CorrelatedFinding]:
        """
        Persist correlated clusters and relationships to the database idempotently.
        Leaves original Finding records untouched and preserves prior correlation runs
        with version tracking.
        """
        # Determine correlation version non-destructively
        version_stmt = (
            select(CorrelatedFinding.correlation_version)
            .where(CorrelatedFinding.review_id == review_id)
            .order_by(CorrelatedFinding.correlation_version.desc())
        )
        version_res = await db.execute(version_stmt)
        existing_versions = [v for (v,) in version_res.fetchall() if v]

        if existing_versions:
            numeric_versions = []
            for v in existing_versions:
                try:
                    numeric_versions.append(float(v))
                except ValueError:
                    pass
            next_ver = max(numeric_versions) + 1.0 if numeric_versions else 1.0
            correlation_version = f"{next_ver:.1f}"
        else:
            correlation_version = "1.0"

        persisted_models: List[CorrelatedFinding] = []

        for c in clusters:
            primary_id = c.primary_finding.get("id")
            if not primary_id:
                continue

            # Ensure ID is unique across versions to prevent duplicate key collision on retry
            cluster_id = c.cluster_id
            if correlation_version != "1.0":
                cluster_id = f"{c.cluster_id}-v{correlation_version}"

            cf_model = CorrelatedFinding(
                id=cluster_id,
                review_id=review_id,
                snapshot_id=snapshot_id,
                primary_finding_id=primary_id,
                category=c.category,
                severity=c.severity,
                title=c.title,
                description=c.description,
                root_cause=c.root_cause,
                file_path=c.file_path,
                line_number=c.line_number,
                start_line=c.start_line,
                end_line=c.end_line,
                confidence=c.confidence,
                evidence=c.evidence,
                cwe=c.cwe,
                correlation_score=c.correlation_score,
                correlation_explanation=c.correlation_explanation,
                correlation_version=correlation_version,
                status="open",
            )
            db.add(cf_model)

            for rel in c.relationships:
                rel_model = FindingRelationship(
                    id=str(uuid.uuid4()),
                    correlated_finding_id=cluster_id,
                    source_finding_id=rel.source_finding_id,
                    relationship_type=rel.relationship_type,
                    confidence=rel.confidence,
                    rationale=rel.rationale,
                )
                db.add(rel_model)

            persisted_models.append(cf_model)

        await db.commit()
        return persisted_models
