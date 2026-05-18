from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from sqlmodel import Session

from app.services.filing_validators.shared import *


class I485FilingValidator:
    form_code = "form_i485"

    def validate(self, session: Session, case_id: UUID, template_path: Path | None) -> dict[str, Any]:
        state = get_i485_state(session, case_id)
        answers = state["answers"]
        answer_sources = state["answer_sources"]
        preview = build_i485_form_fill_preview(session, case_id)
        evaluation = evaluate_i485_answers(answers)
        merged = get_merged_case_intake(session, case_id)
        template_fields, template_error = _template_field_names(template_path)
        payload = build_i485_pdf_field_payload(answers, template_fields)

        issues: list[dict[str, Any]] = []
        if template_error:
            issues.append(
                _issue(
                    form_code="form_i485",
                    severity="important",
                    code="form_i485_template_unavailable",
                    title="I-485 template could not be inspected",
                    description=(
                        "The validator could not inspect the selected blank I-485 PDF, so PDF field-name coverage "
                        "could not be confirmed."
                    ),
                    source="blank_pdf_template",
                    actual=template_error,
                )
            )

        for missing in preview["missing_required"]:
            question_id = missing["question_id"]
            issues.append(
                _issue(
                    form_code="form_i485",
                    severity="blocking",
                    code=f"form_i485_{question_id}_missing_required",
                    title="Required I-485 answer is missing",
                    description=(
                        f"'{missing['label']}' is required in the current I-485 questionnaire map before this "
                        "record should be used for filing review or PDF generation."
                    ),
                    source="i485_questionnaire",
                    field_key=f"form_i485.{question_id}",
                    question_id=question_id,
                    pdf_ref=missing["pdf_ref"],
                )
            )

        for flag in evaluation["flags"]:
            severity = "blocking" if flag["severity"] == "blocking" else "important"
            issues.append(
                _issue(
                    form_code="form_i485",
                    severity=severity,
                    code=f"form_i485_{flag['code']}",
                    title=flag["title"],
                    description=flag["description"],
                    source="i485_questionnaire",
                    field_key=f"form_i485.{flag['question_id']}",
                    question_id=flag["question_id"],
                    pdf_ref=flag["pdf_ref"],
                )
            )

        for field in preview["low_confidence_fields"]:
            issues.append(
                _issue(
                    form_code="form_i485",
                    severity="important",
                    code=f"form_i485_{field['question_id']}_low_confidence",
                    title="PDF-extracted I-485 value needs review",
                    description=(
                        f"'{field['label']}' came from a lower-confidence extraction. Confirm the value against "
                        "the source document before treating it as filing-ready."
                    ),
                    source="answer_provenance",
                    field_key=field["target_key"],
                    question_id=field["question_id"],
                    pdf_ref=field["pdf_ref"],
                    actual=field["value"],
                )
            )

        if payload.missing_template_fields:
            issues.append(
                _issue(
                    form_code="form_i485",
                    severity="important",
                    code="form_i485_template_field_mismatch",
                    title="Mapped I-485 PDF fields are absent from the selected template",
                    description=(
                        "Some answered fields map to PDF field names that are not present in the selected blank "
                        "template. Regenerate the field map before relying on automated fill output."
                    ),
                    source="blank_pdf_template",
                    pdf_fields=payload.missing_template_fields,
                )
            )

        mapped_answered_required_ids = {
            entry["question_id"]
            for entry in payload.mapped_questions
            if _value_is_answered(answers.get(entry["question_id"]))
        }
        for question in all_i485_questions():
            question_id = question["id"]
            if not question.get("required") or not _value_is_answered(answers.get(question_id)):
                continue
            if question_id in mapped_answered_required_ids:
                continue
            issues.append(
                _issue(
                    form_code="form_i485",
                    severity="recommended",
                    code=f"form_i485_{question_id}_unmapped_pdf_field",
                    title="Answered I-485 field is not mapped to the PDF yet",
                    description=(
                        f"'{question['label']}' has an answer, but the current PDF fill map does not yet point "
                        "to a concrete blank-form field. A human should verify that answer on the final PDF."
                    ),
                    source="pdf_field_map",
                    field_key=f"form_i485.{question_id}",
                    question_id=question_id,
                    pdf_ref=question["pdf_ref"],
                )
            )

        current_since = _parse_iso_date(
            answers.get("beneficiary_address_since") or merged.get("beneficiary_current_address_since")
        )
        if current_since and current_since > _subtract_years(date.today(), 5):
            if not _value_is_answered(answers.get("beneficiary_prior_address_history")) and not _value_is_answered(
                merged.get("beneficiary_prior_address_history")
            ):
                issues.append(
                    _issue(
                        form_code="form_i485",
                        severity="blocking",
                        code="form_i485_five_year_address_history_missing",
                        title="Five-year address history is incomplete",
                        description=(
                            f"The current address starts on {current_since.isoformat()}, which is less than five "
                            "years ago, but no prior address history is saved for I-485 review."
                        ),
                        source="record_consistency",
                        field_key="beneficiary_prior_address_history",
                        question_id="beneficiary_prior_address_history",
                        pdf_ref=I485_QUESTION_BY_ID["beneficiary_prior_address_history"]["pdf_ref"],
                    )
                )

        for question in all_i485_questions():
            db_path = question.get("db_path")
            if not isinstance(db_path, str) or not db_path.startswith("intake."):
                continue
            intake_key = db_path.removeprefix("intake.")
            answer_value = answers.get(question["id"])
            intake_value = merged.get(intake_key)
            if not _value_is_answered(answer_value) or not _value_is_answered(intake_value):
                continue
            if _normalize_scalar(answer_value) == _normalize_scalar(intake_value):
                continue
            issues.append(
                _issue(
                    form_code="form_i485",
                    severity="important",
                    code=f"form_i485_{question['id']}_source_of_truth_mismatch",
                    title="I-485 answer differs from the case source of truth",
                    description=(
                        f"The I-485 answer for '{question['label']}' does not match the current case record. "
                        "Review which value should control before generating or filing the form."
                    ),
                    source="record_consistency",
                    field_key=intake_key,
                    question_id=question["id"],
                    pdf_ref=question["pdf_ref"],
                    expected=intake_value,
                    actual=answer_value,
                )
            )

        return _form_result(
            form_code="form_i485",
            issues=issues,
            field_count=preview["field_count"],
            required_field_count=evaluation["required_questions"],
            template_field_count=len(template_fields),
            template_path=template_path,
            metadata={
                "generation_status": preview["generation_status"],
                "ready_for_pdf_generation": preview["ready_for_pdf_generation"],
                "answered_required": evaluation["answered_required"],
                "mapped_pdf_field_count": len(payload.text_values) + len(payload.checkbox_values),
                "answer_source_count": len(answer_sources),
            },
        )
