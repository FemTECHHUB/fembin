"""add resolved voucher series/prefix to material_centers

Revision ID: 27c5dba7056c
Revises: b3e9f71a2c4d
Create Date: 2026-09-07 04:02:54.713005

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "27c5dba7056c"
down_revision: str | Sequence[str] | None = "b3e9f71a2c4d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "material_centers", sa.Column("vch_series_name", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "material_centers", sa.Column("vch_no_prefix", sa.String(length=32), nullable=True)
    )
    op.add_column(
        "material_centers", sa.Column("vch_series_resolved_at", sa.DateTime(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("material_centers", "vch_series_resolved_at")
    op.drop_column("material_centers", "vch_no_prefix")
    op.drop_column("material_centers", "vch_series_name")
