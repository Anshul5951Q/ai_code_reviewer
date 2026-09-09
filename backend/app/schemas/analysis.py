"""
Pydantic schemas for analysis job API responses.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


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
