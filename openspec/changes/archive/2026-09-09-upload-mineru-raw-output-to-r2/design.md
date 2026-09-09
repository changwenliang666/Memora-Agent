# Design: upload-mineru-raw-output-to-r2

## Context

`prepare_ingest` 的 PDF/DOCX 分支调用 `MinerU.extract()` 拿到 `ExtractResult`（`markdown: str` + `images: list[Image]`，每个 `Image` 有 `name` / `data` / `path`，`path` 是 zip 内相对路径如 `images/img_0.png`）。当前只有视觉 KEEP 的图经 `_try_copy_markdown_image` 落到 `{prefix}/images/`，其余产物随函数返回即丢弃。R2 上传走现成的 `R2Storage.put_object`（同步 boto3），Content-Type 用 `_image_content_type` 推断。动机见 proposal.md「Why」。

## Goals / Non-Goals

**Goals:**

- 转换成功后立刻把原始 markdown 和全部配图字节归档到 `{prefix}/mineru/`，与 KEEP/SKIP 判定、嵌入结果完全解耦。
- 归档布局复刻 zip 内结构，让排查者下载后 markdown 相对引用可直接对照图片。
- 单个对象归档失败只记日志，不影响其余归档和建库主流程。

**Non-Goals:**

- 不上传完整结果 zip 或 `content_list.json`（用户明确要 markdown 和素材；SDK 未暴露的额外产物不纳入）。
- 不改数据库结构、不在 `KnowledgeFile` 记录归档 key（位置可由 `object_key` 推导）。
- 不做归档对象的清理 / 生命周期策略，不提供查询归档的 API。
- 不改独立图片、纯文本两条入库路径。

## Decisions

### 1. 归档位置：`{prefix}/mineru/`，复刻 zip 布局

- 原始 markdown 固定命名为 `{prefix}/mineru/full.md`（沿用 MinerU 结果 zip 里的惯例文件名；`ExtractResult` 不暴露原始 md 文件名，固定名更便于按约定直接定位）。
- 配图写到 `{prefix}/mineru/images/<name>`，与 raw markdown 中的 `images/<name>` 引用一一对应；用 `Image.name`（basename）而非完整 `path`，与 markdown 引用形式保持一致。
- 备选①复用 `{prefix}/images/`：拒绝——该段语义是「KEEP 且入库成功的图」，混入未处理图会破坏 `image_keys` 与对象的一一对应，也可能与 KEEP 拷贝互相覆盖。
- 备选② `{prefix}/raw/`：与 `mineru/` 等价，选 `mineru/` 是为了明示产物来源，未来换转换器时可再开新段。

### 2. 归档时机：转换成功后、`replace_images_with_ocr` 之前

归档在 `prepare_ingest` 的 `_CONVERTER_EXTS` 分支内、拿到 `result` 校验通过后立即执行。这样即使后续视觉 OCR 抛异常导致建库失败，原始产出已在 R2，可直接对账「转换器出了几张图」。备选「嵌入成功后才归档」：拒绝——那正是最需要排查资料却拿不到的场景。

### 3. 失败语义：逐对象 try/except，记日志跳过

归档函数内部对每个对象单独 try，失败 `print`（与现有错误处理风格一致）后继续下一个，整体不抛异常。归档是辅助产物，不应让调试通道反过来阻断业务主流程。备选「归档失败即建库失败」：拒绝——R2 短暂抖动会拖垮正常入库。

### 4. 实现形态：`RagService` 新增私有静态方法 `_archive_mineru_output`

签名约 `_archive_mineru_output(object_key, markdown, images) -> None`：内部构造 `R2Storage`，先 PUT markdown（`text/markdown; charset=utf-8`），再循环 PUT 配图（复用 `_image_content_type`）。保持同步调用，与现有 `_try_copy_markdown_image` 的同步 `put_object` 风格一致，不引入并发。

## Risks / Trade-offs

- [每个转换文件多出 1 个 md + N 张图的存储占用] → MinerU 配图通常为 KB~数百 KB 级，量可控；如后续膨胀明显，再对 `mineru/` 前缀加桶生命周期规则（本期不做）。
- [顺序上传增加建库耗时] → 配图数量通常个位数到几十，且与现有逐张拷贝同级开销；不引入并发，保持失败语义简单。
- [归档失败被静默跳过，排查时仍可能缺料] → 失败必打日志（含 object_key 与异常），运维可据日志补偿；这是「不阻断主流程」的既定取舍。
