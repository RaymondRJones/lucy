from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import UUID

from pypdf import PdfReader, PdfWriter
from sqlmodel import Session, select

from app.content.fee_schedule import G1450_FORM_FEES
from app.content.packet_mailing import mailing_recommendation_for_location
from app.content.packet_ordering import (
    I131_SECTION_UPLOAD_CODES,
    I485_SECTION_UPLOAD_CODES,
    I485_PACKET_EXCLUDED_UPLOAD_CODES,
    I485_PACKET_GENERATED_FORMS,
    I485_PACKET_PAYMENT_CHECKLIST_ORDER,
    I485_PACKET_PAYMENT_UPLOAD_CODES,
    I485_PACKET_UPLOAD_ORDER,
    I765_SECTION_UPLOAD_CODES,
    I864_SECTION_UPLOAD_CODES,
    PACKET_ASSEMBLY_GUIDANCE_SOURCES,
    PACKET_ASSEMBLY_GUIDANCE_VERIFIED_ON,
    PACKET_OUTLINE_SOURCE_PATH,
)
from app.core.config import settings
from app.models.entities import CaseChecklistItem, UploadedDocument
from app.services.checklist import generate_checklist, get_checklist
from app.services.cover_letter import generate_cover_letter_pdf, generate_section_index_pdf
from app.services.family_pdf import generate_g1145_pdf
from app.services.form_ingestion import get_form_state
from app.services.form_pdf import generate_form_pdf
from app.services.g1450 import generate_case_g1450_packet_from_payload, payable_checklist_items
from app.services.g1650 import generate_case_g1650_packet_from_payload
from app.services.i485_pdf import generate_i485_pdf
from app.services.intake import derive_case_facts, get_merged_case_intake


PACKET_OUTPUT_DIR = Path("storage/generated")
DEFAULT_PACKET_FORMS = I485_PACKET_GENERATED_FORMS
GENERIC_FORM_WARNINGS = {
    "Review every generated value against the source documents before filing.",
    "The generated PDF is not legal advice and must be printed, reviewed, and signed in ink where required.",
}
PAYMENT_SOURCE_TYPE = "generated_payment_form"
COVER_LETTER_FORM_ITEMS = {
    "g1145": "E-Notification of Application/Petition Acceptance",
    "i485": "Completed and signed Form I-485",
    "i864": "Completed and signed Form I-864",
    "i765": "Completed and signed Form I-765",
    "i131": "Completed and signed Form I-131",
}
COVER_LETTER_UPLOAD_ITEMS = {
    "form_g1145": "E-Notification of Application/Petition Acceptance",
    "form_i485": "Completed and signed Form I-485",
    "beneficiary_passport_photos": "2 passport-style photos of applicant",
    "beneficiary_passport_bio": "Copy of passport (biographic page)",
    "beneficiary_visa_or_entry_stamp": "Copy of visa page or entry stamp",
    "beneficiary_i94": "Copy of Form I-94",
    "beneficiary_birth_certificate": "Copy of birth certificate (+ certified English translation, if applicable)",
    "translation_certification": "Certified English translation(s)",
    "i130_receipt_notice": "Copy of Form I-797 (I-130 receipt notice)",
    "marriage_certificate": "Copy of marriage certificate",
    "prior_marriage_termination_records": "Prior marriage termination record(s)",
    "joint_bank_statement": "Joint bank statements",
    "joint_lease": "Lease agreement",
    "utility_bills": "Utility bills",
    "photos_together": "Photographs together",
    "affidavits": "Affidavits from friends or family",
    "form_i864": "Completed and signed Form I-864",
    "sponsor_tax_return": "Petitioner's most recent federal tax return",
    "sponsor_w2_1099": "W-2s / 1099s",
    "sponsor_pay_stubs": "Pay stubs (last 2-3 months)",
    "employment_verification_letter": "Employment verification letter",
    "medical_exam_i693": "Sealed Form I-693 medical exam packet (not opened)",
    "form_i765": "Completed and signed Form I-765",
    "form_i131": "Completed and signed Form I-131",
    "travel_explanation_i131": "Advance parole travel explanation and evidence",
}
COVER_LETTER_PAYMENT_FEE_ITEMS = {
    "form_i485": "Form I-485 filing fee",
    "form_i765": "Form I-765 filing fee",
    "form_i131": "Form I-131 filing fee",
}
I485_BONA_FIDE_CODES = {
    "joint_bank_statement",
    "joint_lease",
    "utility_bills",
    "photos_together",
    "affidavits",
}
GENERATED_FORM_UPLOAD_CODES = {
    "form_g1145",
    "form_i485",
    "form_i864",
    "form_i765",
    "form_i131",
}
SECTION_INDEX_PURPOSES = {
    "I-485 section": (
        "This section supports Form I-485 with applicant identity, last-entry/I-94, civil-document, "
        "underlying-petition, and relationship evidence for the adjustment packet."
    ),
    "I-864 section": (
        "This section supports Form I-864 with sponsor financial evidence such as tax, wage, pay, "
        "and employment records."
    ),
    "I-693 medical section": (
        "This section marks the medical-exam portion of the packet. A sealed I-693 envelope should "
        "remain sealed for mailing."
    ),
    "I-765 section": (
        "This section supports Form I-765 for employment authorization based on the pending I-485."
    ),
    "I-131 section": (
        "This section supports Form I-131 advance parole based on the pending I-485."
    ),
}
SCANNER_FRIENDLY_PRINTING_GUIDANCE = {
    "payment_first_when_present": True,
    "uses_plain_letter_size_index_pages": True,
    "print_single_sided_letter_size": True,
    "avoid_when_printing": [
        "binders",
        "folders that cannot be easily disassembled",
        "insertable tab dividers",
        "sticky notes",
        "heavy-duty staples",
        "folded pages",
        "duplicate evidence copies unless required",
        "photo albums",
        "scrapbooks",
        "digital media",
        "unnecessary original documents",
    ],
}


