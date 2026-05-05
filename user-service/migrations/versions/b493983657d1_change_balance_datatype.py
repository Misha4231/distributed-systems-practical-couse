"""change balance datatype

Revision ID: b493983657d1
Revises: f66ac93a3482
Create Date: 2026-05-03 10:24:49.540959

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b493983657d1"
down_revision: Union[str, Sequence[str], None] = "f66ac93a3482"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "users",
        "balance",
        type_=sa.DECIMAL(8, 2),
        existing_type=sa.Integer,
        server_default=sa.text("0"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "users",
        "balance",
        type_=sa.Integer,
        existing_type=sa.DECIMAL(8, 2),
        server_default=sa.text("0"),
    )
