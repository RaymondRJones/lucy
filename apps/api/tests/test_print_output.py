from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from pypdf import PdfReader, PdfWriter
import pypdfium2
import pytest
from test_g1650 import bank_payload
from test_generated_form_pdfs import READY_PREVIEW
from test_packet_assembly import create_case, make_session
from test_supplemental_forms import (
    sample_i130_answers,
    sample_i130a_answers,
    sample_i131_answers,
    sample_i765_answers,
    sample_i864_answers,
)
import zxingcpp

from app.content.fee_schedule import G1450_FORM_EDITION, G1650_FORM_EDITION
from app.content.i485_sample import build_sample_i485_answers
from app.content.uscis_requirements import USCIS_REQUIREMENTS
from app.core.config import settings
from app.services.family_pdf import (
    I130_CHECKBOX_FIELD_MAP,
    I130_UNIT_FIELD_MAP,
    I130A_CHECKBOX_FIELD_MAP,
    I130A_UNIT_FIELD_MAP,
    generate_g1145_pdf,
)
from app.services.form_pdf import CHECKBOX_FIELD_MAP, UNIT_FIELD_MAP, generate_form_pdf_from_answers
from app.services.g1450 import generate_g1450_pdf_from_payload
from app.services.g1650 import generate_g1650_pdf_from_payload
from app.services.i485_pdf import CHECKBOX_FIELD_MAP as I485_CHECKBOX_FIELD_MAP
from app.services.i485_pdf import (
    MULTI_CHECKBOX_FIELD_MAP,
    generate_i485_pdf_from_answers,
)
from app.services.intake import upsert_intake_step
from app.services.packet_assembly import _append_pdf_pages, _flatten_form_fields, assemble_packet_pdf
from app.services.pdf_fields import (
    set_checkbox_values,
)

# Forms are printed and mailed, and USCIS scans each page's PDF417 barcode. It encodes FORM|EDITION|PAGE.
TEMPLATE_DIR = Path("blank-immigration-documents")
PRINT_DPI = 300
EDITIONS = {
    **{
        requirement["code"].removeprefix("form_"): requirement["accepted_edition"]
        for requirement in USCIS_REQUIREMENTS
        if requirement.get("accepted_edition")
    },
    "g1450": G1450_FORM_EDITION,
    "g1650": G1650_FORM_EDITION,
}
SUPPLEMENTAL_ANSWERS = {
    "i130": sample_i130_answers,
    "i130a": sample_i130a_answers,
    "i131": sample_i131_answers,
    "i765": sample_i765_answers,
    "i864": sample_i864_answers,
}
FORM_LABELS = {
    "g1145": "G-1145",
    "g1450": "G-1450",
    "g1650": "G-1650",
    "i130": "I-130",
    "i130a": "I-130A",
    "i131": "I-131",
    "i485": "I-485",
    "i765": "I-765",
    "i864": "I-864",
}
G1450_PAYLOAD: dict[str, Any] = {
    "cardholder_name": "Jordan Lee Petitioner",
    "credit_card_type": "Mastercard",
    "credit_card_number": "5555444433332222",
    "expiration_month": "8",
    "expiration_year": "2028",
    "security_code": "321",
    "billing_address": {
        "street_1": "222 Petitioner Road",
        "city": "Oakland",
        "state": "CA",
        "postal_code": "94612",
    },
    "daytime_phone_number": "0000000101",
    "email": "jordan.petitioner@example.com",
    "authorized_amount": "1440",
    "applicant_name": "Avery Maria Sample",
}


def _generate(form_key: str, output_path: Path) -> Path:
    if form_key == "i485":
        generate_i485_pdf_from_answers(
            case_id=uuid4(),
            answers=build_sample_i485_answers(),
            template_path=TEMPLATE_DIR / "i-485.pdf",
            output_path=output_path,
            allow_incomplete=False,
        )
    elif form_key == "g1145":
        generate_g1145_pdf(
            case_id=uuid4(),
            values={"g1145_last_name": "Sample", "g1145_first_name": "Avery", "g1145_email": "avery@example.com"},
            template_path=TEMPLATE_DIR / "g-1145.pdf",
            output_path=output_path,
        )
    elif form_key == "g1450":
        generate_g1450_pdf_from_payload(
            payload=G1450_PAYLOAD,
            template_path=TEMPLATE_DIR / "g-1450.pdf",
            output_path=output_path,
        )
    elif form_key == "g1650":
        generate_g1650_pdf_from_payload(
            payload={**bank_payload(), "applicant_name": "Avery Parker"},
            template_path=TEMPLATE_DIR / "g-1650.pdf",
            output_path=output_path,
            amount_override="1440.00",
        )
    else:
        generate_form_pdf_from_answers(
            case_id=uuid4(),
            form_key=form_key,
            answers=SUPPLEMENTAL_ANSWERS[form_key](),
            template_path=TEMPLATE_DIR / f"{FORM_LABELS[form_key].lower()}.pdf",
            output_path=output_path,
            allow_incomplete=False,
            preview=READY_PREVIEW,
        )
    return output_path


