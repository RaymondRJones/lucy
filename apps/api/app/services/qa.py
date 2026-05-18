from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlmodel import Session, select

from app.content.reference_data import EXPLANATION_CONTENT
from app.models.entities import (
    CaseChecklistItem,
    CaseRecord,
    CaseStatus,
    QAIssue,
    UploadedDocument,
)
from app.services.i485 import evaluate_i485_answers, get_i485_state
from app.services.intake import derive_case_facts, get_merged_case_intake, normalize_country
from app.services.rules.qa import QARuleContext, QARuleDependencies, QARuleEngine
from app.services.upload_links import satisfied_checklist_codes_for_upload


VERIFICATION_FIELD_RULES = (
    {
        "field": "petitioner_name",
        "label": "petitioner name",
        "title": "Petitioner name does not match across uploaded forms",
        "severity": "important",
        "source_priority": ("form_i130", "form_i485"),
        "compare_codes": {"form_i130", "form_i485", "form_i864"},
    },
    {
        "field": "beneficiary_name",
        "label": "beneficiary name",
        "title": "Beneficiary name does not match across uploaded documents",
        "severity": "important",
        "source_priority": ("beneficiary_birth_certificate", "form_i485", "form_i130"),
        "compare_codes": {"beneficiary_birth_certificate", "form_i130", "form_i485", "form_i130a"},
    },
    {
        "field": "marriage_date",
        "label": "marriage date",
        "title": "Marriage date does not match across uploaded forms",
        "severity": "important",
        "source_priority": ("form_i130", "form_i485"),
        "compare_codes": {"form_i130", "form_i485"},
    },
    {
        "field": "beneficiary_date_of_birth",
        "label": "beneficiary date of birth",
        "title": "Beneficiary birth date does not match across uploaded documents",
        "severity": "important",
        "source_priority": ("beneficiary_birth_certificate", "form_i485"),
        "compare_codes": {"beneficiary_birth_certificate", "form_i485"},
    },
    {
        "field": "beneficiary_country_of_birth",
        "label": "beneficiary country of birth",
        "title": "Beneficiary country of birth does not match across uploaded documents",
        "severity": "important",
        "source_priority": ("beneficiary_birth_certificate", "form_i130", "form_i485"),
        "compare_codes": {"beneficiary_birth_certificate", "form_i130", "form_i485"},
    },
    {
        "field": "beneficiary_current_immigration_status",
        "label": "beneficiary immigration status",
        "title": "Current immigration status does not match across uploaded forms",
        "severity": "important",
        "source_priority": ("form_i485", "form_i130"),
        "compare_codes": {"form_i130", "form_i485"},
    },
    {
        "field": "beneficiary_i94_number",
        "label": "beneficiary I-94 number",
        "title": "I-94 number does not match across uploaded forms",
        "severity": "important",
        "source_priority": ("form_i485", "form_i130"),
        "compare_codes": {"form_i130", "form_i485"},
    },
    {
        "field": "beneficiary_current_address",
        "label": "beneficiary current address",
        "title": "Current address does not match across uploaded forms",
        "severity": "important",
        "source_priority": ("form_i485", "form_i130"),
        "compare_codes": {"form_i130", "form_i485"},
    },
)
ADDRESS_TOKEN_ALIASES = {
    "apartment": "apt",
    "apt": "apt",
    "avenue": "ave",
    "ave": "ave",
    "boulevard": "blvd",
    "blvd": "blvd",
    "circle": "cir",
    "cir": "cir",
    "court": "ct",
    "ct": "ct",
    "drive": "dr",
    "dr": "dr",
    "floor": "fl",
    "fl": "fl",
    "lane": "ln",
    "ln": "ln",
    "place": "pl",
    "pl": "pl",
    "road": "rd",
    "rd": "rd",
    "street": "st",
    "st": "st",
    "suite": "ste",
    "ste": "ste",
}
INTAKE_VERIFICATION_RULES = (
    {
        "field": "petitioner_name",
        "label": "petitioner name",
        "source_priority": ("form_i130", "form_i485", "form_i864"),
    },
    {
        "field": "beneficiary_name",
        "label": "beneficiary name",
        "source_priority": ("beneficiary_birth_certificate", "form_i485", "form_i130", "form_i130a"),
    },
    {
        "field": "beneficiary_date_of_birth",
        "label": "beneficiary date of birth",
        "source_priority": ("beneficiary_birth_certificate", "form_i485"),
    },
    {
        "field": "beneficiary_country_of_birth",
        "label": "beneficiary country of birth",
        "source_priority": ("beneficiary_birth_certificate", "form_i130", "form_i485"),
    },
    {
        "field": "beneficiary_current_immigration_status",
        "label": "beneficiary immigration status",
        "source_priority": ("form_i485", "form_i130"),
    },
    {
        "field": "beneficiary_i94_number",
        "label": "beneficiary I-94 number",
        "source_priority": ("form_i485", "form_i130"),
    },
    {
        "field": "beneficiary_current_address",
        "label": "beneficiary current address",
        "source_priority": ("form_i485", "form_i130"),
    },
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _names_match(expected: str | None, actual: str | None) -> bool:
    if not expected or not actual:
        return True
    return " ".join(expected.lower().split()) == " ".join(actual.lower().split())


def _build_issue(
    case_id: UUID,
    severity: str,
    code: str,
    title: str,
    description: str,
    checklist_item_code: str | None = None,
) -> QAIssue:
    return QAIssue(
        case_id=case_id,
        severity=severity,
        code=code,
        title=title,
        description=description,
        checklist_item_code=checklist_item_code,
    )


def _build_upload_map(uploads: list[UploadedDocument]) -> dict[str, list[UploadedDocument]]:
    upload_map: dict[str, list[UploadedDocument]] = {}
    for upload in uploads:
        for checklist_code in satisfied_checklist_codes_for_upload(upload):
            upload_map.setdefault(checklist_code, []).append(upload)
    return upload_map


def _item_is_satisfied(
    item: CaseChecklistItem,
    upload_map: dict[str, list[UploadedDocument]],
    facts: dict[str, Any],
) -> bool:
    if item.code == "review_current_fees":
        return bool(facts.get("reviewed_current_fees"))
    if item.code == "review_form_editions":
        return bool(facts.get("reviewed_current_form_editions"))
    return bool(upload_map.get(item.code))


def _latest_representative_uploads(uploads: list[UploadedDocument]) -> list[UploadedDocument]:
    latest_by_key: dict[str, UploadedDocument] = {}
    for upload in uploads:
        key = upload.checklist_item_code or str(upload.id)
        current = latest_by_key.get(key)
        if current is None or (upload.version, upload.updated_at) > (current.version, current.updated_at):
            latest_by_key[key] = upload
    return list(latest_by_key.values())


def _normalize_text(value: Any) -> str | None:
    if value in (None, "", [], {}):
        return None
    normalized = re.sub(r"[^a-z0-9]+", " ", str(value).lower())
    normalized = " ".join(normalized.split())
    return normalized or None


def _normalize_identifier(value: Any) -> str | None:
    if value in (None, "", [], {}):
        return None
    normalized = re.sub(r"[^A-Za-z0-9]+", "", str(value).upper())
    return normalized or None


def _normalize_address(value: Any) -> str | None:
    base = _normalize_text(value)
    if not base:
        return None
    tokens = [ADDRESS_TOKEN_ALIASES.get(token, token) for token in base.split()]
    return " ".join(tokens) or None


def _normalize_verification_value(field: str, value: Any) -> str | None:
    if field in {"petitioner_name", "beneficiary_name", "beneficiary_current_immigration_status"}:
        return _normalize_text(value)
    if field in {"beneficiary_i94_number"}:
        return _normalize_identifier(value)
    if field in {"beneficiary_current_address"}:
        return _normalize_address(value)
    if field in {"marriage_date", "beneficiary_date_of_birth"}:
        return str(value).strip() if value not in (None, "") else None
    if field == "beneficiary_country_of_birth":
        return normalize_country(value)
    return _normalize_text(value)


def _field_value(upload: UploadedDocument, field: str) -> Any:
    return (upload.extracted_fields or {}).get(field)


def _select_source_upload(
    uploads: list[UploadedDocument],
    field: str,
    source_priority: tuple[str, ...],
) -> UploadedDocument | None:
    for checklist_code in source_priority:
        for upload in uploads:
            if upload.checklist_item_code != checklist_code:
                continue
            if _normalize_verification_value(field, _field_value(upload, field)):
                return upload
    for upload in uploads:
        if _normalize_verification_value(field, _field_value(upload, field)):
            return upload
    return None


def _source_backed_consistency_issues(
    case_id: UUID,
    uploads: list[UploadedDocument],
) -> tuple[list[QAIssue], dict[str, UploadedDocument]]:
    issues: list[QAIssue] = []
    sources: dict[str, UploadedDocument] = {}
    for rule in VERIFICATION_FIELD_RULES:
        field = rule["field"]
        source_upload = _select_source_upload(uploads, field, rule["source_priority"])
        if source_upload is None:
            continue
        sources[field] = source_upload
        source_value = _field_value(source_upload, field)
        source_normalized = _normalize_verification_value(field, source_value)
        if not source_normalized:
            continue
        compare_codes = rule["compare_codes"]
        for upload in uploads:
            if upload.id == source_upload.id:
                continue
            if upload.checklist_item_code not in compare_codes:
                continue
            candidate_value = _field_value(upload, field)
            candidate_normalized = _normalize_verification_value(field, candidate_value)
            if not candidate_normalized or candidate_normalized == source_normalized:
                continue
            issues.append(
                _build_issue(
                    case_id,
                    rule["severity"],
                    f"document_mismatch_{field}_{source_upload.id}_{upload.id}",
                    rule["title"],
                    (
                        f"{source_upload.original_filename} is currently being used as the reference for the "
                        f"{rule['label']} and shows '{source_value}', but {upload.original_filename} shows "
                        f"'{candidate_value}'. Review both documents before filing."
                    ),
                    upload.checklist_item_code,
                )
            )
    return issues, sources


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


def _address_history_entries(upload: UploadedDocument, key: str) -> list[dict[str, Any]]:
    raw = (upload.extracted_fields or {}).get(key)
    if not isinstance(raw, list):
        return []
    return [entry for entry in raw if isinstance(entry, dict)]


def _address_history_issues(
    case_id: UUID,
    uploads: list[UploadedDocument],
) -> list[QAIssue]:
    issues: list[QAIssue] = []
    cutoff = _subtract_years(date.today(), 5)
    supporting_history_upload = next(
        (
            upload
            for upload in uploads
            if upload.checklist_item_code in {"form_i130", "form_i130a"}
            and _address_history_entries(upload, "beneficiary_address_history")
        ),
        None,
    )
    for upload in uploads:
        fields = upload.extracted_fields or {}
        current_since = _parse_iso_date(fields.get("beneficiary_address_since"))
        if current_since is None or current_since <= cutoff:
            continue
        prior_history = _address_history_entries(upload, "beneficiary_prior_address_history")
        if prior_history:
            continue
        if supporting_history_upload:
            description = (
                f"{upload.original_filename} shows the beneficiary moved to the current address on "
                f"{current_since.isoformat()}, which is less than five years ago, but no prior address was "
                f"detected in that form. {supporting_history_upload.original_filename} includes earlier address "
                "history, so make sure the same history is carried into the final filing set."
            )
        else:
            description = (
                f"{upload.original_filename} shows the beneficiary moved to the current address on "
                f"{current_since.isoformat()}, which is less than five years ago, but no prior address was "
                "detected in the extracted form text. Review the five-year address history section before filing."
            )
        issues.append(
            _build_issue(
                case_id,
                "important",
                f"address_history_missing_{upload.id}",
                "Prior address history may be missing from a core form",
                description,
                upload.checklist_item_code,
            )
        )
    return issues


def _join_name(*parts: Any) -> str:
    return " ".join(str(part).strip() for part in parts if str(part or "").strip())


def _intake_value_for_field(merged: dict[str, Any], field: str) -> Any:
    if field == "petitioner_name":
        return _join_name(
            merged.get("petitioner_first_name"),
            merged.get("petitioner_middle_name"),
            merged.get("petitioner_last_name"),
        )
    if field == "beneficiary_name":
        return _join_name(
            merged.get("beneficiary_first_name"),
            merged.get("beneficiary_middle_name"),
            merged.get("beneficiary_last_name"),
        )
    return merged.get(field)


def _intake_to_document_issues(
    case_id: UUID,
    merged: dict[str, Any],
    uploads: list[UploadedDocument],
) -> list[QAIssue]:
    issues: list[QAIssue] = []
    for rule in INTAKE_VERIFICATION_RULES:
        field = rule["field"]
        intake_value = _intake_value_for_field(merged, field)
        intake_normalized = _normalize_verification_value(field, intake_value)
        if not intake_normalized:
            continue
        source_upload = _select_source_upload(uploads, field, rule["source_priority"])
        if source_upload is None:
            continue
        source_value = _field_value(source_upload, field)
        source_normalized = _normalize_verification_value(field, source_value)
        if not source_normalized or source_normalized == intake_normalized:
            continue
        issues.append(
            _build_issue(
                case_id,
                "important",
                f"intake_document_mismatch_{field}_{source_upload.id}",
                f"Intake {rule['label']} does not match an uploaded document",
                (
                    f"The saved intake shows '{intake_value}' for the {rule['label']}, but "
                    f"{source_upload.original_filename} shows '{source_value}'. Review the intake answer and "
                    "the uploaded document before using these facts for form fill."
                ),
                source_upload.checklist_item_code,
            )
        )
    return issues


def _has_prior_address_in_intake(merged: dict[str, Any]) -> bool:
    prior_address_keys = (
        "beneficiary_prior_address_1",
        "beneficiary_prior_address_2",
        "beneficiary_prior_address_history",
    )
    for key in prior_address_keys:
        value = merged.get(key)
        if isinstance(value, list) and value:
            return True
        if isinstance(value, str) and value.strip():
            return True
    return False


def _upload_has_prior_address_history(uploads: list[UploadedDocument]) -> bool:
    return any(_address_history_entries(upload, "beneficiary_prior_address_history") for upload in uploads)


def _intake_address_history_issues(
    case_id: UUID,
    merged: dict[str, Any],
    uploads: list[UploadedDocument],
) -> list[QAIssue]:
    current_since = _parse_iso_date(merged.get("beneficiary_current_address_since"))
    if current_since is None:
        return []
    cutoff = _subtract_years(date.today(), 5)
    if current_since <= cutoff:
        return []
    if _has_prior_address_in_intake(merged) or _upload_has_prior_address_history(uploads):
        return []
    return [
        _build_issue(
            case_id,
            "important",
            "intake_address_history_missing",
            "Five-year address history may be incomplete",
            (
                f"The saved intake says the beneficiary moved to the current address on "
                f"{current_since.isoformat()}, which is less than five years ago, but no prior address history "
                "is saved in intake or detected in uploaded forms. Review the address-history sections before "
                "using this case for form fill."
            ),
        )
    ]


def _completion_counts(
    items: list[CaseChecklistItem],
    upload_map: dict[str, list[UploadedDocument]],
    facts: dict[str, Any],
) -> tuple[int, int]:
    required_items = [item for item in items if item.applicability == "required"]
    completed = [item for item in required_items if _item_is_satisfied(item, upload_map, facts)]
    return len(completed), len(required_items)


def _readiness_summary(
    items: list[CaseChecklistItem],
    issues: list[QAIssue],
    upload_map: dict[str, list[UploadedDocument]],
    facts: dict[str, Any],
) -> dict[str, Any]:
    if not items:
        return {
            "score": 0,
            "label": "Not ready",
            "required_completion_pct": 0,
            "issue_counts": {"blocking": 0, "important": 0, "recommended": 0},
            "explanation": "Start by completing intake and generating a checklist.",
        }

    completed_required, total_required = _completion_counts(items, upload_map, facts)
    required_pct = int(round((completed_required / total_required) * 100)) if total_required else 100
    issue_counts = {
        "blocking": sum(1 for issue in issues if issue.severity == "blocking"),
        "important": sum(1 for issue in issues if issue.severity == "important"),
        "recommended": sum(1 for issue in issues if issue.severity == "recommended"),
    }

    score = max(
        0,
        min(
            100,
            required_pct
            - (issue_counts["blocking"] * 20)
            - (issue_counts["important"] * 8)
            - (issue_counts["recommended"] * 3),
        ),
    )

    if issue_counts["blocking"] > 0 or required_pct < 70:
        label = "Not ready"
    elif issue_counts["important"] > 1 or required_pct < 90:
        label = "Almost ready"
    elif issue_counts["recommended"] > 0:
        label = "Ready for final review"
    else:
        label = "Ready to print and assemble"

    return {
        "score": score,
        "label": label,
        "required_completion_pct": required_pct,
        "issue_counts": issue_counts,
        "explanation": EXPLANATION_CONTENT["readiness_labels"][label],
    }


def _i485_ingestion_issues(session: Session, case_id: UUID) -> list[QAIssue]:
    state = get_i485_state(session, case_id)
    if not state["answers"]:
        return []

    evaluation = evaluate_i485_answers(state["answers"])
    issues: list[QAIssue] = []
    for flag in evaluation["flags"]:
        severity = "blocking" if flag["severity"] == "blocking" else "important"
        code = f"i485_{flag['code']}_{flag['question_id']}"
        if flag["category"] == "outside_niche":
            title = "I-485 answer is outside the standard marriage case profile"
        else:
            title = "I-485 answer may need professional legal review"
        description = (
            f"{flag['description']} Source: {flag['pdf_ref']}. "
            "Review the I-485 ingestion page before relying on this case as packet-ready."
        )
        issues.append(
            _build_issue(
                case_id,
                severity,
                code,
                title,
                description,
                "form_i485",
            )
        )
    return issues


def run_qa(session: Session, case_id: UUID) -> tuple[list[QAIssue], dict[str, Any]]:
    case = session.get(CaseRecord, case_id)
    if not case:
        raise ValueError("Case not found")

    items = list(
        session.exec(
            select(CaseChecklistItem)
            .where(CaseChecklistItem.case_id == case_id)
            .order_by(CaseChecklistItem.sort_order.asc())
        )
    )
    uploads = list(
        session.exec(
            select(UploadedDocument).where(
                UploadedDocument.case_id == case_id,
                UploadedDocument.upload_status == "confirmed",
            )
        )
    )
    upload_map = _build_upload_map(uploads)
    representative_uploads = _latest_representative_uploads(uploads)

    merged = get_merged_case_intake(session, case_id)
    facts = derive_case_facts(merged)
    expected_petitioner_name = " ".join(
        part for part in [merged.get("petitioner_first_name"), merged.get("petitioner_last_name")] if part
    )
    expected_beneficiary_name = " ".join(
        part for part in [merged.get("beneficiary_first_name"), merged.get("beneficiary_last_name")] if part
    )

    existing = list(session.exec(select(QAIssue).where(QAIssue.case_id == case_id)))
    for issue in existing:
        session.delete(issue)
    session.flush()

    qa_context = QARuleContext(
        session=session,
        case_id=case_id,
        items=items,
        uploads=uploads,
        representative_uploads=representative_uploads,
        upload_map=upload_map,
        facts=facts,
        merged=merged,
        expected_petitioner_name=expected_petitioner_name,
        expected_beneficiary_name=expected_beneficiary_name,
        dependencies=QARuleDependencies(
            build_issue=_build_issue,
            item_is_satisfied=_item_is_satisfied,
            names_match=_names_match,
            source_backed_consistency_issues=_source_backed_consistency_issues,
            address_history_issues=_address_history_issues,
            intake_to_document_issues=_intake_to_document_issues,
            intake_address_history_issues=_intake_address_history_issues,
            i485_ingestion_issues=_i485_ingestion_issues,
        ),
    )
    issues = QARuleEngine().evaluate(qa_context)

    for issue in issues:
        session.add(issue)

    summary = _readiness_summary(items, issues, upload_map, facts)
    case.readiness_score = summary["score"]
    case.readiness_label = summary["label"]
    case.status = CaseStatus.qa_reviewed.value
    case.updated_at = _utcnow()
    session.add(case)
    session.commit()

    persisted = list(
        session.exec(select(QAIssue).where(QAIssue.case_id == case_id).order_by(QAIssue.created_at.asc()))
    )
    return persisted, summary


def get_qa_results(session: Session, case_id: UUID) -> tuple[list[QAIssue], dict[str, Any]]:
    issues = list(
        session.exec(select(QAIssue).where(QAIssue.case_id == case_id).order_by(QAIssue.created_at.asc()))
    )
    items = list(
        session.exec(select(CaseChecklistItem).where(CaseChecklistItem.case_id == case_id))
    )
    uploads = list(
        session.exec(
            select(UploadedDocument).where(
                UploadedDocument.case_id == case_id,
                UploadedDocument.upload_status == "confirmed",
            )
        )
    )
    upload_map = _build_upload_map(uploads)
    facts = derive_case_facts(get_merged_case_intake(session, case_id))
    return issues, _readiness_summary(items, issues, upload_map, facts)
