"""Saves and evaluates answers for supplemental forms."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlmodel import Session, select

from app.content.admission_classes import normalize_class_of_admission
from app.content.supplemental_forms import (
    all_supplemental_form_questions,
    get_supplemental_form_config,
)
from app.models.entities import IntakeResponse, utcnow
from app.services.case_facts import enrich_case_fact_aliases, value_is_answered
from app.services.i485 import build_i485_intake_projection, get_i485_state
from app.services.intake import apply_case_projection, get_merged_case_intake, upsert_intake_step
from app.services.rules.questionnaire import QuestionnaireEvaluationConfig, QuestionnaireRuleEngine

FORM_STEP_PREFIX = "form_ingestion:"
LOW_CONFIDENCE_THRESHOLD = 0.85

BLOCKING_RISK_CODES = {
    "criminal_history",
    "outside_niche_petitioner_status",
    "outside_niche_spouse_not_us_citizen",
}

OUTSIDE_NICHE_RISK_CODES = {
    "i131_not_i485_advance_parole",
    "i765_non_c9_category",
    "i765_non_initial_request",
    "i864_joint_or_substitute_sponsor",
    "i864_multiple_immigrants",
    "outside_niche_consular_processing",
    "outside_niche_marital_status",
    "outside_niche_petitioner_status",
    "outside_niche_prior_marriage",
    "outside_niche_relationship",
    "outside_niche_spouse_not_us_citizen",
}


def normalize_form_key(form_key: str) -> str:
    """Returns a form key in lowercase without hyphens, such as i130a."""
    return form_key.lower().replace("-", "")


def form_step_key(form_key: str, page_id: str) -> str:
    """Returns the intake step key for a form page."""
    return f"{FORM_STEP_PREFIX}{normalize_form_key(form_key)}:{page_id}"


def form_projection_step_key(form_key: str) -> str:
    """Returns the intake step key for a form's projected case facts."""
    return f"{normalize_form_key(form_key)}_projection"


def _question_by_id(form_key: str) -> dict[str, dict[str, Any]]:
    return {question["id"]: question for question in all_supplemental_form_questions(form_key)}


def _page_by_question_id(form_key: str) -> dict[str, str]:
    config = get_supplemental_form_config(form_key)
    return {
        question["id"]: page["id"]
        for page in config["pages"]
        for question in page["questions"]
    }


def get_form_steps(session: Session, case_id: UUID, form_key: str) -> list[IntakeResponse]:
    """Returns a case's saved pages for a form."""
    prefix = f"{FORM_STEP_PREFIX}{normalize_form_key(form_key)}:"
    return list(
        session.exec(
            select(IntakeResponse)
            .where(
                IntakeResponse.case_id == case_id,
                IntakeResponse.step_key.startswith(prefix),
            )
            .order_by(IntakeResponse.updated_at.asc())
        )
    )


def merge_form_answers(steps: list[IntakeResponse]) -> dict[str, Any]:
    """Returns answers from saved pages, with later saves winning."""
    answers: dict[str, Any] = {}
    for step in sorted(steps, key=lambda item: item.updated_at.timestamp()):
        payload_answers = step.payload.get("answers", {})
        if isinstance(payload_answers, dict):
            answers.update(
                {
                    question_id: _normalize_form_answer(question_id, value)
                    for question_id, value in payload_answers.items()
                }
            )
    return answers


def merge_form_answer_sources(steps: list[IntakeResponse]) -> dict[str, Any]:
    """Returns where each answer came from, with later saves winning."""
    answer_sources: dict[str, Any] = {}
    for step in sorted(steps, key=lambda item: item.updated_at.timestamp()):
        payload_sources = step.payload.get("answer_sources", {})
        if isinstance(payload_sources, dict):
            answer_sources.update(payload_sources)
    return answer_sources


