## 1. Middleware

- [x] 1.1 在 `src/memora_agent/main.py` 挂载 FastAPI / Starlette 内置 `CORSMiddleware`：`allow_origins=["*"]`、`allow_methods=["*"]`、`allow_headers=["*"]`、`allow_credentials=False`；确认未新增第三方依赖，且 `/chat`、`/files` 路由仍然挂在同一应用上

## 2. Tests

- [x] 2.1 增加跨源预检测试：对 `/files/presign` 发带 `Origin` 与 `Access-Control-Request-Method` 的 `OPTIONS`，断言预检成功并返回允许任意源 / 方法所需的 CORS 头
- [x] 2.2 增加跨源 POST 头断言：带任意 `Origin` 请求已挂载路由时，响应包含 CORS 允许头；执行 `uv run pytest` 全部通过，且现有 `/files` 用例仍然绿色
