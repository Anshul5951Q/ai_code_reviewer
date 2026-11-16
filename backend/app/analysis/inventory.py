"""
Canonical File Inventory and Analysis Coverage Tracking.

Implements rigorous, multi-state file tracking across repository ingestion,
AST parsing, and agent analysis workflows to eliminate blind trust and zero-file
phantom analyses.
"""
from __future__ import annotations

import hashlib
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field


class FileProcessingStatus(str, Enum):
    """Lifecycle states for each repository file during ingestion and review."""
    DISCOVERED = "DISCOVERED"      # Present in Git tree
    FILTERED = "FILTERED"          # Excluded by size, binary check, or vendor rule
    DOWNLOADED = "DOWNLOADED"      # Content successfully fetched over API
    DECODED = "DECODED"            # Base64/UTF-8 successfully decoded
    PARSED = "PARSED"              # AST or token parsed without fatal syntax errors
    ANALYZED = "ANALYZED"          # Inspected by one or more analysis agents
    FAILED = "FAILED"              # Fetch, decode, or parse operation threw an error
    UNSUPPORTED = "UNSUPPORTED"    # File extension not supported by platform analyzers


class FileInventoryItem(BaseModel):
    """Tracks the complete provenance and status of a single repository file."""
    path: str
    status: FileProcessingStatus = FileProcessingStatus.DISCOVERED
    language: Optional[str] = None
    size_bytes: int = 0
    content_hash: Optional[str] = None  # SHA-256
    is_source: bool = False
    is_test: bool = False
    is_config: bool = False
    parsing_status: str = "not_attempted"  # "not_attempted" | "parsed" | "failed" | "unsupported"
    analysis_status: str = "pending"        # "pending" | "analyzed" | "skipped" | "failed"
    applicable_agents: List[str] = Field(default_factory=list)
    analyzed_by_agents: List[str] = Field(default_factory=list)
    failure_reason: Optional[str] = None

    def mark_downloaded(self, content: str, language: Optional[str] = None) -> None:
        self.status = FileProcessingStatus.DOWNLOADED
        self.content_hash = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()
        self.size_bytes = len(content.encode("utf-8", errors="replace"))
        if language:
            self.language = language

    def mark_parsed(self, success: bool = True, error: Optional[str] = None) -> None:
        if success:
            self.status = FileProcessingStatus.PARSED
            self.parsing_status = "parsed"
        else:
            self.status = FileProcessingStatus.FAILED
            self.parsing_status = "failed"
            self.failure_reason = error

    def mark_analyzed_by(self, agent_name: str) -> None:
        if agent_name not in self.analyzed_by_agents:
            self.analyzed_by_agents.append(agent_name)
        self.status = FileProcessingStatus.ANALYZED
        self.analysis_status = "analyzed"

    def mark_failed(self, reason: str) -> None:
        self.status = FileProcessingStatus.FAILED
        self.failure_reason = reason


class InventoryCoverage(BaseModel):
    """Aggregated coverage metrics for repository analysis."""
    total_discovered: int = 0
    total_eligible_source: int = 0
    total_downloaded: int = 0
    total_parsed: int = 0
    total_analyzed: int = 0
    agent_coverage: Dict[str, int] = Field(default_factory=dict)
    total_failed: int = 0
    total_unsupported: int = 0
    total_excluded: int = 0
    coverage_percentage: float = 0.0
    coverage_status: str = "INSUFFICIENT ANALYSIS COVERAGE"
    limitations: List[str] = Field(default_factory=list)

    @property
    def downloaded_count(self) -> int:
        return self.total_downloaded

    @property
    def analyzed_count(self) -> int:
        return self.total_analyzed


