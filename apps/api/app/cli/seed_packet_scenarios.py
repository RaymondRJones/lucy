from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from sqlmodel import Session, select

from app.cli.seed_happy_path import _sample_answers, _seed_i485, _seed_supplemental_form
from app.cli.seed_placeholder_pdf import packet_section_for_checklist_code, write_seed_placeholder_pdf
from app.db.session import create_db_and_tables, engine
from app.models.entities import (
    CaseChecklistItem,
    CaseRecord,
    ChecklistProgressStatus,
    UploadedDocument,
)
from app.services.checklist import generate_checklist
from app.services.intake import upsert_intake_step
from app.services.packet_assembly import assemble_packet_pdf
from app.services.qa import run_qa


@dataclass(frozen=True)
class PacketScenario:
    slug: str
    case_name: str
    state_code: str
    carrier: str
    petitioner_first_name: str
    petitioner_last_name: str
    beneficiary_first_name: str
    beneficiary_last_name: str
    beneficiary_country: str
    city: str
    state: str
    zip_code: str
    wants_i765: bool
    wants_i131: bool
    needs_translation: bool
    first_marriage_for_both: bool = True
    annual_income: int = 95000
    extra_answers: dict[str, Any] = field(default_factory=dict)


SCENARIOS = [
    PacketScenario(
        slug="ca-full-translation",
        case_name="Packet scenario - California full packet with translation",
        state_code="CA",
        carrier="usps",
        petitioner_first_name="Jordan",
        petitioner_last_name="Parker",
        beneficiary_first_name="Avery",
        beneficiary_last_name="Parker",
        beneficiary_country="Colombia",
        city="Oakland",
        state="CA",
        zip_code="94612",
        wants_i765=True,
        wants_i131=True,
        needs_translation=True,
        annual_income=98000,
    ),
    PacketScenario(
        slug="tx-work-only",
        case_name="Packet scenario - Texas work permit no travel",
        state_code="TX",
        carrier="private",
        petitioner_first_name="Mia",
        petitioner_last_name="Rivera",
        beneficiary_first_name="Nolan",
        beneficiary_last_name="Rivera",
        beneficiary_country="Canada",
        city="Austin",
        state="TX",
        zip_code="78704",
        wants_i765=True,
        wants_i131=False,
        needs_translation=False,
        annual_income=72000,
        extra_answers={
            "beneficiary_sex": "male",
            "beneficiary_ethnicity": "not_hispanic_or_latino",
            "beneficiary_hair_color": "black",
            "beneficiary_eye_color": "blue",
        },
    ),
    PacketScenario(
        slug="ga-core-only",
        case_name="Packet scenario - Georgia core adjustment only",
        state_code="GA",
        carrier="usps",
        petitioner_first_name="Taylor",
        petitioner_last_name="Brooks",
        beneficiary_first_name="Sam",
        beneficiary_last_name="Brooks",
        beneficiary_country="United Kingdom",
        city="Atlanta",
        state="GA",
        zip_code="30309",
        wants_i765=False,
        wants_i131=False,
        needs_translation=False,
        annual_income=112000,
    ),
    PacketScenario(
        slug="az-prior-marriage-travel",
        case_name="Packet scenario - Arizona travel request with prior marriage record",
        state_code="AZ",
        carrier="private",
        petitioner_first_name="Casey",
        petitioner_last_name="Nguyen",
        beneficiary_first_name="Riley",
        beneficiary_last_name="Nguyen",
        beneficiary_country="Mexico",
        city="Phoenix",
        state="AZ",
        zip_code="85004",
        wants_i765=False,
        wants_i131=True,
        needs_translation=True,
        first_marriage_for_both=False,
        annual_income=86000,
        extra_answers={
            "beneficiary_marriage_count": 2,
            "beneficiary_prior_marriages": "One prior marriage ended by final divorce decree in 2021.",
            "beneficiary_prior_marriage_termination_date": "2021-08-20",
            "i131_travel_purpose": "Short family visit for a parent's scheduled medical procedure.",
            "i131_countries_to_visit": "Mexico",
            "i131_expected_trip_length": "10 days",
        },
    ),
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seed varied local packet-assembly test cases with real mergeable PDF uploads."
    )
    parser.add_argument("--web-base-url", default="http://localhost:3000")
    parser.add_argument("--no-generate-packets", action="store_true")
    return parser


def _safe_email(name: str, slug: str) -> str:
    local = name.lower().replace(" ", ".")
    return f"{local}.{slug.replace('-', '.')}@example.com"


