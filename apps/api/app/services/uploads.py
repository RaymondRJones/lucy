"""Rules and storage for uploaded evidence documents."""

from __future__ import annotations

from pathlib import Path
import re
from uuid import UUID

from sqlmodel import Session, select

from app.core.config import settings
from app.models.entities import UploadedDocument, UploadStatus, utcnow
from app.schemas.common import UploadConfirmRequest, UploadRequestCreate
from app.services.audit import log_action

ALLOWED_UPLOAD_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
}
LANGUAGES_NOT_NEEDING_TRANSLATION = {"english", "en", "unknown"}


def _safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "-", name)


def _requires_translation(document_language: str) -> bool:
    return document_language.lower() not in LANGUAGES_NOT_NEEDING_TRANSLATION


def create_upload_request(session: Session, case_id: UUID, payload: UploadRequestCreate) -> UploadedDocument:
    """Records an expected upload as the next version for its checklist item."""
    existing_versions = list(
        session.exec(
            select(UploadedDocument).where(
                UploadedDocument.case_id == case_id,
                UploadedDocument.checklist_item_code == payload.checklist_item_code,
            )
        )
    )
    upload = UploadedDocument(
        case_id=case_id,
        checklist_item_code=payload.checklist_item_code,
        original_filename=payload.original_filename,
        mime_type=payload.mime_type,
        document_language=payload.document_language,
        requires_translation=_requires_translation(payload.document_language),
        has_translation=payload.has_translation,
        extracted_fields=payload.extracted_fields,
        version=len(existing_versions) + 1,
    )
    session.add(upload)
    log_action(session, case_id, "upload.requested", payload.model_dump())
    session.commit()
    session.refresh(upload)
    return upload


def save_upload_binary(
    session: Session, upload: UploadedDocument, content: bytes, content_type: str | None, filename: str | None
) -> UploadedDocument:
    """Writes the file to the upload directory and marks the upload as received."""
    stored_filename = f"{upload.id}-{_safe_filename(filename or upload.original_filename)}"
    destination = settings.upload_dir / stored_filename
    destination.write_bytes(content)

    upload.stored_filename = stored_filename
    upload.file_size = len(content)
    upload.mime_type = content_type
    upload.upload_status = UploadStatus.uploaded.value
    upload.updated_at = utcnow()
    session.add(upload)
    log_action(session, upload.case_id, "upload.binary_saved", {"upload_id": str(upload.id), "path": str(destination)})
    session.commit()
    session.refresh(upload)
    return upload


def confirm_upload(session: Session, upload: UploadedDocument, payload: UploadConfirmRequest) -> UploadedDocument:
    """Applies the user's review details and marks the upload as confirmed."""
    if payload.document_type is not None:
        upload.document_type = payload.document_type
    if payload.document_language is not None:
        upload.document_language = payload.document_language
        upload.requires_translation = _requires_translation(payload.document_language)
    if payload.has_translation is not None:
        upload.has_translation = payload.has_translation
    if payload.extracted_fields is not None:
        upload.extracted_fields = {**upload.extracted_fields, **payload.extracted_fields}
    if payload.extraction_confidence is not None:
        upload.extraction_confidence = payload.extraction_confidence

    upload.upload_status = UploadStatus.confirmed.value
    upload.updated_at = utcnow()
    session.add(upload)
    log_action(session, upload.case_id, "upload.confirmed", {"upload_id": str(upload.id)})
    session.commit()
    session.refresh(upload)
    return upload


def list_case_uploads(session: Session, case_id: UUID) -> list[UploadedDocument]:
    """Returns a case's uploads, newest first."""
    return list(
        session.exec(
            select(UploadedDocument)
            .where(UploadedDocument.case_id == case_id)
            .order_by(UploadedDocument.created_at.desc())
        )
    )


def delete_upload(session: Session, upload: UploadedDocument) -> None:
    """Deletes the upload's record and its stored file, if any."""
    if upload.stored_filename:
        path = Path(settings.upload_dir / upload.stored_filename)
        if path.exists():
            path.unlink()
    log_action(session, upload.case_id, "upload.deleted", {"upload_id": str(upload.id)})
    session.delete(upload)
    session.commit()
