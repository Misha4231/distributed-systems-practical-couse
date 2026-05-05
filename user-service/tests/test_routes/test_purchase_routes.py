import pytest
import uuid
from httpx import AsyncClient

from sqlalchemy.ext.asyncio import AsyncSession
from tests.helper import cleanup_prepared, create_user
from user_service.services import purchases as purchases_service


# ----------------- prepare
@pytest.mark.anyio
async def test_route_prepare_success(client: AsyncClient, db_session_2pc: AsyncSession):
    user = await create_user(db_session_2pc, "henry", 200.0)
    transaction_id = str(uuid.uuid4())

    response = await client.post(
        "/purchases/prepare",
        json={
            "transaction_id": transaction_id,
            "user_id": user.id,
            "amount": 50.0,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True
    assert data["transaction_id"] == transaction_id

    await cleanup_prepared(db_session_2pc, transaction_id)


@pytest.mark.anyio
async def test_route_prepare_insufficient_balance(
    client: AsyncClient, db_session_2pc: AsyncSession
):
    user = await create_user(db_session_2pc, "iris", 10.0)
    transaction_id = str(uuid.uuid4())

    response = await client.post(
        "/purchases/prepare",
        json={
            "transaction_id": transaction_id,
            "user_id": user.id,
            "amount": 999.0,
        },
    )

    assert response.status_code == 200
    assert response.json()["ready"] is False


@pytest.mark.anyio
async def test_route_prepare_user_not_found(client: AsyncClient):
    response = await client.post(
        "/purchases/prepare",
        json={
            "transaction_id": str(uuid.uuid4()),
            "user_id": 99999,
            "amount": 10.0,
        },
    )

    assert response.status_code == 200
    assert response.json()["ready"] is False


# ----------------- prepare + commit


@pytest.mark.anyio
async def test_route_commit_success(client: AsyncClient, db_session_2pc: AsyncSession):
    user = await create_user(db_session_2pc, "jack", 100.0)
    transaction_id = str(uuid.uuid4())

    await purchases_service.prepare(transaction_id, user.id, 25.0)

    response = await client.post(
        "/purchases/commit",
        json={
            "transaction_id": transaction_id,
            "user_id": user.id,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["remaining_balance"] == 75.0


@pytest.mark.anyio
async def test_route_commit_unknown_transaction(client: AsyncClient):
    response = await client.post(
        "/purchases/commit",
        json={
            "transaction_id": "qweqweqwwe",
            "user_id": 1,
        },
    )

    assert response.status_code == 500


# ----------------- prepare + rollback


@pytest.mark.anyio
async def test_route_rollback_success(
    client: AsyncClient, db_session_2pc: AsyncSession
):
    user = await create_user(db_session_2pc, "kate", 100.0)
    transaction_id = str(uuid.uuid4())

    await purchases_service.prepare(transaction_id, user.id, 40.0)

    response = await client.post(
        "/purchases/rollback",
        json={
            "transaction_id": transaction_id,
        },
    )

    assert response.status_code == 204

    await db_session_2pc.refresh(user)
    assert float(user.balance) == 100.0


@pytest.mark.anyio
async def test_route_rollback_unknown_transaction(client: AsyncClient):
    response = await client.post(
        "/purchases/rollback",
        json={
            "transaction_id": "asdasda",
        },
    )

    assert response.status_code == 500
