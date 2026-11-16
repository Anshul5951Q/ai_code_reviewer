"""
Pydantic schemas for Sub-Phase 7.6:
Independent Verification Agent, Deterministic Re-Scanning, and Gate 5 Decision Engine.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class VerificationOutcome(str, Enum):
    """Explicit verification outcomes determined by the independent VerificationAgent."""
    FIXED = "FIXED"
    PARTIALLY_FIXED = "PARTIALLY_FIXED"
    NOT_FIXED = "NOT_FIXED"
    REGRESSION_DETECTED = "REGRESSION_DETECTED"
    UNABLE_TO_VERIFY = "UNABLE_TO_VERIFY"


class Gate5Decision(str, Enum):
    """Final deterministic resolution decisions issued by Gate 5."""
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"
    PARTIALLY_RESOLVED = "PARTIALLY_RESOLVED"
    BLOCKED = "BLOCKED"
    UNABLE_TO_VERIFY = "UNABLE_TO_VERIFY"


class SourceTransformationSinkAssessment(BaseModel):
    """Structured assessment evaluating data flow from untrusted source to sink."""
    source_input: Optional[str] = None
    transformation: Optional[str] = None
    sink: Optional[str] = None
    is_exploitable_path_severed: bool = True
    remaining_attack_surface: Optional[str] = None
    rationale: str = "Root cause analysis of untrusted data flow."


class ScannerComparisonResult(BaseModel):
    """Empirical comparison between pre-patch and post-patch static analyzer outputs."""
    pre_patch_findings_count: int = 0
    post_patch_findings_count: int = 0
    target_defect_cleared: bool = True
    cleared_findings: List[Dict[str, Any]] = Field(default_factory=list)
    retained_findings: List[Dict[str, Any]] = Field(default_factory=list)
    new_findings: List[Dict[str, Any]] = Field(default_factory=list)


class Gate5DecisionResult(BaseModel):
    """Audit output produced by Gate 5 Deterministic Decision Engine."""
    decision: str = Gate5Decision.UNRESOLVED.value
    passed_conditions: List[str] = Field(default_factory=list)
    failed_conditions: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    patch_version: int = 1
    snapshot_id: Optional[str] = None
    is_resolved: bool = False
    limitations: Optional[str] = None


class VerificationAgentReport(BaseModel):
    """Structured response from the LLM-powered independent VerificationAgent."""
    outcome: str = VerificationOutcome.UNABLE_TO_VERIFY.value
    status_alias: Optional[str] = Field(default=None, alias="status")
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    reason: str
    source_transformation_sink: Optional[SourceTransformationSinkAssessment] = None
    remaining_risk: Optional[str] = None
    new_findings: List[Dict[str, Any]] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)

    def model_post_init(self, __context: Any) -> None:
        if self.status_alias and self.outcome == VerificationOutcome.UNABLE_TO_VERIFY.value:
            from app.agents.verification import VerificationAgent
            self.outcome = VerificationAgent._normalize_outcome(self.status_alias)

    @property
    def status(self) -> str:
        """Backward compatibility alias for outcome."""
        mapping = {
            VerificationOutcome.FIXED.value: "resolved",
            VerificationOutcome.PARTIALLY_FIXED.value: "partially_resolved",
            VerificationOutcome.NOT_FIXED.value: "still_vulnerable",
            VerificationOutcome.REGRESSION_DETECTED.value: "verification_failed",
            VerificationOutcome.UNABLE_TO_VERIFY.value: "verification_failed",
        }
        return mapping.get(self.outcome, self.outcome.lower())


class VerificationRunResponse(BaseModel):
    """Complete API response model for a persisted verification run."""
    id: str
    review_id: str
    remediation_run_id: str
    finding_id: Optional[str] = None
    correlated_finding_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    patch_version: int = 1
    agent_run_id: Optional[str] = None
    status: str = "completed"
    outcome: str = VerificationOutcome.UNABLE_TO_VERIFY.value
    gate_5_decision: str = Gate5Decision.UNRESOLVED.value
    confidence: float = 0.9
    methodology: str = "source_transformation_sink"
    reason: Optional[str] = None
    source_transformation_sink: Optional[SourceTransformationSinkAssessment] = None
    scanner_comparison: Optional[ScannerComparisonResult] = None
    test_results: List[Dict[str, Any]] = Field(default_factory=list)
    regression_results: List[Dict[str, Any]] = Field(default_factory=list)
    remaining_evidence: Optional[str] = None
    new_issues_detected: List[Dict[str, Any]] = Field(default_factory=list)
    decision_reasons: List[str] = Field(default_factory=list)
    failed_conditions: List[str] = Field(default_factory=list)
    limitations: Optional[str] = None
    duration_ms: Optional[int] = None
    created_at: datetime


class VerificationHistoryResponse(BaseModel):
    """Historical verification runs for a remediation run or finding."""
    remediation_run_id: Optional[str] = None
    finding_id: Optional[str] = None
    total_runs: int = 0
    runs: List[VerificationRunResponse] = Field(default_factory=list)
