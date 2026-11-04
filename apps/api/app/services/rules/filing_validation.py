"""Rule engine that runs filing validators."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from uuid import UUID

from sqlmodel import Session

from app.services.rules.core import RuleEngine, RuleResult

FormValidator = Callable[[Session, UUID, Path | None], dict[str, Any]]
DefaultTemplateResolver = Callable[[str], Path | None]
UnsupportedFormValidator = Callable[[str, Path | None], dict[str, Any]]


@dataclass(frozen=True)
class FilingValidationContext:
    session: Session
    case_id: UUID
    template_paths: dict[str, str]
    default_template_path: DefaultTemplateResolver
    unsupported_form_result: UnsupportedFormValidator

    def template_path_for(self, form_code: str) -> Path | None:
        if form_code in self.template_paths:
            return Path(self.template_paths[form_code])
        return self.default_template_path(form_code)


class FormValidationDispatchRule:
    def __init__(self, form_code: str, validators: dict[str, FormValidator]) -> None:
        self.form_code = form_code
        self.rule_id = f"filing_validation:{form_code}"
        self._validators = validators

    def evaluate(self, context: FilingValidationContext) -> RuleResult[dict[str, Any]]:
        template_path = context.template_path_for(self.form_code)
        validator = self._validators.get(self.form_code)
        if validator is None:
            result = context.unsupported_form_result(self.form_code, template_path)
        else:
            result = validator(context.session, context.case_id, template_path)
        return RuleResult(self.rule_id, result)


class FilingValidationRuleEngine:
    def __init__(self, validators: dict[str, FormValidator]) -> None:
        self._validators = validators

    def evaluate(self, context: FilingValidationContext, form_codes: list[str]) -> list[dict[str, Any]]:
        engine = RuleEngine(FormValidationDispatchRule(form_code, self._validators) for form_code in form_codes)
        return [result.outcome for result in engine.evaluate(context)]

