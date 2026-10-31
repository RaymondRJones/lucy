from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pypdf import PdfReader
from sqlmodel import Session, select

from app.cli.seed_happy_path import _sample_answers, _seed_i485, _seed_supplemental_form
from app.cli.seed_placeholder_pdf import packet_section_for_checklist_code, write_seed_placeholder_pdf
from app.core.config import settings
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
    i130_filing_status: str = "not_filed"
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
            "beneficiary_prior_marriages": [
                {
                    "family_name": "Example",
                    "given_name": "Former",
                    "marriage_date": "2015-06-01",
                    "end_date": "2021-03-15",
                    "how_ended": "divorced",
                }
            ],
            "beneficiary_prior_marriage_termination_date": "2021-08-20",
            "i131_travel_purpose": "Short family visit for a parent's scheduled medical procedure.",
            "i131_countries_to_visit": "Mexico",
            "i131_expected_trip_length": "10 days",
        },
    ),
    PacketScenario(
        slug="co-pending-i130",
        case_name="Packet scenario - Colorado I-485 after I-130 already pending",
        state_code="CO",
        carrier="usps",
        petitioner_first_name="Robin",
        petitioner_last_name="Hayes",
        beneficiary_first_name="Quinn",
        beneficiary_last_name="Hayes",
        beneficiary_country="Kenya",
        city="Denver",
        state="CO",
        zip_code="80202",
        wants_i765=True,
        wants_i131=False,
        needs_translation=False,
        annual_income=79000,
        i130_filing_status="pending",
        extra_answers={"i130_receipt_number": "IOE0000000000"},
    ),
    PacketScenario(
        slug="wa-public-benefit-history",
        case_name="Packet scenario - Washington means-tested benefit on 09/18/26 I-485",
        state_code="WA",
        carrier="usps",
        petitioner_first_name="Morgan",
        petitioner_last_name="Lee",
        beneficiary_first_name="Dana",
        beneficiary_last_name="Lee",
        beneficiary_country="Philippines",
        city="Seattle",
        state="WA",
        zip_code="98101",
        wants_i765=True,
        wants_i131=False,
        needs_translation=False,
        annual_income=64000,
        extra_answers={
            "public_charge_family_status": "Married; 2 people in household",
            "certifications_licenses_skills": "Licensed practical nurse\nTagalog and English fluency",
            "received_means_tested_public_benefit": True,
            "means_tested_benefit_history": [
                {
                    "benefit_name": "Sample cash aid",
                    "start_date": "2024-02-01",
                    "end_date": "2024-07-31",
                    "dollar_amount": "1800",
                    "reason": "Job loss",
                },
                {
                    "benefit_name": "Sample rental assistance program",
                    "start_date": "2025-01-15",
                    "end_date": "",
                    "dollar_amount": "",
                    "reason": "Income dropped during a long-term illness and treatment.",
                },
            ],
        },
    ),
    PacketScenario(
        slug="il-long-public-charge-answers",
        case_name="Packet scenario - Illinois long public charge answers using Part 14",
        state_code="IL",
        carrier="private",
        petitioner_first_name="Alex",
        petitioner_last_name="Novak",
        beneficiary_first_name="Jamie",
        beneficiary_last_name="Novak",
        beneficiary_country="Poland",
        city="Chicago",
        state="IL",
        zip_code="60601",
        wants_i765=False,
        wants_i131=False,
        needs_translation=True,
        annual_income=58000,
        extra_answers={
            "household_size": 4,
            "public_charge_family_status": (
                "Married and living with my spouse, my spouse's two minor children from a prior relationship, "
                "and no other relatives."
            ),
            "certifications_licenses_skills": "\n".join(f"Sample skill or license {index}" for index in range(1, 11)),
            "received_means_tested_public_benefit": True,
            "means_tested_benefit_history": [
                {
                    "benefit_name": f"Sample benefit program {index}",
                    "start_date": f"202{index}-01-01",
                    "end_date": f"202{index}-06-30",
                    "dollar_amount": str(index * 100),
                    "reason": "Income loss",
                }
                for index in range(1, 7)
            ],
        },
    ),
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seed varied local packet-assembly test cases with real mergeable PDF uploads."
    )
    parser.add_argument("--web-base-url", default="http://localhost:3000")
    parser.add_argument("--no-generate-packets", action="store_true")
    parser.add_argument("--only", nargs="+", metavar="SLUG", help="Seed only these scenario slugs.")
    return parser


def _safe_email(name: str, slug: str) -> str:
    local = name.lower().replace(" ", ".")
    return f"{local}.{slug.replace('-', '.')}@example.com"


def _scenario_answers(scenario: PacketScenario) -> dict[str, Any]:
    answers = _sample_answers()
    beneficiary_email = _safe_email(scenario.beneficiary_first_name, scenario.slug)
    petitioner_email = _safe_email(scenario.petitioner_first_name, scenario.slug)
    address = {
        "line1": f"100 {scenario.city} Avenue",
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
            "i130_filing_status": scenario.i130_filing_status,
            "petitioner_physical_address_line1": address["line1"],
            "petitioner_physical_address_line2": address["line2"],
            "petitioner_physical_city": address["city"],
            "petitioner_physical_state": address["state"],
            "petitioner_physical_zip": address["zip"],
            "beneficiary_intended_us_address_line1": address["line1"],
            "beneficiary_intended_us_address_line2": address["line2"],
            "beneficiary_intended_us_city": address["city"],
            "beneficiary_intended_us_state": address["state"],
            "beneficiary_intended_us_zip": address["zip"],
            "beneficiary_last_shared_address_line1": address["line1"],
            "beneficiary_last_shared_address_line2": address["line2"],
            "beneficiary_last_shared_city": address["city"],
            "beneficiary_last_shared_state": address["state"],
            "beneficiary_last_shared_zip": address["zip"],
            "beneficiary_adjustment_city": address["city"],
            "beneficiary_adjustment_state": address["state"],
            "petitioner_spouse1_first_name": scenario.beneficiary_first_name,
            "beneficiary_spouse1_last_name": scenario.petitioner_last_name,
            "beneficiary_spouse1_first_name": scenario.petitioner_first_name,
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
    upload_dir = settings.upload_dir
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
    if scenario.i130_filing_status == "not_filed":
        _seed_supplemental_form(session, case, "i130", answers)
        _seed_supplemental_form(session, case, "i130a", answers)
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
    scenarios = [scenario for scenario in SCENARIOS if not args.only or scenario.slug in args.only]

    with Session(engine) as session:
        results = [_seed_scenario(session, scenario, generate_packets) for scenario in scenarios]

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
