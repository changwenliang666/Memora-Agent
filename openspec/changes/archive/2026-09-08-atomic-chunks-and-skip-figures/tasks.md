## 1. Markdown 装箱切分

- [x] 1.1 新增切分模块（如 `service/text_split.py`）：扫描围栏代码、HTML `<table>`、管道表、ATX 标题与散文；原子块不内切且可超过 500 字；heading 路径写入 metadata 并合并 `source` / `filename`。用超 500 字的 HTML 表、含 `console.log()` 与 `#` 的围栏、管道表 fixture 断言各占一块且围栏完整
- [x] 1.2 纯文本路径保留 `RecursiveCharacterTextSplitter`（chunk_size=500、overlap=50）。用带行首 `#` 的长 `.txt` fixture 断言不按 Markdown 标题切节

## 2. 接到入库入口

- [x] 2.1 `RagService.split_text` 按后缀委托：`.md` / `.pdf` / `.docx` 走 Markdown 装箱，`.txt` / `.png` / `.jpg` / `.jpeg` 走纯文本切；该类不再内联 `MarkdownHeaderTextSplitter`。用同文件名后缀的 `split_text` 调用覆盖 1.1 / 1.2 的分流断言

## 3. Markdown 配图 SKIP

- [x] 3.1 `OcrService` 拆成独立图片提取与 Markdown 配图判别两条调用；配图提示词在无检索价值时只输出 `SKIP`。用单元测试或对提示词/返回解析的测试确认 trim 后大小写不敏感的 `SKIP` 视为跳过，`SKIP` 后仍有其它文字视为 KEEP
- [x] 3.2 `replace_images_with_ocr`：KEEP 才拷 R2 并追加 `ocr_results`，SKIP 或调用失败删除图片语法且不拷不记账；`stored_markdown` 仍含原图链。更新 `tests/service/test_rag_service.py`：一张 KEEP、一张 SKIP、一张失败时 `ocr_results` 只有 KEEP 那条，嵌入稿含 KEEP 文本且不含另两张的 markup
- [x] 3.3 独立图片路径仍只调提取接口并写入一条 `ocr_results`。更新 png 入库测试：即使返回内容像装饰图，仍落一条且 `image_keys=[]`

## 4. 回归

- [x] 4.1 执行 `uv run pytest tests/service/test_rag_service.py` 以及切分模块测试，确认原子块、SKIP 省略、独立图片不拦、upsert 失败不写行仍通过
