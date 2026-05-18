from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlmodel import Session, select

from app.content.admission_classes import normalize_class_of_admission
from app.content.i485_questionnaire import I485_QUESTIONNAIRE, I485_QUESTIONNAIRE_VERSION, all_i485_questions
from app.core.config import settings
from app.models.entities import IntakeResponse, OCRStatus, UploadedDocument
from app.services.case_facts import enrich_case_fact_aliases
from app.services.intake import apply_case_projection, get_merged_case_intake, upsert_intake_step
from app.services.rules.questionnaire import QuestionnaireEvaluationConfig, QuestionnaireRuleEngine


I485_STEP_PREFIX = "i485_ingestion:"
I485_PROJECTION_STEP = "i485_projection"

BLOCKING_RISK_CODES = {
    "alien_smuggling",
    "commercialized_vice",
    "controlled_substances",
    "criminal_history",
    "false_us_citizenship",
    "fraud_or_misrepresentation",
    "human_rights",
    "illegal_reentry",
    "money_laundering",
    "removal_history",
    "security_related",
    "trafficking",
    "unlawful_entry",
    "unlawful_presence",
}

OUTSIDE_NICHE_RISK_CODES = {
    "outside_niche_245i",
    "outside_niche_category",
    "outside_niche_children",
    "outside_niche_cspa",
    "outside_niche_derivative",
    "outside_niche_i864_exemption",
    "outside_niche_marital_status",
    "outside_niche_prior_marriage",
    "outside_niche_spouse_not_us_citizen",
}

QUESTION_BY_ID = {question["id"]: question for question in all_i485_questions()}
PAGE_BY_QUESTION_ID = {
    question["id"]: page["id"] for page in I485_QUESTIONNAIRE for question in page["questions"]
}
I485_EXTRACTED_FIELD_TO_QUESTION_ID = {
    "beneficiary_a_number": "beneficiary_a_number",
    "beneficiary_last_name": "beneficiary_last_name",
    "beneficiary_first_name": "beneficiary_first_name",
    "beneficiary_middle_name": "beneficiary_middle_name",
    "beneficiary_date_of_birth": "beneficiary_date_of_birth",
    "beneficiary_city_of_birth": "beneficiary_city_of_birth",
    "beneficiary_country_of_birth": "beneficiary_country_of_birth",
    "beneficiary_country_of_citizenship": "beneficiary_country_of_citizenship",
    "beneficiary_passport_number": "beneficiary_passport_number",
    "beneficiary_passport_expiration": "beneficiary_passport_expiration",
    "beneficiary_passport_country": "beneficiary_passport_country",
    "beneficiary_visa_number": "beneficiary_visa_number",
    "beneficiary_last_arrival_city": "beneficiary_last_arrival_city",
    "beneficiary_last_arrival_state": "beneficiary_last_arrival_state",
    "beneficiary_last_arrival_date": "beneficiary_last_arrival_date",
    "beneficiary_class_of_admission": "beneficiary_class_of_admission",
    "beneficiary_i94_number": "beneficiary_i94_number",
    "beneficiary_last_arrival_first_us_presence": "beneficiary_last_arrival_first_us_presence",
    "beneficiary_status_expires_on": "beneficiary_status_expires_on",
    "beneficiary_current_immigration_status": "beneficiary_current_immigration_status",
    "beneficiary_current_status_expires_on": "beneficiary_current_status_expires_on",
    "beneficiary_current_address_line1": "beneficiary_current_address_line1",
    "beneficiary_current_address_line2": "beneficiary_current_address_line2",
    "beneficiary_current_city": "beneficiary_current_city",
    "beneficiary_current_state": "beneficiary_current_state",
    "beneficiary_current_zip": "beneficiary_current_zip",
    "beneficiary_address_since": "beneficiary_address_since",
    "beneficiary_prior_address_history": "beneficiary_prior_address_history",
    "beneficiary_current_employer_or_school": "beneficiary_current_employer_or_school",
    "beneficiary_current_occupation": "beneficiary_current_occupation",
    "beneficiary_employment_history": "beneficiary_employment_history",
    "beneficiary_ssn": "beneficiary_ssn",
    "beneficiary_current_marital_status": "beneficiary_current_marital_status",
    "beneficiary_marriage_count": "beneficiary_marriage_count",
    "petitioner_last_name": "petitioner_last_name",
    "petitioner_first_name": "petitioner_first_name",
    "petitioner_middle_name": "petitioner_middle_name",
    "petitioner_date_of_birth": "petitioner_date_of_birth",
    "petitioner_country_of_birth": "petitioner_country_of_birth",
    "petitioner_current_address": "petitioner_current_address",
    "marriage_place_city": "marriage_place_city",
    "marriage_place_state": "marriage_place_state",
    "marriage_place_country": "marriage_place_country",
    "marriage_date": "marriage_date",
    "children_count": "children_count",
    "beneficiary_phone": "beneficiary_phone",
    "beneficiary_email": "beneficiary_email",
}

