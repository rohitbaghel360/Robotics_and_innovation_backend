from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.base_repository import BaseRepository
from app.modules.auth.models import User


class AuthRepository(BaseRepository[User]):
    model = User

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create(self, email: str, hashed_password: str) -> User:
        user = User(email=email, hashed_password=hashed_password)
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user
