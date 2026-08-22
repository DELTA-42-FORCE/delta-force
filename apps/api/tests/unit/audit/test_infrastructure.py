from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects import sqlite
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.schema import CreateTable
from sqlalchemy.sql import Select

from crm_api.domain.audit.entities import (
    AuditAction,
    AuditActorKind,
    AuditEvent,
    AuditEventCursor,
    AuditResourceType,
    AuditResult,
)
from crm_api.infrastructure.audit.models import AuditEventModel
from crm_api.infrastructure.audit.repositories import (
    SqlAlchemyAuditEventRepository,
)
from crm_api.infrastructure.audit.transactions import SqlAlchemyTransaction
from crm_api.infrastructure.auth.models import UserModel


class FakeScalarResult:
    def __init__(self, models: list[AuditEventModel]) -> None:
        self.models = models

    def all(self) -> list[AuditEventModel]:
        return self.models


class RecordingSession:
    def __init__(self, models: list[AuditEventModel] | None = None) -> None:
        self.added: list[object] = []
        self.models = models or []
        self.statements: list[Select[tuple[AuditEventModel]]] = []
        self.flush_calls = 0
        self.commit_calls = 0
        self.rollback_calls = 0

    def add(self, model: object) -> None:
        self.added.append(model)

    async def flush(self) -> None:
        self.flush_calls += 1

    async def scalars(
        self, statement: Select[tuple[AuditEventModel]]
    ) -> FakeScalarResult:
        self.statements.append(statement)
        return FakeScalarResult(self.models)

    async def commit(self) -> None:
        self.commit_calls += 1

    async def rollback(self) -> None:
        self.rollback_calls += 1


def _event() -> AuditEvent:
    return AuditEvent(
        id=uuid4(),
        occurred_at=datetime.now(UTC),
        actor_kind=AuditActorKind.ANONYMOUS,
        actor_user_id=None,
        action=AuditAction.LOGIN,
        resource_type=AuditResourceType.OWNER_ACCOUNT,
        resource_id=None,
        result=AuditResult.DENIED,
        context={"reason_code": "invalid_credentials"},
    )


def test_audit_table_contract_compiles_for_postgresql_and_sqlite() -> None:
    assert UserModel.__tablename__ == "users"

    for dialect in (postgresql.dialect(), sqlite.dialect()):
        ddl = str(CreateTable(AuditEventModel.__table__).compile(dialect=dialect))
        normalized = " ".join(ddl.split())

        assert (
            "FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE RESTRICT"
            in normalized
        )
        assert "ck_audit_events_actor_identity" in normalized
        assert "ck_audit_events_action" in normalized
        assert "ck_audit_events_resource_type" in normalized


async def test_repository_appends_with_flush_but_does_not_commit() -> None:
    session = RecordingSession()
    repository = SqlAlchemyAuditEventRepository(session=cast(AsyncSession, session))
    event = _event()

    await repository.append(event)

    assert session.flush_calls == 1
    assert session.commit_calls == 0
    [model] = session.added
    assert isinstance(model, AuditEventModel)
    assert model.id == event.id
    assert model.resource_id is None
    assert model.context == {"reason_code": "invalid_credentials"}


async def test_repository_lists_newest_events_with_stable_pagination() -> None:
    expected = _event()
    model = AuditEventModel(
        id=expected.id,
        # SQLite devolve DateTime sem tzinfo mesmo com timezone=True. O
        # adaptador deve restaurar UTC antes de construir cursor/resposta.
        occurred_at=expected.occurred_at.replace(tzinfo=None),
        actor_kind=expected.actor_kind.value,
        actor_user_id=expected.actor_user_id,
        action=expected.action.value,
        resource_type=expected.resource_type.value,
        resource_id=expected.resource_id,
        result=expected.result.value,
        context=dict(expected.context),
    )
    session = RecordingSession(models=[model])
    repository = SqlAlchemyAuditEventRepository(session=cast(AsyncSession, session))

    cursor = AuditEventCursor(
        occurred_at=expected.occurred_at,
        id=expected.id,
    )
    events = await repository.list_recent(
        limit=5,
        before=cursor,
        action=AuditAction.LOGIN,
        result=AuditResult.DENIED,
    )

    assert events == [expected]
    [statement] = session.statements
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "audit_events.occurred_at <" in sql
    assert "audit_events.action = 'auth.login'" in sql
    assert "audit_events.result = 'denied'" in sql
    assert "OR audit_events.occurred_at =" in sql
    assert "audit_events.id <" in sql
    assert "ORDER BY audit_events.occurred_at DESC, audit_events.id DESC" in sql
    assert "LIMIT 5" in sql


async def test_transaction_delegates_commit_and_rollback() -> None:
    session = RecordingSession()
    transaction = SqlAlchemyTransaction(session=cast(AsyncSession, session))

    await transaction.commit()
    await transaction.rollback()

    assert session.commit_calls == 1
    assert session.rollback_calls == 1