def merge_form_manual_flags(steps: list[IntakeResponse]) -> dict[str, Any]:
    """Returns the manual review flags from saved pages."""
    manual_flags: dict[str, Any] = {}
    for step in sorted(steps, key=lambda item: item.updated_at.timestamp()):
        payload_flags = step.payload.get("manual_flags", {})
        if isinstance(payload_flags, dict):
            manual_flags.update({question_id: value for question_id, value in payload_flags.items() if value})
    return manual_flags


def _address_value(value: Any, key: str) -> Any:
    if not isinstance(value, dict):
        return None
    return value.get(key)


ADDRESS_PART_SUFFIXES = ("_address_line2", "_city", "_state", "_zip", "_province", "_postal_code", "_country")


def _address_prefix(question_id: str) -> str | None:
    for suffix in ADDRESS_PART_SUFFIXES:
        if question_id.endswith(suffix):
            return question_id.removesuffix(suffix)
    return None


def proposals_for_blank_answers(proposals: list[dict[str, Any]], answers: dict[str, Any]) -> list[dict[str, Any]]:
    """Proposals for unanswered questions, minus the rest of an address the form already has a street for.

    Case facts can merge two addresses under one name, such as the I-485's physical address and the I-130's
    mailing address, so a saved PO Box would otherwise take the apartment number of the physical address.
    """
    kept = []
    for proposal in proposals:
        question_id = proposal["question_id"]
        if value_is_answered(answers.get(question_id)):
            continue
        prefix = _address_prefix(question_id)
        if prefix and value_is_answered(answers.get(f"{prefix}_address_line1")):
            continue
        kept.append(proposal)
    return kept


def _proposal_from_case_data(
    *,
    form_key: str,
    question_id: str,
    value: Any,
    source_field: str,
) -> dict[str, Any] | None:
    if not value_is_answered(value):
        return None
    questions = _question_by_id(form_key)
    question = questions.get(question_id)
    if not question:
        return None
    value = _normalize_form_answer(question_id, value)
    return {
        "question_id": question_id,
        "page_id": _page_by_question_id(form_key)[question_id],
        "label": question["label"],
        "value": value,
        "source_field": source_field,
        "confidence": 1.0,
        "pdf_ref": question["pdf_ref"],
    }


def _other_names_as_lines(value: Any) -> Any:
    # The I-485 stores other names as structured rows; the I-765 and I-131 questions take one name per line.
    if not isinstance(value, list):
        return value
    lines = []
    for entry in value:
        if isinstance(entry, dict):
            given = " ".join(str(entry.get(key) or "").strip() for key in ("given_name", "middle_name")).strip()
            lines.append(f"{str(entry.get('family_name') or '').strip()}, {given}".strip(", "))
        elif str(entry).strip():
            lines.append(str(entry).strip())
    return "\n".join(line for line in lines if line)


def _add_i765_proposals(
    *,
    merged: dict[str, Any],
    normalized_form_key: str,
    proposals: list[dict[str, Any]],
) -> None:
    if merged.get("wants_i765") is True or merged.get("i485_family_category") == "spouse_us_citizen":
        proposal = _proposal_from_case_data(
            form_key=normalized_form_key,
            question_id="i765_reason_for_applying",
            value="initial_permission",
            source_field="standard_concurrent_i485_flow",
        )
        if proposal:
            proposals.append(proposal)
        proposal = _proposal_from_case_data(
            form_key=normalized_form_key,
            question_id="i765_eligibility_category",
            value="c9_pending_i485",
            source_field="standard_concurrent_i485_flow",
        )
        if proposal:
            proposals.append(proposal)
    for target, source in {
        "beneficiary_mailing_address_line1": "beneficiary_current_address_line1",
        "beneficiary_mailing_address_line2": "beneficiary_current_address_line2",
        "beneficiary_mailing_city": "beneficiary_current_city",
        "beneficiary_mailing_state": "beneficiary_current_state",
        "beneficiary_mailing_zip": "beneficiary_current_zip",
    }.items():
        proposal = _proposal_from_case_data(
            form_key=normalized_form_key,
            question_id=target,
            value=merged.get(source),
            source_field=source,
        )
        if proposal:
            proposals.append(proposal)
    if merged.get("beneficiary_current_address_line1"):
        proposal = _proposal_from_case_data(
            form_key=normalized_form_key,
            question_id="i765_physical_same_as_mailing",
            value=True,
            source_field="beneficiary_current_address_line1",
        )
        if proposal:
            proposals.append(proposal)
    arrival_place = merged.get("beneficiary_last_arrival_place") or ", ".join(
        part
        for part in [
            str(merged.get("beneficiary_last_arrival_city") or "").strip(),
            str(merged.get("beneficiary_last_arrival_state") or "").strip(),
        ]
        if part
    )
    proposal = _proposal_from_case_data(
        form_key=normalized_form_key,
        question_id="beneficiary_last_arrival_place",
        value=arrival_place,
        source_field="beneficiary_last_arrival_city/state",
    )
    if proposal:
        proposals.append(proposal)


