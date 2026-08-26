#!/usr/bin/env python3
"""Pull every product from the local MySQL mirror and log each one — an ops visibility
tool, not an API endpoint (GET /api/v1/products already serves that; this is for
watching the structured logs directly, e.g. after a sync run).

Usage: uv run python scripts/list_products.py
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.db.models import Product
from app.db.session import SessionLocal
from app.logging_config import setup_logging

logger = logging.getLogger("scripts.list_products")


def main() -> None:
    setup_logging(get_settings().log_level)

    session = SessionLocal()
    try:
        products = session.query(Product).order_by(Product.busy_code).all()
        for p in products:
            logger.info(
                "product busy_code=%s name=%r price=%s unit=%s item_group=%s "
                "tracks_stock=%s is_active=%s woo_product_id=%s",
                p.busy_code,
                p.name,
                p.price,
                p.unit,
                p.item_group,
                p.tracks_stock,
                p.is_active,
                p.woo_product_id,
            )
        active = sum(1 for p in products if p.is_active)
        logger.info(
            "product listing done: total=%d active=%d inactive=%d",
            len(products),
            active,
            len(products) - active,
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
