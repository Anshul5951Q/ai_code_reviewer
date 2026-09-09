"""Add analysis_jobs and repository_snapshots tables.

Revision ID: 002_analysis_tables
Revises: 001_initial_schema
Create Date: 2026-09-09

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "002_analysis_tables"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. analysis_jobs table
    op.create_table(
        "analysis_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("current_stage", sa.String(length=64), nullable=True),
        sa.Column("progress", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("files_total", sa.Integer(), server_default="0", nullable=False),
        sa.Column("files_processed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analysis_jobs_review_id", "analysis_jobs", ["review_id"])
    op.create_index("ix_analysis_jobs_status", "analysis_jobs", ["status"])

    # 2. repository_snapshots table
    op.create_table(
        "repository_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("commit_sha", sa.String(length=40), nullable=False),
        sa.Column("branch", sa.String(length=255), nullable=False),
        sa.Column("total_files", sa.Integer(), server_default="0", nullable=False),
        sa.Column("source_files", sa.Integer(), server_default="0", nullable=False),
        sa.Column("test_files", sa.Integer(), server_default="0", nullable=False),
        sa.Column("config_files", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_lines", sa.Integer(), server_default="0", nullable=False),
        sa.Column("languages", sa.Text(), nullable=True),
        sa.Column("frameworks", sa.Text(), nullable=True),
        sa.Column("dependencies", sa.Text(), nullable=True),
        sa.Column("structure", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("review_id"),
    )
    op.create_index("ix_repository_snapshots_review_id", "repository_snapshots", ["review_id"])
    op.create_index("ix_repository_snapshots_commit_sha", "repository_snapshots", ["commit_sha"])


def downgrade() -> None:
    op.drop_index("ix_repository_snapshots_commit_sha", table_name="repository_snapshots")
    op.drop_index("ix_repository_snapshots_review_id", table_name="repository_snapshots")
    op.drop_table("repository_snapshots")

    op.drop_index("ix_analysis_jobs_status", table_name="analysis_jobs")
    op.drop_index("ix_analysis_jobs_review_id", table_name="analysis_jobs")
    op.drop_table("analysis_jobs")
