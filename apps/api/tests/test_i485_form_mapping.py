from __future__ import annotations

from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from pypdf import PdfReader
import pytest

from app.content.i485_questionnaire import all_i485_questions
from app.content.i485_sample import SAMPLE_I485_ANSWERS
from app.services.i485 import build_i485_intake_projection, conditional_required_i485_question_ids
from app.services.i485_pdf import (
    AUTO_BOOLEAN_FIELD_MAP,
    CHECKBOX_FIELD_MAP,
    DEFAULT_I485_TEMPLATE_PATH,
    ENTRY_LIST_MAPPINGS,
    MULTI_CHECKBOX_FIELD_MAP,
    NON_PDF_CONTROL_QUESTIONS,
    OVERLONG_WARNING,
    PART14_ADDITIONAL_INFO_FIELDS,
    RETIRED_QUESTION_IDS,
    SEE_PART14,
    TEXT_FIELD_MAP,
    _template_button_choices,
    _template_field_names,
    build_i485_pdf_field_payload,
    generate_i485_pdf_from_answers,
)

QUESTIONS = {question["id"]: question for question in all_i485_questions()}
READER = PdfReader(DEFAULT_I485_TEMPLATE_PATH)
AVAILABLE_FIELDS = _template_field_names(READER)
BUTTON_CHOICES = _template_button_choices(READER)
TOOLTIPS = {
    str(annotation.get_object().get("/T")): " ".join(str(annotation.get_object().get("/TU") or "").split())
    for page in READER.pages
    for annotation in page.get("/Annots", []) or []
}


def _payload(answers: dict[str, Any]):
    return build_i485_pdf_field_payload(answers, AVAILABLE_FIELDS, BUTTON_CHOICES)


def _item_pattern(item: str) -> re.Pattern[str]:
    match = re.fullmatch(r"(\d+)(?:\.([a-z]))?", item)
    assert match, item
    number, letter = match.groups()
    if letter:
        return re.compile(rf"\b{number}\.? {letter.upper()}\b\.?")
    return re.compile(rf"(?<!Number )(?<!Numbers )\b{number}\.")


PART9_BOOLEANS = sorted(
    question_id
    for question_id, question in QUESTIONS.items()
    if question["answer_type"] == "boolean"
    and str(question.get("pdf_ref", "")).startswith("Part 9, Item ")
)


@pytest.mark.parametrize("question_id", PART9_BOOLEANS)
def test_part9_answer_ticks_the_item_it_claims(question_id: str) -> None:
    item = QUESTIONS[question_id]["pdf_ref"].removeprefix("Part 9, Item ")
    fields = AUTO_BOOLEAN_FIELD_MAP[question_id]

    assert len(fields) == 2, "one question must answer exactly one form item"
    for field in fields:
        assert _item_pattern(item).search(TOOLTIPS[field]), f"{field} is not Item {item}: {TOOLTIPS[field]}"
    assert {BUTTON_CHOICES[field].get("yes") for field in fields} - {None} == {"/Y"}
    assert {BUTTON_CHOICES[field].get("no") for field in fields} - {None} == {"/N"}


def test_every_part9_item_on_the_form_has_a_question() -> None:
    template_items = {
        field.rsplit("[", 1)[0]
        for field in TOOLTIPS
        if re.search(r"YesNo\[\d\]$", field)
    }
    mapped = {
        field.rsplit("[", 1)[0]
        for fields in AUTO_BOOLEAN_FIELD_MAP.values()
        for field in fields
        if re.search(r"YesNo\[\d\]$", field)
    }

    assert template_items - mapped == set()


def test_a_yes_ticks_only_its_own_item() -> None:
    payload = _payload({"prostitution_procured": True})

    assert payload.checkbox_values == {field: "/Y" for field in AUTO_BOOLEAN_FIELD_MAP["prostitution_procured"] if BUTTON_CHOICES[field].get("yes")}
    assert len(payload.checkbox_values) == 1
    assert next(iter(payload.checkbox_values)).startswith("Pt8Line31")


