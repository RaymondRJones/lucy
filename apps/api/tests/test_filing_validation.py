from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.content.i485_questionnaire import I485_VERIFIED_ON
from app.db.session import get_session
from app.main import app
from app.models.entities import CaseRecord, QAIssue, UploadedDocument
from app.services.filing_validation import validate_case_filings
from app.services.family_pdf import build_i130_pdf_field_payload, build_i130a_pdf_field_payload
from app.services.form_ingestion import save_form_page_answers
from app.services.i485 import import_i485_answers_from_upload, save_i485_page_answers
from app.services.intake import upsert_intake_step


I130_TEMPLATE_PATH = Path("blank-immigration-documents/i-130.pdf")
I130A_TEMPLATE_PATH = Path("blank-immigration-documents/i-130a.pdf")


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def create_case(session: Session) -> CaseRecord:
    case = CaseRecord(case_name="Filing validation case", workflow_type="marriage_concurrent")
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


def make_client_session() -> tuple[TestClient, Session]:
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
    return TestClient(app), session


def issue_codes(report: dict) -> set[str]:
    return {issue["code"] for form in report["forms"] for issue in form["issues"]}


def pdf_field_names(path: Path) -> set[str]:
    reader = PdfReader(path)
    names: set[str] = set()
    for name, field in (reader.get_fields() or {}).items():
        names.add(str(name))
        field_name = field.get("/T")
        if field_name:
            names.add(str(field_name))
    return names


def test_filing_validation_default_scope_is_non_persistent_preflight():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {
            "petitioner_first_name": "Jordan",
            "petitioner_last_name": "Petitioner",
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Garcia",
        },
    )
    session.commit()

    report = validate_case_filings(
        session,
        case.id,
        template_paths={
            "form_i485": "missing-template.pdf",
            "form_i864": "missing-template.pdf",
        },
    )
    persisted_issues = list(session.exec(select(QAIssue).where(QAIssue.case_id == case.id)))

    assert report["validation_scope"] == ["form_i485", "form_i864"]
    assert [form["form_code"] for form in report["forms"]] == ["form_i485", "form_i864"]
    assert report["summary"]["form_count"] == 2
    assert report["summary"]["status"] == "blocked"
    assert set(report["summary"]["blocking_forms"]) == {"form_i485", "form_i864"}
    assert persisted_issues == []


def test_filing_validation_reports_unknown_requested_form_as_roadmap_issue():
    session = make_session()
    case = create_case(session)

    report = validate_case_filings(
        session,
        case.id,
        form_codes=["form_i999"],
        template_paths={"form_i999": "missing-template.pdf"},
    )

    form = report["forms"][0]
    assert report["validation_scope"] == ["form_i999"]
    assert report["summary"]["status"] == "needs_review"
    assert form["form_code"] == "form_i999"
    assert form["metadata"]["validator_level"] == "roadmap_only"
    assert form["issues"][0]["code"] == "form_i999_validator_not_implemented"
    assert any(item["form_code"] == "form_i999" and item["status"] == "unknown" for item in report["roadmap"])


def test_filing_validation_flags_low_confidence_i485_imported_answers():
    session = make_session()
    case = create_case(session)
    upload = UploadedDocument(
        case_id=case.id,
        checklist_item_code="form_i485",
        original_filename="I-485.pdf",
        stored_filename="I-485.pdf",
        mime_type="application/pdf",
        file_size=1234,
        upload_status="confirmed",
        document_type="form_i485",
        document_language="english",
        extraction_confidence=0.42,
        extracted_fields={
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Garcia",
            "beneficiary_date_of_birth": "2001-11-23",
        },
    )
    session.add(upload)
    session.commit()

    import_i485_answers_from_upload(session, case.id, upload.id)
    session.commit()

    report = validate_case_filings(
        session,
        case.id,
        form_codes=["form_i485"],
        template_paths={"form_i485": "missing-template.pdf"},
    )

    codes = issue_codes(report)
    assert "form_i485_beneficiary_first_name_low_confidence" in codes
    assert "form_i485_beneficiary_last_name_low_confidence" in codes
    assert report["forms"][0]["metadata"]["answer_source_count"] >= 3


