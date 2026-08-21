from datetime import timedelta
from uuid import uuid4

from crm_api.application.auth.session_issuer import SessionIssuer
from crm_api.domain.auth.entities import User
from fakes import FakeSessionRepository, FakeSessionTokenHasher


async def test_session_issuer_persists_only_the_token_hash() -> None:
    user = User(
        id=uuid4(),
        email="owner@deltaforce.internal",
        full_name="Proprietário",
        password_hash="irrelevant",
        is_active=True,
    )
    sessions = FakeSessionRepository()
    issuer = SessionIssuer(
        sessions=sessions,
        token_hasher=FakeSessionTokenHasher(),
        session_ttl=timedelta(hours=1),
    )

    result = await issuer.issue(user=user)

    assert result.user == user
    assert result.session.token_hash == f"hashed:{result.session_token}"
    assert result.session_token not in sessions.sessions
