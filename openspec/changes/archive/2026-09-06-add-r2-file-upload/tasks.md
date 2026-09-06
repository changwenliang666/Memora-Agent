## 1. Setup

- [x] 1.1 将 `boto3` 加入 `pyproject.toml` 并执行 `uv sync`，确认安装成功
- [x] 1.2 在 `.example.env` 增加 `R2_ACCOUNT_ID`、`R2_ACCESS_KEY_ID`、`R2_SECRET_ACCESS_KEY`、`R2_BUCKET_NAME` 空占位，确认名称与 `design.md` 一致且不含真实密钥
- [x] 1.3 创建 `src/memora_agent/storage/`、`src/memora_agent/api/files/` 包目录，确认这些路径存在且可被 import

## 2. 配置与 Schema

- [x] 2.1 用现有 `get_secret()` 增加 R2 配置读取（未填写时不在 import 阶段崩溃），并加上「为什么走 .env、不写 TOML」的注释；用测试或 REPL 确认缺省时能读到 `None`
- [x] 2.2 在 `schema/files.py` 定义 `PresignRequest`、`CompleteRequest`、`FileInfo`；用 pydantic 校验确认缺字段或非法类型会被拒绝

## 3. 校验与签发

- [x] 3.1 实现 `storage/validate.py`（`.pdf` / `.md` / `.txt` 与 content_type 配对，`1..104857600`），注释写明只信申报；`pytest` 覆盖合法 PDF/MD、非法扩展名、类型不配、size=0、size>100MiB
- [x] 3.2 实现 `storage/r2.py`：拼 endpoint、签发 PUT、`object_key` 为 `{uuid}/{filename}`、过期 900 秒；注释写明这是本地 HMAC、不访问网络；用 mock `generate_presigned_url` 的单测确认返回 `upload_url` / `object_key` / `expires_in`

## 4. HTTP 接口

- [x] 4.1 实现 `POST /files/presign`：先校验再签发，失败返回 4xx，缺 R2 配置返回 5xx；路由注释说明为何文件不进本服务；用测试客户端确认合法请求有 `upload_url`，非法请求无 `upload_url`
- [x] 4.2 实现 `POST /files/complete`：只回传 `FileInfo`，不调用 R2、不落库；在函数内留下「以后入库加在这里」的注释；用测试确认回传字段一致，缺 `object_key` 为 4xx，且测试中 R2 客户端未被调用
- [x] 4.3 在 `main.py` 挂载 files 路由，确认 `/docs` 出现 `/files/presign` 与 `/files/complete`，且现有 `/chat/*` 仍可访问

## 5. 测试

- [x] 5.1 新增 `tests/storage/` 与 `tests/api/`（或等价位置）覆盖 spec 场景，执行 `uv run pytest` 确认全部通过
- [x] 5.2 确认测试不依赖真实 `.env` 中的 R2 密钥（mock 或占位），`pytest` 在未填写 R2 时也能绿

## 6. 教学材料

- [x] 6.1 检查 `core/config.py`、`storage/validate.py`、`storage/r2.py`、两个路由上的注释：只解释为什么，不逐行复述代码
- [x] 6.2 撰写 `docs/r2-file-upload.md`（中文），覆盖 design 中的 8 点：为何直传、三步时序、预签名原理、校验与只信申报、`.env` 填法、CORS、对照源码路径、以后入库切入点；确认文件存在且能对照代码读完一遍
- [x] 6.3 更新 `README.md` 的 API 表与项目结构，确认列出两个新接口和 `storage/`、`docs/r2-file-upload.md`
