from __future__ import annotations

import argparse
import json
from typing import Any
from uuid import UUID

from sqlmodel import Session, select

from app.db.session import create_db_and_tables, engine
from app.models.entities import (
    AuditLog,
    CaseChecklistItem,
    CaseRecord,
    MarriageRecord,
    PersonRecord,
    QAIssue,
    UploadedDocument,
)
from app.services.i485 import build_i485_form_fill_preview, get_i485_state
from app.services.intake import get_case_steps, get_missing_fields, merge_intake_state


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect the saved facts, uploads, checklist, and QA state for a local case."
    )
    parser.add_argument(
        "--case-id",
        default=None,
        help="Case ID to inspect. If omitted, the most recently created case is used.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print a compact summary instead of the full debug payload.",
    )
    return parser


def _rows(session: Session, model: type[Any], case_id: UUID) -> list[Any]:
    return list(session.exec(select(model).where(model.case_id == case_id)))


def _latest_case(session: Session) -> CaseRecord | None:
    return session.exec(select(CaseRecord).order_by(CaseRecord.created_at.desc())).first()


def build_debug_payload(session: Session, case: CaseRecord) -> dict[str, Any]:
    steps = get_case_steps(session, case.id)
    merged = merge_intake_state(steps)
    checklist = list(
        session.exec(
            select(CaseChecklistItem)
            .where(CaseChecklistItem.case_id == case.id)
            .order_by(CaseChecklistItem.sort_order.asc())
        )
    )
    uploads = list(
        session.exec(
            select(UploadedDocument)
            .where(UploadedDocument.case_id == case.id)
            .order_by(UploadedDocument.created_at.desc())
        )
    )
    issues = list(
        session.exec(select(QAIssue).where(QAIssue.case_id == case.id).order_by(QAIssue.created_at.asc()))
    )
    audit_logs = list(
        session.exec(
            select(AuditLog).where(AuditLog.case_id == case.id).order_by(AuditLog.created_at.desc()).limit(50)
        )
    )
    marriage = session.exec(select(MarriageRecord).where(MarriageRecord.case_id == case.id)).first()
    return {
        "case": case.model_dump(mode="json"),
        "people": [person.model_dump(mode="json") for person in _rows(session, PersonRecord, case.id)],
        "marriage": marriage.model_dump(mode="json") if marriage else None,
        "intake": {
            "steps": [step.model_dump(mode="json") for step in steps],
            "merged": merged,
            "missing_fields": get_missing_fields(merged),
        },
        "checklist": [item.model_dump(mode="json") for item in checklist],
        "uploads": [upload.model_dump(mode="json") for upload in uploads],
        "i485_ingestion": get_i485_state(session, case.id),
        "i485_form_fill_preview": build_i485_form_fill_preview(session, case.id),
        "qa_issues": [issue.model_dump(mode="json") for issue in issues],
        "audit_logs": [entry.model_dump(mode="json") for entry in audit_logs],
    }


def build_summary(payload: dict[str, Any]) -> dict[str, Any]:
    merged = payload["intake"]["merged"]
    return {
        "case_id": payload["case"]["id"],
        "case_name": payload["case"]["case_name"],
        "status": payload["case"]["status"],
        "readiness": {
            "score": payload["case"]["readiness_score"],
            "label": payload["case"]["readiness_label"],
        },
        "people": payload["people"],
        "key_intake_facts": {
            key: merged.get(key)
            for key in (
                "petitioner_first_name",
                "petitioner_last_name",
                "beneficiary_first_name",
                "beneficiary_last_name",
                "beneficiary_date_of_birth",
                "beneficiary_current_address",
                "beneficiary_current_address_since",
                "beneficiary_current_immigration_status",
                "beneficiary_i94_number",
            )
        },
        "missing_intake_fields": payload["intake"]["missing_fields"],
        "counts": {
            "checklist": len(payload["checklist"]),
            "uploads": len(payload["uploads"]),
            "i485_answers": len(payload["i485_ingestion"]["answers"]),
            "i485_flags": len(payload["i485_ingestion"]["evaluation"]["flags"]),
            "i485_fill_fields": payload["i485_form_fill_preview"]["field_count"],
            "qa_issues": len(payload["qa_issues"]),
            "audit_logs": len(payload["audit_logs"]),
        },
    }


def main() -> None:
    args = build_parser().parse_args()
    create_db_and_tables()
    with Session(engine) as session:
        case = session.get(CaseRecord, UUID(args.case_id)) if args.case_id else _latest_case(session)
        if not case:
            raise SystemExit("No case found.")
        payload = build_debug_payload(session, case)

    print(json.dumps(build_summary(payload) if args.summary else payload, indent=2))


if __name__ == "__main__":
    main()
