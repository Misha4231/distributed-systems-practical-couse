import pytest
from mock import patch, AsyncMock
from httpx import AsyncClient

from coordinator.schemas.purchase import PurchaseResponse
from coordinator.core.exceptions import (
    InsufficientStockError,
    InsufficientBalanceError,
    CommitError,
)


@pytest.mark.anyio
async def test_purchase_success(client: AsyncClient):
    mock_response = PurchaseResponse(
        user_id=1,
        book_id=1,
        quantity=1,
        total_price=20.0,
        remaining_balance=40.0,
        remaining_stock=10,
    )

    with patch(
        "coordinator.services.purchases.purchase",
        new=AsyncMock(return_value=mock_response),
    ):
        response = await client.post(
            "/orders/purchase", json={"user_id": 1, "book_id": 1, "quantity": 1}
        )

    assert response.status_code == 200
    assert response.json()["total_price"] == 20.0


@pytest.mark.anyio
async def test_purchase_insufficient_stock(client: AsyncClient):
    with patch(
        "coordinator.services.purchases.purchase",
        new=AsyncMock(side_effect=InsufficientStockError("no stock")),
    ):
        response = await client.post(
            "/orders/purchase", json={"user_id": 1, "book_id": 1, "quantity": 1}
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "no stock"


@pytest.mark.anyio
async def test_purchase_insufficient_balance(client: AsyncClient):
    with patch(
        "coordinator.services.purchases.purchase",
        new=AsyncMock(side_effect=InsufficientBalanceError("no balance")),
    ):
        response = await client.post(
            "/orders/purchase", json={"user_id": 1, "book_id": 1, "quantity": 1}
        )

    assert response.status_code == 402
    assert response.json()["detail"] == "no balance"


@pytest.mark.anyio
async def test_purchase_commit_error(client: AsyncClient):
    with patch(
        "coordinator.services.purchases.purchase",
        new=AsyncMock(side_effect=CommitError()),
    ):
        response = await client.post(
            "/orders/purchase", json={"user_id": 1, "book_id": 1, "quantity": 1}
        )

    assert response.status_code == 500
    assert response.json()["detail"] == "Transaction failed during commit"
