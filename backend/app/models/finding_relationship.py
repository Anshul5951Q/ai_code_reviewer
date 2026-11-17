from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.correlated_finding import CorrelatedFinding
    from app.models.finding import Finding


class FindingRelationship(Base):
    """Link between a correlated finding and one of its source findings."""

    __tablename__ = "finding_relationships"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    correlated_finding_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("correlated_findings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_finding_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relationship_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.85, server_default="0.85")
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    correlated_finding: Mapped["CorrelatedFinding"] = relationship(
        "CorrelatedFinding", back_populates="relationships"
    )
    source_finding: Mapped["Finding"] = relationship(
        "Finding", back_populates="finding_relationships", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<FindingRelationship {self.relationship_type!r}>"
