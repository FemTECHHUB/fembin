#!/usr/bin/env python3
"""Create the first superadmin user — run this once, by hand, with shell/DB access.

POST /api/v1/auth/users requires an existing superadmin (locked down 2026-08-20), so
there is no HTTP path to create the very first one — that would be a self-service admin
hole. This script is that bootstrap step.

Usage:
    uv run python scripts/create_superadmin.py --username admin --password '...' \
        --full-name "Admin" --material-center-code 201
"""

import argparse
import logging
import sys

from app.config import get_settings
from app.db.session import SessionLocal
from app.domain.auth.users import (
    DuplicateUsernameError,
    UnknownMaterialCenterError,
    create_user,
)
from app.logging_config import setup_logging

logger = logging.getLogger("scripts.create_superadmin")


def main() -> None:
    setup_logging(get_settings().log_level)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--full-name", required=True)
    parser.add_argument("--material-center-code", required=True, type=int)
    args = parser.parse_args()

    session = SessionLocal()
    try:
        user = create_user(
            session,
            username=args.username,
            password=args.password,
            full_name=args.full_name,
            material_center_code=args.material_center_code,
            is_superadmin=True,
        )
    except DuplicateUsernameError:
        logger.error("username %r is already taken", args.username)
        sys.exit(1)
    except UnknownMaterialCenterError:
        logger.error(
            "material_center_code=%s does not match a known, active material center",
            args.material_center_code,
        )
        sys.exit(1)
    finally:
        session.close()

    logger.info("created superadmin id=%s username=%s", user.id, user.username)


if __name__ == "__main__":
    main()
