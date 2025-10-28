"""add tipo column to notificaciones

Revision ID: b2c3d4e5f607
Revises: a1b2c3d4e5f6
Create Date: 2025-09-16 00:10:00.000000

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f607"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "Notificaciones", sa.Column("tipo", sa.String(length=30), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("Notificaciones", "tipo")
