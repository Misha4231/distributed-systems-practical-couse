from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy import text

from common.schemas.purchase import PrepareResponse, UserCommitResponse
from user_service.core.logging import logger
from user_service.models.user import User
from common.core.database import engine

"""
Opens a database session, locks user row, validate balance
"""


async def prepare(transaction_id: str, user_id: int, amount: float) -> PrepareResponse:
    logger.info("user_prepare_start", transaction_id=transaction_id, user_id=user_id)

    # using raw sql to use prepare
    async with engine.connect() as conn:
        try:
            tx = await conn.begin()
            result = await conn.execute(
                text("SELECT * FROM users WHERE id = :id FOR UPDATE NOWAIT"),
                {"id": user_id},
            )
            user = result.mappings().first()

            if user is None:
                await tx.rollback()

                logger.warning(
                    "user_prepare_not_found",
                    transaction_id=transaction_id,
                    user_id=user_id,
                )
                return PrepareResponse(
                    transaction_id=transaction_id, ready=False, reason="User not found"
                )

            if user["balance"] < amount:
                await tx.rollback()
                logger.warning(
                    "user_prepare_insufficient_balance",
                    transaction_id=transaction_id,
                    user_id=user_id,
                    balance=user["balance"],
                    required=amount,
                )

                return PrepareResponse(
                    transaction_id=transaction_id,
                    ready=False,
                    reason=f"Insufficient balance: has {user['balance']}, needs {amount}",
                )

            # don't commit
            await conn.execute(
                text("UPDATE users SET balance = balance - :amount WHERE id = :id"),
                {"amount": amount, "id": user_id},
            )

            await conn.execute(
                text(f"PREPARE TRANSACTION '{transaction_id}'")
            )  # detach transaction from connection
            logger.info(
                "user_prepare_ready", transaction_id=transaction_id, user_id=user_id
            )
            return PrepareResponse(transaction_id=transaction_id, ready=True)

        except Exception as e:
            await tx.rollback()
            logger.error(
                "user_prepare_error", transaction_id=transaction_id, error=str(e)
            )
            raise


async def commit(transaction_id: str, user_id: int) -> UserCommitResponse:
    async with engine.connect() as conn:
        conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
        await conn.execute(text(f"COMMIT PREPARED '{transaction_id}'"))

        logger.info("user_commit_success", transaction_id=transaction_id)

        # query updated user after commit
        result = await conn.execute(
            text("SELECT * FROM users WHERE id = :id"), {"id": user_id}
        )
        user = result.mappings().first()

        return UserCommitResponse(
            transaction_id=transaction_id, remaining_balance=float(user["balance"])
        )


async def rollback(transaction_id: str) -> None:
    async with engine.connect() as conn:
        conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
        await conn.execute(text(f"ROLLBACK PREPARED '{transaction_id}'"))

        logger.info("user_rollback_success", transaction_id=transaction_id)
        return
