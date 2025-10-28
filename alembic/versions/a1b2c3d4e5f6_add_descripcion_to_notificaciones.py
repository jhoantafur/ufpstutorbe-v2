"""add descripcion to notificaciones

Revision ID: a1b2c3d4e5f6
Revises: 6fcb3915639e
Create Date: 2025-09-16 00:00:00.000000

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
# Chain after the profesor_asignatura pk fix to avoid multiple heads
down_revision: Union[str, None] = "fix_prof_asig_pk_20250916"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "Notificaciones", sa.Column("descripcion", sa.String(length=500), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("Notificaciones", "descripcion")
