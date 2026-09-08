## Why

入库成功后写入 `knowledge_files` 的 markdown 会被截断，库里往往只剩文档开头一截（例如只看到 `#员工企业制度`）。根因是三列正文用了 SQLAlchemy `Text`，落到 MySQL 是 `TEXT`（约 64KB），装不下 MinerU 转出来的长文。需要立刻改列类型，已入库的不完整行只能改类型后重新上传。

## What Changes

- `knowledge_files.markdown`、`plain_text`、`ocr_text` 从 MySQL `TEXT` 改为 `MEDIUMTEXT`（约 16MB）
- 模型定义与已存在的表都要改到 `MEDIUMTEXT`；项目没有 alembic，启动时 `create_all` 不会改已有列，需要额外 `ALTER`
- 不改解析、切分、向量入库路径

## Capabilities

### New Capabilities

- （无）

### Modified Capabilities

- `knowledge-ingest`: 成功落库的知识文件正文必须完整保存，三列正文使用 `MEDIUMTEXT`，不得因 `TEXT` 64KB 上限截断

## Impact

- `src/memora_agent/db/models/knowledge_file.py`：三列改为 MySQL `MEDIUMTEXT`
- 启动建表逻辑（`main.py` lifespan）：对已存在的表执行 `ALTER ... MODIFY ... MEDIUMTEXT`
- `tests/db/test_knowledge_file.py`：断言列类型
- 已截断的历史行不会自动补全，需重新入库
