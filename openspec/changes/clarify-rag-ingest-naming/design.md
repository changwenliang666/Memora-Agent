## Context

动机见 `proposal.md`。本 change 设了 `skip_specs`，入库行为仍以已有 `knowledge-ingest` 为准，这里只定内部命名和返回结构。

当前主链路在 `RagService.build_knowledge_base`：`prepare_ingest` 按扩展名产出五元组，再 `split_text` → embedding → Qdrant → `save_knowledge_file`。五元组顺序是 `(embed_text, markdown, plain_text, ocr_text, image_keys)`。同一次调用里，`embed_text` 和某列落库正文经常是同一份字符串（txt 时等于 `plain_text`，图片时等于 `ocr_text`），PDF 时又故意不是同一份（嵌入用「图已换成 OCR」的稿，落库 `markdown` 仍是 MinerU 原文）。按位置解包看不出这种分家。

`replace_markdown_images` 同样返回 `(replaced, ocr_text)`。`split_text` 把标题切块叫 `sessions`。`build_points_data` 的 `embedding: list[float]` 实际是一组向量。项目里已有 `@dataclass(frozen=True, slots=True)`（`CurrentUser`）。

## Goals / Non-Goals

**Goals:**

- `build_knowledge_base` 用字段名读写「嵌入稿」和「落库稿」，不再靠元组下标
- 局部变量名能对上它在流水线里的角色（章节块、向量、OCR 单张结果）
- 测试跟命名一起改，行为断言保持原样

**Non-Goals:**

- 不改分流规则、OCR、切块参数、Qdrant payload、webhook
- 不改 `knowledge_files` 列名，不写迁移
- 不改 `save_knowledge_file` 的形参名（继续对齐 ORM：`markdown` / `plain_text` / `ocr_text`）
- 不改 `chat.py` 里同名的 `sessions`
- 不更新 README 模块表

## Decisions

### 1. 用 frozen dataclass，不用元组或 NamedTuple

在 `rag_service.py` 模块级增加两个结果类型，风格对齐 `CurrentUser`：

```python
@dataclass(frozen=True, slots=True)
class ImageOcrReplacement:
    text_for_embedding: str
    concatenated_ocr: str | None

@dataclass(frozen=True, slots=True)
class PreparedIngest:
    text_for_embedding: str
    stored_markdown: str | None
    stored_plain_text: str | None
    stored_ocr_text: str | None
    stored_image_keys: list[str]
```

`text_for_embedding` 始终有值，只交给 `split_text`。`stored_*` 只交给 `save_knowledge_file`。PDF 路径里 `text_for_embedding` 和 `stored_markdown` 不是同一份字符串，字段名把这件事说清楚。

`prepare_ingest` / `replace_images_with_ocr` 返回对象，调用方写 `prepared.text_for_embedding`，禁止再按位置解包。

备选：只把元组元素改名，仍 `return a, b, c, d, e`。否决：调用处仍靠顺序，改名解决不了「记错第几个」。

备选：`NamedTuple`。否决：仍然可以 `a, b, c, d, e = result`，五元组问题会回来。

备选：`TypedDict`。否决：没有属性访问，也没有构造期字段约束。

### 2. 命名对照（实现必须按这张表改）

主流程读起来应是：

```python
prepared = await RagService.prepare_ingest(...)
chunks = RagService.split_text(prepared.text_for_embedding, object_key, filename)
vectors = await EmbeddingService().get_batch_embedding(chunks)
points = RagService.build_qdrant_points(chunks, vectors)
await RagService.save_knowledge_file(
    ...,
    image_keys=prepared.stored_image_keys,
    markdown=prepared.stored_markdown,
    plain_text=prepared.stored_plain_text,
    ocr_text=prepared.stored_ocr_text,
)
```

| 现在 | 改为 | 原因 |
|------|------|------|
| `prepare_ingest` 五元组 | `PreparedIngest` | 嵌入稿 vs 落库稿 |
| `replace_markdown_images` 两元组 | `ImageOcrReplacement` | 替换后全文 vs 各图 OCR 拼接 |
| `replace_markdown_images` | `replace_images_with_ocr` | 方法名补上 OCR，不再只说 replace |
| `build_points_data` | `build_qdrant_points` | 产物是 Qdrant point |
| `embedding: list[float]` | `vectors: list[list[float]]` | 实际是一批向量 |
| `sessions` / `session` | `header_sections` / `section` | 按标题切开的章节，不是会话 |
| `final_docs` | `chunks` | 二次切分后的嵌入块 |
| `replaced` | `text_for_embedding` | 替换图之后就是嵌入稿 |
| `text`（单张 OCR） | `ocr_result` | 避免和整篇 `text` 撞名 |
| `data`（下载字节） | `file_bytes` / `image_bytes` | 标明是文件体 |
| `keys`（拷图） | `stored_image_keys` | 与 `PreparedIngest` 字段对齐 |
| `markdown`（MinerU 原文，prepare 内部） | `converted_markdown` | 和嵌入稿区分 |

保持不变：`prepare_ingest`、`split_text`、`copy_markdown_images`、`save_knowledge_file`、`build_knowledge_base`，以及 `_suffix` 等私有辅助方法。`copy_markdown_images` 已经说明「拷走配图」，不必再改。

落库方法形参继续用 ORM 列名，例如 `save_knowledge_file(..., markdown=prepared.stored_markdown, ...)`。调用处能看出「结果对象字段 → 表列」，表本身不改。

### 3. 测试跟着字段走，不断言元组顺序

`tests/service/test_rag_service.py` 里所有 `a, b, c, d, e = prepare_ingest(...)` 改成读 `PreparedIngest` 字段。`build_knowledge_base` 的 fake 返回 `PreparedIngest(...)`，不再返回五元组。行为断言（txt 跳过 MinerU、png 走 OCR、PDF 保留原 markdown 图语法、单张 OCR 失败继续）保持原样。

## Risks / Trade-offs

- [漏改一处仍按五元组解包] → 类型检查和单测会立刻失败；`prepare_ingest` 的公开返回类型改掉后，旧解包无法通过。
- [frozen dataclass 不能原地改字段] → 本流程本就是构造一次后只读，符合用法。
- [方法改名让未提交的本地补丁难 rebase] → 只改两个误导方法；其余入口名不动。

## Migration Plan

内部 Python 调用，无部署步骤。回滚：还原本 change 的 `rag_service.py` 与对应测试。

## Open Questions

无。结果类型、字段名、改哪些方法名已在 Decisions 里定死。
