"""Add remediation_runs table for Phase 6.

Revision ID: 005_remediation_runs
Revises: 004_agent_runs_and_findings
Create Date: 2026-09-09

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "005_remediation_runs"
down_revision: Union[str, None] = "004_agent_runs_and_findings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "remediation_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("finding_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("agent_type", sa.String(length=64), server_default="remediation_agent", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("files_modified", sa.Integer(), server_default="0", nullable=False),
        sa.Column("patch_valid", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("verification_status", sa.String(length=32), server_default="not_started", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["finding_id"], ["findings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_remediation_runs_review_id", "remediation_runs", ["review_id"], unique=False)
    op.create_index("ix_remediation_runs_finding_id", "remediation_runs", ["finding_id"], unique=False)
    op.create_index("ix_remediation_runs_status", "remediation_runs", ["status"], unique=False)
    op.create_index("ix_remediation_runs_verification_status", "remediation_runs", ["verification_status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_remediation_runs_verification_status", table_name="remediation_runs")
    op.drop_index("ix_remediation_runs_status", table_name="remediation_runs")
    op.drop_index("ix_remediation_runs_finding_id", table_name="remediation_runs")
    op.drop_index("ix_remediation_runs_review_id", table_name="remediation_runs")
    op.drop_table("remediation_runs")
