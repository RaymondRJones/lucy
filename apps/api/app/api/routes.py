from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from app.content.country_guidance import COUNTRY_GUIDANCE
from app.content.fee_schedule import G1450_PAYMENT_NOTE
from app.content.i485_questionnaire import (
    I485_LOCAL_REFERENCE_PDF,
    I485_OFFICIAL_PDF_URL,
    I485_OFFICIAL_URL,
    I485_QUESTIONNAIRE,
    I485_QUESTIONNAIRE_VERSION,
    I485_SOURCES,
    I485_VERIFIED_ON,
)
from app.content.prescreen import PRESCREEN_QUESTIONS, PRESCREEN_SOURCES, PRESCREEN_VERIFIED_ON, PRESCREEN_VERSION
from app.content.reference_data import EXPLANATION_CONTENT, FEE_TABLE, FORM_EDITIONS
from app.content.supplemental_forms import get_supplemental_form_config
from app.content.uscis_requirements import GENERAL_USCIS_RULES, USCIS_REQUIREMENTS, VERIFIED_ON
from app.core.config import settings
from app.db.session import get_session
from app.models.entities import (
    AuditLog,
    CaseChecklistItem,
    CaseRecord,
    Invitation,
    MarriageRecord,
    PersonRecord,
    QAIssue,
    UploadedDocument,
    UploadStatus,
)
from app.schemas.common import (
    CaseCreateRequest,
    CaseRead,
    CaseUpdateRequest,
    ChecklistItemRead,
    ChecklistItemUpdateRequest,
    ChecklistResponse,
    CountryGuidanceRead,
    ExplanationContentRead,
    FilingValidationCapabilitiesRead,
    FilingValidationRequest,
    FilingValidationResponseRead,
    FormCaseDataImportRequest,
    FormCaseDataImportResponseRead,
    FormFillPreviewRead,
    FormIngestionStateRead,
    FormPageAnswersWrite,
    FormPdfGenerateRequest,
    FormPdfGenerateResponseRead,
    FormQuestionnaireRead,
    G1450GenerateRequest,
    G1450GenerateResponseRead,
    G1450GeneratedPdfRead,
    G1450PaymentOptionRead,
    G1450PaymentOptionsRead,
    I485CaseDataImportRequest,
    I485CaseDataImportResponseRead,
    I485IngestionStateRead,
    I485FormFillPreviewRead,
    I485PageAnswersWrite,
    I485PdfGenerateRequest,
    I485PdfGenerateResponseRead,
    I485PdfImportRequest,
    I485PdfImportResponseRead,
    I485QuestionnaireRead,
    IntakeStateRead,
    IntakeStepRead,
    IntakeStepWrite,
    IntakeSubmitResponse,
    InvitationCreateRequest,
    InvitationRead,
    MarriageRead,
    PacketAssemblyGenerateRequest,
    PacketAssemblyResponseRead,
    PersonRead,
    PrescreenAnswersWrite,
    PrescreenQuestionnaireRead,
    PrescreenStateRead,
    QAResultsRead,
    QAIssueRead,
    QASummaryRead,
    UploadConfirmRequest,
    UploadedDocumentRead,
    UploadRequestCreate,
    UploadRequestRead,
    USCISRequirementRead,
    USCISRequirementsPayloadRead,
)
from app.services.checklist import generate_checklist, get_checklist
from app.services.filing_validation import get_filing_validation_capabilities, validate_case_filings
from app.services.form_ingestion import (
    build_form_fill_preview,
    get_form_state,
    import_form_answers_from_case_data,
    save_form_page_answers,
)
from app.services.form_pdf import generate_form_pdf
from app.services.g1450 import generate_case_g1450_packet_from_payload, get_case_g1450_payment_options
from app.services.i485 import (
    build_i485_form_fill_preview,
    get_i485_state,
    import_i485_answers_from_case_data,
    import_i485_answers_from_upload,
    save_i485_page_answers,
)
from app.services.i485_pdf import DEFAULT_I485_TEMPLATE_PATH, generate_i485_pdf
from app.services.intake import (
    apply_case_projection,
    get_case_steps,
    get_merged_case_intake,
    get_missing_fields,
    merge_intake_state,
    normalize_country,
    upsert_intake_step,
)
from app.services.packet_assembly import assemble_packet_pdf
from app.services.prescreen import get_prescreen_state, save_prescreen_answers
from app.services.qa import get_qa_results, run_qa


router = APIRouter()
GENERATED_PDF_DIR = Path("storage/generated").resolve()
ALLOWED_UPLOAD_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "-", name)


def _generated_pdf_download_url(case_id: UUID, path: Path) -> str:
    version = int(path.stat().st_mtime) if path.exists() else int(_utcnow().timestamp())
    return f"/api/v1/cases/{case_id}/generated-pdfs/{path.name}?v={version}"


