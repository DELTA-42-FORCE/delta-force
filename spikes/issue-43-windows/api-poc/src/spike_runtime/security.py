"""Per-execution bootstrap and capability checks for the isolated spike."""

from __future__ import annotations

import base64
import hashlib
import hmac
import math
import re
import secrets
import threading
import time
from collections.abc import Callable

MINIMUM_SECRET_BYTES = 32
DEFAULT_BOOTSTRAP_TTL_SECONDS = 10.0
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class RuntimeAccessDenied(Exception):
    """A deliberately detail-free runtime authentication failure."""


class RuntimeConfigurationError(Exception):
    """A startup configuration failure safe to map to a generic error code."""


def validate_urlsafe_token(token: str) -> str:
    """Validate the wire encoding and decoded size, not its source of entropy."""

    if not token or not _TOKEN_PATTERN.fullmatch(token):
        raise RuntimeConfigurationError("invalid runtime token")

    try:
        encoded = token.encode("ascii")
        padding = b"=" * (-len(encoded) % 4)
        decoded = base64.b64decode(
            encoded + padding,
            altchars=b"-_",
            validate=True,
        )
    except (UnicodeEncodeError, ValueError) as exc:
        raise RuntimeConfigurationError("invalid runtime token") from exc

    if len(decoded) < MINIMUM_SECRET_BYTES:
        raise RuntimeConfigurationError("runtime token is too short")

    return token


class RuntimeGate:
    """Exchange one short-lived bootstrap secret for one runtime capability."""

    def __init__(
        self,
        bootstrap_secret: str,
        *,
        clock: Callable[[], float] = time.monotonic,
        ttl_seconds: float = DEFAULT_BOOTSTRAP_TTL_SECONDS,
        capability_factory: Callable[[], str] = lambda: secrets.token_urlsafe(32),
    ) -> None:
        if not math.isfinite(ttl_seconds) or ttl_seconds <= 0:
            raise RuntimeConfigurationError("bootstrap TTL must be positive")

        secret = validate_urlsafe_token(bootstrap_secret)
        self._bootstrap_digest: bytes | None = self._digest(secret)
        self._capability_digest: bytes | None = None
        self._clock = clock
        self._expires_at = clock() + ttl_seconds
        self._capability_factory = capability_factory
        self._lock = threading.Lock()

    @staticmethod
    def _digest(candidate: str) -> bytes:
        return hashlib.sha256(candidate.encode("ascii")).digest()

    def exchange(self, candidate: str | None) -> str:
        """Consume the bootstrap secret once and return a fresh capability."""

        with self._lock:
            if self._bootstrap_digest is None:
                raise RuntimeAccessDenied

            if self._clock() >= self._expires_at:
                self._bootstrap_digest = None
                raise RuntimeAccessDenied

            candidate_digest = self._candidate_digest(candidate)
            if candidate_digest is None or not hmac.compare_digest(
                candidate_digest,
                self._bootstrap_digest,
            ):
                raise RuntimeAccessDenied

            capability = validate_urlsafe_token(self._capability_factory())
            self._capability_digest = self._digest(capability)
            self._bootstrap_digest = None
            return capability

    def authorizes(self, candidate: str | None) -> bool:
        """Check a capability without retaining the presented plaintext token."""

        with self._lock:
            if self._capability_digest is None:
                return False

            candidate_digest = self._candidate_digest(candidate)
            return candidate_digest is not None and hmac.compare_digest(
                candidate_digest,
                self._capability_digest,
            )

    @classmethod
    def _candidate_digest(cls, candidate: str | None) -> bytes | None:
        if candidate is None:
            return None
        try:
            return cls._digest(candidate)
        except UnicodeEncodeError:
            return None
