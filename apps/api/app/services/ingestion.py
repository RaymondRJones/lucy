from __future__ import annotations

import hashlib
import logging
import re
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from uuid import UUID

from pypdf import PdfReader
from sqlmodel import Session, select

from app.content.uscis_requirements import USCIS_REQUIREMENT_BY_CHECKLIST_CODE
from app.core.config import settings
from app.models.entities import CaseRecord, IntakeResponse, OCRStatus, UploadedDocument, UploadStatus
from app.services.checklist import generate_checklist
from app.services.i485 import import_i485_answers_from_upload
from app.services.intake import apply_case_projection, get_merged_case_intake, normalize_country
from app.services.qa import run_qa
from app.services.upload_links import infer_satisfied_checklist_codes


logger = logging.getLogger(__name__)


DATE_RE = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
INGESTED_INTAKE_KEYS = {
    "petitioner_first_name",
    "petitioner_middle_name",
    "petitioner_last_name",
    "petitioner_date_of_birth",
    "petitioner_country_of_birth",
    "petitioner_current_address_line1",
    "petitioner_current_address_line2",
    "petitioner_current_city",
    "petitioner_current_state",
    "petitioner_current_zip",
    "beneficiary_first_name",
    "beneficiary_middle_name",
    "beneficiary_last_name",
    "beneficiary_date_of_birth",
    "beneficiary_city_of_birth",
    "beneficiary_birth_department",
    "beneficiary_country_of_birth",
    "beneficiary_current_immigration_status",
    "beneficiary_i94_number",
    "beneficiary_last_arrival_date",
    "beneficiary_status_expires_on",
    "beneficiary_current_status_expires_on",
    "beneficiary_current_address_line1",
    "beneficiary_current_address_line2",
    "beneficiary_current_city",
    "beneficiary_current_state",
    "beneficiary_current_zip",
    "beneficiary_address_since",
    "beneficiary_passport_number",
    "beneficiary_location",
    "beneficiary_entered_us_legally",
    "marriage_date",
    "marriage_place_city",
    "marriage_place_state",
    "marriage_place_country",
    "petitioner_first_marriage_detected",
    "beneficiary_first_marriage_detected",
}


@dataclass
class InferredDocument:
    source_path: str
    checklist_item_code: str | None
    document_type: str
    document_language: str
    has_translation: bool
    requires_translation: bool
    text: str
    extracted_fields: dict[str, Any]


def _clean_token(token: str) -> str:
    token = re.sub(r"Form I-\d+[A-Z-]*\s+Edition.*", "", token).strip()
    return token.replace("►", "").strip()


def _pdf_text(path: Path) -> str:
    reader = PdfReader(path)
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:  # noqa: BLE001 - unreadable uploads should still scan as empty text
            logger.warning("Could not decrypt PDF during scan: %s", type(exc).__name__)
    parts: list[str] = []
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            parts.append(page.extract_text() or "")
        except Exception as exc:  # noqa: BLE001 - one malformed page should not fail the whole document
            logger.warning("Skipped unreadable PDF page %d during scan: %s", page_number, type(exc).__name__)
    return "\n".join(parts)


def _tokens(text: str) -> list[str]:
    return [_clean_token(token) for token in text.replace("\n", " | ").split("|") if token.strip()]


def _find_index(tokens: list[str], marker: str) -> int | None:
    for index, token in enumerate(tokens):
        if marker in token:
            return index
    return None


def _find_date_in_token(token: str) -> str | None:
    match = DATE_RE.search(token)
    return match.group(1) if match else None


def _to_iso_date(value: str | None) -> str | None:
    if not value:
        return None
    parts = value.split("/")
    if len(parts) != 3:
        return None
    month, day, year = parts
    return date(int(year), int(month), int(day)).isoformat()


def _extract_form_edition(text: str) -> str | None:
    match = re.search(r"Form\s+(I-\d+[A-Z-]*|G-1145)\s+Edition\s+(\d{2}/\d{2}/\d{2})", text)
    return match.group(2) if match else None


