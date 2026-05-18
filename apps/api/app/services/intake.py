from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlmodel import Session, select

from app.models.entities import CaseRecord, IntakeResponse, MarriageRecord, PersonRecord
from app.services.case_facts import enrich_case_fact_aliases
from app.services.rules.case_facts import CaseFactsContext, CaseFactsRuleEngine


REQUIRED_FIELDS = {
    "petitioner_first_name": "Petitioner first name",
    "petitioner_last_name": "Petitioner last name",
    "beneficiary_first_name": "Beneficiary first name",
    "beneficiary_last_name": "Beneficiary last name",
    "marriage_date": "Marriage date",
    "first_marriage_for_both": "First marriage confirmation",
    "beneficiary_location": "Beneficiary location",
    "beneficiary_entered_us_legally": "Legal entry confirmation",
    "beneficiary_country_of_birth": "Beneficiary country of birth",
    "household_size": "Household size",
}

COUNTRY_ALIASES = {
    "co": "CO",
    "colombia": "CO",
    "us": "US",
    "usa": "US",
    "united states": "US",
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def normalize_country(value: Any) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    alias = COUNTRY_ALIASES.get(raw.lower())
    if alias:
        return alias
    return raw.upper()


def merge_intake_state(steps: list[IntakeResponse]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for step in sorted(steps, key=lambda item: item.updated_at.timestamp()):
        merged.update(step.payload)
    merged = enrich_case_fact_aliases(merged)
    if "beneficiary_country_of_birth" in merged:
        merged["beneficiary_country_of_birth"] = normalize_country(merged["beneficiary_country_of_birth"])
    if "country_of_focus" in merged:
        merged["country_of_focus"] = normalize_country(merged["country_of_focus"])
    return merged


def get_case_steps(session: Session, case_id: UUID) -> list[IntakeResponse]:
    return list(
        session.exec(
            select(IntakeResponse)
            .where(
                IntakeResponse.case_id == case_id,
                ~IntakeResponse.step_key.startswith("i485_ingestion:"),
                ~IntakeResponse.step_key.startswith("form_ingestion:"),
            )
            .order_by(IntakeResponse.updated_at.asc())
        )
    )


def get_merged_case_intake(session: Session, case_id: UUID) -> dict[str, Any]:
    return merge_intake_state(get_case_steps(session, case_id))


def get_missing_fields(merged: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for key, label in REQUIRED_FIELDS.items():
        value = merged.get(key)
        if value is None or value == "":
            missing.append(label)
    return missing


def derive_case_facts(merged: dict[str, Any]) -> dict[str, Any]:
    return CaseFactsRuleEngine().evaluate(
        CaseFactsContext(
            merged=merged,
            normalize_country=normalize_country,
        )
    )


def _get_or_create_person(session: Session, case_id: UUID, role: str) -> PersonRecord:
    person = session.exec(
        select(PersonRecord).where(PersonRecord.case_id == case_id, PersonRecord.role == role)
    ).first()
    if person:
        return person
    person = PersonRecord(case_id=case_id, role=role)
    session.add(person)
    session.flush()
    return person


def _get_or_create_marriage(session: Session, case_id: UUID) -> MarriageRecord:
    marriage = session.exec(select(MarriageRecord).where(MarriageRecord.case_id == case_id)).first()
    if marriage:
        return marriage
    marriage = MarriageRecord(case_id=case_id)
    session.add(marriage)
    session.flush()
    return marriage


def _parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def apply_case_projection(session: Session, case_id: UUID, merged: dict[str, Any]) -> None:
    case = session.get(CaseRecord, case_id)
    if not case:
        return

    country_of_focus = normalize_country(
        merged.get("country_of_focus") or merged.get("beneficiary_country_of_birth")
    )
    if country_of_focus:
        case.country_of_focus = country_of_focus
    case.petitioner_email = merged.get("petitioner_email", case.petitioner_email)
    case.beneficiary_email = merged.get("beneficiary_email", case.beneficiary_email)
    case.updated_at = _utcnow()

    petitioner = _get_or_create_person(session, case_id, "petitioner")
    petitioner.first_name = merged.get("petitioner_first_name", petitioner.first_name)
    petitioner.last_name = merged.get("petitioner_last_name", petitioner.last_name)
    petitioner.email = merged.get("petitioner_email", petitioner.email)
    petitioner.country_of_citizenship = "US"
    petitioner.country_of_birth = normalize_country(
        merged.get("petitioner_country_of_birth") or petitioner.country_of_birth
    )
    petitioner.annual_income = merged.get("annual_income", petitioner.annual_income)
    petitioner.employment_status = merged.get("employment_status", petitioner.employment_status)
    petitioner.updated_at = _utcnow()

    beneficiary = _get_or_create_person(session, case_id, "beneficiary")
    beneficiary.first_name = merged.get("beneficiary_first_name", beneficiary.first_name)
    beneficiary.last_name = merged.get("beneficiary_last_name", beneficiary.last_name)
    beneficiary.email = merged.get("beneficiary_email", beneficiary.email)
    beneficiary.country_of_birth = normalize_country(
        merged.get("beneficiary_country_of_birth") or beneficiary.country_of_birth
    )
    beneficiary.country_of_citizenship = normalize_country(
        merged.get("beneficiary_country_of_citizenship") or beneficiary.country_of_citizenship
    )
    beneficiary.location = merged.get("beneficiary_location", beneficiary.location)
    beneficiary.entered_us_legally = merged.get(
        "beneficiary_entered_us_legally", beneficiary.entered_us_legally
    )
    beneficiary.current_immigration_status = merged.get(
        "beneficiary_current_immigration_status", beneficiary.current_immigration_status
    )
    beneficiary.updated_at = _utcnow()

    marriage = _get_or_create_marriage(session, case_id)
    marriage.marriage_date = _parse_date(merged.get("marriage_date")) or marriage.marriage_date
    marriage.first_marriage_for_both = merged.get(
        "first_marriage_for_both", marriage.first_marriage_for_both
    )
    marriage.has_children = merged.get("has_children", marriage.has_children)
    marriage.household_size = merged.get("household_size", marriage.household_size)
    marriage.updated_at = _utcnow()


def upsert_intake_step(session: Session, case_id: UUID, step_key: str, payload: dict[str, Any]) -> IntakeResponse:
    step = session.exec(
        select(IntakeResponse).where(IntakeResponse.case_id == case_id, IntakeResponse.step_key == step_key)
    ).first()
    if step:
        step.payload = payload
        step.updated_at = _utcnow()
    else:
        step = IntakeResponse(case_id=case_id, step_key=step_key, payload=payload)
        session.add(step)
        session.flush()

    merged = get_merged_case_intake(session, case_id)
    apply_case_projection(session, case_id, merged)
    return step
