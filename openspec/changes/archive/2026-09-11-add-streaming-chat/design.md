## Context

`POST /chat/stream` 已挂路由并要求 JWT，但 handler 仍返回占位 JSON；注释里的 `provider.astream` 不走 Agent 工具循环。`Agent.run_loop` 用 `ainvoke` 整段返回，`AgentConfig.stream` 未使用。`ChatRequest` 只有 `message` / `provider_type` / `model_name`。`/chat/agent` 写死演示历史，本次不改那条路由。动机见 proposal.md。

约束：继续用现有 `LLMProvider`、`Tools`（天气/时间）、`AuthMiddleware`。Redis 已在开发栈（`compose.yaml` 的 `redis:7-alpine`、`RedisConfig`），但应用层还没有 Redis 客户端。前端用 `POST` + Bearer，不能改成 `EventSource` GET。

## Goals / Non-Goals

**Goals:**

- Agent 文本增量经 SSE 到达客户端；工具循环留在服务端
- 断线后凭 `message_id` 从 Redis 续传，不重新生成
- 请求校验失败不进入流；流开始后的失败用 `message.failed` 收尾
- 用假模型与假 Redis 测协议，再用真实调用确认是否真流式

**Non-Goals:**

- 不改鉴权中间件，除非验证确认响应被整段缓冲
- 不推 `tool.*` 事件（v1 前端不需要）
- 不做可翻页的服务端会话历史；Redis 只是带 TTL 的在生成缓冲
- 不改 `/chat/agent`、不注册 RAG 检索工具

## Decisions

### 1. SSE 用 `event:` 命名 + 各事件自己的载荷

每帧 `event: <name>` + `data: {json}`。v1 只有 `message.started` / `message.delta` / `message.completed` / `message.failed`。以后加工具、引用只新增 event 名，旧前端忽略不认识的 event。响应头带 `Cache-Control: no-cache` 和 `X-Accel-Buffering: no`。

载荷：

- `message.started`：`{"message_id": "..."}`
- `message.delta`：`{"seq": 1, "content": "根"}`
- `message.completed`：`{}`
- `message.failed`：`{"message": "..."}`

备选：每帧统一信封 `{id, message_id, role, status, parts[]}`。否决：v1 只出文本，这套块协议偏重；事件名 + 载荷更贴「问答流」。

备选：GET + `EventSource`。否决：不能方便地带 Bearer。

### 2. `message_id` + 每事件 `seq`，恢复不重新生成

`message.started` 给本轮 `message_id`。`message.delta` 的 `seq` 单调递增。断线重连是「接着收同一轮」，不是再跑一次模型；同一句提问重新生成既费 token 又改答案。

### 3. Agent 增加 `run_stream`，路由只负责把事件写成 SSE

`run_stream` 为 async 生成器：`history` + 本轮 `HumanMessage` 进入现有循环；每轮 `astream`，把 `AIMessageChunk` 累加成完整 `AIMessage` 再入历史。仅当 chunk 含非空文本 `content` 时产出 `message.delta`；`tool_call_chunks` 不产出。有 `tool_calls` 则 `ainvoke` 工具（与 `run_loop` 相同），静音若干时间后进入下一轮；无工具则产出 `message.completed` 并结束。`max_round` 耗尽仍无最终文本则产出 `message.failed`。

`run_loop` 保持非流式，`/chat/agent` 继续调用它。

备选：把 `run_loop` 改成内部生成器再包装。否决：要动 `/chat/agent` 的返回时序；分开两个入口更小。

### 4. 在生成的那轮事件缓存进 Redis（状态 hash + 事件 list，带 TTL）

每轮：`HSET chat:msg:{message_id}` 存 `status` / `created_at` / `model` / 最终 `content`；`RPUSH chat:msg:{message_id}:events` 存每帧 JSON，`seq` 取 `LLEN`。终态写 `completed`/`failed`。两个 key 都 `EXPIRE`（默认 10 分钟）。这是「可续传缓冲」，不是会话历史；Redis 重启或过期即不可恢复，客户端重问。

备选：Redis Stream（XADD/XRANGE）。否决：断线重放不需要消费组和逐条 id，list 更直白。

备选：进程内存。否决：进程重启即丢、多实例不可共享，且用户已选 Redis。

### 5. 重连走独立 `GET /chat/messages/{message_id}?from_seq=N`

不复用 `POST /chat/stream`：后者是「新提问」，重连不是。GET 同样过 Bearer。仍生成中：`LRANGE from_seq..` 回放后继续推新帧；已结束：回放剩余后直接发终态；key 不存在或过期：JSON 404，不开流。同一路由返回 SSE 或 JSON，按消息是否存在决定。

备选：`POST /chat/stream` 带 `Last-Event-ID`。否决：混淆「恢复」与「新提问」，容易误触发再生成。

### 6. 校验在开流之前用 JSON 拒绝

缺 `provider_type` / `model_name` 或 `LLMProvider` 构造失败时返回 JSON 错误，不开 `StreamingResponse`。JWT 失败仍由现有中间件 401。流已经开始后的异常（模型中断、工具抛错）才发 `message.failed`，且不再发 `completed`。

### 7. `ChatRequest` 增加可选 `history`，服务端无会话

`history` 默认空列表，元素为 `{role: "user"|"assistant", content: str}`，转成 `HumanMessage` / `AIMessage`。省略或空列表时不注入任何演示历史。本请求不写库；Redis 只存本轮事件，不构成可翻历史。`/rule`、`/intent`、`/agent` 忽略该字段。

### 8. 假流式：先不动 `AuthMiddleware`

Starlette `BaseHTTPMiddleware` 可能缓冲 body，使 SSE 变成一次整段返回。本张按「不影响」落地：中间件保持原样。用带间隔的假模型或真实模型观察帧是否陆续到达；若整段到达，再把鉴权改成不包裹 response body 的 ASGI 中间件（或在路由内验 token）。自动化 `TestClient` 往往自己缓冲，不能当作真流式的唯一证据。

## Risks / Trade-offs

- [调工具期间前端无帧] → 接受；v1 协议只要文本，暂停后下一轮文本再推。
- [BaseHTTPMiddleware 假流式] → 先实现再验证；确认后再改中间件，避免预防性重构。
- [Redis 重启 / key 过期后无法恢复] → 接受；定位为带 TTL 的缓冲，前端重问，不做持久会话。
- [客户端伪造/截断 history] → 接受；服务端无会话时这是调用方责任。
- [工具结果过大撑上下文] → 沿用现有天气/时间工具，体量可忽略；RAG 工具不在本张。
- [max_round 用尽无最终回复] → 发 `message.failed`，避免连接挂起。

## Migration Plan

1. 扩展 `ChatRequest` 与 SSE 事件 schema；实现 `Agent.run_stream`
2. 新增 Redis 事件缓存与 `redis` 依赖；接入 `POST /chat/stream`
3. 新增 `GET /chat/messages/{message_id}` 重连端点
4. 用假模型/假 Redis 测帧顺序、`seq`、`from_seq` 与 404；联调确认是否真流式，必要时再改中间件
5. 更新 README；回滚时去掉两个流式路由与 Redis 缓存即可，无数据迁移

## Open Questions

无。事件名、`message_id`/`seq`、Redis 状态+list、独立 GET 重连、TTL 10 分钟、可选 history、中间件后置修复、与 RAG 分 change，均已按讨论定下来。
