from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from pdf_form_assertions import assert_pdf_field_values, template_field_names
from pypdf import PdfReader
import pytest
from test_supplemental_forms import (
    sample_i130_answers,
    sample_i130a_answers,
    sample_i131_answers,
    sample_i765_answers,
    sample_i864_answers,
)

from app.content.i485_sample import build_sample_i485_answers
from app.services.family_pdf import (
    G1145_TEXT_FIELD_MAP,
    I130_CHECKBOX_FIELD_MAP,
    I130_TEXT_FIELD_MAP,
    I130_UNIT_FIELD_MAP,
    I130A_CHECKBOX_FIELD_MAP,
    I130A_PRIOR_ADDRESS_FIELD_MAP,
    I130A_TEXT_FIELD_MAP,
    I130A_UNIT_FIELD_MAP,
    build_g1145_pdf_field_payload,
    generate_g1145_pdf,
)
from app.services.form_pdf import (
    CHECKBOX_FIELD_MAP,
    I864_HOUSEHOLD_DEFAULT_TEXT_VALUES,
    TEXT_FIELD_MAP,
    UNIT_FIELD_MAP,
    build_form_pdf_field_payload,
    generate_form_pdf_from_answers,
)
from app.services.g1450 import CARD_TYPE_APPEARANCES, generate_g1450_pdf_from_payload
from app.services.i485_pdf import (
    AUTO_BOOLEAN_FIELD_MAP,
    MULTI_CHECKBOX_FIELD_MAP,
    _template_button_choices,
    build_i485_pdf_field_payload,
    generate_i485_pdf_from_answers,
)
from app.services.i485_pdf import (
    CHECKBOX_FIELD_MAP as I485_CHECKBOX_FIELD_MAP,
)
from app.services.i485_pdf import (
    TEXT_FIELD_MAP as I485_TEXT_FIELD_MAP,
)
from app.services.pdf_fields import (
    PART14_ADDITIONAL_INFO_DA,
)

TEMPLATE_DIR = Path("blank-immigration-documents")
READY_PREVIEW = {
    "generation_status": "ready_for_user_review",
    "ready_for_pdf_generation": True,
    "missing_required_count": 0,
    "blocking_flag_count": 0,
    "outside_niche_flag_count": 0,
    "low_confidence_count": 0,
}


def _text_fields(field_map: dict[str, tuple[str, ...]]) -> set[str]:
    return {field_name for field_names in field_map.values() for field_name in field_names}


def _checkbox_fields(field_map: dict[str, dict[Any, tuple[str, str]]]) -> set[str]:
    return {field_name for choices in field_map.values() for field_name, _appearance in choices.values()}


def _multi_checkbox_fields(field_map: dict[str, dict[Any, tuple[tuple[str, str], ...]]]) -> set[str]:
    return {
        field_name
        for choices in field_map.values()
        for selected_fields in choices.values()
        for field_name, _appearance in selected_fields
    }


def _unit_fields(field_map: dict[str, tuple[str, str, str, str]]) -> set[str]:
    return {field_name for field_names in field_map.values() for field_name in field_names}


def _assert_template_has_fields(template_name: str, expected_fields: set[str]) -> None:
    template_path = TEMPLATE_DIR / template_name
    if not template_path.exists():
        pytest.skip(f"Local editable {template_name} template is not present.")
    missing = sorted(expected_fields - template_field_names(template_path))
    assert missing == []


