"""Store only hashes of session tokens.

Revision ID: 20260819_0003
Revises: 20260812_0002
Create Date: 2026-08-19 00:00:00
"""

import hashlib
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260819_0003"
down_revision: str | Sequence[str] | None = "20260812_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_PRIMARY_KEY_NAME = "sessions_pkey"
HASH_PRIMARY_KEY_NAME = "pk_sessions"


def upgrade() -> None:
    """Converte tokens existentes em hashes antes de remover o texto puro."""
    op.add_column("sessions", sa.Column("token_hash", sa.String(), nullable=True))
    connection = op.get_bind()
    sessions = sa.table(
        "sessions",
        sa.column("token", sa.String()),
        sa.column("token_hash", sa.String()),
    )
    for token in connection.execute(sa.select(sessions.c.token)).scalars():
        connection.execute(
            sessions.update()
            .where(sessions.c.token == token)
            .values(token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest())
        )

    # batch_alter_table recria a tabela (copy-and-move) em vez de emitir ALTER
    # TABLE ... DROP CONSTRAINT/ADD CONSTRAINT, que o SQLite não suporta. O
    # mesmo caminho roda nos dois dialetos para não haver dois comportamentos
    # de migration a manter (ADR 0003 / #54).
    with op.batch_alter_table("sessions", recreate="always") as batch_op:
        batch_op.alter_column("token_hash", nullable=False)
        batch_op.drop_constraint(LEGACY_PRIMARY_KEY_NAME, type_="primary")
        batch_op.drop_column("token")
        batch_op.create_primary_key(HASH_PRIMARY_KEY_NAME, ["token_hash"])


def downgrade() -> None:
    """Restaura identificadores funcionais, sem recuperar segredos apagados."""
    op.add_column("sessions", sa.Column("token", sa.String(), nullable=True))
    connection = op.get_bind()
    sessions = sa.table(
        "sessions",
        sa.column("token", sa.String()),
        sa.column("token_hash", sa.String()),
    )
    connection.execute(sessions.update().values(token=sessions.c.token_hash))
    with op.batch_alter_table("sessions", recreate="always") as batch_op:
        batch_op.alter_column("token", nullable=False)
        batch_op.drop_constraint(HASH_PRIMARY_KEY_NAME, type_="primary")
        batch_op.drop_column("token_hash")
        batch_op.create_primary_key(LEGACY_PRIMARY_KEY_NAME, ["token"])
