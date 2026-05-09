"""add timestamp columns

Revision ID: f66ac93a3482
Revises: 52b6c0f6c7c5
Create Date: 2026-04-29 13:04:30.349712

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func


# revision identifiers, used by Alembic.
revision: str = "f66ac93a3482"
down_revision: Union[str, Sequence[str], None] = "52b6c0f6c7c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now()),
    )
    op.add_column(
        "users",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "created_at")
    op.drop_column("users", "updated_at")