def test_every_configured_generated_form_field_exists_in_blank_templates():
    i485_fields = (
        _text_fields(I485_TEXT_FIELD_MAP)
        | _checkbox_fields(I485_CHECKBOX_FIELD_MAP)
        | _multi_checkbox_fields(MULTI_CHECKBOX_FIELD_MAP)
        | _unit_fields({key: tuple(value) for key, value in AUTO_BOOLEAN_FIELD_MAP.items()})
    )
    _assert_template_has_fields("i-485.pdf", i485_fields)

    for form_key, template_name in [
        ("i765", "i-765.pdf"),
        ("i864", "i-864.pdf"),
        ("i131", "i-131.pdf"),
    ]:
        expected_fields = (
            _text_fields(TEXT_FIELD_MAP[form_key])
            | _checkbox_fields(CHECKBOX_FIELD_MAP[form_key])
            | _unit_fields(UNIT_FIELD_MAP.get(form_key, {}))
        )
        if form_key == "i864":
            expected_fields |= set(I864_HOUSEHOLD_DEFAULT_TEXT_VALUES)
        _assert_template_has_fields(template_name, expected_fields)

    _assert_template_has_fields(
        "i-130.pdf",
        _text_fields(I130_TEXT_FIELD_MAP) | _checkbox_fields(I130_CHECKBOX_FIELD_MAP) | _unit_fields(I130_UNIT_FIELD_MAP),
    )
    _assert_template_has_fields(
        "i-130a.pdf",
        _text_fields(I130A_TEXT_FIELD_MAP)
        | _checkbox_fields(I130A_CHECKBOX_FIELD_MAP)
        | _unit_fields(I130A_UNIT_FIELD_MAP)
        | set(I130A_PRIOR_ADDRESS_FIELD_MAP.values())
        | {"Pt1Line6b_Unit[0]", "Pt1Line6b_Unit[1]", "Pt1Line6b_Unit[2]", "Pt1Line6b_AptSteFlrNumber[0]"},
    )
    _assert_template_has_fields("g-1145.pdf", _text_fields(G1145_TEXT_FIELD_MAP))
    _assert_template_has_fields(
        "g-1450.pdf",
        {
            "FamilyName[0]",
            "GivenName[0]",
            "MiddleName[0]",
            "CCHolderFamilyName[0]",
            "CCHolderGivenName[0]",
            "CCHolderMiddleName[0]",
            "Pt1Line2b_StreetNumberName[0]",
            "CCHolderAptSteFlrNumber[0]",
            "CityOrTown[0]",
            "State[0]",
            "ZipCode[0]",
            "DaytimeTelephoneNumber[0]",
            "Email[0]",
            "CreditCardNumber_1[0]",
            "CreditCardNumber_2[0]",
            "CreditCardNumber_3[0]",
            "CreditCardNumber_4[0]",
            "CreditCardNumber_4[1]",
            "ExpirationDate[0]",
            "SignatureOfApplicant[0]",
            "AuthorizedPaymentAmt[0]",
            "CCHolderAptSteFlr_Unit[0]",
            "CCHolderAptSteFlr_Unit[1]",
            "CCHolderAptSteFlr_Unit[2]",
            *{field_name for field_name, _appearance in CARD_TYPE_APPEARANCES.values()},
        },
    )


def test_i485_generation_writes_every_mapped_payload_field(tmp_path: Path):
    template_path = TEMPLATE_DIR / "i-485.pdf"
    if not template_path.exists():
        pytest.skip("Local editable I-485 template is not present.")

    answers = build_sample_i485_answers()
    reader = PdfReader(template_path)
    payload = build_i485_pdf_field_payload(
        answers,
        available_fields=template_field_names(template_path),
        button_choices=_template_button_choices(reader),
    )
    output_path = tmp_path / "i485-output.pdf"

    result = generate_i485_pdf_from_answers(
        case_id=uuid4(),
        answers=answers,
        template_path=template_path,
        output_path=output_path,
        allow_incomplete=False,
    )

    assert payload.missing_template_fields == []
    assert payload.unmapped_answered_questions == []
    assert result.missing_template_fields == []
    assert result.unmapped_answer_count == 0
    assert_pdf_field_values(
        output_path,
        text_values=payload.text_values,
        checkbox_values=payload.checkbox_values,
    )


