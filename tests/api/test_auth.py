from dataclasses import dataclass

from fastapi.testclient import TestClient

from memora_agent.core.auth import create_access_token, hash_password
from memora_agent.main import app
from memora_agent.schema.bizcode import BizCode
from memora_agent.service.user_service import UserAlreadyExistsError, userService


def bearer_headers(user_id: int = 1, username: str = "tester") -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id, username)}"}


@dataclass
class FakeUser:
    id: int
    username: str
    password: str


def test_register_creates_user_without_password(monkeypatch) -> None:
    async def create_user(username: str, password: str) -> FakeUser:
        return FakeUser(id=3, username=username, password=hash_password(password))

    monkeypatch.setattr(userService, "create_user", create_user)
    client = TestClient(app)

    response = client.post(
        "/auth/register",
        json={"username": "dawei", "password": "secret12"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == BizCode.SUCCESS.value
    assert body["data"]["username"] == "dawei"
    assert body["data"]["user_id"] == 3
    assert "password" not in body["data"]
    assert "secret12" not in response.text


def test_register_duplicate_username(monkeypatch) -> None:
    async def create_user(username: str, password: str) -> FakeUser:
        raise UserAlreadyExistsError

    monkeypatch.setattr(userService, "create_user", create_user)
    client = TestClient(app)

    response = client.post(
        "/auth/register",
        json={"username": "dawei", "password": "secret12"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == BizCode.USERNAME_ALREADY_EXISTS.value
    assert body["data"] is None
    assert "password" not in str(body.get("data"))


def test_login_returns_jwt(monkeypatch) -> None:
    hashed = hash_password("secret12")

    async def get_user_by_username(username: str) -> FakeUser:
        return FakeUser(id=3, username=username, password=hashed)

    monkeypatch.setattr(userService, "get_user_by_username", get_user_by_username)
    client = TestClient(app)

    response = client.post(
        "/auth/login",
        json={"username": "dawei", "password": "secret12"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == BizCode.SUCCESS.value
    data = body["data"]
    assert data["username"] == "dawei"
    assert data["user_id"] == 3
    assert data["token"]


def test_login_wrong_password(monkeypatch) -> None:
    hashed = hash_password("secret12")

    async def get_user_by_username(username: str) -> FakeUser:
        return FakeUser(id=3, username=username, password=hashed)

    monkeypatch.setattr(userService, "get_user_by_username", get_user_by_username)
    client = TestClient(app)

    response = client.post(
        "/auth/login",
        json={"username": "dawei", "password": "wrong-password"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == BizCode.INVALID_CREDENTIALS.value
    assert body["data"] is None
    assert "token" not in str(body.get("data"))


def test_login_unknown_user(monkeypatch) -> None:
    async def get_user_by_username(username: str) -> FakeUser | None:
        return None

    monkeypatch.setattr(userService, "get_user_by_username", get_user_by_username)
    client = TestClient(app)

    response = client.post(
        "/auth/login",
        json={"username": "ghost", "password": "secret12"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == BizCode.INVALID_CREDENTIALS.value
    assert body["data"] is None


def test_presign_without_token_is_unauthorized() -> None:
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
    assert "detail" not in body
    assert "upload_url" not in body


def test_presign_with_invalid_token_is_unauthorized() -> None:
    client = TestClient(app)
    response = client.post(
        "/files/presign",
        headers={"Authorization": "Bearer not-a-real-token"},
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
    assert "detail" not in body


def test_openapi_is_public() -> None:
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/auth/register" in response.json()["paths"]
    assert "/auth/login" in response.json()["paths"]


def test_protected_route_accepts_valid_token(monkeypatch) -> None:
    from memora_agent.storage.r2 import PresignResult

    class Storage:
        def presign_put(self, filename: str, content_type: str) -> PresignResult:
            return PresignResult(
                upload_url="https://r2.example/upload",
                object_key="abc/notes.pdf",
                expires_in=900,
            )

    monkeypatch.setattr(
        "memora_agent.api.files.files.get_r2_storage",
        lambda: Storage(),
    )
    client = TestClient(app)
    response = client.post(
        "/files/presign",
        headers=bearer_headers(),
        json={
            "filename": "notes.pdf",
            "content_type": "application/pdf",
            "size": 1024,
        },
    )
    assert response.status_code == 200
    assert response.json()["upload_url"]