def _sample_answer(question: dict[str, Any]) -> list[Any]:
    answer_type = question["answer_type"]
    if answer_type == "boolean":
        return [True, False]
    if answer_type in {"select", "single_check"} and question.get("options"):
        return [option["value"] for option in question["options"]]
    if answer_type == "multi_select":
        return [[option["value"]] for option in question["options"]]
    if answer_type == "date":
        return ["2020-01-02"]
    if answer_type == "number":
        return [2]
    if question.get("entry_fields"):
        entry = {
            field["key"]: "2020-01-02" if field.get("type") == "date" else (field["options"][0]["value"] if field.get("options") else "1")
            for field in question["entry_fields"]
        }
        return [entry if answer_type == "address" else [entry]]
    return ["1"]


# Questions that steer the workflow but have no box of their own on the form.
NO_FORM_FIELD = NON_PDF_CONTROL_QUESTIONS
# Answers outside the standard flow with no box mapped yet: they must be reported, never silently left blank.
REPORTED_NOT_FILLED = {
    "i485_family_category": {"other"},
    "public_charge_exempt_category": {"asylee_refugee_or_other", "unsure"},
}


@pytest.mark.parametrize("question_id", sorted(QUESTIONS))
def test_every_answer_reaches_the_form_or_is_declared_formless(question_id: str) -> None:
    question = QUESTIONS[question_id]
    if question_id in NO_FORM_FIELD:
        return
    for answer in _sample_answer(question):
        payload = _payload({question_id: answer})
        filled = set(payload.text_values) | set(payload.checkbox_values)
        reported = {entry["question_id"] for entry in payload.unmapped_answered_questions}

        if answer in REPORTED_NOT_FILLED.get(question_id, ()):
            assert question_id in reported
            continue
        assert question_id not in reported, f"{question_id}={answer!r} is not on the form"
        assert filled, f"{question_id}={answer!r} wrote nothing"
        assert not payload.missing_template_fields


def test_every_mapped_field_exists_on_the_template() -> None:
    fields = {field for names in TEXT_FIELD_MAP.values() for field in names}
    fields |= {field for names in AUTO_BOOLEAN_FIELD_MAP.values() for field in names}
    fields |= {field for choices in CHECKBOX_FIELD_MAP.values() for field, _ in choices.values()}
    fields |= {field for choices in MULTI_CHECKBOX_FIELD_MAP.values() for pairs in choices.values() for field, _ in pairs}
    for mapping in ENTRY_LIST_MAPPINGS:
        for row in mapping.rows:
            fields |= set(row.values())
        for row_choices in mapping.choices:
            fields |= {field for choices in row_choices.values() for field, _ in choices.values()}

    assert fields - AVAILABLE_FIELDS == set()


def test_retired_questions_are_no_longer_asked() -> None:
    assert RETIRED_QUESTION_IDS & set(QUESTIONS) == set()


@pytest.mark.parametrize("mapping", ENTRY_LIST_MAPPINGS, ids=lambda mapping: mapping.question_id)
def test_every_entry_field_has_a_home_on_the_form(mapping) -> None:
    question = QUESTIONS[mapping.question_id]
    assert question["form_entry_limit"] == len(mapping.rows)
    choice_keys = {key for row in mapping.choices for key in row}
    for row in mapping.rows:
        assert {field["key"] for field in question["entry_fields"]} == set(row) | choice_keys


def test_part3_ticks_exactly_one_box() -> None:
    options = [option["value"] for option in QUESTIONS["i485_i864_exemption"]["options"]]
    ticked = set()
    for option in options:
        boxes = [field for field in _payload({"i485_i864_exemption": option}).checkbox_values if field.startswith("Pt3Line1_CB")]
        assert len(boxes) == 1
        ticked.add(boxes[0])

    assert len(ticked) == len(options)
    assert "required to submit an Affidavit of Support" in TOOLTIPS["Pt3Line1_CB[5]"]
    assert _payload({"i485_i864_exemption": "not_requesting_exemption"}).checkbox_values == {"Pt3Line1_CB[5]": "/5"}


