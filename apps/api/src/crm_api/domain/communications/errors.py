"""Erros estáveis dos modelos de comunicação."""


class MessageTemplateNotFoundError(LookupError):
    """O modelo solicitado não existe."""
