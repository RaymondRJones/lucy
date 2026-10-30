from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

import pytest
from pypdf import PdfReader

from app.cli.seed_packet_scenarios import SCENARIOS, _scenario_answers
from app.content.i485_questionnaire import all_i485_questions
from app.content.i485_sample import build_sample_i485_answers
from app.content.uscis_requirements import USCIS_REQUIREMENTS
from app.services.form_pdf import build_form_pdf_field_payload, generate_form_pdf_from_answers
from app.services.g1450 import generate_g1450_pdf_from_payload
from app.services.i485 import conditional_required_i485_question_ids, evaluate_i485_answers
from app.services.i485_pdf import (
    AUTO_BOOLEAN_FIELD_MAP,
    _template_button_choices,
    _template_field_names,
    build_i485_pdf_field_payload,
    generate_i485_pdf_from_answers,
)
from pdf_form_assertions import assert_pdf_field_values, pdf_field_values
from test_supplemental_forms import sample_i864_answers


TEMPLATE_DIR = Path("blank-immigration-documents")
I485_TEMPLATE = TEMPLATE_DIR / "i-485.pdf"
I864_TEMPLATE = TEMPLATE_DIR / "i-864.pdf"
REQUIREMENT_BY_CODE = {requirement["code"]: requirement for requirement in USCIS_REQUIREMENTS}
QUESTION_BY_ID = {question["id"]: question for question in all_i485_questions()}


def _printed_edition(path: Path) -> str:
    match = re.search(r"Edition\s+(\d{2}/\d{2}/\d{2})", PdfReader(path).pages[0].extract_text() or "")
    assert match, f"No printed edition found in {path}"
    return match.group(1)


def _tooltip_and_page(path: Path, short_name: str) -> tuple[str, int]:
    for page_number, page in enumerate(PdfReader(path).pages, start=1):
        for annotation_ref in page.get("/Annots") or []:
            node = annotation_ref.get_object()
            if str(node.get("/T")) != short_name:
                continue
            tooltip = None
            while node is not None and tooltip is None:
                tooltip = node.get("/TU")
                parent = node.get("/Parent")
                node = parent.get_object() if parent is not None else None
            return str(tooltip or ""), page_number
    raise AssertionError(f"{short_name} not found in {path}")


def _i485_payload(answers: dict):
    reader = PdfReader(I485_TEMPLATE)
    return build_i485_pdf_field_payload(
        answers,
        available_fields=_template_field_names(reader),
        button_choices=_template_button_choices(reader),
    )


def _unanswered_required_count(answers: dict) -> int:
    evaluation = evaluate_i485_answers(answers)
    return evaluation["required_questions"] - evaluation["answered_required"]


@pytest.mark.parametrize(
    ("code", "template_name"),
    [
        ("form_i130", "i-130.pdf"),
        ("form_i130a", "i-130a.pdf"),
        ("form_i485", "i-485.pdf"),
        ("form_i864", "i-864.pdf"),
        ("form_i765", "i-765.pdf"),
        ("form_i131", "i-131.pdf"),
    ],
)
def test_bundled_template_edition_matches_accepted_edition(code: str, template_name: str):
    assert _printed_edition(TEMPLATE_DIR / template_name) == REQUIREMENT_BY_CODE[code]["accepted_edition"]


@pytest.mark.parametrize(
    ("question_id", "item"),
    [
        ("received_means_tested_public_benefit", "63"),
        ("failed_to_attend_removal", "65"),
        ("fraudulent_documents", "66"),
        ("lied_for_immigration_benefit", "67"),
        ("false_us_citizen_claim", "68"),
        ("stowaway", "69"),
        ("alien_smuggling", "70"),
        ("document_fraud_civil_penalty", "71"),
        ("deported_removed_or_departed_after_order", "72"),
        ("entered_without_inspection", "73"),
    ],
)
def test_i485_question_item_numbers_agree_with_template_tooltips(question_id: str, item: str):
    assert QUESTION_BY_ID[question_id]["pdf_ref"] == f"Part 9, Item {item}"
    for field_name in AUTO_BOOLEAN_FIELD_MAP[question_id]:
        tooltip, _page = _tooltip_and_page(I485_TEMPLATE, field_name)
        assert f"{item}. " in tooltip


def test_i485_item_63_field_asks_about_means_tested_benefits():
    tooltip, page = _tooltip_and_page(I485_TEMPLATE, "Pt9Line63_YesNo[0]")
    assert "means-tested" in tooltip
    assert page == 19


def test_i485_answers_from_prior_edition_do_not_satisfy_item_63():
    answers = build_sample_i485_answers()
    del answers["received_means_tested_public_benefit"]
    answers.update(
        {
            "received_cash_benefits": False,
            "received_long_term_institutionalization": False,
            "public_charge_benefit_details": "Old free-text note",
        }
    )

    payload = _i485_payload(answers)

    assert QUESTION_BY_ID["received_means_tested_public_benefit"]["required"] is True
    assert _unanswered_required_count(answers) == 1
    assert "Pt9Line63_YesNo[1]" not in payload.checkbox_values
    assert payload.unmapped_answered_questions == []


