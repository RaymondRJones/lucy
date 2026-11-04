from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

from sqlmodel import Session, SQLModel, create_engine

from app.models.entities import CaseRecord, UploadedDocument
from app.services.checklist import generate_checklist
from app.services.i485 import save_i485_page_answers
from app.services.intake import derive_case_facts, upsert_intake_step
from app.services.qa import run_qa


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def standard_intake_payload() -> dict[str, object]:
    return {
        "petitioner_first_name": "Jordan",
        "petitioner_last_name": "Petitioner",
        "petitioner_email": "petitioner.sample@example.com",
        "beneficiary_first_name": "Avery",
        "beneficiary_last_name": "Garcia",
        "beneficiary_email": "beneficiary.sample@example.com",
        "marriage_date": date(2025, 7, 20).isoformat(),
        "first_marriage_for_both": True,
        "beneficiary_location": "usa",
        "beneficiary_entered_us_legally": True,
        "beneficiary_country_of_birth": "Colombia",
        "beneficiary_current_immigration_status": "B2",
        "household_size": 2,
        "annual_income": 72000,
        "employment_status": "employed",
        "wants_i765": True,
        "wants_i131": False,
        "needs_translation": True,
        "reviewed_current_fees": True,
        "reviewed_current_form_editions": True,
    }


def create_case(session: Session) -> CaseRecord:
    case = CaseRecord(case_name="Standard Marriage Case", workflow_type="marriage_concurrent")
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


def test_generate_checklist_marks_core_forms_required():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(session, case.id, "baseline", standard_intake_payload())
    session.commit()

    items, facts = generate_checklist(session, case.id)
    codes_to_applicability = {item.code: item.applicability for item in items}

    assert facts["concurrent_filing_eligible"] is True
    assert codes_to_applicability["form_i130"] == "required"
    assert codes_to_applicability["i130_receipt_notice"] == "not_applicable"
    assert codes_to_applicability["form_i485"] == "required"
    assert codes_to_applicability["form_i765"] == "conditional"
    assert codes_to_applicability["translation_certification"] == "conditional"


def test_generate_checklist_switches_to_receipt_when_i130_already_filed():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {**standard_intake_payload(), "i130_filing_status": "pending"},
    )
    session.commit()

    items, facts = generate_checklist(session, case.id)
    codes_to_applicability = {item.code: item.applicability for item in items}

    assert facts["i130_already_filed"] is True
    assert codes_to_applicability["form_i130"] == "not_applicable"
    assert codes_to_applicability["form_i130a"] == "not_applicable"
    assert codes_to_applicability["i130_receipt_notice"] == "conditional"


def test_generate_checklist_groups_pending_i130_relationship_evidence_with_i485():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {**standard_intake_payload(), "i130_filing_status": "pending"},
    )
    session.commit()

    items, _ = generate_checklist(session, case.id)
    by_code = {item.code: item for item in items}

    for code in ("marriage_certificate", "photos_together", "joint_bank_statement", "joint_lease"):
        assert by_code[code].applicability != "not_applicable"
        assert by_code[code].item_metadata["form_codes"] == ["form_i485"]
        assert by_code[code].item_metadata["packet_group_reason"] == "pending_i130_relationship_evidence"


def test_generate_checklist_pauses_i130_drafts_when_petition_history_needs_review():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {**standard_intake_payload(), "i130_filing_status": "denied_revoked_withdrawn"},
    )
    session.commit()

    items, facts = generate_checklist(session, case.id)
    codes_to_applicability = {item.code: item.applicability for item in items}

    assert facts["i130_needs_review"] is True
    assert codes_to_applicability["form_i130"] == "not_applicable"
    assert codes_to_applicability["form_i130a"] == "not_applicable"


def test_generate_checklist_counts_combined_upload_for_i130a():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(session, case.id, "baseline", standard_intake_payload())
    session.commit()
    generate_checklist(session, case.id)

    session.add(
        UploadedDocument(
            case_id=case.id,
            checklist_item_code="form_i130",
            original_filename="I-130.pdf",
            stored_filename=f"{uuid4()}-I-130.pdf",
            mime_type="application/pdf",
            file_size=45678,
            upload_status="confirmed",
            document_type="form_i130",
            document_language="english",
            requires_translation=False,
            has_translation=False,
            extracted_fields={
                "satisfies_checklist_codes": ["form_i130", "form_i130a"],
                "embedded_i130a_detected": True,
            },
        )
    )
    session.commit()

    items, _ = generate_checklist(session, case.id)
    by_code = {item.code: item for item in items}

    assert by_code["form_i130"].completion_status == "uploaded"
    assert by_code["form_i130a"].completion_status == "uploaded"
    assert by_code["form_i130a"].item_metadata["upload_count"] == 1


