"""Rules that derive case facts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.services.rules.core import RuleEngine, RuleResult

CountryNormalizer = Callable[[Any], str | None]


@dataclass
class CaseFactsContext:
    merged: dict[str, Any]
    normalize_country: CountryNormalizer
    facts: dict[str, Any] = field(default_factory=dict)
    scratch: dict[str, Any] = field(default_factory=dict)


class NormalizeCaseInputsRule:
    rule_id = "case_facts:normalize_inputs"

    def evaluate(self, context: CaseFactsContext) -> RuleResult[dict[str, Any]]:
        merged = context.merged
        context.scratch.update(
            {
                "petitioner_citizenship_status": str(
                    merged.get("petitioner_citizenship_status", "us_citizen")
                ).lower(),
                "beneficiary_location": str(merged.get("beneficiary_location", "usa")).lower(),
                "i130_filing_status": str(merged.get("i130_filing_status", "not_filed")).lower(),
                "entered_legally": bool(merged.get("beneficiary_entered_us_legally")),
                "country_code": context.normalize_country(
                    merged.get("beneficiary_country_of_birth") or merged.get("country_of_focus")
                ),
                "wants_i765": bool(merged.get("wants_i765", True)),
                "wants_i131": bool(merged.get("wants_i131", False)),
                "first_marriage": bool(merged.get("first_marriage_for_both")),
                "employment_status": str(merged.get("employment_status", "employed")).lower(),
            }
        )
        return RuleResult(self.rule_id, context.scratch)


class WorkflowEligibilityFactsRule:
    rule_id = "case_facts:workflow_eligibility"

    def evaluate(self, context: CaseFactsContext) -> RuleResult[dict[str, Any]]:
        petitioner_status = context.scratch["petitioner_citizenship_status"]
        beneficiary_location = context.scratch["beneficiary_location"]
        entered_legally = context.scratch["entered_legally"]
        context.facts.update(
            {
                "petitioner_is_us_citizen": petitioner_status == "us_citizen",
                "beneficiary_in_us": beneficiary_location == "usa",
                "entered_us_legally": entered_legally,
                "concurrent_filing_eligible": petitioner_status == "us_citizen"
                and beneficiary_location == "usa"
                and entered_legally,
            }
        )
        return RuleResult(self.rule_id, context.facts)


class I130BranchFactsRule:
    rule_id = "case_facts:i130_branch"

    def evaluate(self, context: CaseFactsContext) -> RuleResult[dict[str, Any]]:
        i130_status = context.scratch["i130_filing_status"]
        context.facts.update(
            {
                "i130_filing_status": i130_status,
                "i130_already_filed": i130_status in {"pending", "approved", "filed"},
                "i130_not_filed": i130_status in {"", "not_filed", "none"},
                "i130_needs_review": i130_status in {"unknown", "denied_revoked_withdrawn"},
            }
        )
        return RuleResult(self.rule_id, context.facts)


class FilingChoiceFactsRule:
    rule_id = "case_facts:filing_choices"

    def evaluate(self, context: CaseFactsContext) -> RuleResult[dict[str, Any]]:
        context.facts.update(
            {
                "wants_i765": context.scratch["wants_i765"],
                "wants_i131": context.scratch["wants_i131"],
            }
        )
        return RuleResult(self.rule_id, context.facts)


class EvidenceReadinessFactsRule:
    rule_id = "case_facts:evidence_readiness"

    def evaluate(self, context: CaseFactsContext) -> RuleResult[dict[str, Any]]:
        merged = context.merged
        country_code = context.scratch["country_code"]
        employment_status = context.scratch["employment_status"]
        needs_translation = bool(
            merged.get(
                "needs_translation",
                country_code not in {"US", None},
            )
        )
        context.facts.update(
            {
                "first_marriage_for_both": context.scratch["first_marriage"],
                "has_marriage_date": bool(merged.get("marriage_date")),
                "beneficiary_country_known": country_code is not None,
                "beneficiary_has_passport": True,
                "country_code": country_code,
                "country_is_colombia": country_code == "CO",
                "needs_translation": needs_translation,
                "has_employment_income": employment_status not in {"", "unemployed", "none"},
                "household_size": int(merged.get("household_size") or 0),
                "reviewed_current_fees": bool(merged.get("reviewed_current_fees")),
                "reviewed_current_form_editions": bool(merged.get("reviewed_current_form_editions")),
                "has_joint_lease": bool(merged.get("has_joint_lease")),
                "has_joint_bank_account": bool(merged.get("has_joint_bank_account")),
                "has_relationship_photos": bool(merged.get("has_relationship_photos")),
                "has_affidavits": bool(merged.get("has_affidavits")),
            }
        )
        return RuleResult(self.rule_id, context.facts)


class EscalationFactsRule:
    rule_id = "case_facts:escalation"

    def evaluate(self, context: CaseFactsContext) -> RuleResult[dict[str, Any]]:
        merged = context.merged
        escalation_flags = {
            "unlawful_entry": bool(merged.get("unlawful_entry"))
            or (
                context.scratch["beneficiary_location"] == "usa"
                and not context.scratch["entered_legally"]
            ),
            "criminal_history": bool(merged.get("criminal_history")),
            "prior_immigration_denials": bool(merged.get("prior_immigration_denials")),
            "removal_history": bool(merged.get("removal_history")),
            "identity_inconsistencies": bool(merged.get("identity_inconsistencies")),
        }
        context.facts.update(
            {
                "complex_case": any(escalation_flags.values()),
                "escalation_flags": escalation_flags,
            }
        )
        return RuleResult(self.rule_id, context.facts)


class CaseFactsRuleEngine:
    def __init__(self) -> None:
        self._engine = RuleEngine(
            [
                NormalizeCaseInputsRule(),
                WorkflowEligibilityFactsRule(),
                I130BranchFactsRule(),
                FilingChoiceFactsRule(),
                EvidenceReadinessFactsRule(),
                EscalationFactsRule(),
            ]
        )

    def evaluate(self, context: CaseFactsContext) -> dict[str, Any]:
        self._engine.evaluate(context)
        return context.facts

