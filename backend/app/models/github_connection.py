from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class GitHubConnection(Base):
    """
    Stores an encrypted OAuth connection to a user's GitHub account.
    Bound to an anonymous browser session identifier in Phase 4.
    Includes optional user_id for future application authentication in Phase 7.
    """

    __tablename__ = "github_connections"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # Session binding (temporary identity boundary prior to full user auth)
    session_identifier: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )

    # Future multi-tenant user identification
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, index=True
    )

    # GitHub account details
    github_user_id: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True
    )
    github_login: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    github_avatar_url: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True
    )

    # Security: token is ALWAYS stored encrypted at rest
    access_token_encrypted: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    token_type: Mapped[str] = mapped_column(
        String(32), default="bearer", nullable=False
    )
    scope: Mapped[Optional[str]] = mapped_column(
        String(256), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        # Never log or expose token fields
        return f"<GitHubConnection login={self.github_login!r} session={self.session_identifier[:8]}...>"
