"""Add agent_runs table and extend findings and reviews for Phase 5.

Revision ID: 004_agent_runs_and_findings
Revises: 003_github_connections
Create Date: 2026-09-09

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "004_agent_runs_and_findings"
down_revision: Union[str, None] = "003_github_connections"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create agent_runs table
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("agent_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("files_analyzed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("findings_generated", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_runs_review_id", "agent_runs", ["review_id"], unique=False)
    op.create_index("ix_agent_runs_agent_type", "agent_runs", ["agent_type"], unique=False)
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"], unique=False)

    # 2. Extend findings table
    with op.batch_alter_table("findings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("start_line", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("end_line", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("type", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("evidence", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("cwe", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("source", sa.String(length=64), server_default="code_review_agent", nullable=True))
        batch_op.create_index("ix_findings_type", ["type"], unique=False)
        batch_op.create_index("ix_findings_cwe", ["cwe"], unique=False)

    # 3. Extend reviews table
    with op.batch_alter_table("reviews", schema=None) as batch_op:
        batch_op.add_column(sa.Column("architecture_score", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("reviews", schema=None) as batch_op:
        batch_op.drop_column("architecture_score")

    with op.batch_alter_table("findings", schema=None) as batch_op:
        batch_op.drop_index("ix_findings_cwe")
        batch_op.drop_index("ix_findings_type")
        batch_op.drop_column("source")
        batch_op.drop_column("cwe")
        batch_op.drop_column("evidence")
        batch_op.drop_column("type")
        batch_op.drop_column("end_line")
        batch_op.drop_column("start_line")

    op.drop_index("ix_agent_runs_status", table_name="agent_runs")
    op.drop_index("ix_agent_runs_agent_type", table_name="agent_runs")
    op.drop_index("ix_agent_runs_review_id", table_name="agent_runs")
    op.drop_table("agent_runs")
