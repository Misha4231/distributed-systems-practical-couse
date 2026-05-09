"""create users table

Revision ID: 2d036ff97351
Revises: 
Create Date: 2026-05-07 13:01:23.699935

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func


# revision identifiers, used by Alembic.
revision: str = '2d036ff97351'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("balance", sa.DECIMAL(8, 2), default=0),
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
    op.drop_table("users")
