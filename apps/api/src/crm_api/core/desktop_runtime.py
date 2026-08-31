"""Estado efêmero que protege a API quando iniciada pelo shell Windows."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass, field

DESKTOP_CAPABILITY_HEADER = "X-Delta-Desktop-Capability"
DESKTOP_BOOTSTRAP_SECRET_HEADER = "X-Delta-Desktop-Secret"
DESKTOP_ORIGIN = "http://tauri.localhost"


def _digest(value: str) -> bytes:
    return hashlib.sha256(value.encode("ascii")).digest()


@dataclass(slots=True)
class DesktopRuntime:
    """Mantém segredo e capability somente na memória de uma execução."""

    bootstrap_secret: str
    port: int
    origin: str = DESKTOP_ORIGIN
    _bootstrap_secret_digest: bytes = field(init=False, repr=False)
    _capability_digest: bytes | None = field(default=None, init=False, repr=False)
    _bootstrap_consumed: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not self.bootstrap_secret.isascii() or not self.bootstrap_secret:
            raise ValueError("desktop bootstrap secret must be non-empty ASCII")
        if not 1 <= self.port <= 65535:
            raise ValueError("desktop port must be between 1 and 65535")
        self._bootstrap_secret_digest = _digest(self.bootstrap_secret)

    def accepts_source(self, *, host: str | None, origin: str | None) -> bool:
        return host == f"127.0.0.1:{self.port}" and origin == self.origin

    def issue_capability(
        self,
        *,
        supplied_secret: str | None,
        host: str | None,
        origin: str | None,
    ) -> str | None:
        """Troca o segredo de uso único por uma capability também efêmera."""
        if self._bootstrap_consumed or not self.accepts_source(
            host=host, origin=origin
        ):
            return None
        if supplied_secret is None or not supplied_secret.isascii():
            return None
        if not hmac.compare_digest(
            _digest(supplied_secret), self._bootstrap_secret_digest
        ):
            return None

        self._bootstrap_consumed = True
        capability = secrets.token_urlsafe(32)
        self._capability_digest = _digest(capability)
        return capability

    def accepts_capability(
        self,
        *,
        supplied_capability: str | None,
        host: str | None,
        origin: str | None,
    ) -> bool:
        if not self.accepts_source(host=host, origin=origin):
            return False
        if supplied_capability is None or not supplied_capability.isascii():
            return False
        return self._capability_digest is not None and hmac.compare_digest(
            _digest(supplied_capability), self._capability_digest
        )
