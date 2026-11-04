from __future__ import annotations

from uuid import uuid4

from pypdf import PdfReader
import pytest

from app.cli.seed_happy_path import _answer_for_question, sample_answers
from app.cli.seed_packet_scenarios import SCENARIOS, _scenario_answers
from app.content.admission_classes import I130_CLASS_OF_ADMISSION_CODES
from app.content.family_questionnaires import all_i130_questions, all_i130a_questions
from app.content.supplemental_forms import all_supplemental_form_questions, get_supplemental_form_config
from app.services.case_facts import enrich_case_fact_aliases, value_is_answered
from app.services.family_pdf import (
    I130_CHECKBOX_FIELD_MAP,
    I130_CLASS_NOT_OFFERED_WARNING,
    I130A_FOREIGN_ADDRESS_FIELD_MAP,
    build_i130_pdf_field_payload,
    build_i130a_pdf_field_payload,
    generate_i130_pdf,
)
from app.services.form_ingestion import build_form_answer_proposals_from_case_data
from app.services.form_pdf import NON_PDF_CONTROL_QUESTIONS, OTHER_NAME_MAPPINGS, build_form_pdf_field_payload
from app.services.pdf_fields import (
    employment_continuation_line,
    template_field_names,
)


def _available(form: str) -> set[str]:
    return template_field_names(PdfReader(f"blank-immigration-documents/{form}.pdf"))


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
    assert payload.checkbox_values["Pt2Line2b_Unit[0]"] == "/ APT "
    assert payload.text_values["Pt2Line5_EmployerOrCompName[0]"] == "Beta"
    assert payload.text_values["Pt2Line8b_DateTo[0]"] == "12/31/2021"
    assert payload.checkbox_values["Pt2Line6_Unit[1]"] == "/ STE "
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


@pytest.mark.parametrize(
    ("answer", "code"),
    [
        ("B-2", "B2"),
        ("B-1 visitor for business", "B1"),
        ("parolee", "PAR"),
        ("H-1B", "H1B"),
        ("DT", "DT"),
    ],
)
def test_i130_class_of_admission_prints_an_option_of_the_dropdown(answer: str, code: str) -> None:
    payload = build_i130_pdf_field_payload({"beneficiary_class_of_admission": answer}, _available("i-130"))

    assert payload.text_values["Pt4Line21a_ClassOfAdmission[0]"] == code


@pytest.mark.parametrize("answer", ["TN", "L-2S", "E-1S", "E-2S", "E-3S", "Visa Waiver", "in parole"])
def test_i130_class_of_admission_stays_blank_and_warns_when_no_option_matches(answer: str, tmp_path) -> None:
    values = {"beneficiary_class_of_admission": answer}

    assert "Pt4Line21a_ClassOfAdmission[0]" not in build_i130_pdf_field_payload(values, _available("i-130")).text_values
    generated = generate_i130_pdf(case_id=uuid4(), values=values, output_dir=tmp_path)
    assert I130_CLASS_NOT_OFFERED_WARNING in generated.warnings


def test_i130_class_of_admission_codes_match_the_blank_form() -> None:
    field = PdfReader("blank-immigration-documents/i-130.pdf").get_fields()["form1[0].#subform[6].Pt4Line21a_ClassOfAdmission[0]"]
    options = {option[0] if isinstance(option, list) else option for option in field["/Opt"]}

    assert options - {""} == I130_CLASS_OF_ADMISSION_CODES


def test_i130a_prints_every_job_when_the_current_employer_is_not_first_in_the_history() -> None:
    payload = build_i130a_pdf_field_payload(
        {
            "beneficiary_current_employer_or_school": "New Co",
            "beneficiary_employment_history": [
                {"name": "Old Co", "line1": "1 Old St", "to": "2021-01-01"},
                {"name": "New Co", "line1": "9 New Ave", "from": "2021-01-02"},
            ],
        },
        _available("i-130a"),
    )

    assert payload.text_values["Pt2Line1_EmployerOrCompName[0]"] == "New Co"
    assert payload.text_values["Pt2Line2a_StreetNumberName[0]"] == "9 New Ave"
    assert payload.text_values["Pt2Line5_EmployerOrCompName[0]"] == "Old Co"
    assert payload.text_values["Pt2Line6_StreetNumberName[0]"] == "1 Old St"


