from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from user_service.models.user import User


async def create_user(db_session: AsyncSession, name: str, balance: float) -> User:
    # we are not using user_service.create_user to make tests isolated
    user = User(name=name, balance=balance)
    db_session.add(user)

    await db_session.commit()
    await db_session.refresh(user)
    return user


async def cleanup_prepared(db_session: AsyncSession, transaction_id: str) -> None:
    # Roll back a prepared transaction if it was left open by a failed test.
    try:
        conn = await db_session.connection()
        await conn.execution_options(isolation_level="AUTOCOMMIT")
        await conn.execute(text(f"ROLLBACK PREPARED '{transaction_id}'"))
    except Exception:
        pass
