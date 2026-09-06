from fastapi.testclient import TestClient

from memora_agent.main import app
from memora_agent.storage.r2 import PresignResult, R2ConfigError
from memora_agent.storage.validate import MAX_UPLOAD_SIZE


class RecordingStorage:
    def __init__(self, result: PresignResult | None = None, error: Exception | None = None) -> None:
        self.presign_calls: list[tuple[str, str]] = []
        self.result = result or PresignResult(
            upload_url="https://r2.example/upload",
            object_key="abc/notes.pdf",
            expires_in=900,
        )
        self.error = error

    def presign_put(self, filename: str, content_type: str) -> PresignResult:
        self.presign_calls.append((filename, content_type))
        if self.error is not None:
            raise self.error
        return self.result


def test_presign_valid_pdf_returns_upload_url(monkeypatch) -> None:
    storage = RecordingStorage()
    monkeypatch.setattr(
        "memora_agent.api.files.files.get_r2_storage",
        lambda: storage,
    )
    client = TestClient(app)

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
        "memora_agent.api.files.files.get_r2_storage",
        lambda: storage,
    )
    client = TestClient(app)

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


def test_presign_rejects_disallowed_extension(monkeypatch) -> None:
    storage = RecordingStorage()
    monkeypatch.setattr(
        "memora_agent.api.files.files.get_r2_storage",
        lambda: storage,
    )
    client = TestClient(app)

    response = client.post(
        "/files/presign",
        json={
            "filename": "photo.png",
            "content_type": "image/png",
            "size": 1024,
        },
    )

    assert response.status_code == 400
    assert "upload_url" not in response.json()
    assert storage.presign_calls == []


def test_presign_rejects_size_above_limit(monkeypatch) -> None:
    storage = RecordingStorage()
    monkeypatch.setattr(
        "memora_agent.api.files.files.get_r2_storage",
        lambda: storage,
    )
    client = TestClient(app)

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
        "memora_agent.api.files.files.get_r2_storage",
        lambda: storage,
    )
    client = TestClient(app)

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
        "memora_agent.api.files.files.get_r2_storage",
        lambda: storage,
    )
    client = TestClient(app)

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
        "memora_agent.api.files.files.get_r2_storage",
        lambda: storage,
    )
    client = TestClient(app)

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


def test_complete_returns_declared_file_info() -> None:
    client = TestClient(app)
    payload = {
        "object_key": "abc/notes.pdf",
        "filename": "notes.pdf",
        "content_type": "application/pdf",
        "size": 1_048_576,
    }

    response = client.post("/files/complete", json=payload)

    assert response.status_code == 200
    assert response.json() == payload


def test_complete_missing_object_key_is_422() -> None:
    client = TestClient(app)

    response = client.post(
        "/files/complete",
        json={
            "filename": "notes.pdf",
            "content_type": "application/pdf",
            "size": 1024,
        },
    )

    assert response.status_code == 422


def test_complete_does_not_call_r2(monkeypatch) -> None:
    storage = RecordingStorage()
    monkeypatch.setattr(
        "memora_agent.api.files.files.get_r2_storage",
        lambda: storage,
    )
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

    assert response.status_code == 200
    assert storage.presign_calls == []


def test_openapi_lists_file_and_chat_routes() -> None:
    client = TestClient(app)
    spec = client.get("/openapi.json").json()
    paths = spec["paths"]

    assert "/files/presign" in paths
    assert "/files/complete" in paths
    assert "/chat/agent" in paths
    assert "/chat/rule" in paths
