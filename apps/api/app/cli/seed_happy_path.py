"""Seeds a complete sample case for local development."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from typing import Any

from sqlmodel import Session, select

from app.cli.seed_placeholder_pdf import packet_section_for_checklist_code, write_seed_placeholder_pdf
from app.content.i485_questionnaire import I485_QUESTIONNAIRE
from app.content.i485_sample import build_sample_i485_answers
from app.content.supplemental_forms import get_supplemental_form_config
from app.core.config import settings
from app.db.session import create_db_and_tables, engine
from app.models.entities import (
    CaseChecklistItem,
    CaseRecord,
    ChecklistProgressStatus,
    UploadedDocument,
)
from app.services.checklist import generate_checklist
from app.services.form_ingestion import get_form_state, save_form_page_answers
from app.services.form_pdf import DEFAULT_FORM_OUTPUT_DIR, generate_form_pdf
from app.services.i485 import get_i485_state, save_i485_page_answers
from app.services.i485_pdf import DEFAULT_I485_OUTPUT_DIR, DEFAULT_I485_TEMPLATE_PATH, generate_i485_pdf
from app.services.intake import upsert_intake_step
from app.services.prescreen import save_prescreen_answers
from app.services.qa import run_qa

BASE_SAMPLE: dict[str, Any] = {
    "petitioner_phone": "0000000101",
    "petitioner_email": "jordan.petitioner@example.com",
    "petitioner_city_of_birth": "San Diego",
    "petitioner_social_security_number": "000000001",
    "petitioner_mobile_phone": "0000000101",
    "beneficiary_mobile_phone": "0000000100",
    "beneficiary_last_arrival_place": "Miami, FL",
    "parent1_city_of_birth": "Bogota",
    "parent1_city_of_residence": "Bogota",
    "parent1_country_of_residence": "Colombia",
    "parent2_city_of_birth": "Medellin",
    "parent2_city_of_residence": "Medellin",
    "parent2_country_of_residence": "Colombia",
    "employment_status": "employed",
    "annual_income": 95000,
    "i864_household_income": 95000,
    "i864_tax_income_1": 95000,
    "i864_tax_income_2": 91000,
    "i864_tax_income_3": 87000,
    "petitioner_current_employer": "Sample Robotics Inc.",
    "sponsor_willing": True,
    "petitioner_current_address_line1": "123 Sample Street",
    "petitioner_current_city": "Oakland",
    "petitioner_current_state": "CA",
    "petitioner_current_zip": "94612",
    "beneficiary_mailing_address_line1": "123 Sample Street",
    "beneficiary_mailing_city": "Oakland",
    "beneficiary_mailing_state": "CA",
    "beneficiary_mailing_zip": "94612",
    "i130_filing_status": "not_filed",
    "wants_i765": True,
    "wants_i131": True,
    "needs_translation": True,
    "reviewed_current_fees": True,
    "reviewed_current_form_editions": True,
    "g1145_last_name": "Sample",
    "g1145_first_name": "Avery",
    "g1145_middle_name": "Maria",
    "g1145_email": "avery.sample@example.com",
    "g1145_mobile_phone": "0000000100",
    "i131_intended_departure_date": "2026-12-15",
    "i131_travel_purpose": "Short family visit to see beneficiary's parents while adjustment is pending.",
    "i131_countries_to_visit": "Colombia",
    "i131_expected_trip_length": 14,
}


SUPPLEMENTAL_OVERRIDES: dict[str, dict[str, Any]] = {
    "i130": {
        "petitioner_sex": "male",
        "petitioner_ethnicity": "not_hispanic_or_latino",
        "petitioner_race": ["white"],
        "petitioner_height_feet": 5,
        "petitioner_height_inches": 10,
        "petitioner_weight_pounds": 170,
        "petitioner_eye_color": "brown",
        "petitioner_hair_color": "black",
        "petitioner_filed_prior_petition": False,
        "petitioner_current_employer_address_line1": "200 Robotics Way",
        "petitioner_current_employer_city": "San Jose",
        "petitioner_current_employer_state": "CA",
        "petitioner_current_employer_zip": "95113",
        "petitioner_current_employment_from": "2023-01-09",
        "petitioner_parent1_city_of_residence": "San Diego",
        "petitioner_parent2_city_of_residence": "San Diego",
        "petitioner_mailing_same_as_physical": True,
        "petitioner_physical_address_from": "2024-01-01",
        "petitioner_parent1_last_name": "Sampleparent",
        "petitioner_parent1_first_name": "Casey",
        "petitioner_parent1_date_of_birth": "1969-02-03",
        "petitioner_parent1_sex": "female",
        "petitioner_parent2_last_name": "Sampleparent",
        "petitioner_parent2_first_name": "Morgan",
        "petitioner_parent2_date_of_birth": "1968-03-04",
        "petitioner_parent2_sex": "male",
        "beneficiary_prior_petition_filed": "no",
        "beneficiary_current_country": "United States",
        "beneficiary_ever_in_united_states": True,
        "beneficiary_ever_in_immigration_proceedings": False,
        "beneficiary_immigration_proceedings_type": "",
        "beneficiary_current_employer_country": "United States",
        "beneficiary_last_shared_country": "United States",
        "beneficiary_last_shared_address_from": "2025-04-15",
        "beneficiary_consular_country": "",
        "petitioner_prior_employer_country": "",
        "petitioner_prior_country": "",
        "beneficiary_foreign_country": "",
        "beneficiary_native_country": "",
    },
    "i130a": {
        "parent1_sex": "female",
        "parent2_sex": "male",
        "beneficiary_current_country": "United States",
        "beneficiary_current_employer_country": "United States",
    },
    "i765": {
        "i765_reason_for_applying": "initial_permission",
        "i765_physical_same_as_mailing": True,
        "i765_previously_filed": False,
        "i765_eligibility_category": "c9_pending_i485",
        "i765_arrested_or_convicted": False,
        "applicant_reviewed_certification": True,
        "interpreter_used": False,
        "preparer_used": False,
        "additional_information_needed": False,
    },
    "i131": {
        "i131_application_type": "advanced_parole_i485_pending",
        "beneficiary_mailing_country": "United States",
        "i131_physical_same_as_mailing": True,
        "beneficiary_race_primary": "white",
        "i131_removal_proceedings": False,
        "i131_prior_reentry_refugee_document": False,
        "i131_prior_advance_parole": False,
        "i131_replacement_request": False,
        "i131_processing_location": "domestic_address",
        "i131_trip_count": "one",
        "applicant_reviewed_certification": True,
        "interpreter_used": False,
        "preparer_used": False,
        "additional_information_needed": False,
    },
    "i864": {
        "i864_sponsor_basis": "petitioner",
        "i864_physical_same_as_mailing": True,
        "petitioner_country_of_domicile": "United States",
        "spouse_us_military": False,
        "i864_only_principal_immigrant": True,
        "i864_sponsoring_family_members": False,
        "i864_total_immigrants": 1,
        "i864_sponsor_married_count": 0,
        "i864_dependent_children_count": 0,
        "i864_other_dependents_count": 0,
        "i864_prior_sponsored_immigrants_count": 0,
        "i864_household_members_combining_income_count": 0,
        "employment_status": "employed",
        "petitioner_current_occupation": "Engineer",
        "i864_filed_recent_tax_return": True,
        "i864_tax_year_1": 2025,
        "i864_tax_year_2": 2024,
        "i864_tax_year_3": 2023,
        "i864_cash_assets": 15000,
        "i864_total_assets": 15000,
        "sponsor_reviewed_contract": True,
        "interpreter_used": False,
        "preparer_used": False,
        "additional_information_needed": False,
    },
}


PRESCREEN_ANSWERS: dict[str, Any] = {
    "case_basis": "usc_spouse",
    "relationship_spouse": True,
    "prior_immigration_denials": False,
    "criminal_history": False,
    "intent_timing_snapshot": {
        "married_before_entry": False,
        "i130_pending_at_entry": False,
        "days_between_entry_and_filing": 200,
        "plans_changed_after_arrival": True,
    },
    "has_children": False,
    "bona_fide_evidence_categories": ["joint_lease_mortgage", "joint_bank", "photos_family"],
    "birth_certificate_available": True,
    "name_variation_snapshot": {"has_name_variations": False, "name_variations_note": ""},
    "has_i693": True,
    "immigration_violations": ["none"],
    "inadmissibility_review_categories": ["none"],
    "security_or_military_history": False,
}

SEEDED_SUPPLEMENTAL_FORMS = ("i130", "i130a", "i765", "i131", "i864")

UPLOADS: list[tuple[str, str, dict[str, Any]]] = [
    ("form_i130", "sample-form-i-130.pdf", {"satisfies_checklist_codes": ["form_i130", "form_i130a"]}),
    ("form_i485", "sample-form-i-485.pdf", {}),
    ("form_i864", "sample-form-i-864.pdf", {}),
    ("form_g1145", "sample-form-g-1145.pdf", {}),
    ("form_i765", "sample-form-i-765.pdf", {}),
    ("form_i131", "sample-form-i-131.pdf", {}),
    ("petitioner_citizenship_proof", "sample-us-passport.pdf", {}),
    ("beneficiary_passport_bio", "sample-beneficiary-passport.pdf", {}),
    ("beneficiary_passport_photos", "sample-passport-photos.pdf", {}),
    ("petitioner_passport_photos", "sample-petitioner-passport-photos.pdf", {}),
    ("beneficiary_i94", "sample-i-94.pdf", {}),
    ("beneficiary_visa_or_entry_stamp", "sample-entry-stamp.pdf", {}),
    ("marriage_certificate", "sample-marriage-certificate.pdf", {}),
    ("beneficiary_birth_certificate", "sample-birth-certificate-with-translation.pdf", {}),
    ("sponsor_tax_return", "sample-tax-return.pdf", {}),
    ("sponsor_pay_stubs", "sample-pay-stubs.pdf", {}),
    ("employment_verification_letter", "sample-employment-letter.pdf", {}),
    ("joint_lease", "sample-joint-lease.pdf", {}),
    ("joint_bank_statement", "sample-joint-bank-statement.pdf", {}),
    ("photos_together", "sample-relationship-photos.pdf", {}),
    ("affidavits", "sample-family-affidavit.pdf", {}),
    ("medical_exam_i693", "sample-i-693-sealed-packet-tracker.pdf", {}),
    ("medical_exam_supporting_records", "sample-vaccine-records.pdf", {}),
    ("travel_explanation_i131", "sample-travel-explanation.pdf", {}),
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a complete fake happy-path case for local E2E testing.")
    parser.add_argument("--case-name", default="Happy path sample packet")
    parser.add_argument("--web-base-url", default="http://localhost:3000")
    parser.add_argument("--generate-pdfs", action="store_true")
    return parser


def sample_answers() -> dict[str, Any]:
    answers = build_sample_i485_answers()
    answers.update(BASE_SAMPLE)
    return answers


def _empty_value(answer_type: str) -> Any:
    if answer_type == "boolean":
        return False
    if answer_type == "number":
        return 0
    if answer_type == "multi_select":
        return []
    return ""


def _answer_for_question(form_key: str, question: dict[str, Any], sample: dict[str, Any]) -> Any:
    overrides = SUPPLEMENTAL_OVERRIDES.get(form_key, {})
    question_id = question["id"]
    if question_id in overrides:
        return overrides[question_id]
    if question_id in sample:
        return sample[question_id]

    db_path = question.get("db_path")
    if isinstance(db_path, str) and db_path.startswith("intake."):
        source_key = db_path.removeprefix("intake.")
        if source_key in sample:
            return sample[source_key]

    options = question.get("options") or []
    if question.get("ideal_answer") is not None:
        return question["ideal_answer"]
    if question["answer_type"] == "boolean":
        return False
    if question["answer_type"] == "number":
        return 1 if question.get("required") else 0
    if question["answer_type"] == "date":
        return "2026-01-01" if question.get("required") else ""
    if question["answer_type"] == "select":
        return options[0]["value"] if options else ""
    if question["answer_type"] == "country":
        return "United States" if "petitioner" in question_id else ""
    return "Sample response" if question.get("required") else _empty_value(question["answer_type"])


def _create_case(session: Session, case_name: str) -> CaseRecord:
    case = CaseRecord(
        case_name=case_name,
        workflow_type="marriage_concurrent",
        petitioner_email="jordan.petitioner@example.com",
        beneficiary_email="avery.sample@example.com",
        country_of_focus="CO",
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


def seed_i485(session: Session, case: CaseRecord, sample: dict[str, Any]) -> None:
    for page in I485_QUESTIONNAIRE:
        page_answers = {
            question["id"]: sample[question["id"]]
            for question in page["questions"]
            if question["id"] in sample
        }
        save_i485_page_answers(session, case.id, page["id"], page_answers)


def seed_supplemental_form(session: Session, case: CaseRecord, form_key: str, sample: dict[str, Any]) -> None:
    config = get_supplemental_form_config(form_key)
    for page in config["pages"]:
        page_answers = {
            question["id"]: _answer_for_question(form_key, question, sample)
            for question in page["questions"]
        }
        save_form_page_answers(session, case.id, form_key, page["id"], page_answers)


def _seed_base_intake(session: Session, case: CaseRecord, sample: dict[str, Any]) -> None:
    payload = dict(sample)
    payload.update(BASE_SAMPLE)
    upsert_intake_step(session, case.id, "happy_path_sample", payload)
    save_prescreen_answers(session, case.id, PRESCREEN_ANSWERS)


def _seed_uploads(session: Session, case: CaseRecord) -> None:
    upload_dir = settings.upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)

    for code, filename, extracted_fields in UPLOADS:
        stored_filename = f"{case.id}-{filename}"
        stored_path = upload_dir / stored_filename
        if not stored_path.exists():
            write_seed_placeholder_pdf(
                stored_path,
                section=packet_section_for_checklist_code(code),
                category="sample_upload",
                label=filename,
                code=code,
            )

        existing = session.exec(
            select(UploadedDocument).where(
                UploadedDocument.case_id == case.id,
                UploadedDocument.checklist_item_code == code,
                UploadedDocument.original_filename == filename,
            )
        ).first()
        upload = existing or UploadedDocument(case_id=case.id, checklist_item_code=code, original_filename=filename)
        upload.stored_filename = stored_filename
        upload.mime_type = "application/pdf"
        upload.file_size = stored_path.stat().st_size
        upload.upload_status = "confirmed"
        upload.review_status = "reviewed"
        upload.ocr_status = "complete"
        upload.extraction_confidence = 1.0
        upload.document_type = code
        upload.document_language = "english"
        upload.requires_translation = code == "beneficiary_birth_certificate"
        upload.has_translation = code == "beneficiary_birth_certificate"
        upload.extracted_fields = extracted_fields
        upload.updated_at = now
        session.add(upload)


def _mark_applicable_checklist_complete(session: Session, case: CaseRecord) -> None:
    items = list(session.exec(select(CaseChecklistItem).where(CaseChecklistItem.case_id == case.id)))
    for item in items:
        if item.applicability == "not_applicable":
            continue
        item.completion_status = ChecklistProgressStatus.complete.value
        item.updated_at = datetime.now(UTC)
        session.add(item)


def _generate_pdfs(session: Session, case: CaseRecord) -> dict[str, str | None]:
    generated: dict[str, str | None] = {}
    try:
        generated["i485"] = str(
            generate_i485_pdf(
                session=session,
                case_id=case.id,
                template_path=DEFAULT_I485_TEMPLATE_PATH,
                output_dir=DEFAULT_I485_OUTPUT_DIR,
                allow_incomplete=False,
            ).output_path
        )
    except Exception as exc:  # noqa: BLE001  # pragma: no cover - dev convenience output
        generated["i485"] = f"skipped: {exc}"

    for form_key in SEEDED_SUPPLEMENTAL_FORMS:
        try:
            generated[form_key] = str(
                generate_form_pdf(
                    session=session,
                    case_id=case.id,
                    form_key=form_key,
                    output_dir=DEFAULT_FORM_OUTPUT_DIR,
                    allow_incomplete=False,
                ).output_path
            )
        except Exception as exc:  # noqa: BLE001  # pragma: no cover - dev convenience output
            generated[form_key] = f"skipped: {exc}"
    return generated


def main() -> None:
    args = build_parser().parse_args()
    create_db_and_tables()
    sample = sample_answers()

    with Session(engine) as session:
        case = _create_case(session, args.case_name)
        _seed_base_intake(session, case, sample)
        seed_i485(session, case, sample)
        for form_key in SEEDED_SUPPLEMENTAL_FORMS:
            seed_supplemental_form(session, case, form_key, sample)
        _seed_uploads(session, case)
        session.commit()

        checklist_items, _ = generate_checklist(session, case.id)
        _mark_applicable_checklist_complete(session, case)
        session.commit()
        qa_issues, qa_summary = run_qa(session, case.id)
        _mark_applicable_checklist_complete(session, case)
        session.commit()

        generated_pdfs = _generate_pdfs(session, case) if args.generate_pdfs else {}
        i485_state = get_i485_state(session, case.id)
        form_states = {key: get_form_state(session, case.id, key) for key in SEEDED_SUPPLEMENTAL_FORMS}

    base_url = args.web_base_url.rstrip("/")
    print(
        json.dumps(
            {
                "case_id": str(case.id),
                "case_url": f"{base_url}/?caseId={case.id}",
                "i485_url": f"{base_url}/i485-ingestion?caseId={case.id}",
                **{
                    f"{key}_url": f"{base_url}/form-ingestion?form={key}&caseId={case.id}"
                    for key in SEEDED_SUPPLEMENTAL_FORMS
                },
                "checklist_items": len(checklist_items),
                "i485_completion_pct": i485_state["evaluation"]["completion_pct"],
                "form_completion_pct": {
                    key: state["evaluation"]["completion_pct"] for key, state in form_states.items()
                },
                "form_readiness": {
                    key: state["evaluation"]["readiness"] for key, state in form_states.items()
                },
                "qa_issue_count": len(qa_issues),
                "qa_summary": qa_summary,
                "generated_pdfs": generated_pdfs,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
