from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from pypdf import PdfReader, PdfWriter
from sqlmodel import Session, SQLModel, create_engine

from app.content.packet_mailing import mailing_recommendation_for_location
from app.content.packet_ordering import PACKET_OUTLINE_SOURCE_PATH
from app.core.config import settings
from app.models.entities import CaseChecklistItem, CaseRecord, UploadedDocument
from app.services import packet_assembly
from app.services.intake import derive_case_facts, get_merged_case_intake, upsert_intake_step
from app.services.packet_assembly import _packet_form_sequence, assemble_packet_pdf


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def create_case(session: Session) -> CaseRecord:
    case = CaseRecord(case_name="Packet assembly case", workflow_type="marriage_concurrent")
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


def write_one_page_pdf(path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with path.open("wb") as handle:
        writer.write(handle)


def add_checklist_item(session: Session, case: CaseRecord, code: str, sort_order: int = 0) -> None:
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
            what_to_save_now="test",
            sort_order=sort_order,
        )
    )


def add_confirmed_upload(
    session: Session,
    case: CaseRecord,
    upload_dir: Path,
    code: str,
    created_at: datetime,
) -> None:
    path = upload_dir / f"{code}.pdf"
    write_one_page_pdf(path)
    session.add(
        UploadedDocument(
            case_id=case.id,
            checklist_item_code=code,
            original_filename=f"{code}.pdf",
            stored_filename=path.name,
            mime_type="application/pdf",
            file_size=path.stat().st_size,
            upload_status="confirmed",
            created_at=created_at,
        )
    )


def test_packet_mailing_routes_california_to_chicago_lockbox():
    recommendation = mailing_recommendation_for_location("CA", "usps")

    assert recommendation is not None
    assert recommendation["lockbox"] == "USCIS Chicago Lockbox"
    assert recommendation["address_lines"] == [
        "USCIS",
        "Attn: AOS",
        "P.O. Box 805887",
        "Chicago, IL 60680",
    ]
    assert recommendation["source_last_reviewed"] == "2024-10-11"


def test_packet_mailing_routes_texas_private_carrier_to_dallas_lockbox():
    recommendation = mailing_recommendation_for_location("Texas", "private")

    assert recommendation is not None
    assert recommendation["lockbox"] == "USCIS Dallas Lockbox"
    assert "Lewisville, TX 75067-8003" in recommendation["address_lines"]


def test_packet_assembly_merges_valid_uploads_and_reports_invalid_pdfs(tmp_path, monkeypatch):
    session = make_session()
    case = create_case(session)
    monkeypatch.setattr(settings, "upload_dir", tmp_path)

    valid_upload_path = tmp_path / "valid-evidence.pdf"
    invalid_upload_path = tmp_path / "invalid-evidence.pdf"
    write_one_page_pdf(valid_upload_path)
    invalid_upload_path.write_text("not a real pdf")

    session.add(
        CaseChecklistItem(
            case_id=case.id,
            code="marriage_certificate",
            category="civil_document",
            label="Marriage certificate",
            applicability="required",
            completion_status="uploaded",
            owner_role="shared",
            description="Marriage certificate",
            why_needed="Proof of marriage",
            what_to_save_now="Marriage certificate PDF",
            sort_order=1,
        )
    )
    session.add(
        UploadedDocument(
            case_id=case.id,
            checklist_item_code="marriage_certificate",
            original_filename="valid-evidence.pdf",
            stored_filename=valid_upload_path.name,
            mime_type="application/pdf",
            file_size=valid_upload_path.stat().st_size,
            upload_status="confirmed",
        )
    )
    session.add(
        UploadedDocument(
            case_id=case.id,
            checklist_item_code="marriage_certificate",
            original_filename="invalid-evidence.pdf",
            stored_filename=invalid_upload_path.name,
            mime_type="application/pdf",
            file_size=invalid_upload_path.stat().st_size,
            upload_status="confirmed",
        )
    )
    session.commit()

    result = assemble_packet_pdf(
        session=session,
        case_id=case.id,
        state_code="CA",
        carrier="usps",
        include_generated_forms=False,
        output_dir=tmp_path / "generated",
    )

    assert result.output_path.exists()
    assert result.manifest_path.exists()
    assert len(PdfReader(result.output_path).pages) == 1
    assert result.total_page_count == 1
    assert [document["filename"] for document in result.included_documents] == ["valid-evidence.pdf"]
    assert len(result.skipped_documents) == 1
    assert result.skipped_documents[0]["filename"] == "invalid-evidence.pdf"
    assert result.mailing_recommendation is not None
    assert result.mailing_recommendation["lockbox"] == "USCIS Chicago Lockbox"

    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["case_id"] == str(case.id)
    assert manifest["generated_pdf"].endswith("-full-packet.pdf")
    assert manifest["total_page_count"] == 1
    assert manifest["selected_carrier"] == "usps"
    assert manifest["lockbox_source_last_reviewed"] == "2024-10-11"
    assert manifest["packet_outline_source_path"] == PACKET_OUTLINE_SOURCE_PATH
    assert manifest["packet_assembly_guidance_verified_on"] == "2026-05-09"
    assert manifest["scanner_friendly_printing_guidance"]["payment_first_when_present"] is True
    assert "insertable tab dividers" in manifest["scanner_friendly_printing_guidance"]["avoid_when_printing"]
    assert manifest["included_document_count"] == 1
    assert manifest["skipped_document_count"] == 1
    assert manifest["included_documents"][0]["section"] == "I-485 section"


