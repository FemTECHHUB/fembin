"""add last_full_at to sync_state — records when the last FULL re-pull happened per entity,
so the "reconcile" products sync strategy can decide when the next full refresh is due.

Revision ID: 0a1b2c3d4e5f
Revises: c90dd2905fbc
Create Date: 2026-09-05

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0a1b2c3d4e5f"
down_revision: str | Sequence[str] | None = "c90dd2905fbc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "sync_state",
        sa.Column("last_full_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("sync_state", "last_full_at")
