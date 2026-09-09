import asyncio
from types import SimpleNamespace

from qdrant_client.models import UpdateStatus

from app.schema.config import MineruConfig
from app.service.rag_service import (
    ImageOcrItem,
    PreparedIngest,
    RagService,
    _image_bytes_table,
    _lookup_image_bytes,
)

_HTTPS_MARKDOWN = (
    "# Title\n\n"
    "![ok](https://cdn.example/ok.jpg)\n\n"
    "![deco](https://cdn.example/deco.jpg)\n\n"
    "![bad](https://cdn.example/bad.jpg)"
)
_RELATIVE_HASH = "3d4eb58402df44d443412b86c7fbeb16c90fdd6564234da5eb3622d2dbd08b09.jpg"
_RELATIVE_MARKDOWN = f"![](images/{_RELATIVE_HASH})![](images/{_RELATIVE_HASH})"


class BoomMinerU:
    def __init__(self, *args, **kwargs):
        raise AssertionError("MinerU should not run")


class FakeMinerU:
    markdown = _HTTPS_MARKDOWN
    images: list = []

    def __init__(self, token=None):
        self.token = token

    def extract(self, source, **kwargs):
        return SimpleNamespace(
            state="done",
            markdown=self.markdown,
            images=list(self.images),
        )


class FakeOcr:
    def __init__(self):
        self.calls: list[str] = []
        self.figure_calls: list[str] = []

    async def invoke(self, image_url: str) -> str:
        self.calls.append(image_url)
        return "公司 Logo"

    async def invoke_markdown_figure(self, image_url: str) -> str | None:
        self.figure_calls.append(image_url)
        if "deco" in image_url or "skip" in image_url:
            return None
        if "bad" in image_url:
            raise RuntimeError("ocr failed")
        return "图中有一只猫"


class FakeResponse:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self) -> None:
        return None


class FakeR2Storage:
    def __init__(self, puts: list[tuple[str, bytes, str]]):
        self.puts = puts

    def put_object(self, object_key: str, body: bytes, content_type: str) -> None:
        self.puts.append((object_key, body, content_type))


class FakeEmbedding:
    async def get_batch_embedding(self, documents):
        return [[0.1, 0.2, 0.3] for _ in documents]


class FakeQdrant:
    def __init__(self, status):
        self._status = status
        self.points = None

    def upsert(self, points):
        self.points = points
        return SimpleNamespace(status=self._status)


def test_image_bytes_table_accepts_path_name_and_dot_slash() -> None:
    image = SimpleNamespace(name="a.jpg", data=b"abc", path="images/a.jpg")
    table = _image_bytes_table([image])

    assert _lookup_image_bytes("images/a.jpg", table) == b"abc"
    assert _lookup_image_bytes("./images/a.jpg", table) == b"abc"
    assert _lookup_image_bytes("a.jpg", table) == b"abc"


def test_prepare_ingest_txt_skips_mineru(monkeypatch) -> None:
    puts: list[tuple[str, bytes, str]] = []
    monkeypatch.setattr("app.service.rag_service.MinerU", BoomMinerU)
    monkeypatch.setattr(
        "app.service.rag_service.R2Storage",
        lambda *args, **kwargs: FakeR2Storage(puts),
    )
    monkeypatch.setattr(
        "app.service.rag_service.httpx.get",
        lambda url, **kwargs: FakeResponse("hello txt".encode("utf-8")),
    )

    prepared = asyncio.run(
        RagService.prepare_ingest(
            "https://r2.example/notes.txt",
            "abc/notes.txt",
            "notes.txt",
        )
    )

    assert prepared.text_for_embedding == "hello txt"
    assert prepared.stored_markdown is None
    assert prepared.stored_plain_text == "hello txt"
    assert prepared.stored_ocr_results == []
    assert prepared.stored_image_keys == []
    # 非转换文件不产生 mineru/ 归档
    assert [key for key, _, _ in puts if "/mineru/" in key] == []