def test_filing_validation_reports_missing_i485_required_answers():
    session = make_session()
    case = create_case(session)
    save_i485_page_answers(
        session,
        case.id,
        "page_08_marriage_spouse",
        {
            "petitioner_first_name": "Jordan",
            "petitioner_last_name": "Petitioner",
            "petitioner_citizenship_status": "us_citizen",
            "beneficiary_marriage_count": 1,
            "beneficiary_current_marital_status": "married",
        },
    )
    session.commit()

    report = validate_case_filings(
        session,
        case.id,
        form_codes=["form_i485"],
        template_paths={"form_i485": "missing-template.pdf"},
    )

    codes = issue_codes(report)

    assert report["summary"]["status"] == "blocked"
    assert "form_i485_beneficiary_last_name_missing_required" in codes
    assert report["forms"][0]["source"]["verified_on"] == I485_VERIFIED_ON


def test_filing_validation_inspects_default_blank_i485_pdf_fields():
    session = make_session()
    case = create_case(session)

    report = validate_case_filings(session, case.id, form_codes=["form_i485"])

    assert report["forms"][0]["template_path"] == "blank-immigration-documents/i-485.pdf"
    assert report["forms"][0]["template_field_count"] > 0


def test_filing_validation_flags_recent_i485_address_without_prior_history():
    session = make_session()
    case = create_case(session)
    save_i485_page_answers(
        session,
        case.id,
        "page_04_addresses_ssn",
        {
            "beneficiary_current_address_line1": "385 14th St",
            "beneficiary_current_city": "Oakland",
            "beneficiary_current_state": "CA",
            "beneficiary_current_zip": "94612",
            "beneficiary_address_since": (date.today() - timedelta(days=30)).isoformat(),
            "beneficiary_current_address_five_years": False,
            "beneficiary_has_ssn": False,
        },
    )
    session.commit()

    report = validate_case_filings(
        session,
        case.id,
        form_codes=["form_i485"],
        template_paths={"form_i485": "missing-template.pdf"},
    )

    assert "form_i485_five_year_address_history_missing" in issue_codes(report)


def test_filing_validation_flags_i485_source_of_truth_mismatch():
    session = make_session()
    case = create_case(session)
    save_i485_page_answers(
        session,
        case.id,
        "page_01_identity",
        {
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Garcia",
            "beneficiary_date_of_birth": "2001-11-23",
            "beneficiary_used_other_dob": False,
        },
    )
    upsert_intake_step(session, case.id, "baseline", {"beneficiary_first_name": "Lara"})
    session.commit()

    report = validate_case_filings(
        session,
        case.id,
        form_codes=["form_i485"],
        template_paths={"form_i485": "missing-template.pdf"},
    )

    assert "form_i485_beneficiary_first_name_source_of_truth_mismatch" in issue_codes(report)


def test_filing_validation_reports_i864_income_gap():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {
            "petitioner_first_name": "Jordan",
            "petitioner_last_name": "Petitioner",
            "petitioner_current_address": "123 Sample Street, Example City, CA 90000",
            "employment_status": "employed",
            "household_size": 2,
        },
    )
    session.commit()

    report = validate_case_filings(
        session,
        case.id,
        form_codes=["form_i864"],
        template_paths={"form_i864": "missing-template.pdf"},
    )

    assert report["forms"][0]["metadata"]["validator_level"] == "sponsor_preflight"
    assert "form_i864_annual_income_missing_required" in issue_codes(report)


def test_filing_validation_flags_i864_income_below_i864p_threshold():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {
            "petitioner_first_name": "Jordan",
            "petitioner_last_name": "Petitioner",
            "petitioner_current_address": "123 Sample Street, Example City, CA 90000",
            "petitioner_current_state": "CA",
            "annual_income": 25000,
            "employment_status": "employed",
            "household_size": 2,
            "reviewed_current_fees": True,
        },
    )
    session.add(
        UploadedDocument(
            case_id=case.id,
            checklist_item_code="sponsor_tax_return",
            original_filename="tax-return.pdf",
            stored_filename="tax-return.pdf",
            mime_type="application/pdf",
            file_size=1234,
            upload_status="confirmed",
            document_type="tax_return",
            document_language="english",
        )
    )
    session.commit()

    report = validate_case_filings(
        session,
        case.id,
        form_codes=["form_i864"],
        template_paths={"form_i864": "missing-template.pdf"},
    )

    form = report["forms"][0]
    assert "form_i864_income_below_i864p_guideline" in issue_codes(report)
    assert form["metadata"]["i864p_version"] == "i864p-2025"
    assert form["metadata"]["i864p_required_income"] == 26437


