## Context

见 `proposal.md` 的 Why。当前 `replace_images_with_ocr` 对 Markdown 配图逐张调视觉模型，再用 `"\n\n".join` 得到 `concatenated_ocr` 写入 `KnowledgeFile.ocr_text`。`copy_markdown_images` 另起循环拷图，失败则跳过，因此 `image_keys` 与拼接字符串的段数可以对不齐。独立图片路径把 OCR 字符串同时用作嵌入文本和落库字段；`image_keys` 仍为 `[]`。无 alembic，启动 `create_all` 外加 lifespan 里对 `markdown` / `plain_text` / `ocr_text` 的 `MEDIUMTEXT` ALTER。`ocr_text` 未出现在 HTTP 响应里。

## Goals / Non-Goals

**Goals:**

- 落库按图保留识别结果，并能对上对象存储 key
- Markdown 配图的 OCR 与拷贝按同一出现顺序产出，失败占位而不是缩短列表
- 新库 `create_all` 直接出 JSON 列；已有库启动时改列

**Non-Goals:**

- 不改切块、embedding、Qdrant payload（嵌入文本仍把图换成 OCR 文字）
- 不上 alembic、不做旧 `ocr_text` 字符串拆分迁移
- 不提供文件列表 / 详情 API
- 不引入图片子表或新的 OCR 策略抽象

## Decisions

### 1. 同表 JSON 列，不建子表

`ocr_results` 用 SQLAlchemy `JSON`，非空，默认 `[]`，与现有 `image_keys` 同一套存储方式。元素形状：`{"image_key": str | null, "text": str}`。

备选：`knowledge_file_images` 子表。否决：现阶段没有按图查询或独立生命周期，JSON 足够，也与 `image_keys` 的既有选择一致。

备选：保留列名 `ocr_text` 只改类型。否决：名字仍像一整段正文，调用处容易继续当 `str` 拼接。

### 2. 配图：按 Markdown 出现顺序一次走完 OCR 和拷贝

现在两条独立循环（OCR 失败留空段，拷贝失败直接 `continue`）是对不齐的根因。PDF/DOCX 路径改为对每个 `![...](url)`：先 OCR（失败则 `text=""`），再尝试 PUT 到 `{prefix}/images/{name}`（失败则 `image_key=null`），追加一条结果，并用 OCR 文字替换嵌入稿中的图片语法。`image_keys` 仍只收集拷贝成功的 key，可从 `ocr_results` 里 `image_key is not None` 的项导出，避免第三份顺序。

独立图片：`ocr_results=[{"image_key": object_key, "text": <ocr>}]`，`image_keys` 仍为 `[]`（源文件不是配图）。txt/md：`ocr_results=[]`。

`ImageOcrReplacement.concatenated_ocr` 和 `PreparedIngest.stored_ocr_text` 改为按图列表；禁止再 `"\n\n".join` 后写入数据库。

### 3. 启动改列，不迁旧数据

新库：`create_all` 出 `ocr_results` JSON。已有库：lifespan 在 `create_all` 之后 `CHANGE COLUMN ocr_text ocr_results JSON NOT NULL`（或等价的 DROP + ADD）。失败只打日志，不阻断启动。不再对 `ocr_text` 做 `MEDIUMTEXT` ALTER；`markdown` / `plain_text` 仍维持 `MEDIUMTEXT`。已有拼接字符串不解析、不回填。

备选：把旧字符串按 `\n\n` 切开再对齐 `image_keys`。否决：失败空段与拷贝跳过已经错位，拆出来也不可信。

## Risks / Trade-offs

- [已有行的 `ocr_text` 无法自动变成按图 JSON] → 不迁移；开发期重建表或接受该列为空 / 改列失败。
- [拷贝失败时 `image_key` 为 null，只剩文本] → 接受；至少不再把多图糊成一段。
- [JSON 列没有 `MEDIUMTEXT` 那种 16MB 正文上限语义] → 单张 OCR 是摘要，列表体积远小于 markdown；不为此改列类型。
- [`fix-knowledge-file-mediumtext` 仍要求 `ocr_text` 为 `MEDIUMTEXT`] → 本变更取代该列；实现时去掉对 `ocr_text` 的 ALTER。

## Migration Plan

1. 改模型与入库结构，测试按图列表而不是拼接字符串
2. lifespan：`ocr_text` → `ocr_results` JSON；保留 markdown / plain_text 的 MEDIUMTEXT 修改
3. 回滚：列改回可空 `MEDIUMTEXT ocr_text`，入库再拼接；已写成 JSON 的行不自动还原

## Open Questions

无。JSON 同表、按图 `{image_key, text}`、嵌入路径不变、旧数据不迁，已按现有 `image_keys` 惯例定下来。
