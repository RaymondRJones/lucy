"""Generates packet cover letters and section index pages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from textwrap import wrap
from typing import Any
from uuid import UUID

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

SECTION_TITLES = {
    "Payment": "Payment",
    "Form G-1145": "Form G-1145 (Optional)",
    "I-485 section": "Form I-485 (Application to Adjust Status)",
    "I-864 section": "Form I-864 (Affidavit of Support)",
    "I-693 medical section": "Form I-693 (Medical Examination)",
    "I-765 section": "Form I-765 (Application for Work Authorization)",
    "I-131 section": "Form I-131 (Application for Advance Parole)",
    "I-130 section": "Forms I-130 and I-130A (Petition for Alien Relative)",
}

SIGNATURE_LINE = "X________________________________"
PENDING_I130_STATUSES = {"pending", "filed"}


@dataclass(frozen=True)
class GeneratedCoverLetter:
    output_path: Path
    warnings: list[str]


def _clean_text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text if text else fallback


def _person_name(values: dict[str, Any], role: str) -> str:
    parts = [
        _clean_text(values.get(f"{role}_first_name")),
        _clean_text(values.get(f"{role}_middle_name")),
        _clean_text(values.get(f"{role}_last_name")),
    ]
    name = " ".join(part for part in parts if part)
    return name or f"[insert {role} name]"


def _formatted_date(value: date) -> str:
    return f"{value:%B} {value.day}, {value:%Y}"


def _city_state_zip(*, city: str, state: str, zip_code: str) -> str:
    city_state = ", ".join(part for part in [city, state] if part)
    if city_state and zip_code:
        return f"{city_state} {zip_code}"
    return city_state or zip_code


def _address_dict_lines(raw: Any) -> list[str]:
    if not isinstance(raw, dict):
        return []
    line1 = _clean_text(raw.get("line1") or raw.get("street_1") or raw.get("street"))
    line2 = _clean_text(raw.get("line2") or raw.get("street_2"))
    city_line = _city_state_zip(
        city=_clean_text(raw.get("city")),
        state=_clean_text(raw.get("state")),
        zip_code=_clean_text(raw.get("zip") or raw.get("postal_code")),
    )
    return [line for line in [line1, line2, city_line] if line]


def _structured_address_lines(values: dict[str, Any], role: str, address_kind: str) -> list[str]:
    prefix = f"{role}_{address_kind}"
    address_key = f"{prefix}_address"
    lines = _address_dict_lines(values.get(address_key))
    if lines:
        return lines

    line1 = _clean_text(values.get(f"{address_key}_line1"))
    line2 = _clean_text(values.get(f"{address_key}_line2"))
    city_line = _city_state_zip(
        city=_clean_text(values.get(f"{prefix}_city")),
        state=_clean_text(values.get(f"{prefix}_state")),
        zip_code=_clean_text(values.get(f"{prefix}_zip")),
    )
    if any([line1, line2, city_line]):
        return [line for line in [line1, line2, city_line] if line]

    raw_address = values.get(address_key)
    if isinstance(raw_address, str):
        return [_clean_text(raw_address)] if _clean_text(raw_address) else []
    return []


def _applicant_address_lines(values: dict[str, Any]) -> list[str]:
    for address_kind in ["mailing", "current"]:
        lines = _structured_address_lines(values, "beneficiary", address_kind)
        if lines:
            return lines
    return ["[Your Address]", "[City, State ZIP]"]


def _lockbox_address_lines(address_lines: list[str] | None) -> list[str]:
    if address_lines:
        return address_lines
    return ["[Lockbox Address - depends on your filing location]"]


def _escape_pdf_text(text: str) -> str:
    ascii_text = text.encode("ascii", "replace").decode("ascii")
    return ascii_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrapped(lines: list[str], width: int = 92) -> list[str]:
    output: list[str] = []
    for line in lines:
        if not line:
            output.append("")
            continue
        chunks = wrap(line, width=width, subsequent_indent="  ")
        output.extend(chunks or [""])
    return output


def _page_chunks(lines: list[str], lines_per_page: int = 47) -> list[list[str]]:
    return [lines[index : index + lines_per_page] for index in range(0, len(lines), lines_per_page)]


def _is_bold_line(line: str) -> bool:
    return (
        line.startswith("RE:")
        or line.startswith("Applicant (Beneficiary):")
        or line.startswith("Petitioner (U.S. Citizen Spouse):")
        or line.startswith("I-130 Receipt Number:")
        or line == "Contents of Submission"
        or line == "Section Index Page"
        or line == "Purpose"
        or line == "Documents queued for this section"
        or line == "Mailing note"
        or line in SECTION_TITLES.values()
        or bool(line[:1].isdigit() and ". " in line[:5])
    )


def _draw_rule_after(line: str) -> bool:
    return line.startswith("I-130 Receipt Number:") or line == (
        "I am concurrently submitting supporting forms and documentation as outlined below."
    )


def _text_x(line: str) -> int:
    if line.startswith("  * "):
        return 100
    if line.startswith("* ") or line.startswith("  "):
        return 86
    return 72


def _add_text_page(writer: PdfWriter, lines: list[str], font_refs: dict[str, Any]) -> None:
    page = writer.add_blank_page(width=612, height=792)
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {
                    NameObject("/F1"): font_refs["regular"],
                    NameObject("/F2"): font_refs["bold"],
                }
            ),
        }
    )
    commands = ["BT"]
    y_position = 742
    for line in lines:
        if line:
            font_name = "/F2" if _is_bold_line(line) else "/F1"
            commands.append(f"{font_name} 10 Tf")
            commands.append(f"1 0 0 1 {_text_x(line)} {y_position} Tm")
            commands.append(f"({_escape_pdf_text(line)}) Tj")
        y_position -= 14
        if _draw_rule_after(line):
            commands.extend(
                [
                    "ET",
                    "q",
                    "0.5 w",
                    f"72 {y_position + 4} m",
                    f"540 {y_position + 4} l",
                    "S",
                    "Q",
                    "BT",
                ]
            )
            y_position -= 8
    commands.append("ET")
    stream = DecodedStreamObject()
    stream.set_data("\n".join(commands).encode("ascii"))
    page[NameObject("/Contents")] = writer._add_object(stream)


def _section_lines(sections: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for index, section in enumerate(sections, start=1):
        label = SECTION_TITLES.get(section["label"], section["label"])
        lines.append(f"{index}. {label}")
        for item in section.get("items", []):
            if isinstance(item, dict):
                lines.append(f"* {item['label']}")
                for child in item.get("children", []):
                    lines.append(f"  * {child}")
                continue
            lines.append(f"* {item}")
        lines.append("")
    return lines


def build_cover_letter_lines(
    *,
    values: dict[str, Any],
    sections: list[dict[str, Any]],
    lockbox_address_lines: list[str] | None = None,
    generated_on: date | None = None,
) -> list[str]:
    """Returns the text of a packet's cover letter."""
    beneficiary_name = _person_name(values, "beneficiary")
    petitioner_name = _person_name(values, "petitioner")
    i130_status = str(values.get("i130_filing_status") or "").strip().lower()
    concurrent_i130 = i130_status in {"not_filed", "none"}
    approved_i130 = i130_status == "approved"
    pending_i130 = i130_status in PENDING_I130_STATUSES
    receipt_number = _clean_text(
        values.get("i130_receipt_number"),
        "[insert pending Form I-130 receipt number]" if pending_i130 else "[insert Form I-130 receipt number]",
    )
    i130_status_sentence = (
        "has been approved by USCIS."
        if approved_i130
        else "is currently pending with USCIS."
        if pending_i130
        else "[state the current status of the Form I-130 before filing]."
    )
    generated_date = generated_on or date.today()

    lines = [
        beneficiary_name,
        *_applicant_address_lines(values),
        "",
        _formatted_date(generated_date),
        "",
        "U.S. Citizenship and Immigration Services",
        *_lockbox_address_lines(lockbox_address_lines),
        "",
        (
            "RE: Concurrent Forms I-130 and I-485 (Marriage-Based)"
            if concurrent_i130
            else "RE: Form I-485 Adjustment of Status (Marriage-Based)"
        ),
        f"Applicant (Beneficiary): {beneficiary_name}",
        f"Petitioner (U.S. Citizen Spouse): {petitioner_name}",
        *([] if concurrent_i130 else [f"I-130 Receipt Number: {receipt_number}"]),
        "",
        "Dear Sir or Madam,",
        "",
        (
            "Please find enclosed my Form I-485 Application to Register Permanent Residence or "
            "Adjust Status, based on my marriage to a U.S. citizen, filed concurrently with the "
            "Form I-130 Petition for Alien Relative and Form I-130A filed on my behalf."
            if concurrent_i130
            else "Please find enclosed my Form I-485 Application to Register Permanent Residence or "
            "Adjust Status, based on my marriage to a U.S. citizen. My Form I-130 petition "
            + i130_status_sentence
        ),
        "",
        "I am concurrently submitting supporting forms and documentation as outlined below.",
        "",
        "Contents of Submission",
        "",
        *_section_lines(sections),
        "",
        "Thank you for your time and consideration of my application. Please do not hesitate to contact me if additional information is required.",
        "",
        "Sincerely,",
        beneficiary_name,
        SIGNATURE_LINE,
    ]
    return _wrapped(lines)


