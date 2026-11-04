from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from sqlmodel import Session

from app.services.filing_validators.shared import *


class I765FilingValidator:
    form_code = "form_i765"

    def validate(self, session: Session, case_id: UUID, template_path: Path | None) -> dict[str, Any]:
        merged = _intake_with_form_gaps_filled(session, case_id, "i765")
        facts = derive_case_facts(merged)
        uploads = _confirmed_uploads(session, case_id)
        template_fields, template_error = _template_field_names(template_path)
        issues: list[dict[str, Any]] = []

        if template_error:
            issues.append(
                _issue(
                    form_code="form_i765",
                    severity="important",
                    code="form_i765_template_unavailable",
                    title="I-765 template could not be inspected",
                    description="The validator could not inspect the selected blank I-765 PDF.",
                    source="blank_pdf_template",
                    actual=template_error,
                )
            )

        if not facts["concurrent_filing_eligible"]:
            issues.append(
                _issue(
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
            if _value_is_answered(merged.get(field_key)):
                continue
            issues.append(
                _issue(
                    form_code="form_i765",
                    severity="blocking",
                    code=f"form_i765_{field_key}_missing_required",
                    title="Required I-765 fact is missing",
                    description=f"{label} is missing from the case record for I-765 preflight review.",
                    source="case_intake",
                    field_key=field_key,
                )
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
                    form_code="form_i765",
                    severity="blocking",
                    code="form_i765_current_address_missing_required",
                    title="Beneficiary current address is missing",
                    description="A current U.S. mailing or physical address is needed before I-765 review.",
                    source="case_intake",
                    field_key="beneficiary_current_address",
                )
            )

        upload_codes = {upload.checklist_item_code for upload in uploads}
        supporting_evidence = {
            "beneficiary_i94": "I-94 or comparable arrival/travel-document evidence",
            "beneficiary_passport_bio": "Passport or travel-document identity page",
        }
        for checklist_code, label in supporting_evidence.items():
            if checklist_code in upload_codes:
                continue
            issues.append(
                _issue(
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
                _issue(
                    form_code="form_i765",
                    severity="important",
                    code="form_i765_underlying_i485_not_confirmed",
                    title="Underlying I-485 basis is not confirmed for I-765",
                    description=(
                        "For this MVP path, I-765 is expected to rely on a concurrent or pending Form I-485. "
                        "Confirm the I-485 draft or upload before treating I-765 as ready."
                    ),
                    source="case_intake",
                    field_key="form_i485",
                )
            )

        if _value_is_answered(merged.get("i765_eligibility_category")) and merged.get("i765_eligibility_category") != "c9":
            issues.append(
                _issue(
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

        answered_count = sum(1 for field_key in required_fields if _value_is_answered(merged.get(field_key)))
        if has_structured_address or _value_is_answered(merged.get("beneficiary_current_address")):
            answered_count += 1
        return _form_result(
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
