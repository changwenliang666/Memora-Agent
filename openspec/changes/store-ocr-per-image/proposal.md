## Why

`knowledge_files.ocr_text` 把多张配图的识别结果用空行拼成一段字符串。事后无法按图回查、也无法和 `image_keys` 对齐；某一张失败时只留下一段空白，分不清是哪张图。入库已经按图逐张调用视觉模型，落库却把结构丢掉了。

## What Changes

- **BREAKING**：`ocr_text`（可空 `MEDIUMTEXT`）改为 `ocr_results`（JSON 数组）。每张被识别的图一条记录，至少包含对应的对象 key 与该图文本；无 OCR 时为空数组 `[]`
- 独立图片（png/jpg/jpeg）存一条，`image_key` 为源文件 `object_key`
- PDF/DOCX 配图按 Markdown 出现顺序各存一条，与拷贝到 R2 的配图对应；单张 OCR 失败仍保留该条，文本为空字符串
- 切块嵌入仍把 OCR 文字内联进待嵌入文本，不改检索路径
- 不新增文件详情 API；不引入图片子表

## Capabilities

### New Capabilities

### Modified Capabilities

- `knowledge-ingest`: 知识文件记录中的视觉识别结果从「一整段拼接字符串」改为「按图一条的 JSON 列表」

## Impact

- `src/memora_agent/db/models/knowledge_file.py`：列名与类型
- `src/memora_agent/service/rag_service.py`：`PreparedIngest` / `ImageOcrReplacement` / `save_knowledge_file` 停止拼接落库
- `src/memora_agent/main.py`：启动时的列变更（去掉对 `ocr_text` 的 `MEDIUMTEXT` 修改）
- `tests/db/test_knowledge_file.py`、`tests/service/test_rag_service.py`
- 无新依赖、无 HTTP 契约变化
- 已写入的 `ocr_text` 拼接字符串不迁移；开发期表可重建