LOW_CONFIDENCE_THRESHOLD = 0.85


def _utcnow() -> datetime:
    return datetime.now(UTC)


def i485_step_key(page_id: str) -> str:
    return f"{I485_STEP_PREFIX}{page_id}"


def get_i485_steps(session: Session, case_id: UUID) -> list[IntakeResponse]:
    return list(
        session.exec(
            select(IntakeResponse)
            .where(IntakeResponse.case_id == case_id, IntakeResponse.step_key.startswith(I485_STEP_PREFIX))
            .order_by(IntakeResponse.updated_at.asc())
        )
    )


def _datetime_sort_key(value: datetime) -> float:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.timestamp()


def merge_i485_answers(steps: list[IntakeResponse]) -> dict[str, Any]:
    answers: dict[str, Any] = {}
    for step in sorted(steps, key=lambda item: _datetime_sort_key(item.updated_at)):
        payload_answers = step.payload.get("answers", {})
        if isinstance(payload_answers, dict):
            answers.update(
                {
                    question_id: _normalize_i485_answer(question_id, value)
                    for question_id, value in payload_answers.items()
                }
            )
    return answers


def _normalize_i485_answer(question_id: str, value: Any) -> Any:
    if question_id == "beneficiary_class_of_admission":
        return normalize_class_of_admission(value)
    return value


def merge_i485_answer_sources(steps: list[IntakeResponse]) -> dict[str, Any]:
    answer_sources: dict[str, Any] = {}
    for step in sorted(steps, key=lambda item: _datetime_sort_key(item.updated_at)):
        payload_sources = step.payload.get("answer_sources", {})
        if isinstance(payload_sources, dict):
            answer_sources.update(payload_sources)
    return answer_sources


def merge_i485_manual_flags(steps: list[IntakeResponse]) -> dict[str, Any]:
    manual_flags: dict[str, Any] = {}
    for step in sorted(steps, key=lambda item: _datetime_sort_key(item.updated_at)):
        payload_flags = step.payload.get("manual_flags", {})
        if isinstance(payload_flags, dict):
            manual_flags.update({question_id: value for question_id, value in payload_flags.items() if value})
    return manual_flags


def save_i485_page_answers(
    session: Session,
    case_id: UUID,
    page_id: str,
    answers: dict[str, Any],
    manual_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    page_by_id = {page["id"]: page for page in I485_QUESTIONNAIRE}
    page_ids = set(page_by_id)
    if page_id not in page_ids:
        raise ValueError("Unknown I-485 questionnaire page")
    answers = {question_id: _normalize_i485_answer(question_id, value) for question_id, value in answers.items()}

    step_key = i485_step_key(page_id)
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
                "updated_at": _utcnow().isoformat(),
            }
            for question_id, value in answers.items()
            if value not in (None, "", [], {})
        },
    }
    page_question_ids = {question["id"] for question in page_by_id[page_id]["questions"]}
    filtered_manual_flags = {
        question_id: value
        for question_id, value in (manual_flags or {}).items()
        if question_id in page_question_ids and value
    }
    payload = {
        "page_id": page_id,
        "answers": answers,
        "answer_sources": answer_sources,
        "manual_flags": filtered_manual_flags,
    }
    if step:
        step.payload = payload
        step.updated_at = _utcnow()
    else:
        session.add(IntakeResponse(case_id=case_id, step_key=step_key, payload=payload))
    session.flush()

    state = get_i485_state(session, case_id)
    projection = build_i485_intake_projection(state["answers"])
    upsert_intake_step(session, case_id, I485_PROJECTION_STEP, projection)
    apply_case_projection(session, case_id, get_merged_case_intake(session, case_id))
    return get_i485_state(session, case_id)


