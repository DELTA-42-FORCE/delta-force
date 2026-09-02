"""Normalização das anotações livres de um documento anexado (#22).

Nenhuma anotação é obrigatória e não existe catálogo documental rígido: texto
em branco vira ausência de anotação, não string vazia no banco.
"""

MAX_TITLE_LENGTH = 200
MAX_CATEGORY_LENGTH = 100
MAX_NOTES_LENGTH = 2000


def _normalize(
    value: str | None, *, field: str, max_length: int, collapse: bool
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"document {field} must be a string")

    normalized = " ".join(value.split()) if collapse else value.strip()
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise ValueError(f"document {field} must not exceed {max_length} characters")
    return normalized


def normalize_title(value: str | None) -> str | None:
    return _normalize(value, field="title", max_length=MAX_TITLE_LENGTH, collapse=True)


def normalize_category(value: str | None) -> str | None:
    """Categoria é texto livre: o proprietário não escolhe de uma lista fechada."""
    return _normalize(
        value, field="category", max_length=MAX_CATEGORY_LENGTH, collapse=True
    )


def normalize_notes(value: str | None) -> str | None:
    """A observação preserva quebras de linha; só as bordas são aparadas."""
    return _normalize(value, field="notes", max_length=MAX_NOTES_LENGTH, collapse=False)
