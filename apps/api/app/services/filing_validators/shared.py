from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from pypdf import PdfReader
from sqlmodel import Session, select

from app.content.family_questionnaires import (
    FAMILY_FORM_SOURCES,
    FAMILY_FORMS_VERIFIED_ON,
    I130_OFFICIAL_PDF_URL,
    I130_OFFICIAL_URL,
    I130_QUESTIONNAIRE_VERSION,
    I130A_OFFICIAL_PDF_URL,
    I130A_QUESTIONNAIRE_VERSION,
    all_i130_questions,
    all_i130a_questions,
    required_family_questions,
)
from app.content.i485_questionnaire import (
    I485_OFFICIAL_PDF_URL,
    I485_OFFICIAL_URL,
    I485_QUESTIONNAIRE_VERSION,
    I485_SOURCES,
    I485_VERIFIED_ON,
    all_i485_questions,
)
from app.content.i864_poverty_guidelines import (
    I864P_CONTIGUOUS_STATES_AND_TERRITORIES,
    I864P_GUIDELINES,
    I864P_REGION_BY_STATE,
    I864P_SOURCES,
    I864P_VERSION,
    i864p_region_for_state,
    i864p_required_income,
)
from app.content.supplemental_forms import get_supplemental_form_config
from app.content.uscis_requirements import USCIS_REQUIREMENTS, VERIFIED_ON
from app.models.entities import UploadedDocument
from app.services.family_pdf import (
    I130_CLASS_NOT_OFFERED_WARNING,
    build_i130_pdf_field_payload,
    build_i130a_pdf_field_payload,
    i130_class_of_admission_not_offered,
)
from app.services.form_ingestion import build_form_fill_preview, get_form_case_intake, get_form_state
from app.services.form_pdf import build_form_pdf_field_payload
from app.services.i485 import build_i485_form_fill_preview, evaluate_i485_answers, get_i485_state
from app.services.i485_pdf import build_i485_pdf_field_payload
from app.services.intake import derive_case_facts, get_merged_case_intake


BLANK_DOCUMENTS_DIR = Path("blank-immigration-documents")
DEFAULT_TEMPLATE_PATHS = {
    "form_g1145": Path("blank-immigration-documents/g-1145.pdf"),
    "form_i130": Path("blank-immigration-documents/i-130.pdf"),
    "form_i130a": Path("blank-immigration-documents/i-130a.pdf"),
    "form_i485": Path("blank-immigration-documents/i-485.pdf"),
    "form_i131": Path("blank-immigration-documents/i-131.pdf"),
    "form_i765": Path("blank-immigration-documents/i-765.pdf"),
    "form_i864": Path("blank-immigration-documents/i-864.pdf"),
}
TEMPLATE_FILENAME_CANDIDATES = {
    "form_i130": ("i-130.pdf", "i130.pdf", "form-i-130.pdf", "form_i-130.pdf"),
    "form_i130a": ("i-130a.pdf", "i130a.pdf", "form-i-130a.pdf", "form_i-130a.pdf"),
}
DEFAULT_VALIDATION_SCOPE = ("form_i485", "form_i864")
SUPPORTED_FORM_CODES = {"form_i130", "form_i130a", "form_i131", "form_i485", "form_i765", "form_i864", "form_g1145"}
ROADMAP_FORM_CODES = ("form_i130", "form_i130a", "form_i765", "form_i131", "form_g1145")

REQUIREMENTS_BY_CODE = {str(requirement["code"]): requirement for requirement in USCIS_REQUIREMENTS}
I485_QUESTION_BY_ID = {question["id"]: question for question in all_i485_questions()}
I130_QUESTION_BY_ID = {question["id"]: question for question in all_i130_questions()}
I130A_QUESTION_BY_ID = {question["id"]: question for question in all_i130a_questions()}

def _utcnow() -> datetime:
    return datetime.now(UTC)


def _value_is_answered(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(_value_is_answered(entry) for entry in value)
    if isinstance(value, dict):
        return any(_value_is_answered(entry_value) for entry_value in value.values())
    return True


def _valid_positive_integer(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value > 0
    if isinstance(value, str):
        return value.strip().isdigit() and int(value.strip()) > 0
    return False


def _parse_iso_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _subtract_years(anchor: date, years: int) -> date:
    try:
        return anchor.replace(year=anchor.year - years)
    except ValueError:
        return anchor.replace(year=anchor.year - years, day=28)


def _normalize_scalar(value: Any) -> str | None:
    if not _value_is_answered(value):
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return " ".join(str(value).strip().lower().split()) or None


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "y", "1"}
    return bool(value)


def _as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "").replace("$", ""))
    except ValueError:
        return None


