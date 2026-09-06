# Cloudflare R2 文件直传：这条链路是怎么做的

这不是接口说明书，而是一份对照源码读的笔记。读完你应该能自己讲清楚：为什么文件不进 FastAPI、预签名 URL 到底签了什么、两个接口各自干什么、以后要入库改哪一行。

建议按下面的顺序，打开对应文件一起看。

---

## 1. 为什么文件不走本服务

如果做成「前端把文件 POST 到 FastAPI，再由后端上传 R2」，会出现三件事：

- 100MB 的 PDF 会占满应用服务器的带宽和内存，还容易超时。
- R2 的 Access Key / Secret 必须出现在「整段上传」这条链路上，暴露面更大。
- Agent 服务的职责是对话，不是文件中转站。

所以采用 **直传**：本服务只签发一个短时有效的上传地址，浏览器拿着这个地址 `PUT` 到 R2。文件字节从不进入 `memora_agent` 进程。

密钥始终留在服务端的 `.env` 里。前端拿到的只是一段签过名的 URL，过期后就不能再上传。

---

## 2. 三步时序

```
前端                         Memora Agent                      Cloudflare R2
 |                                |                                 |
 |  POST /files/presign           |                                 |
 |  filename, content_type, size  |                                 |
 |------------------------------->|  校验申报，本地 HMAC 签名         |
 |  upload_url, object_key,       |                                 |
 |  expires_in                    |                                 |
 |<-------------------------------|                                 |
 |                                |                                 |
 |  PUT upload_url                |                                 |
 |  Header: Content-Type = 申报值 |                                 |
 |--------------------------------------------------------------->  |
 |                                |                                 |
 |  POST /files/complete          |                                 |
 |  object_key, filename,         |                                 |
 |  content_type, size            |                                 |
 |------------------------------->|  本地签发 GET，不读对象字节       |
 |  FileInfo + download_url       |                                 |
 |<-------------------------------|                                 |
```

对应代码：

| 步骤 | 谁做 | 文件 |
|------|------|------|
| 校验申报 | 后端 | `src/memora_agent/storage/validate.py` |
| 签发 URL | 后端 | `src/memora_agent/storage/r2.py` |
| HTTP 入口 | 后端 | `src/memora_agent/api/files/files.py` |
| 真正传文件 | 前端 / 浏览器 | 本仓库没有前端，用 curl 或网页 `PUT` |
| 回传元数据 + 短时 GET | 后端 | `files.py` 的 `complete`，`R2Storage.presign_get` |

---

## 3. 预签名 URL 是什么

很多人以为流程是：「后端先问 R2 要一个洞，R2 再给一个临时地址」。不是这样。

`boto3` 的 `generate_presigned_url("put_object", ...)` **只在本地算一个 HMAC 签名**，拼进 URL 的 query string。这一步 **不访问网络**，Cloudflare 此时还不知道即将有一次上传。

浏览器稍后 `PUT` 时，R2 用同一套密钥验签：签名对、没过期、Bucket / Key / Content-Type 与签名时一致，就收下对象。

endpoint 由 Account ID 拼出来，不单独配置：

```text
https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com
```

region 对 R2 固定写 `auto`。见 `R2Storage.presign_put` 和 `presign_get`。

`object_key` 的形状是 `{uuid4()}/{原文件名}`，例如 `3f2a.../notes.pdf`。若 `.env` 填了 `R2_KEY_PREFIX`，则变成 `{前缀}/{uuid4()}/{原文件名}`，例如 `knowledge-base/3f2a.../notes.pdf`。前面的 UUID 避免两人上传同名文件时互相覆盖；后面的文件名以后还能还原。

PUT 有效期 900 秒（15 分钟），`presign` 响应里的 `expires_in` 就是这个数。前端必须在过期前 `PUT`。

GET 有效期 3600 秒（1 小时），`complete` 响应里的 `expires_in` 是这个更长的值，留给 MinerU 排队后再拉。`presign_get` 同样只做本地 HMAC，不读桶。

签发 PUT 时带了 `ContentType`。浏览器上传时 **必须使用同一个 Content-Type**，否则 R2 会认为签名不匹配而拒绝。

---

## 4. 校验矩阵，以及「只信申报」的代价

`presign` 在签发之前检查三个申报字段，规则在 `validate_declaration`：

| 扩展名 | 允许的 content_type | 大小 |
|--------|---------------------|------|
| `.pdf` | `application/pdf` | 1 ～ 104857600 字节（100 MiB） |
| `.md`  | `text/markdown` 或 `text/plain` | 同上 |
| `.txt` | `text/plain` | 同上 |

`.md` 接受 `text/plain`，是因为很多浏览器选 markdown 时会报成纯文本。

这次 **完全信任前端申报**：

- `presign` 不读桶。
- `complete` 只按 `object_key` 签发 GET，不读对象、不核对真实大小、不删除对象。没上传过的键也会拿到 URL，MinerU 去拉时才会失败。
- 预签名 PUT 本身也无法在签名里强制「最大 100MB」（那是 S3 POST Policy 的能力，本次不用）。

