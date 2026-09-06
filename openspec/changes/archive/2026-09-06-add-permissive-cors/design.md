## Context

动机见 `proposal.md`；行为见 `specs/http-cors/spec.md`。

现状：`main.py` 只创建 FastAPI 应用并挂载 `/chat` 与 `/files`，没有 CORS 中间件。前端开发源是 `http://localhost:5173`，本服务默认 `http://127.0.0.1:8000`。浏览器对 JSON POST 会先发 OPTIONS 预检，没有 CORS 头就会失败。

R2 桶 CORS 已在 `docs/r2-file-upload.md` 说明，属于 Cloudflare 控制台，不是本服务策略。本次只解决「浏览器 → FastAPI」。

## Goals / Non-Goals

**Goals:**

- 用最少代码让任意前端源站能调用本服务的全部方法。
- 不增加第三方依赖，不改现有路由协议。

**Non-Goals:**

- 不按环境维护 Origin 白名单。
- 不配置 R2 桶 CORS。
- 不引入 cookie / `allow_credentials=True`。

## Decisions

### 1. 在 `main.py` 挂内置 `CORSMiddleware`，通配放宽

- **选择**：

  ```
  allow_origins=["*"]
  allow_methods=["*"]
  allow_headers=["*"]
  allow_credentials=False
  ```

- **原因**：产品明确要求先放宽；Starlette 中间件已随 FastAPI 提供，不必新依赖。`allow_credentials=True` 与 `origins=["*"]` 不能同时用；本服务当前也不靠 cookie。
- **备选**：`CORS_ORIGINS` 环境变量——这次不需要。按路由分别配 CORS——文件和聊天都会被前端跨源打到，入口统一挂更简单。

### 2. 不加新配置项，不改 `.example.env`

- **选择**：策略写死在 `main.py`。
- **原因**：放宽后没有要填的源站列表；再加环境变量是空配置。
- **备选**：以后要收紧再加白名单，那时再改这一处即可。

### 3. 用 TestClient 覆盖预检，不引入真实浏览器

- **选择**：对 `/files/presign`（或任意已挂路由）发带 `Origin` 与 `Access-Control-Request-Method` 的 `OPTIONS`，断言预检成功且回了允许头。
- **原因**：现有文件测试已用 `TestClient`；CORS 是响应头行为，不必上浏览器。
- **备选**：只手测 localhost——回归时容易漏。

## Risks / Trade-offs

- [任意网站都可从浏览器调用本服务] → 当前文件接口无鉴权，这是明确接受的宽松策略；以后加登录或收紧 Origin 再改中间件参数。
- [通配 Origin 不能带 cookie] → 保持 `allow_credentials=False`；前端用 Bearer 头不受影响。
- [R2 PUT 仍可能被桶 CORS 拦截] → 文档已有控制台步骤；本变更不处理。

## Migration Plan

- 在 `main.py` 增加中间件后重启 uvicorn 即可。
- 回滚：删掉中间件，行为回到无 CORS。
- 无数据迁移。
