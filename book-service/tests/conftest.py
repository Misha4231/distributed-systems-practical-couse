import pytest

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from book_service.main import app
from common.core.database import get_db

pytest_plugins = ["common.tests.db_conf"]


# Setup http client
@pytest.fixture
async def client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://books_test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
