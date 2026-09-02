"""Erros de domínio da importação do acervo legado (#45)."""


class LegacyImportSourceError(Exception):
    """A pasta de origem informada não existe, não é diretório ou é grande demais."""
