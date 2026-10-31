from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlmodel import Session

from app.services.filing_validators.family import I130AFilingValidator, I130FilingValidator
from app.services.filing_validators.g1145 import G1145FilingValidator
from app.services.filing_validators.i131 import I131FilingValidator
from app.services.filing_validators.i485 import I485FilingValidator
from app.services.filing_validators.i765 import I765FilingValidator
from app.services.filing_validators.i864 import I864FilingValidator
from app.services.filing_validators.shared import (
    DEFAULT_VALIDATION_SCOPE,
    ROADMAP_FORM_CODES,
    SUPPORTED_FORM_CODES,
    _default_template_path,
    _form_label,
    _source_payload,
    _status_for_counts,
    _template_metadata,
    _unsupported_form_result,
    _utcnow,
    derive_case_facts,
    get_merged_case_intake,
)
from app.services.rules.filing_validation import FilingValidationContext, FilingValidationRuleEngine, FormValidator


def build_validation_roadmap(requested_form_codes: list[str]) -> list[dict[str, Any]]:
    roadmap: list[dict[str, Any]] = [
        {
            "form_code": "form_i485",
            "status": "implemented",
            "next_step": "Regenerate and expand the PDF field map when USCIS publishes a new edition.",
        },
        {
            "form_code": "form_i864",
            "status": "partial",
            "next_step": "Add a full I-864 questionnaire map, poverty-guideline calculations, tax transcript checks, and sponsor/joint-sponsor branching.",
        },
        {
            "form_code": "form_g1145",
            "status": "partial",
            "next_step": "Add explicit PDF field mapping for optional e-notification output.",
        },
        {
            "form_code": "form_i765",
            "status": "partial",
            "next_step": "Add a full I-765 question map, category-specific evidence branching, and PDF fill mapping.",
        },
        {
            "form_code": "form_i131",
            "status": "partial",
            "next_step": "Expand the I-131 map beyond the pending-I-485 advance parole path and add deeper evidence branching.",
        },
        {
            "form_code": "form_i130",
            "status": "partial",
            "next_step": "Expand the source-dated I-130 question map to every line and add generated-PDF output.",
        },
        {
            "form_code": "form_i130a",
            "status": "partial",
            "next_step": "Expand the source-dated I-130A question map to every line and add generated-PDF output.",
        },
    ]
    for form_code in ROADMAP_FORM_CODES:
        if form_code in {"form_i485", "form_i864", "form_g1145", "form_i765", "form_i131", "form_i130", "form_i130a"}:
            continue
        roadmap.append(
            {
                "form_code": form_code,
                "status": "planned",
                "next_step": "Extract the blank PDF fields, create a source-dated question map, then add record, PDF, and cross-document rules.",
            }
        )
    extra_codes = [
        code
        for code in requested_form_codes
        if code not in SUPPORTED_FORM_CODES and code not in ROADMAP_FORM_CODES
    ]
    for form_code in extra_codes:
        roadmap.append(
            {
                "form_code": form_code,
                "status": "unknown",
                "next_step": "Register the form with USCIS source metadata before adding validation rules.",
            }
        )
    return roadmap


def get_filing_validation_capabilities() -> dict[str, Any]:
    forms: list[dict[str, Any]] = []
    for roadmap_item in build_validation_roadmap([]):
        form_code = roadmap_item["form_code"]
        template_path = _default_template_path(form_code)
        template_info: dict[str, Any] = {
            "field_count": 0,
            "page_count": 0,
            "sha256": None,
            "error": None,
        }
        if template_path:
            template_info = _template_metadata(template_path)
        forms.append(
            {
                "form_code": form_code,
                "label": _form_label(form_code),
                "status": roadmap_item["status"],
                "next_step": roadmap_item["next_step"],
                "default_template_path": str(template_path) if template_path else None,
                "template_field_count": template_info["field_count"] if template_path else 0,
                "template_page_count": template_info["page_count"] if template_path else 0,
                "template_sha256": template_info["sha256"] if template_path else None,
                "template_error": template_info["error"],
                "source": _source_payload(form_code),
            }
        )
    return {
        "default_validation_scope": list(DEFAULT_VALIDATION_SCOPE),
        "supported_form_codes": sorted(SUPPORTED_FORM_CODES),
        "forms": forms,
    }


def _filing_validation_registry() -> dict[str, FormValidator]:
    return {
        "form_i485": I485FilingValidator().validate,
        "form_i864": I864FilingValidator().validate,
        "form_g1145": G1145FilingValidator().validate,
        "form_i765": I765FilingValidator().validate,
        "form_i131": I131FilingValidator().validate,
        "form_i130": I130FilingValidator().validate,
        "form_i130a": I130AFilingValidator().validate,
    }


def validate_case_filings(
    session: Session,
    case_id: UUID,
    *,
    form_codes: list[str] | None = None,
    template_paths: dict[str, str] | None = None,
) -> dict[str, Any]:
    requested_form_codes = form_codes or list(DEFAULT_VALIDATION_SCOPE)
    templates = template_paths or {}
    results = FilingValidationRuleEngine(_filing_validation_registry()).evaluate(
        FilingValidationContext(
            session=session,
            case_id=case_id,
            template_paths=templates,
            default_template_path=_default_template_path,
            unsupported_form_result=_unsupported_form_result,
        ),
        requested_form_codes,
    )

    issue_counts = {
        "blocking": sum(result["issue_counts"]["blocking"] for result in results),
        "important": sum(result["issue_counts"]["important"] for result in results),
        "recommended": sum(result["issue_counts"]["recommended"] for result in results),
    }
    facts = derive_case_facts(get_merged_case_intake(session, case_id))
    summary = {
        "status": _status_for_counts(issue_counts),
        "issue_counts": issue_counts,
        "form_count": len(results),
        "forms_passed": sum(1 for result in results if result["status"] == "passed"),
        "blocking_forms": [result["form_code"] for result in results if result["issue_counts"]["blocking"]],
    }
    return {
        "case_id": str(case_id),
        "generated_at": _utcnow(),
        "validation_scope": requested_form_codes,
        "summary": summary,
        "assumptions": {
            "workflow": "standard first-marriage marriage-based concurrent filing",
            "petitioner_is_us_citizen": facts["petitioner_is_us_citizen"],
            "beneficiary_in_us": facts["beneficiary_in_us"],
            "entered_us_legally": facts["entered_us_legally"],
            "not_legal_advice": True,
        },
        "forms": results,
        "roadmap": build_validation_roadmap(requested_form_codes),
    }