def _strip_leading_label(token: str, label: str) -> str | None:
    cleaned = _clean_token(token)
    if cleaned.startswith(label):
        cleaned = cleaned[len(label) :].strip()
    return cleaned or None


def _compact_history_entry(**values: Any) -> dict[str, Any]:
    return {
        key: value
        for key, value in values.items()
        if value not in (None, "", [], {})
    }


def _append_history_entry(entries: list[dict[str, Any]], **values: Any) -> None:
    entry = _compact_history_entry(**values)
    if any(
        entry.get(key)
        for key in ("line1", "line2", "city", "state", "zip", "country", "from", "to")
    ):
        entries.append(entry)


def _build_person_name(first_name: Any, last_name: Any) -> str | None:
    parts = [
        str(part).strip()
        for part in (first_name, last_name)
        if part not in (None, "") and str(part).strip()
    ]
    return " ".join(parts) or None


def _build_address_value(*parts: Any) -> str | None:
    present = [
        str(part).strip()
        for part in parts
        if part not in (None, "") and str(part).strip()
    ]
    return ", ".join(present) or None


def _enrich_verification_fields(fields: dict[str, Any]) -> None:
    petitioner_name = _build_person_name(
        fields.get("petitioner_first_name"),
        fields.get("petitioner_last_name"),
    )
    if petitioner_name:
        fields["petitioner_name"] = petitioner_name

    beneficiary_name = _build_person_name(
        fields.get("beneficiary_first_name"),
        fields.get("beneficiary_last_name"),
    )
    if beneficiary_name:
        fields["beneficiary_name"] = beneficiary_name

    beneficiary_current_address = _build_address_value(
        fields.get("beneficiary_current_address_line1"),
        fields.get("beneficiary_current_address_line2"),
        fields.get("beneficiary_current_city"),
        fields.get("beneficiary_current_state"),
        fields.get("beneficiary_current_zip"),
        fields.get("beneficiary_current_country"),
    )
    if beneficiary_current_address:
        fields["beneficiary_current_address"] = beneficiary_current_address


def _has_embedded_i130a(text: str) -> bool:
    markers = (
        "Provide your physical addresses for the last five years",
        "Employment History",
        "42. Name of Employer/Company",
        "Provide your employment history for the last five years",
    )
    matches = sum(1 for marker in markers if marker in text)
    return matches >= 3


def _infer_language(path: Path, text: str) -> str:
    lowered_name = path.name.lower()
    lowered_text = text.lower()
    if "translated" in lowered_name:
        return "spanish"
    spanish_markers = [
        "republic of colombia",
        "registro",
        "nacimiento",
        "fecha de expedición",
        "nombre",
    ]
    if any(marker in lowered_text for marker in spanish_markers):
        return "spanish"
    return "english"


def _infer_mapping(path: Path, text: str = "") -> tuple[str | None, str, bool]:
    lowered = path.as_posix().lower()
    lowered_name = path.name.lower()
    lowered_text = text.lower()
    if lowered.endswith("i-130.pdf"):
        return "form_i130", "form_i130", False
    if "i-130a" in lowered:
        return "form_i130a", "form_i130a", False
    if "i-485" in lowered_name or "i485" in lowered_name or "form i-485" in lowered_text[:3000]:
        return "form_i485", "form_i485", False
    if "/i-864-financial support form/i-864.pdf" in lowered:
        return "form_i864", "form_i864", False
    if "/i-765/" in lowered and path.name.lower().startswith("i-765"):
        return "form_i765", "form_i765", False
    if "/i-131/" in lowered and path.name.lower().startswith("i-131"):
        return "form_i131", "form_i131", False
    if "g-1145" in lowered:
        return "form_g1145", "form_g1145", False
    if "i94" in lowered or "i-94" in lowered:
        return "beneficiary_i94", "identity_i94", False
    if "birth" in lowered:
        return "beneficiary_birth_certificate", "civil_birth_record", "translated" in lowered
    if "passport photo" in lowered or "passport-photo" in lowered or "passport_photo" in lowered:
        return "beneficiary_passport_photos", "passport_photos", False
    if "lease" in lowered:
        return "joint_lease", "housing_evidence", False
    if "employment_verification" in lowered:
        return "employment_verification_letter", "employment_verification", False
    if "tax_returns" in lowered or "taxreturn" in lowered or "tax return" in lowered:
        return "sponsor_tax_return", "federal_tax_return", False
    if "pay_stubs" in lowered or "statement of earnings" in lowered:
        return "sponsor_pay_stubs", "pay_stub", False
    if "vaccine" in lowered or "vaccination" in lowered:
        return "medical_exam_supporting_records", "vaccination_record", False
    return None, "supporting_document", False


