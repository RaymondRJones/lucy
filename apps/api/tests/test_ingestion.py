from __future__ import annotations

from pathlib import Path
import shutil
from uuid import UUID

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.entities import OCRStatus, UploadedDocument, UploadStatus
from app.core.config import settings
from app.content.uscis_requirements import USCIS_REQUIREMENT_BY_CHECKLIST_CODE
from app.services.i485 import get_i485_state
from app.services import ingestion as ingestion_service
from app.services.ingestion import InferredDocument, ingest_evidence_directory, scan_document
from app.services.intake import get_merged_case_intake


REPO_ROOT = Path(__file__).resolve().parents[3]
PRIVATE_EVIDENCE_DIR = REPO_ROOT / "MARRIAGE_EVIDENCE"


def require_private_fixture(path: Path) -> None:
    if not path.exists():
        pytest.skip("Private local evidence fixture is not included in the public repository.")


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def make_inferred_document(
    path: Path,
    *,
    checklist_item_code: str | None,
    document_type: str,
    extracted_fields: dict[str, object] | None = None,
    document_language: str = "english",
    has_translation: bool = False,
    requires_translation: bool = False,
    text: str = "stubbed pdf text",
) -> InferredDocument:
    return InferredDocument(
        source_path=path.as_posix(),
        checklist_item_code=checklist_item_code,
        document_type=document_type,
        document_language=document_language,
        has_translation=has_translation,
        requires_translation=requires_translation,
        text=text,
        extracted_fields={
            "source_path": path.as_posix(),
            "ingested_from_filesystem": True,
            **(extracted_fields or {}),
        },
    )


def write_fake_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4\n% public ingest unit-test placeholder\n%%EOF\n")


def configure_tmp_ingest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    upload_dir = repo_root / "storage" / "uploads"
    evidence_dir = repo_root / "MARRIAGE_EVIDENCE"
    upload_dir.mkdir(parents=True)
    evidence_dir.mkdir(parents=True)
    monkeypatch.setattr(settings, "upload_dir", upload_dir)
    return evidence_dir, upload_dir