def _scenario_answers(scenario: PacketScenario) -> dict[str, Any]:
    answers = _sample_answers()
    beneficiary_email = _safe_email(scenario.beneficiary_first_name, scenario.slug)
    petitioner_email = _safe_email(scenario.petitioner_first_name, scenario.slug)
    address = {
        "line1": f"100 {scenario.case_name.split(' - ')[-1][:24]} Avenue",
        "line2": "Apt 2",
        "city": scenario.city,
        "state": scenario.state,
        "zip": scenario.zip_code,
        "country": "United States",
    }
    answers.update(
        {
            "petitioner_first_name": scenario.petitioner_first_name,
            "petitioner_last_name": scenario.petitioner_last_name,
            "petitioner_middle_name": "",
            "petitioner_email": petitioner_email,
            "petitioner_phone": "0000001000",
            "petitioner_mobile_phone": "0000001000",
            "petitioner_social_security_number": "000000001",
            "petitioner_current_address": address,
            "petitioner_current_address_line1": address["line1"],
            "petitioner_current_address_line2": address["line2"],
            "petitioner_current_city": address["city"],
            "petitioner_current_state": address["state"],
            "petitioner_current_zip": address["zip"],
            "beneficiary_first_name": scenario.beneficiary_first_name,
            "beneficiary_last_name": scenario.beneficiary_last_name,
            "beneficiary_middle_name": "",
            "beneficiary_email": beneficiary_email,
            "beneficiary_phone": "0000002000",
            "beneficiary_mobile_phone": "0000002000",
            "beneficiary_country_of_birth": scenario.beneficiary_country,
            "beneficiary_country_of_citizenship": scenario.beneficiary_country,
            "beneficiary_current_address_line1": address["line1"],
            "beneficiary_current_address_line2": address["line2"],
            "beneficiary_current_city": address["city"],
            "beneficiary_current_state": address["state"],
            "beneficiary_current_zip": address["zip"],
            "beneficiary_mailing_address_line1": address["line1"],
            "beneficiary_mailing_address_line2": address["line2"],
            "beneficiary_mailing_city": address["city"],
            "beneficiary_mailing_state": address["state"],
            "beneficiary_mailing_zip": address["zip"],
            "beneficiary_mailing_country": "United States",
            "first_marriage_for_both": scenario.first_marriage_for_both,
            "beneficiary_marriage_count": 1 if scenario.first_marriage_for_both else 2,
            "wants_i765": scenario.wants_i765,
            "wants_i131": scenario.wants_i131,
            "needs_translation": scenario.needs_translation,
            "annual_income": scenario.annual_income,
            "i864_household_income": scenario.annual_income,
            "i864_tax_income_1": scenario.annual_income,
            "i864_tax_income_2": scenario.annual_income - 4000,
            "i864_tax_income_3": scenario.annual_income - 8000,
            "g1145_last_name": scenario.beneficiary_last_name,
            "g1145_first_name": scenario.beneficiary_first_name,
            "g1145_middle_name": "",
            "g1145_email": beneficiary_email,
            "g1145_mobile_phone": "0000002000",
            "reviewed_current_fees": True,
            "reviewed_current_form_editions": True,
        }
    )
    answers.update(scenario.extra_answers)
    return answers