def build_i485_intake_projection(answers: dict[str, Any]) -> dict[str, Any]:
    projection: dict[str, Any] = {}
    for question_id, value in answers.items():
        question = QUESTION_BY_ID.get(question_id)
        if not question:
            continue
        db_path = question.get("db_path")
        if not isinstance(db_path, str) or not db_path.startswith("intake."):
            continue
        field_name = db_path.removeprefix("intake.")
        if value not in (None, "", [], {}):
            projection[field_name] = _normalize_i485_answer(question_id, value)

    if projection.get("i485_family_category") == "spouse_us_citizen":
        projection["beneficiary_location"] = projection.get("beneficiary_location") or "usa"
    if answers.get("beneficiary_last_arrival_type") in {"admitted", "paroled"}:
        projection["beneficiary_entered_us_legally"] = True
    if answers.get("beneficiary_last_arrival_type") == "without_admission":
        projection["beneficiary_entered_us_legally"] = False
        projection["unlawful_entry"] = True
    marriage_count = answers.get("beneficiary_marriage_count")
    if marriage_count == 1 and answers.get("beneficiary_current_marital_status") == "married":
        projection["first_marriage_for_both"] = True
    elif marriage_count not in (None, "", [], {}) and marriage_count != 1:
        projection["first_marriage_for_both"] = False
    return enrich_case_fact_aliases(projection)


def _value_is_answered(value: Any) -> bool:
    if isinstance(value, list):
        return any(_value_is_answered(entry) for entry in value)
    if isinstance(value, dict):
        return any(_value_is_answered(entry_value) for entry_value in value.values())
    return value not in (None, "", [], {})


US_COUNTRY_NAMES = {
    "united states",
    "united states of america",
    "usa",
    "us",
    "u s",
    "u s a",
    "america",
}


def _normalized_country(value: Any) -> str:
    return " ".join(str(value or "").lower().replace(".", " ").replace(",", " ").split())