def test_prepare_ingest_png_skips_mineru(monkeypatch) -> None:
    ocr = FakeOcr()
    puts: list[tuple[str, bytes, str]] = []
    monkeypatch.setattr("app.service.rag_service.MinerU", BoomMinerU)
    monkeypatch.setattr("app.service.rag_service.OcrService", lambda: ocr)
    monkeypatch.setattr(
        "app.service.rag_service.R2Storage",
        lambda *args, **kwargs: FakeR2Storage(puts),
    )
    monkeypatch.setattr(
        "app.service.rag_service.httpx.get",
        lambda url, **kwargs: FakeResponse(b"\x89PNG"),
    )

    prepared = asyncio.run(
        RagService.prepare_ingest(
            "https://r2.example/photo.png",
            "abc/photo.png",
            "photo.png",
        )
    )

    assert prepared.stored_markdown is None
    assert prepared.stored_plain_text is None
    assert prepared.stored_ocr_results == [
        ImageOcrItem(image_key="abc/photo.png", text="公司 Logo")
    ]
    assert prepared.text_for_embedding == "公司 Logo"
    assert prepared.stored_image_keys == []
    assert ocr.calls[0].startswith("data:image/png;base64,")
    assert ocr.figure_calls == []
    # 独立图片不产生 mineru/ 归档
    assert [key for key, _, _ in puts if "/mineru/" in key] == []


def test_prepare_ingest_pdf_uses_mineru(monkeypatch) -> None:
    ocr = FakeOcr()
    puts: list[tuple[str, bytes, str]] = []
    monkeypatch.setattr(
        "app.service.rag_service.config.mineru",
        MineruConfig(api_key="token"),
    )
    FakeMinerU.markdown = _HTTPS_MARKDOWN
    FakeMinerU.images = []
    monkeypatch.setattr("app.service.rag_service.MinerU", FakeMinerU)
    monkeypatch.setattr("app.service.rag_service.OcrService", lambda: ocr)
    monkeypatch.setattr(
        "app.service.rag_service.R2Storage",
        lambda *args, **kwargs: FakeR2Storage(puts),
    )
    monkeypatch.setattr(
        "app.service.rag_service.httpx.get",
        lambda url, **kwargs: FakeResponse(b"img"),
    )

    prepared = asyncio.run(
        RagService.prepare_ingest(
            "https://r2.example/notes.pdf",
            "folder/uuid/notes.pdf",
            "notes.pdf",
        )
    )

    assert prepared.stored_markdown is not None
    assert "![ok](https://cdn.example/ok.jpg)" in prepared.stored_markdown
    assert "![deco](https://cdn.example/deco.jpg)" in prepared.stored_markdown
    assert "![bad](https://cdn.example/bad.jpg)" in prepared.stored_markdown
    assert "图中有一只猫" in prepared.text_for_embedding
    assert "![ok]" not in prepared.text_for_embedding
    assert "![deco]" not in prepared.text_for_embedding
    assert "![bad]" not in prepared.text_for_embedding
    assert prepared.stored_plain_text is None
    assert prepared.stored_ocr_results == [
        ImageOcrItem(image_key="folder/uuid/images/ok.jpg", text="图中有一只猫"),
    ]
    assert prepared.stored_image_keys == [
        "folder/uuid/images/ok.jpg",
    ]
    assert len(ocr.figure_calls) == 3
    assert ocr.calls == []


