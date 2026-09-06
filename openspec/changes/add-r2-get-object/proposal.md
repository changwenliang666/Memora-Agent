## Why

前端直传 R2 之后，会把 `object_key` 交给 `POST /files/complete`，但本服务只回传申报字段，没有一份 MinerU 能直接拉的地址。自己读桶再给本地路径，文件会进本进程，MinerU 还要再传一遍。现在要按 complete 里的键签发短时可读 URL，后续直接交给 `MinerULoader(source=url)`。

## What Changes

- 在 `R2Storage` 新增按 `object_key` 签发预签名 GET 的方法，与现有 `presign_put` 同一套本地 HMAC
- `POST /files/complete` 用请求里的 `object_key` 签发该地址，并在 `FileInfo` 中一并返回 `download_url` 与 `expires_in`
- 本服务不读取、不删除对象字节，也不把文件内容写进响应体
- 本次不落库、不在 `complete` 里调用 MinerU；URL 留给之后的解析入口使用

## Capabilities

### New Capabilities

### Modified Capabilities
- `file-upload`: `complete` 从「只回传申报、不签发下载地址」改为「按申报的 `object_key` 签发短时 GET 地址并返回」

## Impact

- `src/memora_agent/storage/r2.py`：新增 `presign_get`
- `src/memora_agent/schema/files.py`：`FileInfo` 增加 `download_url`、`expires_in`
- `src/memora_agent/api/files/files.py`：`complete` 调用签发方法
- `tests/storage/test_r2.py`、`tests/api/test_files.py`、`tests/schema/test_file_schemas.py`：覆盖新字段与签发调用
- `docs/r2-file-upload.md`：complete 改为回传可读 URL
- 无新依赖；仍用现有 boto3
- **兼容**：`FileInfo` 多两个字段。已按三步走完的客户端多拿到 URL；未实际上传时 complete 仍会成功（签发不读桶），MinerU 拉文件时才会失败