def _extract_i130_payload(text: str) -> dict[str, Any]:
    tokens = _tokens(text)
    payload: dict[str, Any] = {}

    full_name_index = _find_index(tokens, "Your Full Name")
    if full_name_index is not None and full_name_index + 8 < len(tokens):
        payload["petitioner_last_name"] = _clean_token(tokens[full_name_index + 6])
        payload["petitioner_first_name"] = _clean_token(tokens[full_name_index + 7])
        payload["petitioner_middle_name"] = _clean_token(tokens[full_name_index + 8])

    marriage_count_index = _find_index(tokens, "16. How many times have you been married?")
    if marriage_count_index is not None:
        count_match = re.search(r"(\d+)", tokens[marriage_count_index])
        if count_match and int(count_match.group(1)) == 1:
            payload["petitioner_first_marriage_detected"] = True

    marriage_index = _find_index(tokens, "18. Date of Current Marriage (if currently married)")
    if marriage_index is not None and marriage_index + 2 < len(tokens):
        payload["marriage_date"] = _to_iso_date(_find_date_in_token(tokens[marriage_index + 2]))
        if marriage_index + 8 < len(tokens):
            payload["marriage_place_city"] = _clean_token(tokens[marriage_index + 4]).replace(
                "19.a. City or Town", ""
            ).strip()
            payload["marriage_place_country"] = _clean_token(tokens[marriage_index + 8])
        if marriage_index + 20 < len(tokens):
            payload["beneficiary_last_name"] = _clean_token(tokens[marriage_index + 18])
            payload["beneficiary_first_name"] = _clean_token(tokens[marriage_index + 19])
            payload["beneficiary_middle_name"] = _clean_token(tokens[marriage_index + 20])

    i94_index = _find_index(tokens, "46.a. He or she arrived as a (Class of Admission):")
    if i94_index is not None and i94_index + 10 < len(tokens):
        payload["beneficiary_location"] = "usa"
        payload["beneficiary_entered_us_legally"] = True
        payload["beneficiary_current_immigration_status"] = _clean_token(tokens[i94_index + 1])
        payload["beneficiary_i94_number"] = _clean_token(tokens[i94_index + 3])
        payload["beneficiary_last_arrival_date"] = _to_iso_date(_find_date_in_token(tokens[i94_index + 4]))
        payload["beneficiary_status_expires_on"] = _to_iso_date(_clean_token(tokens[i94_index + 8]))
        payload["beneficiary_passport_number"] = _clean_token(tokens[i94_index + 10])

    country_index = _find_index(tokens, "7. Country of Birth")
    if country_index is not None and country_index + 2 < len(tokens):
        payload["beneficiary_city_of_birth"] = _clean_token(tokens[country_index + 1])
        payload["beneficiary_country_of_birth"] = normalize_country(tokens[country_index + 2])

    address_history_index = _find_index(tokens, "Provide your physical addresses for the last five years")
    if address_history_index is not None and address_history_index + 27 < len(tokens):
        current_line1 = _strip_leading_label(tokens[address_history_index + 6], "and Name")
        current_city = _strip_leading_label(tokens[address_history_index + 8], "12.c. City or Town")
        current_zip = _strip_leading_label(tokens[address_history_index + 9], "12.d. 12.e. Zip Code")
        current_country = _clean_token(tokens[address_history_index + 13])
        if current_line1:
            payload["beneficiary_current_address_line1"] = current_line1
        if current_city:
            payload["beneficiary_current_city"] = current_city
        if current_zip:
            payload["beneficiary_current_zip"] = current_zip
        if current_country:
            payload["beneficiary_current_country"] = current_country

        address_history: list[dict[str, Any]] = []
        _append_history_entry(
            address_history,
            line1=current_line1,
            city=current_city,
            zip=current_zip,
            country=current_country,
        )

        prior_line1 = _strip_leading_label(tokens[address_history_index + 18], "and Name")
        prior_line2 = _strip_leading_label(tokens[address_history_index + 19], "14.b. Ste.Apt. Flr.")
        prior_city = _strip_leading_label(tokens[address_history_index + 20], "14.c. City or Town")
        prior_state = _strip_leading_label(tokens[address_history_index + 22], "14.f. Province")
        prior_zip = _strip_leading_label(tokens[address_history_index + 23], "14.g. Postal Code")
        prior_country = _clean_token(tokens[address_history_index + 25])
        prior_from = _to_iso_date(_find_date_in_token(tokens[address_history_index + 26]))
        prior_to = _to_iso_date(_find_date_in_token(tokens[address_history_index + 27]))
        _append_history_entry(
            address_history,
            line1=prior_line1,
            line2=prior_line2,
            city=prior_city,
            state=prior_state,
            zip=prior_zip,
            country=prior_country,
            **{"from": prior_from, "to": prior_to},
        )
        if address_history:
            payload["beneficiary_address_history"] = address_history
        if len(address_history) > 1:
            payload["beneficiary_prior_address_history"] = address_history[1:]

    return {key: value for key, value in payload.items() if value not in (None, "", [])}


