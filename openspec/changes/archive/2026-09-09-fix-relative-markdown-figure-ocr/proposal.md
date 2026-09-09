## Why

MinerU 转出的 Markdown 配图有两种地址：可在线访问的 `http(s)` URL，以及结果包内的相对路径（例如 `![](images/<hash>.jpg)`）。现有入库只按 URL 下载并交给视觉模型，相对路径会失败并被当成 SKIP，于是 `ocr_results` 为空。相对路径对应的字节其实在同一次转换的 zip/`images` 里，取出来规范化后应交回现有识别与拷贝流程。真实 PDF 已经踩中第二种格式，需要立刻补上这条支路。

## What Changes

- 配图按地址形态分流：绝对 `http(s)` / `data:` 继续走现有「视觉识别 → KEEP 则拷 R2」流程，不改 KEEP/SKIP 规则
- 相对路径先从同一次转换结果中取出对应图像字节，规范化成现有流程能消费的形态（data URI + 原字节拷贝），再交给同一套后续逻辑
- PDF/DOCX 转换必须同时保留 Markdown 和配图字节；只取 loader 的 `page_content` 会丢掉相对路径对应的资源
- 落库 `markdown` 仍保留转换器原文；修好的是 `ocr_results`、`image_keys` 和嵌入文本
- 不改 HTTP 契约、表结构、独立图片路径、txt/md 路径

## Capabilities

### New Capabilities

### Modified Capabilities

- `knowledge-ingest`: Markdown 配图允许两种地址；相对路径必须先解析成可识别资源，再按与在线 URL 相同的规则做视觉识别和拷贝

## Impact

- `src/app/service/rag_service.py`：转换出口带出配图字节；`replace_images_with_ocr` 前增加相对路径解析，后续 KEEP/SKIP/拷贝复用现逻辑
- `tests/service/test_rag_service.py`：覆盖相对路径与 https 两种地址，且都进入同一套 OCR/拷贝断言
- 依赖：用已有 `mineru` SDK（`langchain-mineru` 带入的 `mineru-open-sdk`）读取 `ExtractResult.images`；可不新增顶层依赖
- 无 HTTP / 表结构变化；已入库的空 `ocr_results` 行不回填，需重新上传
