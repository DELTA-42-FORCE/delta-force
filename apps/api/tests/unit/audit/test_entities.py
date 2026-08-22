from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from crm_api.domain.audit.entities import (
    AuditAction,
    AuditActorKind,
    AuditEvent,
    AuditResourceType,
    AuditResult,
)


def test_audit_event_and_its_context_are_immutable() -> None:
    source_context = {"http_method": "GET"}
    event = AuditEvent(
        id=uuid4(),
        occurred_at=datetime.now(UTC),
        actor_kind=AuditActorKind.AUTHENTICATED,
        actor_user_id=uuid4(),
        action=AuditAction.OWNER_PROFILE_VIEW,
        resource_type=AuditResourceType.OWNER_ACCOUNT,
        resource_id=str(uuid4()),
        result=AuditResult.SUCCESS,
        context=source_context,
    )

    source_context["http_method"] = "DELETE"

    assert event.context == {"http_method": "GET"}
    with pytest.raises(TypeError):
        event.context["http_method"] = "POST"  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        event.action = AuditAction.LOGOUT  # type: ignore[misc]
