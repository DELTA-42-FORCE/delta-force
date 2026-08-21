from uuid import UUID

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.auth.view_owner_profile import ViewOwnerProfileUseCase
from crm_api.domain.auth.entities import User
from fakes import FakeAuditEventRepository, FakeTransaction


async def test_returns_authenticated_owner_and_audits_profile_view() -> None:
    user = User(
        id=UUID("00000000-0000-0000-0000-000000000017"),
        email="owner@deltaforce.internal",
        full_name="Synthetic Owner",
        password_hash="not-returned",
        is_active=True,
    )
    events = FakeAuditEventRepository()
    transaction = FakeTransaction()
    use_case = ViewOwnerProfileUseCase(
        audit=RecordAuditEventUseCase(events=events),
        transaction=transaction,
    )

    result = await use_case.execute(user=user)

    assert result is user
    assert [event.action for event in events.events] == ["auth.owner_profile_view"]
    assert events.events[0].actor_user_id == user.id
    assert user.email not in repr(events.events[0])
    assert user.password_hash not in repr(events.events[0])
    assert transaction.commit_calls == 1
    assert transaction.rollback_calls == 0
