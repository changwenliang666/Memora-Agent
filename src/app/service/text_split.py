"""入库文本切分：Markdown 结构装箱（表 / 围栏代码不内切）+ 纯文本递归切分。"""

import re
from dataclasses import dataclass
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 切块目标大小（字符数）
CHUNK_SIZE = 500
# 相邻块之间的重叠字符数，避免语义在边界处被截断
CHUNK_OVERLAP = 50
# 需要按 Markdown 结构装箱切分的文件后缀
_MARKDOWN_SUFFIXES = frozenset({".md", ".pdf", ".docx"})
# ATX 标题行：1~3 个 # 开头，捕获组为级别和标题文本
_ATX_HEADING = re.compile(r"^(#{1,3})\s+(.+)$")
# 管道表格行：以 | 开头、| 结尾
_PIPE_ROW = re.compile(r"^\|.+\|$")
# 纯文本递归切分的分隔符优先级：段落 > 行 > 中英文句读 > 词 > 字符
_PLAIN_SEPARATORS = ["\n\n", "\n", "。", "；", ";", ". ", " ", ""]


@dataclass(frozen=True, slots=True)
class _Block:
    """扫描出的文本块。

    kind 取值：
    - ``atomic``：不可内切的整体（围栏代码块、HTML 表格、管道表格）。
    - ``heading``：ATX 标题行，``level`` / ``title`` 有效。
    - ``prose``：普通散文，超长时可递归切小。
    """

    kind: str
    text: str
    level: int = 0
    title: str = ""


def _plain_splitter() -> RecursiveCharacterTextSplitter:
    """构造纯文本递归切分器，按 CHUNK_SIZE / CHUNK_OVERLAP 切。"""
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=_PLAIN_SEPARATORS,
    )


def _fence_marker(line: str) -> str | None:
    """识别围栏代码块标记行，返回 ``` 或 ~~~；非围栏行返回 None。"""
    stripped = line.strip()
    if stripped.startswith("```"):
        return "```"
    if stripped.startswith("~~~"):
        return "~~~"
    return None


def _is_special_line(line: str) -> bool:
    """判断是否为特殊行（围栏 / HTML 表格 / 管道表格 / 标题）。

    散文扫描遇到特殊行会停下，交给对应的原子或标题逻辑处理。
    """
    stripped = line.strip()
    if _fence_marker(line) is not None:
        return True
    if "<table" in stripped.lower():
        return True
    if _PIPE_ROW.match(stripped):
        return True
    if _ATX_HEADING.match(stripped):
        return True
    return False


def _scan_blocks(text: str) -> list[_Block]:
    """把整篇文本按行扫描成有序块列表。

    围栏代码块、HTML 表格、管道表格整体保留为 atomic 块（不内切）；
    ATX 标题单独成 heading 块；其余连续普通行合并为 prose 块。
    """
    lines = text.splitlines(keepends=True)
    blocks: list[_Block] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        marker = _fence_marker(line)
        if marker is not None:
            # 围栏代码块：吃到同标记的结束行（没有结束行就吃到文末）
            start = index
            index += 1
            while index < len(lines) and _fence_marker(lines[index]) != marker:
                index += 1
            if index < len(lines):
                index += 1
            blocks.append(_Block("atomic", "".join(lines[start:index])))
            continue

        if "<table" in line.lower():
            # HTML 表格：从 <table> 吃到包含 </table> 的行为止
            start = index
            index += 1
            while index < len(lines):
                combined = "".join(lines[start:index])
                if "</table>" in combined.lower():
                    break
                index += 1
            if "</table>" not in "".join(lines[start:index]).lower() and index < len(lines):
                index += 1
            blocks.append(_Block("atomic", "".join(lines[start:index])))
            continue

        if _PIPE_ROW.match(line.strip()):
            # 管道表格：连续的 |...| 行整体作为一个 atomic 块
            start = index
            index += 1
            while index < len(lines) and _PIPE_ROW.match(lines[index].strip()):
                index += 1
            blocks.append(_Block("atomic", "".join(lines[start:index])))
            continue

        heading = _ATX_HEADING.match(line.strip())
        if heading is not None:
            # ATX 标题：单独成块，记录级别（# 个数）和标题文本
            blocks.append(
                _Block(
                    "heading",
                    line,
                    level=len(heading.group(1)),
                    title=heading.group(2).strip(),
                )
            )
            index += 1
            continue

        # 普通散文：一直吃到下一个特殊行为止，合并为一个 prose 块
        start = index
        index += 1
        while index < len(lines) and not _is_special_line(lines[index]):
            index += 1
        blocks.append(_Block("prose", "".join(lines[start:index])))
    return blocks


