from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class FindingResponse(BaseModel):
    """Serialized representation of a security or quality finding."""

    id: str
    review_id: str
    category: str
    severity: str
    title: str
    description: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    confidence: Optional[float] = None
    evidence: Optional[str] = None
    cwe: Optional[str] = None
    type: Optional[str] = None
    source: Optional[str] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class FindingListResponse(BaseModel):
    """Paginated list of findings."""

    items: List[FindingResponse] = Field(default_factory=list)
    total: int = 0


class SecuritySummaryResponse(BaseModel):
    """Aggregated security overview across all repositories."""

    overall_score: Optional[float] = None
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    resolved_count: int = 0
    open_count: int = 0
    repositories_analyzed: int = 0
    remediation_runs_count: int = 0
    verification_success_rate: Optional[float] = None


class FindingRelationshipResponse(BaseModel):
    """Serialized representation of a relationship edge between correlated and raw findings."""

    id: str
    correlated_finding_id: str
    source_finding_id: str
    relationship_type: str
    confidence: float
    rationale: Optional[str] = None
    created_at: datetime
    source_finding: Optional[FindingResponse] = None

    model_config = {"from_attributes": True}


class CorrelatedFindingResponse(BaseModel):
    """Unified cross-agent correlated finding."""

    id: str
    review_id: str
    snapshot_id: Optional[str] = None
    primary_finding_id: str
    category: str
    severity: str
    title: str
    description: Optional[str] = None
    root_cause: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    confidence: Optional[float] = None
    evidence: Optional[str] = None
    cwe: Optional[str] = None
    correlation_score: float = 1.0
    correlation_explanation: Optional[str] = None
    correlation_version: str = "1.0"
    status: str = "open"
    created_at: datetime
    relationships: List[FindingRelationshipResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class CorrelatedFindingListResponse(BaseModel):
    """Paginated list of correlated findings."""

    items: List[CorrelatedFindingResponse] = Field(default_factory=list)
    total: int = 0


class CorrelationStatusResponse(BaseModel):
    """Execution status and metrics for finding correlation."""

    review_id: str
    status: str
    total_raw_findings: int = 0
    correlated_clusters_count: int = 0
    exact_duplicates_count: int = 0
    overlapping_count: int = 0
    shared_root_cause_count: int = 0
    independent_count: int = 0
    semantic_evaluated: bool = False
    correlation_version: str = "1.0"


