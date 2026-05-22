"""Add response columns to user_ratings for admin triage.

Adds four columns so superusers can record an action taken on each
rating directly in the same table:

- ``response_status``  : short string (open / acknowledged /
  info_needed / resolved / wontfix). Validated at the Pydantic layer,
  not by a DB CHECK constraint, so new values can be added without a
  migration.
- ``response_notes``   : optional free-text follow-up.
- ``responded_by_user_id`` : FK to ``users.id`` (SET NULL on delete) —
  who recorded the response.
- ``responded_at``     : timestamp the response was last edited.

An index on ``response_status`` supports the admin grid's filter.

Revision ID: 0026_add_response_to_user_ratings
Revises: 0025_merge_0024_heads
Create Date: 2026-05-20
"""

import sqlalchemy as sa

from alembic import op

revision = "0026_add_response_to_user_ratings"
down_revision = "0025_merge_0024_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_ratings",
        sa.Column("response_status", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "user_ratings",
        sa.Column("response_notes", sa.Text(), nullable=True),
    )
    op.add_column(
        "user_ratings",
        sa.Column(
            "responded_by_user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.add_column(
        "user_ratings",
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_user_ratings_responded_by_user_id",
        "user_ratings",
        "users",
        ["responded_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_user_ratings_response_status",
        "user_ratings",
        ["response_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_ratings_response_status", table_name="user_ratings")
    op.drop_constraint(
        "fk_user_ratings_responded_by_user_id",
        "user_ratings",
        type_="foreignkey",
    )
    op.drop_column("user_ratings", "responded_at")
    op.drop_column("user_ratings", "responded_by_user_id")
    op.drop_column("user_ratings", "response_notes")
    op.drop_column("user_ratings", "response_status")
