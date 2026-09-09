## Context

现状见 `proposal.md`。`KnowledgeFile` 三列正文现在是 SQLAlchemy `Text`，在 MySQL 上就是 `TEXT`（65535 字节）。MinerU 转出的 markdown 经常超过这个上限，INSERT 时被截成开头一段。项目没有 alembic，启动只跑 `create_all`，改模型不会改已有列。上一版 ingest 设计写过 LONGTEXT，实现没用上；这次按产品要求用 `MEDIUMTEXT`。

## Goals / Non-Goals

**Goals:**

- 模型和新表、旧表都落到 MySQL `MEDIUMTEXT`
- 启动后已有库不必手工改列

**Non-Goals:**

- 不引入 alembic
- 不回填已经截断的历史行
- 不改 MinerU / OCR / 切分 / Qdrant

## Decisions

### 1. 三列都用 `MEDIUMTEXT`，不用 `LONGTEXT`

`MEDIUMTEXT` 上限约 16MB，够一篇带图链的制度文档。`LONGTEXT`（4GB）超出当前需要。上一版设计写 LONGTEXT，这次明确改成 `MEDIUMTEXT`。

备选：只改 `markdown`。否决：`plain_text` / `ocr_text` 同一类正文，同样会被 `TEXT` 截断。

### 2. 模型用 `sqlalchemy.dialects.mysql.MEDIUMTEXT`

`KnowledgeFile.markdown` / `plain_text` / `ocr_text` 换成该类型，可空不变。新库 `create_all` 直接出 `MEDIUMTEXT`。

备选：`Text().with_variant(...)`。否决：本项目只跑 MySQL，方言类型更直。

### 3. 已有表在 lifespan 里 `ALTER`

`create_all` 之后对 `knowledge_files` 执行：

```sql
ALTER TABLE knowledge_files
  MODIFY markdown MEDIUMTEXT NULL,
  MODIFY plain_text MEDIUMTEXT NULL,
  MODIFY ocr_text MEDIUMTEXT NULL
```

和现有建表一样包在 try/except。列已经是 `MEDIUMTEXT` 时这句是空操作。

备选：文档里让人手工 ALTER。否决：本地和部署都会漏。

### 4. 截断行不自动修复

改列只放大容量，已经写入的残缺字符串不会变完整。需要重新走 complete / 入库。

## Risks / Trade-offs

- [已截断行仍残缺] → 不回填；改列后重新上传同一文件。
- [lifespan ALTER 失败] → 打日志不阻断启动；新表仍靠模型类型。
- [超过 16MB 的正文] → 接受；再大应拆文件，不上 `LONGTEXT`。

## Migration Plan

1. 改模型三列为 `MEDIUMTEXT`，补列类型测试
2. lifespan 增加上述 `ALTER`
3. 重启服务让旧表升列
4. 对已截断文件重新入库
5. 回滚：把三列改回 `TEXT`（会再次截断，不建议）

## Open Questions

无。列类型、三列一起改、启动 ALTER、不回填，已按讨论定下来。
