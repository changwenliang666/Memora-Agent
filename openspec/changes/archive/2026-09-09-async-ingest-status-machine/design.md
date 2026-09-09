## Context

See proposal.md for motivation. Today `POST /files/complete` calls `RagService.build_knowledge_base` via FastAPI `BackgroundTasks`. `KnowledgeFile` is inserted only after Qdrant `COMPLETED`. RabbitMQ is already in compose and `RabbitMQConfig`; `aio-pika` is already a dependency. There is no alembic; schema changes go through `create_all` plus `align_knowledge_files_schema`. Complete currently passes a short-lived `presign_get` URL into ingest; that URL can expire if work is queued.

## Goals / Non-Goals

**Goals:**
- Move ingest execution into a separate consumer process with durable publish.
- Persist a row at complete time so status and timing can be queried.
- Keep `prepare_ingest` / split / embed / figure OCR behavior unchanged.

**Non-Goals:**
- Outbox, DLQ, exponential backoff, content-hash idempotency, delete-sync, per-stage timings, retry HTTP API.

## Decisions

1. **Status lives on `knowledge_files`, not a second jobs table.** The file list is the status machine. Alternative: `ingest_jobs` + success-only `KnowledgeFile` would preserve the old "no row until success" spec but force every query to join.

2. **Separate worker process (`python -m app.worker`), not a FastAPI lifespan consumer.** `--reload` would kill in-flight MinerU jobs. Alternative: in-process consumer is simpler locally but couples API restarts to ingest.

3. **Use aio-pika, not Celery.** Ingest is already async (SQLAlchemy async, OCR, embedding). Celery is sync-first. aio-pika is already listed in `pyproject.toml`.

4. **Queue topology:** durable direct exchange `memora.knowledge`, durable queue `memora.knowledge.ingest`, routing key `ingest`, `prefetch=1`. Message body: `knowledge_file_id`, `object_key`, `filename`, `user_id`, `username`, `size`. Worker calls `presign_get` at consume time.

5. **Ack after a terminal DB write.** Business failure (`failed` row) is acked, not requeued. Crash without ack redelivers. If status is already `done`/`failed`, ack and skip. If `pending`/`processing`, run ingest; only the first `pending`/`processing` → `processing` transition writes `started_at` and `queue_wait_ms`. RabbitMQ `consumer_timeout` must exceed MinerU's 1200s (set 40 minutes on the queue).

6. **Insert then publish.** If publish fails after insert, mark the row `failed` with a public enqueue error and return HTTP 500. Dual-write outbox is deferred.

7. **Existing rows migrate to `status='done'`.** Align `ADD COLUMN` defaults: `status` default `'done'` (every current row was a successful insert), `content_type` default `''`. New inserts set `pending` and the declared content type explicitly.

8. **List/detail omit bodies.** `GET /files` returns `{ items, total }` and `GET /files/{id}` returns a summary. `total` is the owner's full count, independent of `limit`/`offset`. Pagination: `limit` default 20 max 100, `offset` default 0. Other users' ids → 404. Index `(user_id, created_at)`.

9. **`build_knowledge_base` updates the existing row.** Signature gains `knowledge_file_id`. Empty chunks still `done`. Success webhook unchanged; no failure webhook this change.

## Risks / Trade-offs

- [API 与 worker 双写] → 先插行再发布；发布失败立刻标 `failed` 并 500，避免永久 `pending`。
- [预签名 URL 过期] → 消息不带 URL，消费时重签。
- [processing 卡死且已 ack] → 本次不扫超时；靠手动 ack + 足够长的 `consumer_timeout`。
- [旧行 content_type 为空] → 列表允许空字符串，前端可回退文件名后缀。

## Migration Plan

1. 部署含新列的模型与 `align_knowledge_files_schema`（启动时 ALTER）。
2. 先启 worker，再发带队列的 API，避免 pending 无人消费。
3. 回滚：停 worker、恢复 complete 走 BackgroundTasks 会留下新列，可忽略；不要删列以免丢失状态。

## Open Questions

（无）
