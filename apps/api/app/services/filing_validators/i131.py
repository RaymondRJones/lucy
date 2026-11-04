"""Filing validator for Form I-131."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from sqlmodel import Session

from app.content.supplemental_forms import get_supplemental_form_config
from app.models.entities import UploadedDocument
from app.services.case_facts import value_is_answered
from app.services.filing_validators.shared import (
    append_cross_form_mismatch_issues,
    append_state_country_mismatch_issues,
    append_uploaded_document_mismatch_issues,
    build_issue,
    confirmed_uploads,
    form_result,
    inspect_template_fields,
    intake_with_form_gaps_filled,
    template_unavailable_issue,
    valid_positive_integer,
)
from app.services.form_ingestion import build_form_fill_preview, get_form_state
from app.services.form_pdf import FormPdfFieldPayload, build_form_pdf_field_payload
from app.services.i485 import get_i485_state
from app.services.intake import derive_case_facts


def _check_i131_template_fields(*, issues: list[dict[str, Any]], pdf_payload: FormPdfFieldPayload) -> None:
    if pdf_payload.missing_template_fields:
        issues.append(
            build_issue(
                form_code="form_i131",
                severity="important",
                code="form_i131_template_field_mismatch",
                title="Mapped I-131 PDF fields are absent from the selected template",
                description=(
                    "Some answered I-131 fields map to PDF field names that are not present in the selected "
                    "blank template. Review the I-131 field map before relying on automated fill output."
                ),
                source="blank_pdf_template",
                pdf_fields=pdf_payload.missing_template_fields,
            )
        )


def _check_i131_filing_path(*, facts: dict[str, Any], issues: list[dict[str, Any]], values: dict[str, Any]) -> None:
    if not facts["concurrent_filing_eligible"]:
        issues.append(
            build_issue(
                form_code="form_i131",
                severity="blocking",
                code="form_i131_not_standard_concurrent_advance_parole_path",
                title="I-131 is outside the standard concurrent adjustment path",
                description=(
                    "This validator only covers the simple advance parole path for a beneficiary filing Form "
                    "I-131 with, or based on, a pending Form I-485 as the spouse of a U.S. citizen."
                ),
                source="case_intake",
                field_key="wants_i131",
            )
        )

    if value_is_answered(values.get("i131_application_type")) and values.get("i131_application_type") != "advanced_parole_i485_pending":
        issues.append(
            build_issue(
                form_code="form_i131",
                severity="blocking",
                code="form_i131_application_type_not_i485_advance_parole",
                title="I-131 application type is outside the supported path",
                description="This validator expects the pending-I-485 advance parole selection.",
                source="form_i131_questionnaire",
                field_key="i131_application_type",
                question_id="i131_application_type",
                pdf_ref="Part 1, Item 5.A",
                expected="advanced_parole_i485_pending",
                actual=values.get("i131_application_type"),
            )
        )


def _check_i131_required_fields(
    *,
    issues: list[dict[str, Any]],
    values: dict[str, Any],
) -> dict[str, str]:
    required_fields = {
        "beneficiary_first_name": "Beneficiary given name",
        "beneficiary_last_name": "Beneficiary family name",
        "beneficiary_date_of_birth": "Beneficiary date of birth",
        "beneficiary_country_of_birth": "Beneficiary country of birth",
        "beneficiary_country_of_citizenship": "Beneficiary country of citizenship",
        "beneficiary_class_of_admission": "Beneficiary class of admission",
        "beneficiary_i94_number": "Most recent I-94 number",
        "i131_intended_departure_date": "Intended departure date",
        "i131_travel_purpose": "Purpose of trip",
        "i131_countries_to_visit": "Countries to visit",
        "i131_expected_trip_length": "Expected length of trip in days",
    }
    for field_key, label in required_fields.items():
        if value_is_answered(values.get(field_key)):
            continue
        issues.append(
            build_issue(
                form_code="form_i131",
                severity="blocking",
                code=f"form_i131_{field_key}_missing_required",
                title="Required I-131 fact is missing",
                description=f"{label} is missing from the case record or I-131 questionnaire for preflight review.",
                source="case_intake",
                field_key=field_key,
            )
        )

    if value_is_answered(values.get("i131_expected_trip_length")) and not valid_positive_integer(
        values.get("i131_expected_trip_length")
    ):
        issues.append(
            build_issue(
                form_code="form_i131",
                severity="blocking",
                code="form_i131_expected_trip_length_not_days",
                title="I-131 expected trip length must be a whole number of days",
                description="Enter the expected trip length as a whole number of days, for example 14 for a two-week trip.",
                source="form_i131_questionnaire",
                field_key="i131_expected_trip_length",
                question_id="i131_expected_trip_length",
                pdf_ref="Part 7, Item 5",
                actual=values.get("i131_expected_trip_length"),
            )
        )
    return required_fields


def _check_i131_address_and_prior_documents(
    *,
    issues: list[dict[str, Any]],
    values: dict[str, Any],
) -> bool:
    has_structured_address = all(
        value_is_answered(values.get(key))
        for key in (
            "beneficiary_current_address_line1",
            "beneficiary_current_city",
            "beneficiary_current_state",
            "beneficiary_current_zip",
        )
    ) or all(
        value_is_answered(values.get(key))
        for key in (
            "beneficiary_mailing_address_line1",
            "beneficiary_mailing_city",
            "beneficiary_mailing_state",
            "beneficiary_mailing_zip",
        )
    )
    if not has_structured_address and not value_is_answered(values.get("beneficiary_current_address")):
        issues.append(
            build_issue(
                form_code="form_i131",
                severity="blocking",
                code="form_i131_current_address_missing_required",
                title="Beneficiary current address is missing",
                description="A current U.S. mailing or physical address is needed before I-131 review.",
                source="case_intake",
                field_key="beneficiary_current_address",
            )
        )

    for field_key, question_id, title in (
        ("i131_removal_proceedings", "i131_removal_proceedings", "Removal or rescission proceedings need review"),
        ("i131_prior_reentry_refugee_document", "i131_prior_reentry_refugee_document", "Prior travel document history needs review"),
        ("i131_replacement_request", "i131_replacement_request", "Replacement request needs review"),
    ):
        if values.get(field_key) is not True:
            continue
        issues.append(
            build_issue(
                form_code="form_i131",
                severity="important",
                code=f"form_i131_{field_key}_review",
                title=title,
                description=(
                    "The saved I-131 answer may require additional facts or evidence before relying on the "
                    "standard first-marriage concurrent-filing packet workflow."
                ),
                source="form_i131_questionnaire",
                field_key=field_key,
                question_id=question_id,
            )
        )
    return has_structured_address


def _check_i131_supporting_evidence(
    *,
    case_id: UUID,
    session: Session,
    issues: list[dict[str, Any]],
    uploads: list[UploadedDocument],
) -> None:
    upload_codes = {upload.checklist_item_code for upload in uploads}
    supporting_evidence = {
        "beneficiary_passport_bio": "Official photo identity document, such as a passport identity page",
        "beneficiary_i94": "Current status or I-94 evidence",
        "beneficiary_passport_photos": "Two passport-style photos",
        "travel_explanation_i131": "Travel explanation and supporting evidence",
    }
    for checklist_code, label in supporting_evidence.items():
        if checklist_code in upload_codes:
            continue
        issues.append(
            build_issue(
                form_code="form_i131",
                severity="blocking",
                code=f"form_i131_{checklist_code}_evidence_missing_required",
                title="Required I-131 supporting evidence is missing",
                description=f"{label} is not confirmed in uploads for I-131 preflight review.",
                source="case_intake",
                field_key=checklist_code,
            )
        )

    if "form_i485" not in upload_codes and not get_i485_state(session, case_id)["answers"]:
        issues.append(
            build_issue(
                form_code="form_i131",
                severity="important",
                code="form_i131_underlying_i485_not_confirmed",
                title="Underlying I-485 basis is not confirmed for I-131",
                description=(
                    "On the standard path, I-131 is expected to rely on a concurrent or pending Form I-485. "
                    "Confirm the I-485 draft or upload before treating I-131 as ready."
                ),
                source="case_intake",
                field_key="form_i485",
            )
        )


def _check_i131_cross_form_mismatches(
    *,
    case_id: UUID,
    session: Session,
    issues: list[dict[str, Any]],
    uploads: list[UploadedDocument],
    values: dict[str, Any],
) -> None:
    append_state_country_mismatch_issues(issues=issues, form_code="form_i131", answers=values)
    i485_answers = get_i485_state(session, case_id)["answers"]
    append_cross_form_mismatch_issues(
        issues=issues,
        form_code="form_i131",
        other_form_label="Form I-485",
        current_values=values,
        other_values=i485_answers,
        field_labels={
            "beneficiary_a_number": "Beneficiary A-number",
            "beneficiary_first_name": "Beneficiary given name",
            "beneficiary_last_name": "Beneficiary family name",
            "beneficiary_middle_name": "Beneficiary middle name",
            "beneficiary_date_of_birth": "Beneficiary date of birth",
            "beneficiary_country_of_birth": "Beneficiary country of birth",
            "beneficiary_country_of_citizenship": "Beneficiary country of citizenship",
            "beneficiary_i94_number": "Beneficiary I-94 number",
            "beneficiary_class_of_admission": "Beneficiary class of admission",
        },
    )
    append_uploaded_document_mismatch_issues(
        issues=issues,
        form_code="form_i131",
        uploads=uploads,
        checklist_codes={"form_i131"},
        current_values=values,
        field_labels={
            "beneficiary_first_name": "Beneficiary given name",
            "beneficiary_last_name": "Beneficiary family name",
            "beneficiary_date_of_birth": "Beneficiary date of birth",
            "beneficiary_country_of_birth": "Beneficiary country of birth",
            "beneficiary_i94_number": "Beneficiary I-94 number",
        },
    )


class I131FilingValidator:
    form_code = "form_i131"

    def validate(self, session: Session, case_id: UUID, template_path: Path | None) -> dict[str, Any]:
        merged = intake_with_form_gaps_filled(session, case_id, "i131")
        facts = derive_case_facts(merged)
        uploads = confirmed_uploads(session, case_id)
        state = get_form_state(session, case_id, "i131")
        answers = state["answers"]
        values = {**merged, **answers}
        preview = build_form_fill_preview(session, case_id, "i131")
        template_fields, template_error = inspect_template_fields(template_path)
        pdf_payload = build_form_pdf_field_payload("i131", answers, template_fields)
        issues: list[dict[str, Any]] = []

        if template_error:
            issues.append(template_unavailable_issue("form_i131", "I-131", template_error))
        _check_i131_template_fields(issues=issues, pdf_payload=pdf_payload)

        _check_i131_filing_path(facts=facts, issues=issues, values=values)

        required_fields = _check_i131_required_fields(issues=issues, values=values)

        has_structured_address = _check_i131_address_and_prior_documents(issues=issues, values=values)

        _check_i131_supporting_evidence(case_id=case_id, session=session, issues=issues, uploads=uploads)

        _check_i131_cross_form_mismatches(
            case_id=case_id,
            session=session,
            issues=issues,
            uploads=uploads,
            values=values,
        )

        answered_count = sum(1 for field_key in required_fields if value_is_answered(values.get(field_key)))
        if has_structured_address or value_is_answered(values.get("beneficiary_current_address")):
            answered_count += 1
        return form_result(
            form_code="form_i131",
            issues=issues,
            field_count=answered_count,
            required_field_count=len(required_fields) + 1,
            template_field_count=len(template_fields),
            template_path=template_path,
            metadata={
                "validator_level": "advance_parole_i485_preflight",
                "note": "Checks core I-131 advance parole facts, tracked supporting evidence, and first-pass PDF fill payload coverage.",
                "questionnaire_version": get_supplemental_form_config("i131")["version"],
                "generation_status": preview["generation_status"],
                "ready_for_pdf_generation": preview["ready_for_pdf_generation"],
                "mapped_pdf_field_count": len(pdf_payload.text_values) + len(pdf_payload.checkbox_values),
                "mapped_pdf_fields": [
                    field_name
                    for entry in pdf_payload.mapped_questions
                    for field_name in entry["pdf_fields"]
                ],
                "missing_template_fields": pdf_payload.missing_template_fields,
                "pdf_text_field_count": len(pdf_payload.text_values),
                "pdf_checkbox_field_count": len(pdf_payload.checkbox_values),
                "answered_required": state["evaluation"]["answered_required"],
            },
        )
