"""Writes placeholder PDFs for seeded evidence."""

from __future__ import annotations

from pathlib import Path
from textwrap import wrap

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.content.packet_ordering import (
    I131_SECTION_UPLOAD_CODES,
    I485_PACKET_EXCLUDED_UPLOAD_CODES,
    I485_PACKET_PAYMENT_UPLOAD_CODES,
    I485_SECTION_UPLOAD_CODES,
    I765_SECTION_UPLOAD_CODES,
    I864_SECTION_UPLOAD_CODES,
)

PAGE_WIDTH = 612
PAGE_HEIGHT = 792


def packet_section_for_checklist_code(code: str | None) -> str:
    if code in I485_PACKET_PAYMENT_UPLOAD_CODES:
        return "Payment"
    if code == "form_g1145":
        return "Form G-1145"
    matching_sections: list[str] = []
    if code in I485_SECTION_UPLOAD_CODES:
        matching_sections.append("I-485")
    if code in I864_SECTION_UPLOAD_CODES:
        matching_sections.append("I-864")
    if code == "medical_exam_i693":
        matching_sections.append("I-693 medical")
    if code in I765_SECTION_UPLOAD_CODES:
        matching_sections.append("I-765")
    if code in I131_SECTION_UPLOAD_CODES:
        matching_sections.append("I-131")
    if matching_sections:
        suffix = "section" if len(matching_sections) == 1 else "sections"
        return f"{' / '.join(matching_sections)} {suffix}"
    if code in I485_PACKET_EXCLUDED_UPLOAD_CODES:
        return "Additional uploaded documents"
    return "Additional uploaded documents"


def _escape_pdf_text(text: str) -> str:
    ascii_text = text.encode("ascii", "replace").decode("ascii")
    return ascii_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _estimated_text_width(text: str, font_size: int) -> float:
    return len(text) * font_size * 0.52


def _centered_text_command(text: str, *, y_position: float, font_name: str, font_size: int) -> str:
    estimated_width = _estimated_text_width(text, font_size)
    x_position = max(36, (PAGE_WIDTH - estimated_width) / 2)
    return "\n".join(
        [
            f"{font_name} {font_size} Tf",
            f"1 0 0 1 {x_position:.2f} {y_position:.2f} Tm",
            f"({_escape_pdf_text(text)}) Tj",
        ]
    )


def write_seed_placeholder_pdf(
    path: Path,
    *,
    section: str,
    category: str,
    label: str,
    code: str | None = None,
) -> None:
    lines: list[tuple[str, str, int]] = [
        (f"[SECTION: {section}]", "/F2", 13),
        (f"[CATEGORY: {category}]", "/F2", 13),
        ("PLACEHOLDER", "/F2", 22),
    ]
    lines.extend((chunk, "/F1", 11) for chunk in wrap(label, width=58))
    if code:
        lines.append((f"Checklist code: {code}", "/F1", 10))
    lines.append(("Local seeded sample PDF. Do not file this document.", "/F1", 9))

    writer = PdfWriter()
    page = writer.add_blank_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    regular_font_ref = writer._add_object(
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
    )
    bold_font_ref = writer._add_object(
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica-Bold"),
            }
        )
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {
                    NameObject("/F1"): regular_font_ref,
                    NameObject("/F2"): bold_font_ref,
                }
            ),
        }
    )

    line_height = 18
    y_position = (PAGE_HEIGHT / 2) + ((len(lines) - 1) * line_height / 2)
    commands = ["BT"]
    for text, font_name, font_size in lines:
        commands.append(
            _centered_text_command(
                text,
                y_position=y_position,
                font_name=font_name,
                font_size=font_size,
            )
        )
        y_position -= line_height
    commands.append("ET")

    stream = DecodedStreamObject()
    stream.set_data("\n".join(commands).encode("ascii"))
    page[NameObject("/Contents")] = writer._add_object(stream)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        writer.write(handle)
