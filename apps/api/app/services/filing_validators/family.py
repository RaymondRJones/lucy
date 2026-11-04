from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from sqlmodel import Session

from app.services.filing_validators.shared import *


class I130FilingValidator:
    form_code = "form_i130"

    def validate(self, session: Session, case_id: UUID, template_path: Path | None) -> dict[str, Any]:
        merged = get_merged_case_intake(session, case_id)
        facts = derive_case_facts(merged)
        uploads = _confirmed_uploads(session, case_id)
        template_fields, template_error = _template_field_names(template_path) if template_path else (set(), None)
        payload_values = {
            **merged,
            "relationship_spouse": "spouse",
            "beneficiary_adjustment_path": (
                merged.get("beneficiary_adjustment_path")
                if "beneficiary_adjustment_path" in merged
                else str(merged.get("beneficiary_location", "usa")).strip().lower() in {"usa", "us", "united states"}
            ),
        }
        pdf_payload = build_i130_pdf_field_payload(payload_values, template_fields)
        issues: list[dict[str, Any]] = []

        if i130_class_of_admission_not_offered(merged):
            issues.append(
                _issue(
                    form_code="form_i130",
                    severity="important",
                    code="form_i130_class_of_admission_not_offered",
                    title="Class of admission must be chosen by hand",
                    description=I130_CLASS_NOT_OFFERED_WARNING,
                    source="blank_pdf_template",
                    field_key="beneficiary_class_of_admission",
                    question_id="beneficiary_class_of_admission",
                    pdf_ref="Part 4, Item 21.a",
                    actual=merged.get("beneficiary_class_of_admission"),
                )
            )
        if template_error:
            issues.append(
                _issue(
                    form_code="form_i130",
                    severity="important",
                    code="form_i130_template_unavailable",
                    title="I-130 template could not be inspected",
                    description="The validator could not inspect the selected blank I-130 PDF.",
                    source="blank_pdf_template",
                    actual=template_error,
                )
            )
        if pdf_payload.missing_template_fields:
            issues.append(
                _issue(
                    form_code="form_i130",
                    severity="important",
                    code="form_i130_template_field_mismatch",
                    title="Mapped I-130 PDF fields are absent from the selected template",
                    description=(
                        "Some core I-130 case fields map to PDF field names that are not present in the selected "
                        "blank template. Regenerate or review the I-130 field map before relying on automated fill output."
                    ),
                    source="blank_pdf_template",
                    pdf_fields=pdf_payload.missing_template_fields,
                )
            )

        if not facts["petitioner_is_us_citizen"]:
            issues.append(
                _issue(
                    form_code="form_i130",
                    severity="blocking",
                    code="form_i130_petitioner_not_us_citizen_standard_path",
                    title="Petitioner is outside the U.S.-citizen spouse path",
                    description=(
                        "This validator is scoped to a simple marriage case where the petitioner is a U.S. citizen."
                    ),
                    source="case_intake",
                    field_key="petitioner_citizenship_status",
                    expected="us_citizen",
                    actual=merged.get("petitioner_citizenship_status"),
                )
            )

        required_questions = required_family_questions("form_i130")
        _append_missing_required_question_issues(
            issues=issues,
            form_code="form_i130",
            values=payload_values,
            questions=required_questions,
            title="Required I-130 fact is missing",
            description_suffix="from the case record for source-dated I-130 preflight review.",
        )

        has_structured_beneficiary_address = all(
            _value_is_answered(merged.get(key))
            for key in (
                "beneficiary_current_address_line1",
                "beneficiary_current_city",
                "beneficiary_current_state",
                "beneficiary_current_zip",
            )
        )
        if not has_structured_beneficiary_address and not _value_is_answered(merged.get("beneficiary_current_address")):
            issues.append(
                _issue(
                    form_code="form_i130",
                    severity="blocking",
                    code="form_i130_beneficiary_current_address_missing_required",
                    title="Beneficiary physical address is missing",
                    description="Beneficiary physical address is needed for source-dated I-130 preflight review.",
                    source="case_intake",
                    field_key="beneficiary_current_address",
                    question_id="beneficiary_current_address",
                    pdf_ref=I130_QUESTION_BY_ID["beneficiary_current_address"]["pdf_ref"],
                )
            )

        if payload_values["beneficiary_adjustment_path"] is not True:
            issues.append(
                _issue(
                    form_code="form_i130",
                    severity="blocking",
                    code="form_i130_adjustment_path_not_confirmed",
                    title="I-130 adjustment-of-status path is not confirmed",
                    description=(
                        "This validator is scoped to a concurrent adjustment packet and expects Part 4 to select "
                        "adjustment of status inside the United States, not consular processing abroad."
                    ),
                    source="case_intake",
                    field_key="beneficiary_adjustment_path",
                    question_id="beneficiary_adjustment_path",
                    pdf_ref=I130_QUESTION_BY_ID["beneficiary_adjustment_path"]["pdf_ref"],
                    expected=True,
                    actual=payload_values["beneficiary_adjustment_path"],
                )
            )

        if merged.get("first_marriage_for_both") is not True:
            severity = "blocking" if _value_is_answered(merged.get("first_marriage_for_both")) else "important"
            issues.append(
                _issue(
                    form_code="form_i130",
                    severity=severity,
                    code="form_i130_first_marriage_not_confirmed",
                    title="First-marriage assumption is not confirmed",
                    description=(
                        "This validator is scoped to first-marriage cases. If either spouse had a prior marriage, "
                        "the packet needs prior-marriage termination records and additional review."
                    ),
                    source="case_intake",
                    field_key="first_marriage_for_both",
                    expected=True,
                    actual=merged.get("first_marriage_for_both"),
                )
            )

        upload_codes = {upload.checklist_item_code for upload in uploads}
        evidence = {
            "petitioner_citizenship_proof": "Petitioner proof of U.S. citizenship",
            "marriage_certificate": "Marriage certificate",
        }
        for checklist_code, label in evidence.items():
            if checklist_code in upload_codes:
                continue
            issues.append(
                _issue(
                    form_code="form_i130",
                    severity="blocking",
                    code=f"form_i130_{checklist_code}_evidence_missing_required",
                    title="Required I-130 supporting evidence is missing",
                    description=f"{label} is not confirmed in uploads for I-130 preflight review.",
                    source="case_intake",
                    field_key=checklist_code,
                )
            )

        if merged.get("first_marriage_for_both") is False and "prior_marriage_termination_records" not in upload_codes:
            issues.append(
                _issue(
                    form_code="form_i130",
                    severity="blocking",
                    code="form_i130_prior_marriage_termination_evidence_missing_required",
                    title="Prior-marriage termination evidence is missing",
                    description=(
                        "The case says this is not a first marriage for both spouses, but no prior-marriage "
                        "termination evidence is confirmed in uploads."
                    ),
                    source="case_intake",
                    field_key="prior_marriage_termination_records",
                )
            )

        i485_answers = get_i485_state(session, case_id)["answers"]
        _append_cross_form_mismatch_issues(
            issues=issues,
            form_code="form_i130",
            other_form_label="Form I-485",
            current_values=merged,
            other_values=i485_answers,
            field_labels={
                "petitioner_first_name": "Petitioner given name",
                "petitioner_last_name": "Petitioner family name",
                "beneficiary_a_number": "Beneficiary A-number",
                "beneficiary_first_name": "Beneficiary given name",
                "beneficiary_last_name": "Beneficiary family name",
                "beneficiary_date_of_birth": "Beneficiary date of birth",
                "beneficiary_country_of_birth": "Beneficiary country of birth",
                "marriage_date": "Marriage date",
                "beneficiary_current_address_line1": "Beneficiary street address",
                "beneficiary_current_city": "Beneficiary city",
                "beneficiary_current_state": "Beneficiary state",
                "beneficiary_current_zip": "Beneficiary ZIP code",
            },
        )
        _append_uploaded_document_mismatch_issues(
            issues=issues,
            form_code="form_i130",
            uploads=uploads,
            checklist_codes={"form_i130"},
            current_values=merged,
            field_labels={
                "petitioner_first_name": "Petitioner given name",
                "petitioner_last_name": "Petitioner family name",
                "beneficiary_a_number": "Beneficiary A-number",
                "beneficiary_first_name": "Beneficiary given name",
                "beneficiary_last_name": "Beneficiary family name",
                "beneficiary_date_of_birth": "Beneficiary date of birth",
                "beneficiary_country_of_birth": "Beneficiary country of birth",
                "marriage_date": "Marriage date",
            },
        )

        answered_count = sum(1 for question in required_questions if _value_is_answered(payload_values.get(question["id"])))
        if has_structured_beneficiary_address or _value_is_answered(merged.get("beneficiary_current_address")):
            answered_count += 1
        return _form_result(
            form_code="form_i130",
            issues=issues,
            field_count=answered_count,
            required_field_count=len(required_questions) + 1,
            template_field_count=len(template_fields),
            template_path=template_path,
            metadata={
                "validator_level": "relationship_petition_preflight",
                "note": "Checks core I-130 relationship facts, tracked supporting evidence, and first-pass PDF fill payload coverage.",
                "questionnaire_version": I130_QUESTIONNAIRE_VERSION,
                "source_question_count": len(all_i130_questions()),
                "mapped_pdf_field_count": len(pdf_payload.text_values) + len(pdf_payload.checkbox_values),
                "mapped_pdf_fields": pdf_payload.mapped_fields,
                "missing_template_fields": pdf_payload.missing_template_fields,
                "pdf_text_field_count": len(pdf_payload.text_values),
                "pdf_checkbox_field_count": len(pdf_payload.checkbox_values),
            },
        )


