"""Hash unidirecional de tokens de sessão."""

import hashlib


class Sha256SessionTokenHasher:
    """Produz um identificador fixo sem persistir o segredo reutilizável."""

    def hash(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