def test_replace_images_with_ocr_keeps_going_after_one_failure(monkeypatch) -> None:
    ocr = FakeOcr()
    puts: list[tuple[str, bytes, str]] = []
    monkeypatch.setattr("app.service.rag_service.OcrService", lambda: ocr)
    monkeypatch.setattr(
        "app.service.rag_service.R2Storage",
        lambda *args, **kwargs: FakeR2Storage(puts),
    )
    monkeypatch.setattr(
        "app.service.rag_service.httpx.get",
        lambda url, **kwargs: FakeResponse(b"img"),
    )
    markdown = (
        "前![ok](https://cdn.example/ok.jpg)中"
        "![deco](https://cdn.example/deco.jpg)间"
        "![bad](https://cdn.example/bad.jpg)后"
    )

    replacement = asyncio.run(
        RagService.replace_images_with_ocr(markdown, "folder/uuid/notes.pdf")
    )
    docs = RagService.split_text(
        replacement.text_for_embedding, "folder/uuid/notes.pdf", "notes.pdf"
    )

    assert replacement.text_for_embedding == "前图中有一只猫中间后"
    assert replacement.ocr_results == [
        ImageOcrItem(image_key="folder/uuid/images/ok.jpg", text="图中有一只猫"),
    ]
    assert puts == [("folder/uuid/images/ok.jpg", b"img", "image/jpeg")]
    assert docs
    assert "图中有一只猫" in docs[0].page_content
    assert "![deco]" not in replacement.text_for_embedding
    assert "![bad]" not in replacement.text_for_embedding


def _patch_ingest(monkeypatch, ocr, puts, downloads: list[str] | None = None):
    monkeypatch.setattr(
        "app.service.rag_service.config.mineru",
        MineruConfig(api_key="token"),
    )
    monkeypatch.setattr("app.service.rag_service.MinerU", FakeMinerU)
    monkeypatch.setattr("app.service.rag_service.OcrService", lambda: ocr)
    monkeypatch.setattr(
        "app.service.rag_service.R2Storage",
        lambda *args, **kwargs: FakeR2Storage(puts),
    )

    def fake_get(url, **kwargs):
        if downloads is not None:
            downloads.append(url)
        return FakeResponse(b"img")

    monkeypatch.setattr("app.service.rag_service.httpx.get", fake_get)


def test_prepare_ingest_pdf_relative_images_use_converter_bytes(monkeypatch) -> None:
    ocr = FakeOcr()
    puts: list[tuple[str, bytes, str]] = []
    downloads: list[str] = []
    FakeMinerU.markdown = _RELATIVE_MARKDOWN
    FakeMinerU.images = [
        SimpleNamespace(name=_RELATIVE_HASH, data=b"page-bytes", path=f"images/{_RELATIVE_HASH}")
    ]
    _patch_ingest(monkeypatch, ocr, puts, downloads)

    prepared = asyncio.run(
        RagService.prepare_ingest(
            "https://r2.example/notes.pdf",
            "folder/uuid/notes.pdf",
            "notes.pdf",
        )
    )

    assert prepared.stored_markdown == _RELATIVE_MARKDOWN
    assert prepared.text_for_embedding == "图中有一只猫图中有一只猫"
    assert prepared.stored_ocr_results == [
        ImageOcrItem(image_key=f"folder/uuid/images/{_RELATIVE_HASH}", text="图中有一只猫"),
        ImageOcrItem(image_key=f"folder/uuid/images/{_RELATIVE_HASH}", text="图中有一只猫"),
    ]
    assert prepared.stored_image_keys == [f"folder/uuid/images/{_RELATIVE_HASH}"] * 2
    assert all(call.startswith("data:image/") for call in ocr.figure_calls)
    assert len(ocr.figure_calls) == 1
    # 先是归档（原文 + 素材），再是两张 KEEP 拷贝
    assert puts == [
        (
            "folder/uuid/mineru/full.md",
            _RELATIVE_MARKDOWN.encode("utf-8"),
            "text/markdown; charset=utf-8",
        ),
        (f"folder/uuid/mineru/images/{_RELATIVE_HASH}", b"page-bytes", "image/jpeg"),
        (f"folder/uuid/images/{_RELATIVE_HASH}", b"page-bytes", "image/jpeg"),
        (f"folder/uuid/images/{_RELATIVE_HASH}", b"page-bytes", "image/jpeg"),
    ]
    assert downloads == []


