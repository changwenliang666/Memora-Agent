## Context

动机见 `proposal.md`。行为约束见 `specs/knowledge-ingest/spec.md`。

MinerU 精度抽取会下载结果 zip：Markdown 在包内，配图文件也在包内，`path` 形如 `images/img_0.png`。Markdown 里的图链因此有两种形态：

1. 可在线访问的 `http(s)` URL（现有 `replace_images_with_ocr` / `_try_copy_markdown_image` 已按 URL 下载并识别）
2. 相对路径 `images/<hash>.jpg`，对应 zip 里那张图

`MinerULoader.load()` 内部已经走 `extract()`，但只把 `result.markdown` 写进 `page_content`，丢掉 `result.images`。相对路径被原样传给视觉模型和 `httpx.get`，失败后按 SKIP 处理。独立图片路径已经会把字节转成 data URI；配图路径缺的是「相对路径 → 资源」这一步，而不是另一套 KEEP/SKIP。`chat.py` 的 `/test-mineru` 仍用 Loader，本次不改。

## Goals / Non-Goals

**Goals:**

- 两种地址分流后汇入同一套现有配图流程（视觉 KEEP/SKIP、嵌入替换、KEEP 才拷 R2）
- 相对路径从同一次转换的 zip/`images` 取出字节，规范化后再交给上述流程
- 绝对 URL 行为与现网一致，现有 https 单测仍能过

**Non-Goals:**

- 不新造一套 OCR/拷贝策略，不改 KEEP/SKIP 语义
- 不改落库 `markdown` 原文、表结构、HTTP
- 不打开 MinerU 自身的 `ocr=True`
- 不回填已入库的空 `ocr_results`
- 不改独立图片 / txt / md 路径，不改 `/test-mineru`

## Decisions

### 1. 转换出口保留 zip 配图，后续流程不另起炉灶

入库仍要 Markdown + 配图资源，但后续继续调用现有 `replace_images_with_ocr`（KEEP 才记账并拷 R2，SKIP/失败删 markup）。`MinerULoader` 拿不到 `images`，因此 PDF/DOCX 改为直接 `MinerU(token=api_key).extract(...)`，一次拿到 `markdown` 和 `images`。参数对齐当前 Loader：`formula=True`、`table=True`、`ocr=False`、`timeout=1200`、`language="ch"`。`state != "done"` 或 `markdown` 为空仍当转换失败。

备选：继续 `load()`，发现相对路径再另下 `zip_url`。否决：Loader 已经 extract 过一次却把图丢掉，重复下载。

备选：给 Loader 打补丁。否决：包内没有配图出口。

### 2. 按地址形态规范化，再交给现有循环

在现有逐张 `![...](url)` 循环前（或循环开头）判断：

- `http://` / `https://` / `data:` → 视觉模型仍吃该 URI；KEEP 时仍 `httpx.get` 再 `put_object`（现逻辑）
- 相对路径 → 用字节表解析；命中则 `data:{content_type};base64,...` 交给同一个 `invoke_markdown_figure`，KEEP 时用原字节 `put_object`，禁止 `httpx.get(相对路径)`
- 相对路径解析失败 → 与现网「识别失败」相同：删 markup、不记账、不拷图

字节表至少索引每张 `Image` 的 `path`、`name`、`images/{name}`。查找顺序：原串、去掉 `./`、basename。R2 key 仍是 `{file_prefix}/images/{basename}`。同一相对路径出现多次按出现顺序各走一遍流程；可用路径缓存视觉结果，避免两张相同 hash 打两次模型。

备选：先全部 PUT 到 R2 再预签名给视觉模型。否决：独立图片已用 data URI；预签名有过期和 Qwen 能否打到 R2 的问题。

### 3. 不改 `stored_markdown`，不把 SDK 写成顶层依赖

落库 markdown 仍是转换器原文（相对路径也原样保留）。`from mineru import MinerU` 使用 `langchain-mineru` 已带入的 `mineru-open-sdk`，本次不改 `pyproject.toml`。

备选：打开 MinerU `ocr=True` 让扫描 PDF 直接出正文。否决：不解决相对路径支路，且改变转换耗时与质量。本变更只补「取到资源 → 现有流程」。

## Risks / Trade-offs

- [扫描件的 `markdown` 列仍可能只有 `![](images/...)`] → 接受；规格要求保留原文。可检索内容在嵌入稿和 `ocr_results`。
- [Markdown 引用与 `Image.path`/`name` 对不上] → 当识别失败，与现网单张失败相同；三键索引降低概率。
- [直接依赖未写入 pyproject] → 接受；`langchain-mineru` 已声明 `mineru-open-sdk`。
- [整页图走视觉模型比 MinerU 自带 OCR 更慢] → 接受；KEEP/SKIP 不变，装饰页仍可 SKIP。
- [已入库空 `ocr_results` 不会变] → 重新上传该 PDF。

## Migration Plan

1. 转换带出配图字节；相对路径规范化后接入现有识别/拷贝；https 配图回归保持通过
2. 部署代码即可，无 schema / HTTP 变更
3. 回滚：恢复 `MinerULoader` 与纯 URL 识别；已按新支路写入的 `ocr_results` / `image_keys` 可保留
4. 受影响的旧行需重新 complete / 建库

## Open Questions

无。两种地址分流、相对路径从 zip/`images` 取资源再交现有流程、markdown 原文不改，均已定。
