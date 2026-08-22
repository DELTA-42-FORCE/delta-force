import pytest
from pydantic import ValidationError

from crm_api.presentation.auth.schemas import LoginRequest, SetupOwnerRequest


@pytest.mark.parametrize(
    ("request_type", "payload"),
    [
        (
            SetupOwnerRequest,
            {
                "email": "proprietario@deltaforce.internal",
                "full_name": "Proprietário Delta Force",
                "password": "á" * 36,
            },
        ),
        (
            LoginRequest,
            {
                "email": "proprietario@deltaforce.internal",
                "password": "á" * 36,
            },
        ),
    ],
)
def test_request_schema_accepts_multibyte_password_at_72_byte_limit(
    request_type: type[SetupOwnerRequest] | type[LoginRequest],
    payload: dict[str, str],
) -> None:
    request = request_type.model_validate(payload)

    assert request.password == "á" * 36


@pytest.mark.parametrize(
    ("request_type", "payload"),
    [
        (
            SetupOwnerRequest,
            {
                "email": "proprietario@deltaforce.internal",
                "full_name": "Proprietário Delta Force",
                "password": "á" * 37,
            },
        ),
        (
            LoginRequest,
            {
                "email": "proprietario@deltaforce.internal",
                "password": "á" * 37,
            },
        ),
    ],
)
def test_request_schema_rejects_password_over_72_utf8_bytes(
    request_type: type[SetupOwnerRequest] | type[LoginRequest],
    payload: dict[str, str],
) -> None:
    with pytest.raises(ValidationError, match="72 UTF-8 bytes"):
        request_type.model_validate(payload)
