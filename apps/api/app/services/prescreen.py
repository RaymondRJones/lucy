from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlmodel import Session

from app.content.prescreen import PRESCREEN_QUESTIONS
from app.services.case_facts import enrich_case_fact_aliases
from app.services.intake import get_merged_case_intake, upsert_intake_step
from app.services.rules.prescreen import (
    I130_ALREADY_FILED_STATUSES,
    PrescreenRuleEngine,
    value_is_answered as _value_is_answered,
)


PRESCREEN_STEP_KEY = "prescreen"

LEGAL_ENTRY_TYPES = {"visa_admitted", "esta_vwp", "paroled", "visa_esta_parole"}


def _set_projection_value(projection: dict[str, Any], db_path: Any, value: Any) -> None:
    if not isinstance(db_path, str) or not db_path.startswith("intake."):
        return
    if _value_is_answered(value):
        projection[db_path.removeprefix("intake.")] = value


def _project_prescreen_answers(answers: dict[str, Any]) -> dict[str, Any]:
    projection: dict[str, Any] = {}
    for question in PRESCREEN_QUESTIONS:
        value = answers.get(question["id"])
        if question.get("answer_type") == "field_group" and isinstance(value, dict):
            for field_key, db_path in (question.get("field_mappings") or {}).items():
                _set_projection_value(projection, db_path, value.get(field_key))
            continue
        _set_projection_value(projection, question.get("db_path"), value)

    if projection.get("case_basis") == "usc_spouse":
        projection.setdefault("workflow_category", "immediate_relative_spouse_of_us_citizen")
    if projection.get("relationship_spouse") is True:
        projection.setdefault("beneficiary_current_marital_status", "married")
    if projection.get("first_marriage_for_both") is True:
        projection.setdefault("beneficiary_marriage_count", 1)

    last_entry_type = projection.get("beneficiary_last_entry_type")
    if last_entry_type in LEGAL_ENTRY_TYPES:
        projection["beneficiary_entered_us_legally"] = True
        projection["beneficiary_last_arrival_type"] = "paroled" if last_entry_type == "paroled" else "admitted"
    elif last_entry_type == "entered_without_inspection":
        projection["beneficiary_entered_us_legally"] = False
        projection["beneficiary_last_arrival_type"] = "without_admission"

    address_parts = [
        projection.get("beneficiary_current_address_line1"),
        projection.get("beneficiary_current_address_line2"),
        projection.get("beneficiary_current_address_city"),
        projection.get("beneficiary_current_address_state"),
        projection.get("beneficiary_current_address_postal_code"),
    ]
    if any(_value_is_answered(part) for part in address_parts):
        projection["beneficiary_current_address"] = ", ".join(str(part).strip() for part in address_parts if _value_is_answered(part))

    if projection.get("i130_filing_status") in I130_ALREADY_FILED_STATUSES:
        projection["i130_already_filed"] = True
    elif projection.get("i130_filing_status") == "not_filed":
        projection["i130_already_filed"] = False

    evidence_categories = projection.get("bona_fide_evidence_categories")
    if isinstance(evidence_categories, list):
        projection["has_joint_lease"] = "joint_lease_mortgage" in evidence_categories
        projection["has_joint_bank_account"] = "joint_bank" in evidence_categories
        projection["has_relationship_photos"] = "photos_family" in evidence_categories
        projection["has_affidavits"] = "mostly_photos_chats_affidavits" in evidence_categories

    immigration_violations = projection.get("immigration_violations")
    if isinstance(immigration_violations, list):
        projection["unlawful_entry"] = "unlawful_entry" in immigration_violations
        projection["removal_history"] = projection.get("removal_history") or "prior_removal" in immigration_violations

    return enrich_case_fact_aliases(projection)


def evaluate_prescreen(answers: dict[str, Any]) -> dict[str, Any]:
    return PrescreenRuleEngine().evaluate(answers)


def _default_answer_from_legacy_facts(question_id: str, merged: dict[str, Any]) -> Any:
    if question_id == "last_entry_type" and "beneficiary_entered_us_legally" in merged:
        return "visa_admitted" if merged.get("beneficiary_entered_us_legally") else "entered_without_inspection"
    return None


def _normalize_current_status(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    normalized = value.strip().lower().replace("-", "").replace(" ", "_").replace("/", "_")
    aliases = {
        "b2": "b2",
        "b_2": "b2",
        "b2_visitor": "b2",
        "f1": "f1",
        "f_1": "f1",
        "h1b": "h1b",
        "h_1b": "h1b",
        "l1": "l1",
        "l_1": "l1",
        "j1": "j1",
        "j_1": "j1",
        "k1": "k1",
        "k_1": "k1",
        "esta": "esta_vwp",
        "vwp": "esta_vwp",
        "esta_vwp": "esta_vwp",
        "visa_waiver_program": "esta_vwp",
        "out_of_status": "out_of_status",
        "overstay": "overstay",
        "overstayed": "overstay",
        "no_status": "no_status",
    }
    return aliases.get(normalized, value)


def get_prescreen_state(session: Session, case_id: UUID) -> dict[str, Any]:
    merged = get_merged_case_intake(session, case_id)
    answers = {question["id"]: merged.get(question["id"]) for question in PRESCREEN_QUESTIONS}
    answer_sources: dict[str, str] = {}

    for question in PRESCREEN_QUESTIONS:
        db_path = question.get("db_path")
        if isinstance(db_path, str) and db_path.startswith("intake."):
            source_key = db_path.removeprefix("intake.")
            if source_key in merged:
                value = merged[source_key]
                if question["id"] == "current_status":
                    value = _normalize_current_status(value)
                answers[question["id"]] = value
                answer_sources[question["id"]] = source_key

        field_mappings = question.get("field_mappings") or {}
        if field_mappings:
            grouped_answer = answers.get(question["id"])
            if not isinstance(grouped_answer, dict):
                grouped_answer = {}
            for field_key, field_db_path in field_mappings.items():
                if not isinstance(field_db_path, str) or not field_db_path.startswith("intake."):
                    continue
                source_key = field_db_path.removeprefix("intake.")
                if source_key in merged:
                    grouped_answer[field_key] = merged[source_key]
                    answer_sources[f"{question['id']}.{field_key}"] = source_key
            if grouped_answer:
                answers[question["id"]] = grouped_answer

        if not _value_is_answered(answers.get(question["id"])):
            default_value = _default_answer_from_legacy_facts(question["id"], merged)
            if default_value is not None:
                answers[question["id"]] = default_value
                answer_sources[question["id"]] = "legacy_case_fact"

    return {
        "case_id": str(case_id),
        "answers": {key: value for key, value in answers.items() if _value_is_answered(value)},
        "answer_sources": answer_sources,
        "evaluation": evaluate_prescreen(answers),
    }


def save_prescreen_answers(session: Session, case_id: UUID, answers: dict[str, Any]) -> dict[str, Any]:
    current_state = get_prescreen_state(session, case_id)
    merged_answers = {**current_state["answers"], **answers}
    projection = _project_prescreen_answers(merged_answers)
    upsert_intake_step(session, case_id, PRESCREEN_STEP_KEY, projection)
    return get_prescreen_state(session, case_id)
