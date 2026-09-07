from sqlalchemy import select

from memora_agent.db.database import AsyncSessionLocal
from memora_agent.db.models.user import User


class UserService:
    # async def create_user(
    #     self,
    #     username: str,
    #     password: str,
    #     nickname: str | None = None,
    # ) -> User:
    #     async with AsyncSessionLocal() as session:
    #         user = User(username=username, password=password)
    #         if nickname is not None:
    #             user.nickname = nickname
    #         session.add(user)
    #         await session.commit()
    #         await session.refresh(user)
    #         return user

    # async def get_user_by_id(self, user_id: int) -> User | None:
    #     async with AsyncSessionLocal() as session:
    #         return await session.get(User, user_id)

    # async def get_user_by_username(self, username: str) -> User | None:
    #     async with AsyncSessionLocal() as session:
    #         result = await session.execute(
    #             select(User).where(User.username == username)
    #         )
    #         return result.scalar_one_or_none()

    # async def list_users(self) -> list[User]:
    #     async with AsyncSessionLocal() as session:
    #         result = await session.execute(select(User).order_by(User.id.desc()))
    #         return list(result.scalars().all())

    # async def update_user(
    #     self,
    #     user_id: int,
    #     *,
    #     nickname: str | None = None,
    #     password: str | None = None,
    # ) -> User | None:
    #     async with AsyncSessionLocal() as session:
    #         user = await session.get(User, user_id)
    #         if user is None:
    #             return None
    #         if nickname is not None:
    #             user.nickname = nickname
    #         if password is not None:
    #             user.password = password
    #         await session.commit()
    #         await session.refresh(user)
    #         return user

    # async def delete_user(self, user_id: int) -> bool:
        async with AsyncSessionLocal() as session:
            user = await session.get(User, user_id)
            if user is None:
                return False
            await session.delete(user)
            await session.commit()
            return True


userService = UserService()
