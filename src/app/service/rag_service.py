"""知识库入库（RAG）编排：按类型解析文件、切块、向量化、写库。"""

import base64
import re
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

import httpx
from langchain_core.documents import Document
from mineru import MinerU
from qdrant_client.models import PointStruct, UpdateStatus

from app.core.config import config
from app.service.embedding_service import EmbeddingService
from app.service.knowledge_file_service import knowledgeFileService
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


def _is_remote_url(url: str) -> bool:
    """判断配图地址能不能直接给视觉模型 / httpx。

    MinerU 会产出两种地址：在线 URL，或 zip 内相对路径（如 ``images/hash.jpg``）。
    只有 http(s) 和 data URI 能直接拉；相对路径必须先查本地字节。
    """
    return url.startswith(("http://", "https://", "data:"))


def _image_bytes_table(images) -> dict[str, bytes]:
    """把 MinerU zip 里的配图编成查找表。

    Markdown 有时写 ``images/a.jpg``，有时只写文件名，所以 path / name /
    ``images/{name}`` 三个键都指向同一份 bytes。
    """
    table: dict[str, bytes] = {}
    for image in images:
        table[image.path] = image.data
        table[image.name] = image.data
        table[f"images/{image.name}"] = image.data
    return table


def _lookup_image_bytes(url: str, image_bytes: dict[str, bytes]) -> bytes | None:
    """用相对路径从查找表取图。按原串、去掉 ``./``、basename 依次试。"""
    keys = [url]
    if url.startswith("./"):
        keys.append(url[2:])
    keys.append(PurePosixPath(url).name)
    for key in keys:
        data = image_bytes.get(key)
        if data is not None:
            return data
    return None