def _as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _looks_like_email(value: Any) -> bool:
    if not _value_is_answered(value):
        return False
    raw = str(value).strip()
    return "@" in raw and "." in raw.rsplit("@", 1)[-1]


def _phone_digits(value: Any) -> str:
    if not _value_is_answered(value):
        return ""
    return "".join(char for char in str(value) if char.isdigit())


def _confirmed_uploads(session: Session, case_id: UUID) -> list[UploadedDocument]:
    return list(
        session.exec(
            select(UploadedDocument).where(
                UploadedDocument.case_id == case_id,
                UploadedDocument.upload_status == "confirmed",
            )
        )
    )


def _default_template_path(form_code: str) -> Path | None:
    default_path = DEFAULT_TEMPLATE_PATHS.get(form_code)
    if default_path and default_path.exists():
        return default_path
    candidates = TEMPLATE_FILENAME_CANDIDATES.get(form_code, ())
    if not candidates or not BLANK_DOCUMENTS_DIR.exists():
        return default_path
    available = {path.name.lower(): path for path in BLANK_DOCUMENTS_DIR.glob("*.pdf")}
    for candidate in candidates:
        path = available.get(candidate.lower())
        if path:
            return path
    return None


def _sponsor_state(merged: dict[str, Any]) -> str | None:
    for key in (
        "sponsor_state",
        "petitioner_current_state",
        "petitioner_state",
        "petitioner_mailing_state",
    ):
        value = merged.get(key)
        if _value_is_answered(value):
            return str(value).strip().upper()
    address = str(
        merged.get("petitioner_current_address")
        or merged.get("petitioner_mailing_address")
        or ""
    ).upper()
    known_states = set(I864P_REGION_BY_STATE) | I864P_CONTIGUOUS_STATES_AND_TERRITORIES
    tokens = [
        token.strip(" .")
        for chunk in address.replace("\n", ",").split(",")
        for token in chunk.split()
    ]
    for token in tokens:
        if token in known_states:
            return token
    return None


def _template_field_names(template_path: Path) -> tuple[set[str], str | None]:
    if not template_path.exists():
        return set(), f"Template PDF not found: {template_path}"
    try:
        reader = PdfReader(template_path)
        fields = reader.get_fields() or {}
    except Exception as exc:  # noqa: BLE001  # pragma: no cover - defensive around malformed local PDFs
        return set(), f"Template PDF could not be read: {exc}"
    names: set[str] = set()
    for name, field in fields.items():
        names.add(str(name))
        field_name = field.get("/T")
        if field_name:
            names.add(str(field_name))
    return names, None


def _template_metadata(template_path: Path) -> dict[str, Any]:
    if not template_path.exists():
        return {
            "path": str(template_path),
            "exists": False,
            "page_count": 0,
            "field_count": 0,
            "sha256": None,
            "error": f"Template PDF not found: {template_path}",
        }
    try:
        content = template_path.read_bytes()
        reader = PdfReader(template_path)
        fields = reader.get_fields() or {}
    except Exception as exc:  # noqa: BLE001  # pragma: no cover - defensive around malformed local PDFs
        return {
            "path": str(template_path),
            "exists": True,
            "page_count": 0,
            "field_count": 0,
            "sha256": None,
            "error": f"Template PDF could not be read: {exc}",
        }
    return {
        "path": str(template_path),
        "exists": True,
        "page_count": len(reader.pages),
        "field_count": len(fields),
        "sha256": hashlib.sha256(content).hexdigest(),
        "error": None,
    }


def _intake_with_form_gaps_filled(session: Session, case_id: UUID, form_key: str) -> dict[str, Any]:
    # Import and generation can find facts only in saved I-485 answers, so those must not read as missing.
    # Facts already in intake stay as they are, so the cross-form checks can still compare them with the I-485.
    merged = get_merged_case_intake(session, case_id)
    form_intake = get_form_case_intake(session, case_id, form_key)
    return {**merged, **{key: value for key, value in form_intake.items() if not _value_is_answered(merged.get(key))}}


