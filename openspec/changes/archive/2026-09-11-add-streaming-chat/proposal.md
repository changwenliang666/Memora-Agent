## Why

`POST /chat/stream` 仍是占位：注释掉的 SSE 没有走现有 Agent，前端无法边生成边展示，断线后也没有可重连的标识。`POST /chat/agent` 能跑工具循环，但整段 JSON 返回，且夹着写死的演示历史，不能当正式聊天入口。需要先接上可续传的流式聊天并验证真流式，RAG 检索另开 change。

## What Changes

- 落地 `POST /chat/stream`：鉴权后用现有 Agent 跑工具循环，以 SSE 把模型文本增量推给前端
- SSE 用事件名 + 载荷：`message.started`、`message.delta`、`message.completed`、`message.failed`。v1 只发这四种，不推工具事件
- 每个 `message.delta` 带单调 `seq`；首帧 `message.started` 给出本轮 `message_id`
- 正在生成的这一轮事件写入 Redis（`chat:msg:{message_id}` 状态 hash + `:events` 列表，带 TTL），供断线恢复
- 新增 `GET /chat/messages/{message_id}?from_seq=N`：重连后从 N 之后继续以 SSE 推送；消息不存在或已过期返回 JSON 404
- 请求继续带 `message`、`provider_type`、`model_name`；可选 `history` 由客户端传入。服务端不建会话库
- Agent 增加流式循环（`astream` 拼出完整 AIMessage 后再决定是否调工具）；`/chat/agent` 本次不改
- 鉴权中间件先不动。联调若发现响应被缓冲成假流式，再单独修中间件
- 不接入 RAG 检索图、不改工具清单（仍为现有天气/时间）
- 新增 `redis` 客户端依赖

## Capabilities

### New Capabilities
- `streaming-chat`: 已登录用户通过 SSE 流式接收 Agent 文本回复，断线后可凭消息 id 续传

### Modified Capabilities
- （无）现有 `user-auth` 已要求 `/chat/*` 带 JWT；`GET /chat/messages/{id}` 沿用同一鉴权，不改鉴权规则

## Impact

- `src/app/agent/agent.py`：增加流式循环，文本 delta 向外产出
- `src/app/api/chat/chat.py`：实现 `POST /chat/stream` 与 `GET /chat/messages/{message_id}` 的 `StreamingResponse`
- `src/app/schema/chat.py`：流式请求增加可选 `history`；补齐 SSE 事件载荷形状
- 新增聊天消息事件缓存（Redis），TTL 兜底；`pyproject.toml` 增加 `redis`
- `tests/`：覆盖请求校验、缺模型参数拒绝、事件名/seq、`from_seq` 回放与 404；用假模型和假 Redis，避免打真实 LLM / Redis
- `README.md`：把 `/chat/stream` 从占位改成可用说明，写清事件名、seq 与重连端点
- 不改 `AuthMiddleware`（除非测出假流式）、不改 `/chat/agent`、不改 Qdrant / 入库 / Tools