def _add_i131_proposals(
    *,
    merged: dict[str, Any],
    normalized_form_key: str,
    proposals: list[dict[str, Any]],
) -> None:
    if merged.get("wants_i131") is True or merged.get("i485_family_category") == "spouse_us_citizen":
        proposal = _proposal_from_case_data(
            form_key=normalized_form_key,
            question_id="i131_application_type",
            value="advanced_parole_i485_pending",
            source_field="standard_concurrent_i485_flow",
        )
        if proposal:
            proposals.append(proposal)
    for target, source in {
        "beneficiary_mailing_address_line1": "beneficiary_current_address_line1",
        "beneficiary_mailing_address_line2": "beneficiary_current_address_line2",
        "beneficiary_mailing_city": "beneficiary_current_city",
        "beneficiary_mailing_state": "beneficiary_current_state",
        "beneficiary_mailing_zip": "beneficiary_current_zip",
    }.items():
        proposal = _proposal_from_case_data(
            form_key=normalized_form_key,
            question_id=target,
            value=merged.get(source),
            source_field=source,
        )
        if proposal:
            proposals.append(proposal)
    if merged.get("beneficiary_current_address_line1"):
        proposal = _proposal_from_case_data(
            form_key=normalized_form_key,
            question_id="i131_physical_same_as_mailing",
            value=True,
            source_field="beneficiary_current_address_line1",
        )
        if proposal:
            proposals.append(proposal)


def _add_i864_proposals(
    *,
    merged: dict[str, Any],
    normalized_form_key: str,
    proposals: list[dict[str, Any]],
) -> None:
    if merged.get("petitioner_citizenship_status") == "us_citizen":
        proposal = _proposal_from_case_data(
            form_key=normalized_form_key,
            question_id="i864_sponsor_basis",
            value="petitioner",
            source_field="petitioner_citizenship_status",
        )
        if proposal:
            proposals.append(proposal)
    petitioner_address = merged.get("petitioner_current_address")
    for target, source_key in {
        "petitioner_current_address_line1": "line1",
        "petitioner_current_address_line2": "line2",
        "petitioner_current_city": "city",
        "petitioner_current_state": "state",
        "petitioner_current_zip": "zip",
    }.items():
        proposal = _proposal_from_case_data(
            form_key=normalized_form_key,
            question_id=target,
            value=_address_value(petitioner_address, source_key),
            source_field=f"petitioner_current_address.{source_key}",
        )
        if proposal:
            proposals.append(proposal)
    if isinstance(petitioner_address, dict) and petitioner_address.get("line1"):
        proposal = _proposal_from_case_data(
            form_key=normalized_form_key,
            question_id="i864_physical_same_as_mailing",
            value=True,
            source_field="petitioner_current_address.line1",
        )
        if proposal:
            proposals.append(proposal)
    if str(merged.get("petitioner_country_of_birth") or "").upper() == "US" or merged.get("petitioner_citizenship_status") == "us_citizen":
        proposal = _proposal_from_case_data(
            form_key=normalized_form_key,
            question_id="petitioner_country_of_domicile",
            value="United States",
            source_field="petitioner_citizenship_status",
        )
        if proposal:
            proposals.append(proposal)
    if merged.get("children_count") in {0, "0", None, ""}:
        for question_id, value in {
            "i864_only_principal_immigrant": True,
            "i864_sponsoring_family_members": False,
            "i864_total_immigrants": 1,
            "i864_sponsor_married_count": 0,
            "i864_dependent_children_count": 0,
            "i864_other_dependents_count": 0,
            "i864_prior_sponsored_immigrants_count": 0,
            "i864_household_members_combining_income_count": 0,
        }.items():
            proposal = _proposal_from_case_data(
                form_key=normalized_form_key,
                question_id=question_id,
                value=value,
                source_field="children_count",
            )
            if proposal:
                proposals.append(proposal)
    if value_is_answered(merged.get("annual_income")):
        proposal = _proposal_from_case_data(
            form_key=normalized_form_key,
            question_id="i864_household_income",
            value=merged.get("annual_income"),
            source_field="annual_income",
        )
        if proposal:
            proposals.append(proposal)


