"""The full-coverage persona takes every data-bearing branch, so its packet shows each mapping on the page."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from pdf_form_assertions import read_pdf_widgets
from pypdf import PdfReader
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.cli.seed_full_coverage import FORM_FILES, generate_full_coverage_pdfs, seed_full_coverage_case
from app.content.full_coverage_sample import build_full_coverage_i485_answers
from app.content.i485_questionnaire import all_i485_questions
from app.models.entities import CaseRecord
from app.services.form_pdf import TEXT_FIELD_MAP as FORM_TEXT_FIELD_MAP
from app.services.i485_pdf import TEXT_FIELD_MAP as I485_TEXT_FIELD_MAP
from app.services.i485_pdf import build_i485_pdf_field_payload

# Mappings the persona cannot reach: one side of a branch that excludes the other, or a box its answers leave empty.
EXCLUSIVE_BRANCHES_LEFT_BLANK: dict[str, set[str]] = {
    # Item 61 asks for a grade only below a diploma; Item 84 only after evading wartime service.
    "i485": {"highest_grade_completed", "status_before_evading_service"}
    # The persona is unemployed, so Item 7 states "Unemployed" and has no employer name.
    | {"beneficiary_current_employer_or_school"},
    # The persona answers "No" to the prior travel documents; the round-trip test covers the dates.
    "i131": {
        "beneficiary_mailing_postal_code",
        "beneficiary_mailing_province",
        "i131_prior_advance_parole_date",
        "i131_prior_advance_parole_disposition",
        "i131_prior_reentry_refugee_document_date",
        "i131_prior_reentry_refugee_document_disposition",
        # Advance parole skips Part 4, Item 7.
        "i131_processing_city",
        "i131_processing_country",
    },
    "i864": set(),
}


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return Session(engine)


@pytest.fixture(scope="module")
def packet(tmp_path_factory: pytest.TempPathFactory) -> dict[str, dict[str, Any]]:
    output_dir = tmp_path_factory.mktemp("full-coverage")
    with _session() as session:
        case = CaseRecord(case_name="Full coverage", workflow_type="marriage_concurrent")
        session.add(case)
        session.commit()
        session.refresh(case)
        seed_full_coverage_case(session, case)
        results = generate_full_coverage_pdfs(session, case.id, output_dir)
    for result in results.values():
        result["values"] = {
            name: widget.value.strip()
            for widget in read_pdf_widgets(Path(result["path"]))
            for name in (widget.name, widget.full_name)
            if widget.value.strip()
        }
    return results


@pytest.mark.parametrize("form_key", FORM_FILES)
def test_every_answer_reaches_the_form(packet, form_key: str) -> None:
    assert packet[form_key].get("unmapped_answered_questions", []) == []


@pytest.mark.parametrize("form_key", ("i485", *FORM_TEXT_FIELD_MAP))
def test_persona_reaches_every_text_mapping_but_exclusive_branches(packet, form_key: str) -> None:
    field_map = I485_TEXT_FIELD_MAP if form_key == "i485" else FORM_TEXT_FIELD_MAP[form_key]
    values = packet[form_key]["values"]
    unreached = {question_id for question_id, fields in field_map.items() if not set(fields) & set(values)}

    assert unreached == EXCLUSIVE_BRANCHES_LEFT_BLANK.get(form_key, set())


def _lines_below_box(path: Path) -> list[str]:
    """Multi-line text whose saved appearance draws a line below the bottom of its field."""
    problems = []
    for page_number, page in enumerate(PdfReader(path).pages, start=1):
        for annotation_ref in page.get("/Annots") or []:
            annotation = annotation_ref.get_object()
            appearance = (annotation.get("/AP") or {}).get("/N")
            if appearance is None or not hasattr(appearance.get_object(), "get_data"):
                continue
            stream = appearance.get_object()
            data = stream.get_data().decode("latin-1")
            if data.count("Tj") < 2:
                continue
            bottom = float(stream["/BBox"][1])
            baseline = 0.0
            for match in re.finditer(r"(-?[\d.]+) (-?[\d.]+) Td|\bTj\b|\bBT\b", data):
                if match.group(0) == "BT":
                    baseline = 0.0
                elif match.group(0) == "Tj":
                    if baseline < bottom:
                        problems.append(f"page {page_number} {annotation.get('/T')}: line at {baseline:.1f}")
                else:
                    baseline += float(match.group(2))
    return problems


@pytest.mark.parametrize("form_key", FORM_FILES)
def test_no_continuation_line_prints_below_its_box(packet, form_key: str) -> None:
    assert _lines_below_box(Path(packet[form_key]["path"])) == []


def test_i485_part14_keeps_every_overflowed_address_with_its_dates(packet) -> None:
    part14 = packet["i485"]["values"]["P14_Line2_AdditionalInfo[0]"]

    assert "Prior address 2: Calle 10 43-21, Apt 502, Medellin, Antioquia, 050021, Colombia; from" in part14
    assert "06/01/2019 to 02/17/2025" in part14
    assert "Prior address 3:" in part14 and "01/04/2016 to 05/31/2019" in part14


def test_i485_other_date_of_birth_yes_ticks_only_yes(packet) -> None:
    values = packet["i485"]["values"]

    assert values["Pt1Line3_YN[0]"] == "/Y"
    assert "Pt1Line3_YN[1]" not in values


def test_i485_name_at_birth_keeps_a_two_word_family_name() -> None:
    payload = build_i485_pdf_field_payload(build_full_coverage_i485_answers())

    assert payload.text_values["Pt5Line2_FamilyName[0]"] == "Gil Ochoa"
    assert payload.text_values["Pt5Line2_GivenName[0]"] == "Luz"
    assert payload.text_values["Pt5Line2_MiddleName[0]"] == "Marina"


def test_i130_lists_the_petitioners_prior_spouse_as_spouse_2(packet) -> None:
    values = packet["i130"]["values"]

    assert values["PtLine20a_FamilyName[0]"] == "Restrepo"
    assert "Pt2Line21_DateMarriageEnded[0]" not in values
    assert values["Pt2Line22a_FamilyName[0]"] == "Novak"
    assert values["Pt2Line23_DateMarriageEnded[0]"] == "08/30/2021"


def test_i130_mailing_po_box_does_not_take_the_physical_apartment(packet) -> None:
    values = packet["i130"]["values"]

    assert values["Pt2Line10_StreetNumberName[0]"] == "PO Box 66120"
    assert "Pt2Line10_AptSteFlrNumber[0]" not in values
    assert values["Pt2Line12_AptSteFlrNumber[0]"] == "1208"


def test_i130a_lists_unemployment_once_and_the_prior_job_second(packet) -> None:
    values = packet["i130a"]["values"]

    assert values["Pt2Line1_EmployerOrCompName[0]"] == "Unemployed"
    assert values["Pt2Line5_EmployerOrCompName[0]"] == "Grupo Andino de Software SAS"
    assert values["Pt1Line3a_FamilyName[1]"] == "Restrepo"


def test_i864_keeps_the_principal_a_number_off_family_member_1(packet) -> None:
    values = packet["i864"]["values"]

    assert values["P2_Line5_AlienNumber[0]"] == "245678913"
    assert "P2_Line5_AlienNumber[1]" not in values
    assert values["P4_Line12_AlienNumber[1]"] == "088123456"
    assert values["P4_Line4a_StreetNumberName[0]"] == "4127 Westheimer Road"


def test_i131_advance_parole_leaves_reentry_permit_delivery_blank(packet) -> None:
    values = packet["i131"]["values"]

    assert not {name for name in values if "P4_Line7" in name}
    assert values["Part2_Line4_AptSteFlrNumber[0]"] == "1208"


def test_payment_forms_generate(packet) -> None:
    assert packet["g1450"]["values"]
    assert packet["g1650"]["values"]
    assert packet["g1145"]["values"]


def test_seed_answers_every_i485_question() -> None:
    answers = build_full_coverage_i485_answers()

    assert {question["id"] for question in all_i485_questions()} <= set(answers)