def _extract_i485_payload(text: str) -> dict[str, Any]:
    tokens = _tokens(text)
    payload: dict[str, Any] = {}

    base_index = _find_index(tokens, "Date of Birth (mm/dd/yyyy)3.")
    if base_index is not None and base_index + 6 < len(tokens):
        payload["beneficiary_last_name"] = _clean_token(tokens[base_index + 4])
        payload["beneficiary_first_name"] = _clean_token(tokens[base_index + 5])
        payload["beneficiary_middle_name"] = _clean_token(tokens[base_index + 6])
        payload["beneficiary_date_of_birth"] = _to_iso_date(_clean_token(tokens[base_index + 7]))

    i94_index = _find_index(tokens, "What is your current immigration status (if it has changed since your last arrival)?")
    if i94_index is not None and i94_index + 34 < len(tokens):
        payload["beneficiary_location"] = "usa"
        payload["beneficiary_entered_us_legally"] = True
        payload["beneficiary_current_immigration_status"] = _clean_token(tokens[i94_index + 32])
        payload["beneficiary_i94_number"] = _clean_token(tokens[i94_index + 30])
        payload["beneficiary_status_expires_on"] = _to_iso_date(_clean_token(tokens[i94_index + 31]))
        payload["beneficiary_current_status_expires_on"] = _to_iso_date(_clean_token(tokens[i94_index + 34]))
        payload["beneficiary_current_address_line1"] = _clean_token(tokens[i94_index + 36])
        payload["beneficiary_current_address_line2"] = _clean_token(tokens[i94_index + 37])
        payload["beneficiary_current_city"] = _clean_token(tokens[i94_index + 38])
        payload["beneficiary_current_state"] = _clean_token(tokens[i94_index + 39])
        payload["beneficiary_current_zip"] = _clean_token(tokens[i94_index + 40])
        payload["beneficiary_address_since"] = _to_iso_date(_clean_token(tokens[i94_index + 41]))
        payload["beneficiary_current_country"] = "United States"

    history_index = _find_index(tokens, "Have you resided at your current address for at least 5 years?")
    if history_index is not None and history_index + 35 < len(tokens):
        prior_address_history: list[dict[str, Any]] = []
        prior_from = _to_iso_date(_clean_token(tokens[history_index + 34]))
        prior_to = _to_iso_date(_clean_token(tokens[history_index + 35]))
        if prior_from or prior_to:
            _append_history_entry(
                prior_address_history,
                in_care_of=_clean_token(tokens[history_index + 27]),
                line1=_clean_token(tokens[history_index + 28]),
                line2=_clean_token(tokens[history_index + 29]),
                city=_clean_token(tokens[history_index + 30]),
                state=_clean_token(tokens[history_index + 31]),
                zip=_clean_token(tokens[history_index + 32]),
                country=_clean_token(tokens[history_index + 33]),
                **{"from": prior_from, "to": prior_to},
            )
        if prior_address_history:
            payload["beneficiary_prior_address_history"] = prior_address_history
            address_history: list[dict[str, Any]] = []
            _append_history_entry(
                address_history,
                line1=payload.get("beneficiary_current_address_line1"),
                line2=payload.get("beneficiary_current_address_line2"),
                city=payload.get("beneficiary_current_city"),
                state=payload.get("beneficiary_current_state"),
                zip=payload.get("beneficiary_current_zip"),
                country=payload.get("beneficiary_current_country"),
                **{"from": payload.get("beneficiary_address_since")},
            )
            address_history.extend(prior_address_history)
            payload["beneficiary_address_history"] = address_history

    spouse_index = _find_index(tokens, "Current Spouse's Current Physical Address8.")
    if spouse_index is not None and spouse_index + 15 < len(tokens):
        marriage_count = _clean_token(tokens[spouse_index + 4])
        if marriage_count == "1":
            payload["beneficiary_first_marriage_detected"] = True
        payload["petitioner_last_name"] = _clean_token(tokens[spouse_index + 5])
        payload["petitioner_first_name"] = _clean_token(tokens[spouse_index + 6])
        payload["petitioner_middle_name"] = _clean_token(tokens[spouse_index + 7])
        payload["petitioner_date_of_birth"] = _to_iso_date(_clean_token(tokens[spouse_index + 9]))
        payload["petitioner_country_of_birth"] = normalize_country(tokens[spouse_index + 10])
        payload["petitioner_current_address_line1"] = _clean_token(tokens[spouse_index + 11])
        payload["petitioner_current_address_line2"] = _clean_token(tokens[spouse_index + 12])
        payload["petitioner_current_city"] = _clean_token(tokens[spouse_index + 13])
        payload["petitioner_current_state"] = _clean_token(tokens[spouse_index + 14])
        payload["petitioner_current_zip"] = _clean_token(tokens[spouse_index + 15])

    marriage_index = _find_index(tokens, "Date of Marriage with Prior Spouse Legally Ended")
    if marriage_index is not None and marriage_index + 6 < len(tokens):
        payload["marriage_place_city"] = _clean_token(tokens[marriage_index + 3])
        payload["marriage_place_state"] = _clean_token(tokens[marriage_index + 4])
        payload["marriage_place_country"] = _clean_token(tokens[marriage_index + 5])
        payload["marriage_date"] = _to_iso_date(_clean_token(tokens[marriage_index + 6]))

    return {key: value for key, value in payload.items() if value not in (None, "", [])}