def _decoded_barcodes(path: Path) -> list[list[str]]:
    document = pypdfium2.PdfDocument(path)
    document.init_forms()
    pages = []
    for page in document:
        image = page.render(scale=PRINT_DPI / 72, may_draw_forms=True).to_pil()
        pages.append([barcode.text for barcode in zxingcpp.read_barcodes(image, formats=zxingcpp.BarcodeFormat.PDF417)])
    document.close()
    return pages


def _expected_barcodes(form_key: str, page_count: int) -> list[list[str]]:
    return [[f"{FORM_LABELS[form_key]}|{EDITIONS[form_key]}|{page}"] for page in range(1, page_count + 1)]


@pytest.fixture(scope="module")
def generated_forms(tmp_path_factory) -> dict[str, Path]:
    output_dir = tmp_path_factory.mktemp("print-output")
    return {form_key: _generate(form_key, output_dir / f"{form_key}.pdf") for form_key in FORM_LABELS}


@pytest.mark.parametrize("form_key", sorted(FORM_LABELS))
def test_every_printed_page_has_a_readable_barcode_for_the_accepted_edition(generated_forms, form_key) -> None:
    path = generated_forms[form_key]

    assert _decoded_barcodes(path) == _expected_barcodes(form_key, len(PdfReader(path).pages))


@pytest.mark.parametrize("form_key", sorted(FORM_LABELS))
def test_filled_forms_print_saved_appearances_instead_of_redrawing_fields(generated_forms, form_key) -> None:
    acroform = PdfReader(generated_forms[form_key]).trailer["/Root"]["/AcroForm"]

    assert acroform.get("/NeedAppearances", False) is False or acroform["/NeedAppearances"].value is False


def _undefined_checkbox_states(path: Path) -> list[tuple[int, str, str]]:
    undefined = []
    for page_number, page in enumerate(PdfReader(path).pages, start=1):
        for reference in page.get("/Annots") or []:
            widget = reference.get_object()
            appearance = widget.get("/AP")
            state = widget.get("/AS")
            if not appearance or state in (None, "/Off"):
                continue
            normal = appearance.get_object()["/N"].get_object()
            if state not in normal:
                undefined.append((page_number, str(widget.get("/T")), str(state)))
    return undefined


@pytest.mark.parametrize("form_key", sorted(FORM_LABELS))
def test_checked_boxes_use_a_state_the_template_can_draw(generated_forms, form_key) -> None:
    assert _undefined_checkbox_states(generated_forms[form_key]) == []


@pytest.mark.parametrize(
    ("template", "field", "unit_state", "drawn_state"),
    [
        ("i-130.pdf", "Pt2Line10_Unit[0]", "/ APT ", "/APT "),
        ("i-130.pdf", "Pt2Line41_Unit[1]", "/ STE ", "/STE"),
        ("i-485.pdf", "Pt1Line18_PriorAddress_Unit[0]", "/ APT ", "/APT"),
    ],
)
def test_unit_checkboxes_print_despite_inconsistent_template_spelling(tmp_path, template, field, unit_state, drawn_state):
    writer = PdfWriter(clone_from=TEMPLATE_DIR / template)
    set_checkbox_values(writer, {field: unit_state})
    path = tmp_path / "unit.pdf"
    with path.open("wb") as handle:
        writer.write(handle)

    states = [
        widget.get("/AS")
        for page in PdfReader(path).pages
        for widget in (reference.get_object() for reference in page.get("/Annots") or [])
        if str(widget.get("/T")) == field
    ]
    assert states == [drawn_state]


def _template_states(template: str) -> dict[str, list[set[str]]]:
    states: dict[str, list[set[str]]] = {}
    for page in PdfReader(TEMPLATE_DIR / template).pages:
        for reference in page.get("/Annots") or []:
            widget = reference.get_object()
            normal = widget["/AP"].get_object().get("/N") if widget.get("/AP") else None
            if normal is not None and "/Subtype" not in normal.get_object():
                defined = {str(state).replace("/", "").strip() for state in normal.get_object()} - {"Off"}
                states.setdefault(str(widget.get("/T")), []).append(defined)
    return states


