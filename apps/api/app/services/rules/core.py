from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Iterable, Protocol, TypeVar


ContextT = TypeVar("ContextT")
OutcomeT = TypeVar("OutcomeT")


@dataclass(frozen=True)
class RuleResult(Generic[OutcomeT]):
    rule_id: str
    outcome: OutcomeT


class Rule(Protocol[ContextT, OutcomeT]):
    rule_id: str

    def evaluate(self, context: ContextT) -> RuleResult[OutcomeT] | None:
        """Evaluate this rule for the provided context."""


class RuleEngine(Generic[ContextT, OutcomeT]):
    """Runs ordered rules and returns their non-empty results."""

    def __init__(self, rules: Iterable[Rule[ContextT, OutcomeT]]) -> None:
        self._rules = tuple(rules)

    def evaluate(self, context: ContextT) -> list[RuleResult[OutcomeT]]:
        results: list[RuleResult[OutcomeT]] = []
        for rule in self._rules:
            result = rule.evaluate(context)
            if result is not None:
                results.append(result)
        return results