def test_i485_generation_normalizes_reported_foreign_address_and_visitor_status(tmp_path: Path):
    template_path = TEMPLATE_DIR / "i-485.pdf"
    if not template_path.exists():
        pytest.skip("Local editable I-485 template is not present.")

    answers = {
        **build_sample_i485_answers(),
        "beneficiary_class_of_admission": "VISITOR",
        "beneficiary_current_immigration_status": "B-2",
        "beneficiary_country_of_birth": "Colombia",
        "beneficiary_last_arrival_date": "2026-01-12",
        "beneficiary_last_arrival_first_us_presence": "",
        "beneficiary_recent_foreign_address": {
            "line1": "Carrera 25 # 65 - 110",
            "line2": "Apt 1101",
            "city": "Manizales",
            "state": "CA",
            "province": "Caldas",
            "postal_code": "170004",
            "from": "2022-04-01",
            "to": "2025-07-15",
        },
        "beneficiary_prior_address_history": [
            {
                "line1": "100 Sample St",
                "city": "Sunnyvale",
                "state": "CA",
                "zip": "94086",
                "country": "United States",
                "from": "2025-07-15",
                "to": "2026-03-15",
            },
            {
                "line1": "Carrera 25 # 65 - 110",
                "city": "Manizales",
                "state": "CA",
                "province": "Caldas",
                "postal_code": "170004",
                "country": "Colombia",
                "from": "2022-04-01",
                "to": "2025-07-15",
            }
        ],
        "beneficiary_employment_history": [
            {
                "activity_type": "school",
                "name": "Universidad Nacional de Colombia",
                "occupation": "Student",
                "line1": "Carrera 27 64 - 60",
                "city": "Manizales",
                "state": "CA",
                "province": "Caldas",
                "postal_code": "170003",
                "country": "Colombia",
                "from": "2019-05-01",
                "to": "2025-06-15",
            }
        ],
    }
    output_path = tmp_path / "i485-output.pdf"

    result = generate_i485_pdf_from_answers(
        case_id=uuid4(),
        answers=answers,
        template_path=template_path,
        output_path=output_path,
        allow_incomplete=False,
    )
    payload = build_i485_pdf_field_payload(
        answers,
        available_fields=template_field_names(template_path),
        button_choices=_template_button_choices(PdfReader(template_path)),
    )

    assert result.missing_template_fields == []
    assert payload.text_values["Pt1Line12_Status[0]"] == "B-2 Visitor"
    assert payload.text_values["Pt1Line14_Status[0]"] == "B-2 Visitor"
    assert payload.text_values["Pt1Line11_Admitted[0]"] == "B-2 Visitor"
    assert payload.checkbox_values["Pt2Line11_CB[0]"] == "/11A"
    assert payload.checkbox_values["Pt1Line13_YN[1]"] == "/N"
    assert payload.text_values["Pt1Line18_RecentCountry[0]"] == "Colombia"
    assert payload.text_values["Pt1Line18_RecentProvince[0]"] == "Caldas"
    assert payload.text_values["Pt1Line18_RecentNumber[0]"] == "1101"
    assert payload.checkbox_values["Pt1Line18_RecentUnit[0]"] == "/ APT "
    assert "Pt1Line18_RecentState[0]" not in payload.text_values
    assert payload.text_values["P4Line7_City[0]"] == "Manizales"
    assert payload.text_values["P4Line7_Province[0]"] == "Caldas"
    assert "P4Line7_State[0]" not in payload.text_values
    assert "Manizales, Caldas, 170004, Colombia" in payload.text_values["P14_Line2_AdditionalInfo[0]"]
    assert "State or province" not in payload.text_values["P14_Line2_AdditionalInfo[0]"]
    assert_pdf_field_values(
        output_path,
        text_values={
            "Pt1Line12_Status[0]": "B-2 Visitor",
            "Pt1Line14_Status[0]": "B-2 Visitor",
            "Pt1Line11_Admitted[0]": "B-2 Visitor",
            "Pt1Line18_RecentCountry[0]": "Colombia",
            "Pt1Line18_RecentProvince[0]": "Caldas",
            "Pt1Line18_RecentNumber[0]": "1101",
            "P4Line7_City[0]": "Manizales",
            "P4Line7_Province[0]": "Caldas",
        },
        checkbox_values={"Pt2Line11_CB[0]": "/11A", "Pt1Line13_YN[1]": "/N", "Pt1Line18_RecentUnit[0]": "/APT"},
    )
    reader = PdfReader(output_path)
    for page in reader.pages:
        for annotation_ref in page.get("/Annots") or []:
            annotation = annotation_ref.get_object()
            if str(annotation.get("/T") or "") == "P14_Line2_AdditionalInfo[0]":
                assert str(annotation.get("/DA")) == PART14_ADDITIONAL_INFO_DA
                return
    raise AssertionError("Expected generated I-485 to include Part 14 additional information")


