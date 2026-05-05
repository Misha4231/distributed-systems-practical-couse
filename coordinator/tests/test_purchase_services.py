import pytest
from mock import AsyncMock, patch

from coordinator.services.purchases import purchase
from coordinator.schemas.purchase import PurchaseRequest
from coordinator.core.exceptions import (
    InsufficientStockError,
    InsufficientBalanceError,
    CommitError,
)


@pytest.mark.anyio
async def test_service_success():
    request = PurchaseRequest(user_id=1, book_id=2, quantity=1)

    with (
        patch("coordinator.clients.participants.prepare_book", new=AsyncMock()) as pb,
        patch("coordinator.clients.participants.prepare_user", new=AsyncMock()) as pu,
        patch("coordinator.clients.participants.commit_user", new=AsyncMock()) as cu,
        patch("coordinator.clients.participants.commit_book", new=AsyncMock()) as cb,
    ):
        pb.return_value.ready = True
        pb.return_value.total_price = 100

        pu.return_value.ready = True

        cu.return_value.remaining_balance = 900
        cb.return_value.remaining_stock = 9

        result = await purchase(request)

    assert result.total_price == 100
    assert result.remaining_balance == 900
    assert result.remaining_stock == 9


@pytest.mark.anyio
async def test_service_insufficient_stock():
    request = PurchaseRequest(user_id=1, book_id=2, quantity=1)

    with (
        patch("coordinator.clients.participants.prepare_book", new=AsyncMock()) as pb,
        patch("coordinator.clients.participants.rollback_book", new=AsyncMock()) as rb,
    ):
        pb.return_value.ready = False
        pb.return_value.reason = "no stock"

        with pytest.raises(InsufficientStockError):
            await purchase(request)

        rb.assert_called_once()


@pytest.mark.anyio
async def test_service_insufficient_balance():
    request = PurchaseRequest(user_id=1, book_id=2, quantity=1)

    with (
        patch("coordinator.clients.participants.prepare_book", new=AsyncMock()) as pb,
        patch("coordinator.clients.participants.prepare_user", new=AsyncMock()) as pu,
        patch("coordinator.clients.participants.rollback_book", new=AsyncMock()) as rb,
    ):
        pb.return_value.ready = True
        pb.return_value.total_price = 100

        pu.return_value.ready = False
        pu.return_value.reason = "no money"

        with pytest.raises(InsufficientBalanceError):
            await purchase(request)

        rb.assert_called_once()


@pytest.mark.anyio
async def test_service_commit_failure():
    request = PurchaseRequest(user_id=1, book_id=2, quantity=1)

    with (
        patch("coordinator.clients.participants.prepare_book", new=AsyncMock()) as pb,
        patch("coordinator.clients.participants.prepare_user", new=AsyncMock()) as pu,
        patch(
            "coordinator.clients.participants.commit_user",
            new=AsyncMock(side_effect=Exception()),
        ),
        patch("coordinator.clients.participants.rollback_user", new=AsyncMock()) as ru,
        patch("coordinator.clients.participants.rollback_book", new=AsyncMock()) as rb,
    ):
        pb.return_value.ready = True
        pb.return_value.total_price = 100
        pu.return_value.ready = True

        with pytest.raises(CommitError):
            await purchase(request)

        ru.assert_called_once()
        rb.assert_called_once()


@pytest.mark.anyio
async def test_prepare_book_exception():
    request = PurchaseRequest(user_id=1, book_id=2, quantity=1)

    with patch(
        "coordinator.clients.participants.prepare_book",
        new=AsyncMock(side_effect=Exception("network error")),
    ):
        with pytest.raises(Exception):
            await purchase(request)


@pytest.mark.anyio
async def test_prepare_user_exception():
    request = PurchaseRequest(user_id=1, book_id=2, quantity=1)

    with (
        patch("coordinator.clients.participants.prepare_book", new=AsyncMock()) as pb,
        patch(
            "coordinator.clients.participants.prepare_user",
            new=AsyncMock(side_effect=Exception("network error")),
        ),
    ):
        pb.return_value.ready = True
        pb.return_value.total_price = 100

        with pytest.raises(Exception):
            await purchase(request)


@pytest.mark.anyio
async def test_insufficient_stock_default_message():
    request = PurchaseRequest(user_id=1, book_id=2, quantity=1)

    with (
        patch("coordinator.clients.participants.prepare_book", new=AsyncMock()) as pb,
        patch("coordinator.clients.participants.rollback_book", new=AsyncMock()),
    ):
        pb.return_value.ready = False
        pb.return_value.reason = None

        with pytest.raises(InsufficientStockError) as exc:
            await purchase(request)

        assert "Insufficient stock" in str(exc.value)


@pytest.mark.anyio
async def test_insufficient_balance_default_message():
    request = PurchaseRequest(user_id=1, book_id=2, quantity=1)

    with (
        patch("coordinator.clients.participants.prepare_book", new=AsyncMock()) as pb,
        patch("coordinator.clients.participants.prepare_user", new=AsyncMock()) as pu,
        patch("coordinator.clients.participants.rollback_book", new=AsyncMock()),
    ):
        pb.return_value.ready = True
        pb.return_value.total_price = 100

        pu.return_value.ready = False
        pu.return_value.reason = None

        with pytest.raises(InsufficientBalanceError) as exc:
            await purchase(request)

        assert "Insufficient balance" in str(exc.value)
