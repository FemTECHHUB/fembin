"""Password hashing — bcrypt directly (not passlib, which has had compatibility churn
with recent bcrypt releases)."""

import bcrypt


def hash_password(password: str) -> str:
    """One-way hash a plaintext password for storage; never store the plaintext itself."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Check a plaintext password against a stored hash from `hash_password`."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
