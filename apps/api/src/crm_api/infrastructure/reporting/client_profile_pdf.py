"""Gerador de PDF da ficha cadastral, em Python puro e sem dependências.

O aplicativo é local e a ficha é simples (nome de identificação e os campos
preenchidos), então o PDF é montado à mão com as fontes padrão do PDF
(Helvetica), sem embutir fontes nem depender de bibliotecas externas. O texto
usa WinAnsiEncoding (equivalente a cp1252), que cobre os acentos do português.
"""

from dataclasses import dataclass

from crm_api.domain.clients.reporting import ClientProfileDocument

# Página A4 em pontos e margem confortável para leitura e impressão.
_PAGE_WIDTH = 595
_PAGE_HEIGHT = 842
_MARGIN = 56
_CONTENT_WIDTH = _PAGE_WIDTH - 2 * _MARGIN
_TOP = _PAGE_HEIGHT - _MARGIN
_BOTTOM = _MARGIN

_HEADING_SIZE = 20
_NAME_SIZE = 14
_LABEL_SIZE = 11
_VALUE_SIZE = 11
_LINE_FACTOR = 1.35
# Largura média conservadora de um caractere Helvetica, para quebrar linhas
# sem medir cada glifo; sobra folga para não estourar a margem.
_CHAR_WIDTH_FACTOR = 0.55

_FONT_REGULAR = "F1"
_FONT_BOLD = "F2"

_EMPTY_NOTE = "Nenhum campo adicional preenchido nesta pasta."


@dataclass(frozen=True, slots=True)
class _Line:
    font: str
    size: float
    text: str


@dataclass(frozen=True, slots=True)
class _Gap:
    height: float


def _wrap(text: str, size: float) -> list[str]:
    """Quebra o texto em linhas que cabem na largura útil da página."""
    max_chars = max(1, int(_CONTENT_WIDTH / (_CHAR_WIDTH_FACTOR * size)))
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            lines.append(current)
        # Uma palavra maior que a linha (URL, número longo) é partida à força.
        while len(word) > max_chars:
            lines.append(word[:max_chars])
            word = word[max_chars:]
        current = word
    if current:
        lines.append(current)
    return lines


def _escape(text: str) -> bytes:
    """Codifica o texto em WinAnsi e escapa os caracteres especiais do PDF."""
    raw = text.encode("cp1252", "replace")
    out = bytearray()
    for byte in raw:
        if byte in (0x28, 0x29, 0x5C):  # ( ) \
            out.append(0x5C)
        out.append(byte)
    return bytes(out)


@dataclass(frozen=True, slots=True)
class MinimalClientProfilePdfRenderer:
    """Renderiza a ficha em um PDF válido de uma ou mais páginas."""

    def render(self, document: ClientProfileDocument) -> bytes:
        rows = self._compose_rows(document)
        pages = self._paginate(rows)
        return self._assemble(pages)

    def _compose_rows(self, document: ClientProfileDocument) -> list[_Line | _Gap]:
        rows: list[_Line | _Gap] = [
            _Line(_FONT_BOLD, _HEADING_SIZE, document.heading),
            _Gap(6),
            _Line(_FONT_BOLD, _NAME_SIZE, document.display_name),
            _Gap(14),
        ]
        if not document.fields:
            rows.append(_Line(_FONT_REGULAR, _VALUE_SIZE, _EMPTY_NOTE))
            return rows
        for field in document.fields:
            for line in _wrap(field.label, _LABEL_SIZE):
                rows.append(_Line(_FONT_BOLD, _LABEL_SIZE, line))
            for line in _wrap(field.value, _VALUE_SIZE):
                rows.append(_Line(_FONT_REGULAR, _VALUE_SIZE, line))
            rows.append(_Gap(8))
        return rows

    def _paginate(self, rows: list[_Line | _Gap]) -> list[list[tuple[float, _Line]]]:
        """Distribui as linhas em páginas, com a coordenada de base de cada uma."""
        pages: list[list[tuple[float, _Line]]] = []
        current: list[tuple[float, _Line]] = []
        y = _TOP
        for row in rows:
            if isinstance(row, _Gap):
                y -= row.height
                continue
            line_height = row.size * _LINE_FACTOR
            if y - line_height < _BOTTOM and current:
                pages.append(current)
                current = []
                y = _TOP
            y -= line_height
            current.append((y, row))
        pages.append(current)
        return pages

    def _content_stream(self, page: list[tuple[float, _Line]]) -> bytes:
        parts = bytearray()
        for baseline, line in page:
            if line.text == "":
                continue
            parts += b"BT /"
            parts += line.font.encode("ascii")
            parts += f" {line.size:g} Tf {_MARGIN} {baseline:g} Td (".encode("ascii")
            parts += _escape(line.text)
            parts += b") Tj ET\n"
        return bytes(parts)

    def _assemble(self, pages: list[list[tuple[float, _Line]]]) -> bytes:
        buffer = bytearray()
        buffer += b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
        offsets: dict[int, int] = {}

        def add_object(number: int, body: bytes) -> None:
            offsets[number] = len(buffer)
            buffer.extend(f"{number} 0 obj\n".encode("ascii"))
            buffer.extend(body)
            buffer.extend(b"\nendobj\n")

        page_object_numbers = [5 + 2 * index for index in range(len(pages))]
        kids = " ".join(f"{number} 0 R" for number in page_object_numbers)

        add_object(1, b"<< /Type /Catalog /Pages 2 0 R >>")
        add_object(
            2,
            f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode("ascii"),
        )
        add_object(
            3,
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
            b"/Encoding /WinAnsiEncoding >>",
        )
        add_object(
            4,
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold "
            b"/Encoding /WinAnsiEncoding >>",
        )

        for index, page in enumerate(pages):
            page_number = page_object_numbers[index]
            content_number = page_number + 1
            page_body = (
                f"<< /Type /Page /Parent 2 0 R "
                f"/MediaBox [0 0 {_PAGE_WIDTH} {_PAGE_HEIGHT}] "
                f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
                f"/Contents {content_number} 0 R >>"
            ).encode("ascii")
            add_object(page_number, page_body)

            stream = self._content_stream(page)
            content_body = bytearray()
            content_body += f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            content_body += stream
            content_body += b"endstream"
            add_object(content_number, bytes(content_body))

        return self._finalize(buffer, offsets)

    @staticmethod
    def _finalize(buffer: bytearray, offsets: dict[int, int]) -> bytes:
        size = max(offsets) + 1
        xref_offset = len(buffer)
        buffer += f"xref\n0 {size}\n".encode("ascii")
        buffer += b"0000000000 65535 f \n"
        for number in range(1, size):
            buffer += f"{offsets[number]:010d} 00000 n \n".encode("ascii")
        buffer += b"trailer\n"
        buffer += f"<< /Size {size} /Root 1 0 R >>\n".encode("ascii")
        buffer += b"startxref\n"
        buffer += f"{xref_offset}\n".encode("ascii")
        buffer += b"%%EOF\n"
        return bytes(buffer)
