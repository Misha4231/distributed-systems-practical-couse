from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from book_service.models.book import Book


async def create_book(
    db_session: AsyncSession, title: str, author: str, stock: int, price: float
) -> Book:
    # we are not using book_service.create_user to keep tests isolated
    book = Book(title=title, author=author, stock=stock, price=price)
    db_session.add(book)

    await db_session.commit()
    await db_session.refresh(book)
    return book


async def cleanup_prepared(db_session: AsyncSession, transaction_id: str) -> None:
    # Rollback a prepared transaction if it was left open by a failed test.
    try:
        conn = await db_session.connection()
        await conn.execution_options(isolation_level="AUTOCOMMIT")
        await conn.execute(text(f"ROLLBACK PREPARED '{transaction_id}'"))
    except Exception:
        pass
