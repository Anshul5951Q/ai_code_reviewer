"""Initial database schema for repositories, reviews, and findings.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-09-09

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. repositories table
    op.create_table(
        "repositories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=512), nullable=False),
        sa.Column("owner", sa.String(length=255), nullable=False),
        sa.Column("default_branch", sa.String(length=255), server_default="main", nullable=False),
        sa.Column("visibility", sa.String(length=32), server_default="private", nullable=False),
        sa.Column("language", sa.String(length=128), nullable=True),
        sa.Column("github_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("full_name"),
        sa.UniqueConstraint("github_id"),
    )
    op.create_index("ix_repositories_full_name", "repositories", ["full_name"])
    op.create_index("ix_repositories_owner", "repositories", ["owner"])
    op.create_index("ix_repositories_github_id", "repositories", ["github_id"])

    # 2. reviews table
    op.create_table(
        "reviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("repository_id", sa.String(length=36), nullable=False),
        sa.Column("commit_sha", sa.String(length=40), nullable=False),
        sa.Column("branch", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=True),
        sa.Column("security_score", sa.Float(), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reviews_repository_id", "reviews", ["repository_id"])
    op.create_index("ix_reviews_status", "reviews", ["status"])
    op.create_index("ix_reviews_commit_sha", "reviews", ["commit_sha"])

    # 3. findings table
    op.create_table(
        "findings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("category", sa.String(length=128), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("file_path", sa.String(length=1024), nullable=True),
        sa.Column("line_number", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="open", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_findings_review_id", "findings", ["review_id"])
    op.create_index("ix_findings_category", "findings", ["category"])
    op.create_index("ix_findings_severity", "findings", ["severity"])
    op.create_index("ix_findings_status", "findings", ["status"])


def downgrade() -> None:
    op.drop_index("ix_findings_status", table_name="findings")
    op.drop_index("ix_findings_severity", table_name="findings")
    op.drop_index("ix_findings_category", table_name="findings")
    op.drop_index("ix_findings_review_id", table_name="findings")
    op.drop_table("findings")

    op.drop_index("ix_reviews_commit_sha", table_name="reviews")
    op.drop_index("ix_reviews_status", table_name="reviews")
    op.drop_index("ix_reviews_repository_id", table_name="reviews")
    op.drop_table("reviews")

    op.drop_index("ix_repositories_github_id", table_name="repositories")
    op.drop_index("ix_repositories_owner", table_name="repositories")
    op.drop_index("ix_repositories_full_name", table_name="repositories")
    op.drop_table("repositories")
