"""Validação e normalização compartilhadas da pasta flexível de clientes."""

from typing import Mapping


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
    return dict(value)
