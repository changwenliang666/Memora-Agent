from datetime import datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.auth import create_access_token
from app.main import app
from app.schema.bizcode import BizCode
from app.storage.r2 import PresignGetResult, PresignResult, R2ConfigError
from app.storage.validate import MAX_UPLOAD_SIZE


def bearer_headers(user_id: int = 1, username: str = "tester") -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id, username)}"}


def authed_client() -> TestClient:
    client = TestClient(app)
    client.headers.update(bearer_headers())
    return client


class RecordingStorage:
    def __init__(
        self,
        result: PresignResult | None = None,
        get_result: PresignGetResult | None = None,
        error: Exception | None = None,
        get_error: Exception | None = None,
    ) -> None:
        self.presign_calls: list[tuple[str, str]] = []
        self.presign_get_calls: list[str] = []
        self.result = result or PresignResult(
            upload_url="https://r2.example/upload",
            object_key="abc/notes.pdf",
            expires_in=900,
        )
        self.get_result = get_result or PresignGetResult(
            download_url="https://r2.example/download",
            object_key="abc/notes.pdf",
            expires_in=3600,
        )
        self.error = error
        self.get_error = get_error

    def presign_put(self, filename: str, content_type: str) -> PresignResult:
        self.presign_calls.append((filename, content_type))
        if self.error is not None:
            raise self.error
        return self.result

    def presign_get(self, object_key: str) -> PresignGetResult:
        self.presign_get_calls.append(object_key)
        if self.get_error is not None:
            raise self.get_error
        return self.get_result


