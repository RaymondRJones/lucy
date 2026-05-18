from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from app.services.rules.case_facts import CaseFactsContext, CaseFactsRuleEngine
from app.services.rules.checklist import ChecklistRuleContext, ChecklistRuleEngine
from app.services.rules.core import RuleEngine, RuleResult
from app.services.rules.filing_validation import FilingValidationContext, FilingValidationRuleEngine
from app.services.rules.prescreen import PrescreenRuleEngine
from app.services.rules.questionnaire import QuestionnaireEvaluationConfig, QuestionnaireRuleEngine


@dataclass(frozen=True)
class SimpleContext:
    include_second: bool


class FirstRule:
    rule_id = "first"

    def evaluate(self, context: SimpleContext) -> RuleResult[str]:
        return RuleResult(self.rule_id, "first")


class OptionalSecondRule:
    rule_id = "second"

    def evaluate(self, context: SimpleContext) -> RuleResult[str] | None:
        if not context.include_second:
            return None
        return RuleResult(self.rule_id, "second")


def test_core_rule_engine_runs_rules_in_order_and_skips_empty_results():
    engine = RuleEngine([FirstRule(), OptionalSecondRule()])

    assert [result.outcome for result in engine.evaluate(SimpleContext(include_second=False))] == ["first"]
    assert [result.outcome for result in engine.evaluate(SimpleContext(include_second=True))] == ["first", "second"]


def test_case_facts_rule_engine_derives_workflow_and_escalation_facts():
    facts = CaseFactsRuleEngine().evaluate(
        CaseFactsContext(
            merged={
                "petitioner_citizenship_status": "us_citizen",
                "beneficiary_location": "usa",
                "beneficiary_entered_us_legally": False,
                "i130_filing_status": "pending",
                "beneficiary_country_of_birth": "Colombia",
                "wants_i765": True,
                "wants_i131": False,
                "first_marriage_for_both": True,
                "marriage_date": "2025-07-20",
                "household_size": 2,
            },
            normalize_country=lambda value: "CO" if str(value).lower() == "colombia" else None,
        )
    )

    assert facts["petitioner_is_us_citizen"] is True
    assert facts["concurrent_filing_eligible"] is False
    assert facts["i130_already_filed"] is True
    assert facts["country_is_colombia"] is True
    assert facts["complex_case"] is True
    assert facts["escalation_flags"]["unlawful_entry"] is True


def test_checklist_rule_engine_groups_pending_i130_relationship_evidence_with_i485():
    decisions = ChecklistRuleEngine().evaluate(
        ChecklistRuleContext(
            facts={
                "i130_filing_status": "pending",
                "i130_already_filed": True,
                "petitioner_is_us_citizen": True,
                "concurrent_filing_eligible": True,
                "has_marriage_date": True,
            },
            upload_counts={},
            existing_status_by_code={},
        )
    )
    by_code = {decision.template.code: decision for decision in decisions}

    assert by_code["form_i130"].applicability == "not_applicable"
    assert by_code["marriage_certificate"].metadata["form_codes"] == ["form_i485"]
    assert by_code["marriage_certificate"].metadata["packet_group_reason"] == "pending_i130_relationship_evidence"


def test_prescreen_rule_engine_pauses_generated_forms_when_i130_status_needs_review():
    evaluation = PrescreenRuleEngine().evaluate(
        {
            "case_basis": "usc_spouse",
            "petitioner_citizenship_status": "us_citizen",
            "relationship_spouse": True,
            "beneficiary_location": "usa",
            "last_entry_type": "visa_admitted",
            "i130_filing_status": "unknown",
        }
    )

    assert evaluation["status"] == "blocked_needs_review"
    assert evaluation["included_forms"] == []
    assert any(item["form_code"] == "form_i485" for item in evaluation["eliminated_forms"])


def test_questionnaire_rule_engine_combines_required_mapped_flag_and_page_summary_rules():
    questions = [
        {
            "id": "name",
            "label": "Name",
            "required": True,
            "db_path": "intake.name",
            "pdf_ref": "Part 1",
        },
        {
            "id": "conditional_detail",
            "label": "Conditional detail",
            "required": False,
            "pdf_ref": "Part 2",
        },
        {
            "id": "risk_answer",
            "label": "Risk answer",
            "required": False,
            "risk_when": True,
            "risk_code": "blocking_risk",
            "pdf_ref": "Part 3",
        },
    ]
    config = QuestionnaireEvaluationConfig(
        form_key="test",
        ready_readiness="ready_for_standard_test_review",
        questions=questions,
        pages=[{"id": "page_1", "title": "Page 1", "questions": questions}],
        blocking_risk_codes={"blocking_risk"},
        outside_niche_risk_codes=set(),
        value_is_answered=lambda value: value not in (None, "", [], {}),
        risk_matches=lambda value, risk_when: risk_when is not None and value == risk_when,
        risk_title=lambda question: "Needs review",
        risk_description=lambda question: f"{question['label']} needs review.",
        conditional_required_ids=lambda answers: {"conditional_detail"} if answers.get("risk_answer") else set(),
    )

    evaluation = QuestionnaireRuleEngine().evaluate(
        {"name": "Avery", "risk_answer": True},
        config,
    )

    assert evaluation["required_questions"] == 2
    assert evaluation["answered_required"] == 1
    assert evaluation["completion_pct"] == 50
    assert evaluation["readiness"] == "needs_professional_review"
    assert evaluation["mapped_fields"] == [
        {"question_id": "name", "db_path": "intake.name", "pdf_ref": "Part 1"}
    ]
    assert evaluation["flags"][0]["code"] == "blocking_risk"
    assert evaluation["page_summaries"][0]["required_questions"] == 2
    assert evaluation["page_summaries"][0]["answered_required"] == 1


def test_filing_validation_rule_engine_dispatches_registered_and_unsupported_forms(tmp_path):
    validators = {
        "form_a": lambda session, case_id, template_path: {
            "form_code": "form_a",
            "template_path": str(template_path),
        }
    }
    context = FilingValidationContext(
        session=None,
        case_id=uuid4(),
        template_paths={"form_a": str(tmp_path / "explicit-a.pdf")},
        default_template_path=lambda form_code: tmp_path / f"{form_code}.pdf",
        unsupported_form_result=lambda form_code, template_path: {
            "form_code": form_code,
            "unsupported": True,
            "template_path": str(template_path),
        },
    )

    results = FilingValidationRuleEngine(validators).evaluate(context, ["form_a", "form_b"])

    assert results == [
        {"form_code": "form_a", "template_path": str(tmp_path / "explicit-a.pdf")},
        {"form_code": "form_b", "unsupported": True, "template_path": str(tmp_path / "form_b.pdf")},
    ]
