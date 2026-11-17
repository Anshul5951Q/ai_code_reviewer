from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.finding import Finding
    from app.models.finding_relationship import FindingRelationship
    from app.models.remediation_run import RemediationRun
    from app.models.review import Review


class CorrelatedFinding(Base):
    """A cluster of related raw findings, represented by a primary finding."""

    __tablename__ = "correlated_findings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    review_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False, index=True
    )
    snapshot_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    primary_finding_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True
    )

    category: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    root_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    file_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True, index=True)
    line_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    start_line: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    end_line: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cwe: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    correlation_score: Mapped[float] = mapped_column(Float, default=1.0, server_default="1.0")
    correlation_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    correlation_version: Mapped[str] = mapped_column(String(32), default="1.0", server_default="1.0")
    status: Mapped[str] = mapped_column(String(32), default="open", server_default="open", index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    review: Mapped["Review"] = relationship("Review", back_populates="correlated_findings")
    primary_finding: Mapped["Finding"] = relationship("Finding", foreign_keys=[primary_finding_id])
    relationships: Mapped[List["FindingRelationship"]] = relationship(
        "FindingRelationship",
        back_populates="correlated_finding",
        cascade="all, delete-orphan",
    )
    remediation_runs: Mapped[List["RemediationRun"]] = relationship(
        "RemediationRun", back_populates="correlated_finding", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<CorrelatedFinding {self.id!r} title={self.title!r}>"
