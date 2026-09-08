## Why

入库现在对所有文件都走 MinerU，图片进不了白名单，markdown 里的图也不会进向量。需要按类型分流解析，把图文都变成可检索文本，并在建库成功后留下一份可查的文件记录。

## What Changes

- 上传白名单扩展为 `.pdf`、`.docx`、`.txt`、`.md`、`.png`、`.jpg`、`.jpeg`
- **BREAKING**：`object_key` 从 `{uuid}-{filename}` 改为每个文件一个前缀文件夹 `{uuid}/{filename}`（可再加 `R2_KEY_PREFIX`）
- 建库按扩展名分流：pdf/docx 走 MinerU，再把 markdown 配图交给现有视觉模型后入库；txt/md 直接读文本；图片直接走视觉模型
- MinerU 配图在 OCR 之后拷到同一文件前缀的 `images/` 下，长期存在自己的桶里
- 向量入库成功后写 MySQL 表 `knowledge_files`：上传人、原始 `object_key`、大小、文件名、配图 keys、markdown / 纯文本 / 视觉识别正文
- HTTP `complete` 仍不读桶、不在请求内写库；后台任务在请求结束前取出 `user_id` 再传入

## Capabilities

### New Capabilities
- `knowledge-ingest`: 按文件类型解析、视觉识别配图、切分向量入库，并在成功后落文件记录

### Modified Capabilities
- `file-upload`: 扩展允许的扩展名与 content-type；签发的 `object_key` 落在每文件独立前缀下

## Impact

- `src/memora_agent/storage/validate.py`、`storage/r2.py`：白名单与 key 形状；R2 增加按 key 写入对象
- `src/memora_agent/api/files/files.py`、`service/rag_service.py`：complete 传入用户与元数据；建库按类型分流并调用 `OcrService`
- `src/memora_agent/db/models/`：新增 `knowledge_files`（启动 `create_all`）
- `tests/storage/test_validate.py`、`tests/storage/test_r2.py`、`tests/api/test_files.py`：png 从拒绝改为接受；覆盖新 key 形状
- `docs/r2-file-upload.md`、`openspec/specs/file-upload/spec.md`：白名单与 key 约定
- 无新依赖；下载用已有 `httpx`，视觉模型用已有 `OcrService`
- **兼容**：已按旧 `{uuid}-{filename}` 上传的对象本次不迁移；新签发的 key 带 `/`