def test_packet_assembly_reports_incomplete_requested_uploads(tmp_path, monkeypatch):
    session = make_session()
    case = create_case(session)
    monkeypatch.setattr(settings, "upload_dir", tmp_path)

    add_checklist_item(session, case, "marriage_certificate", 1)
    add_checklist_item(session, case, "photos_together", 2)
    add_confirmed_upload(session, case, tmp_path, "marriage_certificate", datetime.now(UTC))
    session.add(
        UploadedDocument(
            case_id=case.id,
            checklist_item_code="photos_together",
            original_filename="Relationship Evidence Photo Album.pdf",
            mime_type="application/pdf",
            upload_status="requested",
            created_at=datetime.now(UTC) + timedelta(minutes=1),
        )
    )
    session.commit()

    result = assemble_packet_pdf(
        session=session,
        case_id=case.id,
        state_code="CA",
        carrier="usps",
        include_generated_forms=False,
        output_dir=tmp_path / "generated",
    )

    assert [document["checklist_item_code"] for document in result.included_documents] == ["marriage_certificate"]
    skipped_photos = [
        document for document in result.skipped_documents if document["checklist_item_code"] == "photos_together"
    ]
    assert len(skipped_photos) == 1
    assert skipped_photos[0]["section"] == "I-485 section"
    assert "file was never received" in skipped_photos[0]["reason"]


def test_packet_assembly_ignores_stale_incomplete_upload_when_code_has_confirmed_file(tmp_path, monkeypatch):
    session = make_session()
    case = create_case(session)
    monkeypatch.setattr(settings, "upload_dir", tmp_path)

    add_checklist_item(session, case, "photos_together", 1)
    session.add(
        UploadedDocument(
            case_id=case.id,
            checklist_item_code="photos_together",
            original_filename="stale-photo-upload.pdf",
            mime_type="application/pdf",
            upload_status="requested",
            created_at=datetime.now(UTC),
        )
    )
    add_confirmed_upload(session, case, tmp_path, "photos_together", datetime.now(UTC) + timedelta(minutes=1))
    session.commit()

    result = assemble_packet_pdf(
        session=session,
        case_id=case.id,
        state_code="CA",
        carrier="usps",
        include_generated_forms=False,
        output_dir=tmp_path / "generated",
    )

    assert [document["checklist_item_code"] for document in result.included_documents] == ["photos_together"]
    assert not result.skipped_documents


