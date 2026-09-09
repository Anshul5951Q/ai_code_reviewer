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

