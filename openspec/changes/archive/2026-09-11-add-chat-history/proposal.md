## Why

`add-streaming-chat` 让 Agent 能流式回复，但每轮是无状态的：客户端要么自己背 `history`，要么断线后只能靠 Redis 短期缓冲续传。要翻历史、跨设备继续同一段对话、以及以后压缩长上下文，需要把消息持久化到已拉通的 MySQL。压缩不在本次范围。

## What Changes

- 新增 `conversations` 与 `messages` 两张表（`create_all` 建表 + `align_*` 兼容旧库），按用户归属
- `POST /chat/stream` 请求体增加可选 `conversation_id`：传入则把本轮写进该会话；不传则服务端新建会话
- 用户消息在完成校验后立即写入 `messages`；助手整段回复在流式 `completed` 时一次性写入，并更新会话的 `updated_at` / `message_count` / 标题
- `message.started` 帧同时给出 `message_id`（Redis 续传用）与 `conversation_id`
- 新增只读历史接口：`GET /conversations`（当前用户会话列表）、`GET /conversations/{id}/messages`（分页历史），均需 JWT
- 不传 `conversation_id` 且带 `history` 时仍按无状态跑（`add-streaming-chat` 已支持），本次不改该路径
- Redis 仍是断线续传缓冲（TTL），MySQL 是历史层；两者分层，不互相替代
- 不做消息压缩 / 总结；这是有了历史表之后的后续功能

## Capabilities

### New Capabilities
- `chat-history`: 会话与消息的 MySQL 持久化、按用户读取历史

### Modified Capabilities
- `streaming-chat`: `POST /chat/stream` 支持可选 `conversation_id` 并把完成的轮次写入历史

## Impact

- `src/app/db/models/`：新增 `Conversation`、`Message` 模型并在 `db/models/__init__.py` 导出
- `src/app/db/schema.py`：新增会话/消息表的 `align_*`
- `src/app/main.py`：lifespan 建表包含新表
- `src/app/service/`：新增会话/消息读写服务（按用户隔离）
- `src/app/api/chat/chat.py`：`POST /chat/stream` 接 `conversation_id` 并在完成时落库；新增历史 GET 路由
- `src/app/schema/chat.py`：请求/响应补会话与消息字段
- `tests/`：模型建表、按用户隔离、完成时写库、历史分页；用假模型避免真实 LLM
- `README.md`：会话与历史接口说明
- 依赖：不新增第三方包（沿用现有 SQLAlchemy/asyncmy）；不改变 Redis 依赖
