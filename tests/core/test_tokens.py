from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.auth import (
    CurrentUser,
    TokenError,
    create_access_token,
    current_user_var,
    decode_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.core.config import config


def test_create_and_decode_access_token() -> None:
    token = create_access_token(42, "dawei")
    user = decode_access_token(token)
    assert user.id == 42
    assert user.username == "dawei"


def test_expired_token_is_rejected() -> None:
    token = jwt.encode(
        {
            "sub": "1",
            "username": "dawei",
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        },
        config.jwt.secret,
        algorithm="HS256",
    )
    with pytest.raises(TokenError):
        decode_access_token(token)


def test_token_signed_with_wrong_secret_is_rejected() -> None:
    token = jwt.encode(
        {
            "sub": "1",
            "username": "dawei",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        "not-the-configured-secret-min-32b",
        algorithm="HS256",
    )
    with pytest.raises(TokenError):
        decode_access_token(token)


def test_get_current_user_reads_context_without_parameters() -> None:
    expected = CurrentUser(id=7, username="dawei")

    def nested_service() -> CurrentUser:
        return get_current_user()

    reset = current_user_var.set(expected)
    try:
        assert nested_service() == expected
    finally:
        current_user_var.reset(reset)


def test_get_current_user_without_context_raises() -> None:
    with pytest.raises(RuntimeError, match="没有登录用户"):
        get_current_user()


def test_hash_password_is_not_plaintext() -> None:
    hashed = hash_password("secret12")
    assert hashed != "secret12"
    assert verify_password("secret12", hashed)
    assert not verify_password("wrong-password", hashed)
