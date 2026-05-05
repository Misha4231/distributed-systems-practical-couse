import pytest
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from book_service.services import purchases as purchases_service
from tests.helper import cleanup_prepared, create_book

# ----------------- prepare


@pytest.mark.anyio
async def test_prepare_success(db_session_2pc: AsyncSession):
    book = await create_book(
        db_session_2pc, title="some title", author="author1", stock=10, price=15.0
    )
    transaction_id = str(uuid.uuid4())

    result = await purchases_service.prepare(transaction_id, book.id, 2)

    assert result.ready is True
    assert result.transaction_id == transaction_id
    assert float(result.total_price) == 30.0

    await cleanup_prepared(db_session_2pc, transaction_id)


@pytest.mark.anyio
async def test_prepare_book_not_found(db_session_2pc: AsyncSession):
    transaction_id = str(uuid.uuid4())

    result = await purchases_service.prepare(transaction_id, 99999, 1)

    assert result.ready is False


@pytest.mark.anyio
async def test_prepare_insufficient_stock(db_session_2pc: AsyncSession):
    book = await create_book(
        db_session_2pc, title="some title", author="author1", stock=2, price=15.0
    )
    transaction_id = str(uuid.uuid4())

    result = await purchases_service.prepare(transaction_id, book.id, 10)

    assert result.ready is False


@pytest.mark.anyio
async def test_prepare_exact_stock(db_session_2pc: AsyncSession):
    book = await create_book(
        db_session_2pc, title="some title", author="author1", stock=5, price=15.0
    )
    transaction_id = str(uuid.uuid4())

    result = await purchases_service.prepare(transaction_id, book.id, 5)

    assert result.ready is True

    await cleanup_prepared(db_session_2pc, transaction_id)


@pytest.mark.anyio
async def test_prepare_total_price_calculation(db_session_2pc: AsyncSession):
    book = await create_book(
        db_session_2pc, title="some title", author="author1", stock=10, price=9.99
    )
    transaction_id = str(uuid.uuid4())

    result = await purchases_service.prepare(transaction_id, book.id, 3)

    assert result.ready is True
    assert float(result.total_price) == 29.97

    await cleanup_prepared(db_session_2pc, transaction_id)


# ----------------- prepare + commit


@pytest.mark.anyio
async def test_commit_decrements_stock(db_session_2pc: AsyncSession):
    book = await create_book(
        db_session_2pc, title="some title", author="author1", stock=10, price=9.99
    )
    transaction_id = str(uuid.uuid4())

    await purchases_service.prepare(transaction_id, book.id, 3)
    result = await purchases_service.commit(transaction_id, book.id)

    assert result.remaining_stock == 7
    assert result.transaction_id == transaction_id


@pytest.mark.anyio
async def test_commit_persists_to_db(db_session_2pc: AsyncSession):
    book = await create_book(
        db_session_2pc, title="some title", author="author1", stock=10, price=9.99
    )
    transaction_id = str(uuid.uuid4())

    await purchases_service.prepare(transaction_id, book.id, 4)
    await purchases_service.commit(transaction_id, book.id)

    await db_session_2pc.refresh(book)
    assert book.stock == 6


@pytest.mark.anyio
async def test_commit_unknown_transaction(db_session_2pc: AsyncSession):
    with pytest.raises(Exception):
        await purchases_service.commit("qweqwe", 1)


# ----------------- prepare + rolback


@pytest.mark.anyio
async def test_rollback_restores_stock(db_session_2pc: AsyncSession):
    book = await create_book(
        db_session_2pc, title="some title", author="author1", stock=10, price=9.99
    )
    transaction_id = str(uuid.uuid4())

    await purchases_service.prepare(transaction_id, book.id, 5)
    await purchases_service.rollback(transaction_id)

    await db_session_2pc.refresh(book)
    assert book.stock == 10


@pytest.mark.anyio
async def test_rollback_unknown_transaction(db_session_2pc: AsyncSession):
    with pytest.raises(Exception):
        await purchases_service.rollback("asdasd")


@pytest.mark.anyio
async def test_rollback_then_commit_fails(db_session_2pc: AsyncSession):
    book = await create_book(
        db_session_2pc, title="some title", author="author1", stock=10, price=9.99
    )
    transaction_id = str(uuid.uuid4())

    await purchases_service.prepare(transaction_id, book.id, 2)
    await purchases_service.rollback(transaction_id)

    with pytest.raises(Exception):
        await purchases_service.commit(transaction_id, book.id)
