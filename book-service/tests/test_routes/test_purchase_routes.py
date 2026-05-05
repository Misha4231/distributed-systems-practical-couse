import pytest
import uuid
from httpx import AsyncClient

from sqlalchemy.ext.asyncio import AsyncSession
from tests.helper import cleanup_prepared, create_book
from book_service.services import purchases as purchases_service


# ----------------- prepare
@pytest.mark.anyio
async def test_route_prepare_success(client: AsyncClient, db_session_2pc: AsyncSession):
    book = await create_book(
        db_session_2pc, title="some title", author="author1", stock=10, price=20.0
    )
    transaction_id = str(uuid.uuid4())

    response = await client.post(
        "/purchases/prepare",
        json={
            "transaction_id": transaction_id,
            "book_id": book.id,
            "quantity": 2,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True
    assert data["transaction_id"] == transaction_id
    assert float(data["total_price"]) == 40.0

    await cleanup_prepared(db_session_2pc, transaction_id)


@pytest.mark.anyio
async def test_route_prepare_insufficient_stock(
    client: AsyncClient, db_session_2pc: AsyncSession
):
    book = await create_book(
        db_session_2pc, title="some title", author="author1", stock=1, price=20.0
    )
    transaction_id = str(uuid.uuid4())

    response = await client.post(
        "/purchases/prepare",
        json={
            "transaction_id": transaction_id,
            "book_id": book.id,
            "quantity": 99,
        },
    )

    assert response.status_code == 200
    assert response.json()["ready"] is False


@pytest.mark.anyio
async def test_route_prepare_book_not_found(client: AsyncClient):
    response = await client.post(
        "/purchases/prepare",
        json={
            "transaction_id": str(uuid.uuid4()),
            "book_id": 99999,
            "quantity": 1,
        },
    )

    assert response.status_code == 200
    assert response.json()["ready"] is False


# ----------------- prepare + commit


@pytest.mark.anyio
async def test_route_commit_success(client: AsyncClient, db_session_2pc: AsyncSession):
    book = await create_book(
        db_session_2pc, title="some title", author="author1", stock=10, price=20.0
    )
    transaction_id = str(uuid.uuid4())

    await purchases_service.prepare(transaction_id, book.id, 3)

    response = await client.post(
        "/purchases/commit",
        json={
            "transaction_id": transaction_id,
            "book_id": book.id,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["remaining_stock"] == 7


@pytest.mark.anyio
async def test_route_commit_unknown_transaction(client: AsyncClient):
    response = await client.post(
        "/purchases/commit",
        json={
            "transaction_id": "qweqwe",
            "book_id": 1,
        },
    )

    assert response.status_code == 500


# ----------------- prepare + rollback


@pytest.mark.anyio
async def test_route_rollback_success(
    client: AsyncClient, db_session_2pc: AsyncSession
):
    book = await create_book(
        db_session_2pc, title="some title", author="author1", stock=10, price=20.0
    )
    transaction_id = str(uuid.uuid4())

    await purchases_service.prepare(transaction_id, book.id, 4)

    response = await client.post(
        "/purchases/rollback",
        json={
            "transaction_id": transaction_id,
        },
    )

    assert response.status_code == 204

    await db_session_2pc.refresh(book)
    assert book.stock == 10


@pytest.mark.anyio
async def test_route_rollback_unknown_transaction(client: AsyncClient):
    response = await client.post(
        "/purchases/rollback",
        json={
            "transaction_id": "asdasd",
        },
    )

    assert response.status_code == 500
