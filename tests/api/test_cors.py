from fastapi.testclient import TestClient

from app.core.auth import create_access_token
from app.main import app
from app.storage.r2 import PresignResult


def bearer_headers(user_id: int = 1, username: str = "tester") -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id, username)}"}


class RecordingStorage:
    def __init__(self) -> None:
        self.presign_calls: list[tuple[str, str]] = []

    def presign_put(self, filename: str, content_type: str) -> PresignResult:
        self.presign_calls.append((filename, content_type))
        return PresignResult(
            upload_url="https://r2.example/upload",
            object_key="abc/notes.pdf",
            expires_in=900,
        )


def test_presign_preflight_allows_any_origin_and_method() -> None:
    client = TestClient(app)

    response = client.options(
        "/files/presign",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    allowed_methods = response.headers.get("access-control-allow-methods", "")
    assert "PUT" in allowed_methods.upper() or allowed_methods == "*"
    allowed_headers = response.headers.get("access-control-allow-headers", "").lower()
    assert "content-type" in allowed_headers
    assert "authorization" in allowed_headers


def test_cross_origin_post_includes_cors_headers(monkeypatch) -> None:
    storage = RecordingStorage()
    monkeypatch.setattr(
        "app.api.files.files.get_r2_storage",
        lambda: storage,
    )
    client = TestClient(app)

    response = client.post(
        "/files/presign",
        headers={
            "Origin": "https://arbitrary.example",
            **bearer_headers(),
        },
        json={
            "filename": "notes.pdf",
            "content_type": "application/pdf",
            "size": 1024,
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
