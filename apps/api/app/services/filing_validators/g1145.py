"""Filing validator for Form G-1145."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from sqlmodel import Session

from app.services.case_facts import value_is_answered
from app.services.filing_validators.shared import (
    build_issue,
    form_result,
    inspect_template_fields,
    looks_like_email,
    phone_digits,
    template_unavailable_issue,
)
from app.services.intake import get_merged_case_intake


def _check_g1145_contact_details(
    *,
    email: Any,
    first_name: Any,
    issues: list[dict[str, Any]],
    last_name: Any,
    phone: Any,
) -> None:
    required_values = {
        "last_name": (last_name, "Applicant or petitioner family name"),
        "first_name": (first_name, "Applicant or petitioner given name"),
    }
    for field_key, (value, label) in required_values.items():
        if value_is_answered(value):
            continue
        issues.append(
            build_issue(
                form_code="form_g1145",
                severity="blocking",
                code=f"form_g1145_{field_key}_missing_required",
                title="Required G-1145 name field is missing",
                description=f"{label} is missing, so the e-notification request is not ready.",
                source="case_intake",
                field_key=field_key,
            )
        )

    if not value_is_answered(email) and not value_is_answered(phone):
        issues.append(
            build_issue(
                form_code="form_g1145",
                severity="blocking",
                code="form_g1145_contact_method_missing_required",
                title="G-1145 contact method is missing",
                description="Add an email address or mobile phone number before including Form G-1145.",
                source="case_intake",
                field_key="g1145_email_or_mobile_phone",
            )
        )
    if value_is_answered(email) and not looks_like_email(email):
        issues.append(
            build_issue(
                form_code="form_g1145",
                severity="blocking",
                code="form_g1145_email_invalid",
                title="G-1145 email address looks invalid",
                description="The saved e-notification email address does not look usable.",
                source="case_intake",
                field_key="g1145_email",
                actual=email,
            )
        )
    if value_is_answered(phone) and len(phone_digits(phone)) < 10:
        issues.append(
            build_issue(
                form_code="form_g1145",
                severity="important",
                code="form_g1145_mobile_phone_incomplete",
                title="G-1145 mobile phone number may be incomplete",
                description="The saved e-notification mobile phone number has fewer than 10 digits.",
                source="case_intake",
                field_key="g1145_mobile_phone",
                actual=phone,
            )
        )
    if value_is_answered(email) and not value_is_answered(phone):
        issues.append(
            build_issue(
                form_code="form_g1145",
                severity="recommended",
                code="form_g1145_mobile_phone_missing",
                title="G-1145 text notification phone is not saved",
                description="The form can still be reviewed with email, but adding a mobile number enables text notification.",
                source="case_intake",
                field_key="g1145_mobile_phone",
            )
        )
    if value_is_answered(phone) and not value_is_answered(email):
        issues.append(
            build_issue(
                form_code="form_g1145",
                severity="recommended",
                code="form_g1145_email_missing",
                title="G-1145 email notification address is not saved",
                description="The form can still be reviewed with a mobile number, but adding email enables email notification.",
                source="case_intake",
                field_key="g1145_email",
            )
        )


class G1145FilingValidator:
    form_code = "form_g1145"

    def validate(self, session: Session, case_id: UUID, template_path: Path | None) -> dict[str, Any]:
        merged = get_merged_case_intake(session, case_id)
        template_fields, template_error = inspect_template_fields(template_path)
        issues: list[dict[str, Any]] = []

        if template_error:
            issues.append(template_unavailable_issue("form_g1145", "G-1145", template_error))

        name_source = "g1145" if any(value_is_answered(merged.get(f"g1145_{part}")) for part in ("first_name", "middle_name", "last_name")) else "beneficiary"
        last_name = merged.get(f"{name_source}_last_name") or merged.get("beneficiary_last_name") or merged.get("petitioner_last_name")
        first_name = merged.get(f"{name_source}_first_name") or merged.get("beneficiary_first_name") or merged.get("petitioner_first_name")
        middle_name = merged.get(f"{name_source}_middle_name") or merged.get("beneficiary_middle_name")
        email = merged.get("g1145_email") or merged.get("beneficiary_email") or merged.get("petitioner_email")
        phone = merged.get("g1145_mobile_phone") or merged.get("beneficiary_phone") or merged.get("petitioner_phone")

        _check_g1145_contact_details(
            email=email,
            first_name=first_name,
            issues=issues,
            last_name=last_name,
            phone=phone,
        )

        answered_values = [last_name, first_name, middle_name, email, phone]
        return form_result(
            form_code="form_g1145",
            issues=issues,
            field_count=sum(1 for value in answered_values if value_is_answered(value)),
            required_field_count=3,
            template_field_count=len(template_fields),
            template_path=template_path,
            metadata={
                "validator_level": "optional_e_notification_preflight",
                "note": "Checks the optional G-1145 e-notification name and contact fields only.",
            },
        )
