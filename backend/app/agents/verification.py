"""
Independent Verification Agent.

Audits proposed patches against original findings, static rule re-analysis,
and regression checks to determine whether defects are truly resolved.

Axioms:
- Zero Blind Trust: Never trust the RemediationAgent's success claims, explanation, or confidence score.
- Source -> Transformation -> Sink reasoning for security vulnerabilities.
- Independent verification without confirmation bias (RemediationAgent rationale is withheld).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.llm.client import get_llm_provider
from app.llm.prompts import VERIFICATION_PROMPT_VERSION, VERIFICATION_SYSTEM_PROMPT
from app.llm.provider import LLMProvider
from app.schemas.verification import (
    SourceTransformationSinkAssessment,
    VerificationAgentReport,
    VerificationOutcome,
)

logger = logging.getLogger("ai_code_reviewer.verification_agent")


class VerificationAgent:
    """
    Skeptical evaluator ensuring patches completely resolve root causes
    without introducing regressions or secondary vulnerabilities.
    """

    name: str = "Verification Agent"
    agent_type: str = "verification_agent"
    prompt_version: str = VERIFICATION_PROMPT_VERSION

    def __init__(self, llm_provider: Optional[LLMProvider] = None) -> None:
        self.llm_provider = llm_provider or get_llm_provider()

    async def verify(
        self,
        finding: Any,
        file_path: str,
        original_code: str,
        modified_code: str,
        unified_diff: str,
        static_analysis_signals: Optional[List[Dict[str, Any]]] = None,
        syntax_valid: bool = True,
        syntax_error: Optional[str] = None,
        root_cause: Optional[str] = None,
        related_findings: Optional[List[Dict[str, Any]]] = None,
    ) -> VerificationAgentReport:
        """
        Independently evaluate the modified code and static analysis signals
        using Source -> Transformation -> Sink reasoning without trusting remediation rationale.
        """
        static_signals = static_analysis_signals or []

        # 1. Deterministic syntax failure: If syntax failed, immediately reject
        if not syntax_valid:
            logger.warning(f"Verification: syntax check failed for {file_path}: {syntax_error}")
            return VerificationAgentReport(
                outcome=VerificationOutcome.REGRESSION_DETECTED.value,
                confidence=0.99,
                reason=f"The proposed patch introduces a fatal language syntax error: {syntax_error or 'Code failed to parse.'}",
                source_transformation_sink=SourceTransformationSinkAssessment(
                    is_exploitable_path_severed=False,
                    remaining_attack_surface="Syntax failure causes runtime execution failure.",
                    rationale="Code cannot compile or execute.",
                ),
                remaining_risk="Code will fail at runtime or compilation.",
                new_findings=[{
                    "category": "quality",
                    "type": "syntax_error",
                    "severity": "critical",
                    "title": "Syntax error introduced by patch",
                    "description": syntax_error or "Code syntax is broken",
                    "file_path": file_path,
                }],
                evidence=[syntax_error or "Syntax check failed."],
            )

        # 2. Build prompt with Source -> Transformation -> Sink guidelines
        # Notice: Remediation explanation/strategy is deliberately NOT passed to avoid bias
        prompt = self._build_prompt(
            finding=finding,
            file_path=file_path,
            original_code=original_code,
            modified_code=modified_code,
            unified_diff=unified_diff,
            static_signals=static_signals,
            root_cause=root_cause,
            related_findings=related_findings,
        )

        f_id = getattr(finding, "id", "unknown")[:8]
        f_cat = getattr(finding, "category", "general")
        f_cwe = getattr(finding, "cwe", None) or getattr(finding, "type", "defect")
        logger.info(f"VerificationAgent evaluating fix for finding {f_id} ({f_cat}/{f_cwe})")

        try:
            result = await self.llm_provider.structured_output(
                prompt=prompt,
                schema_class=VerificationAgentReport,
                system=VERIFICATION_SYSTEM_PROMPT,
            )
            # Normalize outcome
            norm_outcome = self._normalize_outcome(result.outcome)
            result.outcome = norm_outcome
            return result
        except Exception as exc:
            logger.warning(f"LLM structured output failed or raised error: {exc}. Attempting fallback parsing.")
            # If Ollama or mock returned legacy schema or failed
            return VerificationAgentReport(
                outcome=VerificationOutcome.UNABLE_TO_VERIFY.value,
                confidence=0.5,
                reason=f"Verification agent encountered provider error: {str(exc)}",
                source_transformation_sink=SourceTransformationSinkAssessment(
                    is_exploitable_path_severed=False,
                    remaining_attack_surface="Unknown",
                    rationale="Provider unavailable to complete semantic audit.",
                ),
                remaining_risk="Uncertainty cannot be treated as resolution.",
                new_findings=[],
                evidence=[],
            )

    @staticmethod
    def _normalize_outcome(val: str) -> str:
        """Map legacy strings to standard VerificationOutcome enum values."""
        clean = (val or "").strip().upper()
        if clean in ("RESOLVED", "FIXED"):
            return VerificationOutcome.FIXED.value
        elif clean in ("PARTIALLY_RESOLVED", "PARTIALLY_FIXED"):
            return VerificationOutcome.PARTIALLY_FIXED.value
        elif clean in ("STILL_VULNERABLE", "NOT_FIXED"):
            return VerificationOutcome.NOT_FIXED.value
        elif clean in ("VERIFICATION_FAILED", "REGRESSION_DETECTED"):
            return VerificationOutcome.REGRESSION_DETECTED.value
        elif clean in ("UNABLE_TO_VERIFY", "UNKNOWN"):
            return VerificationOutcome.UNABLE_TO_VERIFY.value
        return VerificationOutcome.UNABLE_TO_VERIFY.value

    def _build_prompt(
        self,
        finding: Any,
        file_path: str,
        original_code: str,
        modified_code: str,
        unified_diff: str,
        static_signals: List[Dict[str, Any]],
        root_cause: Optional[str] = None,
        related_findings: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        prompt_parts = [
            "AUDIT TARGET FINDING:",
            f"- Title: {getattr(finding, 'title', 'Defect')}",
            f"- Category: {getattr(finding, 'category', 'general')}",
            f"- Type: {getattr(finding, 'type', None) or 'unspecified'}",
            f"- Severity: {getattr(finding, 'severity', 'medium')}",
            f"- CWE: {getattr(finding, 'cwe', None) or 'N/A'}",
            f"- File: {file_path}",
            f"- Description: {getattr(finding, 'description', 'None') or 'None'}",
        ]

        if root_cause:
            prompt_parts.append(f"- Identified Root Cause: {root_cause}")

        if related_findings:
            prompt_parts.append(f"\nRELATED FINDINGS IN SAME CLUSTER ({len(related_findings)}):")
            for rf in related_findings[:4]:
                prompt_parts.append(
                    f"  * [{rf.get('category')}/{rf.get('severity')}] {rf.get('title')} at {rf.get('file_path')}:{rf.get('start_line')}"
                )

        if getattr(finding, "evidence", None):
            prompt_parts.append(f"\nORIGINAL EVIDENCE:\n```\n{finding.evidence}\n```")

        prompt_parts.append(f"\nPROPOSED UNIFIED DIFF:\n```diff\n{unified_diff}\n```")

        prompt_parts.append(f"\nMODIFIED SOURCE (Post-Patch Snippet):\n```\n{modified_code}\n```")

        # Static rule signals on the modified code
        matching_signals = [
            s for s in static_signals
            if s.get("file_path") == file_path
        ]
        if matching_signals:
            prompt_parts.append("\nSTATIC ANALYSIS RE-SCAN ON MODIFIED CODE:")
            prompt_parts.append(f"WARNING: Static analyzer flagged {len(matching_signals)} signal(s) in the modified code:")
            for s in matching_signals:
                prompt_parts.append(f"  - [{s.get('cwe')}] {s.get('title')}: {s.get('evidence')}")
        else:
            prompt_parts.append("\nSTATIC ANALYSIS RE-SCAN ON MODIFIED CODE:")
            prompt_parts.append("✓ Static analyzer detected 0 vulnerability patterns in the modified file.")

        prompt_parts.append("\nSOURCE -> TRANSFORMATION -> SINK AUDIT CHECKLIST:")
        prompt_parts.append("1. Source: Identify where user/external input enters (HTTP params, headers, CLI arguments, files).")
        prompt_parts.append("2. Transformation: Does sanitization, validation, encoding, or parameter binding genuinely sever the attack path?")
        prompt_parts.append("3. Sink: Is the dangerous sink (SQL query, command execution, filesystem write, innerHTML) safely rendered inert?")
        prompt_parts.append("4. Alternate Paths: Does an unescaped or unparameterized secondary execution path remain?")
        prompt_parts.append("5. Regressions: Did the change break function signatures, imports, return contracts, or introduce new defects?")
        prompt_parts.append("\nAllowed outcomes: FIXED, PARTIALLY_FIXED, NOT_FIXED, REGRESSION_DETECTED, UNABLE_TO_VERIFY.")

        return "\n".join(prompt_parts)