def _create_case(session: Session, scenario: PacketScenario, answers: dict[str, Any]) -> CaseRecord:
    case = CaseRecord(
        case_name=scenario.case_name,
        workflow_type="marriage_concurrent",
        petitioner_email=answers["petitioner_email"],
        beneficiary_email=answers["beneficiary_email"],
        country_of_focus=scenario.beneficiary_country[:8].upper(),
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


def _seed_valid_uploads(session: Session, case: CaseRecord, scenario: PacketScenario) -> int:
    upload_dir = Path("storage/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    items = list(
        session.exec(
            select(CaseChecklistItem)
            .where(CaseChecklistItem.case_id == case.id)
            .order_by(CaseChecklistItem.sort_order.asc())
        )
    )
    upload_count = 0
    now = datetime.now(UTC)
    for item in items:
        if item.applicability == "not_applicable" or item.code.startswith("review_"):
            continue
        original_filename = f"{scenario.slug}-{item.code}.pdf"
        stored_filename = f"{case.id}-{original_filename}"
        stored_path = upload_dir / stored_filename
        write_seed_placeholder_pdf(
            stored_path,
            section=packet_section_for_checklist_code(item.code),
            category=item.category,
            label=item.label,
            code=item.code,
        )

        upload = UploadedDocument(
            case_id=case.id,
            checklist_item_code=item.code,
            original_filename=original_filename,
            stored_filename=stored_filename,
            mime_type="application/pdf",
            file_size=stored_path.stat().st_size,
            upload_status="confirmed",
            review_status="reviewed",
            ocr_status="complete",
            extraction_confidence=1.0,
            document_type=item.code,
            document_language="spanish" if scenario.needs_translation and "birth" in item.code else "english",
            requires_translation=scenario.needs_translation and item.code in {"beneficiary_birth_certificate"},
            has_translation=scenario.needs_translation
            and item.code in {"beneficiary_birth_certificate", "translation_certification"},
            extracted_fields={},
            updated_at=now,
        )
        session.add(upload)
        upload_count += 1
    session.commit()
    return upload_count


def _mark_applicable_checklist_complete(session: Session, case_id: Any) -> None:
    items = list(session.exec(select(CaseChecklistItem).where(CaseChecklistItem.case_id == case_id)))
    for item in items:
        if item.applicability == "not_applicable":
            continue
        item.completion_status = ChecklistProgressStatus.complete.value
        item.updated_at = datetime.now(UTC)
        session.add(item)
    session.commit()


def _seed_scenario(session: Session, scenario: PacketScenario, generate_packets: bool) -> dict[str, Any]:
    answers = _scenario_answers(scenario)
    case = _create_case(session, scenario, answers)
    upsert_intake_step(session, case.id, f"packet_scenario:{scenario.slug}", answers)
    _seed_i485(session, case, answers)
    _seed_supplemental_form(session, case, "i864", answers)
    if scenario.wants_i765:
        _seed_supplemental_form(session, case, "i765", answers)
    if scenario.wants_i131:
        _seed_supplemental_form(session, case, "i131", answers)
    session.commit()

    checklist_items, facts = generate_checklist(session, case.id)
    upload_count = _seed_valid_uploads(session, case, scenario)
    checklist_items, facts = generate_checklist(session, case.id)
    _mark_applicable_checklist_complete(session, case.id)
    qa_issues, qa_summary = run_qa(session, case.id)
    _mark_applicable_checklist_complete(session, case.id)

    packet_summary: dict[str, Any] | None = None
    if generate_packets:
        packet = assemble_packet_pdf(
            session=session,
            case_id=case.id,
            state_code=scenario.state_code,
            carrier=scenario.carrier,
            allow_incomplete=True,
        )
        packet_summary = {
            "generated_pdf": str(packet.output_path),
            "page_count": len(PdfReader(packet.output_path).pages),
            "included_count": len(packet.included_documents),
            "generated_form_count": len(
                [document for document in packet.included_documents if document["source_type"] == "generated_form"]
            ),
            "upload_count": len(
                [document for document in packet.included_documents if document["source_type"] == "upload"]
            ),
            "skipped_count": len(packet.skipped_documents),
            "lockbox": packet.mailing_recommendation["lockbox"] if packet.mailing_recommendation else None,
            "carrier": packet.mailing_recommendation["carrier"] if packet.mailing_recommendation else None,
        }

    return {
        "slug": scenario.slug,
        "case_id": str(case.id),
        "case_name": case.case_name,
        "state_code": scenario.state_code,
        "carrier": scenario.carrier,
        "wants_i765": scenario.wants_i765,
        "wants_i131": scenario.wants_i131,
        "needs_translation": scenario.needs_translation,
        "first_marriage_for_both": scenario.first_marriage_for_both,
        "applicable_checklist_items": len(
            [item for item in checklist_items if item.applicability != "not_applicable"]
        ),
        "seeded_valid_uploads": upload_count,
        "facts": {
            "concurrent_filing_eligible": facts.get("concurrent_filing_eligible"),
            "wants_i765": facts.get("wants_i765"),
            "wants_i131": facts.get("wants_i131"),
            "needs_translation": facts.get("needs_translation"),
            "complex_case": facts.get("complex_case"),
        },
        "qa_issue_count": len(qa_issues),
        "qa_summary": qa_summary,
        "packet": packet_summary,
    }


def main() -> None:
    args = build_parser().parse_args()
    create_db_and_tables()
    generate_packets = not args.no_generate_packets

    with Session(engine) as session:
        results = [_seed_scenario(session, scenario, generate_packets) for scenario in SCENARIOS]

    base_url = args.web_base_url.rstrip("/")
    payload = {
        "scenarios": [
            {
                **result,
                "packet_url": f"{base_url}/packet-assembly?caseId={result['case_id']}",
                "case_url": f"{base_url}/?caseId={result['case_id']}",
            }
            for result in results
        ]
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