def test_packet_assembly_normalizes_upload_when_pypdf_cannot_merge(tmp_path, monkeypatch):
    session = make_session()
    case = create_case(session)
    monkeypatch.setattr(settings, "upload_dir", tmp_path)

    add_checklist_item(session, case, "beneficiary_birth_certificate", 1)
    original_path = tmp_path / "beneficiary_birth_certificate.pdf"
    write_one_page_pdf(original_path)
    session.add(
        UploadedDocument(
            case_id=case.id,
            checklist_item_code="beneficiary_birth_certificate",
            original_filename=original_path.name,
            stored_filename=original_path.name,
            mime_type="application/pdf",
            file_size=original_path.stat().st_size,
            upload_status="confirmed",
            created_at=datetime.now(UTC),
        )
    )
    session.commit()

    real_append_pdf_pages = packet_assembly._append_pdf_pages

    def fail_original_upload_once(writer, path):
        if path == original_path:
            raise ValueError("encrypted stream could not be copied")
        return real_append_pdf_pages(writer, path)

    def normalize_upload(source_path, output_dir, upload_id):
        normalized_path = output_dir / f"{upload_id}-normalized.pdf"
        write_one_page_pdf(normalized_path)
        return normalized_path

    monkeypatch.setattr(packet_assembly, "_append_pdf_pages", fail_original_upload_once)
    monkeypatch.setattr(packet_assembly, "_normalize_pdf_for_merge", normalize_upload)

    result = assemble_packet_pdf(
        session=session,
        case_id=case.id,
        state_code="CA",
        carrier="usps",
        include_generated_forms=False,
        output_dir=tmp_path / "generated",
    )

    assert [document["checklist_item_code"] for document in result.included_documents] == [
        "beneficiary_birth_certificate"
    ]
    assert not result.skipped_documents
    assert len(PdfReader(result.output_path).pages) == 1


def test_packet_form_sequence_respects_optional_work_and_travel_forms():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {
            "petitioner_citizenship_status": "us_citizen",
            "beneficiary_location": "usa",
            "beneficiary_entered_us_legally": True,
            "first_marriage_for_both": True,
            "wants_i765": False,
            "wants_i131": False,
        },
    )

    facts = derive_case_facts(get_merged_case_intake(session, case.id))

    assert _packet_form_sequence(session, case.id, facts) == ["g1145", "i485", "i864"]

    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {
            "petitioner_citizenship_status": "us_citizen",
            "beneficiary_location": "usa",
            "beneficiary_entered_us_legally": True,
            "first_marriage_for_both": True,
            "wants_i765": True,
            "wants_i131": True,
        },
    )
    facts = derive_case_facts(get_merged_case_intake(session, case.id))

    assert _packet_form_sequence(session, case.id, facts) == [
        "g1145",
        "i485",
        "i864",
        "i765",
        "i131",
    ]


def test_packet_assembly_orders_i485_uploads_and_excludes_i130_materials(tmp_path, monkeypatch):
    session = make_session()
    case = create_case(session)
    monkeypatch.setattr(settings, "upload_dir", tmp_path)

    codes = [
        "joint_lease",
        "sponsor_tax_return",
        "form_i130",
        "beneficiary_birth_certificate",
        "form_i485",
        "marriage_certificate",
    ]
    now = datetime.now(UTC)
    for index, code in enumerate(codes):
        path = tmp_path / f"{code}.pdf"
        write_one_page_pdf(path)
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
                what_to_save_now="test",
                sort_order=index,
            )
        )
        session.add(
            UploadedDocument(
                case_id=case.id,
                checklist_item_code=code,
                original_filename=f"{code}.pdf",
                stored_filename=path.name,
                mime_type="application/pdf",
                file_size=path.stat().st_size,
                upload_status="confirmed",
                created_at=now + timedelta(minutes=index),
            )
        )
    session.commit()

    result = assemble_packet_pdf(
        session=session,
        case_id=case.id,
        state_code="CA",
        carrier="usps",
        include_generated_forms=False,
        output_dir=tmp_path / "generated",
    )

    assert [document["checklist_item_code"] for document in result.included_documents] == [
        "form_i485",
        "beneficiary_birth_certificate",
        "marriage_certificate",
        "joint_lease",
        "sponsor_tax_return",
    ]
    assert {document["checklist_item_code"] for document in result.skipped_documents} == {
        "form_i130",
    }


