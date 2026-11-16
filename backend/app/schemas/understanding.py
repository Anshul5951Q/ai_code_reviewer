"""
Pydantic schemas for Code Understanding Agent and Gate 1 Verification.

Strict contract enforcing:
1. Structured model output from LLM (CodeUnderstandingResult)
2. Deterministic validation report (ValidationReport)
3. Trusted verified repository intelligence (RepositoryIntelligence)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

from pydantic import BaseModel, Field, model_validator


class ModuleDescription(BaseModel):
    """Structured description of a verified architectural module or package."""

    name: str = Field(description="Module or package name")
    path: str = Field(description="File or directory path representing the module")
    responsibility: str = Field(description="Architectural responsibility and role of this module")
    key_symbols: List[str] = Field(
        default_factory=list,
        description="Key classes, interfaces, or primary functions contained in this module",
    )
    evidence: Optional[str] = Field(
        default=None,
        description="Direct code or configuration evidence supporting this module definition",
    )
    confidence: float = Field(
        default=0.8,
        description="LLM confidence in this module assessment (0.0 to 1.0)",
    )


class CodeUnderstandingResult(BaseModel):
    """
    Direct structured output contract from the CodeUnderstandingAgent LLM call.
    Treated as an UNVERIFIED HYPOTHESIS until validated by Gate 1.
    """

    architecture_summary: str = Field(
        description="High-level synthesis of architecture, style, and design patterns"
    )
    languages: List[str] = Field(
        default_factory=list,
        description="Programming languages identified in the repository",
    )
    frameworks: List[str] = Field(
        default_factory=list,
        description="Application frameworks and libraries identified in the repository",
    )
    entry_points: List[str] = Field(
        default_factory=list,
        description="Primary executable or bootstrap entry points identified in the repository",
    )
    modules: List[ModuleDescription] = Field(
        default_factory=list,
        description="Key architectural modules, packages, and layers",
    )
    important_files: List[str] = Field(
        default_factory=list,
        description="Critical configuration, routing, or architectural anchor files",
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="Core third-party dependencies identified",
    )
    external_integrations: List[str] = Field(
        default_factory=list,
        description="External systems, databases, cloud APIs, or third-party service boundaries",
    )
    security_boundaries: List[str] = Field(
        default_factory=list,
        description="Authentication, authorization, or sensitive data flow boundaries",
    )
    data_flows: List[str] = Field(
        default_factory=list,
        description="Primary end-to-end data and control flow descriptions",
    )
    confidence: float = Field(
        default=0.85,
        description="Overall agent confidence score between 0.0 and 1.0",
    )

    # Backward-compatibility / migration fields for Phase 5 callers
    important_modules: List[str] = Field(
        default_factory=list,
        description="Legacy list of module name strings",
    )
    architecture_risks: List[str] = Field(
        default_factory=list,
        description="Identified architectural risks or design anti-patterns",
    )
    observations: List[str] = Field(
        default_factory=list,
        description="Engineering pattern observations",
    )

    @model_validator(mode="after")
    def sync_legacy_fields(self) -> "CodeUnderstandingResult":
        # Keep important_modules synced with modules
        if self.modules and not self.important_modules:
            self.important_modules = [m.path or m.name for m in self.modules]
        elif self.important_modules and not self.modules:
            self.modules = [
                ModuleDescription(
                    name=m.split("/")[-1] if "/" in m else m,
                    path=m,
                    responsibility="Core architectural module",
                )
                for m in self.important_modules
            ]
        return self


# Backward-compatibility alias
CodeUnderstandingOutput = CodeUnderstandingResult


class ValidationReport(BaseModel):
    """
    Deterministic validation metrics produced exclusively by Gate 1.
    Never generated or influenced by the LLM.
    """

    accepted_claims: int = Field(default=0, description="Total number of empirically verified claims")
    rejected_claims: int = Field(default=0, description="Total number of rejected or unverified claims")
    rejected_paths: List[str] = Field(
        default_factory=list, description="Nonexistent or hallucinated file and directory paths"
    )
    rejected_symbols: List[str] = Field(
        default_factory=list, description="Phantom classes, methods, or functions rejected"
    )
    unsupported_frameworks: List[str] = Field(
        default_factory=list, description="Framework claims lacking package manifest or code evidence"
    )
    validation_warnings: List[str] = Field(
        default_factory=list, description="Specific human-readable validation failure reasons"
    )


class RepositoryIntelligence(BaseModel):
    """
    Trusted Repository Intelligence produced ONLY after Gate 1 verification.
    Guaranteed: Contains zero hallucinated files, phantom symbols, or unsupported frameworks.
    """

    repository_id: str = Field(description="Associated repository identifier")
    snapshot_id: Optional[str] = Field(default=None, description="Associated snapshot identifier")

    languages: List[str] = Field(default_factory=list, description="Empirically verified languages")
    frameworks: List[str] = Field(default_factory=list, description="Empirically verified frameworks")
    entry_points: List[str] = Field(
        default_factory=list, description="Empirically verified entry points with bootstrap evidence"
    )

    modules: List[ModuleDescription] = Field(
        default_factory=list, description="Verified architectural modules with valid paths and symbols"
    )
    important_files: List[str] = Field(
        default_factory=list, description="Verified critical file paths present in the snapshot"
    )

    dependencies: List[str] = Field(
        default_factory=list, description="Verified dependencies anchored to manifests"
    )
    external_integrations: List[str] = Field(
        default_factory=list, description="Verified external integrations"
    )

    security_boundaries: List[str] = Field(
        default_factory=list, description="Identified security and trust boundaries"
    )
    data_flows: List[str] = Field(
        default_factory=list, description="Verified architectural data flows"
    )

    architecture_summary: str = Field(
        description="Synthesized architectural summary from the understanding agent"
    )

    agent_confidence: float = Field(
        description="LLM's internal confidence score (independent from verification status)"
    )
    verification_status: str = Field(
        default="unverified",
        description="Deterministic status: 'verified' | 'verified_with_scrubbing' | 'failed_validation'",
    )

    validation_report: ValidationReport = Field(
        default_factory=ValidationReport,
        description="Comprehensive audit of accepted and scrubbed claims",
    )

    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Timestamp of intelligence generation",
    )