class I130AFilingValidator:
    form_code = "form_i130a"

    def validate(self, session: Session, case_id: UUID, template_path: Path | None) -> dict[str, Any]:
        merged = _intake_with_form_gaps_filled(session, case_id, "i130a")
        uploads = _confirmed_uploads(session, case_id)
        template_fields, template_error = _template_field_names(template_path) if template_path else (set(), None)
        pdf_payload = build_i130a_pdf_field_payload(merged, template_fields)
        issues: list[dict[str, Any]] = []

        if template_error:
            issues.append(
                _issue(
                    form_code="form_i130a",
                    severity="important",
                    code="form_i130a_template_unavailable",
                    title="I-130A template could not be inspected",
                    description="The validator could not inspect the selected blank I-130A PDF.",
                    source="blank_pdf_template",
                    actual=template_error,
                )
            )
        if pdf_payload.missing_template_fields:
            issues.append(
                _issue(
                    form_code="form_i130a",
                    severity="important",
                    code="form_i130a_template_field_mismatch",
                    title="Mapped I-130A PDF fields are absent from the selected template",
                    description=(
                        "Some core I-130A case fields map to PDF field names that are not present in the selected "
                        "blank template. Regenerate or review the I-130A field map before relying on automated fill output."
                    ),
                    source="blank_pdf_template",
                    pdf_fields=pdf_payload.missing_template_fields,
                )
            )

        required_questions = required_family_questions("form_i130a")
        _append_missing_required_question_issues(
            issues=issues,
            form_code="form_i130a",
            values=merged,
            questions=required_questions,
            title="Required I-130A biographic fact is missing",
            description_suffix="from the case record for source-dated I-130A preflight review.",
        )

        has_structured_address = all(
            _value_is_answered(merged.get(key))
            for key in (
                "beneficiary_current_address_line1",
                "beneficiary_current_city",
                "beneficiary_current_state",
                "beneficiary_current_zip",
            )
        )
        if not has_structured_address and not _value_is_answered(merged.get("beneficiary_current_address")):
            issues.append(
                _issue(
                    form_code="form_i130a",
                    severity="blocking",
                    code="form_i130a_current_address_missing_required",
                    title="Beneficiary current address is missing",
                    description="Current address is needed for I-130A biographic preflight review.",
                    source="case_intake",
                    field_key="beneficiary_current_address",
                )
            )

        current_since = _parse_iso_date(
            merged.get("beneficiary_address_since") or merged.get("beneficiary_current_address_since")
        )
        if current_since and current_since > _subtract_years(date.today(), 5):
            if not _value_is_answered(merged.get("beneficiary_prior_address_history")):
                issues.append(
                    _issue(
                        form_code="form_i130a",
                        severity="blocking",
                        code="form_i130a_five_year_address_history_missing",
                        title="I-130A five-year address history is incomplete",
                        description=(
                            f"The current address starts on {current_since.isoformat()}, which is less than five "
                            "years ago, but no prior address history is saved."
                        ),
                        source="case_intake",
                        field_key="beneficiary_prior_address_history",
                    )
                )

        if merged.get("beneficiary_marriage_count") not in (None, "", 1):
            issues.append(
                _issue(
                    form_code="form_i130a",
                    severity="important",
                    code="form_i130a_prior_marriage_outside_simple_case",
                    title="Beneficiary prior marriage count is outside the simple-case scope",
                    description=(
                        "This validator is scoped to first-marriage cases. Review prior spouse fields and "
                        "termination evidence before filing."
                    ),
                    source="case_intake",
                    field_key="beneficiary_marriage_count",
                    expected=1,
                    actual=merged.get("beneficiary_marriage_count"),
                )
            )

        i485_answers = get_i485_state(session, case_id)["answers"]
        _append_cross_form_mismatch_issues(
            issues=issues,
            form_code="form_i130a",
            other_form_label="Form I-485",
            current_values=merged,
            other_values=i485_answers,
            field_labels={
                "beneficiary_a_number": "Beneficiary A-number",
                "beneficiary_first_name": "Beneficiary given name",
                "beneficiary_last_name": "Beneficiary family name",
                "beneficiary_middle_name": "Beneficiary middle name",
                "beneficiary_date_of_birth": "Beneficiary date of birth",
                "beneficiary_country_of_birth": "Beneficiary country of birth",
                "beneficiary_current_address_line1": "Beneficiary street address",
                "beneficiary_current_city": "Beneficiary city",
                "beneficiary_current_state": "Beneficiary state",
                "beneficiary_current_zip": "Beneficiary ZIP code",
                "beneficiary_current_marital_status": "Beneficiary marital status",
                "beneficiary_marriage_count": "Beneficiary marriage count",
            },
        )
        _append_uploaded_document_mismatch_issues(
            issues=issues,
            form_code="form_i130a",
            uploads=uploads,
            checklist_codes={"form_i130", "form_i130a"},
            current_values=merged,
            field_labels={
                "beneficiary_a_number": "Beneficiary A-number",
                "beneficiary_first_name": "Beneficiary given name",
                "beneficiary_last_name": "Beneficiary family name",
                "beneficiary_middle_name": "Beneficiary middle name",
                "beneficiary_date_of_birth": "Beneficiary date of birth",
                "beneficiary_country_of_birth": "Beneficiary country of birth",
                "beneficiary_current_address_line1": "Beneficiary street address",
                "beneficiary_current_city": "Beneficiary city",
                "beneficiary_current_state": "Beneficiary state",
                "beneficiary_current_zip": "Beneficiary ZIP code",
            },
        )

        answered_count = sum(1 for question in required_questions if _value_is_answered(merged.get(question["id"])))
        if has_structured_address or _value_is_answered(merged.get("beneficiary_current_address")):
            answered_count += 1
        return _form_result(
            form_code="form_i130a",
            issues=issues,
            field_count=answered_count,
            required_field_count=len(required_questions) + 1,
            template_field_count=len(template_fields),
            template_path=template_path,
            metadata={
                "validator_level": "spouse_biographic_preflight",
                "note": "Checks core spouse-biographic facts and first-pass PDF fill payload coverage.",
                "questionnaire_version": I130A_QUESTIONNAIRE_VERSION,
                "source_question_count": len(all_i130a_questions()),
                "mapped_pdf_field_count": len(pdf_payload.text_values) + len(pdf_payload.checkbox_values),
                "mapped_pdf_fields": pdf_payload.mapped_fields,
                "missing_template_fields": pdf_payload.missing_template_fields,
                "pdf_text_field_count": len(pdf_payload.text_values),
                "pdf_checkbox_field_count": len(pdf_payload.checkbox_values),
            },
        )
