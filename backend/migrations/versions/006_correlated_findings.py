"""Add correlated_findings and finding_relationships tables for Sub-Phase 7.4.

Revision ID: 006_correlated_findings
Revises: 005_remediation_runs
Create Date: 2026-11-16

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "006_correlated_findings"
down_revision: Union[str, None] = "005_remediation_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create correlated_findings table
    op.create_table(
        "correlated_findings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("snapshot_id", sa.String(length=36), nullable=True),
        sa.Column("primary_finding_id", sa.String(length=36), nullable=False),
        sa.Column("category", sa.String(length=128), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("root_cause", sa.Text(), nullable=True),
        sa.Column("file_path", sa.String(length=1024), nullable=True),
        sa.Column("line_number", sa.Integer(), nullable=True),
        sa.Column("start_line", sa.Integer(), nullable=True),
        sa.Column("end_line", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("cwe", sa.String(length=64), nullable=True),
        sa.Column("correlation_score", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("correlation_explanation", sa.Text(), nullable=True),
        sa.Column("correlation_version", sa.String(length=32), server_default="1.0", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="open", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["primary_finding_id"], ["findings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_correlated_findings_review_id", "correlated_findings", ["review_id"], unique=False)
    op.create_index("ix_correlated_findings_snapshot_id", "correlated_findings", ["snapshot_id"], unique=False)
    op.create_index("ix_correlated_findings_primary_finding_id", "correlated_findings", ["primary_finding_id"], unique=False)
    op.create_index("ix_correlated_findings_category", "correlated_findings", ["category"], unique=False)
    op.create_index("ix_correlated_findings_severity", "correlated_findings", ["severity"], unique=False)
    op.create_index("ix_correlated_findings_file_path", "correlated_findings", ["file_path"], unique=False)
    op.create_index("ix_correlated_findings_cwe", "correlated_findings", ["cwe"], unique=False)
    op.create_index("ix_correlated_findings_status", "correlated_findings", ["status"], unique=False)

    # 2. Create finding_relationships table
    op.create_table(
        "finding_relationships",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("correlated_finding_id", sa.String(length=36), nullable=False),
        sa.Column("source_finding_id", sa.String(length=36), nullable=False),
        sa.Column("relationship_type", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0.85", nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["correlated_finding_id"], ["correlated_findings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_finding_id"], ["findings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_finding_relationships_correlated_finding_id", "finding_relationships", ["correlated_finding_id"], unique=False)
    op.create_index("ix_finding_relationships_source_finding_id", "finding_relationships", ["source_finding_id"], unique=False)
    op.create_index("ix_finding_relationships_relationship_type", "finding_relationships", ["relationship_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_finding_relationships_relationship_type", table_name="finding_relationships")
    op.drop_index("ix_finding_relationships_source_finding_id", table_name="finding_relationships")
    op.drop_index("ix_finding_relationships_correlated_finding_id", table_name="finding_relationships")
    op.drop_table("finding_relationships")

    op.drop_index("ix_correlated_findings_status", table_name="correlated_findings")
    op.drop_index("ix_correlated_findings_cwe", table_name="correlated_findings")
    op.drop_index("ix_correlated_findings_file_path", table_name="correlated_findings")
    op.drop_index("ix_correlated_findings_severity", table_name="correlated_findings")
    op.drop_index("ix_correlated_findings_category", table_name="correlated_findings")
    op.drop_index("ix_correlated_findings_primary_finding_id", table_name="correlated_findings")
    op.drop_index("ix_correlated_findings_snapshot_id", table_name="correlated_findings")
    op.drop_index("ix_correlated_findings_review_id", table_name="correlated_findings")
    op.drop_table("correlated_findings")

