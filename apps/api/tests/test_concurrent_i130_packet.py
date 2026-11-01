from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from pdf_form_assertions import pdf_field_values
from pypdf import PdfReader
from test_g1650 import BANK, TEMPLATE, bank_payload
from test_packet_assembly import add_checklist_item, add_confirmed_upload, create_case, make_session

from app.cli.seed_happy_path import seed_supplemental_form
from app.cli.seed_packet_scenarios import SCENARIOS, _create_case, _scenario_answers
from app.core.config import settings
from app.services.checklist import generate_checklist
from app.services.form_ingestion import build_form_fill_preview
from app.services.form_pdf import build_form_pdf_field_payload
from app.services.intake import upsert_intake_step
from app.services.packet_assembly import assemble_packet_pdf


def _seed(session, tmp_path, status: str | None, codes: list[str]):
    case = create_case(session)
    answers = {
        "beneficiary_first_name": "Avery",
        "beneficiary_last_name": "Parker",
        "petitioner_first_name": "Jordan",
        "petitioner_last_name": "Parker",
    }
    if status is not None:
        answers["i130_filing_status"] = status
    upsert_intake_step(session, case.id, "basics", answers)
    now = datetime.now(UTC)
    for index, code in enumerate(codes):
        add_checklist_item(session, case, code, index)
        add_confirmed_upload(session, case, tmp_path, code, now + timedelta(minutes=index))
    session.commit()
    return case


def _assemble(session, case, tmp_path, **kwargs):
    return assemble_packet_pdf(
        session=session,
        case_id=case.id,
        state_code="CA",
        output_dir=tmp_path / "generated",
        **kwargs,
    )


def _sections(result) -> list[tuple[str, str | None]]:
    return [(document["section"], document["checklist_item_code"]) for document in result.included_documents]


EVIDENCE = [
    "petitioner_citizenship_proof",
    "petitioner_passport_photos",
    "beneficiary_passport_photos",
    "marriage_certificate",
    "joint_lease",
    "form_i130",
    "form_i130a",
]


def test_not_filed_status_builds_i130_section_last_with_required_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    session = make_session()
    case = _seed(session, tmp_path, "not_filed", EVIDENCE)

    result = _assemble(session, case, tmp_path, include_generated_forms=False)

    assert _sections(result) == [
        ("I-485 section", "beneficiary_passport_photos"),
        ("I-485 section", "marriage_certificate"),
        ("I-130 section", "form_i130"),
        ("I-130 section", "form_i130a"),
        ("I-130 section", "petitioner_passport_photos"),
        ("I-130 section", "beneficiary_passport_photos"),
        ("I-130 section", "petitioner_citizenship_proof"),
        ("I-130 section", "marriage_certificate"),
        ("I-130 section", "joint_lease"),
    ]
    assert result.skipped_documents == []


