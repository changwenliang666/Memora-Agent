import asyncio

from sqlalchemy.exc import IntegrityError

import pytest

from app.core.auth import verify_password
from app.db.models.user import User
from app.service.user_service import UserAlreadyExistsError, UserService


class FakeResult:
    def __init__(self, user: User | None) -> None:
        self._user = user

    def scalar_one_or_none(self) -> User | None:
        return self._user


class FakeSession:
    def __init__(
        self,
        *,
        existing: User | None = None,
        commit_error: Exception | None = None,
    ) -> None:
        self.added: list[User] = []
        self.existing = existing
        self.commit_error = commit_error
        self.rolled_back = False

    def add(self, obj: User) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        if self.commit_error is not None:
            raise self.commit_error
        for obj in self.added:
            obj.id = 1

    async def refresh(self, obj: User) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = 1

    async def rollback(self) -> None:
        self.rolled_back = True

    async def execute(self, _stmt) -> FakeResult:
        return FakeResult(self.existing)

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


def test_create_user_stores_hashed_password(monkeypatch) -> None:
    session = FakeSession()
    monkeypatch.setattr(
        "app.service.user_service.AsyncSessionLocal",
        lambda: session,
    )
    service = UserService()

    async def _run() -> User:
        return await service.create_user("dawei", "secret12")

    user = asyncio.run(_run())

    assert user.username == "dawei"
    assert user.password != "secret12"
    assert verify_password("secret12", user.password)
    assert session.added == [user]


def test_create_user_duplicate_username(monkeypatch) -> None:
    session = FakeSession(commit_error=IntegrityError("insert", {}, None))
    monkeypatch.setattr(
        "app.service.user_service.AsyncSessionLocal",
        lambda: session,
    )
    service = UserService()

    async def _run() -> None:
        await service.create_user("dawei", "secret12")

    with pytest.raises(UserAlreadyExistsError):
        asyncio.run(_run())
    assert session.rolled_back is True