def test_filing_validation_flags_missing_i864_tax_evidence():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {
            "petitioner_first_name": "Jordan",
            "petitioner_last_name": "Petitioner",
            "petitioner_current_state": "CA",
            "annual_income": 72000,
            "employment_status": "employed",
            "household_size": 2,
            "reviewed_current_fees": True,
        },
    )
    session.commit()

    report = validate_case_filings(
        session,
        case.id,
        form_codes=["form_i864"],
        template_paths={"form_i864": "missing-template.pdf"},
    )

    assert "form_i864_tax_evidence_missing_required" in issue_codes(report)


def test_filing_validation_validates_optional_g1145_contact_fields():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Garcia",
            "beneficiary_email": "not-an-email",
        },
    )
    session.commit()

    report = validate_case_filings(
        session,
        case.id,
        form_codes=["form_g1145"],
        template_paths={"form_g1145": "missing-template.pdf"},
    )

    form = report["forms"][0]
    assert form["metadata"]["validator_level"] == "optional_e_notification_preflight"
    assert "form_g1145_email_invalid" in issue_codes(report)


def test_filing_validation_g1145_passes_with_name_and_contact():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Garcia",
            "beneficiary_email": "beneficiary.sample@example.com",
            "beneficiary_phone": "5105550101",
        },
    )
    session.commit()

    report = validate_case_filings(session, case.id, form_codes=["form_g1145"])

    assert report["summary"]["status"] == "passed"
    assert report["forms"][0]["template_path"] == "blank-immigration-documents/g-1145.pdf"
    assert report["forms"][0]["template_field_count"] >= 10


def test_filing_validation_i765_flags_missing_identity_and_evidence():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Garcia",
            "beneficiary_location": "usa",
            "beneficiary_entered_us_legally": True,
            "petitioner_citizenship_status": "us_citizen",
            "wants_i765": True,
        },
    )
    session.commit()

    report = validate_case_filings(
        session,
        case.id,
        form_codes=["form_i765"],
        template_paths={"form_i765": "missing-template.pdf"},
    )

    codes = issue_codes(report)
    assert report["forms"][0]["metadata"]["validator_level"] == "adjustment_pending_c9_preflight"
    assert "form_i765_beneficiary_date_of_birth_missing_required" in codes
    assert "form_i765_beneficiary_i94_evidence_missing_required" in codes


def test_filing_validation_i765_passes_with_core_facts_and_evidence():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Garcia",
            "beneficiary_date_of_birth": "2001-11-23",
            "beneficiary_country_of_birth": "CO",
            "beneficiary_country_of_citizenship": "CO",
            "beneficiary_current_immigration_status": "B2",
            "beneficiary_i94_number": "123456789A",
            "beneficiary_passport_number": "AB123456",
            "beneficiary_current_address": "123 Sample Street, Example City, CA 90000",
            "beneficiary_location": "usa",
            "beneficiary_entered_us_legally": True,
            "petitioner_citizenship_status": "us_citizen",
            "wants_i765": True,
        },
    )
    for checklist_code in ("beneficiary_i94", "beneficiary_passport_bio", "form_i485"):
        session.add(
            UploadedDocument(
                case_id=case.id,
                checklist_item_code=checklist_code,
                original_filename=f"{checklist_code}.pdf",
                stored_filename=f"{checklist_code}.pdf",
                mime_type="application/pdf",
                file_size=1234,
                upload_status="confirmed",
                document_type=checklist_code,
                document_language="english",
            )
        )
    session.commit()

    report = validate_case_filings(session, case.id, form_codes=["form_i765"])

    assert report["summary"]["status"] == "passed"
    assert report["forms"][0]["template_path"] == "blank-immigration-documents/i-765.pdf"
    assert report["forms"][0]["template_field_count"] > 0


