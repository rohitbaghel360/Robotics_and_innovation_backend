from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Generic CRUD helpers. Extend per module repository."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, id_: int) -> ModelT | None:
        return await self.session.get(self.model, id_)

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[ModelT]:
        result = await self.session.execute(
            select(self.model).limit(limit).offset(offset)
        )
        return list(result.scalars().all())
