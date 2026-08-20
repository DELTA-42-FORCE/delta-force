"""Adaptador de hashing de senha usando bcrypt."""

import bcrypt

# Não é uma credencial real nem pertence a uma conta. O hash bcrypt válido e
# pré-calculado evita gerar outro hash apenas quando o e-mail não existe.
_DUMMY_PASSWORD_HASH = "$2b$12$TigD74cOBvAhvRpCtMpLIuEhzhLwHxwLnbvcERKV" "jI7q.Xqf9zriq"


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

    @property
    def dummy_hash(self) -> str:
        return _DUMMY_PASSWORD_HASH
