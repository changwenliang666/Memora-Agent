"""知识库入库（RAG）编排：按类型解析文件、切块、向量化、写库。"""

import base64
import re
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

import httpx
from langchain_core.documents import Document
from langchain_mineru import MinerULoader
from qdrant_client.models import PointStruct, UpdateStatus

from app.core.config import config
from app.db.database import AsyncSessionLocal
from app.db.models.knowledge_file import KnowledgeFile
from app.service.embedding_service import EmbeddingService
from app.service.ocr_service import OcrService
from app.service.qdrant_service import qdrantService
from app.service.text_split import split_ingest_text
from app.service.webhook_service import WebhookService
from app.storage.r2 import R2Storage

# Markdown 行内图片语法：![alt](url)，用于抽取 MinerU 产出文档里的配图链接
_MARKDOWN_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
# 需要走 MinerU 转 Markdown 的办公文档
_CONVERTER_EXTS = frozenset({".pdf", ".docx"})
# 可直接按 UTF-8 文本读取、无需 OCR / 转换
_TEXT_EXTS = frozenset({".txt", ".md"})
# 走视觉 OCR 的图片
_IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg"})


@dataclass(frozen=True, slots=True)
class ImageOcrItem:
    """单张图的 OCR 结果，落库时转成 JSON 对象。"""

    image_key: str | None
    text: str


@dataclass(frozen=True, slots=True)
class ImageOcrReplacement:
    """Markdown 配图被 OCR 替换后的结果。"""

    text_for_embedding: str
    ocr_results: list[ImageOcrItem]


