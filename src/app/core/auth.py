from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import config


@dataclass(frozen=True, slots=True)
class CurrentUser:
    id: int
    username: str


current_user_var: ContextVar[CurrentUser | None] = ContextVar(
    "current_user",
    default=None,
)


class TokenError(Exception):
    pass


def get_current_user() -> CurrentUser:
    user = current_user_var.get()
    if user is None:
        raise RuntimeError("当前请求没有登录用户")
    return user


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: int, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=config.jwt.expire_minutes)
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": expire,
    }
    return jwt.encode(payload, config.jwt.secret, algorithm="HS256")


def decode_access_token(token: str) -> CurrentUser:
    try:
        payload = jwt.decode(token, config.jwt.secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise TokenError("令牌无效或已过期") from exc

    sub = payload.get("sub")
    username = payload.get("username")
    if sub is None or not username:
        raise TokenError("令牌缺少身份声明")
    try:
        user_id = int(sub)
    except (TypeError, ValueError) as exc:
        raise TokenError("令牌身份声明无效") from exc
    return CurrentUser(id=user_id, username=str(username))