def _is_non_us_address(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    country = _normalized_country(value.get("country"))
    return bool(country and country not in US_COUNTRY_NAMES)


def _conditional_required_question_ids(answers: dict[str, Any]) -> set[str]:
    required_ids: set[str] = set()
    if answers.get("beneficiary_mailing_same_as_physical") is False:
        required_ids.add("beneficiary_mailing_address")
    if answers.get("beneficiary_has_ssn") is True:
        required_ids.add("beneficiary_ssn")
    prior_addresses = answers.get("beneficiary_prior_address_history")
    first_prior = prior_addresses[0] if isinstance(prior_addresses, list) and prior_addresses else None
    if isinstance(first_prior, dict) and _value_is_answered(first_prior) and not _is_non_us_address(first_prior):
        required_ids.add("beneficiary_recent_foreign_address")
    return required_ids


def conditional_required_i485_question_ids(answers: dict[str, Any]) -> set[str]:
    return _conditional_required_question_ids(answers)


def _risk_matches(value: Any, risk_when: Any) -> bool:
    if risk_when is None:
        return False
    if risk_when == "present":
        return _value_is_answered(value)
    if risk_when == "not_1":
        try:
            return int(value) != 1
        except (TypeError, ValueError):
            return _value_is_answered(value)
    if risk_when == "greater_than_0":
        try:
            return int(value) > 0
        except (TypeError, ValueError):
            return False
    if risk_when == "not_married":
        return _value_is_answered(value) and value != "married"
    if risk_when == "not_us_citizen":
        return _value_is_answered(value) and value != "us_citizen"
    if risk_when == "other":
        return _value_is_answered(value) and value not in {
            "spouse_us_citizen",
            "not_requesting_exemption",
            "not_exempt_complete_questions",
        }
    return value == risk_when


def evaluate_i485_answers(answers: dict[str, Any]) -> dict[str, Any]:
    config = QuestionnaireEvaluationConfig(
        form_key="i485",
        ready_readiness="ready_for_standard_i485_review",
        questions=all_i485_questions(),
        pages=I485_QUESTIONNAIRE,
        blocking_risk_codes=BLOCKING_RISK_CODES,
        outside_niche_risk_codes=OUTSIDE_NICHE_RISK_CODES,
        value_is_answered=_value_is_answered,
        risk_matches=_risk_matches,
        risk_title=lambda question: "Answer needs review before using the standard I-485 flow",
        risk_description=lambda question: (
            f"The answer to '{question['label']}' is outside the expected first-marriage, "
            "U.S.-citizen-spouse, no-criminal-history profile."
        ),
        conditional_required_ids=_conditional_required_question_ids,
    )
    return QuestionnaireRuleEngine().evaluate(answers, config)


def get_i485_state(session: Session, case_id: UUID) -> dict[str, Any]:
    steps = get_i485_steps(session, case_id)
    answers = merge_i485_answers(steps)
    return {
        "case_id": str(case_id),
        "answers": answers,
        "answer_sources": merge_i485_answer_sources(steps),
        "manual_flags": merge_i485_manual_flags(steps),
        "evaluation": evaluate_i485_answers(answers),
        "saved_pages": [step.payload.get("page_id") for step in steps if step.payload.get("page_id")],
    }


def _proposal(
    question_id: str,
    value: Any,
    source_field: str,
    upload: UploadedDocument,
    confidence: float,
) -> dict[str, Any] | None:
    if question_id not in QUESTION_BY_ID or value in (None, "", [], {}):
        return None
    question = QUESTION_BY_ID[question_id]
    value = _normalize_i485_answer(question_id, value)
    return {
        "question_id": question_id,
        "page_id": PAGE_BY_QUESTION_ID[question_id],
        "label": question["label"],
        "value": value,
        "source_field": source_field,
        "source_upload_id": str(upload.id),
        "source_filename": upload.original_filename,
        "confidence": confidence,
        "pdf_ref": question["pdf_ref"],
    }


def build_i485_answer_proposals_from_upload(upload: UploadedDocument) -> list[dict[str, Any]]:
    fields = upload.extracted_fields or {}
    confidence = upload.extraction_confidence or 0.0
    proposals: list[dict[str, Any]] = []
    for source_field, question_id in I485_EXTRACTED_FIELD_TO_QUESTION_ID.items():
        proposal = _proposal(question_id, fields.get(source_field), source_field, upload, confidence)
        if proposal:
            proposals.append(proposal)

    if fields.get("beneficiary_entered_us_legally") is True:
        proposal = _proposal("beneficiary_last_arrival_type", "admitted", "beneficiary_entered_us_legally", upload, confidence)
        if proposal:
            proposals.append(proposal)
    elif fields.get("beneficiary_entered_us_legally") is False:
        proposal = _proposal(
            "beneficiary_last_arrival_type",
            "without_admission",
            "beneficiary_entered_us_legally",
            upload,
            confidence,
        )
        if proposal:
            proposals.append(proposal)

    if fields.get("beneficiary_first_marriage_detected") is True:
        proposal = _proposal("beneficiary_marriage_count", 1, "beneficiary_first_marriage_detected", upload, confidence)
        if proposal:
            proposals.append(proposal)

    if fields.get("beneficiary_prior_address_history"):
        proposal = _proposal(
            "beneficiary_current_address_five_years",
            False,
            "beneficiary_prior_address_history",
            upload,
            confidence,
        )
        if proposal:
            proposals.append(proposal)

    return proposals


def _case_data_proposal(question_id: str, value: Any, source_field: str) -> dict[str, Any] | None:
    if question_id not in QUESTION_BY_ID or not _value_is_answered(value):
        return None
    question = QUESTION_BY_ID[question_id]
    return {
        "question_id": question_id,
        "page_id": PAGE_BY_QUESTION_ID[question_id],
        "label": question["label"],
        "value": _normalize_i485_answer(question_id, value),
        "source_field": source_field,
        "confidence": 1.0,
        "pdf_ref": question["pdf_ref"],
    }


def build_i485_answer_proposals_from_case_data(merged: dict[str, Any]) -> list[dict[str, Any]]:
    merged = enrich_case_fact_aliases(merged)
    proposals: list[dict[str, Any]] = []

    for question in all_i485_questions():
        db_path = question.get("db_path")
        if not isinstance(db_path, str) or not db_path.startswith("intake."):
            continue
        source_field = db_path.removeprefix("intake.")
        proposal = _case_data_proposal(question["id"], merged.get(source_field), source_field)
        if proposal:
            proposals.append(proposal)

    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for proposal in proposals:
        question_id = proposal["question_id"]
        if question_id in seen:
            continue
        seen.add(question_id)
        deduped.append(proposal)
    return deduped


def _latest_i485_upload(
    session: Session,
    case_id: UUID,
    upload_id: UUID | None,
) -> UploadedDocument:
    if upload_id:
        upload = session.get(UploadedDocument, upload_id)
        if not upload or upload.case_id != case_id:
            raise ValueError("I-485 upload not found for this case")
        if upload.checklist_item_code != "form_i485" and upload.document_type != "form_i485":
            raise ValueError("Selected upload is not marked as Form I-485")
        return upload

    upload = session.exec(
        select(UploadedDocument)
        .where(
            UploadedDocument.case_id == case_id,
            UploadedDocument.upload_status == "confirmed",
            UploadedDocument.checklist_item_code == "form_i485",
        )
        .order_by(UploadedDocument.updated_at.desc())
    ).first()
    if upload:
        return upload

    upload = session.exec(
        select(UploadedDocument)
        .where(
            UploadedDocument.case_id == case_id,
            UploadedDocument.upload_status == "confirmed",
            UploadedDocument.document_type == "form_i485",
        )
        .order_by(UploadedDocument.updated_at.desc())
    ).first()
    if not upload:
        raise ValueError("No confirmed I-485 upload was found for this case")
    return upload


def _refresh_upload_extraction_if_needed(upload: UploadedDocument) -> None:
    fields = upload.extracted_fields or {}
    if fields:
        return
    if not upload.stored_filename:
        return
    path = Path(settings.upload_dir / upload.stored_filename)
    if not path.exists() or path.suffix.lower() != ".pdf":
        return

    from app.services.ingestion import scan_document

    inferred = scan_document(path)
    upload.extracted_fields = inferred.extracted_fields
    upload.extraction_confidence = max(upload.extraction_confidence, inferred.text and 0.75 or 0.4)
    upload.ocr_status = OCRStatus.complete.value
    upload.document_type = inferred.document_type
    upload.document_language = inferred.document_language
    upload.requires_translation = inferred.requires_translation
    upload.has_translation = inferred.has_translation
    upload.updated_at = _utcnow()


def _store_i485_imported_answers(
    session: Session,
    case_id: UUID,
    proposals: list[dict[str, Any]],
    source_for_proposal: Callable[[dict[str, Any]], dict[str, Any]],
    overwrite: bool,
) -> tuple[dict[str, Any], set[str], set[str]]:
    state = get_i485_state(session, case_id)
    answers = dict(state["answers"])
    imported_question_ids: set[str] = set()
    skipped_question_ids: set[str] = set()

    page_answers: dict[str, dict[str, Any]] = {}
    page_sources: dict[str, dict[str, Any]] = {}
    for proposal in proposals:
        question_id = proposal["question_id"]
        if not overwrite and _value_is_answered(answers.get(question_id)):
            skipped_question_ids.add(question_id)
            continue
        answers[question_id] = proposal["value"]
        imported_question_ids.add(question_id)
        source = source_for_proposal(proposal)
        page_id = PAGE_BY_QUESTION_ID[question_id]
        page_answers.setdefault(page_id, {})[question_id] = answers[question_id]
        page_sources.setdefault(page_id, {})[question_id] = source

    for page_id, imported_answers in page_answers.items():
        step_key = i485_step_key(page_id)
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
            "page_id": page_id,
            "answers": {**existing_answers, **imported_answers},
            "answer_sources": {**existing_sources, **page_sources[page_id]},
            "manual_flags": existing_manual_flags,
        }
        if step:
            step.payload = payload
            step.updated_at = _utcnow()
        else:
            session.add(IntakeResponse(case_id=case_id, step_key=step_key, payload=payload))
    session.flush()

    refreshed_state = get_i485_state(session, case_id)
    projection = build_i485_intake_projection(refreshed_state["answers"])
    upsert_intake_step(session, case_id, I485_PROJECTION_STEP, projection)
    apply_case_projection(session, case_id, get_merged_case_intake(session, case_id))

    return get_i485_state(session, case_id), imported_question_ids, skipped_question_ids