def test_entries_fill_their_own_rows() -> None:
    payload = _payload(
        {
            "beneficiary_other_names": [
                {"family_name": "Rivera", "given_name": "Ana", "middle_name": ""},
                {"family_name": "Lopez", "given_name": "Ana", "middle_name": "M"},
            ],
            "beneficiary_prior_marriages": [
                {"family_name": "Doe", "given_name": "Sam", "marriage_date": "2015-06-01", "end_date": "2021-03-15", "how_ended": "divorced"}
            ],
            "children_details": [
                {"family_name": "Rivera", "given_name": "Max", "a_number": "A012345678", "date_of_birth": "2019-02-03", "applying_separately": True}
            ],
            "organizations_details": [{"name": "Rotary", "date_from": "2020-01-01", "date_to": "2021-01-01"}],
            "beneficiary_other_a_numbers": [{"a_number": "A-111-222-333"}],
            "beneficiary_other_dates_of_birth": [{"date_of_birth": "1990-01-02"}],
        }
    )

    assert payload.text_values["Pt1Line2_FamilyName[0]"] == "Rivera"
    assert payload.text_values["Pt1Line2a_MiddleName[0]"] == "M"
    assert payload.text_values["Pt6Line12_FamilyName[0]"] == "Doe"
    assert payload.text_values["Pt6Line16_DateofBirth[0]"] == "06/01/2015"
    assert payload.checkbox_values["Pt6Line19_MaritalStatus[3]"] == "/2"
    assert payload.text_values["Pt7Line2_AlienNumber[0]"] == "012345678"
    assert payload.checkbox_values["Pt7Line2_YN[1]"] == "/Y"
    assert payload.text_values["Pt9Line2_Organization1[0]"] == "Rotary"
    assert payload.text_values["Pt1Line5A_ANumber[0]"] == "111222333"
    assert payload.text_values["Pt1Line3A_OtherDOB[0]"] == "01/02/1990"
    assert payload.unmapped_answered_questions == []


def _part14_text(text_values: dict[str, str]) -> str:
    return "\n".join(text_values.get(field, "") for field in sorted(PART14_ADDITIONAL_INFO_FIELDS))


def test_extra_entries_go_to_part14_with_their_location() -> None:
    payload = _payload(
        {
            "children_details": [
                {"family_name": "One", "given_name": "A"},
                {"family_name": "Two", "given_name": "B"},
                {"family_name": "Three", "given_name": "C", "applying_separately": True},
            ]
        }
    )

    assert payload.text_values["Pt7Line3_FamilyName[0]"] == "Two"
    assert "Three" in _part14_text(payload.text_values)
    assert "Three" not in {payload.text_values.get("Pt7Line2_FamilyName[0]"), payload.text_values.get("Pt7Line3_FamilyName[0]")}
    assert payload.text_values["Pt9Line3a_PageNumber[0]"] == "12"
    assert payload.text_values["Pt9Line3b_PartNumber[0]"] == "7"
    assert payload.text_values["Pt9Line3c_ItemNumber[0]"] == "3"
    assert payload.unmapped_answered_questions == []


def test_an_entry_too_long_for_its_box_moves_whole_to_part14() -> None:
    long_name = "Q" * 30
    payload = _payload({"beneficiary_prior_marriages": [{"family_name": long_name, "given_name": "Sam", "how_ended": "annulled"}]})

    assert payload.text_values["Pt6Line12_FamilyName[0]"] == SEE_PART14
    assert long_name in _part14_text(payload.text_values)
    assert "Annulled" in _part14_text(payload.text_values)
    assert "Pt6Line19_MaritalStatus[1]" not in payload.checkbox_values


def test_answers_saved_as_free_text_are_copied_to_part14_verbatim() -> None:
    legacy = "One prior marriage ended by final divorce decree in 2021."
    payload = _payload({"beneficiary_prior_marriages": legacy})

    assert legacy in _part14_text(payload.text_values).replace("\n", " ")
    assert payload.unmapped_answered_questions == []


def test_what_part14_cannot_hold_is_reported_not_dropped() -> None:
    entries = [{"family_name": f"Name{index}", "given_name": "X"} for index in range(60)]
    payload = _payload(
        {
            "children_details": entries,
            "beneficiary_employment_history": [{"name": f"Employer {index}"} for index in range(60)],
            "beneficiary_prior_address_history": [{"line1": f"{index} Main St", "city": "Austin"} for index in range(40)],
        }
    )

    reported = {entry["question_id"] for entry in payload.unmapped_answered_questions}
    assert {"children_details", "beneficiary_employment_history", "beneficiary_prior_address_history"} <= reported


def test_criminal_explanation_is_filed_against_the_items_it_explains() -> None:
    payload = _payload({"criminal_explanations": "Item 22: cited for a traffic offense in 2019."})

    assert "traffic offense" in _part14_text(payload.text_values)
    assert payload.text_values["Pt9Line3c_ItemNumber[0]"] == "22-41"
    assert payload.unmapped_answered_questions == []


