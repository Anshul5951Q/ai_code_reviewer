"""
Independent Verification Agent.

Audits proposed patches against original findings, static rule re-analysis,
and regression checks to determine whether defects are truly resolved.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.llm.client import get_llm_provider
from app.llm.prompts import VERIFICATION_PROMPT_VERSION, VERIFICATION_SYSTEM_PROMPT
from app.llm.provider import LLMProvider
from app.schemas.remediation import VerificationResult

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
        static_analysis_signals: List[Dict[str, Any]],
        syntax_valid: bool = True,
        syntax_error: Optional[str] = None,
    ) -> VerificationResult:
        """
        Independently evaluate the modified code and static analysis signals.
        """
        # If patch failed syntax/compilation check, fail immediately deterministically
        if not syntax_valid:
            logger.warning(f"Verification: syntax check failed for {file_path}: {syntax_error}")
            return VerificationResult(
                status="verification_failed",
                confidence=0.98,
                reason=f"The proposed patch introduces a syntax error: {syntax_error or 'Code failed to parse.'}",
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

        prompt = self._build_prompt(
            finding=finding,
            file_path=file_path,
            original_code=original_code,
            modified_code=modified_code,
            unified_diff=unified_diff,
            static_signals=static_analysis_signals,
        )

        logger.info(
            f"VerificationAgent evaluating fix for finding {finding.id[:8]} "
            f"({finding.category}/{finding.cwe or finding.type})"
        )

        result = await self.llm_provider.structured_output(
            prompt=prompt,
            schema_class=VerificationResult,
            system=VERIFICATION_SYSTEM_PROMPT,
        )

        return result

    def _build_prompt(
        self,
        finding: Any,
        file_path: str,
        original_code: str,
        modified_code: str,
        unified_diff: str,
        static_signals: List[Dict[str, Any]],
    ) -> str:
        prompt_parts = [
            "AUDIT TARGET FINDING:",
            f"- Title: {finding.title}",
            f"- Category: {finding.category}",
            f"- Type: {getattr(finding, 'type', None) or 'unspecified'}",
            f"- Severity: {finding.severity}",
            f"- CWE: {getattr(finding, 'cwe', None) or 'N/A'}",
            f"- File: {file_path}",
            f"- Description: {finding.description or 'None'}",
        ]

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
            prompt_parts.append(f"\nSTATIC ANALYSIS RE-SCAN ON MODIFIED CODE:")
            prompt_parts.append(f"WARNING: Static analyzer flagged {len(matching_signals)} signal(s) in the modified code:")
            for s in matching_signals:
                prompt_parts.append(f"  - [{s.get('cwe')}] {s.get('title')}: {s.get('evidence')}")
        else:
            prompt_parts.append("\nSTATIC ANALYSIS RE-SCAN ON MODIFIED CODE:")
            prompt_parts.append("✓ Static analyzer detected 0 vulnerability patterns in the modified file.")

        prompt_parts.append("\nVERIFICATION QUESTIONS TO ANSWER:")
        prompt_parts.append("1. Is the original defect completely eradicated from the code?")
        prompt_parts.append("2. Does the patch address the actual root cause rather than merely disguising it?")
        prompt_parts.append("3. Did the patch introduce any new vulnerability, unhandled exception, or regression?")
        prompt_parts.append("4. What is the precise verification status: resolved, partially_resolved, still_vulnerable, or verification_failed?")

        return "\n".join(prompt_parts)
