from __future__ import annotations

import json
from pathlib import Path

from pdf_form_assertions import pdf_field_appearance_states, pdf_field_values
from pydantic import ValidationError
from pypdf import PdfReader
import pytest
from sqlmodel import select
from test_packet_assembly import add_checklist_item, create_case, make_session

from app.content.fee_schedule import FEE_SCHEDULE_EDITION, G1450_FORM_FEES
from app.content.packet_mailing import LOCKBOX_BY_LOCATION, mailing_recommendation_for_location
from app.models.entities import AuditLog
from app.schemas.common import G1650BankDetailsWrite, PacketAssemblyGenerateRequest
from app.services.g1650 import generate_g1650_pdf_from_payload, validate_g1650_payload
from app.services.intake import upsert_intake_step
from app.services.packet_assembly import assemble_packet_pdf

TEMPLATE = Path("blank-immigration-documents/g-1650.pdf")
APPLICANT = "form1[0].PG1[0].sfApplicantPetitionerName[0]"
HOLDER = "form1[0].PG1[0].sfBankAccountHolderInfo[0]"
BANK = "form1[0].PG1[0].sfBankAccountInformation[0]"
SAMPLE_ROUTING = "011000015"
SAMPLE_ACCOUNT = "000123456789"


def bank_payload(**overrides) -> dict:
    return {
        "account_ownership": "personal",
        "account_type": "checking",
        "account_holder_name": "Jordan Parker",
        "business_name": "",
        "bank_name": "Sample Community Bank",
        "routing_number": SAMPLE_ROUTING,
        "account_number": SAMPLE_ACCOUNT,
        **overrides,
    }


def _generate(tmp_path: Path, **overrides) -> Path:
    payload = {**bank_payload(**overrides), "applicant_name": "Avery Parker"}
    return generate_g1650_pdf_from_payload(
        payload=payload,
        template_path=TEMPLATE,
        output_path=tmp_path / "g1650.pdf",
        amount_override="1440.00",
    ).output_path


def _checkbox_x(path: Path, short_name: str) -> float:
    for annotation_ref in PdfReader(path).pages[0]["/Annots"]:
        annotation = annotation_ref.get_object()
        if str(annotation.get("/T")) == short_name:
            return float(annotation["/Rect"][0])
    raise AssertionError(short_name)


def test_g1650_keeps_applicant_and_account_holder_names_separate(tmp_path: Path):
    values = pdf_field_values(_generate(tmp_path))

    assert values[f"{APPLICANT}.GivenName[0]"] == {"Avery"}
    assert values[f"{APPLICANT}.FamilyName[0]"] == {"Parker"}
    assert values[f"{HOLDER}.GivenName[0]"] == {"Jordan"}
    assert values[f"{BANK}.RoutingNumber[0]"] == {SAMPLE_ROUTING}
    assert values[f"{BANK}.AccountNumber[0]"] == {SAMPLE_ACCOUNT}
    assert values[f"{BANK}.BankName[0]"] == {"Sample Community Bank"}
    assert values[f"{BANK}.AuthorizedPaymentAmt[0]"] == {"1440"}


def test_g1650_leaves_signature_blank(tmp_path: Path):
    values = pdf_field_values(_generate(tmp_path))
    assert values["SignatureOfApplicant[0]"] == {""}


@pytest.mark.parametrize(
    ("account_type", "field", "state", "printed_x"),
    [("checking", "CB_CreditCardType[1]", "/V", 39), ("savings", "CB_CreditCardType[0]", "/MC", 135)],
)
def test_g1650_account_type_checks_the_box_with_the_printed_label(
    tmp_path: Path, account_type: str, field: str, state: str, printed_x: int
):
    path = _generate(tmp_path, account_type=account_type)
    assert state in pdf_field_appearance_states(path)[field]
    assert round(_checkbox_x(path, field)) == printed_x


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"routing_number": "123456789"}, "routing_number"),
        ({"routing_number": "12345"}, "routing_number"),
        ({"account_number": "12"}, "account_number"),
        ({"account_type": "brokerage"}, "account_type"),
        ({"account_ownership": "business", "business_name": ""}, "business_name"),
        ({"account_holder_name": ""}, "account_holder_name"),
    ],
)
def test_g1650_rejects_invalid_bank_details(overrides: dict, message: str):
    with pytest.raises(ValueError, match=message):
        validate_g1650_payload(bank_payload(**overrides))


