## 1. Schema

- [x] 1.1 在 `ChatRequest` 增加可选 `history`（默认空列表，元素 `role` 为 `user`/`assistant` 且带 `content`）；补齐 SSE 事件载荷模型：`message.started`（`message_id`）、`message.delta`（`seq` + `content`）、`message.completed`、`message.failed`（`message`）。执行 `uv run pytest tests/core/test_chat_schema.py`，补「省略 history 为空」「非法 role 被拒绝」「delta 必须带 seq/content」用例并通过
- [x] 1.2 确认 `/rule`、`/intent`、`/agent` 请求体仍只依赖现有字段，忽略 `history` 时行为不变。用现有相关测试或一次手动请求确认无 422

## 2. Redis 事件缓存

- [x] 2.1 `pyproject.toml` 增加 `redis`，实现 async Redis 客户端封装（连接、按 key 读写）。执行 `uv run pytest tests/core` 确认现有配置与客户端构造不破坏
- [x] 2.2 实现按 `message_id` 的事件缓存：`HSET chat:msg:{id}` 状态（`status`/`created_at`/`model`/最终 `content`），`RPUSH chat:msg:{id}:events` 每帧 JSON，`seq` 取 `LLEN`；两 key 写后 `EXPIRE`（默认 600s）。用 fakeredis 或注入的假客户端断言：写入后 `LRANGE` 有序、`TTL > 0`

## 3. Agent 流式循环

- [x] 3.1 在 `Agent` 增加 `run_stream`：按 `history` 还原消息后追加本轮用户输入；每轮 `astream` 累加 `AIMessageChunk`；非空文本 `content` 产出 `message.delta`（带 `seq`），不把 `tool_call_chunks` 当文本；无工具时产出 `message.completed`。用假模型断言帧名与递增 `seq`
- [x] 3.2 假模型先返回 `tool_calls` 再返回文本时：服务端执行现有 `execute_tool`，对外仍只有后续文本的 `message.delta` 和最终 `message.completed`，无 tool 事件。用天气或时间工具的假调用验证
- [x] 3.3 流已经开始后模型或工具抛错时产出 `message.failed` 且不再 `completed`；`max_round` 耗尽无最终文本同样 `failed`。用假模型验证这两条

## 4. HTTP 入口

- [x] 4.1 实现 `POST /chat/stream`：缺 `provider_type`/`model_name` 或 Provider 构造失败时返回 JSON 错误且 `content-type` 不是 `text/event-stream`；成功则 `StreamingResponse`（`Cache-Control: no-cache`、`X-Accel-Buffering: no`），首帧 `message.started` 含 `message_id`，事件同时写入 Redis 缓存。用带 JWT 的 `TestClient` 断言 content-type 与首帧字段
- [x] 4.2 无 `history` 时不注入演示对话；SSE 体为 `event: message.*` + `data: {json}\n\n`，且无硬编码「大伟」类历史。用假 Agent/模型断言
- [x] 4.3 实现 `GET /chat/messages/{message_id}?from_seq=N`：消息仍在生成时回放 `seq>N` 的事件后继续推；已结束则回放剩余后发终态；不存在或过期返回 JSON 404 且不开流。用假缓存覆盖这三种
- [x] 4.4 无 Bearer 访问两个路由仍为现有 401 JSON，不开流。执行或扩展 `tests/api` 中未授权用例确认

## 5. 自动化测试

- [x] 5.1 新增 `tests/api/test_chat_stream.py`：覆盖无 token、缺模型参数、纯文本流（`started`/`delta`/`completed` 顺序与 `seq`）、带 `history` 会进入 Agent 历史、重连回放与 404。执行 `uv run pytest tests/api/test_chat_stream.py tests/core/test_chat_schema.py` 通过
- [x] 5.2 确认 `/chat/agent` 未改：OpenAPI 路径断言仍含该路由。执行 `uv run pytest tests/api/test_files.py` 中路径相关用例通过

## 6. 真流式验证

- [x] 6.1 对运行中的服务（不要只靠会缓冲的 `TestClient`）用带间隔的假模型或真实模型观察：delta 应陆续到达，而不是结束时一次性出现；并验证断线后 `GET /chat/messages/{id}?from_seq=N` 能续上。记录结果
- [x] 6.2 仅当 6.1 确认为假流式时，再改鉴权使其不缓冲 response body（ASGI 中间件或路由内验 token），并重复 6.1 直到帧按时到达。若 6.1 已是真流式则跳过本项并注明

## 7. 文档

- [x] 7.1 更新 README：`/chat/stream` 改为可用；写明 JWT、请求字段、事件名（`message.started`/`delta`/`completed`/`failed`）、`seq`、可选 `history`、`GET /chat/messages/{id}?from_seq=` 与 TTL 语义。通读与实现一致后执行 `uv run pytest tests/api/test_chat_stream.py tests/core/test_chat_schema.py` 与 `openspec validate add-streaming-chat --type change --strict`
