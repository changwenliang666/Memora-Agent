# Tasks: upload-mineru-raw-output-to-r2

## 1. 归档实现

- [x] 1.1 在 `RagService` 新增 `_archive_mineru_output(object_key, markdown, images) -> None`：构造 `R2Storage`，先 PUT `{prefix}/mineru/full.md`（`text/markdown; charset=utf-8`），再逐张 PUT `{prefix}/mineru/images/<Image.name>`（Content-Type 复用 `_image_content_type`）；每个对象单独 try/except，失败打印日志（含 object_key 与异常）后继续，整体不抛异常。验证：`uv run pytest tests/service/test_rag_service.py -k archive` 中新归档测试通过。
- [x] 1.2 在 `prepare_ingest` 的 `_CONVERTER_EXTS` 分支中，于 `result` 校验通过后、`replace_images_with_ocr` 之前调用 `_archive_mineru_output(object_key, result.markdown, result.images)`。验证：PDF 用例中归档 PUT 发生在任何视觉调用之前（测试用 Fake 记录调用顺序断言）。

## 2. 测试

- [x] 2.1 新增测试「全部配图归档且与 KEEP/SKIP 解耦」：`FakeMinerU` 返回含 3 张图的 markdown（1 张 KEEP、1 张 SKIP、1 张解析失败），断言 `FakeR2Storage.puts` 含 `mineru/full.md` 和全部 3 张 `mineru/images/<name>`，而 `{prefix}/images/` 仍只有 KEEP 的 1 张。验证：该测试通过。
- [x] 2.2 新增测试「单个归档失败不阻断」：让 `FakeR2Storage` 对某一张配图 PUT 抛异常，断言 `prepare_ingest` 正常返回、其余归档对象仍被 PUT、失败被日志记录。验证：该测试通过。
- [x] 2.3 补充断言「非转换文件不归档」：在现有 txt / png 用例上断言 `FakeR2Storage.puts` 不含任何 `mineru/` 前缀对象。验证：相关测试通过。
- [x] 2.4 全量回归：`uv run pytest` 全绿；`openspec validate upload-mineru-raw-output-to-r2` 通过。