def _to_data_uri(name: str, data: bytes) -> str:
    """把本地图片字节编成 data URI，给视觉模型用（和独立图片入库同一套路）。"""
    content_type = RagService._image_content_type(name)
    return f"data:{content_type};base64,{base64.b64encode(data).decode('ascii')}"


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
    并在向量写入成功后把 complete 时插入的 KnowledgeFile 更新为 done。
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
        image_bytes: bytes | None = None,
    ) -> str | None:
        """把一张 Markdown 配图拷到源文件前缀下的 ``images/``。失败返回 None。

        有 ``image_bytes`` 时直接上传，不再按 URL 下载（相对路径走这条）。
        """
        prefix = RagService._file_prefix(object_key)
        name = PurePosixPath(urlparse(url).path).name or f"image-{fallback_index}.jpg"
        try:
            body = image_bytes if image_bytes is not None else RagService._download(url)
            key = f"{prefix}/images/{name}"
            storage.put_object(key, body, RagService._image_content_type(name))
            return key
        except Exception:
            return None

    @staticmethod
    async def replace_images_with_ocr(
        markdown: str,
        object_key: str,
        image_bytes: dict[str, bytes] | None = None,
    ) -> ImageOcrReplacement:
        """把有检索价值的 Markdown 配图换成视觉文本，并只拷这些图。

        绝对 URL 走现有视觉 + 下载拷贝。相对路径先从 ``image_bytes`` 取出，
        转成 data URI 再走同一套 KEEP/SKIP。SKIP 或失败删 markup、不拷不记账。
        """
        matches = list(_MARKDOWN_IMAGE.finditer(markdown))
        if not matches:
            return ImageOcrReplacement(text_for_embedding=markdown, ocr_results=[])

        bytes_table = image_bytes or {}
        ocr = OcrService()
        storage = R2Storage(config.r2)
        text_for_embedding = markdown
        ocr_results: list[ImageOcrItem] = []
        # 同一张图在文中出现多次时，视觉结果复用，避免重复打模型
        vision_cache: dict[str, str | None] = {}
        for index, match in enumerate(matches):
            url = match.group(2).strip()
            local_bytes = None
            vision_url = url
            if not _is_remote_url(url):
                # 相对路径：从 zip 字节表取图，转 data URI 再走下面同一套 KEEP/SKIP
                local_bytes = _lookup_image_bytes(url, bytes_table)
                if local_bytes is None:
                    # 对不上资源，和识别失败一样：删 markup、不记账
                    text_for_embedding = text_for_embedding.replace(match.group(0), "", 1)
                    continue
                vision_url = _to_data_uri(PurePosixPath(url).name, local_bytes)
            try:
                if vision_url in vision_cache:
                    vision_text = vision_cache[vision_url]
                else:
                    vision_text = await ocr.invoke_markdown_figure(vision_url)
                    vision_cache[vision_url] = vision_text
            except Exception:
                vision_text = None
                vision_cache[vision_url] = None
            if vision_text is None:
                # SKIP 或调用失败：嵌入稿去掉图片语法，不拷 R2
                text_for_embedding = text_for_embedding.replace(match.group(0), "", 1)
                continue
            # KEEP：相对路径用已有字节上传，在线 URL 仍下载后再 PUT
            image_key = RagService._try_copy_markdown_image(
                url, object_key, index, storage, image_bytes=local_bytes
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
    def _archive_mineru_output(object_key: str, markdown: str, images) -> None:
        """把 MinerU 原始产出归档到源文件前缀下的 ``mineru/`` 段，供事后对账。

        原始 markdown 存为 ``mineru/full.md``，全部配图按 zip 内文件名存到
        ``mineru/images/<name>``，与 markdown 里的相对引用一一对应，下载后可
        直接对照。归档与配图 KEEP/SKIP 判定无关；单个对象失败只记日志跳过，
        不阻断建库主流程。
        """
        prefix = RagService._file_prefix(object_key)
        storage = R2Storage(config.r2)
        # 待归档清单：先是转换器原文，再是 zip 内全部配图
        objects = [
            (
                f"{prefix}/mineru/full.md",
                markdown.encode("utf-8"),
                "text/markdown; charset=utf-8",
            )
        ] + [
            (
                f"{prefix}/mineru/images/{image.name}",
                image.data,
                RagService._image_content_type(image.name),
            )
            for image in images
        ]
        for key, body, content_type in objects:
            try:
                storage.put_object(key, body, content_type)
            except Exception as e:
                print(f"mineru 原始产出归档失败 {key}: {e}")

    @staticmethod
    async def save_knowledge_file(
        knowledge_file_id: int,
        image_keys: list[str],
        markdown: str | None,
        plain_text: str | None,
        ocr_results: list[ImageOcrItem],
    ) -> None:
        """向量写入成功后，把正文回填到 complete 时插入的那一行并标 done。

        不再 insert。失败路径由 ``mark_failed`` 改同一行，避免向量没写上却多一条记录。
        """
        await knowledgeFileService.mark_done(
            knowledge_file_id,
            image_keys=image_keys,
            markdown=markdown,
            plain_text=plain_text,
            ocr_results=ocr_results,
        )

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
            # PDF/DOCX：直接 extract，才能同时拿到 markdown 和 zip 里的配图字节。
            # MinerULoader 只会把 markdown 放进 page_content，相对路径配图就丢了。
            mineru_config = config.mineru
            if mineru_config.api_key is None:
                raise Exception("mineru api key 不存在")
            result = MinerU(token=mineru_config.api_key).extract(
                file_url,
                ocr=False,
                formula=True,
                table=True,
                language="ch",
                timeout=1200,
            )
            if result.state != "done" or not result.markdown:
                raise Exception("mineru 转换失败")
            converted_markdown = result.markdown
            # 先把原始产出整体归档到 R2，再跑配图 OCR：
            # 即使后续识别异常，转换器原文和全部素材仍留在 mineru/ 段可对账
            RagService._archive_mineru_output(object_key, converted_markdown, result.images)
            replacement = await RagService.replace_images_with_ocr(
                converted_markdown,
                object_key,
                image_bytes=_image_bytes_table(result.images),
            )
            # stored_markdown 仍是转换器原文（含相对路径）；ocr 结果在 replacement 里
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
        knowledge_file_id: int,
    ):
        """知识库入库主流程：解析 → 切块 → 向量化 → 写入 Qdrant → 更新已有行。

        顺序：
        1. ``prepare_ingest`` 按类型产出嵌入文本和 markdown / 纯文本 / OCR / 配图 key。
        2. ``split_text`` 切块；没有任何块则把已有行标 done 后返回。
        3. 批量打 embedding，组装 PointStruct，upsert 到 Qdrant。
        4. 仅当 Qdrant 返回 COMPLETED 才更新 KnowledgeFile 为 done，并发飞书成功 webhook。
        5. 任一步失败都打印异常后把同一行标为 failed，对外只抛「建库失败」。
        """
        try:
            prepared = await RagService.prepare_ingest(file_url, object_key, filename)
            chunks = RagService.split_text(
                prepared.text_for_embedding, object_key, filename
            )
            # 空文件以前是静默 return，有状态机后必须落到 done，否则会永远 processing
            if len(chunks) == 0:
                await RagService.save_knowledge_file(
                    knowledge_file_id,
                    image_keys=prepared.stored_image_keys,
                    markdown=prepared.stored_markdown,
                    plain_text=prepared.stored_plain_text,
                    ocr_results=prepared.stored_ocr_results,
                )
                return

            print("chunk数量", len(chunks))

            vectors = await EmbeddingService().get_batch_embedding(chunks)
            points = RagService.build_qdrant_points(chunks, vectors)
            update_status = qdrantService.upsert(points)
            if update_status.status == UpdateStatus.COMPLETED:
                await RagService.save_knowledge_file(
                    knowledge_file_id,
                    image_keys=prepared.stored_image_keys,
                    markdown=prepared.stored_markdown,
                    plain_text=prepared.stored_plain_text,
                    ocr_results=prepared.stored_ocr_results,
                )
                WebhookService.send_knowledge_base_build_success(filename, username)
            else:
                raise Exception("建库失败")
        except Exception as e:
            # 对内 print 细节，对外和落库都只留「建库失败」
            print(e)
            await knowledgeFileService.mark_failed(knowledge_file_id, "建库失败")
            raise Exception("建库失败")
