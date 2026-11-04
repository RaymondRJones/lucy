"""Rules that select checklist items."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.content.checklist_rules import CHECKLIST_TEMPLATES, ChecklistTemplate
from app.content.uscis_requirements import FORM_CODES_BY_CHECKLIST_CODE, USCIS_REQUIREMENT_BY_CHECKLIST_CODE
from app.models.entities import ChecklistProgressStatus
from app.services.rules.core import RuleEngine, RuleResult

PENDING_I130_STATUSES = {"pending", "filed"}
PENDING_I130_I485_RELATIONSHIP_EVIDENCE_CODES = {
    "marriage_certificate",
    "photos_together",
    "joint_bank_statement",
    "joint_lease",
}


@dataclass(frozen=True)
class ChecklistRuleContext:
    facts: dict[str, Any]
    upload_counts: dict[str, int]
    existing_status_by_code: dict[str, str | None]


@dataclass(frozen=True)
class ChecklistRuleDecision:
    template: ChecklistTemplate
    sort_order: int
    applicability: str
    completion_status: str
    metadata: dict[str, Any]


class FactApplicabilityPolicy:
    def evaluate(self, template: ChecklistTemplate, facts: dict[str, Any]) -> str:
        if template.when_not and any(facts.get(flag) for flag in template.when_not):
            return "not_applicable"
        if template.when_all and not all(facts.get(flag) for flag in template.when_all):
            return "not_applicable"
        return template.default_applicability


class ChecklistCompletionPolicy:
    def evaluate(
        self,
        existing_status: str | None,
        template: ChecklistTemplate,
        applicability: str,
        facts: dict[str, Any],
        upload_count: int,
    ) -> str:
        valid_statuses = {status.value for status in ChecklistProgressStatus}
        if applicability == "not_applicable":
            return ChecklistProgressStatus.not_applicable.value
        if template.code == "review_current_fees":
            return (
                ChecklistProgressStatus.complete.value
                if facts.get("reviewed_current_fees")
                else ChecklistProgressStatus.not_started.value
            )
        if template.code == "review_form_editions":
            return (
                ChecklistProgressStatus.complete.value
                if facts.get("reviewed_current_form_editions")
                else ChecklistProgressStatus.not_started.value
            )

        normalized_status = existing_status if existing_status in valid_statuses else None
        if upload_count > 0 and normalized_status in {None, ChecklistProgressStatus.not_started.value}:
            return ChecklistProgressStatus.uploaded.value
        if upload_count == 0 and normalized_status == ChecklistProgressStatus.uploaded.value:
            return ChecklistProgressStatus.not_started.value
        return normalized_status or ChecklistProgressStatus.not_started.value


class PacketGroupingPolicy:
    def form_codes_for(self, checklist_code: str, facts: dict[str, Any]) -> list[str]:
        if self._should_group_pending_i130_relationship_evidence(checklist_code, facts):
            return ["form_i485"]
        return list(FORM_CODES_BY_CHECKLIST_CODE.get(checklist_code, []))

    def packet_group_reason_for(self, checklist_code: str, facts: dict[str, Any]) -> str | None:
        if self._should_group_pending_i130_relationship_evidence(checklist_code, facts):
            return "pending_i130_relationship_evidence"
        return None

    def _should_group_pending_i130_relationship_evidence(
        self,
        checklist_code: str,
        facts: dict[str, Any],
    ) -> bool:
        i130_status = str(facts.get("i130_filing_status") or "").lower()
        return (
            i130_status in PENDING_I130_STATUSES
            and checklist_code in PENDING_I130_I485_RELATIONSHIP_EVIDENCE_CODES
        )


class ChecklistMetadataPolicy:
    def __init__(self, packet_grouping: PacketGroupingPolicy) -> None:
        self._packet_grouping = packet_grouping

    def build(self, template: ChecklistTemplate, facts: dict[str, Any], upload_count: int) -> dict[str, Any]:
        return {
            "upload_count": upload_count,
            "form_codes": self._packet_grouping.form_codes_for(template.code, facts),
            "packet_group_reason": self._packet_grouping.packet_group_reason_for(template.code, facts),
            "facts_snapshot": {
                "concurrent_filing_eligible": facts.get("concurrent_filing_eligible"),
                "i130_filing_status": facts.get("i130_filing_status"),
                "i130_already_filed": facts.get("i130_already_filed"),
                "needs_translation": facts.get("needs_translation"),
                "complex_case": facts.get("complex_case"),
            },
            "uscis_requirement_code": (
                USCIS_REQUIREMENT_BY_CHECKLIST_CODE[template.code]["code"]
                if template.code in USCIS_REQUIREMENT_BY_CHECKLIST_CODE
                else None
            ),
        }


class ChecklistTemplateRule:
    def __init__(
        self,
        template: ChecklistTemplate,
        sort_order: int,
        applicability_policy: FactApplicabilityPolicy,
        completion_policy: ChecklistCompletionPolicy,
        metadata_policy: ChecklistMetadataPolicy,
    ) -> None:
        self.template = template
        self.sort_order = sort_order
        self.rule_id = f"checklist_template:{template.code}"
        self._applicability_policy = applicability_policy
        self._completion_policy = completion_policy
        self._metadata_policy = metadata_policy

    def evaluate(self, context: ChecklistRuleContext) -> RuleResult[ChecklistRuleDecision]:
        upload_count = context.upload_counts.get(self.template.code, 0)
        applicability = self._applicability_policy.evaluate(self.template, context.facts)
        completion_status = self._completion_policy.evaluate(
            context.existing_status_by_code.get(self.template.code),
            self.template,
            applicability,
            context.facts,
            upload_count,
        )
        return RuleResult(
            rule_id=self.rule_id,
            outcome=ChecklistRuleDecision(
                template=self.template,
                sort_order=self.sort_order,
                applicability=applicability,
                completion_status=completion_status,
                metadata=self._metadata_policy.build(self.template, context.facts, upload_count),
            ),
        )


class ChecklistRuleEngine:
    def __init__(self, templates: list[ChecklistTemplate] | None = None) -> None:
        applicability_policy = FactApplicabilityPolicy()
        completion_policy = ChecklistCompletionPolicy()
        packet_grouping = PacketGroupingPolicy()
        metadata_policy = ChecklistMetadataPolicy(packet_grouping)
        self._engine = RuleEngine(
            ChecklistTemplateRule(
                template=template,
                sort_order=sort_order,
                applicability_policy=applicability_policy,
                completion_policy=completion_policy,
                metadata_policy=metadata_policy,
            )
            for sort_order, template in enumerate(templates or CHECKLIST_TEMPLATES, start=1)
        )

    def evaluate(self, context: ChecklistRuleContext) -> list[ChecklistRuleDecision]:
        return [result.outcome for result in self._engine.evaluate(context)]