def test_prepare_ingest_pdf_missing_relative_image_is_skipped(monkeypatch) -> None:
    ocr = FakeOcr()
    puts: list[tuple[str, bytes, str]] = []
    downloads: list[str] = []
    FakeMinerU.markdown = f"![](images/{_RELATIVE_HASH})"
    FakeMinerU.images = []
    _patch_ingest(monkeypatch, ocr, puts, downloads)

    prepared = asyncio.run(
        RagService.prepare_ingest(
            "https://r2.example/notes.pdf",
            "folder/uuid/notes.pdf",
            "notes.pdf",
        )
    )

    assert prepared.stored_markdown == f"![](images/{_RELATIVE_HASH})"
    assert prepared.text_for_embedding == ""
    assert prepared.stored_ocr_results == []
    assert prepared.stored_image_keys == []
    assert ocr.figure_calls == []
    # 没有任何配图字节时，归档只剩 markdown 原文一个对象
    assert puts == [
        (
            "folder/uuid/mineru/full.md",
            f"![](images/{_RELATIVE_HASH})".encode("utf-8"),
            "text/markdown; charset=utf-8",
        ),
    ]
    assert downloads == []


def test_archive_mineru_output_uploads_all_figures_regardless_of_ocr(monkeypatch) -> None:
    ocr = FakeOcr()
    puts: list[tuple[str, bytes, str]] = []
    # markdown 里 1 张 KEEP（ok）、1 张 SKIP（deco）、1 张识别失败（bad）
    FakeMinerU.markdown = _HTTPS_MARKDOWN
    FakeMinerU.images = [
        SimpleNamespace(name="fig-ok.jpg", data=b"ok-bytes", path="images/fig-ok.jpg"),
        SimpleNamespace(name="fig-deco.jpg", data=b"deco-bytes", path="images/fig-deco.jpg"),
        SimpleNamespace(name="fig-bad.jpg", data=b"bad-bytes", path="images/fig-bad.jpg"),
    ]
    _patch_ingest(monkeypatch, ocr, puts)

    prepared = asyncio.run(
        RagService.prepare_ingest(
            "https://r2.example/notes.pdf",
            "folder/uuid/notes.pdf",
            "notes.pdf",
        )
    )

    # mineru/ 段收全部 3 张配图 + markdown 原文，与 KEEP/SKIP/失败无关
    assert [key for key, _, _ in puts if "/mineru/" in key] == [
        "folder/uuid/mineru/full.md",
        "folder/uuid/mineru/images/fig-ok.jpg",
        "folder/uuid/mineru/images/fig-deco.jpg",
        "folder/uuid/mineru/images/fig-bad.jpg",
    ]
    # full.md 存的是转换器原文，图片引用保持不动
    assert puts[0] == (
        "folder/uuid/mineru/full.md",
        _HTTPS_MARKDOWN.encode("utf-8"),
        "text/markdown; charset=utf-8",
    )
    # images/ 段仍只有视觉 KEEP 的那 1 张
    kept_keys = [
        key for key, _, _ in puts if "/images/" in key and "/mineru/" not in key
    ]
    assert kept_keys == ["folder/uuid/images/ok.jpg"]
    assert prepared.stored_image_keys == ["folder/uuid/images/ok.jpg"]