def import_i485_answers_from_upload(
    session: Session,
    case_id: UUID,
    upload_id: UUID | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    upload = _latest_i485_upload(session, case_id, upload_id)
    _refresh_upload_extraction_if_needed(upload)
    session.add(upload)
    session.flush()

    proposals = build_i485_answer_proposals_from_upload(upload)
    state, imported_question_ids, skipped_question_ids = _store_i485_imported_answers(
        session,
        case_id,
        proposals,
        lambda proposal: {
            "source_type": "pdf_upload",
            "upload_id": proposal["source_upload_id"],
            "filename": proposal["source_filename"],
            "source_field": proposal["source_field"],
            "confidence": proposal["confidence"],
            "updated_at": _utcnow().isoformat(),
        },
        overwrite,
    )

    return {
        "state": state,
        "proposals": proposals,
        "imported_count": len(imported_question_ids),
        "skipped_count": len(skipped_question_ids),
        "upload_id": str(upload.id),
    }


def import_i485_answers_from_case_data(
    session: Session,
    case_id: UUID,
    overwrite: bool = False,
) -> dict[str, Any]:
    proposals = build_i485_answer_proposals_from_case_data(get_merged_case_intake(session, case_id))
    state, imported_question_ids, skipped_question_ids = _store_i485_imported_answers(
        session,
        case_id,
        proposals,
        lambda proposal: {
            "source_type": "case_intake",
            "source_field": proposal["source_field"],
            "confidence": proposal["confidence"],
            "updated_at": _utcnow().isoformat(),
        },
        overwrite,
    )
    return {
        "state": state,
        "proposals": proposals,
        "imported_count": len(imported_question_ids),
        "skipped_count": len(skipped_question_ids),
    }


def build_i485_form_fill_preview(session: Session, case_id: UUID) -> dict[str, Any]:
    state = get_i485_state(session, case_id)
    answers = state["answers"]
    answer_sources = state["answer_sources"]
    evaluation = state["evaluation"]

    fields: list[dict[str, Any]] = []
    missing_required: list[dict[str, Any]] = []
    low_confidence_fields: list[dict[str, Any]] = []
    conditional_required_ids = _conditional_required_question_ids(answers)
    for page in I485_QUESTIONNAIRE:
        for question in page["questions"]:
            question_id = question["id"]
            value = answers.get(question_id)
            if not _value_is_answered(value):
                if question.get("required") or question_id in conditional_required_ids:
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
                "target_key": f"form_i485.{question_id}",
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
        "generation_status": generation_status,
        "ready_for_pdf_generation": generation_status == "ready_for_user_review",
        "questionnaire_version": I485_QUESTIONNAIRE_VERSION,
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
            "Review every PDF-extracted value before using it for form fill.",
            "Manually answer I-485 inadmissibility yes/no questions; flattened PDFs may not expose checkbox selections reliably.",
            "Do not present the case as a standard first-marriage U.S.-citizen-spouse flow while blocking or outside-niche flags remain.",
        ],
    }