@dataclass(frozen=True)
class PacketAssemblyResult:
    case_id: UUID
    output_path: Path
    manifest_path: Path
    total_page_count: int
    included_documents: list[dict[str, Any]]
    skipped_documents: list[dict[str, Any]]
    warnings: list[str]
    mailing_recommendation: dict[str, Any] | None


def _document_entry(
    *,
    label: str,
    path: Path,
    source_type: str,
    page_count: int,
    section: str | None = None,
    form_key: str | None = None,
    checklist_item_code: str | None = None,
    upload_id: UUID | None = None,
) -> dict[str, Any]:
    return {
        "label": label,
        "source_type": source_type,
        "section": section,
        "form_key": form_key,
        "checklist_item_code": checklist_item_code,
        "upload_id": str(upload_id) if upload_id else None,
        "filename": path.name,
        "path": str(path),
        "page_count": page_count,
    }


def _skipped_entry(
    *,
    label: str,
    reason: str,
    source_type: str,
    section: str | None = None,
    form_key: str | None = None,
    checklist_item_code: str | None = None,
    upload_id: UUID | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    return {
        "label": label,
        "source_type": source_type,
        "section": section,
        "form_key": form_key,
        "checklist_item_code": checklist_item_code,
        "upload_id": str(upload_id) if upload_id else None,
        "filename": path.name if path else None,
        "path": str(path) if path else None,
        "reason": reason,
    }


def _append_pdf_pages(writer: PdfWriter, path: Path) -> int:
    reader = PdfReader(path)
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise ValueError("PDF is encrypted and could not be opened") from exc
    page_count = len(reader.pages)
    if page_count == 0:
        raise ValueError("PDF has no pages")
    staged_writer = PdfWriter()
    for page in reader.pages:
        staged_writer.add_page(page)
    for page in staged_writer.pages:
        writer.add_page(page)
    return page_count


def _insert_pdf_pages(writer: PdfWriter, path: Path, page_index: int) -> int:
    reader = PdfReader(path)
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise ValueError("PDF is encrypted and could not be opened") from exc
    page_count = len(reader.pages)
    if page_count == 0:
        raise ValueError("PDF has no pages")
    staged_writer = PdfWriter()
    for page in reader.pages:
        staged_writer.add_page(page)
    for offset, page in enumerate(staged_writer.pages):
        writer.insert_page(page, page_index + offset)
    return page_count


def _normalize_pdf_for_merge(source_path: Path, output_dir: Path, upload_id: UUID) -> Path:
    executable = shutil.which("pdftocairo")
    if not executable:
        raise ValueError("PDF normalization tool is not available on this machine")

    normalized_dir = output_dir / "normalized_uploads"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    normalized_path = normalized_dir / f"{upload_id}-normalized.pdf"
    command = [executable, "-pdf", str(source_path), str(normalized_path)]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "pdftocairo could not normalize the PDF").strip()
        raise ValueError(detail)
    if normalized_path.exists():
        return normalized_path
    alternate_path = normalized_path.with_suffix("")
    if alternate_path.exists():
        return alternate_path
    raise ValueError("PDF normalization did not produce a readable file")


def _append_upload_pdf_pages(writer: PdfWriter, path: Path, output_dir: Path, upload_id: UUID) -> int:
    try:
        return _append_pdf_pages(writer, path)
    except Exception as original_exc:
        try:
            normalized_path = _normalize_pdf_for_merge(path, output_dir, upload_id)
            return _append_pdf_pages(writer, normalized_path)
        except Exception as normalized_exc:
            raise ValueError(f"{original_exc}; normalization also failed: {normalized_exc}") from normalized_exc


def _relevant_form_warnings(label: str, warnings: list[str]) -> list[str]:
    return [f"{label}: {warning}" for warning in warnings if warning not in GENERIC_FORM_WARNINGS]


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _write_manifest(
    *,
    case_id: UUID,
    output_path: Path,
    manifest_path: Path,
    generated_at: datetime,
    selected_location: str | None,
    selected_carrier: str,
    include_supporting_evidence: bool,
    total_page_count: int,
    included_documents: list[dict[str, Any]],
    skipped_documents: list[dict[str, Any]],
    warnings: list[str],
    mailing_recommendation: dict[str, Any] | None,
) -> dict[str, Any]:
    manifest = {
        "case_id": str(case_id),
        "generated_at": generated_at.isoformat(),
        "generated_pdf": str(output_path),
        "generated_pdf_filename": output_path.name,
        "manifest_filename": manifest_path.name,
        "selected_location": selected_location,
        "selected_carrier": mailing_recommendation["carrier"] if mailing_recommendation else selected_carrier,
        "include_supporting_evidence": include_supporting_evidence,
        "total_page_count": total_page_count,
        "included_document_count": len(included_documents),
        "skipped_document_count": len(skipped_documents),
        "included_documents": included_documents,
        "skipped_documents": skipped_documents,
        "warnings": warnings,
        "mailing_recommendation": mailing_recommendation,
        "lockbox_source_last_reviewed": (
            mailing_recommendation["source_last_reviewed"] if mailing_recommendation else None
        ),
        "lockbox_source_verified_on": mailing_recommendation["verified_on"] if mailing_recommendation else None,
        "packet_outline_source_path": PACKET_OUTLINE_SOURCE_PATH,
        "packet_assembly_guidance_verified_on": PACKET_ASSEMBLY_GUIDANCE_VERIFIED_ON,
        "packet_assembly_guidance_sources": PACKET_ASSEMBLY_GUIDANCE_SOURCES,
        "scanner_friendly_printing_guidance": SCANNER_FRIENDLY_PRINTING_GUIDANCE,
    }
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")
    return manifest