代价：一个恶意或出错的客户端可以先用合法 size 拿到 URL，再上传更大的文件。产品上先接受。以后要补，只需要在 `complete` 里加 `HeadObject`（以及可选的删除），**不必改 presign 的请求体**。

---

## 5. `.env` 字段怎么填

复制模板：

```bash
cp .example.env .env
```

填写（值从 Cloudflare 控制台 → R2 → 管理 API 令牌 拿）：

```env
R2_ACCOUNT_ID=你的账号 ID
R2_ACCESS_KEY_ID=令牌的 Access Key ID
R2_SECRET_ACCESS_KEY=令牌的 Secret Access Key
R2_BUCKET_NAME=桶名
R2_KEY_PREFIX=knowledge-base
```

`R2_KEY_PREFIX` 可选。R2 没有真正的文件夹，前缀就是控制台里看到的目录。不填则对象直接落在桶根下。

读取逻辑在 `src/memora_agent/core/config.py` 的 `load_r2_config()`，走现成的 `get_secret()`：先看进程环境变量，再看项目根目录 `.env`。空字符串当成「没填」。

四个值没填齐时，**进程能启动**，校验单测也能跑；只有调用 `presign` 或 `complete` 才会返回 HTTP 500，提示去填占位。这是有意的：不要让缺 R2 配置把整个 Agent 服务拖死。

这些值不写进 `config/models.toml`。TOML 是模型清单，和对象存储密钥不是一类东西，混在一起既难审阅，也更容易被提交。

---

## 6. 桶 CORS 为什么必须在控制台配

浏览器从 `http://localhost:5173`（或你的前端源）`PUT` 到 `*.r2.cloudflarestorage.com`，这是跨域。没有 CORS，浏览器会在发出 PUT 之前或之后拦截，后端代码帮不上忙。

在 Cloudflare 控制台打开对应 R2 桶 → Settings → CORS，允许：

- Origin：你的前端源站（开发期可以是 `http://localhost:5173`）
- Methods：至少 `PUT`（调试时也可加 `HEAD`）
- Headers：至少 `Content-Type`

本仓库不把 CORS 写进代码，因为那是桶的策略，不是 FastAPI 的策略。

---

## 7. 对照源码读

从外往里：

1. `src/memora_agent/main.py`  
   把 `/files` 和 `/chat` 并列挂上。文件能力和对话能力是两条线。

2. `src/memora_agent/api/files/files.py`  
   薄路由。`presign`：先 `validate_declaration`，再 `R2Storage.presign_put`。失败是 400，缺配置是 500。  
   `complete`：用申报的 `object_key` 调 `presign_get`，返回申报四字段加上 `download_url` / `expires_in`。不读对象字节。这个 URL 可以直接传给 `MinerULoader(source=url)`。

3. `src/memora_agent/schema/files.py`  
   `PresignRequest` / `CompleteRequest` / `FileInfo` / `PresignResponse`。缺字段由 Pydantic / FastAPI 直接 422。

4. `src/memora_agent/storage/validate.py`  
   纯函数，不碰网络。单测在 `tests/storage/test_validate.py`。

5. `src/memora_agent/storage/r2.py`  
   唯一和 boto3 打交道的地方。构造客户端、拼 endpoint、签发 PUT / GET。测试用假客户端注入，不连真实 R2。

6. `src/memora_agent/core/config.py`  
   `R2Config` + `load_r2_config()`。看它如何把空值收成 `None`，以及 `endpoint_url` 怎么拼。

7. `tests/api/test_files.py`  
   用 FastAPI `TestClient` 打两个接口。签发被 mock 掉，所以 CI / 本地没填 R2 也能绿。

---

## 8. 以后加数据库，只改一处

`POST /files/complete` 已经是「提交」语义：前端说「我传完了」，后端收下这份元数据，并签发一份短时可读 URL。

现在它会 return `FileInfo`（含 `download_url`）。以后有库时，在 `complete` 里、`return FileInfo(...)` **之前** 插入一行即可，例如：

- `object_key`
- `filename`
- `content_type`
- `size`

`presign` 不用改。不要先做内存伪库，重启即丢，还会和真库打架。

`download_url` 的用途是交给 MinerU 这类按 HTTPS 拉文件的加载器，而不是让本服务先把对象读进内存。如果以后还要「确认桶里真有这个对象」，也是加在 `complete`：`HeadObject` → 不一致就 4xx（可选再 `DeleteObject`）。同样不必改第一步。

---

## 本地怎么试

1. `uv sync`
2. 填写 `.env` 的四个 R2 字段
3. 桶上配好 CORS
4. `uv run uvicorn memora_agent.main:app --reload`
5. 打开 `http://127.0.0.1:8000/docs`，先调 `/files/presign`，再用返回的 `upload_url` 做 `PUT`，最后调 `/files/complete`

没有前端时，第二步可以用 curl：

```bash
curl -X PUT "$UPLOAD_URL" \
  -H "Content-Type: application/pdf" \
  --data-binary @notes.pdf
```

`Content-Type` 必须和 presign 时申报的一致。