def _packet_manifest_download_url(case_id: UUID, path: Path) -> str:
    version = int(path.stat().st_mtime) if path.exists() else int(_utcnow().timestamp())
    return f"/api/v1/cases/{case_id}/packet-assembly/manifests/{path.name}?v={version}"


def _supplemental_form_config_or_404(form_key: str) -> dict[str, Any]:
    try:
        return get_supplemental_form_config(form_key)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supported form not found") from exc


def _log(session: Session, case_id: UUID | None, action: str, details: dict[str, Any]) -> None:
    session.add(AuditLog(case_id=case_id, action=action, details=details))


def _get_case_or_404(session: Session, case_id: UUID) -> CaseRecord:
    case = session.get(CaseRecord, case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return case


def _serialize_case(session: Session, case: CaseRecord) -> CaseRead:
    people = list(session.exec(select(PersonRecord).where(PersonRecord.case_id == case.id)))
    petitioner = next((person for person in people if person.role == "petitioner"), None)
    beneficiary = next((person for person in people if person.role == "beneficiary"), None)
    marriage = session.exec(select(MarriageRecord).where(MarriageRecord.case_id == case.id)).first()
    checklist_count = len(
        list(session.exec(select(CaseChecklistItem).where(CaseChecklistItem.case_id == case.id)))
    )
    upload_count = len(
        list(session.exec(select(UploadedDocument).where(UploadedDocument.case_id == case.id)))
    )
    qa_count = len(list(session.exec(select(QAIssue).where(QAIssue.case_id == case.id))))

    return CaseRead(
        id=case.id,
        case_name=case.case_name,
        workflow_type=case.workflow_type,
        status=case.status,
        petitioner_email=case.petitioner_email,
        beneficiary_email=case.beneficiary_email,
        country_of_focus=case.country_of_focus,
        readiness_score=case.readiness_score,
        readiness_label=case.readiness_label,
        created_at=case.created_at,
        updated_at=case.updated_at,
        petitioner=PersonRead.model_validate(petitioner) if petitioner else None,
        beneficiary=PersonRead.model_validate(beneficiary) if beneficiary else None,
        marriage=MarriageRead.model_validate(marriage) if marriage else None,
        counts={
            "checklist_items": checklist_count,
            "uploads": upload_count,
            "qa_issues": qa_count,
        },
    )


@router.post("/cases", response_model=CaseRead, status_code=status.HTTP_201_CREATED)
def create_case(payload: CaseCreateRequest, session: Session = Depends(get_session)):
    case = CaseRecord(
        case_name=payload.case_name,
        petitioner_email=payload.petitioner_email,
        beneficiary_email=payload.beneficiary_email,
        country_of_focus=normalize_country(payload.country_of_focus),
    )
    session.add(case)
    session.flush()
    session.add(PersonRecord(case_id=case.id, role="petitioner", email=payload.petitioner_email))
    session.add(PersonRecord(case_id=case.id, role="beneficiary", email=payload.beneficiary_email))
    session.add(MarriageRecord(case_id=case.id))
    _log(session, case.id, "case.created", payload.model_dump())
    session.commit()
    session.refresh(case)
    return _serialize_case(session, case)


@router.get("/cases", response_model=list[CaseRead])
def list_cases(session: Session = Depends(get_session)):
    cases = list(session.exec(select(CaseRecord).order_by(CaseRecord.created_at.desc())))
    return [_serialize_case(session, case) for case in cases]


@router.get("/cases/{case_id}", response_model=CaseRead)
def get_case(case_id: UUID, session: Session = Depends(get_session)):
    case = _get_case_or_404(session, case_id)
    return _serialize_case(session, case)


@router.patch("/cases/{case_id}", response_model=CaseRead)
def update_case(case_id: UUID, payload: CaseUpdateRequest, session: Session = Depends(get_session)):
    case = _get_case_or_404(session, case_id)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(case, field, normalize_country(value) if field == "country_of_focus" else value)
    case.updated_at = _utcnow()
    session.add(case)
    _log(session, case.id, "case.updated", payload.model_dump(exclude_none=True))
    session.commit()
    session.refresh(case)
    return _serialize_case(session, case)


@router.post("/cases/{case_id}/invite", response_model=InvitationRead, status_code=status.HTTP_201_CREATED)
def invite_collaborator(
    case_id: UUID,
    payload: InvitationCreateRequest,
    session: Session = Depends(get_session),
):
    _get_case_or_404(session, case_id)
    invitation = Invitation(case_id=case_id, email=payload.email, role=payload.role)
    session.add(invitation)
    _log(session, case_id, "case.invited", payload.model_dump())
    session.commit()
    session.refresh(invitation)
    return InvitationRead.model_validate(invitation)


@router.post("/cases/{case_id}/intake/step", response_model=IntakeStateRead)
def save_intake_step(case_id: UUID, payload: IntakeStepWrite, session: Session = Depends(get_session)):
    _get_case_or_404(session, case_id)
    upsert_intake_step(session, case_id, payload.step_key, payload.payload)
    session.commit()
    steps = get_case_steps(session, case_id)
    merged = get_merged_case_intake(session, case_id)
    return IntakeStateRead(
        case_id=case_id,
        steps=[IntakeStepRead.model_validate(step) for step in steps],
        merged=merged,
        missing_fields=get_missing_fields(merged),
    )


@router.get("/cases/{case_id}/intake", response_model=IntakeStateRead)
def get_intake(case_id: UUID, session: Session = Depends(get_session)):
    _get_case_or_404(session, case_id)
    steps = get_case_steps(session, case_id)
    merged = get_merged_case_intake(session, case_id)
    return IntakeStateRead(
        case_id=case_id,
        steps=[IntakeStepRead.model_validate(step) for step in steps],
        merged=merged,
        missing_fields=get_missing_fields(merged),
    )


@router.post("/cases/{case_id}/intake/submit", response_model=IntakeSubmitResponse)
def submit_intake(case_id: UUID, session: Session = Depends(get_session)):
    case = _get_case_or_404(session, case_id)
    merged = get_merged_case_intake(session, case_id)
    apply_case_projection(session, case_id, merged)
    missing_fields = get_missing_fields(merged)
    if missing_fields:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Intake is incomplete.",
                "missing_fields": missing_fields,
            },
        )
    items, facts = generate_checklist(session, case_id)
    case.status = "checklist_ready"
    case.updated_at = _utcnow()
    session.add(case)
    _log(session, case_id, "intake.submitted", {"facts": facts})
    session.commit()
    return IntakeSubmitResponse(
        case_id=case_id,
        status=case.status,
        missing_fields=[],
        generated_items=len(items),
        facts=facts,
    )