def test_filing_validation_i131_flags_missing_travel_facts_and_evidence():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Garcia",
            "beneficiary_location": "usa",
            "beneficiary_entered_us_legally": True,
            "petitioner_citizenship_status": "us_citizen",
            "wants_i131": True,
        },
    )
    session.commit()

    report = validate_case_filings(
        session,
        case.id,
        form_codes=["form_i131"],
        template_paths={"form_i131": "missing-template.pdf"},
    )

    codes = issue_codes(report)
    assert report["forms"][0]["metadata"]["validator_level"] == "advance_parole_i485_preflight"
    assert "form_i131_i131_travel_purpose_missing_required" in codes
    assert "form_i131_beneficiary_i94_evidence_missing_required" in codes
    assert "form_i131_beneficiary_passport_bio_evidence_missing_required" in codes
    assert "form_i131_beneficiary_passport_photos_evidence_missing_required" in codes
    assert report["forms"][0]["source"]["questionnaire_version"] == "i131-01-20-25-local-v1"


def test_filing_validation_i131_passes_with_core_facts_and_evidence():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Garcia",
            "beneficiary_date_of_birth": "2001-11-23",
            "beneficiary_country_of_birth": "CO",
            "beneficiary_country_of_citizenship": "CO",
            "beneficiary_class_of_admission": "B-2",
            "beneficiary_i94_number": "123456789A",
            "beneficiary_current_address": "123 Sample Street, Example City, CA 90000",
            "beneficiary_location": "usa",
            "beneficiary_entered_us_legally": True,
            "petitioner_citizenship_status": "us_citizen",
            "wants_i131": True,
        },
    )
    save_form_page_answers(
        session,
        case.id,
        "i131",
        "i131_page_01_type_identity",
        {
            "i131_application_type": "advanced_parole_i485_pending",
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Garcia",
        },
    )
    save_form_page_answers(
        session,
        case.id,
        "i131",
        "i131_page_05_proposed_travel",
        {
            "i131_intended_departure_date": "2026-11-03",
            "i131_travel_purpose": "Visit family",
            "i131_countries_to_visit": "Colombia",
            "i131_expected_trip_length": 14,
        },
    )
    for checklist_code in (
        "beneficiary_i94",
        "beneficiary_passport_bio",
        "beneficiary_passport_photos",
        "travel_explanation_i131",
        "form_i485",
    ):
        session.add(
            UploadedDocument(
                case_id=case.id,
                checklist_item_code=checklist_code,
                original_filename=f"{checklist_code}.pdf",
                stored_filename=f"{checklist_code}.pdf",
                mime_type="application/pdf",
                file_size=1234,
                upload_status="confirmed",
                document_type=checklist_code,
                document_language="english",
            )
        )
    session.commit()

    report = validate_case_filings(session, case.id, form_codes=["form_i131"])

    assert report["summary"]["status"] == "passed"
    assert report["forms"][0]["template_path"] == "blank-immigration-documents/i-131.pdf"
    assert report["forms"][0]["template_field_count"] > 0
    assert report["forms"][0]["metadata"]["mapped_pdf_field_count"] > 0


def test_i130_pdf_payload_maps_core_simple_spouse_case_fields():
    payload = build_i130_pdf_field_payload(
        {
            "petitioner_first_name": "Jordan",
            "petitioner_last_name": "Petitioner",
            "petitioner_date_of_birth": "1990-01-02",
            "petitioner_country_of_birth": "United States",
            "petitioner_citizenship_status": "us_citizen",
            "beneficiary_a_number": "ANUMBER_SAMPLE_1",
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Garcia",
            "beneficiary_date_of_birth": "2001-11-23",
            "beneficiary_country_of_birth": "Colombia",
            "beneficiary_current_address_line1": "385 14th St",
            "beneficiary_current_city": "Oakland",
            "beneficiary_current_state": "CA",
            "beneficiary_current_zip": "94612",
            "beneficiary_location": "usa",
            "marriage_date": "2025-07-20",
            "first_marriage_for_both": True,
        },
        pdf_field_names(I130_TEMPLATE_PATH),
    )

    assert payload.form_code == "form_i130"
    assert payload.text_values["Pt2Line4b_GivenName[0]"] == "Jordan"
    assert payload.text_values["Pt4Line4b_GivenName[0]"] == "Avery"
    assert payload.text_values["Pt4Line1_AlienNumber[0]"] == "ANUMBER_SAMPLE_1"
    assert payload.text_values["Pt2Line18_DateOfMarriage[0]"] == "07/20/2025"
    assert payload.text_values["Pt2Line16_NumberofMarriages[0]"] == "1"
    assert payload.checkbox_values["Pt1Line1_Spouse[0]"] == "/Y"
    assert payload.checkbox_values["Pt2Line36_USCitizen[0]"] == "/Y"
    assert payload.checkbox_values["Pt4Line18_MaritalStatus[4]"] == "/M"
    assert payload.missing_template_fields == []


