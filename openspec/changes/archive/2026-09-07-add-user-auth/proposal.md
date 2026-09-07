## Why

对话和文件接口目前完全开放，用户表与 MySQL 会话已经就位，但没有注册、登录，也没有请求级身份。需要先用用户名密码建账号、签发 JWT，再把除登录注册外的 API 锁上，让任意业务层都能取出当前用户，而不把 `user` 一层层往下传。

## What Changes

- 新增 `POST /auth/register` 与 `POST /auth/login`，请求体只有 `username` 和 `password`；注册写入现有 `users` 表，登录校验后签发 JWT
- 密码哈希后入库，不存明文
- **BREAKING**：除登录、注册、OpenAPI 文档和 CORS 预检外，所有已挂载路由必须带有效 `Authorization: Bearer` JWT，否则拒绝
- 鉴权中间件解开 token 后把身份写入请求级 `ContextVar`；业务层通过 `get_current_user()` 读取，中间层不必转发 `user`
- 运行时配置增加 JWT 密钥与过期时间；示例环境文件补上对应占位

## Capabilities

### New Capabilities
- `user-auth`: 用户名密码注册/登录、JWT 校验、请求级当前用户

### Modified Capabilities
- `runtime-config`: 启动快照增加 JWT 配置组，示例环境补上 JWT 占位名
- `file-upload`: `presign` / `complete` 必须携带有效 JWT

## Impact

- `src/memora_agent/api/auth/`：注册与登录路由
- `src/memora_agent/service/user_service.py`：按用户名查询与创建用户
- `src/memora_agent/core/`：JWT 配置、签发/验签、`ContextVar`、鉴权中间件
- `src/memora_agent/main.py`：挂载 auth 路由与鉴权中间件；启动时确保 `users` 表存在
- `src/memora_agent/schema/config.py`、`.example.env`、README：JWT 配置
- `pyproject.toml`：增加 JWT 与密码哈希依赖
- `tests/api/`：覆盖注册登录与未授权拒绝；现有 chat/files/CORS 测试补上 token
- 后台任务（如 `RagService.build_knowledge_base`）不在本次绑定用户；出请求边界后 ContextVar 不可用
