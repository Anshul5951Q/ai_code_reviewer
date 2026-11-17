from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.remediation_run import RemediationRun
    from app.models.review import Review


class VerificationRun(Base):
    """Gate 5 verification result for a remediation patch."""

    __tablename__ = "verification_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    review_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False, index=True
    )
    remediation_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("remediation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    finding_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("findings.id", ondelete="SET NULL"), nullable=True, index=True
    )
    correlated_finding_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("correlated_findings.id", ondelete="SET NULL"), nullable=True, index=True
    )
    snapshot_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    patch_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    agent_run_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(32), default="completed", server_default="completed", index=True)
    outcome: Mapped[str] = mapped_column(
        String(32), default="UNABLE_TO_VERIFY", server_default="UNABLE_TO_VERIFY", index=True
    )
    gate_5_decision: Mapped[str] = mapped_column(
        String(32), default="UNRESOLVED", server_default="UNRESOLVED", index=True
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.9, server_default="0.9")
    methodology: Mapped[str] = mapped_column(
        String(128), default="source_transformation_sink", server_default="source_transformation_sink"
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    source_transformation_sink_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scanner_comparison_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    test_results_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    regression_results_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    remaining_evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_issues_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decision_reasons_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    failed_conditions_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    limitations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    review: Mapped["Review"] = relationship("Review", back_populates="verification_runs")
    remediation_run: Mapped["RemediationRun"] = relationship(
        "RemediationRun", back_populates="verification_runs"
    )

    def __repr__(self) -> str:
        return f"<VerificationRun {self.id!r} outcome={self.outcome!r}>"
