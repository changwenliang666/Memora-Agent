## Context

`POST /auth/register` 与 `POST /auth/login` 成功时已经返回 `ResponseStructure`（`code` / `message` / `data`），`BizCode` 目前只有 `SUCCESS = 0`。重复用户名走 HTTP 409 `{"detail": "用户名已存在"}`，错误口令走 HTTP 401 `{"detail": "用户名或密码错误"}`。`files/complete` 成功也用同一信封，失败仍是 `HTTPException`；本次不改那些接口。动机见 `proposal.md`。

`ResponseStructure.data` 现在是必填泛型字段，失败响应没有载荷，需要对 `data` 允许为空。

## Goals / Non-Goals

**Goals:**

- 登录/注册的业务成功和业务失败都走 `ResponseStructure`
- 用 `BizCode` 区分成功、用户名已存在、用户名或密码错误
- 前端只看信封里的 `code`，不再解析 `detail`

**Non-Goals:**

- 不改 JWT 中间件对受保护路由的 401
- 不改 `/files`、`/chat`、Pydantic 422
- 不引入全局异常处理器去包装所有 HTTPException

## Decisions

### 1. 业务结果 HTTP 200，用 `code` 区分成败

登录/注册在用户名冲突或口令错误时仍返回 HTTP 200，把结果写在 `ResponseStructure.code`。前端按 `code == 0` 判断成功。

备选：保持 409/401，只把 body 换成信封。否决：调用方仍要同时看 HTTP 状态和 `code`，和「都走 ResponseStructure」的目标不一致。

缺字段、密码过短等请求体不合法仍由 FastAPI 返回 422，不在本次包装。

### 2. 在 `BizCode` 增加两个认证码

```
SUCCESS = 0
USERNAME_ALREADY_EXISTS = 1001
INVALID_CREDENTIALS = 1002
```

1000 段留给认证。`INVALID_CREDENTIALS` 同时覆盖「用户不存在」和「密码错误」，不泄露用户名是否存在。

备选：失败都用同一个非 0 码。否决：前端无法区分「换个用户名」和「核对密码」。

### 3. 失败时 `data` 为 null

`ResponseStructure.data` 改为可选，默认 `None`。成功路径继续填 `RegisterData` / `LoginData`。失败不返回空对象里的 `token` 字段，避免前端误读。

接口直接 `return ResponseStructure(...)`，不再 `raise HTTPException`。

### 4. `to_dict` 与 `code` 类型

`code` 继续存 `int`（`BizCode.xxx.value`）。现有 `to_dict` 访问 `self.code.value` 在 `code` 已是 int 时会出错；本次若改到该路径则一并改成直接输出 `self.code`。接口主要走 Pydantic 序列化，不依赖 `to_dict` 也能绿，但仍应修掉。

## Risks / Trade-offs

- [原先按 409/401 判断的客户端会失效] → 这是有意的协议变更；测试改为断言信封 `code`。
- [HTTP 200 表示业务失败] → 约定写进 README 登录注册说明；中间件 401 不变，避免和「没带 token」混淆。
- [只改 auth 两条，其它接口仍混用 detail] → 接受；按用户范围只处理登录注册。

## Migration Plan

1. 扩展 `BizCode`，让 `ResponseStructure.data` 可空，修好 `to_dict`
2. 注册/登录改为返回信封，更新 `tests/api/test_auth.py`
3. README 补一句：这两条接口看 `code`，不要看 HTTP 4xx
4. 回滚：恢复 `HTTPException` 409/401；已发出的客户端需同时兼容两种信封

## Open Questions

无。HTTP 200 + 业务码、失败 `data` 为 null、不包装 422 与中间件 401，已按本次范围定下来。
