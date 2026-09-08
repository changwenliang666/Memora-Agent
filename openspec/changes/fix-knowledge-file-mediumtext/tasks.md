## 1. 模型列类型

- [x] 1.1 把 `KnowledgeFile` 的 `markdown` / `plain_text` / `ocr_text` 从 SQLAlchemy `Text` 改为 `sqlalchemy.dialects.mysql.MEDIUMTEXT`，可空不变。执行 `tests/db/test_knowledge_file.py`：三列类型名为 `MEDIUMTEXT` 且仍可空

## 2. 已有表升列

- [x] 2.1 在 `main.py` lifespan 的 `create_all` 之后执行 `ALTER TABLE knowledge_files MODIFY markdown/plain_text/ocr_text MEDIUMTEXT NULL`，失败只打日志不阻断启动。用代码或启动日志确认语句存在且与 `create_all` 同一 try 块

## 3. 回归

- [x] 3.1 执行 `uv run pytest tests/db/test_knowledge_file.py tests/service/test_rag_service.py`，确认入库测试仍通过、未改 MinerU / 切分路径
