## Why

`RagService.prepare_ingest` 用五元组按位置返回「切块嵌入用的文本」和「落库用的正文 / 配图」，调用处写成 `embed_text, markdown, plain_text, ocr_text, image_keys`。这几个名字都像「一段文本」，顺序记错就会把 MinerU 原文拿去嵌入、或把 OCR 结果当成 markdown 存库。文件里还有 `sessions`、`replaced`、`embedding` 这类对不上含义的局部名，不熟悉流程的人读不懂主链路在干什么。

## What Changes

- 把 `prepare_ingest` 的五元组改成带字段名的结果对象，字段把「给向量用」和「给 MySQL 用」分开
- 把 `replace_markdown_images` 的两元组同样改成命名结果，避免 `replaced` / `ocr_text` 靠位置解包
- 重命名会误导的局部变量和少数方法名（例如 `sessions`、`embedding: list[float]`），让 `build_knowledge_base` 读起来就是：准备材料 → 切块 → 向量化 → 写 Qdrant → 落库
- 同步改 `tests/service/test_rag_service.py`
- 不改解析分流、OCR、切块参数、Qdrant payload、HTTP API、`knowledge_files` 列名

## Capabilities

### New Capabilities

无。入库行为不变，不新增能力。

### Modified Capabilities

无。这是 `RagService` 内部命名与返回结构的重构，不改 `knowledge-ingest` 的需求。本 change 已设 `skip_specs: true`。

## Impact

- `src/memora_agent/service/rag_service.py`：结果类型、局部变量、误导性方法名
- `tests/service/test_rag_service.py`：解包改为读命名字段；若方法改名则改调用
- `files.py` 仍只调 `build_knowledge_base`，HTTP 契约不变
- `KnowledgeFile` 列名 `markdown` / `plain_text` / `ocr_text` 保持不变，避免表结构迁移
- 无新依赖；结果对象用现有 `dataclass` 风格（与 `CurrentUser` 一致）
