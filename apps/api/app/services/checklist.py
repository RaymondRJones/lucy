"""Generates and reads a case checklist."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlmodel import Session, select

from app.models.entities import (
    CaseChecklistItem,
    CaseRecord,
    CaseStatus,
    UploadedDocument,
    utcnow,
)
from app.services.intake import derive_case_facts, get_merged_case_intake
from app.services.rules.checklist import ChecklistRuleContext, ChecklistRuleEngine
from app.services.upload_links import satisfied_checklist_codes_for_upload


def _current_upload_counts(session: Session, case_id: UUID) -> dict[str, int]:
    uploads = list(
        session.exec(
            select(UploadedDocument).where(
                UploadedDocument.case_id == case_id,
                UploadedDocument.upload_status == "confirmed",
            )
        )
    )
    counts: dict[str, int] = {}
    for upload in uploads:
        for checklist_code in satisfied_checklist_codes_for_upload(upload):
            counts[checklist_code] = counts.get(checklist_code, 0) + 1
    return counts


def generate_checklist(session: Session, case_id: UUID) -> tuple[list[CaseChecklistItem], dict[str, Any]]:
    """Builds or refreshes a case's checklist from its facts."""
    case = session.get(CaseRecord, case_id)
    if not case:
        raise ValueError("Case not found")

    merged = get_merged_case_intake(session, case_id)
    facts = derive_case_facts(merged)
    upload_counts = _current_upload_counts(session, case_id)
    existing_items = list(
        session.exec(select(CaseChecklistItem).where(CaseChecklistItem.case_id == case_id))
    )
    existing_by_code = {item.code: item for item in existing_items}
    rule_context = ChecklistRuleContext(
        facts=facts,
        upload_counts=upload_counts,
        existing_status_by_code={item.code: item.completion_status for item in existing_items},
    )
    decisions = ChecklistRuleEngine().evaluate(rule_context)
    created_or_updated: list[CaseChecklistItem] = []

    for decision in decisions:
        template = decision.template
        item = existing_by_code.get(template.code)
        if not item:
            item = CaseChecklistItem(
                case_id=case_id,
                code=template.code,
                category=template.category,
                label=template.label,
                owner_role=template.owner_role,
                description=template.description,
                why_needed=template.why_needed,
                what_to_save_now=template.what_to_save_now,
            )
            session.add(item)
            session.flush()

        item.category = template.category
        item.label = template.label
        item.applicability = decision.applicability
        item.owner_role = template.owner_role
        item.description = template.description
        item.why_needed = template.why_needed
        item.what_to_save_now = template.what_to_save_now
        item.conditional_reason = template.conditional_reason
        item.sort_order = decision.sort_order
        item.item_metadata = decision.metadata
        item.completion_status = decision.completion_status
        item.updated_at = utcnow()
        created_or_updated.append(item)

    case.status = CaseStatus.checklist_ready.value
    case.updated_at = utcnow()
    session.add(case)
    session.commit()

    items = list(
        session.exec(
            select(CaseChecklistItem)
            .where(CaseChecklistItem.case_id == case_id)
            .order_by(CaseChecklistItem.sort_order.asc())
        )
    )
    return items, facts


def get_checklist(session: Session, case_id: UUID) -> tuple[list[CaseChecklistItem], dict[str, Any]]:
    """Returns a case's checklist in order."""
    items = list(
        session.exec(
            select(CaseChecklistItem)
            .where(CaseChecklistItem.case_id == case_id)
            .order_by(CaseChecklistItem.sort_order.asc())
        )
    )
    facts = derive_case_facts(get_merged_case_intake(session, case_id))
    return items, facts