def _safe_upload_path(upload: UploadedDocument) -> Path | None:
    if not upload.stored_filename:
        return None
    upload_dir = settings.upload_dir.resolve()
    path = (upload_dir / upload.stored_filename).resolve()
    try:
        path.relative_to(upload_dir)
    except ValueError:
        return None
    return path


def _has_answered_form_state(session: Session, case_id: UUID, form_key: str) -> bool:
    try:
        state = get_form_state(session, case_id, form_key)
    except Exception:
        return False
    return any(value not in (None, "", [], {}) for value in state.get("answers", {}).values())


def _packet_form_sequence(session: Session, case_id: UUID, facts: dict[str, Any]) -> list[str]:
    forms = ["g1145", "i485", "i864"]
    if facts.get("wants_i765") or _has_answered_form_state(session, case_id, "i765"):
        forms.append("i765")
    if facts.get("wants_i131") or _has_answered_form_state(session, case_id, "i131"):
        forms.append("i131")
    return forms


def _generate_packet_form(
    *,
    session: Session,
    case_id: UUID,
    form_key: str,
    values: dict[str, Any],
    allow_incomplete: bool,
) -> tuple[str, Path, list[str]]:
    if form_key == "g1145":
        generated = generate_g1145_pdf(case_id=case_id, values=values)
        return "Form G-1145", generated.output_path, generated.warnings
    if form_key == "i485":
        generated = generate_i485_pdf(session=session, case_id=case_id, allow_incomplete=allow_incomplete)
        return "Form I-485", generated.output_path, generated.warnings
    if form_key in {"i765", "i131", "i864"}:
        generated = generate_form_pdf(
            session=session,
            case_id=case_id,
            form_key=form_key,
            allow_incomplete=allow_incomplete,
        )
        return f"Form {form_key.upper().replace('I', 'I-', 1)}", generated.output_path, generated.warnings
    raise ValueError(f"Unsupported packet form: {form_key}")


def _confirmed_uploads(
    session: Session,
    case_id: UUID,
    include_upload_ids: list[UUID] | None,
) -> list[UploadedDocument]:
    statement = (
        select(UploadedDocument)
        .where(
            UploadedDocument.case_id == case_id,
            UploadedDocument.upload_status == "confirmed",
        )
        .order_by(UploadedDocument.created_at.asc())
    )
    uploads = list(session.exec(statement))
    if include_upload_ids is None:
        return uploads
    include_set = set(include_upload_ids)
    return [upload for upload in uploads if upload.id in include_set]


def _incomplete_uploads(
    session: Session,
    case_id: UUID,
    include_upload_ids: list[UUID] | None,
) -> list[UploadedDocument]:
    statement = (
        select(UploadedDocument)
        .where(
            UploadedDocument.case_id == case_id,
            UploadedDocument.upload_status != "confirmed",
        )
        .order_by(UploadedDocument.created_at.asc())
    )
    uploads = list(session.exec(statement))
    if include_upload_ids is None:
        return uploads
    include_set = set(include_upload_ids)
    return [upload for upload in uploads if upload.id in include_set]


def _parse_fee_amount(checklist_code: str) -> Decimal:
    try:
        return Decimal(str(G1450_FORM_FEES[checklist_code]["paper_fee"]))
    except (KeyError, InvalidOperation) as exc:
        raise ValueError(f"Missing local fee metadata for {checklist_code}.") from exc


def _i485_payment_items(session: Session, case_id: UUID) -> list[CaseChecklistItem]:
    payment_order = {code: index for index, code in enumerate(I485_PACKET_PAYMENT_CHECKLIST_ORDER)}
    items = [
        item
        for item in payable_checklist_items(session, case_id)
        if item.code in payment_order and _parse_fee_amount(item.code) > 0
    ]
    return sorted(items, key=lambda item: payment_order[item.code])


def _payment_filename(case_id: UUID, checklist_code: str) -> str:
    form_code = G1450_FORM_FEES[checklist_code]["form_code"]
    return f"{case_id}-{form_code.lower()}-g-1450.pdf"


def _payment_label(checklist_code: str, payment_form: str = "G-1450") -> str:
    return f"Form {payment_form} payment for {G1450_FORM_FEES[checklist_code]['label']}"


