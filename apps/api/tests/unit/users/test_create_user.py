import pytest

from crm_api.application.users.create_user import CreateUserUseCase
from crm_api.domain.users.errors import EmailAlreadyRegisteredError
from user_fakes import FakePasswordHasher, FakeUserRepository


def _use_case() -> CreateUserUseCase:
    return CreateUserUseCase(
        users=FakeUserRepository(), password_hasher=FakePasswordHasher()
    )


async def test_creates_a_user_with_hashed_password() -> None:
    use_case = _use_case()

    user = await use_case.execute(
        email="nova@deltaforce.internal",
        full_name="Nova Conta",
        password="senha-do-admin",
        is_admin=False,
    )

    assert user.email == "nova@deltaforce.internal"
    assert user.password_hash == "senha-do-admin"  # fake hasher só ecoa o valor
    assert user.is_active is True
    assert user.is_admin is False


async def test_rejects_duplicate_email() -> None:
    use_case = _use_case()
    await use_case.execute(
        email="duplicado@deltaforce.internal",
        full_name="Primeira",
        password="senha-1",
        is_admin=False,
    )

    with pytest.raises(EmailAlreadyRegisteredError):
        await use_case.execute(
            email="duplicado@deltaforce.internal",
            full_name="Segunda",
            password="senha-2",
            is_admin=False,
        )