def test_i485_generation_writes_foreign_school_item8_address_fields(tmp_path: Path):
    template_path = TEMPLATE_DIR / "i-485.pdf"
    if not template_path.exists():
        pytest.skip("Local editable I-485 template is not present.")

    answers = {
        **build_sample_i485_answers(),
        "beneficiary_country_of_birth": "Colombia",
        "beneficiary_employment_history": [
            {
                "activity_type": "unemployment",
                "occupation": "Unemployed",
                "financial_support": "Husband",
                "from": "2025-06-15",
                "to": "",
            }
        ],
        "beneficiary_foreign_employer_or_school": [
            {
                "name": "Universidad Nacional de Colombia",
                "occupation": "Student",
                "line1": "Carrera 27 64 - 60",
                "city": "Manizales",
                "province": "Caldas",
                "postal_code": "170003",
                "country": "",
                "from": "2019-05-01",
                "to": "2025-06-15",
            }
        ],
    }
    output_path = tmp_path / "i485-output.pdf"

    generate_i485_pdf_from_answers(
        case_id=uuid4(),
        answers=answers,
        template_path=template_path,
        output_path=output_path,
        allow_incomplete=False,
    )

    assert_pdf_field_values(
        output_path,
        text_values={
            "Pt4Line8_EmployerName[0]": "Universidad Nacional de Colombia",
            "Pt4Line8_Occupation[0]": "Student",
            "P4Line8_StreetName[0]": "Carrera 27 64 - 60",
            "P4Line8_City[0]": "Manizales",
            "P4Line8_Province[0]": "Caldas",
            "P4Line8_PostalCode[0]": "170003",
            "P4Line8_Country[0]": "Colombia",
            "Pt4Line8_DateFrom[0]": "05/01/2019",
            "Pt4Line8_DateTo[0]": "06/15/2025",
        },
        checkbox_values={},
    )


@pytest.mark.parametrize(
    ("form_key", "answers", "template_name"),
    [
        ("i765", sample_i765_answers(), "i-765.pdf"),
        ("i131", sample_i131_answers(), "i-131.pdf"),
        ("i864", sample_i864_answers(), "i-864.pdf"),
        ("i130", sample_i130_answers(), "i-130.pdf"),
        ("i130a", sample_i130a_answers(), "i-130a.pdf"),
    ],
)
def test_supplemental_generation_writes_every_mapped_payload_field(
    tmp_path: Path,
    form_key: str,
    answers: dict[str, object],
    template_name: str,
):
    template_path = TEMPLATE_DIR / template_name
    if not template_path.exists():
        pytest.skip(f"Local editable {template_name} template is not present.")

    payload = build_form_pdf_field_payload(form_key, answers, template_field_names(template_path))
    output_path = tmp_path / f"{form_key}-output.pdf"

    result = generate_form_pdf_from_answers(
        case_id=uuid4(),
        form_key=form_key,
        answers=answers,
        template_path=template_path,
        output_path=output_path,
        allow_incomplete=False,
        preview=READY_PREVIEW,
    )

    assert payload.missing_template_fields == []
    assert payload.unmapped_answered_questions == []
    assert result.missing_template_fields == []
    assert result.unmapped_answer_count == 0
    assert result.field_count == len(payload.text_values) + len(payload.checkbox_values)
    assert_pdf_field_values(
        output_path,
        text_values=payload.text_values,
        checkbox_values=payload.checkbox_values,
    )


