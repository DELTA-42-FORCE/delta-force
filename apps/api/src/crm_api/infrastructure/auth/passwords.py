"""Adaptador de hashing de senha usando bcrypt."""

from functools import cached_property

import bcrypt

# Não é uma credencial real: só existe para gerar um hash bcrypt válido a
# comparar quando o e-mail informado não tem conta, mitigando timing oracle.
_DUMMY_PASSWORD = "delta-force-dummy-password-for-timing-safety"  # nosec B105


class BcryptPasswordHasher:
    """Implementa a porta ``PasswordHasher`` do domínio com bcrypt."""

    def hash(self, password: str) -> str:
        """Usado por seeds/testes para criar contas; não há auto-cadastro na API."""
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def verify(self, *, password: str, password_hash: str) -> bool:
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"), password_hash.encode("utf-8")
            )
        except ValueError:
            return False

    @cached_property
    def dummy_hash(self) -> str:
        return self.hash(_DUMMY_PASSWORD)