def _issue(
    *,
    form_code: str,
    severity: str,
    code: str,
    title: str,
    description: str,
    source: str,
    field_key: str | None = None,
    question_id: str | None = None,
    pdf_ref: str | None = None,
    pdf_fields: list[str] | None = None,
    expected: Any = None,
    actual: Any = None,
) -> dict[str, Any]:
    return {
        "form_code": form_code,
        "severity": severity,
        "code": code,
        "title": title,
        "description": description,
        "source": source,
        "field_key": field_key,
        "question_id": question_id,
        "pdf_ref": pdf_ref,
        "pdf_fields": pdf_fields or [],
        "expected": expected,
        "actual": actual,
    }


def _append_cross_form_mismatch_issues(
    *,
    issues: list[dict[str, Any]],
    form_code: str,
    other_form_label: str,
    current_values: dict[str, Any],
    other_values: dict[str, Any],
    field_labels: dict[str, str],
) -> None:
    for field_key, label in field_labels.items():
        current_value = current_values.get(field_key)
        other_value = other_values.get(field_key)
        if not _value_is_answered(current_value) or not _value_is_answered(other_value):
            continue
        if _normalize_scalar(current_value) == _normalize_scalar(other_value):
            continue
        issues.append(
            _issue(
                form_code=form_code,
                severity="important",
                code=f"{form_code}_{field_key}_cross_form_mismatch",
                title=f"{_form_label(form_code)} fact differs from {other_form_label}",
                description=(
                    f"{label} is saved differently for {_form_label(form_code)} review than in "
                    f"{other_form_label}. Confirm which value is correct before treating the packet as ready."
                ),
                source="record_consistency",
                field_key=field_key,
                expected=other_value,
                actual=current_value,
            )
        )


def _append_uploaded_document_mismatch_issues(
    *,
    issues: list[dict[str, Any]],
    form_code: str,
    uploads: list[UploadedDocument],
    checklist_codes: set[str],
    current_values: dict[str, Any],
    field_labels: dict[str, str],
) -> None:
    for upload in uploads:
        if upload.checklist_item_code not in checklist_codes:
            continue
        extracted_fields = upload.extracted_fields if isinstance(upload.extracted_fields, dict) else {}
        if not extracted_fields:
            continue
        for field_key, label in field_labels.items():
            current_value = current_values.get(field_key)
            extracted_value = extracted_fields.get(field_key)
            if not _value_is_answered(current_value) or not _value_is_answered(extracted_value):
                continue
            if _normalize_scalar(current_value) == _normalize_scalar(extracted_value):
                continue
            issues.append(
                _issue(
                    form_code=form_code,
                    severity="important",
                    code=f"{form_code}_{field_key}_uploaded_document_mismatch",
                    title="Uploaded form value differs from the case source of truth",
                    description=(
                        f"{label} in uploaded {upload.checklist_item_code} extraction does not match the "
                        "case source-of-truth value. Review the uploaded document and saved record before filing."
                    ),
                    source="record_consistency",
                    field_key=field_key,
                    expected=current_value,
                    actual=extracted_value,
                )
            )


def _append_missing_required_question_issues(
    *,
    issues: list[dict[str, Any]],
    form_code: str,
    values: dict[str, Any],
    questions: list[dict[str, Any]],
    title: str,
    description_suffix: str,
) -> None:
    for question in questions:
        question_id = question["id"]
        if _value_is_answered(values.get(question_id)):
            continue
        issues.append(
            _issue(
                form_code=form_code,
                severity="blocking",
                code=f"{form_code}_{question_id}_missing_required",
                title=title,
                description=f"{question['label']} is missing {description_suffix}",
                source="case_intake",
                field_key=question_id,
                question_id=question_id,
                pdf_ref=question["pdf_ref"],
            )
        )


