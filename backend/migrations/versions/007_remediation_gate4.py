"""Add correlated_finding_id, snapshot_id, patch_version, risk_level, and gate_4_status to remediation_runs.

Revision ID: 007_remediation_gate4
Revises: 006_correlated_findings
Create Date: 2026-11-16

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "007_remediation_gate4"
down_revision: Union[str, None] = "006_correlated_findings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Allow finding_id to be nullable so a remediation can optionally attach purely to a correlated finding
    op.alter_column("remediation_runs", "finding_id", existing_type=sa.String(length=36), nullable=True)

    # Add columns for Sub-Phase 7.5
    op.add_column("remediation_runs", sa.Column("correlated_finding_id", sa.String(length=36), nullable=True))
    op.add_column("remediation_runs", sa.Column("snapshot_id", sa.String(length=36), nullable=True))
    op.add_column("remediation_runs", sa.Column("patch_version", sa.Integer(), server_default="1", nullable=False))
    op.add_column("remediation_runs", sa.Column("risk_level", sa.String(length=32), server_default="LOW", nullable=False))
    op.add_column("remediation_runs", sa.Column("gate_4_status", sa.String(length=32), server_default="PENDING", nullable=False))

    # Foreign key and indexes
    op.create_foreign_key(
        "fk_remediation_runs_correlated_finding_id",
        "remediation_runs",
        "correlated_findings",
        ["correlated_finding_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_remediation_runs_correlated_finding_id", "remediation_runs", ["correlated_finding_id"], unique=False)
    op.create_index("ix_remediation_runs_snapshot_id", "remediation_runs", ["snapshot_id"], unique=False)
    op.create_index("ix_remediation_runs_risk_level", "remediation_runs", ["risk_level"], unique=False)
    op.create_index("ix_remediation_runs_gate_4_status", "remediation_runs", ["gate_4_status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_remediation_runs_gate_4_status", table_name="remediation_runs")
    op.drop_index("ix_remediation_runs_risk_level", table_name="remediation_runs")
    op.drop_index("ix_remediation_runs_snapshot_id", table_name="remediation_runs")
    op.drop_index("ix_remediation_runs_correlated_finding_id", table_name="remediation_runs")
    op.drop_constraint("fk_remediation_runs_correlated_finding_id", "remediation_runs", type_="foreignkey")

    op.drop_column("remediation_runs", "gate_4_status")
    op.drop_column("remediation_runs", "risk_level")
    op.drop_column("remediation_runs", "patch_version")
    op.drop_column("remediation_runs", "snapshot_id")
    op.drop_column("remediation_runs", "correlated_finding_id")

    op.alter_column("remediation_runs", "finding_id", existing_type=sa.String(length=36), nullable=False)