@dataclass(frozen=True, slots=True)
class PreparedIngest:
    """按文件类型准备好的入库材料。

    ``text_for_embedding`` 交给切块；``stored_*`` 仅在向量写入成功后落库。
    """

    text_for_embedding: str
    stored_markdown: str | None
    stored_plain_text: str | None
    stored_ocr_results: list[ImageOcrItem]
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

        ``.md`` / ``.pdf`` / ``.docx`` 走 Markdown 装箱（表和围栏代码不内切）。
        ``.txt`` 与独立图片 OCR 结果走纯文本 500/50 递归切。
        """
        return split_ingest_text(text, object_key, filename)

    @staticmethod
    def _try_copy_markdown_image(
        url: str,
        object_key: str,
        fallback_index: int,
        storage: R2Storage,
    ) -> str | None:
        """把一张 Markdown 配图拷到源文件前缀下的 ``images/``。失败返回 None。"""
        prefix = RagService._file_prefix(object_key)
        # 文件名优先取 URL path 的 basename，取不到时用序号兜底
        name = PurePosixPath(urlparse(url).path).name or f"image-{fallback_index}.jpg"
        try:
            image_bytes = RagService._download(url)
            key = f"{prefix}/images/{name}"
            storage.put_object(key, image_bytes, RagService._image_content_type(name))
            return key
        except Exception:
            # 下载或上传失败都跳过这张图，不影响其它图
            return None

    @staticmethod
    async def replace_images_with_ocr(
        markdown: str, object_key: str
    ) -> ImageOcrReplacement:
        """把有检索价值的 Markdown 配图换成视觉文本，并只拷这些图。

        对每张 ``![alt](url)`` 调配图视觉接口。KEEP 才拷 R2、写入 ``ocr_results``，
        嵌入稿换成识别文本。SKIP 或调用失败则删掉图片语法，不拷不记账，不中断整篇。
        拷贝失败时该条 ``image_key`` 为 None，仍保留识别文本。
        """
        matches = list(_MARKDOWN_IMAGE.finditer(markdown))
        if not matches:
            return ImageOcrReplacement(text_for_embedding=markdown, ocr_results=[])

        ocr = OcrService()
        storage = R2Storage(config.r2)
        text_for_embedding = markdown
        ocr_results: list[ImageOcrItem] = []
        for index, match in enumerate(matches):
            url = match.group(2).strip()
            try:
                vision_text = await ocr.invoke_markdown_figure(url)
            except Exception:
                # 视觉接口异常按 SKIP 处理，不中断整篇
                vision_text = None
            if vision_text is None:
                # SKIP / 失败：删掉图片语法，不拷图、不记账
                text_for_embedding = text_for_embedding.replace(match.group(0), "", 1)
                continue
            # KEEP：拷图到 R2（拷失败 image_key 为 None），嵌入稿替换为识别文本
            image_key = RagService._try_copy_markdown_image(
                url, object_key, index, storage
            )
            ocr_results.append(ImageOcrItem(image_key=image_key, text=vision_text))
            text_for_embedding = text_for_embedding.replace(match.group(0), vision_text, 1)
        return ImageOcrReplacement(
            text_for_embedding=text_for_embedding,
            ocr_results=ocr_results,
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
        storage = R2Storage(config.r2)
        stored_image_keys: list[str] = []
        for index, match in enumerate(_MARKDOWN_IMAGE.finditer(markdown)):
            url = match.group(2).strip()
            image_key = RagService._try_copy_markdown_image(
                url, object_key, index, storage
            )
            if image_key is not None:
                stored_image_keys.append(image_key)
        return stored_image_keys

    @staticmethod
    def _ocr_results_payload(ocr_results: list[ImageOcrItem]) -> list[dict]:
        """把 OCR 结果转成可落库的 JSON dict 列表（image_key + text）。"""
        return [{"image_key": item.image_key, "text": item.text} for item in ocr_results]

    @staticmethod
    async def save_knowledge_file(
        user_id: int,
        filename: str,
        object_key: str,
        size: int,
        image_keys: list[str],
        markdown: str | None,
        plain_text: str | None,
        ocr_results: list[ImageOcrItem],
    ) -> None:
        """把知识文件元数据写入数据库。

        仅在 Qdrant upsert 成功后调用，避免向量没写上却留下孤立记录。
        markdown / plain_text 按文件类型互斥填充：
        PDF/DOCX 有 markdown，txt/md 有 plain_text。
        ocr_results 在视觉模型跑过时按图一条，否则为空列表。

        Args:
            user_id: 上传用户 id。
            filename: 原始文件名。
            object_key: 源文件在 R2 上的 key。
            size: 文件字节数。
            image_keys: 转存到 R2 的配图 key 列表。
            markdown: MinerU 转换结果；非转换类文件为 None。
            plain_text: 纯文本内容；非 txt/md 为 None。
            ocr_results: 按图 OCR 结果；未跑视觉模型时为空列表。
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
                    ocr_results=RagService._ocr_results_payload(ocr_results),
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
        - 图片（png/jpg/jpeg）：下载后转 data URL 做 OCR，OCR 结果既当嵌入文本，
          也作为 ``stored_ocr_results`` 的唯一一条（``image_key`` 为源文件 object_key）。
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
            # 独立图片：下载后转 data URL 做 OCR，识别文本即嵌入文本
            file_bytes = RagService._download(file_url)
            content_type = RagService._image_content_type(filename)
            ocr_text = await OcrService().invoke(
                f"data:{content_type};base64,{base64.b64encode(file_bytes).decode('ascii')}"
            )
            return PreparedIngest(
                text_for_embedding=ocr_text,
                stored_markdown=None,
                stored_plain_text=None,
                stored_ocr_results=[ImageOcrItem(image_key=object_key, text=ocr_text)],
                stored_image_keys=[],
            )

        if suffix in _TEXT_EXTS:
            # 纯文本：按 UTF-8 解码，原文即嵌入文本
            file_bytes = RagService._download(file_url)
            plain_text = file_bytes.decode("utf-8")
            return PreparedIngest(
                text_for_embedding=plain_text,
                stored_markdown=None,
                stored_plain_text=plain_text,
                stored_ocr_results=[],
                stored_image_keys=[],
            )

        if suffix in _CONVERTER_EXTS:
            # PDF/DOCX：MinerU 转 Markdown，再 OCR 替换配图并转存 R2
            mineru_config = config.mineru
            if mineru_config.api_key is None:
                raise Exception("mineru api key 不存在")
            loader = MinerULoader(
                source=file_url,
                mode="precision",
                token=mineru_config.api_key,
            )
            docs = loader.load()
            # MinerU 按页/段返回多个 Document，合并成完整 Markdown
            converted_markdown = "\n\n".join(doc.page_content for doc in docs)
            replacement = await RagService.replace_images_with_ocr(
                converted_markdown, object_key
            )
            # 只统计成功转存 R2 的图（image_key 非 None）
            stored_image_keys = [
                item.image_key
                for item in replacement.ocr_results
                if item.image_key is not None
            ]
            return PreparedIngest(
                text_for_embedding=replacement.text_for_embedding,
                stored_markdown=converted_markdown,
                stored_plain_text=None,
                stored_ocr_results=replacement.ocr_results,
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
            # 1. 按文件类型解析，产出嵌入文本和附属产物
            prepared = await RagService.prepare_ingest(file_url, object_key, filename)
            # 2. 切块；没有任何块（如空文件）直接结束
            chunks = RagService.split_text(
                prepared.text_for_embedding, object_key, filename
            )
            if len(chunks) == 0:
                return

            # 3. 批量向量化，组装写入点并 upsert 到 Qdrant
            vectors = await EmbeddingService().get_batch_embedding(chunks)
            points = RagService.build_qdrant_points(chunks, vectors)
            update_status = qdrantService.upsert(points)
            if update_status.status == UpdateStatus.COMPLETED:
                # 4. 向量写入成功才落库元数据、发成功 webhook
                await RagService.save_knowledge_file(
                    user_id=user_id,
                    filename=filename,
                    object_key=object_key,
                    size=size,
                    image_keys=prepared.stored_image_keys,
                    markdown=prepared.stored_markdown,
                    plain_text=prepared.stored_plain_text,
                    ocr_results=prepared.stored_ocr_results,
                )
                WebhookService.send_knowledge_base_build_success(filename, username)
            else:
                # Qdrant 未确认完成，按失败处理
                raise Exception("建库失败")
        except Exception as e:
            # 统一兜底：记录内部异常，对外只暴露「建库失败」
            print(e)
            raise Exception("建库失败")