def test_i485_requires_benefit_history_only_after_yes():
    answers = build_sample_i485_answers()
    assert _unanswered_required_count(answers) == 0

    answers["received_means_tested_public_benefit"] = True
    assert "means_tested_benefit_history" in conditional_required_i485_question_ids(answers)
    assert _unanswered_required_count(answers) == 1


def test_i485_item_57_uses_written_status_or_reviewable_draft():
    answers = build_sample_i485_answers()
    assert _i485_payload(answers).text_values["Pt9Line57_HouseholdSize[0]"] == "Married; household size 2"

    answers["public_charge_family_status"] = "Married; two adults at home"
    assert _i485_payload(answers).text_values["Pt9Line57_HouseholdSize[0]"] == "Married; two adults at home"

    answers["public_charge_family_status"] = "Married and living with my spouse and two children. " * 2
    payload = _i485_payload(answers)
    assert payload.text_values["Pt9Line57_HouseholdSize[0]"] == "See Part 14"
    assert "Married and living" in payload.text_values["P14_Line2_AdditionalInfo[0]"]


def test_i485_moves_long_skill_to_part14_without_clipping_a_row():
    answers = build_sample_i485_answers()
    long_skill = "Licensed professional certification in a specific regulated trade, renewed yearly since 2019"
    answers["certifications_licenses_skills"] = f"Welding\n{long_skill}"

    payload = _i485_payload(answers)

    assert payload.text_values["TextField1[0]"] == "Welding"
    assert "TextField2[0]" not in payload.text_values
    assert "renewed yearly" in " ".join(payload.text_values["P14_Line2_AdditionalInfo[0]"].split())


def test_i485_writes_a_number_to_every_renamed_field():
    answers = build_sample_i485_answers()
    answers["beneficiary_a_number"] = "123456789"
    payload = _i485_payload(answers)

    assert payload.missing_template_fields == []
    for index in range(25):
        assert payload.text_values[f"Pt1Line4_AlienNumber[{index}]"] == "123456789"


def test_i485_reports_public_charge_text_that_will_not_fit_in_part14():
    answers = build_sample_i485_answers()
    answers["received_means_tested_public_benefit"] = True
    answers["means_tested_benefit_history"] = [
        {"benefit_name": f"Benefit {index}", "start_date": "2024-01-01", "reason": "Long explanation. " * 60}
        for index in range(1, 8)
    ]

    payload = _i485_payload(answers)

    assert "means_tested_benefit_history" in {
        item["question_id"] for item in payload.unmapped_answered_questions
    }


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda scenario: scenario.slug)
def test_seeded_scenarios_fill_current_i485_and_i864(tmp_path: Path, scenario):
    answers = _scenario_answers(scenario)
    i485_answers = {key: value for key, value in answers.items() if key in QUESTION_BY_ID}

    result = generate_i485_pdf_from_answers(
        case_id=uuid4(),
        answers=i485_answers,
        template_path=I485_TEMPLATE,
        output_path=tmp_path / "i485.pdf",
        allow_incomplete=True,
    )
    payload = _i485_payload(i485_answers)

    assert result.missing_template_fields == []
    assert result.missing_required_count == 0
    # Prior spouse details are outside the standard flow and are not written to Part 6 yet.
    assert {item["question_id"] for item in payload.unmapped_answered_questions} <= {"beneficiary_prior_marriages"}
    assert _printed_edition(result.output_path) == "09/18/26"
    assert_pdf_field_values(
        result.output_path,
        text_values=payload.text_values,
        checkbox_values=payload.checkbox_values,
    )


def test_benefit_history_scenario_fills_item_64_table_and_part_14(tmp_path: Path):
    scenario = next(item for item in SCENARIOS if item.slug == "wa-public-benefit-history")
    answers = {key: value for key, value in _scenario_answers(scenario).items() if key in QUESTION_BY_ID}
    result = generate_i485_pdf_from_answers(
        case_id=uuid4(),
        answers=answers,
        template_path=I485_TEMPLATE,
        output_path=tmp_path / "i485.pdf",
        allow_incomplete=True,
    )
    values = pdf_field_values(result.output_path)

    assert values["Pt8Line68c_Column1Row1[0]"] == {"Sample cash aid"}
    assert values["Pt8Line68c_Column2Row1[0]"] == {"02/01/2024"}
    assert values["Pt8Line68c_Column3Row1[0]"] == {"07/31/2024"}
    assert values["Pt8Line68c_Column4Row1[0]"] == {"1800"}
    assert values["Pt8Line68c_Column5Row1[0]"] == {"Job loss"}
    assert values["Pt8Line68c_Column1Row2[0]"] == {"See Part 14"}
    assert values["Pt8Line68c_Column5Row2[0]"] == {"See Part 14"}
    assert "Sample rental assistance program" in " ".join(next(iter(values["P14_Line2_AdditionalInfo[0]"])).split())
    assert "long-term illness" in " ".join(next(iter(values["P14_Line2_AdditionalInfo[0]"])).split())


