## 1. Result types

- [x] 1.1 在 `rag_service.py` 模块级增加 `ImageOcrReplacement` 与 `PreparedIngest`（`frozen=True, slots=True`，字段与 `design.md` Decisions 1 一致），并确认文件可被 import
- [x] 1.2 把 `replace_markdown_images` 改名为 `replace_images_with_ocr`，返回 `ImageOcrReplacement`；内部用 `text_for_embedding` / `ocr_result` / `concatenated_ocr`，并确认不再返回两元组

## 2. Ingest pipeline names

- [x] 2.1 把 `build_points_data` 改名为 `build_qdrant_points`，参数改为 `vectors: list[list[float]]`；`split_text` 内 `sessions`/`session`/`final_docs` 改为 `header_sections`/`section`/`chunks`，并确认切块行为测试仍覆盖同一断言
- [x] 2.2 把 `copy_markdown_images` 的 `keys`/`data` 改为 `stored_image_keys`/`image_bytes`；`prepare_ingest` 三条路径都返回 `PreparedIngest`（内部 MinerU 原文用 `converted_markdown`，下载体用 `file_bytes`），并确认不再返回五元组
- [x] 2.3 改写 `build_knowledge_base`：`prepared = await prepare_ingest(...)`，切块用 `prepared.text_for_embedding`，向量用 `vectors`，落库用 `prepared.stored_*` 映射到 `save_knowledge_file` 的 ORM 形参，并确认该方法不再按位置解包

## 3. Tests

- [x] 3.1 更新 `tests/service/test_rag_service.py`：`prepare_ingest` 断言读 `PreparedIngest` 字段，`replace_images_with_ocr` 读 `ImageOcrReplacement` 字段，`build_knowledge_base` 的 fake 返回 `PreparedIngest`；执行 `uv run pytest tests/service/test_rag_service.py` 确认通过
- [ ] 3.2 执行 `uv run pytest` 与 `openspec validate --change "clarify-rag-ingest-naming" --strict`，确认全量测试通过且 change 校验成功