def test_g1145_generation_writes_every_mapped_payload_field(tmp_path: Path):
    template_path = TEMPLATE_DIR / "g-1145.pdf"
    if not template_path.exists():
        pytest.skip("Local editable G-1145 template is not present.")

    values = {
        "g1145_last_name": "Sample",
        "g1145_first_name": "Avery",
        "g1145_middle_name": "Maria",
        "g1145_email": "avery.sample@example.com",
        "g1145_mobile_phone": "0000000102",
    }
    payload = build_g1145_pdf_field_payload(values, template_field_names(template_path))
    output_path = tmp_path / "g1145-output.pdf"

    result = generate_g1145_pdf(
        case_id=uuid4(),
        values=values,
        template_path=template_path,
        output_path=output_path,
    )

    assert payload.missing_template_fields == []
    assert result.missing_template_fields == []
    assert result.field_count == len(payload.text_values) + len(payload.checkbox_values)
    assert_pdf_field_values(
        output_path,
        text_values=payload.text_values,
        checkbox_values=payload.checkbox_values,
    )


def test_g1450_generation_writes_all_payment_fields_and_checkboxes(tmp_path: Path):
    template_path = TEMPLATE_DIR / "g-1450.pdf"
    if not template_path.exists():
        pytest.skip("Local editable G-1450 template is not present.")

    output_path = tmp_path / "g1450-output.pdf"
    generate_g1450_pdf_from_payload(
        payload={
            "cardholder_name": "Jordan Lee Petitioner",
            "credit_card_type": "Mastercard",
            "credit_card_number": "5555444433332222",
            "expiration_month": "8",
            "expiration_year": "2028",
            "security_code": "321",
            "billing_address": {
                "street_1": "222 Petitioner Road",
                "street_2": "Suite 12",
                "city": "Oakland",
                "state": "CA",
                "postal_code": "94612",
            },
            "daytime_phone_number": "0000000101",
            "email": "jordan.petitioner@example.com",
            "authorized_amount": "1440",
            "applicant_name": "Avery Maria Sample",
        },
        template_path=template_path,
        output_path=output_path,
    )

    assert_pdf_field_values(
        output_path,
        text_values={
            "FamilyName[0]": "Sample",
            "GivenName[0]": "Avery",
            "MiddleName[0]": "Maria",
            "CCHolderFamilyName[0]": "Petitioner",
            "CCHolderGivenName[0]": "Jordan",
            "CCHolderMiddleName[0]": "Lee",
            "Pt1Line2b_StreetNumberName[0]": "222 Petitioner Road",
            "CCHolderAptSteFlrNumber[0]": "12",
            "CityOrTown[0]": "Oakland",
            "State[0]": "CA",
            "ZipCode[0]": "94612",
            "DaytimeTelephoneNumber[0]": "0000000101",
            "Email[0]": "jordan.petitioner@example.com",
            "CreditCardNumber_1[0]": "5555",
            "CreditCardNumber_2[0]": "4444",
            "CreditCardNumber_3[0]": "3333",
            "CreditCardNumber_4[0]": "2222",
            "CreditCardNumber_4[1]": "321",
            "ExpirationDate[0]": "08/2028",
            "SignatureOfApplicant[0]": "",
            "AuthorizedPaymentAmt[0]": "1440",
        },
        checkbox_values={
            "CreditCardTypeChBx[1]": "/MC",
            "CCHolderAptSteFlr_Unit[0]": "/ STE ",
        },
    )