def _heading_metadata(
    source: str, filename: str, h1: str | None, h2: str | None, h3: str | None
) -> dict[str, str]:
    """组装 chunk metadata：来源信息加上当前标题层级（有才写入）。"""
    metadata = {"source": source, "filename": filename}
    if h1 is not None:
        metadata["h1"] = h1
    if h2 is not None:
        metadata["h2"] = h2
    if h3 is not None:
        metadata["h3"] = h3
    return metadata


def split_markdown(text: str, object_key: str, filename: str) -> list[Document]:
    """按 Markdown 结构装箱：表和围栏代码不内切，散文按 500/50 切。"""
    if not text:
        return []

    splitter = _plain_splitter()
    chunks: list[Document] = []
    bucket: list[str] = []  # 正在装箱的文本片段
    bucket_len = 0  # bucket 累计字符数
    # 当前命中的标题层级，会写入后续每个 chunk 的 metadata
    h1: str | None = None
    h2: str | None = None
    h3: str | None = None

    def metadata() -> dict[str, str]:
        """按当前标题层级生成 chunk metadata。"""
        return _heading_metadata(object_key, filename, h1, h2, h3)

    def flush() -> None:
        """把 bucket 累积的内容结算成一个 chunk（去空白后为空则丢弃）。"""
        nonlocal bucket_len
        if not bucket:
            return
        content = "".join(bucket).strip()
        bucket.clear()
        bucket_len = 0
        if content:
            chunks.append(Document(page_content=content, metadata=metadata()))

    def append_piece(piece: str) -> None:
        """把片段装进 bucket：装不下先 flush 另起一箱；装箱后超限也立即结算。"""
        nonlocal bucket_len
        if not piece:
            return
        if bucket_len > 0 and bucket_len + len(piece) > CHUNK_SIZE:
            flush()
        bucket.append(piece)
        bucket_len += len(piece)
        if bucket_len > CHUNK_SIZE:
            flush()

    for block in _scan_blocks(text):
        if block.kind == "heading":
            # 标题是语义边界：先结算当前 bucket，再更新标题层级状态
            flush()
            if block.level == 1:
                h1, h2, h3 = block.title, None, None
            elif block.level == 2:
                h2, h3 = block.title, None
            else:
                h3 = block.title
            continue
        if block.kind == "atomic":
            # 原子块（代码 / 表格）不内切，直接装箱
            append_piece(block.text)
            continue
        if len(block.text) <= CHUNK_SIZE:
            # 短散文块直接装箱，与前后内容合箱
            append_piece(block.text)
            continue
        # 长散文块：先结算 bucket，再按纯文本递归切小逐块产出
        flush()
        for piece in splitter.split_text(block.text):
            if piece.strip():
                chunks.append(Document(page_content=piece, metadata=metadata()))

    # 结算尾部残留的 bucket
    flush()
    return chunks


def split_plain(text: str, object_key: str, filename: str) -> list[Document]:
    """纯文本递归切分，不解析 Markdown 结构。"""
    if not text:
        return []
    return _plain_splitter().create_documents(
        [text],
        metadatas=[{"source": object_key, "filename": filename}],
    )


def split_ingest_text(text: str, object_key: str, filename: str) -> list[Document]:
    """按文件后缀选择 Markdown 装箱或纯文本切分。"""
    suffix = Path(filename).suffix.lower()
    if suffix in _MARKDOWN_SUFFIXES:
        return split_markdown(text, object_key, filename)
    return split_plain(text, object_key, filename)
