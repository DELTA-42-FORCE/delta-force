"""Erros de domínio da autenticação."""


class InvalidCredentialsError(Exception):
    """E-mail desconhecido ou senha incorreta."""


class InactiveUserError(Exception):
    """Usuário existe mas foi desativado pelo administrador."""


class InvalidSessionError(Exception):
    """Sessão inexistente, expirada ou revogada."""


class SetupAlreadyCompletedError(Exception):
    """A conta única do proprietário já foi configurada."""
