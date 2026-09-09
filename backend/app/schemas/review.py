from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ReviewCreate(BaseModel):
    """Payload to schedule / queue a new code review."""
    repository_id: str
    commit_sha: str = Field(..., min_length=7, max_length=40)
    branch: str = Field(default="main", min_length=1, max_length=255)


class ReviewResponse(BaseModel):
    """Serialized representation of a code review."""

    id: str
    repository_id: str
    commit_sha: str
    branch: str
    status: str
    overall_score: Optional[float] = None
    security_score: Optional[float] = None
    quality_score: Optional[float] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewListResponse(BaseModel):
    """Paginated list of reviews."""

    items: List[ReviewResponse] = Field(default_factory=list)
    total: int = 0