def _selected_i485_payment_codes(
    items: list[CaseChecklistItem],
    selected_payment_checklist_codes: list[str] | None,
) -> tuple[list[str], list[str]]:
    allowed_codes = [item.code for item in items]
    allowed_set = set(allowed_codes)
    if selected_payment_checklist_codes is None:
        return allowed_codes, []
    selected_codes = [code for code in selected_payment_checklist_codes if code in allowed_set]
    skipped_codes = [code for code in selected_payment_checklist_codes if code not in allowed_set]
    return selected_codes, skipped_codes


def _append_payment_forms(
    *,
    writer: PdfWriter,
    session: Session,
    case_id: UUID,
    output_dir: Path,
    included_documents: list[dict[str, Any]],
    skipped_documents: list[dict[str, Any]],
    warnings: list[str],
    payment_payload: dict[str, Any] | None,
    selected_payment_checklist_codes: list[str] | None,
    template_path: Path,
    uploaded_payment_included: bool = False,
    payment_form: str = "G-1450",
) -> None:
    form_key = payment_form.lower().replace("-", "")
    generate_payment_packet = (
        generate_case_g1650_packet_from_payload if payment_form == "G-1650" else generate_case_g1450_packet_from_payload
    )
    items = _i485_payment_items(session, case_id)
    selected_codes, skipped_codes = _selected_i485_payment_codes(items, selected_payment_checklist_codes)
    for code in skipped_codes:
        skipped_documents.append(
            _skipped_entry(
                label=f"Form {payment_form} payment for {code}",
                reason="Payment form is not part of the I-485 packet payment set or is not applicable to this case.",
                source_type=PAYMENT_SOURCE_TYPE,
                section="Payment",
                form_key=form_key,
                checklist_item_code=code,
            )
        )
    if not selected_codes:
        return

    if uploaded_payment_included and payment_payload is None and selected_payment_checklist_codes is None:
        return

    if payment_payload is None:
        for code in selected_codes:
            skipped_documents.append(
                _skipped_entry(
                    label=_payment_label(code, payment_form),
                    reason=(
                        "No fresh G-1450 or G-1650 was generated for this packet. Enter card or bank details "
                        "in this request or upload a reviewed, signed payment PDF."
                    ),
                    source_type=PAYMENT_SOURCE_TYPE,
                    section="Payment",
                    form_key=form_key,
                    checklist_item_code=code,
                )
            )
        return

    payment_paths: list[tuple[str, Path]] = []
    try:
        payment_packet = generate_payment_packet(
            session=session,
            case_id=case_id,
            payload=payment_payload,
            template_path=template_path,
            output_dir=output_dir,
            selected_checklist_codes=selected_codes,
        )
    except ValueError as exc:
        for code in selected_codes:
            skipped_documents.append(
                _skipped_entry(
                    label=_payment_label(code, payment_form),
                    reason=str(exc),
                    source_type=PAYMENT_SOURCE_TYPE,
                    section="Payment",
                    form_key=form_key,
                    checklist_item_code=code,
                )
            )
        warnings.append(f"{payment_form} payment PDFs could not be generated for the packet.")
        return
    payment_paths = [
        (result.checklist_code or "", result.output_path)
        for result in payment_packet.generated
        if result.checklist_code in selected_codes
    ]

    payment_order = {code: index for index, code in enumerate(I485_PACKET_PAYMENT_CHECKLIST_ORDER)}
    for code, path in sorted(payment_paths, key=lambda item: payment_order.get(item[0], 999)):
        try:
            page_count = _append_pdf_pages(writer, path)
        except Exception as exc:
            skipped_documents.append(
                _skipped_entry(
                    label=_payment_label(code, payment_form),
                    reason=f"Could not read payment PDF: {exc}",
                    source_type=PAYMENT_SOURCE_TYPE,
                    section="Payment",
                    form_key=form_key,
                    checklist_item_code=code,
                    path=path,
                )
            )
            continue
        included_documents.append(
            _document_entry(
                label=_payment_label(code, payment_form),
                path=path,
                source_type=PAYMENT_SOURCE_TYPE,
                section="Payment",
                form_key=form_key,
                checklist_item_code=code,
                page_count=page_count,
            )
        )


def _upload_sort_key(upload: UploadedDocument) -> tuple[int, datetime]:
    created_at = upload.created_at or datetime.min.replace(tzinfo=UTC)
    return (
        I485_PACKET_UPLOAD_ORDER.get(upload.checklist_item_code or "", 9000),
        created_at,
    )


def _upload_exclusion_reason(
    upload: UploadedDocument,
    explicit_upload_selection: bool,
    generated_form_upload_codes: set[str] | None = None,
) -> str | None:
    code = upload.checklist_item_code or ""
    if code in (generated_form_upload_codes or set()):
        return "Generated form is already included in this packet; uploaded form PDFs are skipped to avoid duplicate forms."
    if code in I485_PACKET_EXCLUDED_UPLOAD_CODES:
        return "Excluded from this compilation because the packet is centered on I-485, not I-130/I-130A petition materials."
    if not explicit_upload_selection and code and code not in I485_PACKET_UPLOAD_ORDER:
        return "Upload is not mapped to the USCIS-ordered I-485 packet document set."
    return None


def _upload_label(upload: UploadedDocument, checklist_by_code: dict[str, CaseChecklistItem]) -> str:
    item = checklist_by_code.get(upload.checklist_item_code or "")
    if item:
        return f"{item.label}: {upload.original_filename}"
    return upload.original_filename


