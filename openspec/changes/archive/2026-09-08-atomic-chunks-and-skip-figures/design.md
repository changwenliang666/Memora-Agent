## Context

见 `proposal.md` 的 Why。`RagService.split_text` 对所有类型先 `MarkdownHeaderTextSplitter` 再 `RecursiveCharacterTextSplitter`（500/50，分隔符含 `\n`、`;`、空格和空串），然后把 `h1/h2/h3` metadata 覆盖成只有 `source` / `filename`。`OcrService.invoke` 只要求认字；`replace_images_with_ocr` 对每张 Markdown 配图都 OCR、拷 R2、写入 `ocr_results`（失败也留空字符串）。独立图片路径同样调用 `OcrService.invoke`，但必须继续「整图必留」。切分与 OCR 都在 `RagService` 里。Qdrant payload 的 `content` 就是 chunk 正文。

## Goals / Non-Goals

**Goals:**

- Markdown 形态文本按 block 装箱切分，表和围栏代码不内切
- Markdown 配图同一轮视觉调用判 SKIP，无价值或失败不落 R2 / `ocr_results` / `image_keys`
- 切分离开 `RagService`，OCR 抽图仍由它编排
- 独立图片与 `.txt` 保持纯文本切分，独立图片不走 SKIP

**Non-Goals:**

- 不改 500 / 50 数值，不上新切分依赖
- 不拦独立上传的 png/jpg/jpeg
- 不改 `stored_markdown`（MinerU 原文图链保留）
- 不改 HTTP API、表结构、embedding 模型
- 不更新 `chat.py` 里的 `/test-mineru` 实验接口

## Decisions

### 1. 按后缀选择切分形态，而不是看「像不像 Markdown」

`prepare_ingest` 之后，PDF/DOCX 的 `text_for_embedding` 已是 Markdown，但 `filename` 仍是 `.pdf` / `.docx`。`split_text(text, object_key, filename)` 继续用后缀分流：

- `.md`、`.pdf`、`.docx` → Markdown 装箱
- `.txt`、`.png`、`.jpg`、`.jpeg` → 现有 `RecursiveCharacterTextSplitter`（500/50）

备选：给 `split_text` 加 `kind` 参数。否决：调用点已有 filename，三种转换类后缀固定走 Markdown，不必改签名。

### 2. 自写 block 扫描 + 装箱，不用 LangChain 标题切分器切 Markdown

Markdown 路径不再调用 `MarkdownHeaderTextSplitter`（它会把围栏里的 `#` 当成标题）。顺序扫成 block：围栏代码（行首 `` ``` `` / `~~~` 配对）优先，其次 HTML `<table` … `</table>`，其次连续管道表行，其次 ATX `#` / `##` / `###`，其余为散文。未闭合的表或围栏吃到文末，仍当一块原子。围栏内的表和 `#` 属于该围栏。

装箱：按 heading 栈分组；散文块用现有递归切分器；原子块能塞进当前桶就塞，塞不下先封桶再独占一块；原子块超过 500 字整块溢出。heading 路径写入 metadata，再合并 `source` / `filename`，禁止整份覆盖。

备选：占位符替换后再递归切。否决：占位符可能撞上用户原文，且仍解决不了标题误切围栏。

备选：超长表按行切并重复表头。否决：已选方案 A，整块入库。

### 3. 切分模块独立，`RagService` 只做门面

新增模块（如 `service/text_split.py`）承载扫描、装箱、纯文本切分。`RagService.split_text` 保留为入库入口，按后缀委托。OCR、配图拷贝、`prepare_ingest`、写 Qdrant / 库仍在 `RagService`。

备选：继续堆在 `rag_service.py`。否决：切分状态机和入库编排混在一起，正是当前难读的原因。

### 4. Markdown 配图与独立图片用不同视觉契约

`OcrService` 拆成两条调用，避免独立图片吃到 SKIP：

- 独立图片：仍「只输出可嵌入文本」，永不按装饰跳过
- Markdown 配图：无检索价值时整段 trim 后仅输出 `SKIP`（大小写不敏感）；有价值则只输出精炼文本，不要 JSON、不要解释

解析：trim 后等于 `SKIP` 才跳过；模型多写了一句则当作 KEEP，宁可多留一段字，也不误删图表。返回空串或抛错视为识别失败，与 SKIP 同样不落库。

备选：同一提示词加 `allow_skip` 开关。否决：独立图片一旦误用 SKIP 提示会把整份文件判空；两条提示更不容易混。

备选：先分类再 OCR。否决：多一次调用，用户要求用提示词在同一轮判别。

### 5. `replace_images_with_ocr`：先判别，KEEP 才拷贝和记账

对每个 `![...](url)`：

1. 调 Markdown 配图视觉接口
2. SKIP 或失败：嵌入稿删除该图片语法，不拷 R2，不追加 `ocr_results`
3. KEEP：拷 R2（失败则 `image_key=None` 仍记账），追加 `ocr_results`，嵌入稿换成识别文本

`image_keys` 继续从 `ocr_results` 里 `image_key is not None` 导出。`stored_markdown` 仍是替换前的 MinerU 原文。

## Risks / Trade-offs

- [视觉模型把有用的图标成 SKIP] → 只认整段等于 `SKIP`；图表/流程图在提示词里明确列为 KEEP。误删无法从 `ocr_results` 找回，可对同一文件重新入库。
- [模型在有用图上输出 `SKIP` 加解释] → 按 KEEP 收下整段，可能把一句元话语写进向量，优于丢掉图表。
- [超大 HTML 表进入单个 embedding] → 接受溢出；Qwen embedding 窗口远大于常见 MinerU 表。不为这一轮加硬上限。
- [残缺 HTML / 未闭合围栏] → 吃到文末当一块，避免从中间切开；极端脏稿可能得到一块很大的 chunk。
- [`ocr_results` 条数少于 Markdown 配图数] → 预期行为；测试从「失败占空位」改为「省略」。
- [独立图片与配图提示词分叉后被调用反] → 独立路径只调 extract 接口，Markdown 路径只调 figure 接口；测试分别 mock。

## Migration Plan

1. 抽出切分模块，接上 `split_text` 分流；补表 / 代码 / 围栏内 `#` / `.txt` 的单测
2. 改 `OcrService` 与 `replace_images_with_ocr`；更新现有「失败仍留空条」的测试
3. 回滚：恢复 `RagService` 内原切分与「每图必 OCR 必记账」；已写入的跳过图不会自动补拷

## Open Questions

无。切分形态按后缀、原子块溢出、SKIP 整段匹配、独立图片不拦，已在探索中定下来。
