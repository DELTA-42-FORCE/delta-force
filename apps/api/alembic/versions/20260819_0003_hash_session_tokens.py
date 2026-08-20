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

    op.alter_column("sessions", "token_hash", nullable=False)
    op.drop_constraint(LEGACY_PRIMARY_KEY_NAME, "sessions", type_="primary")
    op.drop_column("sessions", "token")
    op.create_primary_key(HASH_PRIMARY_KEY_NAME, "sessions", ["token_hash"])


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
    op.alter_column("sessions", "token", nullable=False)
    op.drop_constraint(HASH_PRIMARY_KEY_NAME, "sessions", type_="primary")
    op.drop_column("sessions", "token_hash")
    op.create_primary_key(LEGACY_PRIMARY_KEY_NAME, "sessions", ["token"])