def _packet_section_for_upload_code(checklist_code: str, form_sequence: list[str]) -> str:
    if checklist_code in I485_PACKET_PAYMENT_UPLOAD_CODES:
        return "Payment"
    if checklist_code in I485_SECTION_UPLOAD_CODES:
        return "I-485 section"
    if checklist_code in I864_SECTION_UPLOAD_CODES:
        return "I-864 section"
    if checklist_code == "medical_exam_i693":
        return "I-693 medical section"
    if "i765" in form_sequence and checklist_code in I765_SECTION_UPLOAD_CODES:
        return "I-765 section"
    if "i131" in form_sequence and checklist_code in I131_SECTION_UPLOAD_CODES:
        return "I-131 section"
    return "Additional uploaded documents"


def _incomplete_upload_reason(upload: UploadedDocument) -> str:
    if upload.upload_status == "requested":
        return "Upload was started, but the file was never received. Re-upload this PDF before generating the packet."
    if upload.upload_status == "uploaded":
        return "Upload file was received but not confirmed. Confirm or re-upload this PDF before generating the packet."
    return f"Upload status is {upload.upload_status}; only confirmed uploads are merged into the packet."


def _append_generated_form_document(
    *,
    writer: PdfWriter,
    session: Session,
    case_id: UUID,
    values: dict[str, Any],
    form_key: str,
    section: str,
    allow_incomplete: bool,
    included_documents: list[dict[str, Any]],
    skipped_documents: list[dict[str, Any]],
    warnings: list[str],
) -> None:
    try:
        label, path, form_warnings = _generate_packet_form(
            session=session,
            case_id=case_id,
            form_key=form_key,
            values=values,
            allow_incomplete=allow_incomplete,
        )
        page_count = _append_pdf_pages(writer, path)
        included_documents.append(
            _document_entry(
                label=label,
                path=path,
                source_type="generated_form",
                section=section,
                form_key=form_key,
                page_count=page_count,
            )
        )
        warnings.extend(_relevant_form_warnings(label, form_warnings))
    except Exception as exc:
        skipped_documents.append(
            _skipped_entry(
                label=f"Form {form_key.upper()}",
                form_key=form_key,
                section=section,
                source_type="generated_form",
                reason=str(exc),
            )
        )


def _append_upload_document(
    *,
    writer: PdfWriter,
    upload: UploadedDocument,
    section: str,
    output_dir: Path,
    checklist_by_code: dict[str, CaseChecklistItem],
    explicit_upload_selection: bool,
    generated_form_upload_codes: set[str] | None,
    included_documents: list[dict[str, Any]],
    skipped_documents: list[dict[str, Any]],
) -> None:
    label = _upload_label(upload, checklist_by_code)
    path = _safe_upload_path(upload)
    exclusion_reason = _upload_exclusion_reason(upload, explicit_upload_selection, generated_form_upload_codes)
    if exclusion_reason:
        skipped_documents.append(
            _skipped_entry(
                label=label,
                reason=exclusion_reason,
                source_type="upload",
                section=section,
                checklist_item_code=upload.checklist_item_code,
                upload_id=upload.id,
                path=path,
            )
        )
        return
    if path is None:
        skipped_documents.append(
            _skipped_entry(
                label=label,
                reason="Upload file path was not available.",
                source_type="upload",
                section=section,
                checklist_item_code=upload.checklist_item_code,
                upload_id=upload.id,
            )
        )
        return
    if (upload.mime_type or "").lower() != "application/pdf":
        skipped_documents.append(
            _skipped_entry(
                label=label,
                reason="Only uploaded PDFs can be merged into the printable packet.",
                source_type="upload",
                section=section,
                checklist_item_code=upload.checklist_item_code,
                upload_id=upload.id,
                path=path,
            )
        )
        return
    if not path.exists():
        skipped_documents.append(
            _skipped_entry(
                label=label,
                reason="Uploaded file was not found on disk.",
                source_type="upload",
                section=section,
                checklist_item_code=upload.checklist_item_code,
                upload_id=upload.id,
                path=path,
            )
        )
        return
    try:
        page_count = _append_upload_pdf_pages(writer, path, output_dir, upload.id)
    except Exception as exc:
        skipped_documents.append(
            _skipped_entry(
                label=label,
                reason=f"Could not read PDF: {exc}",
                source_type="upload",
                section=section,
                checklist_item_code=upload.checklist_item_code,
                upload_id=upload.id,
                path=path,
            )
        )
        return
    included_documents.append(
        _document_entry(
            label=label,
            path=path,
            source_type="upload",
            section=section,
            checklist_item_code=upload.checklist_item_code,
            upload_id=upload.id,
            page_count=page_count,
        )
    )


def _cover_letter_item(document: dict[str, Any]) -> str | None:
    if document.get("source_type") == "generated_form":
        return COVER_LETTER_FORM_ITEMS.get(document.get("form_key") or "")
    checklist_code = document.get("checklist_item_code") or ""
    return COVER_LETTER_UPLOAD_ITEMS.get(checklist_code)


def _add_cover_letter_item(
    section_payload: dict[str, Any],
    seen_items: dict[str, set[str]],
    item: str | dict[str, Any],
) -> None:
    section_label = section_payload["label"]
    item_key = item["label"] if isinstance(item, dict) else item
    if item_key in seen_items.setdefault(section_label, set()):
        return
    section_payload["items"].append(item)
    seen_items[section_label].add(item_key)


