## 1. 配置与依赖

- [x] 1.1 在 `pyproject.toml` 增加 `pyjwt` 与 `bcrypt`，`uv lock` 后确认 `uv run python -c "import jwt, bcrypt"` 成功
- [x] 1.2 在 `schema/config.py` 增加 `JwtConfig`（secret、expire_minutes），`Config` 增加 `load_jwt()` 与 `jwt` 组；`.example.env` 增加 `JWT_SECRET`、`JWT_EXPIRE_MINUTES` 占位。执行 `tests/core/test_r2_config.py` 确认快照含 `jwt` 且导入不因缺 R2/MinerU 崩溃

## 2. 身份与中间件

- [x] 2.1 实现 `CurrentUser`、`ContextVar`、`get_current_user()`、JWT 签发/验签；用单元测试覆盖：合法 token 解出 id/username、过期或错密钥失败、`get_current_user()` 在 set 之后可读且不查库
- [x] 2.2 实现鉴权中间件：白名单为注册、登录、`/docs`、`/redoc`、`/openapi.json`、`OPTIONS`；其余路径校验 Bearer。在 `main.py` 先挂该中间件再挂 CORS。用接口测试确认无 token 访问 `/files/presign` 为 4xx、错误 token 为 4xx、`/openapi.json` 无 token 可访问

## 3. 用户写入与 auth 接口

- [x] 3.1 落地 `UserService.create_user` / `get_user_by_username`：创建时 bcrypt 哈希，不写明文；lifespan 里异步 `create_all`。用服务测试或接口测试确认库中密码不是明文
- [x] 3.2 新增 `POST /auth/register` 与 `POST /auth/login`（仅 username、password），挂到 app 且不要求 JWT。测试：新用户注册成功且响应无密码；重复用户名 4xx；正确登录返回 JWT；错密码 4xx 且无 token

## 4. 现有接口与文档

- [x] 4.1 更新 `tests/api/test_files.py` 与 `tests/api/test_cors.py`：受保护请求带有效 JWT；无 token 的 presign/complete 断言 4xx。执行这些测试确认通过
- [x] 4.2 更新 README：说明注册登录、Bearer 鉴权、`JWT_SECRET`。通读能对上 `.example.env` 与 `/auth` 路由
- [x] 4.3 执行 `uv run pytest tests/api tests/core/test_r2_config.py`，确认配置、CORS、files、auth 相关用例全绿