def _add_i130_proposals(
    *,
    merged: dict[str, Any],
    normalized_form_key: str,
    proposals: list[dict[str, Any]],
) -> None:
    if merged.get("relationship_spouse") is True or merged.get("marriage_date"):
        proposal = _proposal_from_case_data(
            form_key=normalized_form_key,
            question_id="relationship_spouse",
            value=True,
            source_field="relationship_spouse/marriage_date",
        )
        if proposal:
            proposals.append(proposal)
    if merged.get("first_marriage_for_both") is True:
        for question_id in ("beneficiary_marriage_count", "beneficiary_current_marital_status"):
            proposal = _proposal_from_case_data(
                form_key=normalized_form_key,
                question_id=question_id,
                value=1 if question_id == "beneficiary_marriage_count" else "married",
                source_field="first_marriage_for_both",
            )
            if proposal:
                proposals.append(proposal)
    if str(merged.get("beneficiary_location") or "").lower() == "usa":
        proposal = _proposal_from_case_data(
            form_key=normalized_form_key,
            question_id="beneficiary_adjustment_path",
            value=True,
            source_field="beneficiary_location",
        )
        if proposal:
            proposals.append(proposal)


def _add_i130a_proposals(*, merged: dict[str, Any], normalized_form_key: str, proposals: list[dict[str, Any]]) -> None:
    if merged.get("marriage_date"):
        proposal = _proposal_from_case_data(
            form_key=normalized_form_key,
            question_id="beneficiary_current_marital_status",
            value="married",
            source_field="marriage_date",
        )
        if proposal:
            proposals.append(proposal)
    if merged.get("first_marriage_for_both") is True:
        proposal = _proposal_from_case_data(
            form_key=normalized_form_key,
            question_id="beneficiary_marriage_count",
            value=1,
            source_field="first_marriage_for_both",
        )
        if proposal:
            proposals.append(proposal)
    proposal = _proposal_from_case_data(
        form_key=normalized_form_key,
        question_id="beneficiary_address_since",
        value=merged.get("beneficiary_current_address_since"),
        source_field="beneficiary_current_address_since",
    )
    if proposal:
        proposals.append(proposal)


