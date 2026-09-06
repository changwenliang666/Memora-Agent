## Context

现有服务是 FastAPI + LangChain Agent：HTTP 入口在 `api/chat/chat.py`，领域逻辑在独立包，密钥用 `core/config.py` 的 `get_secret()` 从 `.env` 读取，模型清单在 `config/models.toml`。没有存储层、没有数据库、没有文件接口。动机与范围见 `proposal.md`；对外行为见 `specs/file-upload/spec.md`。

本设计要解决三件事：新能力挂在哪、R2 怎么签临时地址、如何把流程写成后来的人（包括作者自己）能读懂的注释和本地文档。

## Goals / Non-Goals

**Goals:**

- 按现有「薄路由 + 领域包 + schema」分层新增 `/files`，不把逻辑塞进 `chat.py`
- 只用 boto3 在本地签发预签名 PUT URL；`complete` 是无副作用的元数据回传
- 密钥与桶名全部走 `.env` 占位，源码与 TOML 不出现真实值
- 校验逻辑可单测，不依赖真实 R2
- 代码注释讲「为什么」；完成后产出一份中文教学文档，覆盖流程、签名原理、校验、配置和后续入库切入点

**Non-Goals:**

- 不引入数据库或内存登记
- 不在 `complete` 上 HeadObject / 删除对象 / 签发 GET 地址
- 不接入 Agent、记忆或解析文件内容
- 不在代码里配置 R2 CORS（控制台操作）
- 不改现有 `/chat/*` 的错误返回风格

## Decisions

### 1. 目录与职责，对齐现有分层

```
src/memora_agent/
  api/files/files.py      # 路由：参数进出，不写签名细节
  schema/files.py         # PresignRequest / CompleteRequest / FileInfo
  storage/r2.py           # boto3 客户端 + 签发 URL
  storage/validate.py     # 扩展名 / content_type / size 纯函数
  core/config.py          # 增加读取 R2 环境变量
```

`memory/` 与 `graph/` 已是顶层能力包，存储同样放顶层 `storage/`，不塞进 `core/`。`core` 继续只负责配置与模型提供商。

备选：把一切写进 `api/files/files.py`。否决原因是路由会同时承担校验、签名和配置，后续入库时更难拆。

### 2. 用 boto3 签发，complete 不访问 R2

Cloudflare R2 是 S3 兼容。`generate_presigned_url("put_object", ...)` 是本地 HMAC 签名，不发起网络请求。endpoint 由 `R2_ACCOUNT_ID` 拼出：`https://<ACCOUNT_ID>.r2.cloudflarestorage.com`，region 用 `auto`。

`complete` 只把请求体整理成 `FileInfo` 返回。以后入库只在这个函数末尾加一行持久化，不必改协议。

备选：`aioboto3`（异步）或自写签名。当前只有本地签名、没有并发上传代理，boto3 更小、文档与 R2 官方示例一致。

### 3. 配置只放 `.env`，沿用 `get_secret()`

占位名：

- `R2_ACCOUNT_ID`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_BUCKET_NAME`

与 `DEEPSEEK_API_KEY` 同一通道。桶名虽非密钥，也放 `.env`，避免再开一份 TOML。`.example.env` 写空占位，`.env` 仍被 gitignore。未配置时 `presign` 返回明确的服务端错误，而不是在 import 时崩溃。

备选：`config/storage.toml` 存桶名。否决：本次只有四个值，拆文件收益低。

### 4. 对象键、过期与错误码

- `object_key`：`{uuid4()}/{原文件名}`，满足「可还原文件名」，并避免覆盖
- 预签名有效期：900 秒（15 分钟），响应里返回 `expires_in`
- 签发 PUT 时带上申报的 `ContentType`，浏览器上传须使用同一值
- 新接口用 HTTP 4xx/5xx（FastAPI `HTTPException` 或 Request Validation），不模仿 `/chat` 的「HTTP 200 + error 字段」

校验白名单写死在 `storage/validate.py`：

| 扩展名 | 允许的 content_type |
|--------|---------------------|
| `.pdf` | `application/pdf` |
| `.md`  | `text/markdown` 或 `text/plain` |
| `.txt` | `text/plain` |

大小：`1 <= size <= 104857600`。只信申报，不读桶。

### 5. 注释与教学文档是交付物，不是事后补丁

注释写在模块顶、配置读取、校验规则、签发函数和两个路由上，说明「为什么直传 / 为什么只信申报 / 以后入库加在哪」。禁止逐行复述代码。

教学文档路径：`docs/r2-file-upload.md`。必须用中文讲清楚：

1. 为什么文件不走本服务（体积、超时、密钥不暴露给前端）
2. 三步时序：presign → 浏览器 PUT R2 → complete
3. 预签名 URL 是什么：本地 HMAC，不是先问桶要一个洞
4. 校验矩阵和只信申报的代价
5. `.env` 四个字段怎么填、endpoint 怎么拼
6. 桶 CORS 为什么必须在控制台配
7. 对照仓库里的真实文件路径读代码
8. 以后加数据库时，唯一应该改的切入点

该文档不参与运行时，但必须在实现任务里完成，不能只留 TODO。

## Risks / Trade-offs

- [只信前端申报] → 超限或类型不符的对象仍可能进桶。本次接受；以后若要治理，在 `complete` 加 HeadObject / 删除，不必改 presign 协议。
- [桶未配 CORS] → 浏览器 PUT 失败。文档写明控制台步骤；代码无法代替。
- [`.env` 未填] → `presign` 失败。用明确错误信息，避免启动即崩，方便先跑校验单测。
- [预签名 PUT 无法在签名里强制最大体积] → 与「只信申报」一致，不引入 POST Policy。
- [无鉴权] → 与现有 `/chat` 相同。任何人可申请上传地址。本次不新增认证。

## Migration Plan

1. 增加 `boto3` 依赖与 `.example.env` 占位
2. 合并代码后，本地复制占位到 `.env` 并填写 R2 值
3. 在 R2 桶配置允许前端源站的 CORS（允许 `PUT`、需要的头）
4. 用 `/docs` 或测试调用 `presign` / `complete` 验证
5. 回滚：去掉 `/files` 路由与 `storage/` 即可，不影响 `/chat`

## Open Questions

无。规格、路径、校验规则和「complete 不访问 R2」已在探索中确认。