def test_i130a_pdf_payload_maps_core_spouse_biographic_fields():
    payload = build_i130a_pdf_field_payload(
        {
            "beneficiary_a_number": "ANUMBER_SAMPLE_1",
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Garcia",
            "beneficiary_current_address_line1": "385 14th St",
            "beneficiary_current_city": "Oakland",
            "beneficiary_current_state": "CA",
            "beneficiary_current_zip": "94612",
            "beneficiary_address_since": "2025-08-01",
            "beneficiary_current_employer_or_school": "Laney College",
            "beneficiary_current_occupation": "Student",
            "beneficiary_current_employment_from": "2024-01-01",
            "beneficiary_phone": "5105550101",
            "beneficiary_email": "beneficiary.sample@example.com",
            "beneficiary_prior_address_history": [
                {
                    "line1": "10 Calle 1",
                    "city": "Bogota",
                    "province": "Bogota",
                    "postal_code": "110111",
                    "country": "Colombia",
                    "from": "2020-01-01",
                    "to": "2025-08-01",
                }
            ],
        },
        pdf_field_names(I130A_TEMPLATE_PATH),
    )

    assert payload.form_code == "form_i130a"
    assert payload.text_values["Pt1Line3b_GivenName[0]"] == "Avery"
    assert payload.text_values["Pt1Line5a_DateFrom[0]"] == "08/01/2025"
    assert payload.text_values["Pt2Line1_EmployerOrCompName[0]"] == "Laney College"
    assert payload.text_values["Pt1Line7a_DateFrom[0]"] == "01/01/2020"
    assert payload.text_values["Pt4Line5_Email[0]"] == "beneficiary.sample@example.com"
    assert payload.checkbox_values == {}
    assert payload.missing_template_fields == []


def test_filing_validation_i130_flags_missing_relationship_evidence():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {
            "petitioner_first_name": "Jordan",
            "petitioner_last_name": "Petitioner",
            "petitioner_date_of_birth": "1990-01-02",
            "petitioner_country_of_birth": "United States",
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Garcia",
            "beneficiary_date_of_birth": "2001-11-23",
            "beneficiary_country_of_birth": "CO",
            "beneficiary_current_address": "123 Sample Street, Example City, CA 90000",
            "beneficiary_current_marital_status": "married",
            "beneficiary_marriage_count": 1,
            "marriage_date": "2025-07-20",
            "first_marriage_for_both": True,
            "petitioner_citizenship_status": "us_citizen",
        },
    )
    session.commit()

    report = validate_case_filings(session, case.id, form_codes=["form_i130"])

    codes = issue_codes(report)
    form = report["forms"][0]
    assert report["forms"][0]["metadata"]["validator_level"] == "relationship_petition_preflight"
    assert "form_i130_petitioner_citizenship_proof_evidence_missing_required" in codes
    assert "form_i130_marriage_certificate_evidence_missing_required" in codes
    template_path = report["forms"][0]["template_path"]
    assert template_path is None or template_path.lower().endswith("i-130.pdf")
    if template_path:
        assert form["template_field_count"] > 0
        assert form["metadata"]["mapped_pdf_field_count"] > 0
        assert form["metadata"]["missing_template_fields"] == []


