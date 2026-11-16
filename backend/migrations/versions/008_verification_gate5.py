"""Add verification_runs table and gate_5_decision to remediation_runs.

Revision ID: 008_verification_gate5
Revises: 007_remediation_gate4
Create Date: 2026-11-16

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "008_verification_gate5"
down_revision: Union[str, None] = "007_remediation_gate4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add gate_5_decision to remediation_runs
    op.add_column(
        "remediation_runs",
        sa.Column("gate_5_decision", sa.String(length=32), server_default="UNRESOLVED", nullable=False),
    )
    op.create_index("ix_remediation_runs_gate_5_decision", "remediation_runs", ["gate_5_decision"])

    # 2. Create verification_runs table
    op.create_table(
        "verification_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("review_id", sa.String(length=36), sa.ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False),
        sa.Column("remediation_run_id", sa.String(length=36), sa.ForeignKey("remediation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("finding_id", sa.String(length=36), sa.ForeignKey("findings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("correlated_finding_id", sa.String(length=36), sa.ForeignKey("correlated_findings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("snapshot_id", sa.String(length=36), nullable=True),
        sa.Column("patch_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("agent_run_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="completed", nullable=False),
        sa.Column("outcome", sa.String(length=32), server_default="UNABLE_TO_VERIFY", nullable=False),
        sa.Column("gate_5_decision", sa.String(length=32), server_default="UNRESOLVED", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0.9", nullable=False),
        sa.Column("methodology", sa.String(length=128), server_default="source_transformation_sink", nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("source_transformation_sink_json", sa.Text(), nullable=True),
        sa.Column("scanner_comparison_json", sa.Text(), nullable=True),
        sa.Column("test_results_json", sa.Text(), nullable=True),
        sa.Column("regression_results_json", sa.Text(), nullable=True),
        sa.Column("remaining_evidence", sa.Text(), nullable=True),
        sa.Column("new_issues_json", sa.Text(), nullable=True),
        sa.Column("decision_reasons_json", sa.Text(), nullable=True),
        sa.Column("failed_conditions_json", sa.Text(), nullable=True),
        sa.Column("limitations", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index("ix_verification_runs_review_id", "verification_runs", ["review_id"])
    op.create_index("ix_verification_runs_remediation_run_id", "verification_runs", ["remediation_run_id"])
    op.create_index("ix_verification_runs_finding_id", "verification_runs", ["finding_id"])
    op.create_index("ix_verification_runs_correlated_finding_id", "verification_runs", ["correlated_finding_id"])
    op.create_index("ix_verification_runs_snapshot_id", "verification_runs", ["snapshot_id"])
    op.create_index("ix_verification_runs_agent_run_id", "verification_runs", ["agent_run_id"])
    op.create_index("ix_verification_runs_status", "verification_runs", ["status"])
    op.create_index("ix_verification_runs_outcome", "verification_runs", ["outcome"])
    op.create_index("ix_verification_runs_gate_5_decision", "verification_runs", ["gate_5_decision"])


def downgrade() -> None:
    op.drop_table("verification_runs")
    op.drop_index("ix_remediation_runs_gate_5_decision", table_name="remediation_runs")
    op.drop_column("remediation_runs", "gate_5_decision")