def test_ingest_evidence_directory_uses_public_deterministic_scan_boundary(tmp_path, monkeypatch):
    evidence_dir, upload_dir = configure_tmp_ingest(monkeypatch, tmp_path)
    pdf_paths = {
        "I-130.pdf": evidence_dir / "I-130.pdf",
        "Sample-Form-I-485.pdf": evidence_dir / "I-485" / "Sample-Form-I-485.pdf",
        "Birth_Certificate.pdf": evidence_dir / "I-485" / "Birth_Certificate.pdf",
        "Translated_Birth_Certificate.pdf": evidence_dir / "I-485" / "Translated_Birth_Certificate.pdf",
    }
    for path in pdf_paths.values():
        write_fake_pdf(path)

    inferred_by_name = {
        "I-130.pdf": make_inferred_document(
            pdf_paths["I-130.pdf"],
            checklist_item_code="form_i130",
            document_type="form_i130",
            extracted_fields={
                "petitioner_first_name": "Jordan",
                "petitioner_last_name": "Petitioner",
                "beneficiary_first_name": "Avery",
                "beneficiary_last_name": "Garcia",
                "marriage_date": "2025-07-20",
                "petitioner_first_marriage_detected": True,
                "edition_matches_current_uscis_requirement": True,
                "satisfies_checklist_codes": ["form_i130"],
            },
        ),
        "Sample-Form-I-485.pdf": make_inferred_document(
            pdf_paths["Sample-Form-I-485.pdf"],
            checklist_item_code="form_i485",
            document_type="form_i485",
            extracted_fields={
                "beneficiary_i94_number": "898715649A4",
                "beneficiary_current_immigration_status": "B2",
                "beneficiary_location": "usa",
                "beneficiary_entered_us_legally": True,
                "beneficiary_first_marriage_detected": True,
                "edition_matches_current_uscis_requirement": True,
                "satisfies_checklist_codes": ["form_i485"],
            },
        ),
        "Birth_Certificate.pdf": make_inferred_document(
            pdf_paths["Birth_Certificate.pdf"],
            checklist_item_code="beneficiary_birth_certificate",
            document_type="civil_birth_record",
            document_language="spanish",
            requires_translation=True,
            extracted_fields={
                "beneficiary_country_of_birth": "CO",
                "satisfies_checklist_codes": ["beneficiary_birth_certificate"],
            },
        ),
        "Translated_Birth_Certificate.pdf": make_inferred_document(
            pdf_paths["Translated_Birth_Certificate.pdf"],
            checklist_item_code="beneficiary_birth_certificate",
            document_type="civil_birth_record",
            document_language="spanish",
            has_translation=True,
            extracted_fields={
                "beneficiary_country_of_birth": "CO",
                "satisfies_checklist_codes": [
                    "beneficiary_birth_certificate",
                    "translation_certification",
                ],
            },
        ),
    }
    monkeypatch.setattr(
        ingestion_service,
        "scan_document",
        lambda path: inferred_by_name[path.name],
    )

    imported_upload_ids: list[UUID] = []

    def fake_import_i485_answers_from_upload(session: Session, case_id: UUID, upload_id: UUID):
        upload = session.get(UploadedDocument, upload_id)
        assert upload is not None
        assert upload.upload_status == UploadStatus.confirmed.value
        assert upload.checklist_item_code == "form_i485"
        imported_upload_ids.append(upload_id)
        return {
            "imported_count": 2,
            "skipped_count": 0,
            "proposals": [{"question_id": "beneficiary_first_name"}, {"question_id": "beneficiary_i94_number"}],
            "upload_id": str(upload_id),
        }

    monkeypatch.setattr(
        ingestion_service,
        "import_i485_answers_from_upload",
        fake_import_i485_answers_from_upload,
    )

    session = make_session()
    summary = ingest_evidence_directory(session, evidence_dir)
    case_id = UUID(summary["case_id"])
    uploads = list(session.exec(select(UploadedDocument).where(UploadedDocument.case_id == case_id)))
    by_filename = {upload.original_filename: upload for upload in uploads}
    merged = get_merged_case_intake(session, case_id)

    assert summary["documents_scanned"] == 4
    assert summary["matched_documents"] == 4
    assert summary["unmatched_documents"] == 0
    assert summary["case_name"] == "Jordan & Avery packet"
    assert summary["i485_import"] == {"imported_count": 2, "skipped_count": 0, "proposal_count": 2}
    assert len(imported_upload_ids) == 1
    assert {upload.upload_status for upload in uploads} == {UploadStatus.confirmed.value}
    assert {upload.ocr_status for upload in uploads} == {OCRStatus.complete.value}
    assert all((upload_dir / str(upload.stored_filename)).exists() for upload in uploads)
    assert by_filename["Birth_Certificate.pdf"].has_translation is True
    assert by_filename["Birth_Certificate.pdf"].requires_translation is False
    assert by_filename["Birth_Certificate.pdf"].extracted_fields["paired_translation_detected"] is True
    assert "translation_certification" in by_filename["Birth_Certificate.pdf"].extracted_fields[
        "satisfies_checklist_codes"
    ]
    assert summary["intake_payload"]["first_marriage_for_both"] is True
    assert summary["intake_payload"]["needs_translation"] is True
    assert summary["intake_payload"]["reviewed_current_form_editions"] is True
    assert merged["beneficiary_i94_number"] == "898715649A4"
    assert merged["country_of_focus"] == "CO"


def test_ingest_evidence_directory_updates_existing_source_upload_without_duplicates(tmp_path, monkeypatch):
    evidence_dir, _ = configure_tmp_ingest(monkeypatch, tmp_path)
    i130_path = evidence_dir / "I-130.pdf"
    write_fake_pdf(i130_path)
    scan_count = 0

    def fake_scan_document(path: Path) -> InferredDocument:
        nonlocal scan_count
        scan_count += 1
        beneficiary_name = "Avery" if scan_count == 1 else "Avery Updated"
        return make_inferred_document(
            path,
            checklist_item_code="form_i130",
            document_type="form_i130",
            extracted_fields={
                "petitioner_first_name": "Jordan",
                "beneficiary_first_name": beneficiary_name,
                "satisfies_checklist_codes": ["form_i130"],
            },
        )

    monkeypatch.setattr(ingestion_service, "scan_document", fake_scan_document)
    session = make_session()

    first_summary = ingest_evidence_directory(session, evidence_dir)
    second_summary = ingest_evidence_directory(session, evidence_dir, case_id=UUID(first_summary["case_id"]))
    case_id = UUID(first_summary["case_id"])
    uploads = list(session.exec(select(UploadedDocument).where(UploadedDocument.case_id == case_id)))
    merged = get_merged_case_intake(session, case_id)

    assert first_summary["documents_scanned"] == 1
    assert second_summary["documents_scanned"] == 1
    assert len(uploads) == 1
    assert uploads[0].version == 1
    assert uploads[0].extracted_fields["beneficiary_first_name"] == "Avery Updated"
    assert merged["beneficiary_first_name"] == "Avery Updated"