@pytest.mark.parametrize("raw", ["+1 (512) 555-0100", "512.555.0100", "15125550100", "5125550100"])
def test_phone_numbers_print_as_ten_digits(raw: str) -> None:
    payload = _payload({"beneficiary_phone": raw, "beneficiary_mobile_phone": raw})

    assert payload.text_values["Pt3Line3_DaytimePhoneNumber1[0]"] == "5125550100"
    assert payload.text_values["Pt3Line4_MobileNumber1[0]"] == "5125550100"


@pytest.mark.parametrize(
    ("answers", "required"),
    [
        ({"controlled_substance_family_benefit": True}, "controlled_substance_family_benefit_knowledge"),
        ({"served_as_foreign_government_official": True}, "religious_freedom_violations"),
        ({"trafficking_family_benefit": True}, "trafficking_family_benefit_knowledge"),
        ({"j_exchange_two_year_rule": True}, "j_foreign_residence_complied"),
        ({"j_exchange_two_year_rule": True, "j_foreign_residence_complied": False}, "j_waiver_granted"),
        ({"unlawful_presence_after_1997": True}, "unlawful_presence_due_to_trafficking"),
        ({"evaded_wartime_service": True}, "status_before_evading_service"),
        ({"highest_education": "less_than_high_school"}, "highest_grade_completed"),
        ({"beneficiary_used_other_dob": True}, "beneficiary_other_dates_of_birth"),
        ({"beneficiary_has_other_a_numbers": True}, "beneficiary_other_a_numbers"),
        ({"children_count": 1}, "children_details"),
        ({"beneficiary_marriage_count": 2}, "beneficiary_prior_marriages"),
        ({"organizations_membership": True}, "organizations_details"),
    ],
)
def test_follow_up_items_become_required(answers: dict[str, Any], required: str) -> None:
    assert required in conditional_required_i485_question_ids(answers)
    assert required not in conditional_required_i485_question_ids({})


def test_generated_pdf_carries_part3_and_a_single_item(tmp_path: Path) -> None:
    result = generate_i485_pdf_from_answers(
        case_id=uuid4(),
        answers={**SAMPLE_I485_ANSWERS, "prostitution_procured": True},
        output_path=tmp_path / "i-485.pdf",
    )

    assert result.missing_template_fields == []
    states = {
        str(annotation.get_object().get("/T")): str(annotation.get_object().get("/AS"))
        for page in PdfReader(result.output_path).pages
        for annotation in page.get("/Annots", []) or []
    }
    assert states["Pt3Line1_CB[5]"] == "/5"
    yes, no = sorted(AUTO_BOOLEAN_FIELD_MAP["prostitution_procured"], key=lambda field: "no" in BUTTON_CHOICES[field])
    assert states[yes] == "/Y"
    assert states[no] == "/Off"


def test_overlong_values_are_named_in_the_warnings(tmp_path: Path) -> None:
    long_name = "Q" * 60
    result = generate_i485_pdf_from_answers(
        case_id=uuid4(),
        answers={**SAMPLE_I485_ANSWERS, "beneficiary_city_of_birth": long_name},
        output_path=tmp_path / "i-485.pdf",
    )

    assert any("Pt1Line7_CityTownOfBirth[0]" in warning for warning in result.warnings)
    assert not any(warning.startswith(OVERLONG_WARNING) for warning in generate_i485_pdf_from_answers(
        case_id=uuid4(), answers=SAMPLE_I485_ANSWERS, output_path=tmp_path / "clean.pdf"
    ).warnings)


def test_a_note_left_on_a_completed_entry_does_not_keep_it_off_the_form() -> None:
    payload = _payload(
        {
            "beneficiary_prior_marriages": [
                {"family_name": "Doe", "given_name": "Sam", "how_ended": "divorced", "notes": "Ended by final decree in 2021."}
            ]
        }
    )

    assert payload.text_values["Pt6Line12_FamilyName[0]"] == "Doe"
    assert payload.checkbox_values["Pt6Line19_MaritalStatus[3]"] == "/2"
    assert "Ended by final decree in 2021." in _part14_text(payload.text_values).replace("\n", " ")


def test_other_names_are_shared_with_the_other_forms() -> None:
    projection = build_i485_intake_projection({"beneficiary_other_names": [{"family_name": "Rivera", "given_name": "Ana"}]})

    assert projection["beneficiary_other_names"] == [{"family_name": "Rivera", "given_name": "Ana"}]