class FileInventory(BaseModel):
    """Canonical registry of repository files for a review."""
    review_id: str
    commit_sha: str
    snapshot_id: Optional[str] = None
    items: Dict[str, FileInventoryItem] = Field(default_factory=dict)

    def add_discovered(
        self,
        path: str,
        size_bytes: int = 0,
        is_source: bool = False,
        is_test: bool = False,
        is_config: bool = False,
        language: Optional[str] = None,
    ) -> FileInventoryItem:
        if path not in self.items:
            # Determine applicable agents
            applicable = []
            if is_source:
                applicable.extend(["code_understanding", "code_quality", "security_agent", "security_static"])
            elif is_config:
                applicable.extend(["code_understanding", "security_agent", "security_static"])

            item = FileInventoryItem(
                path=path,
                status=FileProcessingStatus.DISCOVERED,
                language=language,
                size_bytes=size_bytes,
                is_source=is_source,
                is_test=is_test,
                is_config=is_config,
                applicable_agents=applicable,
            )
            self.items[path] = item
        return self.items[path]

    def mark_filtered(self, path: str, reason: str) -> None:
        if path in self.items:
            self.items[path].status = FileProcessingStatus.FILTERED
            self.items[path].failure_reason = reason

    def mark_downloaded(self, path: str, content: str, language: Optional[str] = None) -> None:
        if path not in self.items:
            self.add_discovered(path, size_bytes=len(content))
        self.items[path].mark_downloaded(content, language)

    def mark_parsed(self, path: str, success: bool = True, error: Optional[str] = None) -> None:
        if path in self.items:
            self.items[path].mark_parsed(success, error)

    def mark_analyzed_by(self, path: str, agent_name: str) -> None:
        if path in self.items:
            self.items[path].mark_analyzed_by(agent_name)

    def mark_failed(self, path: str, reason: str) -> None:
        if path in self.items:
            self.items[path].mark_failed(reason)

    def record_discovered(self, path: str, size_bytes: int = 0, is_source: bool = True, **kwargs) -> FileInventoryItem:
        return self.add_discovered(path, size_bytes=size_bytes, is_source=is_source, **kwargs)

    def record_filtered(self, path: str, reason: str) -> None:
        return self.mark_filtered(path, reason)

    def record_downloaded(self, path: str, size_bytes: int = 0) -> None:
        if path not in self.items:
            self.add_discovered(path, size_bytes=size_bytes, is_source=True)
        self.items[path].status = FileProcessingStatus.DOWNLOADED

    def record_decoded(self, path: str, content: str) -> None:
        if path in self.items:
            self.items[path].mark_downloaded(content)

    def record_analyzed(self, path: str, agent_name: str) -> None:
        if path not in self.items:
            self.add_discovered(path, is_source=True)
        self.mark_analyzed_by(path, agent_name)

    def calculate_coverage(self, total_eligible_source: Optional[int] = None) -> InventoryCoverage:
        """Derive coverage metrics from actual persisted file records."""
        total_disc = len(self.items)
        eligible_source = [it for it in self.items.values() if it.is_source]
        downloaded = [it for it in self.items.values() if it.status in (
            FileProcessingStatus.DOWNLOADED,
            FileProcessingStatus.DECODED,
            FileProcessingStatus.PARSED,
            FileProcessingStatus.ANALYZED,
        )]
        parsed = [it for it in self.items.values() if it.parsing_status == "parsed" or it.status == FileProcessingStatus.ANALYZED]
        analyzed = [it for it in self.items.values() if it.status == FileProcessingStatus.ANALYZED]
        failed = [it for it in self.items.values() if it.status == FileProcessingStatus.FAILED]
        unsupported = [it for it in self.items.values() if it.status == FileProcessingStatus.UNSUPPORTED]
        excluded = [it for it in self.items.values() if it.status == FileProcessingStatus.FILTERED]

        # Calculate agent-specific counts
        agent_counts: Dict[str, int] = {}
        for it in self.items.values():
            for ag in it.analyzed_by_agents:
                agent_counts[ag] = agent_counts.get(ag, 0) + 1

        source_count = total_eligible_source if total_eligible_source is not None else len(eligible_source)
        denom = max(1, source_count)
        coverage_pct = round((len(analyzed) / denom) * 100.0, 1)

        limitations = []
        if len(failed) > 0:
            limitations.append(f"{len(failed)} files failed downloading or parsing.")
        if len(unsupported) > 0:
            limitations.append(f"{len(unsupported)} files have unsupported extensions.")
        if len(excluded) > 0:
            limitations.append(f"{len(excluded)} non-source or oversized files were excluded.")

        if total_disc == 0 or len(analyzed) == 0:
            coverage_status = "INSUFFICIENT ANALYSIS COVERAGE"
            coverage_pct = 0.0
            limitations.append("Zero files were analyzed by analysis agents.")
        elif coverage_pct < 40.0:
            coverage_status = "PARTIAL ANALYSIS COVERAGE"
        elif len(failed) > 0:
            coverage_status = "SECURITY ANALYSIS DEGRADED"
        else:
            coverage_status = "ADEQUATE ANALYSIS COVERAGE"

        return InventoryCoverage(
            total_discovered=total_disc,
            total_eligible_source=len(eligible_source),
            total_downloaded=len(downloaded),
            total_parsed=len(parsed),
            total_analyzed=len(analyzed),
            agent_coverage=agent_counts,
            total_failed=len(failed),
            total_unsupported=len(unsupported),
            total_excluded=len(excluded),
            coverage_percentage=coverage_pct,
            coverage_status=coverage_status,
            limitations=limitations,
        )

    def to_dict(self) -> Dict[str, Any]:
        coverage = self.calculate_coverage()
        return {
            "review_id": self.review_id,
            "commit_sha": self.commit_sha,
            "snapshot_id": self.snapshot_id,
            "coverage": coverage.model_dump(),
            "items": {p: it.model_dump() for p, it in self.items.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileInventory":
        inv = cls(
            review_id=data.get("review_id", ""),
            commit_sha=data.get("commit_sha", ""),
            snapshot_id=data.get("snapshot_id"),
        )
        raw_items = data.get("items", {})
        for p, it_data in raw_items.items():
            inv.items[p] = FileInventoryItem(**it_data)
        return inv
