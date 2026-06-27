from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings

# Async engine setup
engine = create_async_engine(
    settings.DB.URL,
    echo=False,
    pool_recycle=3600,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, 
    autocommit=False, 
    autoflush=False, 
    expire_on_commit=False
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yields an asynchronous database session per request."""
    async with AsyncSessionLocal() as db:
        yield db