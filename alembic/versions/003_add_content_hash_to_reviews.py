"""Add content_hash column to reviews table.

Revision ID: 003
Revises: 002
Create Date: 2026-10-06 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op  # type: ignore[attr-defined]

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "reviews",
        sa.Column("content_hash", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_reviews_profile_id_content_hash",
        "reviews",
        ["profile_id", "content_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_reviews_profile_id_content_hash", table_name="reviews")
    op.drop_column("reviews", "content_hash")
