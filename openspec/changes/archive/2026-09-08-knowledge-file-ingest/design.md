## Context

现状见 `proposal.md`。上传仍是 presign → 直传 R2 → complete 签发 GET，后台调用 `RagService.build_knowledge_base`。当前 `object_key` 是 `{uuid}-{filename}`；白名单只有 pdf/md/txt；建库一律 `MinerULoader`。`OcrService.invoke(image_url)` 已能吃 https 与 data URI。MySQL 只有 `users`，启动 `create_all`，无 alembic。请求级用户在 `ContextVar`，后台任务不可用。MinerU 产出的 markdown 配图 URL 已实测可访问。

## Goals / Non-Goals

**Goals:**

- 按扩展名分流解析，视觉识别后再切分入库
- 每文件一个 R2 前缀，原始文件与配图拷贝住在一起
- 建库成功写 `knowledge_files`，地址只存 object_key

**Non-Goals:**

- 不提供文件列表 / 详情 API
- 不迁移旧 `{uuid}-{filename}` 对象
- 不上 alembic，不改向量切分参数
- 不引入 paddleocr 或新的策略/工厂抽象
- 不把桶改成公开读；markdown 正文保持 MinerU 原 URL，长期展示走 `image_keys`

## Decisions

### 1. 用扩展名分流，方法放在 `RagService`

`build_knowledge_base` 增加 `user_id`、`size`。按 `Path(filename).suffix.lower()` 分支：pdf/docx → MinerU + 处理配图；txt/md → `httpx` GET `download_url` 当 UTF-8 文本；png/jpg/jpeg → 视觉模型。切分、embedding、Qdrant 复用现有代码。

备选：策略类按类型注册。否决：三种路径，过度设计。

### 2. `object_key` 形状

`{R2_KEY_PREFIX?}/{uuid}/{filename}`。S3 无真实目录，斜杠即前缀。presign 只签原始文件；配图由后端 `put_object` 写到 `{uuid}/images/{name}`。`R2Storage` 增加 `put_object(key, body, content_type)`，与现有 presign 共用客户端。

备选：presign 同时签 images/。否决：此时还不知道有哪些图。

### 3. 配图：先用 MinerU URL 做视觉识别，再拷进自己的桶

继续 `MinerULoader.load()`。正则替换 `![...](url)`，把 url 交给 `OcrService`。识别后再把图下载并 PUT 到本文件前缀。独立图片与 txt 读取：本服务 GET 预签名地址（Qwen 不一定能打到 `*.r2.cloudflarestorage.com`）；独立图片转 data URI 再调视觉模型。多图顺序处理；单张失败记下空段，整篇继续。

备选：改用 MinerU SDK 拿图片 bytes。否决：URL 已可访问。

### 4. `knowledge_files` 表

启动 `create_all` 出表。列：`user_id`、`filename`、`object_key`、`size`、`image_keys`（JSON 数组，无图为 `[]`）、`markdown`、`plain_text`、`ocr_text`（三个 LONGTEXT 可空）、`created_at`、`updated_at`。按类型只填有值的正文列。不存「替换图之后」的合并稿。Qdrant 成功后再 INSERT；失败不写行。

备选：图片子表。否决：一个 JSON 字段足够。

备选：存预签名 URL。否决：一小时过期。

### 5. 上传人

`complete` 里 `get_current_user()`，把 `user.id` 传进后台任务。ingest 不读 `ContextVar`。

## Risks / Trade-offs

- [markdown 里的 MinerU 图链以后失效] → 正文保持原样便于对照；长期文件以 `image_keys` 为准。
- [Qdrant 成功、MySQL 失败] → 向量已在、记录没有。接受；不引入两阶段提交。
- [视觉模型超时或配图很多] → 顺序调用，可能拉长建库时间。接受。
- [旧 object_key 无文件夹] → 不迁移。
- [后端 GET/PUT 配图与 txt] → 字节进入本进程，但只在后台、且图通常远小于 100MiB 原文。原文 pdf/docx 仍由 MinerU 自己拉。

## Migration Plan

1. 改白名单与 `object_key`，补校验 / R2 单测
2. 分流建库、配图 OCR 与拷贝、`knowledge_files`
3. complete 传入 `user_id` 与 `size`；更新 `docs/r2-file-upload.md`
4. 回滚：恢复旧 key 与白名单、去掉新表（`DROP TABLE`）和新 PUT；已写入的 `{uuid}/` 对象可留在桶内

## Open Questions

无。扩展名分流、object_key 存地址、三列正文、JSON 配图 keys、建库成功才写表，已按讨论定下来。