def test_i130a_keeps_a_past_job_address_off_the_current_employer() -> None:
    values = enrich_case_fact_aliases(
        {
            "beneficiary_current_employer_or_school": "Laney College",
            "beneficiary_employment_history": [{"name": "Old Co", "line1": "1 Old St"}],
        }
    )

    assert "beneficiary_current_employer_address_line1" not in values


def test_only_open_history_entry_supplies_a_missing_current_employer() -> None:
    values = enrich_case_fact_aliases(
        {
            "beneficiary_employment_history": [
                {"name": "Old Co", "line1": "1 Old St", "to": "2021-01-01"},
                {"name": "New Co", "line1": "9 New Ave", "from": "2021-01-02"},
            ],
        }
    )
    payload = build_i130a_pdf_field_payload(values, _available("i-130a"))

    assert payload.text_values["Pt2Line1_EmployerOrCompName[0]"] == "New Co"
    assert payload.text_values["Pt2Line2a_StreetNumberName[0]"] == "9 New Ave"
    assert payload.text_values["Pt2Line4a_DateFrom[0]"] == "01/02/2021"
    assert payload.text_values["Pt2Line5_EmployerOrCompName[0]"] == "Old Co"


def test_two_open_history_entries_do_not_guess_the_current_employer() -> None:
    values = enrich_case_fact_aliases(
        {"beneficiary_employment_history": [{"name": "A Co", "line1": "1 A St"}, {"name": "B Co", "line1": "2 B St"}]}
    )

    assert "beneficiary_current_employer_or_school" not in values
    assert "beneficiary_current_employer_address_line1" not in values


def test_i130a_checks_one_unit_box_when_the_answer_and_history_differ() -> None:
    payload = build_i130a_pdf_field_payload(
        {
            "beneficiary_current_employer_or_school": "Acme",
            "beneficiary_current_employer_address_line2": "Apt 4",
            "beneficiary_employment_history": [{"name": "Acme", "line1": "1 A St", "line2": "Ste 200"}],
        },
        _available("i-130a"),
    )

    assert payload.text_values["Pt2Line2b_AptSteFlrNumber[0]"] == "4"
    assert "Pt2Line2b_Unit[0]" in payload.checkbox_values
    assert "Pt2Line2b_Unit[1]" not in payload.checkbox_values


def test_i130a_note_only_employment_continues_in_part7() -> None:
    payload = build_i130a_pdf_field_payload(
        {"beneficiary_employment_history": [{"notes": "Legacy job text"}, {"name": "Acme"}]}, _available("i-130a")
    )

    assert payload.text_values["Pt2Line1_EmployerOrCompName[0]"] == "Acme"
    assert "Legacy job text" in payload.text_values["Pt7Line3d_AdditionalInfo[0]"]


def test_i130a_foreign_address_question_offers_structured_fields_the_pdf_reads() -> None:
    question = next(item for item in all_i130a_questions() if item["id"] == "beneficiary_recent_foreign_address")
    keys = {field["key"] for field in question["entry_fields"]}

    assert question["answer_type"] == "address"
    assert set(I130A_FOREIGN_ADDRESS_FIELD_MAP) <= keys
    assert "line2" in keys


@pytest.mark.parametrize(
    ("value", "answered"),
    [
        (None, False),
        ("", False),
        ("   ", False),
        ([], False),
        ({}, False),
        (["", None], False),
        ({"line1": "", "city": "  "}, False),
        ([{"line1": ""}], False),
        (False, True),
        (0, True),
        ("Austin", True),
        ({"line1": "", "city": "Austin"}, True),
        ([{"line1": "1 Main St"}], True),
    ],
)
def test_value_is_answered_treats_blank_form_controls_as_no_answer(value: object, answered: bool) -> None:
    assert value_is_answered(value) is answered


def test_a_cleared_address_does_not_block_its_proposal() -> None:
    # The address control saves blank keys when a user clears it, which must not read as an answer.
    assert not value_is_answered({"line1": "", "line2": "", "city": "", "country": ""})
    payload = build_i130a_pdf_field_payload(
        {"beneficiary_recent_foreign_address": {"line1": "", "city": ""}}, _available("i-130a")
    )
    assert "beneficiary_recent_foreign_address" not in {entry["field_key"] for entry in payload.mapped_fields}


