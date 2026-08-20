from app.domain.auth.passwords import hash_password, verify_password


def test_hash_password_does_not_store_plaintext() -> None:
    hashed = hash_password("correct-horse-battery-staple")
    assert hashed != "correct-horse-battery-staple"


def test_verify_password_accepts_the_right_password() -> None:
    hashed = hash_password("correct-horse-battery-staple")
    assert verify_password("correct-horse-battery-staple", hashed) is True


def test_verify_password_rejects_the_wrong_password() -> None:
    hashed = hash_password("correct-horse-battery-staple")
    assert verify_password("wrong-password", hashed) is False
