"""Validação e normalização compartilhadas da pasta flexível de clientes."""

from typing import Mapping

MAX_PROFILE_FIELDS = 100
MAX_PROFILE_KEY_LENGTH = 100
MAX_PROFILE_VALUE_LENGTH = 4_000
MAX_PROFILE_TOTAL_LENGTH = 64 * 1024


def normalize_display_name(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("client folder display_name must be a string")
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError("client folder display_name must not be blank")
    return normalized


def normalize_profile_data(value: Mapping[str, str] | None) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, Mapping) or any(
        not isinstance(key, str) or not isinstance(item, str)
        for key, item in value.items()
    ):
        raise ValueError("client folder profile_data must map strings to strings")
    if len(value) > MAX_PROFILE_FIELDS:
        raise ValueError(
            f"client folder profile_data must not exceed {MAX_PROFILE_FIELDS} fields"
        )

    normalized: dict[str, str] = {}
    total_length = 0
    for key, item in value.items():
        normalized_key = " ".join(key.split())
        normalized_value = item.strip()
        if not normalized_key:
            raise ValueError("client folder profile_data keys must not be blank")
        if len(normalized_key) > MAX_PROFILE_KEY_LENGTH:
            raise ValueError(
                "client folder profile_data keys must not exceed "
                f"{MAX_PROFILE_KEY_LENGTH} characters"
            )
        if len(normalized_value) > MAX_PROFILE_VALUE_LENGTH:
            raise ValueError(
                "client folder profile_data values must not exceed "
                f"{MAX_PROFILE_VALUE_LENGTH} characters"
            )
        if normalized_key in normalized:
            raise ValueError(
                "client folder profile_data contains duplicate normalized keys"
            )
        total_length += len(normalized_key) + len(normalized_value)
        if total_length > MAX_PROFILE_TOTAL_LENGTH:
            raise ValueError(
                "client folder profile_data must not exceed "
                f"{MAX_PROFILE_TOTAL_LENGTH} characters in total"
            )
        normalized[normalized_key] = normalized_value
    return normalized
