## Why

`POST /files/complete` 用 FastAPI `BackgroundTasks` 在 API 进程里同步跑入库，MinerU 最长约 20 分钟；进程 reload 或崩溃会丢任务，失败后 MySQL 没有任何行可查、无法轮询。需要真正入队，并用状态机把排队/处理/成功/失败和耗时暴露给前端。

## What Changes

- **BREAKING**：`complete` 在请求内插入一条 `knowledge_files` 记录（`status=pending`），不再等到向量写入成功才插行；失败改为把同一行标为 `failed` 并写入 `error_message`。
- **BREAKING**：`complete` 响应的 `FileInfo` 增加 `id`、`status`；入库改为发布 RabbitMQ 消息，API 进程不再调用 `build_knowledge_base`。
- 独立 worker 消费队列：现场签发 GET URL（消息不携带会过期的 `download_url`），驱动现有解析/切块/向量化；成功回填正文并标 `done`，失败标 `failed`。
- `KnowledgeFile` 增加状态、失败文案、`content_type`、开始/结束时间、`queue_wait_ms`、`duration_ms`。
- 新增 `GET /files`（当前用户列表，limit/offset）和 `GET /files/{id}`（非本人 404）；两者只返回摘要，不含 markdown / plain_text / ocr_results。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `knowledge-ingest`: 入库改为队列驱动的状态机；文件行在 complete 时插入；向量成功后更新而非插入；记录排队等待与处理耗时。
- `file-upload`: complete 持久化 pending 行并入队；新增列表与按 id 查询摘要。

## Impact

- 代码：`api/files/files.py`、`service/rag_service.py`、`db/models/knowledge_file.py`、`db/schema.py`；新增队列发布/消费与 worker 入口（`aio-pika` 已在依赖中）。
- API：`POST /files/complete` 响应字段增加；新增两个 GET。
- 数据：已有成功行在加列时默认 `status=done`；新行由 complete 写 `pending`。
- 运行：本地除 uvicorn 外需再启 worker；RabbitMQ 已在 compose 中。
- 测试：complete 不再断言直接调用建库；覆盖入队、状态流转、列表/详情隔离、耗时字段。
- 不做：幂等 hash、删除同步、指数退避/DLQ、分阶段耗时、md 配图 OCR、失败重试接口。
