"""
Pydantic schemas for analysis job API responses.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel


class PipelineStage(str, Enum):
    """Canonical 13-stage lifecycle state machine for repository code analysis."""
    PENDING = "PENDING"
    INGESTING = "INGESTING"
    SNAPSHOTTING = "SNAPSHOTTING"
    UNDERSTANDING = "UNDERSTANDING"
    VERIFYING_UNDERSTANDING = "VERIFYING_UNDERSTANDING"
    QUALITY_ANALYSIS = "QUALITY_ANALYSIS"
    SECURITY_ANALYSIS = "SECURITY_ANALYSIS"
    VERIFYING_FINDINGS = "VERIFYING_FINDINGS"
    CORRELATING = "CORRELATING"
    ANALYSIS_COMPLETED = "ANALYSIS_COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


STAGE_PROGRESS_MAP: Dict[str, float] = {
    PipelineStage.PENDING.value: 0.0,
    PipelineStage.INGESTING.value: 15.0,
    PipelineStage.SNAPSHOTTING.value: 30.0,
    PipelineStage.UNDERSTANDING.value: 45.0,
    PipelineStage.VERIFYING_UNDERSTANDING.value: 55.0,
    PipelineStage.QUALITY_ANALYSIS.value: 65.0,
    PipelineStage.SECURITY_ANALYSIS.value: 75.0,
    PipelineStage.VERIFYING_FINDINGS.value: 85.0,
    PipelineStage.CORRELATING.value: 95.0,
    PipelineStage.ANALYSIS_COMPLETED.value: 100.0,
    PipelineStage.PARTIALLY_COMPLETED.value: 100.0,
    PipelineStage.FAILED.value: 100.0,
    PipelineStage.CANCELLED.value: 100.0,
}


class AnalysisJobResponse(BaseModel):
    """Serialized representation of an AnalysisJob."""
    id: str
    review_id: str
    status: str
    current_stage: Optional[str] = None
    progress: float
    files_total: int
    files_processed: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StartAnalysisResponse(BaseModel):
    """Response from POST /reviews/{id}/analyze."""
    job_id: str
    review_id: str
    status: str
    message: str
