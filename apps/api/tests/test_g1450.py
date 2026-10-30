from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.api import routes
from app.db.session import get_session
from app.main import app
from app.models.entities import CaseChecklistItem, CaseRecord
from app.schemas.common import G1450CardDetailsWrite, PacketAssemblyGenerateRequest
from app.services.g1450 import (
    generate_case_g1450_packet,
    generate_case_g1450_packet_from_payload,
    generate_g1450_pdf,
    get_case_g1450_payment_options,
)
from app.services.intake import upsert_intake_step


REPO_ROOT = Path(__file__).resolve().parents[3]
G1450_TEMPLATE = REPO_ROOT / "blank-immigration-documents" / "g-1450.pdf"

BENEFICIARY_INTAKE = {
    "beneficiary_first_name": "Avery",
    "beneficiary_middle_name": "Maria",
    "beneficiary_last_name": "Sample",
    "petitioner_first_name": "Jordan",
    "petitioner_middle_name": "Taylor",
    "petitioner_last_name": "Petitioner",
}

PAYMENT_PAYLOAD = {
    "cardholder_name": "Jordan Taylor Petitioner",
    "credit_card_type": "Visa",
    "credit_card_number": "4111111111111111",
    "expiration_month": "8",
    "expiration_year": "2028",
    "security_code": "123",
    "billing_address": {
        "street_1": "123 Example St",
        "street_2": "Apt 4B",
        "city": "Los Angeles",
        "state": "CA",
        "postal_code": "90001",
    },
    "daytime_phone_number": "0000000123",
    "authorized_amount": "1.00",
}


def require_g1450_template() -> Path:
    if not G1450_TEMPLATE.exists():
        pytest.skip("Local G-1450 template is not included in blank-immigration-documents.")
    return G1450_TEMPLATE


def _checklist_item(case_id, code: str, sort_order: int = 0) -> CaseChecklistItem:
    return CaseChecklistItem(
        case_id=case_id,
        code=code,
        category="forms",
        label=code,
        applicability="required",
        owner_role="shared",
        description="test",
        why_needed="test",
        sort_order=sort_order,
    )


def _page_field_value(reader: PdfReader, field_name: str) -> str | None:
    for page in reader.pages:
        for annotation_ref in page.get("/Annots") or []:
            annotation = annotation_ref.get_object()
            if annotation.get("/T") == field_name:
                return annotation.get("/V")
    return None


def _create_engine():
    return create_engine("sqlite://", connect_args={"check_same_thread": False})


def _seed_payment_case(
    session: Session,
    *,
    codes: list[str],
    case_name: str = "Payment regression test",
) -> CaseRecord:
    case = CaseRecord(case_name=case_name)
    session.add(case)
    session.commit()
    session.refresh(case)
    for index, code in enumerate(codes):
        session.add(_checklist_item(case.id, code, sort_order=index))
    upsert_intake_step(session, case.id, "baseline", BENEFICIARY_INTAKE)
    session.commit()
    return case


def test_generate_g1450_pdf_from_card_json(tmp_path: Path):
    card_json = tmp_path / "card.json"
    output = tmp_path / "generated-g1450.pdf"
    card_json.write_text(
        json.dumps(
            {
                "cardholder_name": "Jane Q Example",
                "credit_card_type": "Visa",
                "credit_card_number": "4111111111111111",
                "expiration_month": "8",
                "expiration_year": "2028",
                "security_code": "123",
                "billing_address": {
                    "street_1": "123 Example St",
                    "street_2": "Apt 4B",
                    "city": "Los Angeles",
                    "state": "CA",
                    "postal_code": "90001",
                },
                "daytime_phone_number": "0000000123",
                "authorized_amount": "675.00",
                "applicant_name": "Jane Q Example",
            }
        ),
        encoding="utf-8",
    )

    result = generate_g1450_pdf(
        card_json_path=card_json,
        template_path=require_g1450_template(),
        output_path=output,
    )

    reader = PdfReader(result.output_path)

    assert result.authorized_amount == "675.00"
    assert _page_field_value(reader, "FamilyName[0]") == "Example"
    assert _page_field_value(reader, "GivenName[0]") == "Jane"
    assert _page_field_value(reader, "MiddleName[0]") == "Q"
    assert _page_field_value(reader, "CCHolderGivenName[0]") == "Jane"
    assert _page_field_value(reader, "CreditCardNumber_1[0]") == "4111"
    assert _page_field_value(reader, "AuthorizedPaymentAmt[0]") == "675"
    assert _page_field_value(reader, "SignatureOfApplicant[0]") in {None, ""}


