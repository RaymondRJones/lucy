from __future__ import annotations

from pypdf import PdfReader
import pytest

from app.content.family_questionnaires import all_i130_questions, all_i130a_questions
from app.content.supplemental_forms import all_supplemental_form_questions
from app.services.family_pdf import build_i130a_pdf_field_payload
from app.services.form_ingestion import build_form_answer_proposals_from_case_data
from app.services.form_pdf import NON_PDF_CONTROL_QUESTIONS, OTHER_NAME_MAPPINGS, build_form_pdf_field_payload
from app.services.i485_pdf import _template_field_names


def _available(form: str) -> set[str]:
    return _template_field_names(PdfReader(f"blank-immigration-documents/{form}.pdf"))


@pytest.mark.parametrize(
    ("form_key", "template", "first_row"),
    [
        ("i765", "i-765", ("Line2a_FamilyName[0]", "Line2b_GivenName[0]", "Line2c_MiddleName[0]")),
        ("i131", "i-131", ("Part2_Line2_FamilyName1[0]", "Part2_Line2_GivenName1[0]", "Part2_Line2_MiddleName1[0]")),
    ],
)
def test_other_names_reach_the_supplemental_forms(form_key: str, template: str, first_row: tuple[str, str, str]) -> None:
    payload = build_form_pdf_field_payload(
        form_key, {"beneficiary_other_names": "Rivera, Ana Maria\nAna Lopez"}, _available(template)
    )

    assert [payload.text_values[field] for field in first_row] == ["Rivera", "Ana", "Maria"]
    # Without a comma the family name cannot be told apart, so it goes to additional information as written.
    assert "Ana Lopez" in payload.text_values[OTHER_NAME_MAPPINGS[form_key].continuation_slot[3]]
    assert payload.missing_template_fields == []
    assert payload.unmapped_answered_questions == []


def test_other_names_that_do_not_fit_are_reported() -> None:
    names = "\n".join(f"Unsplittable Name Number {index}" for index in range(40))
    payload = build_form_pdf_field_payload("i131", {"beneficiary_other_names": names}, _available("i-131"))

    assert [entry["question_id"] for entry in payload.unmapped_answered_questions] == ["beneficiary_other_names"]


def test_structured_i485_other_names_propose_as_lines() -> None:
    proposals = build_form_answer_proposals_from_case_data(
        "i765", {"beneficiary_other_names": [{"family_name": "Rivera", "given_name": "Ana", "middle_name": "M"}]}
    )

    assert next(item for item in proposals if item["question_id"] == "beneficiary_other_names")["value"] == "Rivera, Ana M"


def test_i130a_free_text_employment_history_goes_to_part7() -> None:
    history = "Acme Corp, analyst, 2019 to 2021. Unemployed 2021 to 2022. " * 3
    payload = build_i130a_pdf_field_payload({"beneficiary_employment_history": history}, _available("i-130a"))

    assert payload.text_values["Pt7Line3a_PageNumber[0]"] == "2"
    assert payload.text_values["Pt7Line3b_PartNumber[0]"] == "2"
    assert "Acme Corp" in payload.text_values["Pt7Line3d_AdditionalInfo[0]"]
    assert max(len(line) for line in payload.text_values["Pt7Line3d_AdditionalInfo[0]"].splitlines()) <= 38
    assert payload.missing_template_fields == []
    assert {entry["field_key"] for entry in payload.mapped_fields} == {"beneficiary_employment_history"}


def test_i130a_structured_employment_fills_both_employers_then_part7() -> None:
    payload = build_i130a_pdf_field_payload(
        {
            "beneficiary_current_employer_or_school": "Acme",
            "beneficiary_employment_history": [
                {"name": "Acme", "occupation": "Analyst", "line1": "1 Main St", "line2": "Apt 2", "city": "Austin", "state": "Texas", "zip": "78701", "from": "2022-01-01"},
                {"name": "Beta", "occupation": "Clerk", "line1": "9 Elm", "line2": "Ste 4", "city": "Reno", "state": "NV", "from": "2019-01-01", "to": "2021-12-31"},
                {"name": "Gamma", "occupation": "Intern", "from": "2018-01-01", "to": "2018-12-31"},
            ],
        },
        _available("i-130a"),
    )

    assert payload.text_values["Pt2Line1_EmployerOrCompName[0]"] == "Acme"
    assert payload.text_values["Pt2Line2d_State[0]"] == "TX"
    assert payload.text_values["Pt2Line2b_AptSteFlrNumber[0]"] == "2"
    assert payload.checkbox_values["Pt2Line2b_Unit[0]"] == "/APT"
    assert payload.text_values["Pt2Line5_EmployerOrCompName[0]"] == "Beta"
    assert payload.text_values["Pt2Line8b_DateTo[0]"] == "12/31/2021"
    assert payload.checkbox_values["Pt2Line6_Unit[1]"] == "/STE"
    assert "Gamma" in payload.text_values["Pt7Line3d_AdditionalInfo[0]"]
    assert payload.missing_template_fields == []


def test_i130a_does_not_overwrite_the_current_employer_answer() -> None:
    payload = build_i130a_pdf_field_payload(
        {
            "beneficiary_current_employer_or_school": "Acme",
            "beneficiary_employment_history": [{"name": "Older Name", "line1": "1 Main St"}],
        },
        _available("i-130a"),
    )

    assert payload.text_values["Pt2Line1_EmployerOrCompName[0]"] == "Acme"
    assert "Pt2Line2a_StreetNumberName[0]" not in payload.text_values


def test_i130a_history_too_long_for_part7_is_reported() -> None:
    payload = build_form_pdf_field_payload("i130a", {"beneficiary_employment_history": "job detail " * 400}, _available("i-130a"))

    assert "beneficiary_employment_history" in {entry["question_id"] for entry in payload.unmapped_answered_questions}


def _sample(question: dict) -> list:
    answer_type = question["answer_type"]
    if answer_type == "boolean":
        return [True, False]
    if question.get("options"):
        values = [option["value"] for option in question["options"]]
        return [[value] for value in values] if answer_type == "multi_select" else values
    if answer_type == "date":
        return ["2020-01-02"]
    if answer_type == "number":
        return [2]
    if question.get("entry_fields"):
        entry = {field["key"]: "1" for field in question["entry_fields"]}
        return [entry if answer_type == "address" else [entry]]
    return ["1"]


FORM_QUESTIONS = {
    "i765": lambda: all_supplemental_form_questions("i765"),
    "i131": lambda: all_supplemental_form_questions("i131"),
    "i864": lambda: all_supplemental_form_questions("i864"),
    "i130": all_i130_questions,
    "i130a": all_i130a_questions,
}


@pytest.mark.parametrize("form_key", sorted(FORM_QUESTIONS))
def test_answers_reach_the_form_or_are_reported(form_key: str) -> None:
    template = {"i765": "i-765", "i131": "i-131", "i864": "i-864", "i130": "i-130", "i130a": "i-130a"}[form_key]
    available = _available(template)
    silent = []
    for question in FORM_QUESTIONS[form_key]():
        question_id = question["id"]
        if question_id in NON_PDF_CONTROL_QUESTIONS:
            continue
        for answer in _sample(question):
            payload = build_form_pdf_field_payload(form_key, {question_id: answer}, available)
            reported = {entry["question_id"] for entry in payload.unmapped_answered_questions}
            if not (set(payload.text_values) | set(payload.checkbox_values)) and question_id not in reported:
                silent.append((question_id, answer))
            assert not payload.missing_template_fields, question_id

    assert silent == []
