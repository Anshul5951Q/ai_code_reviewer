"""
Base agent interface and structured context/result definitions.

Every analysis agent conforms to BaseAnalysisAgent.
Agents return structured AgentResult objects rather than directly manipulating the database.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.analysis.chunker import FileChunk


@dataclass
class AgentFinding:
    """A finding emitted by an individual analysis agent."""

    category: str  # security | quality | maintainability | architecture
    title: str
    description: str
    severity: str  # critical | high | medium | low | info
    file_path: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    confidence: float = 0.8
    evidence: Optional[str] = None
    cwe: Optional[str] = None
    type: Optional[str] = None
    source: str = "code_review_agent"

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "cwe": self.cwe,
            "type": self.type,
            "source": self.source,
        }


@dataclass
class AnalysisContext:
    """
    Controlled, bounded context provided to an individual analysis agent.

    Contains only relevant files, chunks, and metadata without leaking
    unrelated files, environment secrets, or credentials.
    """

    review_id: str
    repository_id: str
    repository_name: str
    commit_sha: str
    branch: str
    agent_type: str

    # Deterministic metadata from Phase 3 snapshot
    languages: Dict[str, Any]
    frameworks: List[str]
    dependencies: List[Dict[str, Any]]
    structure: Dict[str, Any]
    statistics: Dict[str, int]
    file_tree: List[str]

    # Selected source files and line-mapped chunks for this agent
    selected_files: Dict[str, str] = field(default_factory=dict)
    chunks: List[FileChunk] = field(default_factory=list)

    # Optional static findings to inform the security agent
    static_findings: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class AgentResult:
    """Structured execution output from an agent run."""

    agent_type: str
    status: str  # completed | failed
    duration_ms: int = 0
    files_analyzed: int = 0
    findings: List[AgentFinding] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "agent_type": self.agent_type,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "files_analyzed": self.files_analyzed,
            "findings_count": len(self.findings),
            "findings": [f.to_dict() for f in self.findings],
            "data": self.data,
            "error": self.error,
        }


class BaseAnalysisAgent(ABC):
    """Common contract that all analysis agents must implement."""

    name: str
    agent_type: str
    description: str

    @abstractmethod
    async def analyze(self, context: AnalysisContext) -> AgentResult:
        """
        Execute analysis on the provided bounded context.

        Returns an AgentResult containing structured data and findings.
        Must not raise uncaught exceptions to allow partial analysis resilience.
        """
        pass
