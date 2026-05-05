import pytest

from httpx import AsyncClient, ASGITransport

from coordinator.main import app


# Setup http client
@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://coordinator_test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
