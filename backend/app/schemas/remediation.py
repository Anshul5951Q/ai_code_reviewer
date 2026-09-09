"""
Pydantic schemas for automated remediation and independent verification.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class CodeChange(BaseModel):
    """An atomic code substitution within a file."""

    file_path: str
    start_line: int
    end_line: int
    original_code: str
    replacement_code: str


class RemediationPlan(BaseModel):
    """Structured remediation plan emitted by the RemediationAgent."""

    strategy: str
    explanation: str
    files_changed: List[str] = Field(default_factory=list)
    changes: List[CodeChange] = Field(default_factory=list)
    unified_diff: Optional[str] = None
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)


class VerificationResult(BaseModel):
    """Structured decision output from the VerificationAgent."""

    status: str  # resolved | partially_resolved | still_vulnerable | verification_failed
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    reason: str
    remaining_risk: Optional[str] = None
    new_findings: List[Dict[str, Any]] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"resolved", "partially_resolved", "still_vulnerable", "verification_failed"}
        val = v.lower().strip()
        if val not in allowed:
            raise ValueError(f"Invalid verification status: '{v}'. Must be one of {allowed}")
        return val


class RemediationRequest(BaseModel):
    """Payload to trigger an AI remediation run for a finding."""

    strategy_preference: Optional[str] = None


class RemediationRunResponse(BaseModel):
    """Execution status and metrics for a remediation run."""

    id: str
    review_id: str
    finding_id: str
    status: str
    agent_type: str = "remediation_agent"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    files_modified: int = 0
    patch_valid: bool = False
    verification_status: str = "not_started"
    error: Optional[str] = None
    metadata_json: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RemediationResultResponse(BaseModel):
    """Detailed remediation results including diff, explanation, and verification state."""

    id: str
    finding_id: str
    status: str
    strategy: Optional[str] = None
    explanation: Optional[str] = None
    changed_files: List[str] = Field(default_factory=list)
    diff: Optional[str] = None
    verification_status: str = "not_started"
    confidence: Optional[float] = None
    verification_explanation: Optional[str] = None
    attempt_number: int = 1


class VerificationDetailResponse(BaseModel):
    """Detailed verification assessment for a remediation run."""

    status: str
    confidence: float
    reason: str
    remaining_risk: Optional[str] = None
    new_findings: List[Dict[str, Any]] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)


class RemediationHistoryResponse(BaseModel):
    """History of all remediation attempts for a single finding."""

    runs: List[RemediationRunResponse] = Field(default_factory=list)
    total_attempts: int = 0
    can_retry: bool = True