def generate_cover_letter_pdf(
    *,
    case_id: UUID,
    values: dict[str, Any],
    sections: list[dict[str, Any]],
    output_dir: Path,
    lockbox_address_lines: list[str] | None = None,
) -> GeneratedCoverLetter:
    """Writes a packet's cover letter."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{case_id}-cover-letter.pdf"
    writer = PdfWriter()
    font_refs = {
        "regular": writer._add_object(
            DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }
            )
        ),
        "bold": writer._add_object(
            DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica-Bold"),
                }
            )
        ),
    }
    for page_lines in _page_chunks(
        build_cover_letter_lines(
            values=values,
            sections=sections,
            lockbox_address_lines=lockbox_address_lines,
        )
    ):
        _add_text_page(writer, page_lines, font_refs)
    with output_path.open("wb") as handle:
        writer.write(handle)
    return GeneratedCoverLetter(
        output_path=output_path,
        warnings=[
            (
                "Cover letter: hand-sign if you use the draft."
                if str(values.get("i130_filing_status") or "").strip().lower() in {"not_filed", "none"}
                else "Cover letter: confirm the Form I-130 status and receipt number, and hand-sign if you use the draft."
            ),
        ],
    )


def _slug(value: str) -> str:
    cleaned = "".join(character.lower() if character.isalnum() else "-" for character in value)
    return "-".join(part for part in cleaned.split("-") if part) or "section"


def build_section_index_lines(
    *,
    section_label: str,
    purpose: str,
    items: list[str],
) -> list[str]:
    """Returns the text of a section index page."""
    title = SECTION_TITLES.get(section_label, section_label)
    lines = [
        "Section Index Page",
        title,
        "",
        "Purpose",
        purpose,
        "",
        "Documents queued for this section",
    ]
    if items:
        lines.extend(f"* {item}" for item in items)
    else:
        lines.append("* No separate uploaded supporting PDFs were queued for this section.")
    lines.extend(
        [
            "",
            "Mailing note",
            (
                "This is a plain letter-size index page for the printable draft. When printing, keep pages "
                "single-sided and do not use tabs, binders, folders, sticky notes, heavy staples, duplicate "
                "copies, albums, scrapbooks, digital media, or unnecessary original documents."
            ),
        ]
    )
    return _wrapped(lines)


def generate_section_index_pdf(
    *,
    case_id: UUID,
    section_label: str,
    purpose: str,
    items: list[str],
    output_dir: Path,
) -> GeneratedCoverLetter:
    """Writes a section index page."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{case_id}-{_slug(section_label)}-index.pdf"
    writer = PdfWriter()
    font_refs = {
        "regular": writer._add_object(
            DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }
            )
        ),
        "bold": writer._add_object(
            DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica-Bold"),
                }
            )
        ),
    }
    for page_lines in _page_chunks(
        build_section_index_lines(section_label=section_label, purpose=purpose, items=items)
    ):
        _add_text_page(writer, page_lines, font_refs)
    with output_path.open("wb") as handle:
        writer.write(handle)
    return GeneratedCoverLetter(output_path=output_path, warnings=[])
