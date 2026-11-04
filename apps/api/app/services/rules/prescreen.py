"""Rules that evaluate prescreen answers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.content.prescreen import PRESCREEN_QUESTIONS, PRESCREEN_SOURCES, PRESCREEN_VERIFIED_ON, PRESCREEN_VERSION
from app.models.entities import utcnow
from app.services.case_facts import value_is_answered
from app.services.rules.core import RuleEngine, RuleResult

I130_ALREADY_FILED_STATUSES = {"pending", "approved", "filed"}


class PrescreenConditionMatcher:
    def scalar_matches(self, actual: Any, expected: Any) -> bool:
        if isinstance(expected, list):
            return actual in expected
        if isinstance(expected, dict):
            if "in" in expected:
                return actual in expected["in"]
            if "not" in expected:
                return actual != expected["not"]
            if "equals" in expected:
                return actual == expected["equals"]
        return actual == expected

    def matches_visibility(self, actual: Any, expected: Any) -> bool:
        return self.scalar_matches(actual, expected)

    def risk_matches(self, value: Any, flag_when: Any) -> bool:
        if flag_when is None or not value_is_answered(value):
            return False
        if flag_when == "not_us_citizen":
            return value != "us_citizen"
        if flag_when == "not_usa":
            return value != "usa"
        if isinstance(flag_when, dict):
            if "in" in flag_when:
                return value in flag_when["in"]
            if "not" in flag_when:
                return value != flag_when["not"]
            if "equals" in flag_when:
                return value == flag_when["equals"]
            if "contains_any" in flag_when and isinstance(value, list):
                return bool(set(value).intersection(set(flag_when["contains_any"])))
            if "field_equals" in flag_when:
                condition = flag_when["field_equals"]
                return self.field_value(value, condition.get("key")) == condition.get("value")
            if "field_lte" in flag_when:
                condition = flag_when["field_lte"]
                actual = self.field_value(value, condition.get("key"))
                try:
                    return actual is not None and float(actual) <= float(condition.get("value"))
                except (TypeError, ValueError):
                    return False
        return value == flag_when

    def field_value(self, value: Any, key: str | None) -> Any:
        if not isinstance(value, dict):
            return None
        return value.get(key)


@dataclass(frozen=True)
class PrescreenQuestionContext:
    answers: dict[str, Any]


@dataclass(frozen=True)
class PrescreenQuestionDecision:
    question: dict[str, Any]
    is_visible: bool
    is_answered: bool
    eliminated_question: dict[str, Any] | None
    flags: list[dict[str, Any]]


class PrescreenQuestionRule:
    def __init__(self, question: dict[str, Any], matcher: PrescreenConditionMatcher) -> None:
        self.question = question
        self.rule_id = f"prescreen_question:{question['id']}"
        self._matcher = matcher

    def evaluate(self, context: PrescreenQuestionContext) -> RuleResult[PrescreenQuestionDecision]:
        is_visible = self._is_visible(context.answers)
        return RuleResult(
            rule_id=self.rule_id,
            outcome=PrescreenQuestionDecision(
                question=self.question,
                is_visible=is_visible,
                is_answered=is_visible and self._is_answered(context.answers),
                eliminated_question=None if is_visible else self._eliminated_question(),
                flags=self._matching_flags(context.answers.get(self.question["id"])) if is_visible else [],
            ),
        )

    def _is_visible(self, answers: dict[str, Any]) -> bool:
        visible_when = self.question.get("visible_when") or {}
        return all(
            self._matcher.matches_visibility(answers.get(key), expected)
            for key, expected in visible_when.items()
        )

    def _is_answered(self, answers: dict[str, Any]) -> bool:
        value = answers.get(self.question["id"])
        if self.question.get("answer_type") != "field_group":
            return value_is_answered(value)
        if not isinstance(value, dict):
            return False
        required_fields = [field for field in self.question.get("fields", []) if field.get("required", True)]
        if not required_fields:
            return value_is_answered(value)
        return all(value_is_answered(value.get(field["key"])) for field in required_fields)

    def _eliminated_question(self) -> dict[str, Any]:
        return {
            "question_id": self.question["id"],
            "label": self.question["label"],
            "reason": self.question.get("elimination_text") or "Eliminated by earlier answers.",
        }

    def _matching_flags(self, value: Any) -> list[dict[str, Any]]:
        flags: list[dict[str, Any]] = []
        if self._matcher.risk_matches(value, self.question.get("flag_when")):
            flags.append(self._build_flag())
        for rule in self.question.get("flag_rules") or []:
            if self._matcher.risk_matches(value, rule.get("when")):
                flags.append(self._build_flag(rule))
        return flags

    def _build_flag(self, rule: dict[str, Any] | None = None) -> dict[str, Any]:
        rule = rule or {}
        return {
            "code": rule.get("code") or self.question.get("flag_code") or self.question["id"],
            "severity": rule.get("severity") or self.question.get("flag_severity") or "important",
            "category": rule.get("category") or self.question.get("flag_category") or "outside_happy_path",
            "question_id": self.question["id"],
            "title": rule.get("title") or self.question.get("flag_title") or "Answer is outside the standard path",
            "description": rule.get("description")
            or self.question.get("flag_description")
            or (
                f"The answer to '{self.question['label']}' does not match the standard U.S.-citizen-spouse, "
                "foreign-spouse-inside-the-United-States path Lucy is designed to handle."
            ),
        }


@dataclass
class PrescreenBranchState:
    included_forms: list[str] = field(default_factory=lambda: ["form_i485", "form_i864", "form_g1145"])
    eliminated_forms: list[dict[str, str]] = field(default_factory=list)
    next_steps: list[dict[str, str]] = field(default_factory=list)


class PrescreenBranchRule(Protocol):
    def apply(self, answers: dict[str, Any], state: PrescreenBranchState) -> None:
        """Mutate branch state in order."""


class I130FilingBranchRule:
    def apply(self, answers: dict[str, Any], state: PrescreenBranchState) -> None:
        i130_status = answers.get("i130_filing_status") or "not_filed"
        if i130_status == "not_filed":
            state.included_forms = ["form_i130", "form_i130a", *state.included_forms]
            state.eliminated_forms.append(
                {
                    "form_code": "i130_receipt_notice",
                    "label": "I-130 receipt/approval notice",
                    "reason": "Not needed yet because this branch prepares the I-130 and I-130A with the packet.",
                }
            )
            state.next_steps.append(
                {
                    "label": "Prepare I-130 and I-130A",
                    "description": "Because the spouse petition has not been filed, the packet plan keeps both family-petition forms active.",
                }
            )
        elif i130_status in I130_ALREADY_FILED_STATUSES:
            state.eliminated_forms.extend(
                [
                    {
                        "form_code": "form_i130",
                        "label": "Form I-130 draft",
                        "reason": "Eliminated because the spouse petition was already filed.",
                    },
                    {
                        "form_code": "form_i130a",
                        "label": "Form I-130A draft",
                        "reason": "Eliminated because the spouse petition was already filed.",
                    },
                ]
            )
            state.next_steps.append(
                {
                    "label": "Upload I-130 receipt or approval evidence",
                    "description": "Use the notice details as the underlying petition reference for the adjustment packet.",
                }
            )
        elif i130_status in {"denied_revoked_withdrawn", "unknown"}:
            paused_forms = [
                "form_i130",
                "form_i130a",
                "form_i485",
                "form_i864",
                "form_g1145",
                "form_i765",
                "form_i131",
            ]
            state.included_forms = []
            state.eliminated_forms.extend(
                {
                    "form_code": form_code,
                    "label": form_code.replace("form_", "Form ").upper(),
                    "reason": "Paused because the I-130 status needs review before packet generation.",
                }
                for form_code in paused_forms
            )
            state.next_steps.append(
                {
                    "label": "Pause for petition-history review",
                    "description": "Do not generate packet documents from the happy-path flow until the I-130 status and history are understood.",
                }
            )
        else:
            state.next_steps.append(
                {
                    "label": "Confirm I-130 status",
                    "description": "Lucy cannot choose the right branch until the spouse petition status is clear.",
                }
            )


class OptionalBenefitBranchRule:
    def apply(self, answers: dict[str, Any], state: PrescreenBranchState) -> None:
        if not state.included_forms:
            return
        if answers.get("wants_i765", True):
            state.included_forms.append("form_i765")
        else:
            state.eliminated_forms.append(
                {
                    "form_code": "form_i765",
                    "label": "Form I-765",
                    "reason": "Eliminated because work authorization was not requested.",
                }
            )

        if answers.get("wants_i131", False):
            state.included_forms.append("form_i131")
        else:
            state.eliminated_forms.append(
                {
                    "form_code": "form_i131",
                    "label": "Form I-131",
                    "reason": "Eliminated because advance parole was not requested.",
                }
            )


class PrescreenStatusPolicy:
    def evaluate(self, flags: list[dict[str, Any]], completion_pct: int) -> str:
        if any(flag.get("severity") == "critical" for flag in flags):
            return "blocked_needs_review"
        if flags:
            return "needs_review"
        if completion_pct < 100:
            return "incomplete"
        return "happy_path_ready"


class PrescreenRuleEngine:
    def __init__(
        self,
        questions: list[dict[str, Any]] | None = None,
        branch_rules: list[PrescreenBranchRule] | None = None,
    ) -> None:
        matcher = PrescreenConditionMatcher()
        self._questions = questions or PRESCREEN_QUESTIONS
        self._question_engine = RuleEngine(
            PrescreenQuestionRule(question, matcher) for question in self._questions
        )
        self._branch_rules = branch_rules or [
            I130FilingBranchRule(),
            OptionalBenefitBranchRule(),
        ]
        self._status_policy = PrescreenStatusPolicy()

    def evaluate(self, answers: dict[str, Any]) -> dict[str, Any]:
        question_decisions = [result.outcome for result in self._question_engine.evaluate(PrescreenQuestionContext(answers))]
        visible_questions = [decision.question for decision in question_decisions if decision.is_visible]
        eliminated_questions = [
            decision.eliminated_question
            for decision in question_decisions
            if decision.eliminated_question is not None
        ]
        flags = [flag for decision in question_decisions for flag in decision.flags]
        answered_visible = [decision for decision in question_decisions if decision.is_visible and decision.is_answered]
        completion_pct = int(round((len(answered_visible) / len(visible_questions)) * 100)) if visible_questions else 100

        branch_state = PrescreenBranchState()
        for rule in self._branch_rules:
            rule.apply(answers, branch_state)

        return {
            "version": PRESCREEN_VERSION,
            "verified_on": PRESCREEN_VERIFIED_ON,
            "sources": PRESCREEN_SOURCES,
            "status": self._status_policy.evaluate(flags, completion_pct),
            "completion_pct": completion_pct,
            "visible_questions": visible_questions,
            "eliminated_questions": eliminated_questions,
            "flags": flags,
            "included_forms": branch_state.included_forms,
            "eliminated_forms": branch_state.eliminated_forms,
            "next_steps": branch_state.next_steps,
            "generated_at": utcnow().isoformat(),
        }