def test_packet_assembly_does_not_reuse_stale_generated_payment_pdfs(tmp_path):
    session = make_session()
    case = create_case(session)
    for index, code in enumerate(["form_i130", "form_i485", "form_i765"]):
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
                what_to_save_now="test",
                sort_order=index,
            )
        )
    session.commit()

    write_one_page_pdf(tmp_path / f"{case.id}-i-130-g-1450.pdf")
    write_one_page_pdf(tmp_path / f"{case.id}-i-485-g-1450.pdf")
    write_one_page_pdf(tmp_path / f"{case.id}-i-765-g-1450.pdf")

    result = assemble_packet_pdf(
        session=session,
        case_id=case.id,
        state_code="CA",
        carrier="usps",
        include_generated_forms=True,
        output_dir=tmp_path,
    )

    assert result.included_documents[0]["source_type"] == "generated_cover_letter"
    assert "RE: Form I-485 Adjustment of Status (Marriage-Based)" in (
        PdfReader(result.output_path).pages[0].extract_text()
    )
    assert not any(document["source_type"] == "generated_payment_form" for document in result.included_documents)
    assert {
        document["checklist_item_code"]
        for document in result.skipped_documents
        if document["source_type"] == "generated_payment_form"
    } == {"form_i485", "form_i765"}
    assert all("No fresh G-1450 or G-1650 was generated" in document["reason"] for document in result.skipped_documents)


def test_packet_assembly_includes_uploaded_g1450_payment_pdf(tmp_path, monkeypatch):
    session = make_session()
    case = create_case(session)
    monkeypatch.setattr(settings, "upload_dir", tmp_path)

    add_checklist_item(session, case, "payment_g1450", 0)
    add_checklist_item(session, case, "form_i485", 1)
    add_confirmed_upload(
        session,
        case,
        tmp_path,
        "payment_g1450",
        datetime.now(UTC),
    )
    session.commit()

    result = assemble_packet_pdf(
        session=session,
        case_id=case.id,
        state_code="CA",
        carrier="usps",
        include_generated_forms=True,
        output_dir=tmp_path / "generated",
    )

    assert result.included_documents[0]["section"] == "Payment"
    assert result.included_documents[0]["source_type"] == "upload"
    assert result.included_documents[0]["checklist_item_code"] == "payment_g1450"
    assert result.included_documents[1]["source_type"] == "generated_cover_letter"
    assert not [
        document
        for document in result.skipped_documents
        if document["source_type"] == "generated_payment_form"
        and document["checklist_item_code"] == "form_i485"
    ]
    assert "Contents of Submission" in PdfReader(result.output_path).pages[1].extract_text()


def test_packet_assembly_skips_uploaded_generated_forms_when_generated_forms_are_included(tmp_path, monkeypatch):
    session = make_session()
    case = create_case(session)
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {
            "petitioner_citizenship_status": "us_citizen",
            "beneficiary_location": "usa",
            "beneficiary_entered_us_legally": True,
            "first_marriage_for_both": True,
            "wants_i765": True,
            "wants_i131": True,
        },
    )

    generated_upload_codes = ["form_g1145", "form_i485", "form_i864", "form_i765", "form_i131"]
    now = datetime.now(UTC)
    for index, code in enumerate(generated_upload_codes):
        add_checklist_item(session, case, code, index)
        add_confirmed_upload(session, case, tmp_path, code, now + timedelta(minutes=index))
    session.commit()

    result = assemble_packet_pdf(
        session=session,
        case_id=case.id,
        state_code="CA",
        carrier="usps",
        include_generated_forms=True,
        output_dir=tmp_path / "generated",
    )

    generated_form_keys = {
        document["form_key"]
        for document in result.included_documents
        if document["source_type"] == "generated_form"
    }
    assert {"g1145", "i485", "i864", "i765", "i131"} <= generated_form_keys
    assert not any(
        document["source_type"] == "upload" and document["checklist_item_code"] in generated_upload_codes
        for document in result.included_documents
    )
    skipped_generated_uploads = [
        document
        for document in result.skipped_documents
        if document["source_type"] == "upload" and document["checklist_item_code"] in generated_upload_codes
    ]
    assert {document["checklist_item_code"] for document in skipped_generated_uploads} == set(generated_upload_codes)
    assert all("avoid duplicate forms" in document["reason"] for document in skipped_generated_uploads)


