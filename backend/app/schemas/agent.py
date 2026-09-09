"""
Pydantic schemas for agent runs and multi-agent execution.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentRunResponse(BaseModel):
    """Execution status and metrics for an individual agent run."""

    id: str
    review_id: str
    agent_type: str
    type: Optional[str] = None
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    files_analyzed: int = 0
    findings_generated: int = 0
    error: Optional[str] = None
    metadata_json: Optional[str] = None

    model_config = {"from_attributes": True}

    def model_post_init(self, __context: Any) -> None:
        if self.type is None:
            self.type = self.agent_type


class AgentRunListResponse(BaseModel):
    """List of agent runs for a review."""

    agents: List[AgentRunResponse] = Field(default_factory=list)


class StartPhase5AnalysisResponse(BaseModel):
    """Response when triggering Phase 5 multi-agent analysis."""

    review_id: str
    status: str
    message: str
