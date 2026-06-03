"""Merge two 0026 heads: rating response triage and activity token usage.

Both ``0026_add_rating_response`` (PR #308, ratings admin response) and
``0026_add_token_usage`` (this branch, admin Activity tab token/cost
columns) declare ``0025_merge_0024_heads`` as their ``down_revision``.
This is the established sibling-migration pattern used by the
``0024_*`` pair merged by ``0025_merge_0024_heads``.

This revision is a no-op merge point so ``alembic upgrade head`` has a
single linear path to follow on environments that pull both changes.

Revision ID: 0027_merge_0026_heads
Revises: 0026_add_rating_response, 0026_add_token_usage
Create Date: 2026-05-28
"""

revision = "0027_merge_0026_heads"
down_revision = ("0026_add_rating_response", "0026_add_token_usage")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
