"""
Pydantic schemas for automated remediation, Gate 4 patch verification, and risk assessment.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class PatchRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Gate4Status(str, Enum):
    PENDING = "PENDING"
    VALIDATING = "VALIDATING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    PARTIALLY_PASSED = "PARTIALLY_PASSED"
    UNABLE_TO_VERIFY = "UNABLE_TO_VERIFY"


class CodeChange(BaseModel):
    """An atomic code substitution within a file."""

    file_path: str
    start_line: int
    end_line: int
    original_code: str
    replacement_code: str


class Gate4CheckResult(BaseModel):
    """Individual Gate 4 deterministic verification check result."""

    check_name: str
    status: str  # passed | failed | warning | skipped
    details: str
    evidence: Optional[str] = None


class Gate4AuditReport(BaseModel):
    """Structured report of all Gate 4 patch verification checks."""

    gate_status: str = Gate4Status.PENDING.value
    checks: List[Gate4CheckResult] = Field(default_factory=list)
    target_files: List[str] = Field(default_factory=list)
    syntax_valid: bool = False
    static_finding_cleared: bool = False
    new_issues_detected: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PatchRiskAssessment(BaseModel):
    """Deterministic remediation patch risk assessment."""

    level: str = PatchRiskLevel.LOW.value  # LOW | MEDIUM | HIGH | CRITICAL
    score: float = Field(default=0.1, ge=0.0, le=1.0)
    factors: List[str] = Field(default_factory=list)
    explanation: str = "Low risk patch confined to single function without interface changes."


class RemediationPlan(BaseModel):
    """Structured remediation plan emitted by the RemediationAgent."""

    strategy: str
    explanation: str
    files_changed: List[str] = Field(default_factory=list)
    changes: List[CodeChange] = Field(default_factory=list)
    unified_diff: Optional[str] = None
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)

    # Sub-Phase 7.5 fields
    root_cause: Optional[str] = None
    proposed_solution: Optional[str] = None
    expected_behavior: Optional[str] = None
    potential_side_effects: Optional[str] = None
    required_tests: List[str] = Field(default_factory=list)
    risk_assessment: Optional[PatchRiskAssessment] = None
    patch_status: str = "generated"
    gate_4_status: str = Gate4Status.PENDING.value


class VerificationResult(BaseModel):
    """Structured decision output from the VerificationAgent (Gate 5 / Phase 7.6)."""

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
    """Payload to trigger an AI remediation run for a finding or correlated cluster."""

    strategy_preference: Optional[str] = None
    correlated_finding_id: Optional[str] = None


class BatchRemediationRequest(BaseModel):
    """Payload to trigger remediation on all eligible findings of a review."""

    min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    categories: Optional[List[str]] = None


class RemediationRunResponse(BaseModel):
    """Execution status and metrics for a remediation run."""

    id: str
    review_id: str
    finding_id: Optional[str] = None
    correlated_finding_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    status: str
    agent_type: str = "remediation_agent"
    patch_version: int = 1
    risk_level: str = PatchRiskLevel.LOW.value
    gate_4_status: str = Gate4Status.PENDING.value
    gate_5_decision: str = "UNRESOLVED"
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
    """Detailed remediation results including diff, explanation, Gate 4 audit, and risk state."""

    id: str
    finding_id: Optional[str] = None
    correlated_finding_id: Optional[str] = None
    status: str
    strategy: Optional[str] = None
    explanation: Optional[str] = None
    changed_files: List[str] = Field(default_factory=list)
    diff: Optional[str] = None
    patch_version: int = 1
    risk_level: str = PatchRiskLevel.LOW.value
    risk_assessment: Optional[PatchRiskAssessment] = None
    gate_4_status: str = Gate4Status.PENDING.value
    gate_4_checks: List[Gate4CheckResult] = Field(default_factory=list)
    gate_5_decision: str = "UNRESOLVED"
    gate_5_result: Optional[Dict[str, Any]] = None
    root_cause: Optional[str] = None
    potential_side_effects: Optional[str] = None
    expected_behavior: Optional[str] = None
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
    """History of all remediation attempts for a single finding or correlated cluster."""

    runs: List[RemediationRunResponse] = Field(default_factory=list)
    total_attempts: int = 0
    can_retry: bool = True


class BatchRemediationResponse(BaseModel):
    """Response when triggering remediation for eligible findings across a review."""

    review_id: str
    queued_runs: List[RemediationRunResponse] = Field(default_factory=list)
    total_queued: int = 0
    skipped_count: int = 0
    skipped_reasons: List[str] = Field(default_factory=list)