def _extract_birth_certificate_payload(text: str) -> dict[str, Any]:
    normalized = re.sub(r"\s+", " ", text.replace("─", " "))
    payload: dict[str, Any] = {}
    surname_match = re.search(
        r"First Surname Second Surname\s+([A-Z]+)\s+([A-Z]+)\s+Name\(s\)\s+([A-Z ]+?)\s+Date of birth",
        normalized,
        re.S,
    )
    if surname_match:
        last_name = f"{surname_match.group(1)} {surname_match.group(2)}"
        given_names = " ".join(surname_match.group(3).split())
        names = given_names.split()
        payload["beneficiary_last_name"] = last_name.title()
        if names:
            payload["beneficiary_first_name"] = names[0].title()
        if len(names) > 1:
            payload["beneficiary_middle_name"] = " ".join(name.title() for name in names[1:])

    birth_match = re.search(
        r"Year\s+(\d)\s+(\d)\s+(\d)\s+(\d)\s+Mo\.\s+(\d)\s+(\d)\s+Day\s+(\d)\s+(\d).*?Place of birth.*?([A-Z]+)\s*-\s*([A-Z]+)\s*-\s*([A-Z]+)",
        normalized,
        re.S,
    )
    if birth_match:
        year = "".join(birth_match.group(index) for index in range(1, 5))
        month = "".join(birth_match.group(index) for index in range(5, 7))
        day = "".join(birth_match.group(index) for index in range(7, 9))
        payload["beneficiary_date_of_birth"] = f"{year}-{month}-{day}"
        payload["beneficiary_city_of_birth"] = birth_match.group(9).title()
        payload["beneficiary_birth_department"] = birth_match.group(10).title()
        payload["beneficiary_country_of_birth"] = normalize_country(birth_match.group(11))

    return {key: value for key, value in payload.items() if value not in (None, "", [])}


