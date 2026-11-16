from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.correlated_finding import CorrelatedFinding
    from app.models.finding import Finding
    from app.models.review import Review
    from app.models.verification_run import VerificationRun


class RemediationRun(Base):
    """Tracks an automated remediation attempt, Gate 4 patch verification, and risk assessment."""

    __tablename__ = "remediation_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    review_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False, index=True
    )
    finding_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("findings.id", ondelete="CASCADE"), nullable=True, index=True
    )
    correlated_finding_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("correlated_findings.id", ondelete="CASCADE"), nullable=True, index=True
    )
    snapshot_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, index=True
    )

    # Status: queued | generating | patch_generated | patch_validated | verifying | completed | failed | cancelled
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)

    agent_type: Mapped[str] = mapped_column(String(64), default="remediation_agent")

    # Patch version and risk assessment
    patch_version: Mapped[int] = mapped_column(Integer, default=1)
    risk_level: Mapped[str] = mapped_column(String(32), default="LOW", index=True)

    # Gate 4 Status: PENDING | VALIDATING | PASSED | FAILED | PARTIALLY_PASSED | UNABLE_TO_VERIFY
    gate_4_status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)

    # Gate 5 Decision: RESOLVED | UNRESOLVED | PARTIALLY_RESOLVED | BLOCKED | UNABLE_TO_VERIFY
    gate_5_decision: Mapped[str] = mapped_column(String(32), default="UNRESOLVED", index=True)

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    files_modified: Mapped[int] = mapped_column(Integer, default=0)
    patch_valid: Mapped[bool] = mapped_column(Boolean, default=False)

    # Verification status: not_started | resolved | partially_resolved | still_vulnerable | verification_failed
    verification_status: Mapped[str] = mapped_column(
        String(32), default="not_started", index=True
    )

    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    review: Mapped["Review"] = relationship("Review", back_populates="remediation_runs")
    finding: Mapped[Optional["Finding"]] = relationship("Finding", back_populates="remediation_runs")
    correlated_finding: Mapped[Optional["CorrelatedFinding"]] = relationship(
        "CorrelatedFinding", back_populates="remediation_runs"
    )
    verification_runs: Mapped[list["VerificationRun"]] = relationship(
        "VerificationRun",
        back_populates="remediation_run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<RemediationRun {self.id!r} finding={self.finding_id!r} status={self.status!r}>"