def _source_payload(form_code: str) -> dict[str, Any]:
    requirement = REQUIREMENTS_BY_CODE.get(form_code, {})
    if form_code == "form_i485":
        return {
            "verified_on": I485_VERIFIED_ON,
            "official_url": I485_OFFICIAL_URL,
            "official_pdf_url": I485_OFFICIAL_PDF_URL,
            "questionnaire_version": I485_QUESTIONNAIRE_VERSION,
            "sources": I485_SOURCES,
        }
    if form_code == "form_i864":
        return {
            "verified_on": requirement.get("verified_on", VERIFIED_ON),
            "official_url": requirement.get("official_url"),
            "official_pdf_url": None,
            "questionnaire_version": None,
            "sources": [
                {
                    "label": requirement.get("label", form_code),
                    "url": requirement.get("official_url", ""),
                    "verified_on": requirement.get("verified_on", VERIFIED_ON),
                    "notes": requirement.get("summary", ""),
                },
                *I864P_SOURCES,
            ],
        }
    if form_code == "form_i130":
        return {
            "verified_on": FAMILY_FORMS_VERIFIED_ON,
            "official_url": I130_OFFICIAL_URL,
            "official_pdf_url": I130_OFFICIAL_PDF_URL,
            "questionnaire_version": I130_QUESTIONNAIRE_VERSION,
            "sources": FAMILY_FORM_SOURCES,
        }
    if form_code == "form_i130a":
        return {
            "verified_on": FAMILY_FORMS_VERIFIED_ON,
            "official_url": I130_OFFICIAL_URL,
            "official_pdf_url": I130A_OFFICIAL_PDF_URL,
            "questionnaire_version": I130A_QUESTIONNAIRE_VERSION,
            "sources": FAMILY_FORM_SOURCES,
        }
    if form_code == "form_i131":
        config = get_supplemental_form_config("i131")
        return {
            "verified_on": config["verified_on"],
            "official_url": config["official_url"],
            "official_pdf_url": config["official_pdf_url"],
            "questionnaire_version": config["version"],
            "sources": config["sources"],
        }
    return {
        "verified_on": requirement.get("verified_on", VERIFIED_ON),
        "official_url": requirement.get("official_url"),
        "official_pdf_url": None,
        "questionnaire_version": None,
        "sources": [
            {
                "label": requirement.get("label", form_code),
                "url": requirement.get("official_url", ""),
                "verified_on": requirement.get("verified_on", VERIFIED_ON),
                "notes": requirement.get("summary", ""),
            }
        ],
    }


def _form_label(form_code: str) -> str:
    return str(REQUIREMENTS_BY_CODE.get(form_code, {}).get("label") or form_code)


def _status_for_counts(counts: dict[str, int]) -> str:
    if counts["blocking"]:
        return "blocked"
    if counts["important"]:
        return "needs_review"
    if counts["recommended"]:
        return "review_suggested"
    return "passed"


def _form_result(
    *,
    form_code: str,
    issues: list[dict[str, Any]],
    field_count: int,
    required_field_count: int,
    template_field_count: int,
    template_path: Path | None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    issue_counts = {
        "blocking": sum(1 for issue in issues if issue["severity"] == "blocking"),
        "important": sum(1 for issue in issues if issue["severity"] == "important"),
        "recommended": sum(1 for issue in issues if issue["severity"] == "recommended"),
    }
    return {
        "form_code": form_code,
        "label": _form_label(form_code),
        "status": _status_for_counts(issue_counts),
        "issue_counts": issue_counts,
        "field_count": field_count,
        "required_field_count": required_field_count,
        "missing_required_count": sum(1 for issue in issues if issue["code"].endswith("_missing_required")),
        "template_field_count": template_field_count,
        "template_path": str(template_path) if template_path else None,
        "source": _source_payload(form_code),
        "metadata": metadata or {},
        "issues": issues,
    }


def _unsupported_form_result(form_code: str, template_path: Path | None) -> dict[str, Any]:
    template_field_count = 0
    template_error = None
    if template_path:
        template_info = _template_metadata(template_path)
        template_field_count = int(template_info["field_count"])
        template_error = template_info["error"]

    issues = [
        _issue(
            form_code=form_code,
            severity="important",
            code=f"{form_code}_validator_not_implemented",
            title=f"{_form_label(form_code)} validator is not implemented yet",
            description=(
                "The extension API can see this form code, but it does not yet have a source-backed required "
                "field map or cross-record rules for it."
            ),
            source="validator_registry",
            actual=template_error,
        )
    ]
    return _form_result(
        form_code=form_code,
        issues=issues,
        field_count=0,
        required_field_count=0,
        template_field_count=template_field_count,
        template_path=template_path,
        metadata={"validator_level": "roadmap_only"},
    )


__all__ = [name for name in globals() if not name.startswith("__")]
