"""woocommerce tracking: woo_synced_name, woo_hidden on products

BUSY's Stamp doesn't advance on item edits (CLAUDE.md §8), so the only way to catch a
BUSY rename is to compare against what we last pushed — a per-product `woo_synced_name`.
`woo_hidden` records that a deactivated BUSY product was already set to `private` on
WooCommerce, so the sync doesn't re-issue the same status update every pass.

Revision ID: b3e9f71a2c4d
Revises: 0a1b2c3d4e5f
Create Date: 2026-09-05

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3e9f71a2c4d"
down_revision: str | Sequence[str] | None = "0a1b2c3d4e5f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("products", sa.Column("woo_synced_name", sa.String(length=255), nullable=True))
    op.add_column(
        "products", sa.Column("woo_hidden", sa.Boolean(), nullable=False, server_default="0")
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("products", "woo_hidden")
    op.drop_column("products", "woo_synced_name")
