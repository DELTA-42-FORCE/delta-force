import pytest

from crm_api.infrastructure.auth import passwords


def test_dummy_hash_is_precomputed_and_reused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_hash_is_generated(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("dummy bcrypt hash must not be generated per request")

    monkeypatch.setattr(passwords.bcrypt, "hashpw", fail_if_hash_is_generated)

    first = passwords.BcryptPasswordHasher().dummy_hash
    second = passwords.BcryptPasswordHasher().dummy_hash

    assert first == second


def test_dummy_hash_is_valid_but_does_not_match_an_arbitrary_password() -> None:
    hasher = passwords.BcryptPasswordHasher()

    assert not hasher.verify(
        password="not-the-dummy-password", password_hash=hasher.dummy_hash
    )
