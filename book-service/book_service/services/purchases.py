from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from common.schemas.purchase import BookCommitResponse, BookPrepareResponse
from book_service.core.logging import logger
from common.core.database import engine

"""
Opens a database session, locks books row, validate stock
"""


async def prepare(
    transaction_id: str, book_id: int, quantity: int
) -> BookPrepareResponse:
    logger.info(
        "book_prepare_start",
        transaction_id=transaction_id,
        book_id=book_id,
        quantity=quantity,
    )

    # using raw sql to use prepare
    async with engine.connect() as conn:
        try:
            tx = await conn.begin()
            result = await conn.execute(
                text("SELECT * FROM books WHERE id = :id FOR UPDATE NOWAIT"),
                {"id": book_id},
            )
            book = result.mappings().first()

            if book is None:
                await tx.rollback()

                logger.warning(
                    "book_prepare_not_found",
                    transaction_id=transaction_id,
                    book_id=book_id,
                )
                return BookPrepareResponse(
                    transaction_id=transaction_id, ready=False, reason="Book not found"
                )

            if book["stock"] < quantity:
                await tx.rollback()
                logger.warning(
                    "book_prepare_insufficient_stock",
                    transaction_id=transaction_id,
                    book_id=book_id,
                    quantity=quantity,
                    required=book["stock"],
                )

                return BookPrepareResponse(
                    transaction_id=transaction_id,
                    ready=False,
                    reason=f"Insufficient stock: has {book['stock']}, needs {quantity}",
                )

            # don't commit
            await conn.execute(
                text("UPDATE books SET stock = stock - :quantity WHERE id = :id"),
                {"quantity": quantity, "id": book_id},
            )

            total_price = book["price"] * quantity

            await conn.execute(
                text(f"PREPARE TRANSACTION '{transaction_id}'")
            )  # detach transaction from connection
            logger.info(
                "book_prepare_ready", transaction_id=transaction_id, book_id=book_id
            )
            return BookPrepareResponse(
                transaction_id=transaction_id, ready=True, total_price=total_price
            )

        except Exception as e:
            await tx.rollback()
            logger.error(
                "book_prepare_error", transaction_id=transaction_id, error=str(e)
            )
            raise


async def commit(transaction_id: str, book_id: int) -> BookCommitResponse:
    async with engine.connect() as conn:
        conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
        await conn.execute(text(f"COMMIT PREPARED '{transaction_id}'"))

        logger.info("book_commit_success", transaction_id=transaction_id)

        # query updated book after commit
        result = await conn.execute(
            text("SELECT * FROM books WHERE id = :id"), {"id": book_id}
        )
        book = result.mappings().first()

        return BookCommitResponse(
            transaction_id=transaction_id, remaining_stock=int(book["stock"])
        )


async def rollback(transaction_id: str) -> None:
    async with engine.connect() as conn:
        conn = await conn.execution_options(isolation_level="AUTOCOMMIT")

        await conn.execute(text(f"ROLLBACK PREPARED '{transaction_id}'"))

        logger.info("book_rollback_success", transaction_id=transaction_id)
        return