def test_long_answers_scenario_keeps_every_skill_and_benefit(tmp_path: Path):
    scenario = next(item for item in SCENARIOS if item.slug == "il-long-public-charge-answers")
    answers = {key: value for key, value in _scenario_answers(scenario).items() if key in QUESTION_BY_ID}
    payload = _i485_payload(answers)
    part14 = " ".join(
        payload.text_values.get(f"P14_Line{line}_AdditionalInfo[0]", "") for line in range(2, 6)
    )

    assert payload.text_values["TextField8[0]"] == "Sample skill or license 8"
    assert "Sample skill or license 10" in part14
    assert payload.text_values["Pt8Line68c_Column1Row4[0]"] == "See Part 14"
    assert "Sample benefit program 4" in part14
    assert "Sample benefit program 6" in part14
    assert payload.unmapped_answered_questions == []


def test_i864_generation_fills_moved_part8_fields(tmp_path: Path):
    tooltip, page = _tooltip_and_page(I864_TEMPLATE, "P8_Line3_DaytimeTelephoneNumber[0]")
    assert "Sponsor" in tooltip
    assert page == 9

    answers = sample_i864_answers()
    result = generate_form_pdf_from_answers(
        form_key="i864",
        case_id=uuid4(),
        answers=answers,
        template_path=I864_TEMPLATE,
        output_path=tmp_path / "i864.pdf",
        allow_incomplete=False,
    )
    values = pdf_field_values(result.output_path)

    assert result.missing_template_fields == []
    assert _printed_edition(result.output_path) == "08/24/26"
    assert values["P8_Line3_DaytimeTelephoneNumber[0]"] == {answers["petitioner_phone"]}
    assert values["P7Line7_EmailAddress[0]"] == {answers["petitioner_email"]}
    payload = build_form_pdf_field_payload(
        "i864",
        answers,
        available_fields=_template_field_names(PdfReader(I864_TEMPLATE)),
    )
    assert payload.missing_template_fields == []


@pytest.mark.parametrize("scenario", SCENARIOS[:1], ids=lambda scenario: scenario.slug)
def test_generated_i485_prints_saved_field_and_barcode_appearances(tmp_path: Path, scenario):
    answers = {key: value for key, value in _scenario_answers(scenario).items() if key in QUESTION_BY_ID}
    result = generate_i485_pdf_from_answers(
        case_id=uuid4(),
        answers=answers,
        template_path=I485_TEMPLATE,
        output_path=tmp_path / "i485.pdf",
        allow_incomplete=True,
    )
    reader = PdfReader(result.output_path)

    assert reader.trailer["/Root"]["/AcroForm"]["/NeedAppearances"].value is False
    widgets = [annotation.get_object() for page in reader.pages for annotation in page.get("/Annots") or []]
    barcodes = [widget for widget in widgets if str(widget.get("/T")).startswith("PDF417BarCode")]
    assert len(barcodes) == len(reader.pages)
    assert all("/AP" in widget for widget in barcodes)
    filled = [widget for widget in widgets if widget.get("/V") and widget.get("/FT") == "/Tx"]
    assert filled and all("/AP" in widget for widget in filled)


def test_g1650_prints_saved_field_and_barcode_appearances(tmp_path: Path):
    from test_g1650 import _generate

    reader = PdfReader(_generate(tmp_path))

    assert reader.trailer["/Root"]["/AcroForm"]["/NeedAppearances"].value is False
    widgets = [annotation.get_object() for annotation in reader.pages[0]["/Annots"]]
    assert all("/AP" in widget for widget in widgets if widget.get("/V") and str(widget.get("/T")) != "None")


def test_payment_forms_write_whole_dollars_before_the_preprinted_cents(tmp_path: Path):
    payload = {
        "cardholder_name": "Jordan Parker",
        "credit_card_type": "Visa",
        "credit_card_number": "4111111111111111",
        "expiration_month": "1",
        "expiration_year": "2030",
        "security_code": "123",
        "billing_address": {"street_1": "1 Main St", "city": "Oakland", "state": "CA", "postal_code": "94612"},
    }
    result = generate_g1450_pdf_from_payload(
        payload=payload,
        template_path=TEMPLATE_DIR / "g-1450.pdf",
        output_path=tmp_path / "g1450.pdf",
        amount_override="675.00",
    )

    assert pdf_field_values(result.output_path)["AuthorizedPaymentAmt[0]"] == {"675"}
    assert result.authorized_amount == "675.00"