@router.get("/content/prescreen", response_model=PrescreenQuestionnaireRead)
def get_prescreen_content():
    return PrescreenQuestionnaireRead(
        version=PRESCREEN_VERSION,
        verified_on=PRESCREEN_VERIFIED_ON,
        sources=PRESCREEN_SOURCES,
        questions=PRESCREEN_QUESTIONS,
    )


@router.get("/cases/{case_id}/prescreen", response_model=PrescreenStateRead)
def get_case_prescreen(case_id: UUID, session: Session = Depends(get_session)):
    _get_case_or_404(session, case_id)
    return PrescreenStateRead(**get_prescreen_state(session, case_id))


@router.post("/cases/{case_id}/prescreen", response_model=PrescreenStateRead)
def save_case_prescreen(
    case_id: UUID,
    payload: PrescreenAnswersWrite,
    session: Session = Depends(get_session),
):
    _get_case_or_404(session, case_id)
    state = save_prescreen_answers(session, case_id, payload.answers)
    _log(session, case_id, "prescreen.saved", {"answered": len(payload.answers)})
    session.commit()
    return PrescreenStateRead(**state)


@router.post("/cases/{case_id}/checklist/generate", response_model=ChecklistResponse)
def generate_case_checklist(case_id: UUID, session: Session = Depends(get_session)):
    _get_case_or_404(session, case_id)
    items, facts = generate_checklist(session, case_id)
    _log(session, case_id, "checklist.generated", {"item_count": len(items)})
    session.commit()
    return ChecklistResponse(
        case_id=case_id,
        facts=facts,
        items=[ChecklistItemRead.model_validate(item) for item in items],
    )


@router.get("/cases/{case_id}/checklist", response_model=ChecklistResponse)
def get_case_checklist(case_id: UUID, session: Session = Depends(get_session)):
    _get_case_or_404(session, case_id)
    items, facts = get_checklist(session, case_id)
    return ChecklistResponse(
        case_id=case_id,
        facts=facts,
        items=[ChecklistItemRead.model_validate(item) for item in items],
    )


