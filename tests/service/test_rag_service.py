import asyncio
from types import SimpleNamespace

from langchain_core.documents import Document
from qdrant_client.models import UpdateStatus

from memora_agent.db.models.knowledge_file import KnowledgeFile
from memora_agent.schema.config import MineruConfig
from memora_agent.service.rag_service import RagService


class BoomLoader:
    def __init__(self, *args, **kwargs):
        raise AssertionError("MinerU should not run")


class FakeLoader:
    def __init__(self, source, mode, token):
        self.source = source
        self.mode = mode
        self.token = token

    def load(self):
        return [
            Document(
                page_content="# Title\n\n![ok](https://cdn.example/ok.jpg)\n\n![bad](https://cdn.example/bad.jpg)"
            )
        ]


class FakeOcr:
    def __init__(self):
        self.calls: list[str] = []

    async def invoke(self, image_url: str) -> str:
        self.calls.append(image_url)
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


class FakeSession:
    def __init__(self):
        self.added: list[KnowledgeFile] = []

    def add(self, obj: KnowledgeFile) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        return None

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


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


def test_prepare_ingest_txt_skips_mineru(monkeypatch) -> None:
    monkeypatch.setattr("memora_agent.service.rag_service.MinerULoader", BoomLoader)
    monkeypatch.setattr(
        "memora_agent.service.rag_service.httpx.get",
        lambda url, **kwargs: FakeResponse("hello txt".encode("utf-8")),
    )

    embed_text, markdown, plain_text, ocr_text, image_keys = asyncio.run(
        RagService.prepare_ingest(
            "https://r2.example/notes.txt",
            "abc/notes.txt",
            "notes.txt",
        )
    )

    assert embed_text == "hello txt"
    assert markdown is None
    assert plain_text == "hello txt"
    assert ocr_text is None
    assert image_keys == []


def test_prepare_ingest_png_skips_mineru(monkeypatch) -> None:
    ocr = FakeOcr()
    monkeypatch.setattr("memora_agent.service.rag_service.MinerULoader", BoomLoader)
    monkeypatch.setattr("memora_agent.service.rag_service.OcrService", lambda: ocr)
    monkeypatch.setattr(
        "memora_agent.service.rag_service.httpx.get",
        lambda url, **kwargs: FakeResponse(b"\x89PNG"),
    )

    embed_text, markdown, plain_text, ocr_text, image_keys = asyncio.run(
        RagService.prepare_ingest(
            "https://r2.example/photo.png",
            "abc/photo.png",
            "photo.png",
        )
    )

    assert markdown is None
    assert plain_text is None
    assert ocr_text == "图中有一只猫"
    assert embed_text == ocr_text
    assert image_keys == []
    assert ocr.calls[0].startswith("data:image/png;base64,")


def test_prepare_ingest_pdf_uses_mineru(monkeypatch) -> None:
    ocr = FakeOcr()
    puts: list[tuple[str, bytes, str]] = []
    monkeypatch.setattr(
        "memora_agent.service.rag_service.config.mineru",
        MineruConfig(api_key="token"),
    )
    monkeypatch.setattr("memora_agent.service.rag_service.MinerULoader", FakeLoader)
    monkeypatch.setattr("memora_agent.service.rag_service.OcrService", lambda: ocr)
    monkeypatch.setattr(
        "memora_agent.service.rag_service.R2Storage",
        lambda *args, **kwargs: FakeR2Storage(puts),
    )
    monkeypatch.setattr(
        "memora_agent.service.rag_service.httpx.get",
        lambda url, **kwargs: FakeResponse(b"img"),
    )

    embed_text, markdown, plain_text, ocr_text, image_keys = asyncio.run(
        RagService.prepare_ingest(
            "https://r2.example/notes.pdf",
            "folder/uuid/notes.pdf",
            "notes.pdf",
        )
    )

    assert markdown is not None
    assert "![ok](https://cdn.example/ok.jpg)" in markdown
    assert "图中有一只猫" in embed_text
    assert "![ok]" not in embed_text
    assert "![bad]" not in embed_text
    assert plain_text is None
    assert ocr_text == "图中有一只猫\n\n"
    assert image_keys == [
        "folder/uuid/images/ok.jpg",
        "folder/uuid/images/bad.jpg",
    ]


