## 1. 数据模型与 schema 对齐

- [x] 1.1 给 `KnowledgeFile` 增加 `status`、`error_message`、`content_type`、`started_at`、`finished_at`、`queue_wait_ms`、`duration_ms`，以及 `(user_id, created_at)` 索引。执行 `tests/db/test_knowledge_file.py`：新列齐全，`status` 非空
- [x] 1.2 扩展 `knowledge_files_align_statements`：缺列则 ADD，`status` 默认 `'done'`，`content_type` 默认 `''`。执行 `tests/db/test_schema.py` 覆盖缺列与已齐列两种情况

## 2. 文件记录服务与状态流转

- [x] 2.1 新增 knowledge-file 服务：complete 插入 `pending`；`mark_processing` 仅在 `pending`/`processing` 时首次写入 `started_at` 与 `queue_wait_ms`；`mark_done` / `mark_failed` 写终态、`finished_at`、`duration_ms` 并回填正文。单测覆盖首次进入 processing、redeliver 不改 started_at、空 chunk 标 done、失败不插新行

## 3. 队列发布与 worker

- [x] 3.1 用 aio-pika 封装 durable exchange/queue（`memora.knowledge` / `memora.knowledge.ingest`），publish 消息含 `knowledge_file_id`、`object_key`、`filename`、`user_id`、`username`、`size`，不含 download URL。单测用假 channel 断言 routing key 与 payload
- [x] 3.2 `build_knowledge_base` 改为更新已有行：消费时 `presign_get`；成功 webhook 仍发；失败写 `failed` + 短文案。更新 `tests/service/test_rag_service.py` 建库用例
- [x] 3.3 新增 `python -m app.worker`：prefetch=1，手动 ack；`done`/`failed` 跳过；`pending`/`processing` 开工。单测用假消息覆盖 skip 与 ack-on-failure

## 4. HTTP：complete / 列表 / 详情

- [x] 4.1 `POST /files/complete` 插 pending、入队、响应带 `id` 与 `status`；入队失败则该行 `failed` 并 HTTP 500。去掉 BackgroundTasks。更新 `tests/api/test_files.py`
- [x] 4.2 `GET /files`：当前用户倒序，limit 默认 20 最大 100，offset 默认 0，摘要不含正文。`GET /files/{id}` 非本人 404。接口测试覆盖隔离与分页

## 5. 回归

- [x] 5.1 执行 `uv run pytest tests/db/test_knowledge_file.py tests/db/test_schema.py tests/service/test_rag_service.py tests/api/test_files.py` 全部通过