def build_form_answer_proposals_from_case_data(form_key: str, merged: dict[str, Any]) -> list[dict[str, Any]]:
    """Returns answers a form can prefill from case facts, one per question."""
    normalized_form_key = normalize_form_key(form_key)
    merged = enrich_case_fact_aliases(merged)
    proposals: list[dict[str, Any]] = []

    for question in all_supplemental_form_questions(normalized_form_key):
        db_path = question.get("db_path")
        if not isinstance(db_path, str) or not db_path.startswith("intake."):
            continue
        source_field = db_path.removeprefix("intake.")
        value = merged.get(source_field)
        if source_field == "beneficiary_other_names":
            value = _other_names_as_lines(value)
        proposal = _proposal_from_case_data(
            form_key=normalized_form_key,
            question_id=question["id"],
            value=value,
            source_field=source_field,
        )
        if proposal:
            proposals.append(proposal)

    if normalized_form_key == "i765":
        _add_i765_proposals(
            merged=merged,
            normalized_form_key=normalized_form_key,
            proposals=proposals,
        )

    if normalized_form_key == "i131":
        _add_i131_proposals(
            merged=merged,
            normalized_form_key=normalized_form_key,
            proposals=proposals,
        )

    if normalized_form_key == "i864":
        _add_i864_proposals(
            merged=merged,
            normalized_form_key=normalized_form_key,
            proposals=proposals,
        )

    if normalized_form_key == "i130":
        _add_i130_proposals(
            merged=merged,
            normalized_form_key=normalized_form_key,
            proposals=proposals,
        )

    if normalized_form_key == "i130a":
        _add_i130a_proposals(merged=merged, normalized_form_key=normalized_form_key, proposals=proposals)

    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for proposal in proposals:
        question_id = proposal["question_id"]
        if question_id in seen:
            continue
        seen.add(question_id)
        deduped.append(proposal)
    return deduped


def build_form_intake_projection(form_key: str, answers: dict[str, Any]) -> dict[str, Any]:
    """Returns the case facts implied by a form's answers."""
    questions = _question_by_id(form_key)
    projection: dict[str, Any] = {}
    for question_id, value in answers.items():
        question = questions.get(question_id)
        if not question:
            continue
        db_path = question.get("db_path")
        if not isinstance(db_path, str) or not db_path.startswith("intake."):
            continue
        field_name = db_path.removeprefix("intake.")
        if value_is_answered(value):
            projection[field_name] = _normalize_form_answer(question_id, value)

    if normalize_form_key(form_key) == "i765":
        if answers.get("i765_eligibility_category") == "c9_pending_i485":
            projection["wants_i765"] = True
        if answers.get("i765_arrested_or_convicted") is True:
            projection["criminal_history"] = True
    if normalize_form_key(form_key) == "i131":
        if answers.get("i131_application_type") == "advanced_parole_i485_pending":
            projection["wants_i131"] = True
    return enrich_case_fact_aliases(projection)


def _normalize_form_answer(question_id: str, value: Any) -> Any:
    if question_id == "beneficiary_class_of_admission":
        raw = str(value or "").strip()
        normalized_raw = raw.lower().replace("-", "").replace(" ", "")
        if normalized_raw in {"parolee", "nostatus"}:
            return raw.lower()
        return normalize_class_of_admission(value)
    if question_id == "i131_expected_trip_length" and isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return value