def test_packet_cover_letter_uses_human_readable_items_without_filenames(tmp_path, monkeypatch):
    session = make_session()
    case = create_case(session)
    monkeypatch.setattr(settings, "upload_dir", tmp_path)

    for index, code in enumerate(["form_i485", "beneficiary_i94", "joint_lease"]):
        add_checklist_item(session, case, code, index)
    raw_upload_filename = "sample-case-id-ca-full-translation-beneficiary_i94.pdf"
    stored_upload_filename = f"upload-{raw_upload_filename}"
    stored_upload_path = tmp_path / stored_upload_filename
    write_one_page_pdf(stored_upload_path)
    session.add(
        UploadedDocument(
            case_id=case.id,
            checklist_item_code="beneficiary_i94",
            original_filename=raw_upload_filename,
            stored_filename=stored_upload_filename,
            mime_type="application/pdf",
            file_size=stored_upload_path.stat().st_size,
            upload_status="confirmed",
            created_at=datetime.now(UTC),
        )
    )
    add_confirmed_upload(session, case, tmp_path, "joint_lease", datetime.now(UTC) + timedelta(minutes=1))
    session.commit()

    result = assemble_packet_pdf(
        session=session,
        case_id=case.id,
        state_code="CA",
        carrier="usps",
        include_generated_forms=True,
        output_dir=tmp_path / "generated",
    )

    reader = PdfReader(result.output_path)
    cover_page_count = result.included_documents[0]["page_count"]
    cover_text = "\n".join(page.extract_text() or "" for page in reader.pages[:cover_page_count])
    packet_text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert "Completed and signed Form I-485" in cover_text
    assert "Copy of Form I-94" in cover_text
    assert "Evidence of bona fide marriage:" in cover_text
    assert "Lease agreement" in cover_text
    assert "Thank you for your time and consideration" in cover_text
    assert raw_upload_filename not in cover_text
    assert "sample-case-id" not in cover_text
    assert "Section Index Page" in packet_text
    assert "Documents queued for this section" in packet_text
    assert "Copy of Form I-94" in packet_text
    assert "Lease agreement" in packet_text
    assert "do not use tabs, binders, folders" in packet_text


def test_packet_assembly_follows_complete_package_outline_for_upload_sections(tmp_path, monkeypatch):
    session = make_session()
    case = create_case(session)
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {
            "petitioner_citizenship_status": "us_citizen",
            "beneficiary_location": "usa",
            "beneficiary_entered_us_legally": True,
            "first_marriage_for_both": True,
            "wants_i765": True,
            "wants_i131": True,
        },
    )

    codes = [
        "sponsor_tax_return",
        "form_i131",
        "beneficiary_i94",
        "form_i130",
        "travel_explanation_i131",
        "medical_exam_i693",
        "form_i765",
        "beneficiary_passport_bio",
        "form_i485",
        "beneficiary_passport_photos",
        "i130_receipt_notice",
        "joint_bank_statement",
        "joint_lease",
        "utility_bills",
        "photos_together",
    ]
    now = datetime.now(UTC)
    for index, code in enumerate(codes):
        add_checklist_item(session, case, code, index)
        add_confirmed_upload(session, case, tmp_path, code, now + timedelta(minutes=index))
    session.commit()

    result = assemble_packet_pdf(
        session=session,
        case_id=case.id,
        state_code="CA",
        carrier="usps",
        include_generated_forms=False,
        output_dir=tmp_path / "generated",
    )

    assert [
        (document["section"], document["checklist_item_code"])
        for document in result.included_documents
    ] == [
        ("I-485 section", "beneficiary_passport_photos"),
        ("I-485 section", "form_i485"),
        ("I-485 section", "beneficiary_passport_bio"),
        ("I-485 section", "beneficiary_i94"),
        ("I-485 section", "i130_receipt_notice"),
        ("I-485 section", "joint_bank_statement"),
        ("I-485 section", "joint_lease"),
        ("I-485 section", "utility_bills"),
        ("I-485 section", "photos_together"),
        ("I-864 section", "sponsor_tax_return"),
        ("I-693 medical section", "medical_exam_i693"),
        ("I-765 section", "form_i765"),
        ("I-131 section", "form_i131"),
        ("I-131 section", "travel_explanation_i131"),
    ]
    assert result.total_page_count == 14
    assert [(document["section"], document["checklist_item_code"]) for document in result.skipped_documents] == [
        ("Additional uploaded documents", "form_i130")
    ]


