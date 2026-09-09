## Why

入库切分把 Markdown 当纯文本按换行和分号硬切，表格和代码块会被拆碎，检索拿到的是残标签和半句代码。同时 MinerU 配图一律 OCR 并落库，装饰图、Logo、占位 `![image]` 也会进向量和 `ocr_results`，污染检索。

## What Changes

- Markdown 形态文本（MinerU 产物和直接上传的 `.md`）改为结构感知切分：HTML `<table>`、Markdown 管道表、围栏代码（`` ``` `` / `~~~`）整块入库，允许超过 500 字；散文仍按 500/50 切
- 标题路径写入 chunk metadata，切分时不再覆盖 `h1` / `h2` / `h3`；标题切分不得把代码块里的 `#` 当成标题
- `.txt` 和独立上传的图片 OCR 结果仍走纯文本递归切，不按 Markdown 结构解析
- Markdown 配图在同一轮视觉调用里判别：无检索价值则不拷 R2、不写 `ocr_results`、不进 `image_keys`，并从嵌入稿删除该图片语法；有价值才识别并落库
- 独立上传的 png/jpg/jpeg 不判别、不跳过
- 切分从 `RagService` 抽出，OCR 抽图链路保留
- 不改 chunk_size / overlap 数值，不上新切分库，不拦独立图片，不改 HTTP API

## Capabilities

### New Capabilities

### Modified Capabilities

- `knowledge-ingest`: 切分必须保持表格和代码块完整；Markdown 配图仅在视觉模型判定有检索价值时才替换进嵌入稿并落库

## Impact

- `src/memora_agent/service/rag_service.py`：`split_text` 外移；`replace_images_with_ocr` 按 SKIP / 失败跳过拷贝与落库
- 新增切分模块（Markdown 装箱 + 纯文本递归切）
- `src/memora_agent/service/ocr_service.py`：提示词改为「SKIP 或可嵌入文本」
- `tests/service/test_rag_service.py` 及新的切分测试
- 无新依赖、无 HTTP 契约变化、无表结构变更
- `ocr_results` 不再与 Markdown 配图条数一一对应（无价值图和调用失败不再占空条）