def test_filing_validation_i130_passes_with_core_facts_and_evidence():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {
            "petitioner_first_name": "Jordan",
            "petitioner_last_name": "Petitioner",
            "petitioner_date_of_birth": "1990-01-02",
            "petitioner_country_of_birth": "United States",
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Garcia",
            "beneficiary_date_of_birth": "2001-11-23",
            "beneficiary_country_of_birth": "CO",
            "beneficiary_current_address": "123 Sample Street, Example City, CA 90000",
            "beneficiary_current_marital_status": "married",
            "beneficiary_marriage_count": 1,
            "marriage_date": "2025-07-20",
            "first_marriage_for_both": True,
            "petitioner_citizenship_status": "us_citizen",
        },
    )
    for checklist_code in ("petitioner_citizenship_proof", "marriage_certificate"):
        session.add(
            UploadedDocument(
                case_id=case.id,
                checklist_item_code=checklist_code,
                original_filename=f"{checklist_code}.pdf",
                stored_filename=f"{checklist_code}.pdf",
                mime_type="application/pdf",
                file_size=1234,
                upload_status="confirmed",
                document_type=checklist_code,
                document_language="english",
            )
        )
    session.commit()

    report = validate_case_filings(session, case.id, form_codes=["form_i130"])

    assert report["summary"]["status"] == "passed"
    assert report["forms"][0]["source"]["questionnaire_version"] == "i130-04-01-24-marriage-v1"
    assert report["forms"][0]["metadata"]["questionnaire_version"] == "i130-04-01-24-marriage-v1"
    assert report["forms"][0]["metadata"]["mapped_pdf_field_count"] > 0
    assert report["forms"][0]["metadata"]["missing_template_fields"] == []


def test_filing_validation_i130_flags_cross_form_i485_mismatch():
    session = make_session()
    case = create_case(session)
    save_i485_page_answers(
        session,
        case.id,
        "page_01_identity",
        {
            "beneficiary_first_name": "Lara",
            "beneficiary_last_name": "Garcia",
            "beneficiary_date_of_birth": "2001-11-23",
        },
    )
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {
            "petitioner_first_name": "Jordan",
            "petitioner_last_name": "Petitioner",
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Garcia",
            "beneficiary_date_of_birth": "2001-11-23",
            "marriage_date": "2025-07-20",
            "first_marriage_for_both": True,
            "petitioner_citizenship_status": "us_citizen",
        },
    )
    for checklist_code in ("petitioner_citizenship_proof", "marriage_certificate"):
        session.add(
            UploadedDocument(
                case_id=case.id,
                checklist_item_code=checklist_code,
                original_filename=f"{checklist_code}.pdf",
                stored_filename=f"{checklist_code}.pdf",
                mime_type="application/pdf",
                file_size=1234,
                upload_status="confirmed",
                document_type=checklist_code,
                document_language="english",
            )
        )
    session.commit()

    report = validate_case_filings(session, case.id, form_codes=["form_i130"])

    assert "form_i130_beneficiary_first_name_cross_form_mismatch" in issue_codes(report)


def test_filing_validation_i130_flags_uploaded_form_extraction_mismatch():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {
            "petitioner_first_name": "Jordan",
            "petitioner_last_name": "Petitioner",
            "petitioner_date_of_birth": "1990-01-02",
            "petitioner_country_of_birth": "United States",
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Garcia",
            "beneficiary_date_of_birth": "2001-11-23",
            "beneficiary_country_of_birth": "CO",
            "beneficiary_current_address": "123 Sample Street, Example City, CA 90000",
            "beneficiary_current_marital_status": "married",
            "beneficiary_marriage_count": 1,
            "marriage_date": "2025-07-20",
            "first_marriage_for_both": True,
            "petitioner_citizenship_status": "us_citizen",
        },
    )
    for checklist_code in ("form_i130", "petitioner_citizenship_proof", "marriage_certificate"):
        session.add(
            UploadedDocument(
                case_id=case.id,
                checklist_item_code=checklist_code,
                original_filename=f"{checklist_code}.pdf",
                stored_filename=f"{checklist_code}.pdf",
                mime_type="application/pdf",
                file_size=1234,
                upload_status="confirmed",
                document_type=checklist_code,
                document_language="english",
                extracted_fields={"beneficiary_first_name": "Lara"} if checklist_code == "form_i130" else {},
            )
        )
    session.commit()

    report = validate_case_filings(session, case.id, form_codes=["form_i130"])

    assert "form_i130_beneficiary_first_name_uploaded_document_mismatch" in issue_codes(report)


def test_filing_validation_i130a_flags_missing_biographic_history():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Garcia",
            "beneficiary_date_of_birth": "2001-11-23",
            "beneficiary_country_of_birth": "CO",
        },
    )
    session.commit()

    report = validate_case_filings(session, case.id, form_codes=["form_i130a"])

    codes = issue_codes(report)
    assert report["forms"][0]["metadata"]["validator_level"] == "spouse_biographic_preflight"
    assert "form_i130a_beneficiary_employment_history_missing_required" in codes
    assert "form_i130a_current_address_missing_required" in codes
    assert report["forms"][0]["template_path"].lower().endswith("i-130a.pdf")
    assert report["forms"][0]["metadata"]["mapped_pdf_field_count"] > 0
    assert report["forms"][0]["metadata"]["missing_template_fields"] == []