def test_archive_mineru_output_runs_before_figure_ocr(monkeypatch) -> None:
    # R2 PUT 和视觉调用写进同一个 events，断言归档全部先于识别
    events: list[str] = []

    class OrderR2:
        def put_object(self, object_key, body, content_type):
            events.append(object_key)

    class OrderOcr:
        async def invoke_markdown_figure(self, image_url):
            events.append("vision")
            return "图中有一只猫"

    monkeypatch.setattr(
        "app.service.rag_service.config.mineru",
        MineruConfig(api_key="token"),
    )
    FakeMinerU.markdown = _RELATIVE_MARKDOWN
    FakeMinerU.images = [
        SimpleNamespace(
            name=_RELATIVE_HASH, data=b"page-bytes", path=f"images/{_RELATIVE_HASH}"
        )
    ]
    monkeypatch.setattr("app.service.rag_service.MinerU", FakeMinerU)
    monkeypatch.setattr("app.service.rag_service.OcrService", lambda: OrderOcr())
    monkeypatch.setattr(
        "app.service.rag_service.R2Storage",
        lambda *args, **kwargs: OrderR2(),
    )

    asyncio.run(
        RagService.prepare_ingest(
            "https://r2.example/notes.pdf",
            "folder/uuid/notes.pdf",
            "notes.pdf",
        )
    )

    first_vision = events.index("vision")
    assert events[:first_vision] == [
        "folder/uuid/mineru/full.md",
        f"folder/uuid/mineru/images/{_RELATIVE_HASH}",
    ]


def test_archive_mineru_output_failure_does_not_block_ingest(monkeypatch, capsys) -> None:
    puts: list[tuple[str, bytes, str]] = []

    class FlakyR2:
        # 对特定配图上传抛错，模拟 R2 抖动
        def put_object(self, object_key, body, content_type):
            if "fig-bad" in object_key:
                raise RuntimeError("r2 down")
            puts.append((object_key, body, content_type))

    monkeypatch.setattr(
        "app.service.rag_service.config.mineru",
        MineruConfig(api_key="token"),
    )
    # markdown 不引用任何图，排除配图 OCR 干扰，只验证归档失败语义
    FakeMinerU.markdown = "# 纯文字"
    FakeMinerU.images = [
        SimpleNamespace(name="fig-bad.jpg", data=b"bad", path="images/fig-bad.jpg"),
        SimpleNamespace(name="fig-good.jpg", data=b"good", path="images/fig-good.jpg"),
    ]
    monkeypatch.setattr("app.service.rag_service.MinerU", FakeMinerU)
    monkeypatch.setattr(
        "app.service.rag_service.R2Storage",
        lambda *args, **kwargs: FlakyR2(),
    )

    prepared = asyncio.run(
        RagService.prepare_ingest(
            "https://r2.example/notes.pdf",
            "folder/uuid/notes.pdf",
            "notes.pdf",
        )
    )

    # 建库材料正常产出，失败图之后的对象仍被上传，失败写进了日志
    assert prepared.text_for_embedding == "# 纯文字"
    assert [key for key, _, _ in puts] == [
        "folder/uuid/mineru/full.md",
        "folder/uuid/mineru/images/fig-good.jpg",
    ]
    assert "folder/uuid/mineru/images/fig-bad.jpg" in capsys.readouterr().out


def test_copy_markdown_images_uses_file_prefix(monkeypatch) -> None:
    puts: list[tuple[str, bytes, str]] = []
    monkeypatch.setattr(
        "app.service.rag_service.R2Storage",
        lambda *args, **kwargs: FakeR2Storage(puts),
    )
    monkeypatch.setattr(
        "app.service.rag_service.httpx.get",
        lambda url, **kwargs: FakeResponse(b"img-bytes"),
    )

    stored_image_keys = RagService.copy_markdown_images(
        "![a](https://cdn.example/fig-a.png) ![b](https://cdn.example/fig-b.jpg)",
        "kb/file-id/notes.pdf",
    )

    assert stored_image_keys == [
        "kb/file-id/images/fig-a.png",
        "kb/file-id/images/fig-b.jpg",
    ]
    assert [key for key, _, _ in puts] == stored_image_keys
    assert all("/images/" in key for key in stored_image_keys)
    assert all(key.startswith("kb/file-id/") for key in stored_image_keys)


class FakeKnowledgeFiles:
    def __init__(self) -> None:
        self.done: list[dict] = []
        self.failed: list[tuple[int, str]] = []

    async def mark_done(self, file_id: int, **kwargs) -> None:
        self.done.append({"id": file_id, **kwargs})

    async def mark_failed(self, file_id: int, error_message: str) -> None:
        self.failed.append((file_id, error_message))