def test_scan_i130_extracts_core_relationship_fields():
    fixture_path = PRIVATE_EVIDENCE_DIR / "I-130.pdf"
    require_private_fixture(fixture_path)
    document = scan_document(fixture_path)

    assert document.checklist_item_code == "form_i130"
    assert document.extracted_fields["form_edition"] == "04/01/24"
    assert document.extracted_fields["embedded_i130a_detected"] is True
    assert "form_i130a" in document.extracted_fields["satisfies_checklist_codes"]
    assert document.extracted_fields["petitioner_first_name"] == "Jordan"
    assert document.extracted_fields["petitioner_last_name"] == "Petitioner Jr"
    assert document.extracted_fields["petitioner_name"] == "Jordan Petitioner Jr"
    assert document.extracted_fields["beneficiary_first_name"] == "Avery"
    assert document.extracted_fields["beneficiary_last_name"] == "Sample"
    assert document.extracted_fields["beneficiary_name"] == "Avery Sample"
    assert document.extracted_fields["marriage_date"] == "2024-05-15"
    assert document.extracted_fields["beneficiary_current_immigration_status"] == "B2"
    assert document.extracted_fields["beneficiary_current_address"].startswith("456 PRIOR AVENUE APT 2")
    assert len(document.extracted_fields["beneficiary_address_history"]) == 2
    assert document.extracted_fields["beneficiary_prior_address_history"][0]["city"] == "Manizales"
    assert document.extracted_fields["edition_matches_current_uscis_requirement"] is True


def test_scan_i485_extracts_status_and_address_fields():
    fixture_path = PRIVATE_EVIDENCE_DIR / "I-485" / "Sample-Form-I-485.pdf"
    require_private_fixture(fixture_path)
    document = scan_document(fixture_path)

    assert document.checklist_item_code == "form_i485"
    assert document.extracted_fields["form_edition"] == "01/20/25"
    assert document.extracted_fields["beneficiary_first_name"] == "Avery"
    assert document.extracted_fields["beneficiary_last_name"] == "Sample"
    assert document.extracted_fields["beneficiary_name"] == "Avery Sample"
    assert document.extracted_fields["beneficiary_i94_number"] == "898715649A4"
    assert document.extracted_fields["beneficiary_current_immigration_status"] == "B2"
    assert document.extracted_fields["beneficiary_current_city"] == "Oakland"
    assert document.extracted_fields["beneficiary_current_address"].startswith("123 Sample Street, Unit 4B, Example City")
    assert document.extracted_fields["beneficiary_prior_address_history"][0]["city"] == "Sunnyvale"
    assert document.extracted_fields["beneficiary_prior_address_history"][0]["from"] == "2025-03-15"
    assert document.extracted_fields["petitioner_first_name"] == "Jordan"


def test_birth_certificate_scan_marks_translation_and_country():
    fixture_path = PRIVATE_EVIDENCE_DIR / "I-485" / "Translated_Birth_Certificate.pdf"
    require_private_fixture(fixture_path)
    document = scan_document(fixture_path)

    assert document.checklist_item_code == "beneficiary_birth_certificate"
    assert document.has_translation is True
    assert document.document_language == "spanish"
    assert document.extracted_fields["beneficiary_country_of_birth"] == "CO"
    assert document.extracted_fields["beneficiary_first_name"] == "Avery"
    assert "translation_certification" in document.extracted_fields["satisfies_checklist_codes"]


def test_current_uscis_requirement_map_has_live_i765_and_i693_rules():
    assert USCIS_REQUIREMENT_BY_CHECKLIST_CODE["form_i765"]["accepted_edition"] == "08/21/25"
    assert USCIS_REQUIREMENT_BY_CHECKLIST_CODE["medical_exam_i693"]["accepted_edition"] == "01/20/25"


def test_ingest_evidence_seeds_i485_questionnaire_from_uploaded_form(tmp_path, monkeypatch):
    fixture_path = PRIVATE_EVIDENCE_DIR / "I-485" / "Sample-Form-I-485.pdf"
    require_private_fixture(fixture_path)
    source_dir = tmp_path / "evidence"
    source_dir.mkdir()
    shutil.copy2(
        fixture_path,
        source_dir / "Sample-Form-I-485.pdf",
    )
    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")

    session = make_session()
    summary = ingest_evidence_directory(session, source_dir)
    state = get_i485_state(session, UUID(summary["case_id"]))

    assert summary["i485_import"]["imported_count"] > 0
    assert summary["i485_import"]["proposal_count"] >= summary["i485_import"]["imported_count"]
    assert state["answers"]["beneficiary_first_name"] == "Avery"
    assert state["answers"]["beneficiary_i94_number"] == "898715649A4"
    assert state["answer_sources"]["beneficiary_i94_number"]["source_type"] == "pdf_upload"
