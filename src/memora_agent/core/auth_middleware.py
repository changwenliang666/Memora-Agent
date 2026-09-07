from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from memora_agent.core.auth import (
    TokenError,
    current_user_var,
    decode_access_token,
)
from memora_agent.schema.bizcode import BizCode
from memora_agent.schema.response import ResponseStructure

_PUBLIC_PATHS = frozenset(
    {
        "/openapi.json",
        "/docs",
        "/redoc",
        "/auth/register",
        "/auth/login",
    }
)
_PUBLIC_PREFIXES = ("/docs", "/redoc")


def _is_public(request: Request) -> bool:
    if request.method == "OPTIONS":
        return True
    path = request.url.path
    if path in _PUBLIC_PATHS:
        return True
    return path.startswith(_PUBLIC_PREFIXES)


def _unauthorized() -> JSONResponse:
    body = ResponseStructure(
        code=BizCode.UNAUTHORIZED.value,
        message="未登录或令牌无效",
    )
    return JSONResponse(status_code=401, content=body.model_dump())


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if _is_public(request):
            return await call_next(request)

        header = request.headers.get("authorization") or request.headers.get(
            "Authorization"
        )
        if header is None or not header.lower().startswith("bearer "):
            return _unauthorized()

        token = header[7:].strip()
        if not token:
            return _unauthorized()

        try:
            user = decode_access_token(token)
        except TokenError:
            return _unauthorized()

        reset = current_user_var.set(user)
        try:
            return await call_next(request)
        finally:
            current_user_var.reset(reset)
