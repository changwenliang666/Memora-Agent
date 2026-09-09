import asyncio

from app.storage.r2 import PresignGetResult
from app.worker import handle_ingest_payload


class FakeKnowledgeFileService:
    def __init__(self, outcome: str = "run") -> None:
        self.outcome = outcome
        self.failed: list[tuple[int, str]] = []
        self.begin_calls: list[int] = []

    async def begin_processing(self, file_id: int) -> str:
        self.begin_calls.append(file_id)
        return self.outcome

    async def mark_failed(self, file_id: int, error_message: str) -> None:
        self.failed.append((file_id, error_message))


class FakeR2:
    def presign_get(self, object_key: str) -> PresignGetResult:
        return PresignGetResult(
            download_url="https://r2.example/fresh",
            object_key=object_key,
            expires_in=3600,
        )


def _payload() -> dict:
    return {
        "knowledge_file_id": 7,
        "object_key": "abc/notes.txt",
        "filename": "notes.txt",
        "user_id": 1,
        "username": "tester",
        "size": 12,
    }


def test_handle_payload_skips_terminal_job(monkeypatch) -> None:
    service = FakeKnowledgeFileService(outcome="skip")
    monkeypatch.setattr("app.worker.knowledgeFileService", service)
    built: list = []

    async def fake_build(*args, **kwargs):
        built.append(args)

    monkeypatch.setattr(
        "app.worker.RagService.build_knowledge_base",
        fake_build,
    )

    assert asyncio.run(handle_ingest_payload(_payload())) == "skip"
    assert built == []
    assert service.begin_calls == [7]


def test_handle_payload_acks_failure_without_raising(monkeypatch) -> None:
    service = FakeKnowledgeFileService(outcome="run")
    monkeypatch.setattr("app.worker.knowledgeFileService", service)
    monkeypatch.setattr("app.worker.get_r2_storage", lambda: FakeR2())

    async def boom(*args, **kwargs):
        raise Exception("建库失败")

    monkeypatch.setattr("app.worker.RagService.build_knowledge_base", boom)

    assert asyncio.run(handle_ingest_payload(_payload())) == "failed"
    assert service.failed == [(7, "建库失败")]


def test_handle_payload_uses_fresh_presign(monkeypatch) -> None:
    service = FakeKnowledgeFileService(outcome="run")
    monkeypatch.setattr("app.worker.knowledgeFileService", service)
    storage = FakeR2()
    monkeypatch.setattr("app.worker.get_r2_storage", lambda: storage)
    captured: list[tuple] = []

    async def fake_build(*args, **kwargs):
        captured.append(args)

    monkeypatch.setattr("app.worker.RagService.build_knowledge_base", fake_build)

    assert asyncio.run(handle_ingest_payload(_payload())) == "done"
    assert captured[0][0] == "https://r2.example/fresh"
    assert captured[0][6] == 7