@router.patch("/checklist-items/{item_id}", response_model=ChecklistItemRead)
def update_checklist_item(
    item_id: UUID,
    payload: ChecklistItemUpdateRequest,
    session: Session = Depends(get_session),
):
    item = session.get(CaseChecklistItem, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checklist item not found")
    if payload.completion_status is not None:
        item.completion_status = payload.completion_status
    item.updated_at = _utcnow()
    session.add(item)
    _log(session, item.case_id, "checklist.updated", {"item_id": str(item.id), **payload.model_dump(exclude_none=True)})
    session.commit()
    session.refresh(item)
    return ChecklistItemRead.model_validate(item)


@router.post("/cases/{case_id}/uploads/request", response_model=UploadRequestRead, status_code=status.HTTP_201_CREATED)
def request_upload(
    case_id: UUID,
    payload: UploadRequestCreate,
    session: Session = Depends(get_session),
):
    _get_case_or_404(session, case_id)
    existing_versions = list(
        session.exec(
            select(UploadedDocument).where(
                UploadedDocument.case_id == case_id,
                UploadedDocument.checklist_item_code == payload.checklist_item_code,
            )
        )
    )
    requires_translation = payload.document_language.lower() not in {"english", "en", "unknown"}
    upload = UploadedDocument(
        case_id=case_id,
        checklist_item_code=payload.checklist_item_code,
        original_filename=payload.original_filename,
        mime_type=payload.mime_type,
        document_language=payload.document_language,
        requires_translation=requires_translation,
        has_translation=payload.has_translation,
        extracted_fields=payload.extracted_fields,
        version=len(existing_versions) + 1,
    )
    session.add(upload)
    _log(session, case_id, "upload.requested", payload.model_dump())
    session.commit()
    session.refresh(upload)
    return UploadRequestRead(
        upload_id=upload.id,
        upload_url=f"{settings.api_prefix}/uploads/{upload.id}/binary",
        max_upload_size_mb=settings.max_upload_size_mb,
    )


@router.post("/uploads/{upload_id}/binary", response_model=UploadedDocumentRead)
async def upload_binary(
    upload_id: UUID,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    upload = session.get(UploadedDocument, upload_id)
    if not upload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found")
    if file.content_type not in ALLOWED_UPLOAD_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Only PDF, JPG, JPEG, and PNG are allowed.",
        )

    content = await file.read()
    max_size = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds the {settings.max_upload_size_mb} MB upload limit.",
        )

    stored_filename = f"{upload.id}-{_safe_filename(file.filename or upload.original_filename)}"
    destination = settings.upload_dir / stored_filename
    destination.write_bytes(content)

    upload.stored_filename = stored_filename
    upload.file_size = len(content)
    upload.mime_type = file.content_type
    upload.upload_status = UploadStatus.uploaded.value
    upload.updated_at = _utcnow()
    session.add(upload)
    _log(session, upload.case_id, "upload.binary_saved", {"upload_id": str(upload.id), "path": str(destination)})
    session.commit()
    session.refresh(upload)
    return UploadedDocumentRead.model_validate(upload)


@router.post("/uploads/{upload_id}/confirm", response_model=UploadedDocumentRead)
def confirm_upload(
    upload_id: UUID,
    payload: UploadConfirmRequest,
    session: Session = Depends(get_session),
):
    upload = session.get(UploadedDocument, upload_id)
    if not upload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found")
    if upload.upload_status == UploadStatus.requested.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload binary is still missing. Send the file before confirming.",
        )

    if payload.document_type is not None:
        upload.document_type = payload.document_type
    if payload.document_language is not None:
        upload.document_language = payload.document_language
        upload.requires_translation = payload.document_language.lower() not in {"english", "en", "unknown"}
    if payload.has_translation is not None:
        upload.has_translation = payload.has_translation
    if payload.extracted_fields is not None:
        merged_fields = dict(upload.extracted_fields)
        merged_fields.update(payload.extracted_fields)
        upload.extracted_fields = merged_fields
    if payload.extraction_confidence is not None:
        upload.extraction_confidence = payload.extraction_confidence

    upload.upload_status = UploadStatus.confirmed.value
    upload.updated_at = _utcnow()
    session.add(upload)
    _log(session, upload.case_id, "upload.confirmed", {"upload_id": str(upload.id)})
    session.commit()
    session.refresh(upload)
    return UploadedDocumentRead.model_validate(upload)


@router.get("/cases/{case_id}/uploads", response_model=list[UploadedDocumentRead])
def list_uploads(case_id: UUID, session: Session = Depends(get_session)):
    _get_case_or_404(session, case_id)
    uploads = list(
        session.exec(
            select(UploadedDocument)
            .where(UploadedDocument.case_id == case_id)
            .order_by(UploadedDocument.created_at.desc())
        )
    )
    return [UploadedDocumentRead.model_validate(upload) for upload in uploads]


