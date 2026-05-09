"""create books table

Revision ID: 4c3d6792331c
Revises: 
Create Date: 2026-05-08 12:39:00.985100

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func


# revision identifiers, used by Alembic.
revision: str = '4c3d6792331c'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "books",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True, index=True),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("author", sa.String(100), nullable=False),
        sa.Column("stock", sa.Integer, nullable=False, default=0),
        sa.Column("price", sa.DECIMAL(8, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("books")