def test_replace_markdown_images_keeps_going_after_one_failure(monkeypatch) -> None:
    ocr = FakeOcr()
    monkeypatch.setattr("memora_agent.service.rag_service.OcrService", lambda: ocr)
    markdown = (
        "前![ok](https://cdn.example/ok.jpg)中"
        "![bad](https://cdn.example/bad.jpg)后"
    )

    replaced, ocr_text = asyncio.run(RagService.replace_markdown_images(markdown))
    docs = RagService.split_text(replaced, "folder/uuid/notes.pdf", "notes.pdf")

    assert replaced == "前图中有一只猫中后"
    assert ocr_text == "图中有一只猫\n\n"
    assert docs
    assert "图中有一只猫" in docs[0].page_content


def test_copy_markdown_images_uses_file_prefix(monkeypatch) -> None:
    puts: list[tuple[str, bytes, str]] = []
    monkeypatch.setattr(
        "memora_agent.service.rag_service.R2Storage",
        lambda *args, **kwargs: FakeR2Storage(puts),
    )
    monkeypatch.setattr(
        "memora_agent.service.rag_service.httpx.get",
        lambda url, **kwargs: FakeResponse(b"img-bytes"),
    )

    keys = RagService.copy_markdown_images(
        "![a](https://cdn.example/fig-a.png) ![b](https://cdn.example/fig-b.jpg)",
        "kb/file-id/notes.pdf",
    )

    assert keys == [
        "kb/file-id/images/fig-a.png",
        "kb/file-id/images/fig-b.jpg",
    ]
    assert [key for key, _, _ in puts] == keys
    assert all("/images/" in key for key in keys)
    assert all(key.startswith("kb/file-id/") for key in keys)


def test_build_knowledge_base_inserts_row_after_upsert(monkeypatch) -> None:
    session = FakeSession()
    monkeypatch.setattr(
        "memora_agent.service.rag_service.AsyncSessionLocal",
        lambda: session,
    )
    monkeypatch.setattr(
        "memora_agent.service.rag_service.EmbeddingService",
        lambda: FakeEmbedding(),
    )
    qdrant = FakeQdrant(UpdateStatus.COMPLETED)
    monkeypatch.setattr("memora_agent.service.rag_service.qdrantService", qdrant)
    monkeypatch.setattr(
        "memora_agent.service.rag_service.WebhookService.send_knowledge_base_build_success",
        lambda filename: None,
    )

    async def fake_prepare(*args, **kwargs):
        return "hello txt", None, "hello txt", None, []

    monkeypatch.setattr(
        "memora_agent.service.rag_service.RagService.prepare_ingest",
        fake_prepare,
    )

    asyncio.run(
        RagService.build_knowledge_base(
            "https://r2.example/notes.txt",
            "abc/notes.txt",
            "notes.txt",
            7,
            12,
        )
    )

    assert qdrant.points is not None
    assert len(session.added) == 1
    record = session.added[0]
    assert record.user_id == 7
    assert record.filename == "notes.txt"
    assert record.object_key == "abc/notes.txt"
    assert record.size == 12
    assert record.image_keys == []
    assert record.markdown is None
    assert record.plain_text == "hello txt"
    assert record.ocr_text is None


def test_build_knowledge_base_skips_insert_when_upsert_fails(monkeypatch) -> None:
    session = FakeSession()
    monkeypatch.setattr(
        "memora_agent.service.rag_service.AsyncSessionLocal",
        lambda: session,
    )
    monkeypatch.setattr(
        "memora_agent.service.rag_service.EmbeddingService",
        lambda: FakeEmbedding(),
    )
    monkeypatch.setattr(
        "memora_agent.service.rag_service.qdrantService",
        FakeQdrant("failed"),
    )

    async def fake_prepare(*args, **kwargs):
        return "hello txt", None, "hello txt", None, []

    monkeypatch.setattr(
        "memora_agent.service.rag_service.RagService.prepare_ingest",
        fake_prepare,
    )

    try:
        asyncio.run(
            RagService.build_knowledge_base(
                "https://r2.example/notes.txt",
                "abc/notes.txt",
                "notes.txt",
                7,
                12,
            )
        )
    except Exception as exc:
        assert "建库失败" in str(exc)
    else:
        raise AssertionError("expected 建库失败")

    assert session.added == []