def test_packet_assembly_manifest_indexes_cover_letter_and_outline_source(tmp_path):
    session = make_session()
    case = create_case(session)
    for index, code in enumerate(["form_i485", "form_i765"]):
        add_checklist_item(session, case, code, index)
    session.commit()
    write_one_page_pdf(tmp_path / f"{case.id}-i-485-g-1450.pdf")
    write_one_page_pdf(tmp_path / f"{case.id}-i-765-g-1450.pdf")

    result = assemble_packet_pdf(
        session=session,
        case_id=case.id,
        state_code="CA",
        carrier="usps",
        include_generated_forms=True,
        g1450_payment_payload={
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
        output_dir=tmp_path,
    )

    manifest = json.loads(result.manifest_path.read_text())

    assert manifest["packet_outline_source_path"] == PACKET_OUTLINE_SOURCE_PATH
    assert manifest["packet_assembly_guidance_verified_on"] == "2026-05-09"
    assert manifest["included_documents"][0]["section"] == "Payment"
    assert manifest["included_documents"][0]["checklist_item_code"] == "form_i485"
    assert manifest["included_documents"][1]["section"] == "Payment"
    assert manifest["included_documents"][1]["checklist_item_code"] == "form_i765"
    assert manifest["included_documents"][2]["source_type"] == "generated_cover_letter"
    assert manifest["included_documents"][2]["section"] == "Cover letter"
    assert any(
        document["source_type"] == "generated_section_index"
        and document["section"] == "I-485 section"
        for document in manifest["included_documents"]
    )


def test_packet_assembly_can_generate_forms_only_without_supporting_evidence(tmp_path, monkeypatch):
    session = make_session()
    case = create_case(session)
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {
            "petitioner_citizenship_status": "us_citizen",
            "beneficiary_location": "usa",
            "beneficiary_entered_us_legally": True,
            "first_marriage_for_both": True,
        },
    )
    for index, code in enumerate(["form_i485", "form_i864", "marriage_certificate"]):
        add_checklist_item(session, case, code, index)
    add_confirmed_upload(session, case, tmp_path, "marriage_certificate", datetime.now(UTC))
    session.commit()

    output_dir = tmp_path / "generated"
    output_dir.mkdir()
    write_one_page_pdf(output_dir / f"{case.id}-i-485-g-1450.pdf")

    result = assemble_packet_pdf(
        session=session,
        case_id=case.id,
        state_code="CA",
        carrier="usps",
        include_generated_forms=True,
        include_supporting_evidence=False,
        output_dir=output_dir,
    )

    assert result.output_path.exists()
    assert all(document["source_type"] != "upload" for document in result.included_documents)
    assert all(document["source_type"] != "generated_section_index" for document in result.included_documents)
    assert not any(document["checklist_item_code"] == "marriage_certificate" for document in result.included_documents)
    assert not any(document["checklist_item_code"] == "marriage_certificate" for document in result.skipped_documents)
    assert any("forms-only packet" in warning for warning in result.warnings)

    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["include_supporting_evidence"] is False
    assert all(document["source_type"] != "upload" for document in manifest["included_documents"])


def _append_generated_form_with_error(monkeypatch, error: Exception) -> list[dict]:
    def fail(**_kwargs):
        raise error

    monkeypatch.setattr(packet_assembly, "_generate_packet_form", fail)
    skipped: list[dict] = []
    packet_assembly._append_generated_form_document(
        writer=PdfWriter(),
        session=None,
        case_id=uuid4(),
        values={},
        form_key="i485",
        section="I-485 section",
        allow_incomplete=False,
        included_documents=[],
        skipped_documents=skipped,
        warnings=[],
    )
    return skipped


def test_expected_form_generation_failure_is_reported_as_skipped(monkeypatch) -> None:
    skipped = _append_generated_form_with_error(monkeypatch, ValueError("I-485 PDF template not found"))

    assert skipped[0]["reason"] == "I-485 PDF template not found"


def test_code_bug_in_form_generation_fails_instead_of_omitting_the_form(monkeypatch) -> None:
    with pytest.raises(AttributeError):
        _append_generated_form_with_error(monkeypatch, AttributeError("bug"))
