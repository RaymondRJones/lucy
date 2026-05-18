from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from sqlmodel import Session

from app.services.filing_validators.shared import *


class I864FilingValidator:
    form_code = "form_i864"

    def validate(self, session: Session, case_id: UUID, template_path: Path | None) -> dict[str, Any]:
        merged = get_merged_case_intake(session, case_id)
        template_fields, template_error = _template_field_names(template_path)
        uploads = _confirmed_uploads(session, case_id)
        issues: list[dict[str, Any]] = []

        if template_error:
            issues.append(
                _issue(
                    form_code="form_i864",
                    severity="important",
                    code="form_i864_template_unavailable",
                    title="I-864 template could not be inspected",
                    description="The validator could not inspect the selected blank I-864 PDF.",
                    source="blank_pdf_template",
                    actual=template_error,
                )
            )

        required_fields = {
            "petitioner_first_name": "Sponsor given name",
            "petitioner_last_name": "Sponsor family name",
            "petitioner_current_address": "Sponsor mailing or physical address",
            "annual_income": "Sponsor annual income",
            "employment_status": "Sponsor employment status",
            "household_size": "Household size",
        }
        for field_key, label in required_fields.items():
            if _value_is_answered(merged.get(field_key)):
                continue
            issues.append(
                _issue(
                    form_code="form_i864",
                    severity="blocking",
                    code=f"form_i864_{field_key}_missing_required",
                    title="Required I-864 sponsor fact is missing",
                    description=(
                        f"{label} is missing from the case record. USCIS Form I-864 review depends on complete "
                        "sponsor identity, household, and income facts."
                    ),
                    source="case_intake",
                    field_key=field_key,
                )
            )

        income = merged.get("annual_income")
        income_value = _as_float(income)
        if _value_is_answered(income):
            if income_value is None or income_value <= 0:
                issues.append(
                    _issue(
                        form_code="form_i864",
                        severity="blocking",
                        code="form_i864_income_invalid",
                        title="Sponsor income must be a positive number",
                        description="The saved annual income value is not usable for I-864 review.",
                        source="case_intake",
                        field_key="annual_income",
                        actual=income,
                    )
                )
        household_size = _as_int(merged.get("household_size"))
        if household_size is not None and household_size < 2:
            issues.append(
                _issue(
                    form_code="form_i864",
                    severity="blocking",
                    code="form_i864_household_size_invalid",
                    title="I-864 household size is too low",
                    description=(
                        "For this marriage-based case, household size should include at least the sponsor and "
                        "the intending immigrant."
                    ),
                    source="case_intake",
                    field_key="household_size",
                    expected="2 or more",
                    actual=household_size,
                )
            )

        sponsor_state = _sponsor_state(merged)
        region = i864p_region_for_state(sponsor_state)
        if region is None:
            region = "contiguous"
            issues.append(
                _issue(
                    form_code="form_i864",
                    severity="recommended",
                    code="form_i864_sponsor_state_not_confirmed",
                    title="Sponsor state should be confirmed for I-864P income review",
                    description=(
                        "The validator is using the 48-contiguous-states I-864P table by default. Confirm the "
                        "sponsor is not domiciled in Alaska or Hawaii before relying on this income comparison."
                    ),
                    source="case_intake",
                    field_key="petitioner_current_state",
                    expected="A U.S. state or territory abbreviation",
                    actual=sponsor_state,
                )
            )
        active_duty = _as_bool(
            merged.get("sponsor_active_duty_sponsoring_spouse_or_child")
            or merged.get("petitioner_active_duty_sponsoring_spouse_or_child")
        )
        required_income = None
        if household_size is not None:
            required_income = i864p_required_income(
                household_size,
                region=region,
                active_duty_sponsoring_spouse_or_child=active_duty,
            )
        if income_value is not None and required_income is not None and income_value < required_income:
            issues.append(
                _issue(
                    form_code="form_i864",
                    severity="blocking",
                    code="form_i864_income_below_i864p_guideline",
                    title="Sponsor income appears below the I-864P guideline",
                    description=(
                        "The saved annual income is below the source-dated USCIS I-864P threshold for the saved "
                        "household size and sponsor region. Review whether assets, household-member income, or a "
                        "joint sponsor is needed."
                    ),
                    source="case_intake",
                    field_key="annual_income",
                    expected=required_income,
                    actual=income_value,
                )
            )

        has_tax_upload = any(upload.checklist_item_code == "sponsor_tax_return" for upload in uploads)
        has_tax_explanation = _value_is_answered(
            merged.get("sponsor_tax_return_explanation") or merged.get("sponsor_not_required_to_file_tax_explanation")
        )
        if not has_tax_upload and not has_tax_explanation:
            issues.append(
                _issue(
                    form_code="form_i864",
                    severity="blocking",
                    code="form_i864_tax_evidence_missing_required",
                    title="I-864 tax evidence or no-filing explanation is missing",
                    description=(
                        "USCIS lists the sponsor's most recent federal income tax return with related evidence, "
                        "or a statement/evidence explaining why the sponsor was not required to file, as required "
                        "initial evidence for Form I-864."
                    ),
                    source="case_intake",
                    field_key="sponsor_tax_return",
                )
            )

        if _normalize_scalar(merged.get("employment_status")) not in {None, "unemployed", "none"}:
            has_pay_stub_upload = any(upload.checklist_item_code == "sponsor_pay_stubs" for upload in uploads)
            has_employment_letter_upload = any(
                upload.checklist_item_code == "employment_verification_letter" for upload in uploads
            )
            if not has_pay_stub_upload and not has_employment_letter_upload:
                issues.append(
                    _issue(
                        form_code="form_i864",
                        severity="recommended",
                        code="form_i864_current_income_support_recommended",
                        title="Current income support is recommended",
                        description=(
                            "The sponsor is marked as employed, but no pay stubs or employment verification letter "
                            "upload is confirmed. Current income evidence can help support the I-864 review."
                        ),
                        source="case_intake",
                        field_key="employment_status",
                    )
                )

        if not _value_is_answered(merged.get("reviewed_current_fees")):
            issues.append(
                _issue(
                    form_code="form_i864",
                    severity="recommended",
                    code="form_i864_fee_review_not_confirmed",
                    title="Current USCIS fee review is not confirmed",
                    description="Confirm the current USCIS fee schedule before mailing the packet.",
                    source="case_intake",
                    field_key="reviewed_current_fees",
                )
            )

        return _form_result(
            form_code="form_i864",
            issues=issues,
            field_count=sum(1 for key in required_fields if _value_is_answered(merged.get(key))),
            required_field_count=len(required_fields),
            template_field_count=len(template_fields),
            template_path=template_path,
            metadata={
                "validator_level": "sponsor_preflight",
                "note": "This pass checks core sponsor facts, I-864P income threshold, and required tax evidence.",
                "i864p_version": I864P_VERSION,
                "i864p_region": region,
                "i864p_region_label": I864P_GUIDELINES[region]["label"],
                "i864p_required_income": required_income,
                "i864p_threshold_pct": 100 if active_duty else 125,
            },
        )
