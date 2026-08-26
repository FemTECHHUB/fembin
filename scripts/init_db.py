#!/usr/bin/env python3
"""One-shot DB init: run all migrations, then seed the superadmin and first normal user.

Usage:
    uv run python scripts/init_db.py \
        --material-center-code 201 \
        --admin-username admin --admin-password 'Admin@123' --admin-full-name "Admin" \
        --user-username taiwo --user-password 'taiwo123' --user-full-name "Taiwo"
"""

import argparse
import logging
import subprocess
import sys

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import SessionLocal
from app.domain.auth.users import (
    DuplicateUsernameError,
    UnknownMaterialCenterError,
    create_user,
)
from app.logging_config import setup_logging

logger = logging.getLogger("scripts.init_db")


def run_migrations() -> None:
    """Run alembic upgrade head to bring the schema to the latest revision."""
    logger.info("running alembic migrations...")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error("alembic upgrade failed:\n%s", result.stderr)
        sys.exit(1)
    logger.info("migrations applied successfully")


def seed_user(
    session: Session,
    *,
    username: str,
    password: str,
    full_name: str,
    material_center_code: int,
    is_superadmin: bool,
) -> None:
    """Create a single user, logging success or specific failure."""
    label = "superadmin" if is_superadmin else "user"
    try:
        user = create_user(
            session,
            username=username,
            password=password,
            full_name=full_name,
            material_center_code=material_center_code,
            is_superadmin=is_superadmin,
        )
        logger.info("created %s: id=%s username=%s", label, user.id, user.username)
    except DuplicateUsernameError:
        logger.warning("%s username=%r already exists — skipping", label, username)
    except UnknownMaterialCenterError:
        logger.error(
            "material_center_code=%s does not exist or is inactive — "
            "run a catalog sync first, or choose an existing code",
            material_center_code,
        )
        sys.exit(1)


def main() -> None:
    setup_logging(get_settings().log_level)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--material-center-code", required=True, type=int)

    parser.add_argument("--admin-username", default="admin")
    parser.add_argument("--admin-password", default="Admin@123")
    parser.add_argument("--admin-full-name", default="Administrator")

    parser.add_argument("--user-username", default="taiwo")
    parser.add_argument("--user-password", default="taiwo123")
    parser.add_argument("--user-full-name", default="Taiwo")
    args = parser.parse_args()

    run_migrations()

    session = SessionLocal()
    try:
        seed_user(
            session,
            username=args.admin_username,
            password=args.admin_password,
            full_name=args.admin_full_name,
            material_center_code=args.material_center_code,
            is_superadmin=True,
        )
        seed_user(
            session,
            username=args.user_username,
            password=args.user_password,
            full_name=args.user_full_name,
            material_center_code=args.material_center_code,
            is_superadmin=False,
        )
    finally:
        session.close()

    logger.info("done — DB is initialized and seeded")


if __name__ == "__main__":
    main()