def test_build_knowledge_base_marks_done_after_upsert(monkeypatch) -> None:
    files = FakeKnowledgeFiles()
    monkeypatch.setattr("app.service.rag_service.knowledgeFileService", files)
    monkeypatch.setattr(
        "app.service.rag_service.EmbeddingService",
        lambda: FakeEmbedding(),
    )
    qdrant = FakeQdrant(UpdateStatus.COMPLETED)
    monkeypatch.setattr("app.service.rag_service.qdrantService", qdrant)
    monkeypatch.setattr(
        "app.service.rag_service.WebhookService.send_knowledge_base_build_success",
        lambda filename, username: None,
    )

    async def fake_prepare(*args, **kwargs):
        return PreparedIngest(
            text_for_embedding="hello txt",
            stored_markdown=None,
            stored_plain_text="hello txt",
            stored_ocr_results=[],
            stored_image_keys=[],
        )

    monkeypatch.setattr(
        "app.service.rag_service.RagService.prepare_ingest",
        fake_prepare,
    )

    asyncio.run(
        RagService.build_knowledge_base(
            "https://r2.example/notes.txt",
            "abc/notes.txt",
            "notes.txt",
            7,
            "tester",
            12,
            99,
        )
    )

    assert qdrant.points is not None
    assert len(files.done) == 1
    record = files.done[0]
    assert record["id"] == 99
    assert record["image_keys"] == []
    assert record["markdown"] is None
    assert record["plain_text"] == "hello txt"
    assert record["ocr_results"] == []
    assert files.failed == []


def test_build_knowledge_base_marks_failed_when_upsert_fails(monkeypatch) -> None:
    files = FakeKnowledgeFiles()
    monkeypatch.setattr("app.service.rag_service.knowledgeFileService", files)
    monkeypatch.setattr(
        "app.service.rag_service.EmbeddingService",
        lambda: FakeEmbedding(),
    )
    monkeypatch.setattr(
        "app.service.rag_service.qdrantService",
        FakeQdrant("failed"),
    )

    async def fake_prepare(*args, **kwargs):
        return PreparedIngest(
            text_for_embedding="hello txt",
            stored_markdown=None,
            stored_plain_text="hello txt",
            stored_ocr_results=[],
            stored_image_keys=[],
        )

    monkeypatch.setattr(
        "app.service.rag_service.RagService.prepare_ingest",
        fake_prepare,
    )

    try:
        asyncio.run(
            RagService.build_knowledge_base(
                "https://r2.example/notes.txt",
                "abc/notes.txt",
                "notes.txt",
                7,
                "tester",
                12,
                99,
            )
        )
    except Exception as exc:
        assert "建库失败" in str(exc)
    else:
        raise AssertionError("expected 建库失败")

    assert files.done == []
    assert files.failed == [(99, "建库失败")]


def test_build_knowledge_base_marks_done_when_chunks_empty(monkeypatch) -> None:
    files = FakeKnowledgeFiles()
    monkeypatch.setattr("app.service.rag_service.knowledgeFileService", files)

    async def fake_prepare(*args, **kwargs):
        return PreparedIngest(
            text_for_embedding="",
            stored_markdown=None,
            stored_plain_text="",
            stored_ocr_results=[],
            stored_image_keys=[],
        )

    monkeypatch.setattr(
        "app.service.rag_service.RagService.prepare_ingest",
        fake_prepare,
    )
    monkeypatch.setattr(
        "app.service.rag_service.RagService.split_text",
        lambda *args, **kwargs: [],
    )

    asyncio.run(
        RagService.build_knowledge_base(
            "https://r2.example/notes.txt",
            "abc/notes.txt",
            "notes.txt",
            7,
            "tester",
            12,
            99,
        )
    )

    assert files.done == [
        {
            "id": 99,
            "image_keys": [],
            "markdown": None,
            "plain_text": "",
            "ocr_results": [],
        }
    ]
    assert files.failed == []