def test_generate_case_g1450_packet_uses_applicable_payable_forms(tmp_path: Path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    card_json = tmp_path / "card.json"
    card_json.write_text(
        json.dumps(
            {
                "cardholder_name": "Jane Q Example",
                "credit_card_type": "Visa",
                "credit_card_number": "4111111111111111",
                "expiration_month": "8",
                "expiration_year": "2028",
                "security_code": "123",
                "billing_address": {
                    "street_1": "123 Example St",
                    "street_2": "Apt 4B",
                    "city": "Los Angeles",
                    "state": "CA",
                    "postal_code": "90001",
                },
                "daytime_phone_number": "0000000123",
                "authorized_amount": "1.00",
                "signature_name": "Jane Q Example",
            }
        ),
        encoding="utf-8",
    )
    with Session(engine) as session:
        case = CaseRecord(case_name="Payment test")
        session.add(case)
        session.commit()
        session.refresh(case)
        for index, code in enumerate(["form_i130", "form_i485", "form_i765", "form_i864"]):
            session.add(
                CaseChecklistItem(
                    case_id=case.id,
                    code=code,
                    category="forms",
                    label=code,
                    applicability="required",
                    owner_role="shared",
                    description="test",
                    why_needed="test",
                    sort_order=index,
                )
            )
        upsert_intake_step(
            session,
            case.id,
            "baseline",
            {
                "beneficiary_first_name": "Avery",
                "beneficiary_middle_name": "Maria",
                "beneficiary_last_name": "Sample",
                "petitioner_first_name": "Jordan",
                "petitioner_middle_name": "Taylor",
                "petitioner_last_name": "Petitioner",
            },
        )
        session.commit()

        packet = generate_case_g1450_packet(
            session=session,
            case_id=case.id,
            card_json_path=card_json,
            template_path=require_g1450_template(),
            output_dir=tmp_path,
        )

    generated_by_form = {result.form_code: result for result in packet.generated}
    assert packet.total_authorized_amount == "2375.00"
    assert generated_by_form["I-130"].authorized_amount == "675.00"
    assert generated_by_form["I-485"].authorized_amount == "1440.00"
    assert generated_by_form["I-765"].authorized_amount == "260.00"
    assert {item["form_code"] for item in packet.skipped} == {"I-864"}
    for result in packet.generated:
        assert result.output_path.exists()

    i130_reader = PdfReader(generated_by_form["I-130"].output_path)
    assert _page_field_value(i130_reader, "FamilyName[0]") == "Petitioner"
    assert _page_field_value(i130_reader, "GivenName[0]") == "Jordan"
    assert _page_field_value(i130_reader, "MiddleName[0]") == "Taylor"

    i485_reader = PdfReader(generated_by_form["I-485"].output_path)
    assert _page_field_value(i485_reader, "FamilyName[0]") == "Sample"
    assert _page_field_value(i485_reader, "GivenName[0]") == "Avery"
    assert _page_field_value(i485_reader, "MiddleName[0]") == "Maria"
    assert _page_field_value(i485_reader, "SignatureOfApplicant[0]") in {None, ""}


def test_generate_case_g1450_packet_defaults_applicant_name_to_beneficiary(tmp_path: Path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        case = CaseRecord(case_name="Payment beneficiary name test")
        session.add(case)
        session.commit()
        session.refresh(case)
        session.add(_checklist_item(case.id, "form_i485"))
        upsert_intake_step(
            session,
            case.id,
            "baseline",
            {
                "beneficiary_first_name": "Avery",
                "beneficiary_middle_name": "Maria",
                "beneficiary_last_name": "Sample",
                "petitioner_first_name": "Jordan",
                "petitioner_middle_name": "Taylor",
                "petitioner_last_name": "Petitioner",
            },
        )
        session.commit()

        packet = generate_case_g1450_packet_from_payload(
            session=session,
            case_id=case.id,
            payload={
                "cardholder_name": "Jordan Taylor Petitioner",
                "credit_card_type": "Visa",
                "credit_card_number": "4111111111111111",
                "expiration_month": "8",
                "expiration_year": "2028",
                "security_code": "123",
                "billing_address": {
                    "street_1": "123 Example St",
                    "street_2": "Apt 4B",
                    "city": "Los Angeles",
                    "state": "CA",
                    "postal_code": "90001",
                },
                "daytime_phone_number": "0000000123",
                "authorized_amount": "1.00",
                "signature_name": "Jordan Taylor Petitioner",
            },
            template_path=require_g1450_template(),
            output_dir=tmp_path,
        )

    generated = packet.generated[0]
    reader = PdfReader(generated.output_path)
    assert _page_field_value(reader, "FamilyName[0]") == "Sample"
    assert _page_field_value(reader, "GivenName[0]") == "Avery"
    assert _page_field_value(reader, "MiddleName[0]") == "Maria"
    assert _page_field_value(reader, "CCHolderGivenName[0]") == "Jordan"
    assert _page_field_value(reader, "CCHolderMiddleName[0]") == "Taylor"
    assert _page_field_value(reader, "SignatureOfApplicant[0]") in {None, ""}


def test_case_g1450_generation_overrides_stale_signature_for_all_beneficiary_forms(tmp_path: Path):
    engine = _create_engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        case = _seed_payment_case(
            session,
            codes=["form_i485", "form_i765", "form_i131"],
            case_name="Beneficiary payment form regression test",
        )

        packet = generate_case_g1450_packet_from_payload(
            session=session,
            case_id=case.id,
            payload={
                **PAYMENT_PAYLOAD,
                "signature_name": "Jordan Taylor Petitioner",
                "applicant_name": "Jordan Taylor Petitioner",
            },
            template_path=require_g1450_template(),
            output_dir=tmp_path,
        )

    assert {result.form_code for result in packet.generated} == {"I-485", "I-765", "I-131"}
    for result in packet.generated:
        reader = PdfReader(result.output_path)
        assert _page_field_value(reader, "FamilyName[0]") == "Sample"
        assert _page_field_value(reader, "GivenName[0]") == "Avery"
        assert _page_field_value(reader, "MiddleName[0]") == "Maria"
        assert _page_field_value(reader, "CCHolderFamilyName[0]") == "Petitioner"
        assert _page_field_value(reader, "CCHolderGivenName[0]") == "Jordan"
        assert _page_field_value(reader, "CCHolderMiddleName[0]") == "Taylor"
        assert _page_field_value(reader, "SignatureOfApplicant[0]") in {None, ""}


def test_case_g1450_generation_uses_petitioner_for_i130_even_with_beneficiary_applicant_payload(tmp_path: Path):
    engine = _create_engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        case = _seed_payment_case(
            session,
            codes=["form_i130"],
            case_name="Petitioner payment form regression test",
        )

        packet = generate_case_g1450_packet_from_payload(
            session=session,
            case_id=case.id,
            payload={
                **PAYMENT_PAYLOAD,
                "applicant_name": "Avery Maria Sample",
                "signature_name": "Avery Maria Sample",
            },
            template_path=require_g1450_template(),
            output_dir=tmp_path,
        )

    assert len(packet.generated) == 1
    assert packet.generated[0].form_code == "I-130"
    reader = PdfReader(packet.generated[0].output_path)
    assert _page_field_value(reader, "FamilyName[0]") == "Petitioner"
    assert _page_field_value(reader, "GivenName[0]") == "Jordan"
    assert _page_field_value(reader, "MiddleName[0]") == "Taylor"
    assert _page_field_value(reader, "CCHolderFamilyName[0]") == "Petitioner"
    assert _page_field_value(reader, "CCHolderGivenName[0]") == "Jordan"
    assert _page_field_value(reader, "SignatureOfApplicant[0]") in {None, ""}


def test_g1450_card_payload_contract_does_not_accept_signature_name():
    payload = G1450CardDetailsWrite.model_validate(
        {
            **PAYMENT_PAYLOAD,
            "signature_name": "Jordan Taylor Petitioner",
        }
    )

    assert "signature_name" not in payload.model_dump()


def test_packet_assembly_payment_payload_contract_does_not_accept_signature_name():
    request = PacketAssemblyGenerateRequest.model_validate(
        {
            "state_code": "CA",
            "carrier": "usps",
            "g1450_payment": {
                **PAYMENT_PAYLOAD,
                "signature_name": "Jordan Taylor Petitioner",
            },
            "g1450_selected_checklist_codes": ["form_i485"],
        }
    )

    assert request.g1450_payment is not None
    assert "signature_name" not in request.g1450_payment.model_dump()


def test_g1450_generate_endpoint_ignores_signature_name_and_uses_beneficiary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    require_g1450_template()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    session = Session(engine)

    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    monkeypatch.setattr(routes, "GENERATED_PDF_DIR", tmp_path)
    try:
        case = _seed_payment_case(
            session,
            codes=["form_i485"],
            case_name="Payment generation endpoint regression test",
        )

        response = TestClient(app).post(
            f"/api/v1/cases/{case.id}/g1450/generate",
            json={
                **PAYMENT_PAYLOAD,
                "signature_name": "Jordan Taylor Petitioner",
                "selected_checklist_codes": ["form_i485"],
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["generated"][0]["form_code"] == "I-485"
        generated_path = Path(payload["generated"][0]["generated_pdf"])
        assert generated_path.parent == tmp_path

        reader = PdfReader(generated_path)
        assert _page_field_value(reader, "FamilyName[0]") == "Sample"
        assert _page_field_value(reader, "GivenName[0]") == "Avery"
        assert _page_field_value(reader, "MiddleName[0]") == "Maria"
        assert _page_field_value(reader, "CCHolderGivenName[0]") == "Jordan"
        assert _page_field_value(reader, "SignatureOfApplicant[0]") in {None, ""}
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_g1450_payment_options_include_payable_and_zero_fee_forms():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        case = CaseRecord(case_name="Payment option test")
        session.add(case)
        session.commit()
        session.refresh(case)
        for index, code in enumerate(["form_i130", "form_i485", "form_i864"]):
            session.add(
                CaseChecklistItem(
                    case_id=case.id,
                    code=code,
                    category="forms",
                    label=code,
                    applicability="required",
                    owner_role="shared",
                    description="test",
                    why_needed="test",
                    sort_order=index,
                )
            )
        session.commit()

        options = get_case_g1450_payment_options(session, case.id)

    by_code = {option.checklist_code: option for option in options}
    assert by_code["form_i130"].is_payable is True
    assert by_code["form_i130"].paper_fee == "675.00"
    assert by_code["form_i864"].is_payable is False
    assert by_code["form_i864"].paper_fee == "0.00"


def test_g1450_payment_options_endpoint_returns_case_options():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    session = Session(engine)

    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        case = CaseRecord(case_name="Payment endpoint test")
        session.add(case)
        session.commit()
        session.refresh(case)
        session.add(_checklist_item(case.id, "form_i130"))
        session.commit()

        response = TestClient(app).get(f"/api/v1/cases/{case.id}/g1450/payment-options")

        assert response.status_code == 200
        payload = response.json()
        assert payload["case_id"] == str(case.id)
        assert payload["options"][0]["checklist_code"] == "form_i130"
        assert payload["options"][0]["paper_fee"] == "675.00"
        assert isinstance(payload["template_exists"], bool)
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_generate_case_g1450_packet_can_skip_unselected_forms_without_template(tmp_path: Path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        case = CaseRecord(case_name="Selected payment test")
        session.add(case)
        session.commit()
        session.refresh(case)
        for index, code in enumerate(["form_i130", "form_i485", "form_i864"]):
            session.add(
                CaseChecklistItem(
                    case_id=case.id,
                    code=code,
                    category="forms",
                    label=code,
                    applicability="required",
                    owner_role="shared",
                    description="test",
                    why_needed="test",
                    sort_order=index,
                )
            )
        session.commit()

        packet = generate_case_g1450_packet_from_payload(
            session=session,
            case_id=case.id,
            payload={
                "cardholder_name": "Jane Q Example",
                "credit_card_type": "Visa",
                "credit_card_number": "4111111111111111",
                "expiration_month": "8",
                "expiration_year": "2028",
                "security_code": "123",
                "billing_address": {
                    "street_1": "123 Example St",
                    "street_2": "Apt 4B",
                    "city": "Los Angeles",
                    "state": "CA",
                    "postal_code": "90001",
                },
            },
            template_path=tmp_path / "missing-g-1450.pdf",
            output_dir=tmp_path,
            selected_checklist_codes=["form_i864"],
        )

    assert packet.generated == []
    assert packet.total_authorized_amount == "0.00"
    assert [item["form_code"] for item in packet.skipped] == ["I-864"]


def test_generate_case_g1450_packet_rejects_selected_forms_not_applicable(tmp_path: Path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        case = CaseRecord(case_name="Missing payment form test")
        session.add(case)
        session.commit()
        session.refresh(case)
        session.add(
            CaseChecklistItem(
                case_id=case.id,
                code="form_i130",
                category="forms",
                label="form_i130",
                applicability="required",
                owner_role="shared",
                description="test",
                why_needed="test",
                sort_order=0,
            )
        )
        session.commit()

        with pytest.raises(ValueError, match="not applicable"):
            generate_case_g1450_packet_from_payload(
                session=session,
                case_id=case.id,
                payload={
                    "cardholder_name": "Jane Q Example",
                    "credit_card_type": "Visa",
                    "credit_card_number": "4111111111111111",
                    "expiration_month": "8",
                    "expiration_year": "2028",
                    "security_code": "123",
                    "billing_address": {
                        "street_1": "123 Example St",
                        "city": "Los Angeles",
                        "state": "CA",
                        "postal_code": "90001",
                    },
                },
                template_path=tmp_path / "missing-g-1450.pdf",
                output_dir=tmp_path,
                selected_checklist_codes=["form_i131"],
            )
