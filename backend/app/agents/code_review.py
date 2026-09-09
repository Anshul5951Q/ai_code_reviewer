"""
Code Review Agent.

Analyzes source code quality, maintainability, code smells, complexity,
and error handling. Emits structured findings anchored to source line ranges.
"""
from __future__ import annotations

import logging
import time
from typing import List, Optional

from pydantic import BaseModel, Field

from app.agents.base import AgentFinding, AgentResult, AnalysisContext, BaseAnalysisAgent
from app.llm.client import get_llm_provider
from app.llm.prompts import CODE_REVIEW_SYSTEM_PROMPT
from app.llm.provider import LLMProvider

logger = logging.getLogger("ai_code_reviewer.agents.code_review")


class RawCodeReviewFinding(BaseModel):
    """Raw finding schema returned by the LLM."""

    category: str = Field(default="quality", description="quality | maintainability | performance | architecture")
    type: str = Field(default="code_smell", description="code_smell | complexity | dead_code | error_handling | naming")
    severity: str = Field(default="medium", description="critical | high | medium | low | info")
    title: str = Field(description="Concise description of the finding")
    description: str = Field(description="Detailed explanation and engineering impact")
    file_path: Optional[str] = Field(default=None, description="Exact relative file path")
    start_line: Optional[int] = Field(default=None, description="Starting line number (1-indexed)")
    end_line: Optional[int] = Field(default=None, description="Ending line number (1-indexed)")
    confidence: float = Field(default=0.85, description="Confidence between 0.0 and 1.0")
    evidence: Optional[str] = Field(default=None, description="Relevant code snippet")


class CodeReviewOutput(BaseModel):
    """Container for code review findings."""

    findings: List[RawCodeReviewFinding] = Field(default_factory=list)


class CodeReviewAgent(BaseAnalysisAgent):
    """Analyzes code quality, complexity, and maintainability."""

    name = "Code Review Agent"
    agent_type = "code_review"
    description = "Detects code smells, maintainability issues, excessive complexity, and engineering defects."

    def __init__(self, provider: Optional[LLMProvider] = None) -> None:
        self.provider = provider or get_llm_provider()

    async def analyze(self, context: AnalysisContext) -> AgentResult:
        start_time = time.perf_counter()

        if not context.chunks:
            return AgentResult(
                agent_type=self.agent_type,
                status="completed",
                duration_ms=0,
                files_analyzed=0,
                findings=[],
            )

        # Build prompt from code chunks
        prompt_parts = [
            f"Reviewing repository: {context.repository_name}",
            f"Examining {len(context.chunks)} source code chunks across {len(context.selected_files)} files.",
            "",
            "SOURCE CODE CHUNKS TO REVIEW:",
        ]

        for chunk in context.chunks[:25]:
            prompt_parts.append(
                f"\n=== File: {chunk.file_path} (Lines {chunk.start_line}-{chunk.end_line}) ===\n"
                f"{chunk.content}"
            )

        prompt_str = "\n".join(prompt_parts)

        try:
            output: CodeReviewOutput = await self.provider.structured_output(
                prompt=prompt_str,
                schema_class=CodeReviewOutput,
                system=CODE_REVIEW_SYSTEM_PROMPT,
            )
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            findings: List[AgentFinding] = []
            for rf in output.findings:
                findings.append(
                    AgentFinding(
                        category=rf.category,
                        type=rf.type,
                        severity=rf.severity,
                        title=rf.title,
                        description=rf.description,
                        file_path=rf.file_path,
                        start_line=rf.start_line,
                        end_line=rf.end_line,
                        confidence=rf.confidence,
                        evidence=rf.evidence,
                        source="code_review_agent",
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
            logger.error(f"CodeReviewAgent failed: {exc}", exc_info=True)
            return AgentResult(
                agent_type=self.agent_type,
                status="failed",
                duration_ms=duration_ms,
                files_analyzed=len(context.selected_files),
                findings=[],
                error=f"Code review analysis failed: {str(exc)}",
            )
