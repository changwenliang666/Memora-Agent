## 1. 存储层签发 GET

- [x] 1.1 在 `storage/r2.py` 增加 GET 过期常量（3600 秒）和 `presign_get(object_key)`，复用 `_require_config()` 与 `_s3_client()`，对 `get_object` 做本地 HMAC；确认 `presign_put` 行为不变
- [x] 1.2 在 `tests/storage/test_r2.py` 覆盖：成功返回 `download_url` / `object_key` / `expires_in` 且假客户端收到 `get_object` 与对应 `Key`；配置不齐抛 `R2ConfigError`。执行这些用例确认通过且不连真实 R2

## 2. complete 回传 URL

- [x] 2.1 在 `schema/files.py` 的 `FileInfo` 增加 `download_url` 与 `expires_in`；用 schema 测试确认缺这些字段的响应模型不合法，申报四字段仍在
- [x] 2.2 改 `POST /files/complete`：用 `request.object_key` 调用 `presign_get`，把申报字段与 `download_url` / `expires_in` 一并返回；`R2ConfigError` → 500；响应不含对象字节
- [x] 2.3 更新 `tests/api/test_files.py`：`RecordingStorage` 增加 `presign_get`；成功 complete 必须调用它并包含非空 `download_url` 与正的 `expires_in`；缺配置为 5xx；缺 `object_key` 为 422 且不调用 `presign_get`。执行接口测试确认通过

## 3. 文档与回归

- [x] 3.1 更新 `docs/r2-file-upload.md`：complete 签发短时 GET、不读桶；说明该 URL 可交给 MinerU loader。通读一遍能对上 `r2.py` 与 `files.py`
- [x] 3.2 执行 `uv run pytest tests/storage/test_r2.py tests/api/test_files.py tests/schema/test_file_schemas.py`，确认 presign PUT 与旧校验用例仍绿
