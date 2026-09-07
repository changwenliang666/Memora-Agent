from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from memora_agent.core.auth import hash_password
from memora_agent.db.database import AsyncSessionLocal
from memora_agent.db.models.user import User


class UserAlreadyExistsError(Exception):
    pass


class UserService:
    async def create_user(self, username: str, password: str) -> User:
        async with AsyncSessionLocal() as session:
            user = User(username=username, password=hash_password(password))
            session.add(user)
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise UserAlreadyExistsError from exc
            await session.refresh(user)
            return user

    async def get_user_by_username(self, username: str) -> User | None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where(User.username == username)
            )
            return result.scalar_one_or_none()


userService = UserService()