def test_filing_validation_i130a_passes_with_core_biographic_facts():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Garcia",
            "beneficiary_date_of_birth": "2001-11-23",
            "beneficiary_country_of_birth": "CO",
            "beneficiary_current_marital_status": "married",
            "beneficiary_current_employer_or_school": "Student",
            "beneficiary_employment_history": "Student from 2020-present",
            "beneficiary_current_address": "123 Sample Street, Example City, CA 90000",
            "beneficiary_address_since": "2020-01-01",
            "beneficiary_marriage_count": 1,
            "parent1_last_name": "Garcia",
            "parent1_first_name": "Rosa",
            "parent1_date_of_birth": "1972-03-03",
            "parent1_country_of_birth": "Colombia",
            "parent2_last_name": "Garcia",
            "parent2_first_name": "Carlos",
            "parent2_date_of_birth": "1970-11-20",
            "parent2_country_of_birth": "Colombia",
        },
    )
    session.commit()

    report = validate_case_filings(session, case.id, form_codes=["form_i130a"])

    assert report["summary"]["status"] == "passed"
    assert report["forms"][0]["source"]["questionnaire_version"] == "i130a-04-01-24-spouse-v2"
    assert report["forms"][0]["metadata"]["questionnaire_version"] == "i130a-04-01-24-spouse-v2"
    assert report["forms"][0]["metadata"]["mapped_pdf_field_count"] > 0
    assert report["forms"][0]["metadata"]["missing_template_fields"] == []


def test_filing_validation_i130a_flags_cross_form_i485_mismatch():
    session = make_session()
    case = create_case(session)
    save_i485_page_answers(
        session,
        case.id,
        "page_04_addresses_ssn",
        {
            "beneficiary_current_address_line1": "400 15th St",
            "beneficiary_current_city": "Oakland",
            "beneficiary_current_state": "CA",
            "beneficiary_current_zip": "94612",
        },
    )
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Garcia",
            "beneficiary_date_of_birth": "2001-11-23",
            "beneficiary_country_of_birth": "CO",
            "beneficiary_current_marital_status": "married",
            "beneficiary_current_employer_or_school": "Student",
            "beneficiary_employment_history": "Student from 2020-present",
            "beneficiary_current_address_line1": "385 14th St",
            "beneficiary_current_city": "Oakland",
            "beneficiary_current_state": "CA",
            "beneficiary_current_zip": "94612",
            "beneficiary_marriage_count": 1,
        },
    )
    session.commit()

    report = validate_case_filings(session, case.id, form_codes=["form_i130a"])

    assert "form_i130a_beneficiary_current_address_line1_cross_form_mismatch" in issue_codes(report)


def test_filing_validation_i130a_flags_uploaded_form_extraction_mismatch():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Garcia",
            "beneficiary_date_of_birth": "2001-11-23",
            "beneficiary_country_of_birth": "CO",
            "beneficiary_current_marital_status": "married",
            "beneficiary_current_employer_or_school": "Student",
            "beneficiary_employment_history": "Student from 2020-present",
            "beneficiary_current_address_line1": "385 14th St",
            "beneficiary_current_city": "Oakland",
            "beneficiary_current_state": "CA",
            "beneficiary_current_zip": "94612",
            "beneficiary_address_since": "2020-01-01",
            "beneficiary_marriage_count": 1,
        },
    )
    session.add(
        UploadedDocument(
            case_id=case.id,
            checklist_item_code="form_i130a",
            original_filename="form_i130a.pdf",
            stored_filename="form_i130a.pdf",
            mime_type="application/pdf",
            file_size=1234,
            upload_status="confirmed",
            document_type="form_i130a",
            document_language="english",
            extracted_fields={"beneficiary_current_address_line1": "400 15th St"},
        )
    )
    session.commit()

    report = validate_case_filings(session, case.id, form_codes=["form_i130a"])

    assert "form_i130a_beneficiary_current_address_line1_uploaded_document_mismatch" in issue_codes(report)


