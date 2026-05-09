import os

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
    AsyncEngine,
)
from sqlalchemy import NullPool, text
from sqlalchemy.engine import URL

from common.models.base import Model

pytest_plugins = ["anyio"]


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


# Setup test database engine
@pytest.fixture(scope="session")
def test_engine():
    DATABASE_URL = URL.create(
        drivername="postgresql+psycopg",
        username=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        database=os.getenv("POSTGRES_DB"),
    )
    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    return engine


# Setup test database
@pytest.fixture(scope="session")
async def setup_db(test_engine: AsyncEngine):
    async with test_engine.begin() as conn:
        await conn.run_sync(Model.metadata.create_all)

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Model.metadata.drop_all)

    await test_engine.dispose()


# Setup test database session
@pytest.fixture
async def db_session(test_engine: AsyncEngine, setup_db):
    conn = await test_engine.connect()
    transaction = await conn.begin()

    test_async_session = async_sessionmaker(
        bind=conn,
        class_=AsyncSession,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",  # data is not really saved in database so that tests are isolated
    )

    async with test_async_session() as session:
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
            await conn.close()