from datetime import UTC, datetime, timedelta
from uuid import uuid4

from crm_api.application.auth.logout import LogoutUseCase
from crm_api.domain.auth.entities import Session
from fakes import FakeSessionRepository


async def test_logout_revokes_the_session_so_it_can_no_longer_be_used() -> None:
    session = Session(
        token="token-to-revoke",
        user_id=uuid4(),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        revoked_at=None,
    )
    sessions = FakeSessionRepository({session.token: session})
    use_case = LogoutUseCase(sessions=sessions)

    await use_case.execute(session_token="token-to-revoke")

    assert sessions.sessions["token-to-revoke"].revoked_at is not None


async def test_logout_of_unknown_token_is_a_no_op() -> None:
    sessions = FakeSessionRepository()
    use_case = LogoutUseCase(sessions=sessions)

    await use_case.execute(session_token="never-issued")

    assert sessions.sessions == {}
