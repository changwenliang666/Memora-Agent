# upload-mineru-raw-output-to-r2

## Why

MinerU 转换 PDF/DOCX 后，系统只把视觉判定为「有检索价值」的配图拷到 R2，原始 markdown 只落 MySQL，被 SKIP 或识别失败的配图字节直接丢弃。出现「用户上传的 PDF 有 5 张图，OCR 只处理了 3 张」这类问题时，没有 MinerU 的原始产出可对账，无法区分是转换器漏图、相对路径解析失败，还是视觉模型 SKIP，排查只能靠猜。

## What Changes

- MinerU 转换成功后，把转换器的原始产出完整归档到 R2：原始 markdown（保留 `images/xxx` 相对引用原文）和 zip 内全部配图字节。
- 归档位置固定在源文件前缀下的独立段 `{prefix}/mineru/`（markdown + `images/` 子目录），与现有 `{prefix}/images/`（仅 KEEP 图）互不覆盖；markdown 里的相对引用下载归档后仍可对照解析。
- 归档对每张图、每个文件独立执行，单个失败只记日志跳过，不阻断建库主流程（与现有配图拷贝的失败语义一致）。
- 不改数据库结构：归档 key 可由源文件 `object_key` 推导，排查时按前缀列目录即可。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `knowledge-ingest`: 新增「MinerU 原始产出归档」需求——PDF/DOCX 转换成功后必须把原始 markdown 和全部配图字节上传到源文件前缀下的 `mineru/` 段，归档结果不受配图 KEEP/SKIP 判定影响，单个归档失败不阻断建库。

## Impact

- 代码：`src/app/service/rag_service.py` 的 PDF/DOCX 解析路径（`prepare_ingest`）新增归档步骤；可能新增一个小型归档辅助函数。
- 存储：R2 上每个转换类文件多出 `mineru/` 段若干对象（1 个 markdown + N 张配图），存储量随转换文件数线性增长。
- 测试：`tests/service/test_rag_service.py` 需覆盖归档行为（全部配图上传、失败不阻断、与 KEEP/SKIP 判定解耦）。
- 无 API、数据库结构、依赖变更。