def _mapped_checkboxes(checkbox_map: dict[str, dict[Any, tuple[str, str]]]) -> set[tuple[str, str]]:
    return {pair for choices in checkbox_map.values() for pair in choices.values()}


def _mapped_units(unit_map: dict[str, tuple[str, str, str, str]]) -> set[tuple[str, str]]:
    return {
        (field, state)
        for apt_field, ste_field, flr_field, _number_field in unit_map.values()
        for field, state in ((apt_field, "APT"), (ste_field, "STE"), (flr_field, "FLR"))
    }


MAPPED_CHECKBOXES = {
    "i-130.pdf": _mapped_checkboxes(I130_CHECKBOX_FIELD_MAP) | _mapped_units(I130_UNIT_FIELD_MAP),
    "i-130a.pdf": _mapped_checkboxes(I130A_CHECKBOX_FIELD_MAP) | _mapped_units(I130A_UNIT_FIELD_MAP),
    "i-131.pdf": _mapped_checkboxes(CHECKBOX_FIELD_MAP["i131"]) | _mapped_units(UNIT_FIELD_MAP.get("i131", {})),
    "i-485.pdf": _mapped_checkboxes(I485_CHECKBOX_FIELD_MAP)
    | {pair for choices in MULTI_CHECKBOX_FIELD_MAP.values() for pairs in choices.values() for pair in pairs},
    "i-765.pdf": _mapped_checkboxes(CHECKBOX_FIELD_MAP["i765"]) | _mapped_units(UNIT_FIELD_MAP.get("i765", {})),
    "i-864.pdf": _mapped_checkboxes(CHECKBOX_FIELD_MAP["i864"]) | _mapped_units(UNIT_FIELD_MAP.get("i864", {})),
}


@pytest.mark.parametrize("template", sorted(MAPPED_CHECKBOXES))
def test_every_mapped_checkbox_state_exists_on_the_template(template) -> None:
    states = _template_states(template)

    problems = sorted(
        (field, requested, str(states.get(field.split(".")[-1])))
        for field, requested in MAPPED_CHECKBOXES[template]
        if not any(requested.replace("/", "").strip() in defined for defined in states.get(field.split(".")[-1], []))
    )

    assert problems == []


def _merged_packet(generated_forms: dict[str, Path], form_keys: tuple[str, ...], output_path: Path) -> list[list[str]]:
    writer = PdfWriter()
    expected: list[list[str]] = []
    for form_key in form_keys:
        expected.extend(_expected_barcodes(form_key, _append_pdf_pages(writer, generated_forms[form_key])))
    assert _flatten_form_fields(writer) == 0
    with output_path.open("wb") as handle:
        writer.write(handle)
    return expected


def test_barcodes_survive_merging_forms_into_one_packet(generated_forms, tmp_path) -> None:
    packet = tmp_path / "packet.pdf"
    expected = _merged_packet(generated_forms, tuple(sorted(FORM_LABELS)), packet)

    assert _decoded_barcodes(packet) == expected


def test_answers_are_drawn_on_packet_pages_in_every_renderer(generated_forms, tmp_path) -> None:
    packet = tmp_path / "packet.pdf"
    _merged_packet(generated_forms, ("g1450",), packet)
    document = pypdfium2.PdfDocument(packet)

    text = document[0].get_textpage().get_text_bounded()
    document.close()

    assert "5555444433332222" in text.replace(" ", "")
    assert "/AcroForm" not in PdfReader(packet).trailer["/Root"]


def test_assembled_packet_prints_a_barcode_on_every_generated_form_page(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    session = make_session()
    case = create_case(session)
    upsert_intake_step(
        session,
        case.id,
        "basics",
        {"beneficiary_first_name": "Avery", "beneficiary_last_name": "Parker", "i130_filing_status": "not_filed"},
    )
    session.commit()

    result = assemble_packet_pdf(
        session=session,
        case_id=case.id,
        state_code="CA",
        output_dir=tmp_path / "generated",
        include_generated_forms=True,
        allow_incomplete=True,
    )

    decoded = {text for page in _decoded_barcodes(result.output_path) for text in page}
    forms = [document for document in result.included_documents if document["source_type"] == "generated_form"]
    assert {document["label"] for document in forms} >= {"Form I-485", "Form I-130"}
    for document in forms:
        form_key = next(key for key, label in FORM_LABELS.items() if document["label"] == f"Form {label}")
        expected = {text for page in _expected_barcodes(form_key, document["page_count"]) for text in page}
        assert expected <= decoded, document["label"]
