"""O gerador de ficha em PDF produz um arquivo válido a partir dos campos (#34)."""

import re

from crm_api.domain.clients.reporting import (
    ClientProfileDocument,
    ClientProfileField,
)
from crm_api.infrastructure.reporting.client_profile_pdf import (
    MinimalClientProfilePdfRenderer,
)

RENDERER = MinimalClientProfilePdfRenderer()


def _document(
    *, display_name: str = "Ana Souza", fields: tuple[ClientProfileField, ...] = ()
) -> ClientProfileDocument:
    return ClientProfileDocument(
        heading="Ficha cadastral", display_name=display_name, fields=fields
    )


def _page_count(pdf: bytes) -> int:
    return pdf.count(b"/Type /Page /Parent")


def test_renders_a_structurally_valid_single_page_pdf() -> None:
    pdf = RENDERER.render(
        _document(
            fields=(
                ClientProfileField(label="Telefone", value="11 99999-0000"),
                ClientProfileField(label="Cidade", value="Sao Paulo"),
            )
        )
    )

    assert pdf.startswith(b"%PDF-")
    assert pdf.rstrip().endswith(b"%%EOF")
    assert b"/Type /Catalog" in pdf
    assert b"/Root 1 0 R" in pdf
    assert b"startxref" in pdf and b"\nxref\n" in pdf
    assert _page_count(pdf) == 1
    assert b"/Count 1" in pdf
    # O rótulo e o valor aparecem no fluxo de conteúdo.
    assert b"(Telefone) Tj" in pdf
    assert b"(11 99999-0000) Tj" in pdf


def test_encodes_accents_with_winansi_and_escapes_pdf_specials() -> None:
    pdf = RENDERER.render(
        _document(
            display_name="José Conceição",
            fields=(ClientProfileField(label="Observação", value="cliente (VIP)"),),
        )
    )

    # Acentos do português saem em cp1252 (WinAnsi), não em UTF-8.
    assert "José Conceição".encode("cp1252") in pdf
    assert "Observação".encode("cp1252") in pdf
    # Parênteses do valor são escapados para não fechar a string do PDF.
    assert rb"(cliente \(VIP\)) Tj" in pdf


def test_generates_a_valid_pdf_when_there_are_no_optional_fields() -> None:
    pdf = RENDERER.render(_document(fields=()))

    assert pdf.startswith(b"%PDF-")
    assert _page_count(pdf) == 1
    assert b"Nenhum campo adicional preenchido nesta pasta." in pdf


def test_paginates_when_the_fields_do_not_fit_in_one_page() -> None:
    fields = tuple(
        ClientProfileField(label=f"Campo {index}", value=f"Valor {index}")
        for index in range(80)
    )

    pdf = RENDERER.render(_document(fields=fields))

    pages = _page_count(pdf)
    assert pages > 1
    assert f"/Count {pages}".encode("ascii") in pdf


def test_breaks_a_value_longer_than_the_line_into_several_lines() -> None:
    long_value = "A" * 400
    pdf = RENDERER.render(
        _document(fields=(ClientProfileField(label="Bloco", value=long_value),))
    )

    drawn = re.findall(rb"\(A+\) Tj", pdf)
    assert len(drawn) > 1
    # Nenhuma linha isolada carrega o valor inteiro sem quebra.
    assert all(len(match) - len(b"() Tj") < 400 for match in drawn)


def test_from_folder_keeps_only_filled_fields_in_order() -> None:
    from datetime import UTC, datetime
    from uuid import uuid4

    from crm_api.domain.clients.entities import ClientFolder

    folder = ClientFolder(
        id=uuid4(),
        display_name="  Ana Souza  ",
        profile_data={
            "telefone": " 11 99999-0000 ",
            "vazio": "   ",
            "cidade": "Sao Paulo",
        },
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    document = ClientProfileDocument.from_folder(folder)

    assert document.display_name == "Ana Souza"
    assert document.fields == (
        ClientProfileField(label="telefone", value="11 99999-0000"),
        ClientProfileField(label="cidade", value="Sao Paulo"),
    )