def _extract_document_fields(path: Path, text: str, checklist_item_code: str | None) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "source_path": path.as_posix(),
        "ingested_from_filesystem": True,
    }
    edition = _extract_form_edition(text)
    if edition:
        fields["form_edition"] = edition

    if checklist_item_code == "form_i130":
        fields.update(_extract_i130_payload(text))
    elif checklist_item_code == "form_i485":
        fields.update(_extract_i485_payload(text))
    elif checklist_item_code == "beneficiary_birth_certificate":
        fields.update(_extract_birth_certificate_payload(text))

    extra_codes: list[str] = []
    if checklist_item_code == "form_i130" and _has_embedded_i130a(text):
        fields["embedded_i130a_detected"] = True
        extra_codes.append("form_i130a")

    requirement = USCIS_REQUIREMENT_BY_CHECKLIST_CODE.get(checklist_item_code or "")
    if requirement and edition:
        fields["current_uscis_accepted_edition"] = requirement["accepted_edition"]
        fields["edition_matches_current_uscis_requirement"] = edition == requirement["accepted_edition"]

    if checklist_item_code or extra_codes:
        fields["satisfies_checklist_codes"] = infer_satisfied_checklist_codes(
            checklist_item_code,
            {"satisfies_checklist_codes": extra_codes},
        )

    _enrich_verification_fields(fields)
    return fields


def scan_document(path: Path) -> InferredDocument:
    text = _pdf_text(path) if path.suffix.lower() == ".pdf" else ""
    checklist_item_code, document_type, has_translation = _infer_mapping(path, text)
    document_language = _infer_language(path, text)
    requires_translation = document_language != "english" and not has_translation
    extracted_fields = _extract_document_fields(path, text, checklist_item_code)
    if checklist_item_code:
        extracted_fields["satisfies_checklist_codes"] = infer_satisfied_checklist_codes(
            checklist_item_code,
            extracted_fields,
            has_translation=has_translation,
        )
    return InferredDocument(
        source_path=path.as_posix(),
        checklist_item_code=checklist_item_code,
        document_type=document_type,
        document_language=document_language,
        has_translation=has_translation,
        requires_translation=requires_translation,
        text=text,
        extracted_fields=extracted_fields,
    )


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        while True:
            chunk = file_handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _existing_ingested_uploads(session: Session, case_id: UUID) -> dict[str, UploadedDocument]:
    uploads = list(session.exec(select(UploadedDocument).where(UploadedDocument.case_id == case_id)))
    mapped: dict[str, UploadedDocument] = {}
    for upload in uploads:
        source_path = str((upload.extracted_fields or {}).get("source_path") or "")
        if source_path:
            mapped[source_path] = upload
    return mapped


