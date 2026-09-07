## Why

登录和注册的成功响应已经包在 `ResponseStructure` 里，失败却走 FastAPI 的 `{"detail": ...}`，前端无法用同一套 `code` / `message` / `data` 解析。业务码也只有 `SUCCESS`，重复用户名和错误口令没有可区分的 code。

## What Changes

- **BREAKING**：`POST /auth/register` 与 `POST /auth/login` 的业务失败不再返回 HTTP 4xx 的 `detail` 信封，一律返回 `ResponseStructure`（`code`、`message`、`data`）
- 在 `BizCode` 中补上注册/登录所需的非成功码（用户名已存在、用户名或密码错误）
- 成功路径继续 `code = SUCCESS`，`data` 为现有注册/登录载荷；失败路径 `data` 为空，且不包含密码或 JWT
- 本次不改鉴权中间件、文件接口、Pydantic 422 的响应形状

## Capabilities

### New Capabilities

### Modified Capabilities
- `user-auth`: 注册与登录的失败响应从 HTTP 客户端错误改为带业务码的统一信封

## Impact

- `src/memora_agent/schema/bizcode.py`：新增登录注册业务码
- `src/memora_agent/schema/response.py`：失败时允许 `data` 为空
- `src/memora_agent/api/auth/auth.py`：去掉 `HTTPException`，成功失败都返回 `ResponseStructure`
- `tests/api/test_auth.py`：按信封和业务码断言，不再断言 409 / 401
- 不改 JWT 中间件对受保护路由的 401