def _valid_positive_integer(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value > 0
    if isinstance(value, str):
        return value.strip().isdigit() and int(value.strip()) > 0
    return False


def _risk_matches(value: Any, risk_when: Any) -> bool:
    if risk_when is None:
        return False
    if risk_when == "present":
        return value_is_answered(value)
    if risk_when == "not_1":
        try:
            return int(value) != 1
        except (TypeError, ValueError):
            return value_is_answered(value)
    if risk_when == "zero_or_less":
        try:
            return float(value) <= 0
        except (TypeError, ValueError):
            return False
    if risk_when == "not_married":
        return value_is_answered(value) and value != "married"
    if risk_when == "not_us_citizen":
        return value_is_answered(value) and value != "us_citizen"
    if risk_when == "not_united_states":
        return value_is_answered(value) and str(value).strip().lower() not in {"us", "usa", "united states"}
    if risk_when == "not_petitioner":
        return value_is_answered(value) and value != "petitioner"
    if risk_when == "replacement_or_renewal":
        return value in {"replacement", "renewal"}
    if risk_when == "not_c9":
        return value_is_answered(value) and value != "c9_pending_i485"
    if risk_when == "not_i485_advance_parole":
        return value_is_answered(value) and value != "advanced_parole_i485_pending"
    return value == risk_when


def _supplemental_format_flags(question: dict[str, Any], value: Any) -> list[dict[str, Any]]:
    if question["id"] != "i131_expected_trip_length":
        return []
    if not value_is_answered(value) or _valid_positive_integer(value):
        return []
    return [
        {
            "code": "i131_expected_trip_length_not_days",
            "severity": "blocking",
            "category": "format",
            "question_id": question["id"],
            "title": "Expected trip length must be entered in days",
            "description": "Enter only a whole number of days, for example 14 for a two-week trip.",
            "pdf_ref": question["pdf_ref"],
        }
    ]


def evaluate_form_answers(form_key: str, answers: dict[str, Any]) -> dict[str, Any]:
    """Returns a form's completeness status and review flags."""
    config = get_supplemental_form_config(form_key)
    normalized_form_key = normalize_form_key(form_key)
    evaluation_config = QuestionnaireEvaluationConfig(
        form_key=normalized_form_key,
        ready_readiness=f"ready_for_standard_{normalized_form_key}_review",
        questions=all_supplemental_form_questions(normalized_form_key),
        pages=config["pages"],
        blocking_risk_codes=BLOCKING_RISK_CODES,
        outside_niche_risk_codes=OUTSIDE_NICHE_RISK_CODES,
        value_is_answered=value_is_answered,
        risk_matches=_risk_matches,
        risk_title=lambda question: f"Answer needs review before using the standard {config['form_code']} flow",
        risk_description=lambda question: (
            f"The answer to '{question['label']}' may be outside the expected first-marriage, "
            "U.S.-citizen-spouse concurrent filing profile."
        ),
        extra_question_flags=_supplemental_format_flags,
    )
    return QuestionnaireRuleEngine().evaluate(answers, evaluation_config)


def get_form_state(session: Session, case_id: UUID, form_key: str) -> dict[str, Any]:
    """Returns a form's answers, sources, flags, and evaluation."""
    config = get_supplemental_form_config(form_key)
    steps = get_form_steps(session, case_id, form_key)
    answers = merge_form_answers(steps)
    return {
        "case_id": str(case_id),
        "form_key": config["form_key"],
        "answers": answers,
        "answer_sources": merge_form_answer_sources(steps),
        "manual_flags": merge_form_manual_flags(steps),
        "evaluation": evaluate_form_answers(form_key, answers),
        "saved_pages": [step.payload.get("page_id") for step in steps if step.payload.get("page_id")],
    }


def save_form_page_answers(
    session: Session,
    case_id: UUID,
    form_key: str,
    page_id: str,
    answers: dict[str, Any],
    manual_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Saves one form page and updates the case facts it projects to."""
    config = get_supplemental_form_config(form_key)
    page_by_id = {page["id"]: page for page in config["pages"]}
    page_ids = set(page_by_id)
    if page_id not in page_ids:
        raise ValueError(f"Unknown {config['form_code']} questionnaire page")
    answers = {question_id: _normalize_form_answer(question_id, value) for question_id, value in answers.items()}

    step_key = form_step_key(form_key, page_id)
    step = session.exec(
        select(IntakeResponse).where(IntakeResponse.case_id == case_id, IntakeResponse.step_key == step_key)
    ).first()
    existing_sources = step.payload.get("answer_sources", {}) if step and isinstance(step.payload, dict) else {}
    if not isinstance(existing_sources, dict):
        existing_sources = {}
    answer_sources = {
        **existing_sources,
        **{
            question_id: {
                "source_type": "user",
                "updated_at": utcnow().isoformat(),
            }
            for question_id, value in answers.items()
            if value_is_answered(value)
        },
    }
    page_question_ids = {question["id"] for question in page_by_id[page_id]["questions"]}
    filtered_manual_flags = {
        question_id: value
        for question_id, value in (manual_flags or {}).items()
        if question_id in page_question_ids and value
    }
    payload = {
        "form_key": config["form_key"],
        "page_id": page_id,
        "answers": answers,
        "answer_sources": answer_sources,
        "manual_flags": filtered_manual_flags,
    }
    if step:
        step.payload = payload
        step.updated_at = utcnow()
    else:
        session.add(IntakeResponse(case_id=case_id, step_key=step_key, payload=payload))
    session.flush()

    state = get_form_state(session, case_id, form_key)
    projection = build_form_intake_projection(form_key, state["answers"])
    upsert_intake_step(session, case_id, form_projection_step_key(form_key), projection)
    apply_case_projection(session, case_id, get_merged_case_intake(session, case_id))
    return get_form_state(session, case_id, form_key)


# These forms reuse saved I-485 answers, so a case saved before a mapping existed still gets them.
FORMS_USING_I485_ANSWERS = {"i765", "i131", "i130a"}


def get_form_case_intake(session: Session, case_id: UUID, form_key: str) -> dict[str, Any]:
    """Return the case facts a form draws on, so import, generation, and validation agree."""
    merged = get_merged_case_intake(session, case_id)
    if normalize_form_key(form_key) in FORMS_USING_I485_ANSWERS:
        return {**merged, **build_i485_intake_projection(get_i485_state(session, case_id)["answers"])}
    return merged


def import_form_answers_from_case_data(
    session: Session,
    case_id: UUID,
    form_key: str,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Fills a form from case facts, keeping existing answers unless told to overwrite."""
    config = get_supplemental_form_config(form_key)
    proposals = build_form_answer_proposals_from_case_data(form_key, get_form_case_intake(session, case_id, form_key))
    state = get_form_state(session, case_id, form_key)
    answers = dict(state["answers"])
    answer_sources = dict(state["answer_sources"])
    imported_question_ids: set[str] = set()
    skipped_question_ids: set[str] = set()

    applicable = proposals if overwrite else proposals_for_blank_answers(proposals, answers)
    applicable_ids = {proposal["question_id"] for proposal in applicable}
    skipped_question_ids.update(
        proposal["question_id"] for proposal in proposals if proposal["question_id"] not in applicable_ids
    )
    for proposal in applicable:
        question_id = proposal["question_id"]
        answers[question_id] = proposal["value"]
        imported_question_ids.add(question_id)
        answer_sources[question_id] = {
            "source_type": "case_intake",
            "source_field": proposal["source_field"],
            "confidence": proposal["confidence"],
            "updated_at": utcnow().isoformat(),
        }

    page_answers: dict[str, dict[str, Any]] = {}
    page_sources: dict[str, dict[str, Any]] = {}
    for question_id in imported_question_ids:
        page_id = _page_by_question_id(form_key)[question_id]
        page_answers.setdefault(page_id, {})[question_id] = answers[question_id]
        page_sources.setdefault(page_id, {})[question_id] = answer_sources[question_id]

    for page_id, imported_answers in page_answers.items():
        step_key = form_step_key(form_key, page_id)
        step = session.exec(
            select(IntakeResponse).where(
                IntakeResponse.case_id == case_id,
                IntakeResponse.step_key == step_key,
            )
        ).first()
        existing_answers = step.payload.get("answers", {}) if step and isinstance(step.payload, dict) else {}
        existing_sources = step.payload.get("answer_sources", {}) if step and isinstance(step.payload, dict) else {}
        existing_manual_flags = step.payload.get("manual_flags", {}) if step and isinstance(step.payload, dict) else {}
        if not isinstance(existing_answers, dict):
            existing_answers = {}
        if not isinstance(existing_sources, dict):
            existing_sources = {}
        if not isinstance(existing_manual_flags, dict):
            existing_manual_flags = {}
        payload = {
            "form_key": config["form_key"],
            "page_id": page_id,
            "answers": {**existing_answers, **imported_answers},
            "answer_sources": {**existing_sources, **page_sources[page_id]},
            "manual_flags": existing_manual_flags,
        }
        if step:
            step.payload = payload
            step.updated_at = utcnow()
        else:
            session.add(IntakeResponse(case_id=case_id, step_key=step_key, payload=payload))
    session.flush()

    refreshed_state = get_form_state(session, case_id, form_key)
    projection = build_form_intake_projection(form_key, refreshed_state["answers"])
    upsert_intake_step(session, case_id, form_projection_step_key(form_key), projection)
    apply_case_projection(session, case_id, get_merged_case_intake(session, case_id))

    return {
        "state": get_form_state(session, case_id, form_key),
        "proposals": proposals,
        "imported_count": len(imported_question_ids),
        "skipped_count": len(skipped_question_ids),
    }


def build_form_fill_preview(session: Session, case_id: UUID, form_key: str) -> dict[str, Any]:
    """Returns what is missing or needs review before a form can be generated."""
    config = get_supplemental_form_config(form_key)
    state = get_form_state(session, case_id, form_key)
    answers = state["answers"]
    answer_sources = state["answer_sources"]
    evaluation = state["evaluation"]

    fields: list[dict[str, Any]] = []
    missing_required: list[dict[str, Any]] = []
    low_confidence_fields: list[dict[str, Any]] = []
    for page in config["pages"]:
        for question in page["questions"]:
            question_id = question["id"]
            value = answers.get(question_id)
            if not value_is_answered(value):
                if question.get("required"):
                    missing_required.append(
                        {
                            "question_id": question_id,
                            "page_id": page["id"],
                            "label": question["label"],
                            "pdf_ref": question["pdf_ref"],
                        }
                    )
                continue

            source = answer_sources.get(question_id, {})
            confidence = source.get("confidence") if isinstance(source, dict) else None
            needs_review = bool(
                isinstance(confidence, (int, float)) and confidence < LOW_CONFIDENCE_THRESHOLD
            )
            field = {
                "target_key": f"form_{config['form_key']}.{question_id}",
                "question_id": question_id,
                "page_id": page["id"],
                "label": question["label"],
                "pdf_ref": question["pdf_ref"],
                "answer_type": question["answer_type"],
                "value": value,
                "source": source,
                "needs_review": needs_review,
            }
            fields.append(field)
            if needs_review:
                low_confidence_fields.append(field)

    blocking_flags = [flag for flag in evaluation["flags"] if flag["severity"] == "blocking"]
    outside_niche_flags = [flag for flag in evaluation["flags"] if flag["category"] == "outside_niche"]

    if blocking_flags:
        generation_status = "blocked_by_risk"
    elif outside_niche_flags:
        generation_status = "blocked_outside_standard_niche"
    elif missing_required:
        generation_status = "incomplete"
    elif low_confidence_fields:
        generation_status = "needs_source_review"
    else:
        generation_status = "ready_for_user_review"

    return {
        "case_id": str(case_id),
        "form_key": config["form_key"],
        "generation_status": generation_status,
        "ready_for_pdf_generation": generation_status == "ready_for_user_review",
        "questionnaire_version": config["version"],
        "field_count": len(fields),
        "missing_required_count": len(missing_required),
        "blocking_flag_count": len(blocking_flags),
        "outside_niche_flag_count": len(outside_niche_flags),
        "low_confidence_count": len(low_confidence_fields),
        "fields": fields,
        "missing_required": missing_required,
        "blocking_flags": blocking_flags,
        "outside_niche_flags": outside_niche_flags,
        "low_confidence_fields": low_confidence_fields,
        "recommendations": [
            "Review every generated value against the source documents before filing.",
            f"Verify the current USCIS {config['form_code']} edition before printing or signing.",
            "Do not treat generated drafts as legal advice or filing-ready output.",
        ],
    }