def _store_upload(
    session: Session,
    case_id: UUID,
    repo_root: Path,
    path: Path,
    inferred: InferredDocument,
    existing_by_source_path: dict[str, UploadedDocument],
) -> UploadedDocument:
    try:
        source_path = path.relative_to(repo_root).as_posix()
    except ValueError:
        source_path = path.as_posix()
    upload = existing_by_source_path.get(source_path)
    stored_filename = f"{case_id}-{path.name}"
    destination = settings.upload_dir / stored_filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)
    file_size = path.stat().st_size
    checksum = _checksum(path)

    version_count = len(
        list(
            session.exec(
                select(UploadedDocument).where(
                    UploadedDocument.case_id == case_id,
                    UploadedDocument.checklist_item_code == inferred.checklist_item_code,
                )
            )
        )
    )

    fields = dict(inferred.extracted_fields)
    fields["source_path"] = source_path
    fields["sha256"] = checksum

    if upload:
        upload.checklist_item_code = inferred.checklist_item_code
        upload.original_filename = path.name
        upload.stored_filename = stored_filename
        upload.mime_type = "application/pdf"
        upload.file_size = file_size
        upload.upload_status = UploadStatus.confirmed.value
        upload.ocr_status = OCRStatus.complete.value
        upload.extraction_confidence = 0.9 if inferred.text else 0.4
        upload.document_type = inferred.document_type
        upload.document_language = inferred.document_language
        upload.requires_translation = inferred.requires_translation
        upload.has_translation = inferred.has_translation
        upload.extracted_fields = fields
    else:
        upload = UploadedDocument(
            case_id=case_id,
            checklist_item_code=inferred.checklist_item_code,
            original_filename=path.name,
            stored_filename=stored_filename,
            mime_type="application/pdf",
            file_size=file_size,
            upload_status=UploadStatus.confirmed.value,
            ocr_status=OCRStatus.complete.value,
            extraction_confidence=0.9 if inferred.text else 0.4,
            document_type=inferred.document_type,
            document_language=inferred.document_language,
            requires_translation=inferred.requires_translation,
            has_translation=inferred.has_translation,
            version=max(1, version_count + 1),
            extracted_fields=fields,
        )
        session.add(upload)
        session.flush()
    return upload


