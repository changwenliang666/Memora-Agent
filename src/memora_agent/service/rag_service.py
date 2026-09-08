import base64
import re
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

import httpx
from langchain_core.documents import Document
from langchain_mineru import MinerULoader
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)
from qdrant_client.models import PointStruct, UpdateStatus

from memora_agent.core.config import config
from memora_agent.db.database import AsyncSessionLocal
from memora_agent.db.models.knowledge_file import KnowledgeFile
from memora_agent.service.embedding_service import EmbeddingService
from memora_agent.service.ocr_service import OcrService
from memora_agent.service.qdrant_service import qdrantService
from memora_agent.service.webhook_service import WebhookService
from memora_agent.storage.r2 import R2Storage

# Markdown 行内图片语法：![alt](url)，用于抽取 MinerU 产出文档里的配图链接
_MARKDOWN_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
# 需要走 MinerU 转 Markdown 的办公文档
_CONVERTER_EXTS = frozenset({".pdf", ".docx"})
# 可直接按 UTF-8 文本读取、无需 OCR / 转换
_TEXT_EXTS = frozenset({".txt", ".md"})
# 走视觉 OCR 的图片
_IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg"})


@dataclass(frozen=True, slots=True)
class ImageOcrReplacement:
    """Markdown 配图被 OCR 替换后的结果。"""

    text_for_embedding: str
    concatenated_ocr: str | None


@dataclass(frozen=True, slots=True)
class PreparedIngest:
    """按文件类型准备好的入库材料。

    ``text_for_embedding`` 交给切块；``stored_*`` 仅在向量写入成功后落库。
    """

    text_for_embedding: str
    stored_markdown: str | None
    stored_plain_text: str | None
    stored_ocr_text: str | None
    stored_image_keys: list[str]