def test_generated_i130_forms_replace_uploads_and_join_the_cover_letter(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    session = make_session()
    case = _seed(session, tmp_path, "not_filed", EVIDENCE)

    result = _assemble(session, case, tmp_path)

    generated = [document["form_key"] for document in result.included_documents if document["source_type"] == "generated_form"]
    assert generated[-2:] == ["i130", "i130a"]
    assert {"form_i130", "form_i130a"} <= {document["checklist_item_code"] for document in result.skipped_documents}
    cover = PdfReader(result.output_path).pages[0].extract_text() + PdfReader(result.output_path).pages[1].extract_text()
    assert "RE: Concurrent Forms I-130 and I-485" in cover
    assert "Receipt Number" not in cover
    assert "Forms I-130 and I-130A (Petition for Alien Relative)" in cover


def test_concurrent_packet_adds_i130_fee_to_payment_set(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    session = make_session()
    case = _seed(session, tmp_path, "not_filed", ["form_i130", "form_i485"])

    result = _assemble(
        session, case, tmp_path, g1650_payment_payload=bank_payload(), g1650_template_path=TEMPLATE
    )

    payments = [document for document in result.included_documents if document["section"] == "Payment"]
    assert [document["checklist_item_code"] for document in payments] == ["form_i130", "form_i485"]
    amounts = {
        next(iter(pdf_field_values(Path(document["path"]))[f"{BANK}.AuthorizedPaymentAmt[0]"]))
        for document in payments
    }
    assert amounts == {"675", "1440"}


def test_pending_status_keeps_i485_only_packet_and_skips_petition_materials(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    session = make_session()
    case = _seed(session, tmp_path, "pending", [*EVIDENCE, "i130_receipt_notice"])

    result = _assemble(session, case, tmp_path, include_generated_forms=False)

    assert not any(section == "I-130 section" for section, _code in _sections(result))
    assert ("I-485 section", "i130_receipt_notice") in _sections(result)
    assert ("I-485 section", "joint_lease") in _sections(result)
    assert {document["checklist_item_code"] for document in result.skipped_documents} == {
        "form_i130",
        "form_i130a",
        "petitioner_citizenship_proof",
        "petitioner_passport_photos",
    }


def test_blank_status_warns_instead_of_guessing(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    session = make_session()
    case = _seed(session, tmp_path, None, ["form_i130", "form_i485"])

    result = _assemble(session, case, tmp_path)

    assert not any(section == "I-130 section" for section, _code in _sections(result))
    assert any("I-130 status is not set" in warning for warning in result.warnings)


def test_checklist_requires_petitioner_photos_only_before_i130_is_filed():
    session = make_session()
    not_filed = create_case(session)
    upsert_intake_step(
        session, not_filed.id, "basics", {"petitioner_citizenship_status": "us_citizen", "i130_filing_status": "not_filed"}
    )
    pending = create_case(session)
    upsert_intake_step(
        session, pending.id, "basics", {"petitioner_citizenship_status": "us_citizen", "i130_filing_status": "pending"}
    )
    session.commit()

    def applicability(case):
        return {item.code: item.applicability for item in generate_checklist(session, case.id)[0]}

    assert applicability(not_filed)["petitioner_passport_photos"] != "not_applicable"
    assert applicability(pending)["petitioner_passport_photos"] == "not_applicable"


def test_seeded_concurrent_scenario_answers_are_on_the_standard_path(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    session = make_session()
    scenario = next(item for item in SCENARIOS if item.slug == "ga-core-only")
    case = _create_case(session, scenario, _scenario_answers(scenario))
    answers = _scenario_answers(scenario)
    for form_key in ("i130", "i130a"):
        seed_supplemental_form(session, case, form_key, answers)
    session.commit()

    i130 = build_form_fill_preview(session, case.id, "i130")
    i130a = build_form_fill_preview(session, case.id, "i130a")
    values = {field["question_id"]: field["value"] for field in i130["fields"]}

    assert i130["generation_status"] == "ready_for_user_review"
    assert i130a["generation_status"] == "ready_for_user_review"
    assert values["beneficiary_prior_petition_filed"] == "no"
    assert values["beneficiary_ever_in_united_states"] is True
    assert values["beneficiary_adjustment_state"] == scenario.state
    assert "beneficiary_immigration_proceedings_type" not in values


def test_i130_keeps_us_zip_out_of_foreign_postal_code_field():
    payload = build_form_pdf_field_payload(
        "i130",
        {
            "beneficiary_current_address_line1": "100 Atlanta Avenue",
            "beneficiary_current_zip": "30309",
            "beneficiary_current_postal_code": "30309",
            "beneficiary_current_address": "100 Atlanta Avenue, Atlanta, GA 30309",
        },
    )

    assert payload.text_values["Pt4Line11_ZipCode[0]"] == "30309"
    assert "Pt4Line11_PostalCode[0]" not in payload.text_values
    assert "beneficiary_current_postal_code" not in {item["question_id"] for item in payload.unmapped_answered_questions}
    assert "beneficiary_current_address" not in {item["question_id"] for item in payload.unmapped_answered_questions}


def test_i130_keeps_a_foreign_postal_code():
    payload = build_form_pdf_field_payload(
        "i130", {"beneficiary_current_postal_code": "110111", "beneficiary_current_country": "Colombia"}
    )

    assert payload.text_values["Pt4Line11_PostalCode[0]"] == "110111"


def test_fresh_payment_replaces_uploaded_payment_pdf(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    session = make_session()
    case = _seed(session, tmp_path, "not_filed", ["form_i485", "payment_g1450"])

    result = _assemble(
        session, case, tmp_path, g1650_payment_payload=bank_payload(), g1650_template_path=TEMPLATE
    )

    assert "payment_g1450" not in {document["checklist_item_code"] for document in result.included_documents}
    assert any(
        document["checklist_item_code"] == "payment_g1450" and "avoid paying twice" in document["reason"]
        for document in result.skipped_documents
    )
