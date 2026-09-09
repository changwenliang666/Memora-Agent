## 1. 模型列

- [x] 1.1 把 `KnowledgeFile.ocr_text` 换成 `ocr_results`：SQLAlchemy `JSON`、非空、默认 `[]`。`markdown` / `plain_text` 仍为可空 `MEDIUMTEXT`。执行 `tests/db/test_knowledge_file.py`：列名含 `ocr_results` 不含 `ocr_text`，JSON 非空，与 `image_keys` 同类

## 2. 按图产出 OCR 结果

- [x] 2.1 把 `ImageOcrReplacement.concatenated_ocr` 和 `PreparedIngest.stored_ocr_text` 改成按图列表（每项 `image_key` + `text`），`save_knowledge_file` 写入 `ocr_results`。全文搜索确认不再 `"\n\n".join` 后落库
- [x] 2.2 PDF/DOCX：对每个 Markdown 配图先 OCR（失败 `text=""`）再拷贝（失败 `image_key=null`），按出现顺序追加；`image_keys` 只收拷贝成功的 key；嵌入稿仍把图换成 OCR 文字。更新 `tests/service/test_rag_service.py`：两张图（一张 OCR 失败）得到两条结果、失败项 `text==""`，且嵌入文本仍含成功图的 OCR
- [x] 2.3 独立图片路径写入 `ocr_results=[{"image_key": object_key, "text": <ocr>}]` 且 `image_keys=[]`；txt/md 写入 `ocr_results=[]`。更新同文件测试：png / txt 两条断言通过

## 3. 已有表改列

- [x] 3.1 在 `main.py` lifespan 的 `create_all` 之后把 `ocr_text` 改成 `ocr_results JSON NOT NULL`（或 DROP + ADD），并去掉对 `ocr_text` 的 `MEDIUMTEXT` ALTER；`markdown` / `plain_text` 的 MEDIUMTEXT 修改保留。失败只打日志不阻断启动。用代码确认语句在同一 try 块且不再出现 `MODIFY ocr_text`

## 4. 回归

- [x] 4.1 执行 `uv run pytest tests/db/test_knowledge_file.py tests/service/test_rag_service.py`，确认按图 JSON 落库、嵌入替换与 upsert 失败不写行仍通过
