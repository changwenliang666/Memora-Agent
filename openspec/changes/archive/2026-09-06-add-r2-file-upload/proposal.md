## Why

前端需要把 PDF / Markdown / 纯文本上传到 Cloudflare R2，但文件不应经过 Agent 服务本身。当前仓库没有存储层、没有上传接口，也没有 R2 配置入口。需要先打通「签发临时地址 → 前端直传 → 回传上传信息」这条闭环，数据库入库留到后续需求再加。

## What Changes

- 新增两个 HTTP 接口：`POST /files/presign` 签发 R2 预签名 PUT 地址；`POST /files/complete` 接收前端申报的上传信息并原样整理返回
- 新增 R2 存储封装与 `.env` 占位（Account ID、Access Key、Secret、Bucket），密钥由使用者自行填写
- `presign` 按前端申报校验：仅允许 `.pdf` / `.md` / `.txt`，大小 1 字节到 100MB；完全信任申报，`complete` 不读桶、不删对象
- 本次不落库、不签发下载地址、不接入 Agent
- 实现代码加讲解注释；开发完成后在仓库生成一份本地教学文档，说明整条流程为什么这样设计、每一步代码在做什么

## Capabilities

### New Capabilities
- `file-upload`: 前端直传 Cloudflare R2 的预签名与完成确认

### Modified Capabilities

## Impact

- FastAPI 入口 `main.py` 增挂 `/files` 路由，与现有 `/chat` 并列
- 新增 `api/files/`、`schema/files.py`、`storage/`，扩展 `core/config.py` 与 `.example.env`
- 依赖新增 `boto3`（S3 兼容，用于本地签发预签名 URL）
- 新增教学文档（建议 `docs/r2-file-upload.md`），供本地阅读，不改变运行时行为
- R2 桶的 CORS 需在 Cloudflare 控制台配置，不在本服务代码范围内
- 无破坏性变更：现有 `/chat/*` 行为不变
