## 1. 转换同时留下 Markdown 和配图资源

- [x] 1.1 在 `src/app/service/rag_service.py` 的 PDF/DOCX 路径改用 `MinerU(token=...).extract(...)` 取代 `MinerULoader`（Loader 会丢掉 zip 里的图）：`formula=True`、`table=True`、`ocr=False`、`timeout=1200`、`language="ch"`；`state != "done"` 或 `markdown` 为空则失败。全文搜索确认 `prepare_ingest` 不再调用 `MinerULoader`
- [x] 1.2 把 `ExtractResult.images` 编成字节表（索引 `path`、`name`、`images/{name}`），Markdown 引用按原串 / 去 `./` / basename 查找。用假 `extract` 返回一张 `path=images/a.jpg` 的图，断言三种写法都能取到同一份 bytes

## 2. 两种地址规范化后接入现有配图流程

- [x] 2.1 在现有 `replace_images_with_ocr` 循环里按地址分流：相对路径查字节表 → data URI 再调同一个 `invoke_markdown_figure`；解析不到按现网识别失败（删 markup、不记账、不拷图）。KEEP 时用原字节 `put_object` 到 `{prefix}/images/{basename}`，不得 `httpx.get` 相对路径。KEEP/SKIP 语义与 https 配图相同。相邻无空白的两张 `![](images/hash.jpg)` 各走一遍；同一路径可缓存视觉结果
- [x] 2.2 `http://` / `https://` / `data:` 完全保持现行为（视觉吃原 URI，拷贝仍下载），不走字节表。更新 `test_prepare_ingest_pdf_uses_mineru` / `test_replace_images_with_ocr_keeps_going_after_one_failure`，使假转换返回 markdown + images，https 场景断言仍通过

## 3. 测试与回归

- [x] 3.1 新增相对路径用例：markdown 为 `![](images/<hash>.jpg)![](images/<hash>.jpg)` 且字节表有该文件时，视觉调用参数以 `data:image/` 开头、后续 `ocr_results` / `image_keys` 与 KEEP 现逻辑一致、R2 put 的 body 为转换器字节、`stored_markdown` 仍含原相对路径。无匹配字节时与识别失败相同：`ocr_results==[]`、嵌入稿不含该 markup、没有对该路径的 `httpx.get`
- [x] 3.2 执行 `uv run pytest tests/service/test_rag_service.py`，确认相对路径、https 配图、SKIP/失败不中断、png/txt 路径均通过
