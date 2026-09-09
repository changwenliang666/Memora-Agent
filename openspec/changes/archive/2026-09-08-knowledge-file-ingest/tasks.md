## 1. 上传白名单与 object_key

- [x] 1.1 扩展 `storage/validate.py` 白名单为 `.pdf` / `.docx` / `.md` / `.txt` / `.png` / `.jpg` / `.jpeg` 及对应 content-type；更新拒绝文案。执行 `tests/storage/test_validate.py`：png/jpeg/docx 合法，`.exe` 拒绝，pdf+text/plain 仍不匹配
- [x] 1.2 把 `R2Storage.presign_put` 的 key 改为 `{prefix?}/{uuid}/{filename}`。执行 `tests/storage/test_r2.py`：无前缀与有 `R2_KEY_PREFIX` 时 key 都含 `/` 且以原文件名结尾
- [x] 1.3 更新 `tests/api/test_files.py`：png/docx presign 成功；原 png 拒绝改为 `.exe`；合法 pdf 的 `object_key` 含前缀文件夹。执行该文件测试通过

## 2. R2 写入配图

- [x] 2.1 在 `R2Storage` 增加 `put_object(key, body, content_type)`，缺配置仍抛 `R2ConfigError`。用假 S3 客户端单测确认调用 `put_object` 且 Bucket/Key/ContentType 正确

## 3. knowledge_files 表

- [x] 3.1 新增 `KnowledgeFile` 模型（`user_id`、`filename`、`object_key`、`size`、`image_keys` JSON 默认 `[]`、`markdown`/`plain_text`/`ocr_text` 可空、时间戳），从 `db.models` 导出以便 `create_all` 建表。用模型或轻量测试确认字段齐全

## 4. 按类型建库

- [x] 4.1 `build_knowledge_base` 增加 `user_id`、`size`；按扩展名分流：pdf/docx 才调 MinerU 且缺 key 才失败；txt/md GET 文本；png/jpg/jpeg 下载后走 `OcrService`。用 mock 测试覆盖三种路径且 txt/png 不实例化 MinerU
- [x] 4.2 在 MinerU markdown 上替换 `![...](url)` 为视觉模型文本（顺序调用，单张失败不中断），再走现有切分入库。用含一张成功图、一张失败图的 markdown fixture 确认替换结果与仍能切分
- [x] 4.3 配图下载后 PUT 到 `{file_prefix}/images/{name}`，收集 object_key 列表。用 mock `put_object` 确认 key 含同一前缀和 `images/`
- [x] 4.4 Qdrant upsert 成功后插入 `knowledge_files`（按类型填 markdown / plain_text / ocr_text，`image_keys` 无图为 `[]`）；upsert 失败不写行。用 mock 会话确认成功插入与失败不 insert

## 5. complete 传入上传人

- [x] 5.1 `complete` 在派发后台任务前调用 `get_current_user()`，把 `user_id`、`size` 与现有参数一起传入；ingest 内不读 ContextVar。接口测试断言 `add_task` 参数含当前用户 id

## 6. 文档

- [x] 6.1 更新 `docs/r2-file-upload.md` 的校验表与 object_key 形状，并写明配图写在同一前缀的 `images/`。通读能对上 `validate.py` 与 `r2.py`
