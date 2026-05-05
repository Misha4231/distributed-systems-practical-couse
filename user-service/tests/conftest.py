import pytest
from mock import patch

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine
from sqlalchemy import text

from user_service.main import app
from common.core.database import get_db

pytest_plugins = ["common.tests.db_conf"]


# Setup http client
@pytest.fixture
async def client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://users_test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def patch_user_service_engine(test_engine: AsyncEngine):
    with patch("user_service.services.purchases.engine", test_engine):
        yield


@pytest.fixture
def tables_to_cleanup() -> list[str]:
    return [
        "users",
    ]