def test_g1650_rejects_cents_because_the_form_preprints_them(tmp_path: Path):
    with pytest.raises(ValueError, match="whole-dollar"):
        generate_g1650_pdf_from_payload(
            payload=bank_payload(),
            template_path=TEMPLATE,
            output_path=tmp_path / "g1650.pdf",
            amount_override="1440.50",
        )


def test_packet_request_rejects_two_payment_methods():
    card = {
        "cardholder_name": "Jordan Parker",
        "credit_card_type": "Visa",
        "credit_card_number": "4111111111111111",
        "expiration_month": "01",
        "expiration_year": "2030",
        "security_code": "123",
        "billing_address": {"street_1": "1 Main St", "city": "Oakland", "state": "CA", "postal_code": "94612"},
    }
    with pytest.raises(ValidationError, match="not both"):
        PacketAssemblyGenerateRequest(g1450_payment=card, g1650_payment=G1650BankDetailsWrite(**bank_payload()))


def test_packet_merges_one_g1650_per_fee_and_keeps_bank_details_out_of_manifest(tmp_path: Path):
    session = make_session()
    case = create_case(session)
    upsert_intake_step(
        session,
        case.id,
        "basics",
        {
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Parker",
            "petitioner_first_name": "Jordan",
            "petitioner_last_name": "Parker",
        },
    )
    for sort_order, code in enumerate(("form_i485", "form_i765", "form_i131")):
        add_checklist_item(session, case, code, sort_order)
    session.commit()

    result = assemble_packet_pdf(
        session=session,
        case_id=case.id,
        state_code="CA",
        g1650_payment_payload=bank_payload(),
        g1650_template_path=TEMPLATE,
        output_dir=tmp_path,
    )

    payments = [document for document in result.included_documents if document["form_key"] == "g1650"]
    assert [document["checklist_item_code"] for document in payments] == ["form_i485", "form_i765", "form_i131"]
    assert all(document["label"].startswith("Form G-1650 payment") for document in payments)
    amounts = {
        path.name.split("-g-1650")[0][-5:]: next(
            iter(pdf_field_values(path)[f"{BANK}.AuthorizedPaymentAmt[0]"])
        )
        for path in tmp_path.glob("*-g-1650.pdf")
    }
    assert sorted(amounts.values()) == ["1440", "260", "630"]
    manifest = result.manifest_path.read_text()
    assert SAMPLE_ACCOUNT not in manifest
    assert SAMPLE_ROUTING not in manifest
    cover_text = " ".join((page.extract_text() or "") for page in PdfReader(result.output_path).pages[:2])
    assert "G-1650" in cover_text
    assert "G-1450" not in cover_text
    assert SAMPLE_ACCOUNT not in json.dumps(
        [entry.details for entry in session.exec(select(AuditLog))], default=str
    )


@pytest.mark.parametrize(
    ("code", "fee"),
    [("form_i130", "675.00"), ("form_i485", "1440.00"), ("form_i765", "260.00"), ("form_i131", "630.00")],
)
def test_fee_table_matches_verified_g1055_edition(code: str, fee: str):
    assert FEE_SCHEDULE_EDITION == "10/26/26"
    assert G1450_FORM_FEES[code]["paper_fee"] == fee


def test_every_location_has_a_mailing_recommendation_with_verification_date():
    for location in LOCKBOX_BY_LOCATION:
        recommendation = mailing_recommendation_for_location(location)
        assert recommendation["verified_on"] == "2026-11-01"
        assert "Oct. 7, 2026" in recommendation["note"]
