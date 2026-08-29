"""Normalização de timestamps entre dialetos de persistência."""

from datetime import UTC, datetime


def as_utc(value: datetime) -> datetime:
    """Normaliza também timestamps ingênuos devolvidos pelo SQLite (ADR 0003)."""
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
