## Context

直传链路已经落地：`R2Storage.presign_put` 本地签发 PUT，`complete` 只回传申报四字段。动机见 `proposal.md`；对外行为见本 change 的 delta spec。

约束：存储层只依赖 `R2Config` 和可注入的 S3 客户端，不引用 FastAPI schema；签发仍是本地 HMAC，测试不连真实 R2。MinerU 云端会自己 GET 这个 URL，所以地址必须带公网可访问的签名，而不能是只对本机有效的路径。

## Goals / Non-Goals

**Goals:**

- 在 `R2Storage` 增加 `presign_get(object_key)`，复用现有客户端与配置检查
- `complete` 用申报的 `object_key` 签发 GET，并把 `download_url` / `expires_in` 放进 `FileInfo`
- 文件字节不进本进程；URL 形状可直接作为 `MinerULoader` 的 `source`

**Non-Goals:**

- 不在 `complete` 里调用 MinerU / Agent
- 不 `GetObject` / `HeadObject`，不核对对象是否真的在桶里
- 不把桶改成公开读，不引入 `r2.dev` 或自定义域（预签名失败再另开 change）
- 不改 `presign` PUT、校验白名单或 R2 配置读取方式

## Decisions

### 1. 签发 GET，不读对象

新增 `R2Storage.presign_get(object_key: str)`，内部 `generate_presigned_url("get_object", Params={Bucket, Key}, ExpiresIn=...)`。与 PUT 一样只做本地 HMAC，不访问 Cloudflare。

返回结构对齐 `PresignResult`：`download_url`、`object_key`、`expires_in`。方法只收键，不收整个 `CompleteRequest`，避免 `storage/` 依赖 schema。

备选：`GetObject` 拉字节再给本地路径。否决：本服务吃 100 MiB，MinerU SDK 还要再上传一次。

备选：公开桶或 `*.r2.dev` 固定 URL。否决：改变桶策略，超出本次范围；预签名能保持私有桶。

### 2. GET 有效期单独加长

PUT 仍是 900 秒。GET 用独立常量，默认 **3600 秒**，给 MinerU 排队和拉取留时间。响应里的 `expires_in` 用这个值。

### 3. `FileInfo` 增加两个字段；complete 缺配置与 presign 相同

```
object_key, filename, content_type, size, download_url, expires_in
```

`complete`：缺字段仍由 Pydantic 422；`R2ConfigError` → 500。签发不读桶，因此 **对象不存在时 complete 仍成功**；MinerU 稍后 GET 失败。这是「不自己写读文件逻辑」的直接代价，接受。

### 4. 测试与文档

- 假客户端已有 `generate_presigned_url`：断言 `complete` / `presign_get` 传入 `get_object` 和正确 `Key`
- `tests/storage/test_r2.py`：成功签发、缺配置
- `tests/api/test_files.py`：`RecordingStorage` 增加 `presign_get`；成功 complete 必须调用它并带上 `download_url`；缺配置 500；「complete 不访问 R2」改为「不读对象、只签发」
- `docs/r2-file-upload.md`：complete 回传短时 GET，用途是交给 MinerU 这类按 URL 拉文件的加载器

## Risks / Trade-offs

- [签发不验证对象存在] → complete 对未上传的键也会 200。接受；避免本服务读桶。
- [MinerU 云端拉不到 R2 S3 API 地址] → 预签名 URL 带 query。若对方丢掉签名或访问不了 `*.r2.cloudflarestorage.com`，再改公开域。本次先走预签名。
- [GET URL 出现在 HTTP 响应里] → 持有响应的人可在过期前下载。与现有无鉴权 presign 同一等级，本次不引入认证。
- [`FileInfo` 多字段] → 旧客户端若严格按四字段解码可能失败。这是有意的协议扩展。

## Migration Plan

1. 实现 `presign_get` 与单测
2. 扩展 `FileInfo`，改 `complete` 与接口测试
3. 更新 `docs/r2-file-upload.md`
4. 回滚：去掉 GET 签发和两个新字段；桶内对象不受影响

## Open Questions

无。用预签名 GET、加长过期、complete 不读桶、本 change 不接 MinerU，已按讨论定下来。