def test_generate_checklist_preserves_manual_status_after_confirmed_upload():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(session, case.id, "baseline", standard_intake_payload())
    session.commit()

    items, _ = generate_checklist(session, case.id)
    item = next(entry for entry in items if entry.code == "form_i130")
    item.completion_status = "almost_done"
    session.add(item)
    session.commit()

    session.add(
        UploadedDocument(
            case_id=case.id,
            checklist_item_code="form_i130",
            original_filename="I-130.pdf",
            stored_filename=f"{uuid4()}-I-130.pdf",
            mime_type="application/pdf",
            file_size=45678,
            upload_status="confirmed",
            document_type="form_i130",
            document_language="english",
            requires_translation=False,
            has_translation=False,
            extracted_fields={"satisfies_checklist_codes": ["form_i130"]},
        )
    )
    session.commit()

    items, _ = generate_checklist(session, case.id)
    by_code = {entry.code: entry for entry in items}

    assert by_code["form_i130"].completion_status == "almost_done"


def test_run_qa_uses_confirmed_uploads_without_overwriting_workflow_status():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(session, case.id, "baseline", standard_intake_payload())
    session.commit()

    items, _ = generate_checklist(session, case.id)
    item = next(entry for entry in items if entry.code == "form_i130")
    item.completion_status = "pending"
    session.add(item)
    session.commit()

    session.add(
        UploadedDocument(
            case_id=case.id,
            checklist_item_code="form_i130",
            original_filename="I-130.pdf",
            stored_filename=f"{uuid4()}-I-130.pdf",
            mime_type="application/pdf",
            file_size=45678,
            upload_status="confirmed",
            document_type="form_i130",
            document_language="english",
            requires_translation=False,
            has_translation=False,
            extracted_fields={"satisfies_checklist_codes": ["form_i130"]},
        )
    )
    session.commit()

    issues, summary = run_qa(session, case.id)
    refreshed = session.get(type(item), item.id)
    codes = {issue.code for issue in issues}

    assert "missing_form_i130" not in codes
    assert summary["required_completion_pct"] > 0
    assert refreshed is not None
    assert refreshed.completion_status == "pending"


def test_run_qa_flags_translation_and_financial_gaps():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(session, case.id, "baseline", standard_intake_payload())
    session.commit()
    generate_checklist(session, case.id)

    session.add(
        UploadedDocument(
            case_id=case.id,
            checklist_item_code="beneficiary_birth_certificate",
            original_filename="birth-cert.pdf",
            stored_filename=f"{uuid4()}-birth-cert.pdf",
            mime_type="application/pdf",
            file_size=12345,
            upload_status="confirmed",
            document_type="civil_birth_record",
            document_language="spanish",
            requires_translation=True,
            has_translation=False,
            extracted_fields={"beneficiary_name": "Avery Garcia"},
        )
    )
    session.commit()

    issues, summary = run_qa(session, case.id)
    codes = {issue.code for issue in issues}

    assert "missing_sponsor_tax_return" in codes
    assert any(code.startswith("translation_missing_") for code in codes)
    assert summary["label"] == "Not ready"


def test_run_qa_flags_source_backed_form_mismatches():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(session, case.id, "baseline", standard_intake_payload())
    session.commit()
    generate_checklist(session, case.id)

    session.add(
        UploadedDocument(
            case_id=case.id,
            checklist_item_code="form_i130",
            original_filename="I-130.pdf",
            stored_filename=f"{uuid4()}-I-130.pdf",
            mime_type="application/pdf",
            file_size=45678,
            upload_status="confirmed",
            document_type="form_i130",
            document_language="english",
            requires_translation=False,
            has_translation=False,
            extracted_fields={
                "petitioner_name": "Jordan Petitioner",
                "beneficiary_name": "Avery Garcia",
                "marriage_date": "2025-07-20",
            },
        )
    )
    session.add(
        UploadedDocument(
            case_id=case.id,
            checklist_item_code="form_i485",
            original_filename="I-485.pdf",
            stored_filename=f"{uuid4()}-I-485.pdf",
            mime_type="application/pdf",
            file_size=45678,
            upload_status="confirmed",
            document_type="form_i485",
            document_language="english",
            requires_translation=False,
            has_translation=False,
            extracted_fields={
                "petitioner_name": "Jordan Petitioner",
                "beneficiary_name": "Avery Garcia",
                "marriage_date": "2025-07-21",
            },
        )
    )
    session.commit()

    issues, _ = run_qa(session, case.id)

    mismatch_issue = next(
        issue for issue in issues if issue.code.startswith("document_mismatch_marriage_date_")
    )

    assert mismatch_issue.title == "Marriage date does not match across uploaded forms"
    assert "I-130.pdf" in mismatch_issue.description
    assert "I-485.pdf" in mismatch_issue.description


