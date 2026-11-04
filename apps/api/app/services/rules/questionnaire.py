"""Rules that evaluate form questionnaires."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.services.rules.core import RuleEngine, RuleResult

ValueIsAnswered = Callable[[Any], bool]
RiskMatcher = Callable[[Any, Any], bool]
ConditionalRequiredIds = Callable[[dict[str, Any]], set[str]]
ExtraQuestionFlags = Callable[[dict[str, Any], Any], list[dict[str, Any]]]
RiskTitle = Callable[[dict[str, Any]], str]
RiskDescription = Callable[[dict[str, Any]], str]


@dataclass(frozen=True)
class QuestionnaireEvaluationConfig:
    form_key: str
    ready_readiness: str
    questions: list[dict[str, Any]]
    pages: list[dict[str, Any]]
    blocking_risk_codes: set[str]
    outside_niche_risk_codes: set[str]
    value_is_answered: ValueIsAnswered
    risk_matches: RiskMatcher
    risk_title: RiskTitle
    risk_description: RiskDescription
    conditional_required_ids: ConditionalRequiredIds = lambda answers: set()
    extra_question_flags: ExtraQuestionFlags = lambda question, value: []


@dataclass
class QuestionnaireEvaluationContext:
    answers: dict[str, Any]
    config: QuestionnaireEvaluationConfig
    conditional_required_ids: set[str] = field(init=False)
    required_questions: list[dict[str, Any]] = field(default_factory=list)
    answered_required: list[dict[str, Any]] = field(default_factory=list)
    flags: list[dict[str, Any]] = field(default_factory=list)
    mapped_fields: list[dict[str, str]] = field(default_factory=list)
    page_summaries: list[dict[str, Any]] = field(default_factory=list)
    readiness: str = ""

    def __post_init__(self) -> None:
        self.conditional_required_ids = self.config.conditional_required_ids(self.answers)

    def question_is_required(self, question: dict[str, Any]) -> bool:
        return bool(question.get("required")) or question["id"] in self.conditional_required_ids

    def value_is_answered(self, value: Any) -> bool:
        return self.config.value_is_answered(value)


class RequiredQuestionRule:
    rule_id = "questionnaire:required_answers"

    def evaluate(self, context: QuestionnaireEvaluationContext) -> RuleResult[dict[str, int]]:
        context.required_questions = [
            question for question in context.config.questions if context.question_is_required(question)
        ]
        context.answered_required = [
            question
            for question in context.required_questions
            if context.value_is_answered(context.answers.get(question["id"]))
        ]
        return RuleResult(
            self.rule_id,
            {
                "required_questions": len(context.required_questions),
                "answered_required": len(context.answered_required),
            },
        )


class MappedFieldRule:
    rule_id = "questionnaire:mapped_fields"

    def evaluate(self, context: QuestionnaireEvaluationContext) -> RuleResult[list[dict[str, str]]]:
        for question in context.config.questions:
            value = context.answers.get(question["id"])
            db_path = question.get("db_path")
            if db_path and context.value_is_answered(value):
                context.mapped_fields.append(
                    {
                        "question_id": question["id"],
                        "db_path": db_path,
                        "pdf_ref": question["pdf_ref"],
                    }
                )
        return RuleResult(self.rule_id, context.mapped_fields)


class QuestionFlagRule:
    rule_id = "questionnaire:question_flags"

    def evaluate(self, context: QuestionnaireEvaluationContext) -> RuleResult[list[dict[str, Any]]]:
        for question in context.config.questions:
            value = context.answers.get(question["id"])
            context.flags.extend(context.config.extra_question_flags(question, value))
            if not context.config.risk_matches(value, question.get("risk_when")):
                continue
            risk_code = question.get("risk_code") or question["id"]
            context.flags.append(
                {
                    "code": risk_code,
                    "severity": "blocking" if risk_code in context.config.blocking_risk_codes else "important",
                    "category": "outside_niche"
                    if risk_code in context.config.outside_niche_risk_codes
                    else "risk",
                    "question_id": question["id"],
                    "title": context.config.risk_title(question),
                    "description": context.config.risk_description(question),
                    "pdf_ref": question["pdf_ref"],
                }
            )
        return RuleResult(self.rule_id, context.flags)


class PageSummaryRule:
    rule_id = "questionnaire:page_summaries"

    def evaluate(self, context: QuestionnaireEvaluationContext) -> RuleResult[list[dict[str, Any]]]:
        for index, page in enumerate(context.config.pages, start=1):
            page_required = [
                question for question in page["questions"] if context.question_is_required(question)
            ]
            page_answered = [
                question
                for question in page_required
                if context.value_is_answered(context.answers.get(question["id"]))
            ]
            page_question_ids = {question["id"] for question in page["questions"]}
            page_flags = [flag for flag in context.flags if flag["question_id"] in page_question_ids]
            context.page_summaries.append(
                {
                    "page_number": index,
                    "page_id": page["id"],
                    "title": page["title"],
                    "required_questions": len(page_required),
                    "answered_required": len(page_answered),
                    "flags": page_flags,
                }
            )
        return RuleResult(self.rule_id, context.page_summaries)


class ReadinessRule:
    rule_id = "questionnaire:readiness"

    def evaluate(self, context: QuestionnaireEvaluationContext) -> RuleResult[str]:
        readiness = context.config.ready_readiness
        if any(flag["severity"] == "blocking" for flag in context.flags):
            readiness = "needs_professional_review"
        elif any(flag["category"] == "outside_niche" for flag in context.flags):
            readiness = "outside_standard_niche"
        elif len(context.answered_required) < len(context.required_questions):
            readiness = "incomplete"
        context.readiness = readiness
        return RuleResult(self.rule_id, readiness)


class QuestionnaireRuleEngine:
    def __init__(self) -> None:
        self._engine = RuleEngine(
            [
                RequiredQuestionRule(),
                MappedFieldRule(),
                QuestionFlagRule(),
                PageSummaryRule(),
                ReadinessRule(),
            ]
        )

    def evaluate(self, answers: dict[str, Any], config: QuestionnaireEvaluationConfig) -> dict[str, Any]:
        context = QuestionnaireEvaluationContext(answers=answers, config=config)
        self._engine.evaluate(context)
        required_count = len(context.required_questions)
        answered_count = len(context.answered_required)
        return {
            "required_questions": required_count,
            "answered_required": answered_count,
            "completion_pct": int(round((answered_count / required_count) * 100))
            if required_count
            else 100,
            "readiness": context.readiness,
            "flags": context.flags,
            "page_summaries": context.page_summaries,
            "mapped_fields": context.mapped_fields,
        }

