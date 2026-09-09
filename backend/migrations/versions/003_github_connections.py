"""Add github_connections table for secure OAuth token storage.

Revision ID: 003_github_connections
Revises: 002_analysis_tables
Create Date: 2026-09-09

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "003_github_connections"
down_revision: Union[str, None] = "002_analysis_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "github_connections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_identifier", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("github_user_id", sa.Integer(), nullable=False),
        sa.Column("github_login", sa.String(length=128), nullable=False),
        sa.Column("github_avatar_url", sa.String(length=512), nullable=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("token_type", sa.String(length=32), server_default="bearer", nullable=False),
        sa.Column("scope", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_identifier", name="uq_github_connections_session_identifier"),
    )
    op.create_index(
        "ix_github_connections_session_identifier",
        "github_connections",
        ["session_identifier"],
        unique=True,
    )
    op.create_index(
        "ix_github_connections_user_id",
        "github_connections",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_github_connections_github_user_id",
        "github_connections",
        ["github_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_github_connections_github_login",
        "github_connections",
        ["github_login"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_github_connections_github_login", table_name="github_connections")
    op.drop_index("ix_github_connections_github_user_id", table_name="github_connections")
    op.drop_index("ix_github_connections_user_id", table_name="github_connections")
    op.drop_index("ix_github_connections_session_identifier", table_name="github_connections")
    op.drop_table("github_connections")