def test_employment_continuation_line_prints_form_dates():
    line = employment_continuation_line({"name": "Acme", "from": "2025-04-01", "to": "2026-01-15"})

    assert "04/01/2025 - 01/15/2026" in line


def test_i131_leaves_overseas_location_blank_for_a_us_delivery_address():
    answers = {"i131_processing_city": "Bogota", "i131_processing_country": "Colombia"}

    domestic = build_form_pdf_field_payload(
        "i131", {**answers, "i131_processing_location": "domestic_address"}, _available("i-131")
    )
    overseas = build_form_pdf_field_payload(
        "i131", {**answers, "i131_processing_location": "overseas_office"}, _available("i-131")
    )

    assert "Colombia" not in domestic.text_values.values()
    assert "Colombia" in overseas.text_values.values()
    assert "Bogota" in overseas.text_values.values()


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda scenario: scenario.slug)
def test_seeded_employer_country_does_not_assume_colombia(scenario):
    config = get_supplemental_form_config("i130a")
    questions = {question["id"]: question for page in config["pages"] for question in page["questions"]}

    answer = _answer_for_question("i130a", questions["beneficiary_current_employer_country"], _scenario_answers(scenario))

    assert answer == "United States"


@pytest.mark.parametrize("form_key", ["i130", "i130a", "i765", "i131", "i864"])
def test_happy_path_seed_does_not_print_placeholder_text(form_key):
    sample = sample_answers()
    config = get_supplemental_form_config(form_key)

    answers = {
        question["id"]: _answer_for_question(form_key, question, sample)
        for page in config["pages"]
        for question in page["questions"]
    }

    assert "Sample response" not in answers.values()


def test_i130_prints_petitioner_biographics_and_prior_petition_answer():
    payload = build_i130_pdf_field_payload(
        {
            "petitioner_ethnicity": "hispanic_or_latino",
            "petitioner_race": ["white", "asian"],
            "petitioner_height_feet": 5,
            "petitioner_height_inches": 0,
            "petitioner_weight_pounds": 95,
            "petitioner_eye_color": "hazel",
            "petitioner_hair_color": "white",
            "petitioner_filed_prior_petition": True,
        },
        _available("i-130"),
    )

    assert payload.missing_template_fields == []
    assert payload.checkbox_values == {
        "Pt3Line1_Ethnicity[1]": "/H",
        "Pt3Line2_Race_White[0]": "/W",
        "Pt3Line2_Race_Asian[0]": "/A",
        "Pt3Line5_EyeColor[2]": "/HZL",
        "Pt3Line6_HairColor[7]": "/WHT",
        "Part4Line1_Yes[0]": "/Y",
    }
    assert payload.text_values["Pt3Line3_HeightFeet[0]"] == "5"
    assert payload.text_values["Pt3Line3_HeightInches[0]"] == "0"
    assert [payload.text_values[f"Pt3Line4_Pound{digit}[0]"] for digit in (1, 2, 3)] == ["0", "9", "5"]


def test_every_i130_eye_and_hair_answer_has_a_checkbox():
    questions = {question["id"]: question for question in all_i130_questions()}

    for question_id in ("petitioner_eye_color", "petitioner_hair_color"):
        options = {option["value"] for option in questions[question_id]["options"]}
        assert options <= set(I130_CHECKBOX_FIELD_MAP[question_id])


def test_i130a_part_3_prints_the_foreign_employer():
    payload = build_i130a_pdf_field_payload(
        {
            "beneficiary_foreign_employer_or_school": [
                {"name": "Universidad", "city": "Bogota", "country": "Colombia", "occupation": "Student", "from": "2018-02-01"}
            ]
        },
        _available("i-130a"),
    )

    assert payload.missing_template_fields == []
    assert payload.text_values["Pt3Line1_EmployerOrCompName[0]"] == "Universidad"
    assert payload.text_values["Pt3Line2h_Country[0]"] == "Colombia"
    assert payload.text_values["Pt3Line4a_DateFrom[0]"] == "02/01/2018"
