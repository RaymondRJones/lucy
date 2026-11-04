"""Filing validator for Form I-765."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from sqlmodel import Session

from app.models.entities import UploadedDocument
from app.services.case_facts import value_is_answered
from app.services.filing_validators.shared import (
    build_issue,
    confirmed_uploads,
    form_result,
    inspect_template_fields,
    intake_with_form_gaps_filled,
    template_unavailable_issue,
)
from app.services.i485 import get_i485_state
from app.services.intake import derive_case_facts


def _check_i765_filing_path(*, facts: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    if not facts["concurrent_filing_eligible"]:
        issues.append(
            build_issue(
                form_code="form_i765",
                severity="blocking",
                code="form_i765_not_standard_concurrent_c9_path",
                title="I-765 is outside the standard concurrent adjustment path",
                description=(
                    "This validator only covers the simple adjustment-pending employment authorization path "
                    "for a beneficiary concurrently filing Form I-485 as the spouse of a U.S. citizen."
                ),
                source="case_intake",
                field_key="wants_i765",
            )
        )


def _check_i765_required_fields(
    *,
    issues: list[dict[str, Any]],
    merged: dict[str, Any],
) -> dict[str, str]:
    required_fields = {
        "beneficiary_first_name": "Beneficiary given name",
        "beneficiary_last_name": "Beneficiary family name",
        "beneficiary_date_of_birth": "Beneficiary date of birth",
        "beneficiary_country_of_birth": "Beneficiary country of birth",
        "beneficiary_country_of_citizenship": "Beneficiary country of citizenship",
        "beneficiary_current_immigration_status": "Beneficiary current immigration status",
        "beneficiary_i94_number": "Most recent I-94 number",
        "beneficiary_passport_number": "Passport or travel document number",
    }
    for field_key, label in required_fields.items():
        if value_is_answered(merged.get(field_key)):
            continue
        issues.append(
            build_issue(
                form_code="form_i765",
                severity="blocking",
                code=f"form_i765_{field_key}_missing_required",
                title="Required I-765 fact is missing",
                description=f"{label} is missing from the case record for I-765 preflight review.",
                source="case_intake",
                field_key=field_key,
            )
        )
    return required_fields


def _check_i765_address(*, issues: list[dict[str, Any]], merged: dict[str, Any]) -> bool:
    has_structured_address = all(
        value_is_answered(merged.get(key))
        for key in (
            "beneficiary_current_address_line1",
            "beneficiary_current_city",
            "beneficiary_current_state",
            "beneficiary_current_zip",
        )
    )
    if not has_structured_address and not value_is_answered(merged.get("beneficiary_current_address")):
        issues.append(
            build_issue(
                form_code="form_i765",
                severity="blocking",
                code="form_i765_current_address_missing_required",
                title="Beneficiary current address is missing",
                description="A current U.S. mailing or physical address is needed before I-765 review.",
                source="case_intake",
                field_key="beneficiary_current_address",
            )
        )
    return has_structured_address


def _check_i765_evidence_and_category(
    *,
    case_id: UUID,
    session: Session,
    issues: list[dict[str, Any]],
    merged: dict[str, Any],
    uploads: list[UploadedDocument],
) -> None:
    upload_codes = {upload.checklist_item_code for upload in uploads}
    supporting_evidence = {
        "beneficiary_i94": "I-94 or comparable arrival/travel-document evidence",
        "beneficiary_passport_bio": "Passport or travel-document identity page",
    }
    for checklist_code, label in supporting_evidence.items():
        if checklist_code in upload_codes:
            continue
        issues.append(
            build_issue(
                form_code="form_i765",
                severity="blocking",
                code=f"form_i765_{checklist_code}_evidence_missing_required",
                title="Required I-765 supporting evidence is missing",
                description=f"{label} is not confirmed in uploads for I-765 preflight review.",
                source="case_intake",
                field_key=checklist_code,
            )
        )

    if "form_i485" not in upload_codes and not get_i485_state(session, case_id)["answers"]:
        issues.append(
            build_issue(
                form_code="form_i765",
                severity="important",
                code="form_i765_underlying_i485_not_confirmed",
                title="Underlying I-485 basis is not confirmed for I-765",
                description=(
                    "On the standard path, I-765 is expected to rely on a concurrent or pending Form I-485. "
                    "Confirm the I-485 draft or upload before treating I-765 as ready."
                ),
                source="case_intake",
                field_key="form_i485",
            )
        )

    if value_is_answered(merged.get("i765_eligibility_category")) and merged.get("i765_eligibility_category") != "c9":
        issues.append(
            build_issue(
                form_code="form_i765",
                severity="important",
                code="form_i765_eligibility_category_not_c9",
                title="I-765 eligibility category is outside the standard adjustment-pending path",
                description="This validator expects category (c)(9) for an adjustment-pending applicant.",
                source="case_intake",
                field_key="i765_eligibility_category",
                expected="c9",
                actual=merged.get("i765_eligibility_category"),
            )
        )


class I765FilingValidator:
    form_code = "form_i765"

    def validate(self, session: Session, case_id: UUID, template_path: Path | None) -> dict[str, Any]:
        merged = intake_with_form_gaps_filled(session, case_id, "i765")
        facts = derive_case_facts(merged)
        uploads = confirmed_uploads(session, case_id)
        template_fields, template_error = inspect_template_fields(template_path)
        issues: list[dict[str, Any]] = []

        if template_error:
            issues.append(template_unavailable_issue("form_i765", "I-765", template_error))

        _check_i765_filing_path(facts=facts, issues=issues)

        required_fields = _check_i765_required_fields(issues=issues, merged=merged)

        has_structured_address = _check_i765_address(issues=issues, merged=merged)

        _check_i765_evidence_and_category(
            case_id=case_id,
            session=session,
            issues=issues,
            merged=merged,
            uploads=uploads,
        )

        answered_count = sum(1 for field_key in required_fields if value_is_answered(merged.get(field_key)))
        if has_structured_address or value_is_answered(merged.get("beneficiary_current_address")):
            answered_count += 1
        return form_result(
            form_code="form_i765",
            issues=issues,
            field_count=answered_count,
            required_field_count=len(required_fields) + 1,
            template_field_count=len(template_fields),
            template_path=template_path,
            metadata={
                "validator_level": "adjustment_pending_c9_preflight",
                "expected_eligibility_category": "c9",
                "note": "Checks core identity, address, travel facts, I-485 basis, and tracked supporting evidence.",
            },
        )
