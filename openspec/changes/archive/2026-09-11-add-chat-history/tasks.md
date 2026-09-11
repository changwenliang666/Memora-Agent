## 1. 数据模型

- [x] 1.1 新增 `Conversation` 与 `Message` 模型并在 `db/models/__init__.py` 导出：`conversations(id,user_id,title,message_count,created_at,updated_at)`，`messages(id,conversation_id,role,content,seq,created_at)`，`messages` 带 `(conversation_id,seq)` 唯一约束。执行 `uv run pytest tests/core` 确认导入与建表模型无误
- [x] 1.2 在 `db/schema.py` 增加两张表的 `align_*`，并在 `main.py` lifespan 的 `create_all` 覆盖到新表。启动应用（或对齐测试）确认表存在、索引存在

## 2. Service 层（按用户隔离）

- [x] 2.1 新增会话/消息服务：建会话（取首条问题做 title）、写 user 消息、完成时写 assistant 整段并更新会话 `updated_at`/`message_count`。用注入的 session 或测试库断言写入顺序与 seq 递增
- [x] 2.2 读路径：`list_conversations(user_id)` 按 `updated_at` 倒序、`get_messages(user_id, conversation_id, limit/offset)` 按 `seq` 正序；别人的会话返回空。用两个用户的数据断言隔离生效

## 3. 流式落库

- [x] 3.1 `POST /chat/stream` 请求体加可选 `conversation_id`：校验归属（非本人 404/拒绝）；传入则从会话历史构造 Agent 输入，忽略 body `history`；不传则新建会话。用假模型 + 测试库断言新建/复用分支
- [x] 3.2 流开始前写 user 消息；`message.started` 帧同时带 `message_id` 与 `conversation_id`；`completed` 时写 assistant 整段，`failed` 不写 assistant。用假模型断言三种落库时机
- [x] 3.3 不带 `conversation_id` 但带 `history` 时仍无状态跑且不建会话（沿用 `add-streaming-chat` 行为）。用假模型断言不产生新会话

## 4. 历史接口

- [x] 4.1 `GET /conversations`：当前用户会话列表，按 `updated_at` 倒序，需 JWT。带两个用户的数据断言只回自己的
- [x] 4.2 `GET /conversations/{id}/messages`：按 `seq` 正序分页；非本人会话返回错误不暴露消息。断言顺序、分页与越权

## 5. 测试与文档

- [x] 5.1 新增/扩展测试：建表、归属隔离、完成时写库、历史分页；执行 `uv run pytest tests/` 通过
- [x] 5.2 更新 README：会话与历史接口、`conversation_id` 与 `message_id` 的分工、Redis 续传 vs MySQL 历史分层。执行 `openspec validate add-chat-history --type change --strict` 通过
