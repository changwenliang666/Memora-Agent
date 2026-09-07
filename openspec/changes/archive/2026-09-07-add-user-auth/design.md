## Context

`User` 模型、`AsyncSessionLocal` 和 `UserService` 草稿已经存在，但接口未接、密码未哈希、进程启动也不建表。FastAPI 只有 CORS 中间件；`/chat` 与 `/files` 全部公开。Redis 已在开发栈里，应用代码未使用。动机见 `proposal.md`；对外行为见本 change 的 delta spec。

约束：配置继续走单一 `Config` 快照；存储层不引用 FastAPI；现有 files/CORS 测试用 `TestClient(app)` 直打接口，锁 API 后必须带 token。

## Goals / Non-Goals

**Goals:**

- 注册/登录只收用户名和密码，写入现有 MySQL `users` 表
- 无状态 JWT；请求内用 `ContextVar` 暴露当前用户
- 除白名单外全部路由鉴权；CORS 预检与 `/docs` 仍可匿名

**Non-Goals:**

- 不引入 refresh token、登出黑名单、Redis 会话
- 不把用户绑到 RAG 建库后台任务
- 不改 `User` 表结构（仍用自动 nickname）
- 不上 alembic；开发用启动时 `create_all`

## Decisions

### 1. 无状态 JWT，身份在 token 里

登录签发 HS256 JWT，claims：`sub`（user id 字符串）、`username`、`exp`。后续请求只验签，不查 `users`。

备选：JWT + Redis 会话。否决：应用还没有 Redis 客户端，本次不需要登出/踢人。

密钥与过期走 `config.jwt`：`JWT_SECRET`、`JWT_EXPIRE_MINUTES`（默认 10080，七天）。开发缺省密钥可以启动，生产必须换掉。依赖用 **PyJWT** 与 **bcrypt**。

### 2. 鉴权中间件 + ContextVar

Starlette 中间件白名单：`POST /auth/register`、`POST /auth/login`、`/docs`、`/redoc`、`/openapi.json`、`OPTIONS`。其余路径无有效 Bearer 则 401。

验签成功后 `current_user_var.set(CurrentUser(id, username))`，`finally` 里 reset。业务只调用 `get_current_user()`；HTTP handler 不必 `Depends`，中间层不必传 `user`。

备选：每个接口 `Depends`。否决：签名噪声大，且注入停在 handler，解决不了深层取值。

备选：只写 `request.state`。否决：service 没有 `Request`，仍要穿透传参。

CORS 必须包在鉴权外面：先 `add_middleware(AuthMiddleware)`，再保留现有 `CORSMiddleware`（后加的先跑），这样 OPTIONS 由 CORS 直接应答，不进鉴权。

### 3. 密码哈希与 UserService

`UserService.create_user` / `get_user_by_username` 落地；创建时 bcrypt 哈希。`password` 列 `String(100)` 放得下 bcrypt。登录用哈希比对，失败统一「用户名或密码错误」。用户名冲突按唯一约束返回 409。nickname 仍用模型默认值。

### 4. 启动建表

lifespan 里 `Base.metadata.create_all`（异步）。没有迁移工具，开发机靠这一步有 `users` 表。不改已有列。

### 5. 后台任务不读 ContextVar

`BackgroundTasks` 在中间件 reset 之后跑。本次建库仍不写 user id。以后要绑用户，在 `add_task` 时显式传入，而不是从 ContextVar 取。

## Risks / Trade-offs

- [无法服务端登出] → 等 token 过期；需要撤销时再加 Redis 黑名单。
- [被删用户的 token 在过期前仍可用] → 接受；避免每请求查库。
- [开发默认 JWT 密钥] → `.example.env` 写占位；生产必须覆盖。
- [create_all 不是正式迁移] → 够用当前单表；以后有多表变更再引入 alembic。
- [现有匿名 API 测试会 401] → 测试签发 token 或走登录，一并改 files/CORS 用例。

## Migration Plan

1. 加 JWT 配置、依赖、ContextVar 与中间件
2. 修好 UserService，挂注册/登录，lifespan 建表
3. 更新示例环境、README、接口测试
4. 回滚：去掉鉴权中间件和 `/auth` 路由；已写入的哈希密码保留，旧明文账号无法登录

## Open Questions

无。无状态 JWT、ContextVar、全站上锁（登录注册与文档除外）、后台任务不绑用户，已按讨论定下来。
