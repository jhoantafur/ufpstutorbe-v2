"""Fix ProfesorAsignatura primary key sequence and constraints

Revision ID: fix_prof_asig_pk_20250916
Revises: 6fcb3915639e
Create Date: 2025-09-16

Ensures:
 - Autoincrement sequence exists
 - id column default set to nextval
 - Unique constraint (id_profesor,id_asignatura) present
 - Sequence aligned with MAX(id)

All steps are guarded to avoid transactional aborts.
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "fix_prof_asig_pk_20250916"
down_revision: Union[str, None] = "6fcb3915639e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Sequence existence
    seq_exists = (
        conn.execute(
            sa.text(
                """
        SELECT 1 FROM information_schema.sequences
        WHERE sequence_schema = current_schema()
          AND sequence_name = 'profesor_asignatura_id_seq'
    """
            )
        ).scalar()
        is not None
    )
    if not seq_exists:
        conn.execute(sa.text("CREATE SEQUENCE profesor_asignatura_id_seq"))

    # 2. Ensure default on id column
    col_default = conn.execute(
        sa.text(
            """
        SELECT column_default FROM information_schema.columns
        WHERE table_name = 'ProfesorAsignatura' AND column_name = 'id'
    """
        )
    ).scalar()
    needs_default = not col_default or "profesor_asignatura_id_seq" not in (
        col_default or ""
    )
    if needs_default:
        conn.execute(
            sa.text(
                "ALTER TABLE \"ProfesorAsignatura\" ALTER COLUMN id SET DEFAULT nextval('profesor_asignatura_id_seq')"
            )
        )

    # 3. Unique constraint existence
    uc_exists = (
        conn.execute(
            sa.text(
                """
        SELECT 1 FROM pg_constraint
        WHERE conname = '_profesor_asignatura_uc'
    """
            )
        ).scalar()
        is not None
    )
    if not uc_exists:
        conn.execute(
            sa.text(
                'ALTER TABLE "ProfesorAsignatura" ADD CONSTRAINT _profesor_asignatura_uc UNIQUE (id_profesor, id_asignatura)'
            )
        )

    # 4. Align sequence (setval) — use is_called=false so next nextval returns exact value
    conn.execute(
        sa.text(
            """
        SELECT setval('profesor_asignatura_id_seq',
                      COALESCE((SELECT MAX(id) FROM "ProfesorAsignatura"),0) + 1,
                      false)
    """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    # Best-effort reversal (may fail safely if objects in use)
    conn.execute(
        sa.text('ALTER TABLE "ProfesorAsignatura" ALTER COLUMN id DROP DEFAULT')
    )
    conn.execute(sa.text("DROP SEQUENCE IF EXISTS profesor_asignatura_id_seq"))
