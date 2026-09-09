"""
Security Agent.

Reasons over candidate code and signals identified by deterministic static analysis.
Evaluates exploitability, attack paths, engineering impact, and assigns verified CWEs.
Filters out false positives.
"""
from __future__ import annotations

import json
import logging
import time
from typing import List, Optional

from pydantic import BaseModel, Field

from app.agents.base import AgentFinding, AgentResult, AnalysisContext, BaseAnalysisAgent
from app.llm.client import get_llm_provider
from app.llm.prompts import SECURITY_AGENT_SYSTEM_PROMPT
from app.llm.provider import LLMProvider

logger = logging.getLogger("ai_code_reviewer.agents.security")


class RawSecurityFinding(BaseModel):
    """Raw security finding returned by the LLM."""

    category: str = Field(default="security", description="Always security")
    type: str = Field(
        default="sql_injection",
        description="sql_injection | xss | hardcoded_secret | command_injection | path_traversal | insecure_file_handling | ssrf | weak_cryptography | authentication_issue | authorization_issue",
    )
    severity: str = Field(default="high", description="critical | high | medium | low | info")
    title: str = Field(description="Clear vulnerability title")
    description: str = Field(description="Attack path, impact, and exploitation rationale")
    file_path: Optional[str] = Field(default=None, description="Exact file path")
    start_line: Optional[int] = Field(default=None, description="Start line (1-indexed)")
    end_line: Optional[int] = Field(default=None, description="End line (1-indexed)")
    confidence: float = Field(default=0.90, description="Confidence score 0.0 to 1.0")
    evidence: Optional[str] = Field(default=None, description="Redacted code excerpt")
    cwe: Optional[str] = Field(default=None, description="Standard CWE identifier (e.g. CWE-89)")


class SecurityAgentOutput(BaseModel):
    """Container for validated security findings."""

    findings: List[RawSecurityFinding] = Field(default_factory=list)


class SecurityAgent(BaseAnalysisAgent):
    """Evaluates exploitability and attack paths for suspicious code."""

    name = "Security Agent"
    agent_type = "security_agent"
    description = "Reasons over security signals to verify vulnerabilities, attack vectors, and CWE classifications."

    def __init__(self, provider: Optional[LLMProvider] = None) -> None:
        self.provider = provider or get_llm_provider()

    async def analyze(self, context: AnalysisContext) -> AgentResult:
        start_time = time.perf_counter()

        # Build prompt including static findings signals and relevant source chunks
        prompt_parts = [
            f"Security Analysis for repository: {context.repository_name}",
            f"Static Security Signals Detected: {len(context.static_findings)}",
            "",
            "STATIC SECURITY SIGNALS SUMMARY:",
            json.dumps(context.static_findings[:15], indent=2),
            "",
            "SOURCE CODE CHUNKS FOR SECURITY INSPECTION:",
        ]

        for chunk in context.chunks[:20]:
            prompt_parts.append(
                f"\n=== File: {chunk.file_path} (Lines {chunk.start_line}-{chunk.end_line}) ===\n"
                f"{chunk.content}"
            )

        prompt_str = "\n".join(prompt_parts)

        try:
            output: SecurityAgentOutput = await self.provider.structured_output(
                prompt=prompt_str,
                schema_class=SecurityAgentOutput,
                system=SECURITY_AGENT_SYSTEM_PROMPT,
            )
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            findings: List[AgentFinding] = []
            for sf in output.findings:
                findings.append(
                    AgentFinding(
                        category="security",
                        type=sf.type,
                        severity=sf.severity,
                        title=sf.title,
                        description=sf.description,
                        file_path=sf.file_path,
                        start_line=sf.start_line,
                        end_line=sf.end_line,
                        confidence=sf.confidence,
                        evidence=sf.evidence,
                        cwe=sf.cwe,
                        source="security_agent",
                    )
                )

            return AgentResult(
                agent_type=self.agent_type,
                status="completed",
                duration_ms=duration_ms,
                files_analyzed=len(context.selected_files),
                findings=findings,
            )
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"SecurityAgent failed: {exc}", exc_info=True)
            return AgentResult(
                agent_type=self.agent_type,
                status="failed",
                duration_ms=duration_ms,
                files_analyzed=len(context.selected_files),
                findings=[],
                error=f"Security agent analysis failed: {str(exc)}",
            )