def test_presign_valid_pdf_returns_upload_url(monkeypatch) -> None:
    storage = RecordingStorage()
    monkeypatch.setattr(
        "app.api.files.files.get_r2_storage",
        lambda: storage,
    )
    client = authed_client()

    response = client.post(
        "/files/presign",
        json={
            "filename": "notes.pdf",
            "content_type": "application/pdf",
            "size": 1_048_576,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["upload_url"] == "https://r2.example/upload"
    assert "notes.pdf" in body["object_key"]
    assert "/" in body["object_key"]
    assert body["expires_in"] > 0
    assert storage.presign_calls == [("notes.pdf", "application/pdf")]


def test_presign_valid_markdown_returns_upload_url(monkeypatch) -> None:
    storage = RecordingStorage(
        result=PresignResult(
            upload_url="https://r2.example/upload-md",
            object_key="abc/readme.md",
            expires_in=900,
        )
    )
    monkeypatch.setattr(
        "app.api.files.files.get_r2_storage",
        lambda: storage,
    )
    client = authed_client()

    response = client.post(
        "/files/presign",
        json={
            "filename": "readme.md",
            "content_type": "text/plain",
            "size": 2048,
        },
    )

    assert response.status_code == 200
    assert response.json()["upload_url"] == "https://r2.example/upload-md"


def test_presign_valid_png_returns_upload_url(monkeypatch) -> None:
    storage = RecordingStorage(
        result=PresignResult(
            upload_url="https://r2.example/upload-png",
            object_key="abc/photo.png",
            expires_in=900,
        )
    )
    monkeypatch.setattr(
        "app.api.files.files.get_r2_storage",
        lambda: storage,
    )
    client = authed_client()

    response = client.post(
        "/files/presign",
        json={
            "filename": "photo.png",
            "content_type": "image/png",
            "size": 1024,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["upload_url"] == "https://r2.example/upload-png"
    assert "photo.png" in body["object_key"]
    assert "/" in body["object_key"]
    assert storage.presign_calls == [("photo.png", "image/png")]


def test_presign_valid_docx_returns_upload_url(monkeypatch) -> None:
    storage = RecordingStorage(
        result=PresignResult(
            upload_url="https://r2.example/upload-docx",
            object_key="abc/report.docx",
            expires_in=900,
        )
    )
    monkeypatch.setattr(
        "app.api.files.files.get_r2_storage",
        lambda: storage,
    )
    client = authed_client()

    response = client.post(
        "/files/presign",
        json={
            "filename": "report.docx",
            "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "size": 2048,
        },
    )

    assert response.status_code == 200
    assert response.json()["upload_url"] == "https://r2.example/upload-docx"
    assert storage.presign_calls == [
        (
            "report.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    ]


def test_presign_rejects_disallowed_extension(monkeypatch) -> None:
    storage = RecordingStorage()
    monkeypatch.setattr(
        "app.api.files.files.get_r2_storage",
        lambda: storage,
    )
    client = authed_client()

    response = client.post(
        "/files/presign",
        json={
            "filename": "notes.exe",
            "content_type": "application/octet-stream",
            "size": 1024,
        },
    )

    assert response.status_code == 400
    assert "upload_url" not in response.json()
    assert storage.presign_calls == []


def test_presign_rejects_size_above_limit(monkeypatch) -> None:
    storage = RecordingStorage()
    monkeypatch.setattr(
        "app.api.files.files.get_r2_storage",
        lambda: storage,
    )
    client = authed_client()

    response = client.post(
        "/files/presign",
        json={
            "filename": "book.pdf",
            "content_type": "application/pdf",
            "size": MAX_UPLOAD_SIZE + 1,
        },
    )

    assert response.status_code == 400
    assert "upload_url" not in response.json()
    assert storage.presign_calls == []


def test_presign_rejects_zero_size(monkeypatch) -> None:
    storage = RecordingStorage()
    monkeypatch.setattr(
        "app.api.files.files.get_r2_storage",
        lambda: storage,
    )
    client = authed_client()

    response = client.post(
        "/files/presign",
        json={
            "filename": "empty.txt",
            "content_type": "text/plain",
            "size": 0,
        },
    )

    assert response.status_code == 400
    assert "upload_url" not in response.json()


def test_presign_rejects_content_type_mismatch(monkeypatch) -> None:
    storage = RecordingStorage()
    monkeypatch.setattr(
        "app.api.files.files.get_r2_storage",
        lambda: storage,
    )
    client = authed_client()

    response = client.post(
        "/files/presign",
        json={
            "filename": "notes.pdf",
            "content_type": "text/plain",
            "size": 1024,
        },
    )

    assert response.status_code == 400
    assert "upload_url" not in response.json()


def test_presign_missing_r2_config_returns_500(monkeypatch) -> None:
    storage = RecordingStorage(error=R2ConfigError("R2 配置不完整"))
    monkeypatch.setattr(
        "app.api.files.files.get_r2_storage",
        lambda: storage,
    )
    client = authed_client()

    response = client.post(
        "/files/presign",
        json={
            "filename": "notes.pdf",
            "content_type": "application/pdf",
            "size": 1024,
        },
    )

    assert response.status_code == 500
    assert "upload_url" not in response.json()


def test_complete_returns_declared_file_info_and_download_url(monkeypatch) -> None:
    storage = RecordingStorage()
    monkeypatch.setattr(
        "app.api.files.files.get_r2_storage",
        lambda: storage,
    )

    async def fake_create_pending(**kwargs):
        return SimpleNamespace(id=42, status="pending")

    published: list[dict] = []

    async def fake_publish(payload: dict) -> None:
        published.append(payload)

    monkeypatch.setattr(
        "app.api.files.files.knowledgeFileService.create_pending",
        fake_create_pending,
    )
    monkeypatch.setattr("app.api.files.files.publish_ingest", fake_publish)
    client = authed_client()
    payload = {
        "object_key": "abc/notes.pdf",
        "filename": "notes.pdf",
        "content_type": "application/pdf",
        "size": 1_048_576,
    }

    response = client.post("/files/complete", json=payload)

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["id"] == 42
    assert body["status"] == "pending"
    assert body["object_key"] == payload["object_key"]
    assert body["filename"] == payload["filename"]
    assert body["content_type"] == payload["content_type"]
    assert body["size"] == payload["size"]
    assert body["download_url"] == "https://r2.example/download"
    assert body["expires_in"] > 0
    assert storage.presign_get_calls == ["abc/notes.pdf"]
    assert storage.presign_calls == []
    assert published[0]["knowledge_file_id"] == 42
    assert "download_url" not in published[0]


def test_complete_passes_user_id_and_size_into_ingest(monkeypatch) -> None:
    storage = RecordingStorage()
    published: list[dict] = []

    async def fake_create_pending(**kwargs):
        assert kwargs["user_id"] == 1
        assert kwargs["size"] == 1_048_576
        return SimpleNamespace(id=8, status="pending")

    async def fake_publish(payload: dict) -> None:
        published.append(payload)

    monkeypatch.setattr(
        "app.api.files.files.get_r2_storage",
        lambda: storage,
    )
    monkeypatch.setattr(
        "app.api.files.files.knowledgeFileService.create_pending",
        fake_create_pending,
    )
    monkeypatch.setattr("app.api.files.files.publish_ingest", fake_publish)
    client = authed_client()
    payload = {
        "object_key": "abc/notes.pdf",
        "filename": "notes.pdf",
        "content_type": "application/pdf",
        "size": 1_048_576,
    }

    response = client.post("/files/complete", json=payload)

    assert response.status_code == 200
    assert published == [
        {
            "knowledge_file_id": 8,
            "object_key": "abc/notes.pdf",
            "filename": "notes.pdf",
            "user_id": 1,
            "username": "tester",
            "size": 1_048_576,
        }
    ]


def test_complete_marks_failed_when_enqueue_fails(monkeypatch) -> None:
    storage = RecordingStorage()
    failed: list[tuple] = []

    async def fake_create_pending(**kwargs):
        return SimpleNamespace(id=5, status="pending")

    async def boom(payload: dict) -> None:
        raise RuntimeError("broker down")

    async def fake_mark_failed(file_id: int, error_message: str) -> None:
        failed.append((file_id, error_message))

    monkeypatch.setattr(
        "app.api.files.files.get_r2_storage",
        lambda: storage,
    )
    monkeypatch.setattr(
        "app.api.files.files.knowledgeFileService.create_pending",
        fake_create_pending,
    )
    monkeypatch.setattr("app.api.files.files.publish_ingest", boom)
    monkeypatch.setattr(
        "app.api.files.files.knowledgeFileService.mark_failed",
        fake_mark_failed,
    )
    client = authed_client()

    response = client.post(
        "/files/complete",
        json={
            "object_key": "abc/notes.pdf",
            "filename": "notes.pdf",
            "content_type": "application/pdf",
            "size": 1024,
        },
    )

    assert response.status_code == 500
    assert failed == [(5, "入队失败")]


def test_complete_missing_object_key_is_422(monkeypatch) -> None:
    storage = RecordingStorage()
    monkeypatch.setattr(
        "app.api.files.files.get_r2_storage",
        lambda: storage,
    )
    client = authed_client()

    response = client.post(
        "/files/complete",
        json={
            "filename": "notes.pdf",
            "content_type": "application/pdf",
            "size": 1024,
        },
    )

    assert response.status_code == 422
    assert "download_url" not in response.json()
    assert storage.presign_get_calls == []


def test_complete_missing_r2_config_returns_500(monkeypatch) -> None:
    storage = RecordingStorage(get_error=R2ConfigError("R2 配置不完整"))
    monkeypatch.setattr(
        "app.api.files.files.get_r2_storage",
        lambda: storage,
    )
    client = authed_client()

    response = client.post(
        "/files/complete",
        json={
            "object_key": "abc/notes.pdf",
            "filename": "notes.pdf",
            "content_type": "application/pdf",
            "size": 1024,
        },
    )

    assert response.status_code == 500
    assert "download_url" not in response.json()


def test_openapi_lists_file_and_chat_routes() -> None:
    client = authed_client()
    spec = client.get("/openapi.json").json()
    paths = spec["paths"]

    assert "/files/presign" in paths
    assert "/files/complete" in paths
    assert "/files" in paths
    assert "/files/{file_id}" in paths
    assert "/chat/agent" in paths
    assert "/chat/rule" in paths


def test_presign_without_token_does_not_issue_upload_url() -> None:
    client = TestClient(app)
    response = client.post(
        "/files/presign",
        json={
            "filename": "notes.pdf",
            "content_type": "application/pdf",
            "size": 1024,
        },
    )
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == BizCode.UNAUTHORIZED.value
    assert body["data"] is None
    assert "upload_url" not in body


def test_complete_without_token_does_not_issue_download_url() -> None:
    client = TestClient(app)
    response = client.post(
        "/files/complete",
        json={
            "object_key": "abc/notes.pdf",
            "filename": "notes.pdf",
            "content_type": "application/pdf",
            "size": 1024,
        },
    )
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == BizCode.UNAUTHORIZED.value
    assert body["data"] is None
    assert "download_url" not in body


def _summary_row(
    file_id: int,
    filename: str,
    created_at: datetime,
    user_id: int = 1,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=file_id,
        user_id=user_id,
        status="done",
        error_message=None,
        filename=filename,
        object_key=f"abc/{filename}",
        content_type="text/plain",
        size=10,
        created_at=created_at,
        started_at=created_at,
        finished_at=created_at,
        queue_wait_ms=100,
        duration_ms=200,
        markdown="SECRET",
        plain_text="SECRET",
        ocr_results=[{"text": "SECRET"}],
    )


def test_list_files_returns_owner_summaries_newest_first(monkeypatch) -> None:
    newer = _summary_row(2, "b.txt", datetime(2026, 1, 2))
    older = _summary_row(1, "a.txt", datetime(2026, 1, 1))

    async def fake_list(user_id: int, limit: int, offset: int):
        assert user_id == 1
        assert limit == 20
        assert offset == 0
        return [newer, older], 2

    monkeypatch.setattr(
        "app.api.files.files.knowledgeFileService.list_for_user",
        fake_list,
    )
    client = authed_client()
    response = client.get("/files")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 2
    items = data["items"]
    assert [item["id"] for item in items] == [2, 1]
    assert "markdown" not in items[0]
    assert "plain_text" not in items[0]
    assert "ocr_results" not in items[0]
    assert items[0]["queue_wait_ms"] == 100
    assert items[0]["duration_ms"] == 200


def test_list_files_honors_limit_and_offset(monkeypatch) -> None:
    captured: list[tuple[int, int, int]] = []

    async def fake_list(user_id: int, limit: int, offset: int):
        captured.append((user_id, limit, offset))
        return [_summary_row(2, "b.txt", datetime(2026, 1, 2))], 3

    monkeypatch.setattr(
        "app.api.files.files.knowledgeFileService.list_for_user",
        fake_list,
    )
    client = authed_client()
    response = client.get("/files", params={"limit": 1, "offset": 1})

    assert response.status_code == 200
    assert captured == [(1, 1, 1)]
    body = response.json()["data"]
    assert body["total"] == 3
    assert len(body["items"]) == 1


def test_get_file_returns_owner_summary(monkeypatch) -> None:
    row = _summary_row(9, "notes.txt", datetime(2026, 1, 1))

    async def fake_get(user_id: int, file_id: int):
        assert user_id == 1
        assert file_id == 9
        return row

    monkeypatch.setattr(
        "app.api.files.files.knowledgeFileService.get_for_user",
        fake_get,
    )
    client = authed_client()
    response = client.get("/files/9")

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["id"] == 9
    assert body["status"] == "done"
    assert "markdown" not in body


def test_get_file_other_user_is_404(monkeypatch) -> None:
    async def fake_get(user_id: int, file_id: int):
        return None

    monkeypatch.setattr(
        "app.api.files.files.knowledgeFileService.get_for_user",
        fake_get,
    )
    client = authed_client()
    response = client.get("/files/99")

    assert response.status_code == 404


def test_list_files_without_token_is_401() -> None:
    client = TestClient(app)
    response = client.get("/files")
    assert response.status_code == 401
