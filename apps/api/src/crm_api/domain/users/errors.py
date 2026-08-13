"""Erros de domínio da gestão de usuários autorizados."""


class EmailAlreadyRegisteredError(Exception):
    """Já existe uma conta cadastrada com esse e-mail."""


class UserNotFoundError(Exception):
    """Nenhum usuário corresponde ao identificador informado."""


class CannotDeactivateSelfError(Exception):
    """Um administrador não pode desativar a própria conta."""