def test_run_qa_flags_recent_address_without_prior_history():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(session, case.id, "baseline", standard_intake_payload())
    session.commit()
    generate_checklist(session, case.id)

    session.add(
        UploadedDocument(
            case_id=case.id,
            checklist_item_code="form_i485",
            original_filename="I-485.pdf",
            stored_filename=f"{uuid4()}-I-485.pdf",
            mime_type="application/pdf",
            file_size=45678,
            upload_status="confirmed",
            document_type="form_i485",
            document_language="english",
            requires_translation=False,
            has_translation=False,
            extracted_fields={
                "beneficiary_name": "Avery Garcia",
                "beneficiary_current_address": "123 Sample Street, Unit 4B, Example City, CA, 94612, United States",
                "beneficiary_address_since": (date.today() - timedelta(days=30)).isoformat(),
            },
        )
    )
    session.commit()

    issues, _ = run_qa(session, case.id)

    assert any(issue.code.startswith("address_history_missing_") for issue in issues)


def test_run_qa_flags_recent_intake_address_without_prior_history():
    session = make_session()
    case = create_case(session)
    payload = standard_intake_payload()
    payload["beneficiary_current_address"] = "123 Sample Street, Example City, CA 90000"
    payload["beneficiary_current_address_since"] = (date.today() - timedelta(days=30)).isoformat()
    upsert_intake_step(session, case.id, "baseline", payload)
    session.commit()
    generate_checklist(session, case.id)

    issues, _ = run_qa(session, case.id)

    assert any(issue.code == "intake_address_history_missing" for issue in issues)


def test_run_qa_flags_intake_to_document_mismatch():
    session = make_session()
    case = create_case(session)
    payload = standard_intake_payload()
    payload["beneficiary_i94_number"] = "ABC123"
    upsert_intake_step(session, case.id, "baseline", payload)
    session.commit()
    generate_checklist(session, case.id)

    session.add(
        UploadedDocument(
            case_id=case.id,
            checklist_item_code="form_i485",
            original_filename="I-485.pdf",
            stored_filename=f"{uuid4()}-I-485.pdf",
            mime_type="application/pdf",
            file_size=45678,
            upload_status="confirmed",
            document_type="form_i485",
            document_language="english",
            requires_translation=False,
            has_translation=False,
            extracted_fields={
                "beneficiary_name": "Avery Garcia",
                "beneficiary_i94_number": "XYZ789",
            },
        )
    )
    session.commit()

    issues, _ = run_qa(session, case.id)

    mismatch = next(issue for issue in issues if issue.code.startswith("intake_document_mismatch_beneficiary_i94_number_"))
    assert mismatch.title == "Intake beneficiary I-94 number does not match an uploaded document"
    assert "ABC123" in mismatch.description
    assert "XYZ789" in mismatch.description


def test_derive_case_facts_marks_complex_case_when_history_reported():
    payload = standard_intake_payload()
    payload["criminal_history"] = True

    facts = derive_case_facts(payload)

    assert facts["complex_case"] is True
    assert facts["escalation_flags"]["criminal_history"] is True


def test_run_qa_surfaces_i485_ingestion_risk_flags():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(session, case.id, "baseline", standard_intake_payload())
    save_i485_page_answers(
        session,
        case.id,
        "page_11_criminal_acts",
        {"ever_committed_crime": True},
    )
    session.commit()
    generate_checklist(session, case.id)

    issues, summary = run_qa(session, case.id)
    codes = {issue.code for issue in issues}

    assert "i485_criminal_history_ever_committed_crime" in codes
    assert summary["issue_counts"]["blocking"] >= 1
    assert summary["label"] == "Not ready"


def test_run_qa_surfaces_i485_outside_niche_flags_as_important():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(session, case.id, "baseline", standard_intake_payload())
    save_i485_page_answers(
        session,
        case.id,
        "page_08_marriage_spouse",
        {
            "beneficiary_current_marital_status": "married",
            "beneficiary_marriage_count": 2,
            "petitioner_citizenship_status": "us_citizen",
        },
    )
    session.commit()
    generate_checklist(session, case.id)

    issues, _ = run_qa(session, case.id)
    issue = next(issue for issue in issues if issue.code == "i485_outside_niche_prior_marriage_beneficiary_marriage_count")

    assert issue.severity == "important"
    assert issue.checklist_item_code == "form_i485"


def test_run_qa_blocks_readiness_while_i485_answers_are_missing():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(session, case.id, "baseline", standard_intake_payload())
    session.commit()
    generate_checklist(session, case.id)
    save_i485_page_answers(session, case.id, "page_01_identity", {"beneficiary_last_name": "Garcia"})
    session.commit()

    issues, summary = run_qa(session, case.id)
    missing = next(issue for issue in issues if issue.code == "i485_missing_required_answers")

    assert missing.severity == "blocking"
    assert summary["label"] == "Not ready"