def test_filing_validation_route_returns_structured_form_issues():
    client, session = make_client_session()
    try:
        case = create_case(session)
        save_i485_page_answers(
            session,
            case.id,
            "page_08_marriage_spouse",
            {
                "petitioner_first_name": "Jordan",
                "petitioner_last_name": "Petitioner",
                "petitioner_citizenship_status": "us_citizen",
            },
        )
        session.commit()

        response = client.post(
            f"/api/v1/cases/{case.id}/filing-validation",
            json={"form_codes": ["form_i485"], "template_paths": {"form_i485": "missing-template.pdf"}},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["summary"]["status"] == "blocked"
        assert payload["forms"][0]["form_code"] == "form_i485"
        assert any(issue["code"].endswith("_missing_required") for issue in payload["forms"][0]["issues"])
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_filing_validation_route_uses_default_scope_without_request_body():
    client, session = make_client_session()
    try:
        case = create_case(session)
        upsert_intake_step(
            session,
            case.id,
            "baseline",
            {
                "petitioner_first_name": "Jordan",
                "beneficiary_first_name": "Avery",
            },
        )
        session.commit()

        response = client.post(f"/api/v1/cases/{case.id}/filing-validation")

        assert response.status_code == 200
        payload = response.json()
        assert payload["validation_scope"] == ["form_i485", "form_i864"]
        assert [form["form_code"] for form in payload["forms"]] == ["form_i485", "form_i864"]
        assert payload["summary"]["status"] == "blocked"
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_filing_validation_capabilities_route_lists_templates_and_roadmap():
    client, session = make_client_session()
    try:
        response = client.get("/api/v1/content/filing-validation")

        assert response.status_code == 200
        payload = response.json()
        by_code = {entry["form_code"]: entry for entry in payload["forms"]}

        assert payload["default_validation_scope"] == ["form_i485", "form_i864"]
        assert "form_i130" in payload["supported_form_codes"]
        assert "form_i130a" in payload["supported_form_codes"]
        assert "form_i131" in payload["supported_form_codes"]
        assert "form_g1145" in payload["supported_form_codes"]
        assert by_code["form_i485"]["status"] == "implemented"
        assert by_code["form_i485"]["template_field_count"] > 0
        assert by_code["form_i485"]["template_page_count"] == 24
        assert len(by_code["form_i485"]["template_sha256"]) == 64
        assert any(source["url"] == "https://www.uscis.gov/i-864p" for source in by_code["form_i864"]["source"]["sources"])
        assert by_code["form_g1145"]["status"] == "partial"
        assert by_code["form_i765"]["status"] == "partial"
        assert by_code["form_i131"]["status"] == "partial"
        assert by_code["form_i131"]["template_field_count"] > 0
        assert by_code["form_i131"]["source"]["questionnaire_version"] == "i131-01-20-25-local-v1"
        assert by_code["form_i130"]["status"] == "partial"
        i130_template_path = by_code["form_i130"]["default_template_path"]
        assert i130_template_path is None or i130_template_path.lower().endswith("i-130.pdf")
        assert by_code["form_i130"]["source"]["questionnaire_version"] == "i130-04-01-24-marriage-v1"
        assert by_code["form_i130a"]["source"]["official_pdf_url"].endswith("/i-130a.pdf")
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_filing_validation_i130a_finds_parent_facts_only_saved_on_the_i485():
    session = make_session()
    case = create_case(session)
    # Saved before these answers projected to intake, so only the I-485 step holds them.
    upsert_intake_step(
        session,
        case.id,
        "i485_ingestion:page_parents",
        {"answers": {"parent1_last_name": "Garcia", "parent1_first_name": "Rosa"}},
    )
    session.commit()

    codes = issue_codes(validate_case_filings(session, case.id, form_codes=["form_i130a"]))

    assert "form_i130a_parent1_last_name_missing_required" not in codes
    assert "form_i130a_parent1_first_name_missing_required" not in codes
    assert "form_i130a_parent2_last_name_missing_required" in codes


def test_filing_validation_i130_flags_a_class_of_admission_the_form_does_not_offer():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(session, case.id, "baseline", {"beneficiary_class_of_admission": "TN"})
    session.commit()

    report = validate_case_filings(session, case.id, form_codes=["form_i130"])

    assert "form_i130_class_of_admission_not_offered" in issue_codes(report)
