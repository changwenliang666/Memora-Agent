## Context

`add-streaming-chat` 提供 `POST /chat/stream`（事件经 Redis 短期缓冲供断线续传）与可选 `history`。本轮对话是无状态的：服务端不留可翻的历史。MySQL / SQLAlchemy 已拉通（`users`、`knowledge_files` 用 `create_all` 建表 + `align_*` 兼容旧库 + service 层按 `user_id` 隔离）。压缩是后续功能，不在本次。

## Goals / Non-Goals

**Goals:**

- 会话与消息两张表，按用户归属；`create_all` 建表 + `align_*` 兼容
- `POST /chat/stream` 支持可选 `conversation_id`；完成的轮次落库
- 只读历史接口：会话列表 + 单会话分页消息
- Redis（断线续传缓冲）与 MySQL（历史）分层，互不替代

**Non-Goals:**

- 不做消息压缩 / 总结
- 不做会话重命名 / 删除 / 分享
- 不改无状态 `history` 路径的行为
- 不引入新第三方依赖（沿用 SQLAlchemy / asyncmy）

## Decisions

### 1. 会话是第一类实体，两张表

`conversations`（id、user_id、title、message_count、created_at、updated_at）+ `messages`（id、conversation_id、role、content、seq、created_at）。索引：会话 `(user_id, updated_at)`，消息 `(conversation_id, seq)`。

备选：只存 message 靠 user_id 串。否决：没有会话实体就谈不上列表、标题、按会话分页，后续压缩也要挂在会话上。

### 2. 完成时写整条，不逐 token 写 MySQL

用户消息在流开始前写入；助手回复在 `message.completed` 时一次性写入整段。逐 token 写库是 Redis 缓冲层的事，MySQL 只存成形的轮次。失败（`message.failed`）不写半成品 assistant 行。

### 3. `message_id`（续传）与 `conversation_id`（历史）分开

`message.started` 同时带两者。`message_id` 对应 Redis 里这一轮的可续传事件流；`conversation_id` 对应 MySQL 会话。一个管断线，一个管历史，不复用同一个 id。

### 4. 服务端从会话取历史，不靠前端背 `history`

传了 `conversation_id` 就从该会话已存消息构造 Agent 历史，忽略 body 里的 `history`。不传 `conversation_id` 才退回无状态 `history`（`add-streaming-chat` 已有行为）。

### 5. 沿用现有建表与隔离模式

`main.py` lifespan `create_all` + 新表的 `align_*`；service 层方法都带 `user_id` 过滤（参考 `KnowledgeFileService.get_for_user` / `list_for_user`），别人的 id 返回空，接口层 404。

## Risks / Trade-offs

- [并发同会话写 seq 冲突] → 单用户单会话串行发，`(conversation_id, seq)` 唯一约束兜底。
- [长会话上下文膨胀] → 本张只存不压；压缩作为后续挂在会话上的功能。
- [失败轮次只留 user 消息] → 接受；assistant 半成品不入库。
- [align_* 只处理已知旧库形态] → 与 `knowledge_files` 一致，开发用，生产再引迁移工具。

## Migration Plan

1. 加两张模型 + `align_*` + lifespan 建表
2. service 层：建会话、写消息、按用户读
3. `POST /chat/stream` 接 `conversation_id` 并完成时落库；首帧带 `conversation_id`
4. 历史 GET 路由；测试 + README
5. 回滚：删两张表与路由即可，Redis 续传不受影响

## Open Questions

无。模型、写入时机、id 分层、隔离与建表方式已按讨论定下来；压缩明确留后续。
