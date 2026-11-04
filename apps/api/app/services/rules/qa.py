"""Rules that produce QA issues."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable
from uuid import UUID

from sqlmodel import Session

from app.content.uscis_requirements import USCIS_REQUIREMENT_BY_CHECKLIST_CODE
from app.models.entities import CaseChecklistItem, ChecklistProgressStatus, QAIssue, UploadedDocument
from app.services.rules.core import RuleEngine, RuleResult

REFERENCE_REVIEW_CODES = {"review_current_fees", "review_form_editions"}

BuildIssue = Callable[[UUID, str, str, str, str, str | None], QAIssue]


@dataclass
class QARuleDependencies:
    build_issue: BuildIssue
    item_is_satisfied: Callable[[CaseChecklistItem, dict[str, list[UploadedDocument]], dict[str, Any]], bool]
    names_match: Callable[[str | None, str | None], bool]
    source_backed_consistency_issues: Callable[[UUID, list[UploadedDocument]], tuple[list[QAIssue], dict[str, UploadedDocument]]]
    address_history_issues: Callable[[UUID, list[UploadedDocument]], list[QAIssue]]
    intake_to_document_issues: Callable[[UUID, dict[str, Any], list[UploadedDocument]], list[QAIssue]]
    intake_address_history_issues: Callable[[UUID, dict[str, Any], list[UploadedDocument]], list[QAIssue]]
    i485_ingestion_issues: Callable[[Session, UUID], list[QAIssue]]
    prescreen_critical_issues: Callable[[Session, UUID], list[QAIssue]]


@dataclass
class QARuleContext:
    session: Session
    case_id: UUID
    items: list[CaseChecklistItem]
    uploads: list[UploadedDocument]
    representative_uploads: list[UploadedDocument]
    upload_map: dict[str, list[UploadedDocument]]
    facts: dict[str, Any]
    merged: dict[str, Any]
    expected_petitioner_name: str
    expected_beneficiary_name: str
    dependencies: QARuleDependencies
    verification_sources: dict[str, UploadedDocument] = field(default_factory=dict)


class ChecklistReferenceSyncRule:
    rule_id = "qa:sync_reference_review_checklist_status"

    def evaluate(self, context: QARuleContext) -> RuleResult[list[QAIssue]]:
        for item in context.items:
            if item.code == "review_current_fees":
                item.completion_status = (
                    ChecklistProgressStatus.complete.value
                    if context.facts.get("reviewed_current_fees")
                    else ChecklistProgressStatus.not_started.value
                )
            if item.code == "review_form_editions":
                item.completion_status = (
                    ChecklistProgressStatus.complete.value
                    if context.facts.get("reviewed_current_form_editions")
                    else ChecklistProgressStatus.not_started.value
                )
            item.updated_at = datetime.now(UTC)
            context.session.add(item)
        return RuleResult(self.rule_id, [])


class MissingRequiredChecklistItemsRule:
    rule_id = "qa:missing_required_checklist_items"

    def evaluate(self, context: QARuleContext) -> RuleResult[list[QAIssue]]:
        issues: list[QAIssue] = []
        for item in context.items:
            if item.applicability != "required":
                continue
            if item.code in REFERENCE_REVIEW_CODES:
                if not context.dependencies.item_is_satisfied(item, context.upload_map, context.facts):
                    issues.append(
                        context.dependencies.build_issue(
                            context.case_id,
                            "important",
                            item.code,
                            "Current USCIS references still need confirmation",
                            (
                                "Before filing, confirm the live USCIS fee schedule and form edition dates so the packet "
                                "is not relying on stale references."
                            ),
                            item.code,
                        )
                    )
                continue
            if context.dependencies.item_is_satisfied(item, context.upload_map, context.facts):
                continue
            severity = "recommended" if item.category == "marriage_evidence" else "blocking"
            issues.append(
                context.dependencies.build_issue(
                    context.case_id,
                    severity,
                    f"missing_{item.code}",
                    f"Missing {item.label}",
                    f"Upload a document for '{item.label}' so the packet is complete.",
                    item.code,
                )
            )
        return RuleResult(self.rule_id, issues)


class ComplexCaseEscalationRule:
    rule_id = "qa:complex_case_escalation"

    def evaluate(self, context: QARuleContext) -> RuleResult[list[QAIssue]] | None:
        if not context.facts.get("complex_case"):
            return None
        return RuleResult(
            self.rule_id,
            [
                context.dependencies.build_issue(
                    context.case_id,
                    "blocking",
                    "complex_case_escalation",
                    "This case may need professional legal review",
                    (
                        "One or more intake answers point to a higher-risk scenario. The workflow can still organize "
                        "documents, but a licensed immigration attorney should review strategy."
                    ),
                    None,
                )
            ],
        )


class SourceBackedDocumentConsistencyRule:
    rule_id = "qa:source_backed_document_consistency"

    def evaluate(self, context: QARuleContext) -> RuleResult[list[QAIssue]]:
        issues, sources = context.dependencies.source_backed_consistency_issues(
            context.case_id,
            context.representative_uploads,
        )
        context.verification_sources.update(sources)
        return RuleResult(self.rule_id, issues)


class AddressHistoryUploadRule:
    rule_id = "qa:uploaded_address_history"

    def evaluate(self, context: QARuleContext) -> RuleResult[list[QAIssue]]:
        return RuleResult(
            self.rule_id,
            context.dependencies.address_history_issues(context.case_id, context.representative_uploads),
        )


class IntakeDocumentConsistencyRule:
    rule_id = "qa:intake_document_consistency"

    def evaluate(self, context: QARuleContext) -> RuleResult[list[QAIssue]]:
        return RuleResult(
            self.rule_id,
            context.dependencies.intake_to_document_issues(
                context.case_id,
                context.merged,
                context.representative_uploads,
            ),
        )


class IntakeAddressHistoryRule:
    rule_id = "qa:intake_address_history"

    def evaluate(self, context: QARuleContext) -> RuleResult[list[QAIssue]]:
        return RuleResult(
            self.rule_id,
            context.dependencies.intake_address_history_issues(
                context.case_id,
                context.merged,
                context.representative_uploads,
            ),
        )


class I485IngestionFlagRule:
    rule_id = "qa:i485_ingestion_flags"

    def evaluate(self, context: QARuleContext) -> RuleResult[list[QAIssue]]:
        return RuleResult(
            self.rule_id,
            context.dependencies.i485_ingestion_issues(context.session, context.case_id),
        )


class PrescreenCriticalFlagRule:
    rule_id = "qa:prescreen_critical_flags"

    def evaluate(self, context: QARuleContext) -> RuleResult[list[QAIssue]]:
        return RuleResult(
            self.rule_id,
            context.dependencies.prescreen_critical_issues(context.session, context.case_id),
        )


class PerUploadQualityRule:
    rule_id = "qa:per_upload_quality"

    def evaluate(self, context: QARuleContext) -> RuleResult[list[QAIssue]]:
        issues: list[QAIssue] = []
        for upload in context.uploads:
            issues.extend(self._issues_for_upload(context, upload))
        return RuleResult(self.rule_id, issues)

    def _issues_for_upload(self, context: QARuleContext, upload: UploadedDocument) -> list[QAIssue]:
        issues: list[QAIssue] = []
        extracted = upload.extracted_fields or {}
        if upload.requires_translation and not upload.has_translation:
            issues.append(
                context.dependencies.build_issue(
                    context.case_id,
                    "important",
                    f"translation_missing_{upload.id}",
                    "A translated document appears to be missing",
                    "This upload appears to be non-English, but no certified English translation was marked as attached.",
                    upload.checklist_item_code,
                )
            )

        petitioner_name = extracted.get("petitioner_name")
        beneficiary_name = extracted.get("beneficiary_name")
        if "petitioner_name" not in context.verification_sources and not context.dependencies.names_match(
            context.expected_petitioner_name,
            petitioner_name,
        ):
            issues.append(
                context.dependencies.build_issue(
                    context.case_id,
                    "important",
                    f"petitioner_name_mismatch_{upload.id}",
                    "Petitioner name mismatch detected",
                    "The uploaded document metadata does not match the petitioner's intake name. Double-check spelling and consistency across forms.",
                    upload.checklist_item_code,
                )
            )
        if "beneficiary_name" not in context.verification_sources and not context.dependencies.names_match(
            context.expected_beneficiary_name,
            beneficiary_name,
        ):
            issues.append(
                context.dependencies.build_issue(
                    context.case_id,
                    "important",
                    f"beneficiary_name_mismatch_{upload.id}",
                    "Beneficiary name mismatch detected",
                    "The uploaded document metadata does not match the beneficiary's intake name. Double-check spelling and consistency across forms.",
                    upload.checklist_item_code,
                )
            )
        if upload.document_type and upload.document_type.startswith("form_") and extracted.get("signed") is False:
            issues.append(
                context.dependencies.build_issue(
                    context.case_id,
                    "important",
                    f"missing_signature_{upload.id}",
                    "A form may be missing a signature",
                    "The uploaded form was marked as unsigned. Review the final printed packet before mailing.",
                    upload.checklist_item_code,
                )
            )

        requirement = USCIS_REQUIREMENT_BY_CHECKLIST_CODE.get(upload.checklist_item_code or "")
        detected_edition = extracted.get("form_edition")
        if requirement and detected_edition and detected_edition != requirement["accepted_edition"]:
            issues.append(
                context.dependencies.build_issue(
                    context.case_id,
                    "blocking",
                    f"outdated_form_edition_{upload.id}",
                    f"{requirement['label']} appears to use a non-current edition",
                    (
                        f"USCIS was verified on {requirement['verified_on']} with accepted edition "
                        f"{requirement['accepted_edition']}, but this upload appears to be {detected_edition}."
                    ),
                    upload.checklist_item_code,
                )
            )
        return issues


class QARuleEngine:
    def __init__(self) -> None:
        self._engine = RuleEngine(
            [
                ChecklistReferenceSyncRule(),
                MissingRequiredChecklistItemsRule(),
                ComplexCaseEscalationRule(),
                SourceBackedDocumentConsistencyRule(),
                AddressHistoryUploadRule(),
                IntakeDocumentConsistencyRule(),
                IntakeAddressHistoryRule(),
                I485IngestionFlagRule(),
                PrescreenCriticalFlagRule(),
                PerUploadQualityRule(),
            ]
        )

    def evaluate(self, context: QARuleContext) -> list[QAIssue]:
        issues: list[QAIssue] = []
        for result in self._engine.evaluate(context):
            issues.extend(result.outcome)
        return issues
