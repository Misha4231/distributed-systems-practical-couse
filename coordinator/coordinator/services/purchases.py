import uuid

from coordinator.core.logging import logger
from coordinator.schemas.purchase import PurchaseRequest, PurchaseResponse
from coordinator.core.exceptions import (
    InsufficientStockError,
    CommitError,
    InsufficientBalanceError,
)
from coordinator.clients import participants as http


async def purchase(request: PurchaseRequest) -> PurchaseResponse:
    transaction_id = str(uuid.uuid4())
    logger.info(
        "purchase_service_start",
        transaction_id=transaction_id,
        user_id=request.user_id,
        book_id=request.book_id,
        quantity=request.quantity,
    )

    # Prepare phase
    try:
        book_vote = await http.prepare_book(
            transaction_id, request.book_id, request.quantity
        )
    except Exception as e:
        logger.error("prepare_book_error", transaction_id=transaction_id, error=str(e))
        raise

    if not book_vote.ready:
        # Book already prepared, must roll it back before surfacing the error
        await http.rollback_book(transaction_id)

        logger.warning(
            "purchase_book_vote_no",
            transaction_id=transaction_id,
            reason=book_vote.reason,
        )
        raise InsufficientStockError(
            book_vote.reason if book_vote.reason else "Insufficient stock"
        )

    try:
        user_vote = await http.prepare_user(
            transaction_id, request.user_id, book_vote.total_price
        )
    except Exception as e:
        logger.error("prepare_user_error", transaction_id=transaction_id, error=str(e))
        raise

    if not user_vote.ready:
        logger.warning(
            "purchase_user_vote_no",
            transaction_id=transaction_id,
            reason=user_vote.reason,
        )
        # Book already prepared, must roll it back before surfacing the error
        await http.rollback_book(transaction_id)
        raise InsufficientBalanceError(
            user_vote.reason if user_vote.reason else "Insufficient balance"
        )

    logger.info("purchase_both_voted_yes", transaction_id=transaction_id)

    # Prepare commit
    try:
        user_result = await http.commit_user(transaction_id, request.user_id)
        book_result = await http.commit_book(transaction_id, request.book_id)
    except Exception as e:
        logger.error(
            "purchase_commit_failed", transaction_id=transaction_id, error=str(e)
        )
        await http.rollback_user(transaction_id)
        await http.rollback_book(transaction_id)
        raise CommitError("Commit failed after successful prepare") from e

    logger.info("purchase_success", transaction_id=transaction_id)
    return PurchaseResponse(
        user_id=request.user_id,
        book_id=request.book_id,
        quantity=request.quantity,
        total_price=book_vote.total_price,
        remaining_balance=user_result.remaining_balance,
        remaining_stock=book_result.remaining_stock,
    )