def _merge_payloads(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for payload in payloads:
        for key, value in payload.items():
            if value not in (None, "", []):
                merged[key] = value
    return merged


def _derive_intake_payload(documents: list[InferredDocument]) -> dict[str, Any]:
    extracted = [
        {
            key: value
            for key, value in document.extracted_fields.items()
            if key in INGESTED_INTAKE_KEYS
        }
        for document in documents
    ]
    payload = _merge_payloads(extracted)
    payload["wants_i765"] = any(document.checklist_item_code == "form_i765" for document in documents)
    payload["wants_i131"] = any(document.checklist_item_code == "form_i131" for document in documents)
    payload["has_joint_lease"] = any(document.checklist_item_code == "joint_lease" for document in documents)
    payload["needs_translation"] = any(
        document.requires_translation or document.has_translation for document in documents
    )
    if payload.get("beneficiary_country_of_birth"):
        payload["country_of_focus"] = payload["beneficiary_country_of_birth"]
    payload["household_size"] = payload.get("household_size") or 2
    payload["beneficiary_location"] = payload.get("beneficiary_location") or "usa"
    payload["beneficiary_entered_us_legally"] = payload.get("beneficiary_entered_us_legally", True)
    payload["reviewed_current_fees"] = False
    payload["reviewed_current_form_editions"] = all(
        document.extracted_fields.get("edition_matches_current_uscis_requirement", True)
        for document in documents
        if document.checklist_item_code in USCIS_REQUIREMENT_BY_CHECKLIST_CODE
    )

    first_marriage_flags = [
        payload.get("petitioner_first_marriage_detected"),
        payload.get("beneficiary_first_marriage_detected"),
    ]
    if all(flag is True for flag in first_marriage_flags if flag is not None) and any(
        flag is True for flag in first_marriage_flags
    ):
        payload["first_marriage_for_both"] = True

    payload.pop("petitioner_first_marriage_detected", None)
    payload.pop("beneficiary_first_marriage_detected", None)
    return payload


def _link_translation_pairs(documents: list[InferredDocument]) -> None:
    has_translated_birth_record = any(
        document.checklist_item_code == "beneficiary_birth_certificate" and document.has_translation
        for document in documents
    )
    if has_translated_birth_record:
        for document in documents:
            if (
                document.checklist_item_code == "beneficiary_birth_certificate"
                and not document.has_translation
                and document.document_language != "english"
            ):
                document.has_translation = True
                document.requires_translation = False
                document.extracted_fields["paired_translation_detected"] = True
                document.extracted_fields["satisfies_checklist_codes"] = infer_satisfied_checklist_codes(
                    document.checklist_item_code,
                    document.extracted_fields,
                    has_translation=document.has_translation,
                )


def upsert_ingested_intake(session: Session, case_id: UUID, payload: dict[str, Any]) -> None:
    existing = session.exec(
        select(IntakeResponse).where(
            IntakeResponse.case_id == case_id,
            IntakeResponse.step_key == "ingested_documents",
        )
    ).first()
    if existing:
        existing.payload = payload
    else:
        session.add(IntakeResponse(case_id=case_id, step_key="ingested_documents", payload=payload))


def create_or_get_case(session: Session, case_id: UUID | None, case_name: str | None) -> CaseRecord:
    if case_id:
        existing = session.get(CaseRecord, case_id)
        if not existing:
            raise ValueError("Case not found")
        return existing

    name = case_name or "Imported marriage packet"
    case = CaseRecord(case_name=name, workflow_type="marriage_concurrent")
    session.add(case)
    session.flush()
    return case


def ingest_evidence_directory(
    session: Session,
    directory: Path,
    case_id: UUID | None = None,
    case_name: str | None = None,
) -> dict[str, Any]:
    repo_root = settings.upload_dir.parents[1]
    case = create_or_get_case(session, case_id, case_name)
    pdf_paths = sorted(path for path in directory.rglob("*.pdf") if path.is_file())
    documents = [scan_document(path) for path in pdf_paths]
    _link_translation_pairs(documents)
    existing_by_source_path = _existing_ingested_uploads(session, case.id)
    stored_uploads: list[UploadedDocument] = []

    for path, document in zip(pdf_paths, documents, strict=True):
        stored_uploads.append(_store_upload(session, case.id, repo_root, path, document, existing_by_source_path))

    intake_payload = _derive_intake_payload(documents)
    if "petitioner_first_name" in intake_payload and "beneficiary_first_name" in intake_payload and not case_name:
        case.case_name = (
            f"{intake_payload['petitioner_first_name']} & {intake_payload['beneficiary_first_name']} packet"
        )

    upsert_ingested_intake(session, case.id, intake_payload)
    apply_case_projection(session, case.id, get_merged_case_intake(session, case.id))
    session.add(case)

    i485_import_result: dict[str, Any] | None = None
    i485_upload = next(
        (
            upload
            for upload in stored_uploads
            if upload.checklist_item_code == "form_i485" or upload.document_type == "form_i485"
        ),
        None,
    )
    if i485_upload:
        i485_import_result = import_i485_answers_from_upload(session, case.id, i485_upload.id)

    session.commit()

    checklist_items, facts = generate_checklist(session, case.id)
    issues, summary = run_qa(session, case.id)

    matched = sum(1 for document in documents if document.checklist_item_code)
    unmatched = len(documents) - matched
    return {
        "case_id": str(case.id),
        "case_name": case.case_name,
        "documents_scanned": len(documents),
        "matched_documents": matched,
        "unmatched_documents": unmatched,
        "intake_payload": intake_payload,
        "facts": facts,
        "i485_import": {
            "imported_count": i485_import_result["imported_count"] if i485_import_result else 0,
            "skipped_count": i485_import_result["skipped_count"] if i485_import_result else 0,
            "proposal_count": len(i485_import_result["proposals"]) if i485_import_result else 0,
        },
        "checklist_items": len(checklist_items),
        "qa_summary": summary,
        "qa_issue_count": len(issues),
    }
