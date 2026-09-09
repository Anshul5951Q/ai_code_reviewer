"""
Code Understanding Agent.

Analyzes architecture, frameworks, entry points, key modules, and structural patterns
from the repository snapshot and entry point source chunks.
Outputs strict validated JSON.
"""
from __future__ import annotations

import json
import logging
import time
from typing import List, Optional

from pydantic import BaseModel, Field

from app.agents.base import AgentFinding, AgentResult, AnalysisContext, BaseAnalysisAgent
from app.llm.client import get_llm_provider
from app.llm.prompts import CODE_UNDERSTANDING_SYSTEM_PROMPT
from app.llm.provider import LLMProvider

logger = logging.getLogger("ai_code_reviewer.agents.understanding")


class CodeUnderstandingOutput(BaseModel):
    """Validated structured schema for Code Understanding output."""

    architecture_summary: str = Field(
        description="High-level architecture and design summary"
    )
    frameworks: List[str] = Field(
        default_factory=list, description="Verified frameworks and runtime technologies"
    )
    important_modules: List[str] = Field(
        default_factory=list, description="Key packages, directories, and architectural layers"
    )
    entry_points: List[str] = Field(
        default_factory=list, description="Primary application entry points"
    )
    architecture_risks: List[str] = Field(
        default_factory=list, description="Identified structural or design risks"
    )
    observations: List[str] = Field(
        default_factory=list, description="Notable engineering patterns or structure observations"
    )


class CodeUnderstandingAgent(BaseAnalysisAgent):
    """Analyzes architecture, modules, and entry points."""

    name = "Code Understanding Agent"
    agent_type = "code_understanding"
    description = "Synthesizes architecture, module boundaries, entry points, and dependencies."

    def __init__(self, provider: Optional[LLMProvider] = None) -> None:
        self.provider = provider or get_llm_provider()

    async def analyze(self, context: AnalysisContext) -> AgentResult:
        start_time = time.perf_counter()

        # Build prompt from bounded context
        prompt_parts = [
            f"Repository: {context.repository_name} (Commit: {context.commit_sha[:7]}, Branch: {context.branch})",
            f"Total Files: {context.statistics.get('total_files', 0)}, Estimated LOC: {context.statistics.get('total_lines', 0)}",
            "",
            "Detected Languages:",
            json.dumps(context.languages, indent=2),
            "",
            "Detected Frameworks (Deterministic):",
            ", ".join(context.frameworks) if context.frameworks else "None detected",
            "",
            "Declared Dependencies (Sample):",
            json.dumps(context.dependencies[:20], indent=2),
            "",
            "Entry Points & Structure:",
            json.dumps(context.structure.get("entry_points", []), indent=2),
            "",
            "Selected Architectural File Excerpts:",
        ]

        for chunk in context.chunks[:10]:
            prompt_parts.append(
                f"--- File: {chunk.file_path} (Lines {chunk.start_line}-{chunk.end_line}) ---\n{chunk.content}\n"
            )

        prompt_str = "\n".join(prompt_parts)

        try:
            output: CodeUnderstandingOutput = await self.provider.structured_output(
                prompt=prompt_str,
                schema_class=CodeUnderstandingOutput,
                system=CODE_UNDERSTANDING_SYSTEM_PROMPT,
            )
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # Convert architecture risks into architectural findings if severe
            findings: List[AgentFinding] = []
            for risk in output.architecture_risks:
                findings.append(
                    AgentFinding(
                        category="architecture",
                        severity="low",
                        title=f"Architectural Observation: {risk[:60]}",
                        description=risk,
                        confidence=0.75,
                        source="code_understanding",
                    )
                )

            return AgentResult(
                agent_type=self.agent_type,
                status="completed",
                duration_ms=duration_ms,
                files_analyzed=len(context.selected_files),
                findings=findings,
                data=output.model_dump(),
            )
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"CodeUnderstandingAgent failed: {exc}", exc_info=True)
            return AgentResult(
                agent_type=self.agent_type,
                status="failed",
                duration_ms=duration_ms,
                files_analyzed=len(context.selected_files),
                findings=[],
                error=f"Understanding analysis failed: {str(exc)}",
            )
