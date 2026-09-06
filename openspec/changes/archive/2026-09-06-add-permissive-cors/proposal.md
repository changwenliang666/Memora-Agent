## Why

浏览器前端要从另一源站调用本服务的 `/files/presign` 与 `/files/complete`。当前 FastAPI 未配置 CORS，预检请求会被浏览器拦截，上传链路无法接通。

## What Changes

- 在应用入口挂上 CORS 中间件，允许任意源站、任意 HTTP 方法访问本服务。
- 允许浏览器预检所需的常见请求头（至少包含 `Content-Type`、`Authorization`）。
- 不使用 cookie 凭证模式，以便与通配源站 `*` 兼容。

不包含：按环境收紧源站白名单、R2 桶 CORS（仍在 Cloudflare 控制台配置）、改动 `/files` 或 `/chat` 的业务协议。

## Capabilities

### New Capabilities

- `http-cors`: 浏览器跨源访问本服务时，任意 Origin、任意方法均被允许。

### Modified Capabilities

- 无。现有 `file-upload` 协议不变。

## Impact

- FastAPI 入口 `main.py` 增加 CORS 中间件。
- 依赖：使用 Starlette / FastAPI 内置 `CORSMiddleware`，不新增第三方包。
- 无破坏性业务变更：现有路由行为不变，仅补跨源响应头。