def _cover_letter_sections(included_documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    by_label: dict[str, dict[str, Any]] = {}
    seen_items: dict[str, set[str]] = {}
    payment_fee_items: list[str] = []
    payment_form_keys: set[str | None] = set()
    has_payment_form = False
    i485_bona_fide_items: list[str] = []

    for document in included_documents:
        section = document.get("section") or "Additional uploaded documents"
        if section == "Cover letter":
            continue
        section_payload = by_label.get(section)
        if section_payload is None:
            section_payload = {"label": section, "items": []}
            by_label[section] = section_payload
            sections.append(section_payload)

        if section == "Payment":
            checklist_code = document.get("checklist_item_code") or ""
            payment_form_keys.add(document.get("form_key"))
            fee_item = COVER_LETTER_PAYMENT_FEE_ITEMS.get(checklist_code)
            if fee_item:
                payment_fee_items.append(fee_item)
            else:
                has_payment_form = True
            continue

        checklist_code = document.get("checklist_item_code") or ""
        item_label = _cover_letter_item(document)
        if not item_label:
            continue
        if section == "Additional uploaded documents" and any(
            item_label in section_seen for section_seen in seen_items.values()
        ):
            continue
        if section == "I-485 section" and checklist_code in I485_BONA_FIDE_CODES:
            if item_label not in i485_bona_fide_items:
                i485_bona_fide_items.append(item_label)
            continue
        _add_cover_letter_item(section_payload, seen_items, item_label)

    payment_section = by_label.get("Payment")
    if payment_section is not None:
        unique_payment_fees = list(dict.fromkeys(payment_fee_items))
        if unique_payment_fees:
            _add_cover_letter_item(
                payment_section,
                seen_items,
                {
                    "label": (
                        "Form G-1650 (ACH Authorization) for:"
                        if "g1650" in payment_form_keys
                        else "Form G-1450 (Credit Card Authorization) for:"
                    ),
                    "children": unique_payment_fees,
                },
            )
        elif has_payment_form:
            _add_cover_letter_item(
                payment_section,
                seen_items,
                "Signed payment authorization (Form G-1450 or Form G-1650)",
            )

    i485_section = by_label.get("I-485 section")
    if i485_section is not None and i485_bona_fide_items:
        _add_cover_letter_item(
            i485_section,
            seen_items,
            {"label": "Evidence of bona fide marriage:", "children": i485_bona_fide_items},
        )
    return [section for section in sections if section["items"]]


def _supporting_item_labels(
    *,
    checklist_codes: tuple[str, ...],
    uploads_by_code: dict[str, list[UploadedDocument]],
    processed_upload_ids: set[UUID],
    checklist_by_code: dict[str, CaseChecklistItem],
) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for code in checklist_codes:
        pending_uploads = [upload for upload in uploads_by_code.get(code, []) if upload.id not in processed_upload_ids]
        if not pending_uploads:
            continue
        checklist_item = checklist_by_code.get(code)
        label = COVER_LETTER_UPLOAD_ITEMS.get(code) or (checklist_item.label if checklist_item else code)
        if label in seen:
            continue
        labels.append(label)
        seen.add(label)
    return labels


def _append_section_index_page(
    *,
    writer: PdfWriter,
    case_id: UUID,
    output_dir: Path,
    section: str,
    item_labels: list[str],
    included_documents: list[dict[str, Any]],
) -> None:
    purpose = SECTION_INDEX_PURPOSES.get(section)
    if not purpose:
        return
    generated = generate_section_index_pdf(
        case_id=case_id,
        section_label=section,
        purpose=purpose,
        items=item_labels,
        output_dir=output_dir,
    )
    page_count = _append_pdf_pages(writer, generated.output_path)
    included_documents.append(
        _document_entry(
            label=f"{section} index page",
            path=generated.output_path,
            source_type="generated_section_index",
            section=section,
            form_key="section_index",
            page_count=page_count,
        )
    )


def _cover_letter_insert_index(included_documents: list[dict[str, Any]]) -> int:
    index = 0
    while index < len(included_documents) and included_documents[index].get("section") == "Payment":
        index += 1
    return index


def _page_index_for_document_insert(included_documents: list[dict[str, Any]], document_index: int) -> int:
    return sum(document.get("page_count", 0) for document in included_documents[:document_index])


def _checklist_lookup(session: Session, case_id: UUID) -> dict[str, CaseChecklistItem]:
    items, _facts = get_checklist(session, case_id)
    if not items:
        items, _facts = generate_checklist(session, case_id)
    return {item.code: item for item in items}


def assemble_packet_pdf(
    *,
    session: Session,
    case_id: UUID,
    state_code: str | None,
    carrier: str = "usps",
    include_upload_ids: list[UUID] | None = None,
    include_supporting_evidence: bool = True,
    include_generated_forms: bool = True,
    allow_incomplete: bool = True,
    g1450_payment_payload: dict[str, Any] | None = None,
    selected_payment_checklist_codes: list[str] | None = None,
    g1450_template_path: Path | None = None,
    g1650_payment_payload: dict[str, Any] | None = None,
    g1650_template_path: Path | None = None,
    output_dir: Path = PACKET_OUTPUT_DIR,
) -> PacketAssemblyResult:
    values = get_merged_case_intake(session, case_id)
    facts = derive_case_facts(values)
    checklist_by_code = _checklist_lookup(session, case_id)
    body_writer = PdfWriter()
    included_documents: list[dict[str, Any]] = []
    skipped_documents: list[dict[str, Any]] = []
    warnings = [
        "Review every generated form and supporting document before printing and mailing.",
        "This packet is an organizational draft, not legal advice.",
        (
            "USCIS mail-filing guidance verified by this app on "
            f"{PACKET_ASSEMBLY_GUIDANCE_VERIFIED_ON} places payment first, then G-1145, "
            "then the filed form and supporting documents."
        ),
        (
            "When printing, use single-sided 8.5 x 11 letter-size pages and avoid binders, folders, "
            "tabs, sticky notes, heavy staples, folded pages, duplicate evidence copies, albums, "
            "scrapbooks, digital media, and unnecessary original documents."
        ),
        f"Packet section order is based on the local outline in {PACKET_OUTLINE_SOURCE_PATH}.",
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    form_sequence = _packet_form_sequence(session, case_id, facts)
    explicit_upload_selection = include_upload_ids is not None
    uploads = sorted(_confirmed_uploads(session, case_id, include_upload_ids), key=_upload_sort_key)
    incomplete_uploads = sorted(_incomplete_uploads(session, case_id, include_upload_ids), key=_upload_sort_key)
    if not include_supporting_evidence:
        uploads = [
            upload
            for upload in uploads
            if (upload.checklist_item_code or "") in I485_PACKET_PAYMENT_UPLOAD_CODES
        ]
        incomplete_uploads = [
            upload
            for upload in incomplete_uploads
            if (upload.checklist_item_code or "") in I485_PACKET_PAYMENT_UPLOAD_CODES
        ]
        warnings.append("Supporting evidence uploads were intentionally excluded from this forms-only packet.")
    uploads_by_code: dict[str, list[UploadedDocument]] = {}
    for upload in uploads:
        uploads_by_code.setdefault(upload.checklist_item_code or "", []).append(upload)
    processed_upload_ids: set[UUID] = set()
    generated_form_upload_codes = GENERATED_FORM_UPLOAD_CODES if include_generated_forms else set()

    def append_uploads(checklist_code: str, section: str, *, duplicate: bool = False) -> None:
        for upload in uploads_by_code.get(checklist_code, []):
            if upload.id in processed_upload_ids and not duplicate:
                continue
            _append_upload_document(
                writer=body_writer,
                upload=upload,
                section=section,
                output_dir=output_dir,
                checklist_by_code=checklist_by_code,
                explicit_upload_selection=explicit_upload_selection,
                generated_form_upload_codes=generated_form_upload_codes,
                included_documents=included_documents,
                skipped_documents=skipped_documents,
            )
            processed_upload_ids.add(upload.id)

    def append_generated_form(form_key: str, section: str) -> None:
        if not include_generated_forms:
            return
        _append_generated_form_document(
            writer=body_writer,
            session=session,
            case_id=case_id,
            values=values,
            form_key=form_key,
            section=section,
            allow_incomplete=allow_incomplete,
            included_documents=included_documents,
            skipped_documents=skipped_documents,
            warnings=warnings,
        )

    def append_section_index(section: str, checklist_codes: tuple[str, ...], *, require_items: bool = False) -> None:
        if not include_generated_forms or not include_supporting_evidence:
            return
        item_labels = _supporting_item_labels(
            checklist_codes=checklist_codes,
            uploads_by_code=uploads_by_code,
            processed_upload_ids=processed_upload_ids,
            checklist_by_code=checklist_by_code,
        )
        if require_items and not item_labels:
            return
        _append_section_index_page(
            writer=body_writer,
            case_id=case_id,
            output_dir=output_dir,
            section=section,
            item_labels=item_labels,
            included_documents=included_documents,
        )

    uploaded_payment_included = False
    if g1450_payment_payload is None and g1650_payment_payload is None:
        before_payment_upload_count = len(included_documents)
        for code in I485_PACKET_PAYMENT_UPLOAD_CODES:
            append_uploads(code, "Payment")
        uploaded_payment_included = len(included_documents) > before_payment_upload_count

    if include_generated_forms:
        _append_payment_forms(
            writer=body_writer,
            session=session,
            case_id=case_id,
            output_dir=output_dir,
            included_documents=included_documents,
            skipped_documents=skipped_documents,
            warnings=warnings,
            payment_payload=g1650_payment_payload or g1450_payment_payload,
            selected_payment_checklist_codes=selected_payment_checklist_codes,
            template_path=(
                g1650_template_path or settings.g1650_template_path
                if g1650_payment_payload
                else g1450_template_path or settings.g1450_template_path
            ),
            uploaded_payment_included=uploaded_payment_included,
            payment_form="G-1650" if g1650_payment_payload else "G-1450",
        )

    append_generated_form("g1145", "Form G-1145")

    for code in I485_SECTION_UPLOAD_CODES:
        if code == "form_i485":
            append_generated_form("i485", "I-485 section")
            append_uploads(code, "I-485 section")
            append_section_index(
                "I-485 section",
                tuple(
                    evidence_code
                    for evidence_code in I485_SECTION_UPLOAD_CODES
                    if evidence_code not in {"beneficiary_passport_photos", "form_i485"}
                ),
            )
            continue
        append_uploads(code, "I-485 section")

    append_generated_form("i864", "I-864 section")
    for code in I864_SECTION_UPLOAD_CODES:
        append_uploads(code, "I-864 section")
        if code == "form_i864":
            append_section_index(
                "I-864 section",
                tuple(evidence_code for evidence_code in I864_SECTION_UPLOAD_CODES if evidence_code != "form_i864"),
            )

    append_section_index("I-693 medical section", ("medical_exam_i693",), require_items=True)
    append_uploads("medical_exam_i693", "I-693 medical section")

    if "i765" in form_sequence:
        append_generated_form("i765", "I-765 section")
        append_section_index(
            "I-765 section",
            tuple(evidence_code for evidence_code in I765_SECTION_UPLOAD_CODES if evidence_code != "form_i765"),
        )
        for code in I765_SECTION_UPLOAD_CODES:
            append_uploads(code, "I-765 section")

    if "i131" in form_sequence:
        append_generated_form("i131", "I-131 section")
        append_section_index(
            "I-131 section",
            tuple(evidence_code for evidence_code in I131_SECTION_UPLOAD_CODES if evidence_code != "form_i131"),
        )
        for code in I131_SECTION_UPLOAD_CODES:
            append_uploads(code, "I-131 section")

    for upload in uploads:
        if upload.id in processed_upload_ids:
            continue
        _append_upload_document(
            writer=body_writer,
            upload=upload,
            section="Additional uploaded documents",
            output_dir=output_dir,
            checklist_by_code=checklist_by_code,
            explicit_upload_selection=explicit_upload_selection,
            generated_form_upload_codes=generated_form_upload_codes,
            included_documents=included_documents,
            skipped_documents=skipped_documents,
        )
        processed_upload_ids.add(upload.id)

    for upload in incomplete_uploads:
        code = upload.checklist_item_code or ""
        if code and uploads_by_code.get(code):
            continue
        if _upload_exclusion_reason(upload, explicit_upload_selection, generated_form_upload_codes):
            continue
        if not explicit_upload_selection and code and code not in I485_PACKET_UPLOAD_ORDER:
            continue
        skipped_documents.append(
            _skipped_entry(
                label=_upload_label(upload, checklist_by_code),
                reason=_incomplete_upload_reason(upload),
                source_type="upload",
                section=_packet_section_for_upload_code(code, form_sequence),
                checklist_item_code=upload.checklist_item_code,
                upload_id=upload.id,
                path=_safe_upload_path(upload),
            )
        )

    if not any(document["source_type"] != "generated_section_index" for document in included_documents):
        raise ValueError("No valid PDF pages were available to merge.")

    mailing_recommendation = mailing_recommendation_for_location(state_code, carrier)

    if include_generated_forms:
        cover_letter = generate_cover_letter_pdf(
            case_id=case_id,
            values=values,
            sections=_cover_letter_sections(included_documents),
            output_dir=output_dir,
            lockbox_address_lines=(
                mailing_recommendation["address_lines"] if mailing_recommendation else None
            ),
        )
        document_insert_index = _cover_letter_insert_index(included_documents)
        page_insert_index = _page_index_for_document_insert(included_documents, document_insert_index)
        cover_page_count = _insert_pdf_pages(body_writer, cover_letter.output_path, page_insert_index)
        included_documents.insert(
            document_insert_index,
            _document_entry(
                label="Cover letter",
                path=cover_letter.output_path,
                source_type="generated_cover_letter",
                section="Cover letter",
                form_key="cover_letter",
                page_count=cover_page_count,
            ),
        )
        warnings.extend(cover_letter.warnings)

    output_path = output_dir / f"{case_id}-full-packet.pdf"
    with output_path.open("wb") as handle:
        body_writer.write(handle)
    manifest_path = output_dir / f"{case_id}-full-packet-manifest.json"

    if skipped_documents:
        warnings.append("Some files were skipped because they were missing, non-PDF, or unreadable.")

    if state_code and mailing_recommendation is None:
        warnings.append("The selected location was not recognized for USCIS lockbox routing.")
    if mailing_recommendation is None:
        warnings.append("Select the filer location before mailing so Lucy can show USCIS lockbox guidance.")
    else:
        warnings.append("Before mailing, verify the address on the live USCIS lockbox page.")

    unique_warnings = list(dict.fromkeys(warnings))
    total_page_count = sum(document["page_count"] for document in included_documents)
    _write_manifest(
        case_id=case_id,
        output_path=output_path,
        manifest_path=manifest_path,
        generated_at=_utcnow(),
        selected_location=state_code,
        selected_carrier=carrier,
        include_supporting_evidence=include_supporting_evidence,
        total_page_count=total_page_count,
        included_documents=included_documents,
        skipped_documents=skipped_documents,
        warnings=unique_warnings,
        mailing_recommendation=mailing_recommendation,
    )

    return PacketAssemblyResult(
        case_id=case_id,
        output_path=output_path,
        manifest_path=manifest_path,
        total_page_count=total_page_count,
        included_documents=included_documents,
        skipped_documents=skipped_documents,
        warnings=unique_warnings,
        mailing_recommendation=mailing_recommendation,
    )
