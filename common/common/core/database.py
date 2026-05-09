from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import URL

from common.core.settings import settings

DATABASE_URL = URL.create(
    drivername="postgresql+asyncpg",
    username=settings.postgres_user,
    password=settings.postgres_password,
    host=settings.postgres_host,
    port=settings.postgres_port,
    database=settings.postgres_db,
)
engine = create_async_engine(DATABASE_URL, isolation_level="REPEATABLE READ")

AsyncSessionLocal = sessionmaker(
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    bind=engine,
    class_=AsyncSession,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