class RagService:
    """知识库入库编排服务。

    按文件类型把上传文件转成可嵌入文本，切块后写入 Qdrant，
    并在向量写入成功后落库 KnowledgeFile 元数据。
    入口是 ``build_knowledge_base``，其余方法按解析 / 切分 / 写库拆开。
    """

    @staticmethod
    def build_qdrant_points(
        documents: list[Document], vectors: list[list[float]]
    ) -> list[PointStruct]:
        """把切块文档和对应向量组装成 Qdrant 写入点。

        每个 Document 与 vector 按位置一一对应。point id 用 UUID 生成，
        payload 保留文档全部 metadata，并额外写入 ``content``（即 page_content），
        检索时可以直接从 payload 取原文。

        Args:
            documents: 切块后的 LangChain Document 列表。
            vectors: 与 documents 等长的向量列表。

        Returns:
            可直接交给 Qdrant upsert 的 PointStruct 列表。
        """
        points = []
        for document, vector in zip(documents, vectors):
            points.append(
                PointStruct(
                    id=uuid.uuid4(),
                    vector=vector,
                    payload={**document.metadata, "content": document.page_content},
                )
            )
        return points

    @staticmethod
    def _suffix(filename: str) -> str:
        """取文件名后缀并转成小写，例如 ``Report.PDF`` -> ``.pdf``。

        后续 ``prepare_ingest`` 用这个后缀决定走图片 OCR、纯文本还是 MinerU。
        """
        return Path(filename).suffix.lower()

    @staticmethod
    def _file_prefix(object_key: str) -> str:
        """从对象存储 key 取出父目录前缀。

        例如 ``user/1/abc/file.pdf`` -> ``user/1/abc``。
        Markdown 配图会写到 ``{prefix}/images/`` 下，跟源文件放在同一层级。
        """
        return str(PurePosixPath(object_key).parent)

    @staticmethod
    def _image_content_type(name: str) -> str:
        """根据文件名后缀推断图片 Content-Type，供 R2 上传和 OCR data URL 使用。

        目前只识别 png / jpg / jpeg；其它后缀一律返回 ``application/octet-stream``。
        """
        suffix = Path(name).suffix.lower()
        if suffix == ".png":
            return "image/png"
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        return "application/octet-stream"

    @staticmethod
    def _download(url: str) -> bytes:
        """按 URL 下载文件二进制内容。

        跟随重定向，超时 60 秒。HTTP 非 2xx 时直接抛出 httpx 异常，
        由上层 ``build_knowledge_base`` 统一转成「建库失败」。
        """
        response = httpx.get(url, follow_redirects=True, timeout=60.0)
        response.raise_for_status()
        return response.content

    @staticmethod
    def split_text(text: str, object_key: str, filename: str) -> list[Document]:
        """把待嵌入文本切成适合向量检索的 Document 块。

        分两步：
        1. 先按 Markdown 标题（h1 / h2 / h3）切开，尽量让同一章节落在一块。
           每个块都会打上 ``source``（对象存储 key）和 ``filename``，方便溯源。
        2. 超过 500 字的章节再用 RecursiveCharacterTextSplitter 二次切分
           （chunk_size=500，overlap=50）。分隔符优先换行，其次中英文句读，
           避免把中文句子从中间硬切。

        Args:
            text: 已经准备好的纯文本 / Markdown / OCR 结果。
            object_key: 源文件在对象存储中的 key，写入 metadata.source。
            filename: 原始文件名，写入 metadata.filename。

        Returns:
            切块后的 Document 列表；空文本时可能为空。
        """
        header_sections: list[Document] = []
        text_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "h1"),
                ("##", "h2"),
                ("###", "h3"),
            ]
        )
        header_sections.extend(text_splitter.split_text(text))
        for section in header_sections:
            section.metadata = {"source": object_key, "filename": filename}

        recursive_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", "。", "；", ";", ". ", " ", ""],
        )
        chunks: list[Document] = []
        for section in header_sections:
            if len(section.page_content) > 500:
                chunks.extend(recursive_splitter.split_documents([section]))
            else:
                chunks.append(section)
        return chunks

    @staticmethod
    async def replace_images_with_ocr(markdown: str) -> ImageOcrReplacement:
        """把 Markdown 里的图片替换成 OCR 文字，供后续切块嵌入。

        MinerU 转出来的 Markdown 常带 ``![alt](url)``。向量检索吃不到图片，
        所以对每张图调 OCR，用识别结果替换原图片语法。
        某张图 OCR 失败时该处替换为空字符串，不中断整篇处理。

        Args:
            markdown: MinerU 产出的原始 Markdown。

        Returns:
            ``ImageOcrReplacement``：
            - text_for_embedding：图片已被 OCR 文字替换后的全文，用于切块嵌入。
            - concatenated_ocr：各图 OCR 结果用空行拼接；没有图片时为 None。
        """
        matches = list(_MARKDOWN_IMAGE.finditer(markdown))
        if not matches:
            return ImageOcrReplacement(text_for_embedding=markdown, concatenated_ocr=None)

        ocr = OcrService()
        text_for_embedding = markdown
        ocr_parts: list[str] = []
        for match in matches:
            url = match.group(2).strip()
            try:
                ocr_result = await ocr.invoke(url)
            except Exception:
                ocr_result = ""
            ocr_parts.append(ocr_result or "")
            text_for_embedding = text_for_embedding.replace(
                match.group(0), ocr_result or "", 1
            )
        return ImageOcrReplacement(
            text_for_embedding=text_for_embedding,
            concatenated_ocr="\n\n".join(ocr_parts),
        )

    @staticmethod
    def copy_markdown_images(markdown: str, object_key: str) -> list[str]:
        """把 Markdown 中的远程配图下载并转存到 R2。

        图片会写到源文件同级的 ``images/`` 目录。文件名优先用 URL path 的 basename，
        解析不到时用 ``image-{序号}.jpg``。单张下载或上传失败会跳过，不影响其它图。

        Args:
            markdown: 含 ``![alt](url)`` 的 Markdown。
            object_key: 源文件对象存储 key，用来计算 ``images/`` 前缀。

        Returns:
            成功写入 R2 的对象 key 列表；没有图或全部失败时为空列表。
        """
        prefix = RagService._file_prefix(object_key)
        storage = R2Storage(config.r2)
        stored_image_keys: list[str] = []
        for match in _MARKDOWN_IMAGE.finditer(markdown):
            url = match.group(2).strip()
            name = PurePosixPath(urlparse(url).path).name or (
                f"image-{len(stored_image_keys)}.jpg"
            )
            try:
                image_bytes = RagService._download(url)
                key = f"{prefix}/images/{name}"
                storage.put_object(key, image_bytes, RagService._image_content_type(name))
                stored_image_keys.append(key)
            except Exception:
                continue
        return stored_image_keys

    @staticmethod
    async def save_knowledge_file(
        user_id: int,
        filename: str,
        object_key: str,
        size: int,
        image_keys: list[str],
        markdown: str | None,
        plain_text: str | None,
        ocr_text: str | None,
    ) -> None:
        """把知识文件元数据写入数据库。

        仅在 Qdrant upsert 成功后调用，避免向量没写上却留下孤立记录。
        markdown / plain_text / ocr_text 按文件类型互斥填充：
        PDF/DOCX 有 markdown，txt/md 有 plain_text，图片有 ocr_text。

        Args:
            user_id: 上传用户 id。
            filename: 原始文件名。
            object_key: 源文件在 R2 上的 key。
            size: 文件字节数。
            image_keys: 转存到 R2 的配图 key 列表。
            markdown: MinerU 转换结果；非转换类文件为 None。
            plain_text: 纯文本内容；非 txt/md 为 None。
            ocr_text: 图片 OCR 或 Markdown 配图 OCR 拼接结果。
        """
        async with AsyncSessionLocal() as session:
            session.add(
                KnowledgeFile(
                    user_id=user_id,
                    filename=filename,
                    object_key=object_key,
                    size=size,
                    image_keys=image_keys,
                    markdown=markdown,
                    plain_text=plain_text,
                    ocr_text=ocr_text,
                )
            )
            await session.commit()

    @staticmethod
    async def prepare_ingest(
        file_url: str,
        object_key: str,
        filename: str,
    ) -> PreparedIngest:
        """按文件类型准备入库文本和附属产物。

        三条路径：
        - 图片（png/jpg/jpeg）：下载后转 data URL 做 OCR，OCR 结果既当嵌入文本也当 stored_ocr_text。
        - 纯文本（txt/md）：按 UTF-8 解码，原文既当嵌入文本也当 stored_plain_text。
        - PDF/DOCX：走 MinerU 转 Markdown，再 OCR 替换配图、把配图转存 R2。
          嵌入用「图片已替换成文字」的文本，stored_markdown 保留 MinerU 原文。

        Args:
            file_url: 可下载的源文件 URL（通常是 R2 预签名地址）。
            object_key: 源文件对象存储 key。
            filename: 原始文件名，用来判断后缀。

        Returns:
            ``PreparedIngest``。text_for_embedding 始终有值；stored_* 按类型填或不填。

        Raises:
            Exception: MinerU api key 缺失，或不支持的文件后缀。
        """
        suffix = RagService._suffix(filename)
        if suffix in _IMAGE_EXTS:
            file_bytes = RagService._download(file_url)
            content_type = RagService._image_content_type(filename)
            ocr_text = await OcrService().invoke(
                f"data:{content_type};base64,{base64.b64encode(file_bytes).decode('ascii')}"
            )
            return PreparedIngest(
                text_for_embedding=ocr_text,
                stored_markdown=None,
                stored_plain_text=None,
                stored_ocr_text=ocr_text,
                stored_image_keys=[],
            )

        if suffix in _TEXT_EXTS:
            file_bytes = RagService._download(file_url)
            plain_text = file_bytes.decode("utf-8")
            return PreparedIngest(
                text_for_embedding=plain_text,
                stored_markdown=None,
                stored_plain_text=plain_text,
                stored_ocr_text=None,
                stored_image_keys=[],
            )

        if suffix in _CONVERTER_EXTS:
            mineru_config = config.mineru
            if mineru_config.api_key is None:
                raise Exception("mineru api key 不存在")
            loader = MinerULoader(
                source=file_url,
                mode="precision",
                token=mineru_config.api_key,
            )
            docs = loader.load()
            converted_markdown = "\n\n".join(doc.page_content for doc in docs)
            replacement = await RagService.replace_images_with_ocr(converted_markdown)
            stored_image_keys = RagService.copy_markdown_images(
                converted_markdown, object_key
            )
            return PreparedIngest(
                text_for_embedding=replacement.text_for_embedding,
                stored_markdown=converted_markdown,
                stored_plain_text=None,
                stored_ocr_text=replacement.concatenated_ocr,
                stored_image_keys=stored_image_keys,
            )

        raise Exception("不支持的文件类型")

    @staticmethod
    async def build_knowledge_base(
        file_url: str,
        object_key: str,
        filename: str,
        user_id: int,
        username: str,
        size: int,
    ):
        """知识库入库主流程：解析 → 切块 → 向量化 → 写入 Qdrant → 落库元数据。

        顺序：
        1. ``prepare_ingest`` 按类型产出嵌入文本和 markdown / 纯文本 / OCR / 配图 key。
        2. ``split_text`` 切块；没有任何块则直接返回（例如空文件）。
        3. 批量打 embedding，组装 PointStruct，upsert 到 Qdrant。
        4. 仅当 Qdrant 返回 COMPLETED 才写 KnowledgeFile，并发飞书成功 webhook。
        5. 任一步失败都打印异常后统一抛出「建库失败」，避免把内部细节漏给调用方。

        Args:
            file_url: 源文件可下载 URL。
            object_key: 源文件在 R2 上的 key。
            filename: 原始文件名。
            user_id: 上传用户 id。
            size: 文件字节数。

        Raises:
            Exception: 切块后写入失败、Qdrant 未完成、或解析过程出错。
        """
        try:
            prepared = await RagService.prepare_ingest(file_url, object_key, filename)
            chunks = RagService.split_text(
                prepared.text_for_embedding, object_key, filename
            )
            if len(chunks) == 0:
                return

            vectors = await EmbeddingService().get_batch_embedding(chunks)
            points = RagService.build_qdrant_points(chunks, vectors)
            update_status = qdrantService.upsert(points)
            if update_status.status == UpdateStatus.COMPLETED:
                await RagService.save_knowledge_file(
                    user_id=user_id,
                    filename=filename,
                    object_key=object_key,
                    size=size,
                    image_keys=prepared.stored_image_keys,
                    markdown=prepared.stored_markdown,
                    plain_text=prepared.stored_plain_text,
                    ocr_text=prepared.stored_ocr_text,
                )
                WebhookService.send_knowledge_base_build_success(filename, username)
            else:
                raise Exception("建库失败")
        except Exception as e:
            print(e)
            raise Exception("建库失败")
