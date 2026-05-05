import pytest
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from user_service.services import purchases as purchases_service
from tests.helper import cleanup_prepared, create_user


# ----------------- prepare
@pytest.mark.anyio
async def test_prepare_success(db_session_2pc: AsyncSession):
    user = await create_user(db_session_2pc, "user1", 200.0)
    transaction_id = str(uuid.uuid4())

    result = await purchases_service.prepare(transaction_id, user.id, 50.0)

    assert result.ready == True
    assert result.transaction_id == transaction_id

    await cleanup_prepared(db_session_2pc, transaction_id)


@pytest.mark.anyio
async def test_prepare_user_not_found(db_session_2pc: AsyncSession):
    transaction_id = str(uuid.uuid4())

    result = await purchases_service.prepare(transaction_id, 999, 50.0)

    assert result.ready == False
    assert result.transaction_id == transaction_id


@pytest.mark.anyio
async def test_prepare_user_insufficient_balance(db_session_2pc: AsyncSession):
    user = await create_user(db_session_2pc, "user1", 10.0)
    transaction_id = str(uuid.uuid4())

    result = await purchases_service.prepare(transaction_id, user.id, 50.0)

    assert result.ready == False
    assert result.transaction_id == transaction_id


@pytest.mark.anyio
async def test_prepare_user_exact_balance(db_session_2pc: AsyncSession):
    user = await create_user(db_session_2pc, "user1", 10.0)
    transaction_id = str(uuid.uuid4())

    result = await purchases_service.prepare(transaction_id, user.id, 10.0)

    assert result.ready == True
    assert result.transaction_id == transaction_id

    await cleanup_prepared(db_session_2pc, transaction_id)


# ----------------- prepare + commit


@pytest.mark.anyio
async def test_commit_deducts_balance(db_session_2pc: AsyncSession):
    user = await create_user(db_session_2pc, "dave", 100.0)
    transaction_id = str(uuid.uuid4())

    await purchases_service.prepare(transaction_id, user.id, 30.0)
    result = await purchases_service.commit(transaction_id, user.id)

    assert result.remaining_balance == 70.0
    assert result.transaction_id == transaction_id


@pytest.mark.anyio
async def test_commit_persists_to_db(db_session_2pc: AsyncSession):
    user = await create_user(db_session_2pc, "eve", 100.0)
    transaction_id = str(uuid.uuid4())

    await purchases_service.prepare(transaction_id, user.id, 40.0)
    await purchases_service.commit(transaction_id, user.id)

    await db_session_2pc.refresh(user)
    assert float(user.balance) == 60.0


@pytest.mark.anyio
async def test_commit_unknown_transaction(db_session_2pc: AsyncSession):
    """Committing a transaction_id that was never prepared should raise."""
    with pytest.raises(Exception):
        await purchases_service.commit("asdasdasd", 1)


# ----------------- prepare + rollback


@pytest.mark.anyio
async def test_rollback_restores_balance(db_session_2pc: AsyncSession):
    user = await create_user(db_session_2pc, "frank", 100.0)
    transaction_id = str(uuid.uuid4())

    await purchases_service.prepare(transaction_id, user.id, 60.0)
    await purchases_service.rollback(transaction_id)

    await db_session_2pc.refresh(user)
    assert float(user.balance) == 100.0


@pytest.mark.anyio
async def test_rollback_unknown_transaction(db_session_2pc: AsyncSession):
    """Rolling back a nonexistent prepared transaction should raise."""
    with pytest.raises(Exception):
        await purchases_service.rollback("qweqweqw")


@pytest.mark.anyio
async def test_rollback_then_commit_fails(db_session_2pc: AsyncSession):
    """After rollback the prepared transaction no longer exists — commit must fail."""
    user = await create_user(db_session_2pc, "grace", 100.0)
    transaction_id = str(uuid.uuid4())

    await purchases_service.prepare(transaction_id, user.id, 20.0)
    await purchases_service.rollback(transaction_id)

    with pytest.raises(Exception):
        await purchases_service.commit(transaction_id, user.id)