@router.delete("/uploads/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_upload(upload_id: UUID, session: Session = Depends(get_session)):
    upload = session.get(UploadedDocument, upload_id)
    if not upload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found")
    if upload.stored_filename:
        path = Path(settings.upload_dir / upload.stored_filename)
        if path.exists():
            path.unlink()
    case_id = upload.case_id
    _log(session, case_id, "upload.deleted", {"upload_id": str(upload.id)})
    session.delete(upload)
    session.commit()


@router.post("/cases/{case_id}/qa/run", response_model=QAResultsRead)
def run_case_qa(case_id: UUID, session: Session = Depends(get_session)):
    _get_case_or_404(session, case_id)
    issues, summary = run_qa(session, case_id)
    return QAResultsRead(
        case_id=case_id,
        summary=QASummaryRead(**summary),
        issues=[QAIssueRead.model_validate(issue) for issue in issues],
    )


@router.get("/cases/{case_id}/qa", response_model=QAResultsRead)
def get_case_qa(case_id: UUID, session: Session = Depends(get_session)):
    _get_case_or_404(session, case_id)
    issues, summary = get_qa_results(session, case_id)
    return QAResultsRead(
        case_id=case_id,
        summary=QASummaryRead(**summary),
        issues=[QAIssueRead.model_validate(issue) for issue in issues],
    )


@router.get("/cases/{case_id}/readiness", response_model=QASummaryRead)
def get_case_readiness(case_id: UUID, session: Session = Depends(get_session)):
    _get_case_or_404(session, case_id)
    _, summary = get_qa_results(session, case_id)
    return QASummaryRead(**summary)


@router.post("/cases/{case_id}/filing-validation", response_model=FilingValidationResponseRead)
def validate_case_filing_records(
    case_id: UUID,
    payload: FilingValidationRequest | None = None,
    session: Session = Depends(get_session),
):
    _get_case_or_404(session, case_id)
    payload = payload or FilingValidationRequest()
    return FilingValidationResponseRead(
        **validate_case_filings(
            session,
            case_id,
            form_codes=payload.form_codes,
            template_paths=payload.template_paths,
        )
    )


@router.get("/content/filing-validation", response_model=FilingValidationCapabilitiesRead)
def get_filing_validation_content():
    return FilingValidationCapabilitiesRead(**get_filing_validation_capabilities())


@router.get("/cases/{case_id}/g1450/payment-options", response_model=G1450PaymentOptionsRead)
def get_case_g1450_options(case_id: UUID, session: Session = Depends(get_session)):
    _get_case_or_404(session, case_id)
    options = get_case_g1450_payment_options(session, case_id)
    return G1450PaymentOptionsRead(
        case_id=case_id,
        template_pdf=str(settings.g1450_template_path),
        template_exists=settings.g1450_template_path.exists(),
        payment_note=G1450_PAYMENT_NOTE,
        options=[G1450PaymentOptionRead(**option.__dict__) for option in options],
    )


@router.post("/cases/{case_id}/g1450/generate", response_model=G1450GenerateResponseRead)
def generate_case_g1450_pdfs(
    case_id: UUID,
    payload: G1450GenerateRequest,
    session: Session = Depends(get_session),
):
    _get_case_or_404(session, case_id)
    try:
        packet = generate_case_g1450_packet_from_payload(
            session=session,
            case_id=case_id,
            payload=payload.model_dump(
                exclude={"selected_checklist_codes"},
                exclude_none=True,
            ),
            template_path=settings.g1450_template_path,
            output_dir=GENERATED_PDF_DIR,
            selected_checklist_codes=payload.selected_checklist_codes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    _log(
        session,
        case_id,
        "g1450.generated",
        {
            "selected_checklist_codes": payload.selected_checklist_codes,
            "generated_count": len(packet.generated),
            "skipped_count": len(packet.skipped),
            "total_authorized_amount": packet.total_authorized_amount,
        },
    )
    session.commit()
    return G1450GenerateResponseRead(
        case_id=case_id,
        generated=[
            G1450GeneratedPdfRead(
                checklist_code=result.checklist_code,
                form_code=result.form_code,
                filing_category=result.filing_category,
                authorized_amount=result.authorized_amount,
                generated_pdf=str(result.output_path),
                download_url=_generated_pdf_download_url(case_id, result.output_path),
            )
            for result in packet.generated
        ],
        skipped=packet.skipped,
        total_authorized_amount=packet.total_authorized_amount,
        payment_note=packet.payment_note,
    )


@router.get("/content/i485-questionnaire", response_model=I485QuestionnaireRead)
def get_i485_questionnaire():
    return I485QuestionnaireRead(
        version=I485_QUESTIONNAIRE_VERSION,
        verified_on=I485_VERIFIED_ON,
        official_url=I485_OFFICIAL_URL,
        official_pdf_url=I485_OFFICIAL_PDF_URL,
        local_reference_pdf=I485_LOCAL_REFERENCE_PDF,
        sources=I485_SOURCES,
        pages=I485_QUESTIONNAIRE,
    )


@router.get("/cases/{case_id}/i485-ingestion", response_model=I485IngestionStateRead)
def get_case_i485_ingestion(case_id: UUID, session: Session = Depends(get_session)):
    _get_case_or_404(session, case_id)
    return I485IngestionStateRead(**get_i485_state(session, case_id))


@router.post("/cases/{case_id}/i485-ingestion/page", response_model=I485IngestionStateRead)
def save_case_i485_page(
    case_id: UUID,
    payload: I485PageAnswersWrite,
    session: Session = Depends(get_session),
):
    _get_case_or_404(session, case_id)
    try:
        state = save_i485_page_answers(session, case_id, payload.page_id, payload.answers, payload.manual_flags)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    _log(
        session,
        case_id,
        "i485_ingestion.page_saved",
        {"page_id": payload.page_id, "answered": len(payload.answers)},
    )
    session.commit()
    return I485IngestionStateRead(**state)


@router.post("/cases/{case_id}/i485-ingestion/import-from-upload", response_model=I485PdfImportResponseRead)
def import_case_i485_from_upload(
    case_id: UUID,
    payload: I485PdfImportRequest,
    session: Session = Depends(get_session),
):
    _get_case_or_404(session, case_id)
    try:
        result = import_i485_answers_from_upload(
            session,
            case_id,
            upload_id=payload.upload_id,
            overwrite=payload.overwrite,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    _log(
        session,
        case_id,
        "i485_ingestion.imported_from_upload",
        {
            "upload_id": result["upload_id"],
            "imported_count": result["imported_count"],
            "skipped_count": result["skipped_count"],
            "overwrite": payload.overwrite,
        },
    )
    session.commit()
    return I485PdfImportResponseRead(**result)


@router.post("/cases/{case_id}/i485-ingestion/import-from-case", response_model=I485CaseDataImportResponseRead)
def import_case_i485_from_case_data(
    case_id: UUID,
    payload: I485CaseDataImportRequest,
    session: Session = Depends(get_session),
):
    _get_case_or_404(session, case_id)
    result = import_i485_answers_from_case_data(
        session,
        case_id,
        overwrite=payload.overwrite,
    )
    _log(
        session,
        case_id,
        "i485_ingestion.imported_from_case",
        {
            "imported_count": result["imported_count"],
            "skipped_count": result["skipped_count"],
            "overwrite": payload.overwrite,
        },
    )
    session.commit()
    return I485CaseDataImportResponseRead(**result)


@router.get("/cases/{case_id}/i485-ingestion/form-fill-preview", response_model=I485FormFillPreviewRead)
def get_case_i485_form_fill_preview(case_id: UUID, session: Session = Depends(get_session)):
    _get_case_or_404(session, case_id)
    return I485FormFillPreviewRead(**build_i485_form_fill_preview(session, case_id))


@router.post("/cases/{case_id}/i485-ingestion/generate-pdf", response_model=I485PdfGenerateResponseRead)
def generate_case_i485_pdf(
    case_id: UUID,
    payload: I485PdfGenerateRequest | None = None,
    session: Session = Depends(get_session),
):
    _get_case_or_404(session, case_id)
    payload = payload or I485PdfGenerateRequest()
    try:
        result = generate_i485_pdf(
            session=session,
            case_id=case_id,
            template_path=Path(payload.template_path) if payload.template_path else DEFAULT_I485_TEMPLATE_PATH,
            output_path=Path(payload.output_path) if payload.output_path else None,
            output_dir=Path(payload.output_dir) if payload.output_dir else Path("storage/generated"),
            allow_incomplete=payload.allow_incomplete,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    _log(
        session,
        case_id,
        "i485_pdf.generated",
        {
            "generated_pdf": str(result.output_path),
            "template_pdf": str(result.template_path),
            "generation_status": result.generation_status,
            "field_count": result.field_count,
        },
    )
    session.commit()
    return I485PdfGenerateResponseRead(
        case_id=result.case_id,
        generated_pdf=str(result.output_path),
        download_url=_generated_pdf_download_url(case_id, result.output_path),
        template_pdf=str(result.template_path),
        generation_status=result.generation_status,
        ready_for_pdf_generation=result.ready_for_pdf_generation,
        field_count=result.field_count,
        text_field_count=result.text_field_count,
        checkbox_field_count=result.checkbox_field_count,
        mapped_question_count=result.mapped_question_count,
        unmapped_answer_count=result.unmapped_answer_count,
        missing_required_count=result.missing_required_count,
        blocking_flag_count=result.blocking_flag_count,
        outside_niche_flag_count=result.outside_niche_flag_count,
        low_confidence_count=result.low_confidence_count,
        warnings=result.warnings,
        mapped_questions=result.mapped_questions,
        unmapped_answered_questions=result.unmapped_answered_questions,
        missing_template_fields=result.missing_template_fields,
    )


@router.get("/content/forms/{form_key}/questionnaire", response_model=FormQuestionnaireRead)
def get_supplemental_form_questionnaire(form_key: str):
    config = _supplemental_form_config_or_404(form_key)
    return FormQuestionnaireRead(**config)


@router.get("/cases/{case_id}/forms/{form_key}/ingestion", response_model=FormIngestionStateRead)
def get_case_form_ingestion(case_id: UUID, form_key: str, session: Session = Depends(get_session)):
    _get_case_or_404(session, case_id)
    _supplemental_form_config_or_404(form_key)
    return FormIngestionStateRead(**get_form_state(session, case_id, form_key))


@router.post("/cases/{case_id}/forms/{form_key}/ingestion/page", response_model=FormIngestionStateRead)
def save_case_form_page(
    case_id: UUID,
    form_key: str,
    payload: FormPageAnswersWrite,
    session: Session = Depends(get_session),
):
    _get_case_or_404(session, case_id)
    config = _supplemental_form_config_or_404(form_key)
    try:
        state = save_form_page_answers(session, case_id, form_key, payload.page_id, payload.answers, payload.manual_flags)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    _log(
        session,
        case_id,
        f"{config['form_key']}_ingestion.page_saved",
        {"page_id": payload.page_id, "answered": len(payload.answers)},
    )
    session.commit()
    return FormIngestionStateRead(**state)


@router.post("/cases/{case_id}/forms/{form_key}/ingestion/import-from-case", response_model=FormCaseDataImportResponseRead)
def import_case_form_from_case_data(
    case_id: UUID,
    form_key: str,
    payload: FormCaseDataImportRequest,
    session: Session = Depends(get_session),
):
    _get_case_or_404(session, case_id)
    config = _supplemental_form_config_or_404(form_key)
    result = import_form_answers_from_case_data(
        session,
        case_id,
        form_key,
        overwrite=payload.overwrite,
    )
    _log(
        session,
        case_id,
        f"{config['form_key']}_ingestion.imported_from_case",
        {
            "imported_count": result["imported_count"],
            "skipped_count": result["skipped_count"],
            "overwrite": payload.overwrite,
        },
    )
    session.commit()
    return FormCaseDataImportResponseRead(**result)


@router.get("/cases/{case_id}/forms/{form_key}/ingestion/form-fill-preview", response_model=FormFillPreviewRead)
def get_case_form_fill_preview(case_id: UUID, form_key: str, session: Session = Depends(get_session)):
    _get_case_or_404(session, case_id)
    _supplemental_form_config_or_404(form_key)
    return FormFillPreviewRead(**build_form_fill_preview(session, case_id, form_key))


@router.post("/cases/{case_id}/forms/{form_key}/ingestion/generate-pdf", response_model=FormPdfGenerateResponseRead)
def generate_case_form_pdf(
    case_id: UUID,
    form_key: str,
    payload: FormPdfGenerateRequest | None = None,
    session: Session = Depends(get_session),
):
    _get_case_or_404(session, case_id)
    config = _supplemental_form_config_or_404(form_key)
    payload = payload or FormPdfGenerateRequest()
    try:
        result = generate_form_pdf(
            session=session,
            case_id=case_id,
            form_key=form_key,
            template_path=Path(payload.template_path) if payload.template_path else None,
            output_path=Path(payload.output_path) if payload.output_path else None,
            output_dir=Path(payload.output_dir) if payload.output_dir else Path("storage/generated"),
            allow_incomplete=payload.allow_incomplete,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    _log(
        session,
        case_id,
        f"{config['form_key']}_pdf.generated",
        {
            "generated_pdf": str(result.output_path),
            "template_pdf": str(result.template_path),
            "generation_status": result.generation_status,
            "field_count": result.field_count,
        },
    )
    session.commit()
    return FormPdfGenerateResponseRead(
        case_id=result.case_id,
        form_key=result.form_key,
        generated_pdf=str(result.output_path),
        download_url=_generated_pdf_download_url(case_id, result.output_path),
        template_pdf=str(result.template_path),
        generation_status=result.generation_status,
        ready_for_pdf_generation=result.ready_for_pdf_generation,
        field_count=result.field_count,
        text_field_count=result.text_field_count,
        checkbox_field_count=result.checkbox_field_count,
        mapped_question_count=result.mapped_question_count,
        unmapped_answer_count=result.unmapped_answer_count,
        missing_required_count=result.missing_required_count,
        blocking_flag_count=result.blocking_flag_count,
        outside_niche_flag_count=result.outside_niche_flag_count,
        low_confidence_count=result.low_confidence_count,
        warnings=result.warnings,
        mapped_questions=result.mapped_questions,
        unmapped_answered_questions=result.unmapped_answered_questions,
        missing_template_fields=result.missing_template_fields,
    )


@router.post("/cases/{case_id}/packet-assembly/generate", response_model=PacketAssemblyResponseRead)
def generate_case_packet_pdf(
    case_id: UUID,
    payload: PacketAssemblyGenerateRequest | None = None,
    session: Session = Depends(get_session),
):
    _get_case_or_404(session, case_id)
    payload = payload or PacketAssemblyGenerateRequest()
    try:
        result = assemble_packet_pdf(
            session=session,
            case_id=case_id,
            state_code=payload.state_code,
            carrier=payload.carrier,
            include_upload_ids=payload.include_upload_ids,
            include_supporting_evidence=payload.include_supporting_evidence,
            include_generated_forms=payload.include_generated_forms,
            allow_incomplete=payload.allow_incomplete,
            g1450_payment_payload=payload.g1450_payment.model_dump() if payload.g1450_payment else None,
            selected_payment_checklist_codes=payload.g1450_selected_checklist_codes,
            g1450_template_path=settings.g1450_template_path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    _log(
        session,
        case_id,
        "packet_assembly.generated",
        {
            "generated_pdf": str(result.output_path),
            "manifest_json": str(result.manifest_path),
            "total_page_count": result.total_page_count,
            "included_count": len(result.included_documents),
            "skipped_count": len(result.skipped_documents),
            "mailing_location": result.mailing_recommendation["location_code"]
            if result.mailing_recommendation
            else None,
        },
    )
    session.commit()
    return PacketAssemblyResponseRead(
        case_id=result.case_id,
        generated_pdf=str(result.output_path),
        download_url=_generated_pdf_download_url(case_id, result.output_path),
        manifest_json=str(result.manifest_path),
        manifest_download_url=_packet_manifest_download_url(case_id, result.manifest_path),
        total_page_count=result.total_page_count,
        included_documents=result.included_documents,
        skipped_documents=result.skipped_documents,
        warnings=result.warnings,
        mailing_recommendation=result.mailing_recommendation,
    )


@router.get("/cases/{case_id}/packet-assembly/manifests/{filename}")
def download_packet_manifest(case_id: UUID, filename: str, session: Session = Depends(get_session)):
    _get_case_or_404(session, case_id)
    if "/" in filename or "\\" in filename or not filename.endswith(".json"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Packet manifest not found")
    expected_prefix = f"{case_id}-"
    if not filename.startswith(expected_prefix):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Packet manifest not found")
    path = (GENERATED_PDF_DIR / filename).resolve()
    try:
        path.relative_to(GENERATED_PDF_DIR)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Packet manifest not found") from exc
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Packet manifest not found")
    return FileResponse(
        path,
        media_type="application/json",
        filename=filename,
        headers={"Cache-Control": "no-store"},
    )


@router.get("/cases/{case_id}/generated-pdfs/{filename}")
def download_generated_pdf(case_id: UUID, filename: str, session: Session = Depends(get_session)):
    _get_case_or_404(session, case_id)
    if "/" in filename or "\\" in filename or not filename.endswith(".pdf"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated PDF not found")
    expected_prefix = f"{case_id}-"
    if not filename.startswith(expected_prefix):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated PDF not found")
    path = (GENERATED_PDF_DIR / filename).resolve()
    try:
        path.relative_to(GENERATED_PDF_DIR)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated PDF not found") from exc
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated PDF not found")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=filename,
        headers={"Cache-Control": "no-store"},
    )


@router.get("/cases/{case_id}/debug")
def get_case_debug(case_id: UUID, session: Session = Depends(get_session)):
    case = _get_case_or_404(session, case_id)
    people = list(session.exec(select(PersonRecord).where(PersonRecord.case_id == case_id)))
    marriage = session.exec(select(MarriageRecord).where(MarriageRecord.case_id == case_id)).first()
    steps = get_case_steps(session, case_id)
    checklist = list(
        session.exec(
            select(CaseChecklistItem)
            .where(CaseChecklistItem.case_id == case_id)
            .order_by(CaseChecklistItem.sort_order.asc())
        )
    )
    uploads = list(
        session.exec(
            select(UploadedDocument)
            .where(UploadedDocument.case_id == case_id)
            .order_by(UploadedDocument.created_at.desc())
        )
    )
    issues = list(
        session.exec(select(QAIssue).where(QAIssue.case_id == case_id).order_by(QAIssue.created_at.asc()))
    )
    audit_logs = list(
        session.exec(
            select(AuditLog).where(AuditLog.case_id == case_id).order_by(AuditLog.created_at.desc()).limit(50)
        )
    )
    merged = merge_intake_state(steps)
    return {
        "case": case.model_dump(mode="json"),
        "people": [person.model_dump(mode="json") for person in people],
        "marriage": marriage.model_dump(mode="json") if marriage else None,
        "intake": {
            "steps": [step.model_dump(mode="json") for step in steps],
            "merged": merged,
            "missing_fields": get_missing_fields(merged),
        },
        "checklist": [item.model_dump(mode="json") for item in checklist],
        "uploads": [upload.model_dump(mode="json") for upload in uploads],
        "i485_ingestion": get_i485_state(session, case_id),
        "i485_form_fill_preview": build_i485_form_fill_preview(session, case_id),
        "qa_issues": [issue.model_dump(mode="json") for issue in issues],
        "audit_logs": [entry.model_dump(mode="json") for entry in audit_logs],
    }


@router.get("/content/countries/{country_code}", response_model=CountryGuidanceRead)
def get_country_guidance(country_code: str):
    normalized = normalize_country(country_code)
    if normalized not in COUNTRY_GUIDANCE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Country guidance not found")
    return CountryGuidanceRead(**COUNTRY_GUIDANCE[normalized])


@router.get("/content/explanations", response_model=ExplanationContentRead)
def get_explanations():
    return ExplanationContentRead(**EXPLANATION_CONTENT)


@router.get("/content/uscis-requirements", response_model=USCISRequirementsPayloadRead)
def get_uscis_requirements():
    return USCISRequirementsPayloadRead(
        verified_on=VERIFIED_ON,
        general_rules=GENERAL_USCIS_RULES,
        forms=[USCISRequirementRead(**requirement) for requirement in USCIS_REQUIREMENTS],
    )


@router.get("/content/fees")
def get_fee_table():
    return FEE_TABLE


@router.get("/content/form-editions")
def get_form_editions():
    return FORM_EDITIONS
