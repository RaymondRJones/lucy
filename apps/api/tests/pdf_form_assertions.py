from __future__ import annotations

from pathlib import Path
from typing import Mapping

from pypdf import PdfReader

from app.services.i485_pdf import _annotation_full_name, _template_field_names


def template_field_names(path: Path) -> set[str]:
    return _template_field_names(PdfReader(path))


def pdf_field_values(path: Path) -> dict[str, set[str]]:
    values: dict[str, set[str]] = {}
    reader = PdfReader(path)
    for page in reader.pages:
        for annotation_ref in page.get("/Annots") or []:
            annotation = annotation_ref.get_object()
            raw_value = annotation.get("/V")
            value = "" if raw_value is None else str(raw_value)
            field_name = annotation.get("/T")
            full_name = _annotation_full_name(annotation)
            if field_name:
                values.setdefault(str(field_name), set()).add(value)
            if full_name:
                values.setdefault(full_name, set()).add(value)
    return values


def pdf_field_appearance_states(path: Path) -> dict[str, set[str]]:
    values: dict[str, set[str]] = {}
    reader = PdfReader(path)
    for page in reader.pages:
        for annotation_ref in page.get("/Annots") or []:
            annotation = annotation_ref.get_object()
            raw_value = annotation.get("/AS")
            value = "" if raw_value is None else str(raw_value)
            field_name = annotation.get("/T")
            full_name = _annotation_full_name(annotation)
            if field_name:
                values.setdefault(str(field_name), set()).add(value)
            if full_name:
                values.setdefault(full_name, set()).add(value)
    return values


def _same_state(expected: object, actual: set[str]) -> bool:
    # Generation writes the spelling each template defines, such as "/APT " for a requested "/ APT ".
    wanted = str(expected).replace("/", "").strip()
    return any(state.replace("/", "").strip() == wanted for state in actual)


def assert_pdf_field_values(
    path: Path,
    *,
    text_values: Mapping[str, str],
    checkbox_values: Mapping[str, str],
) -> None:
    actual = pdf_field_values(path)
    appearances = pdf_field_appearance_states(path)
    expected = {**dict(text_values), **dict(checkbox_values)}
    missing = sorted(field_name for field_name in expected if field_name not in actual)
    mismatched = {
        field_name: sorted(actual[field_name])
        for field_name, expected_value in expected.items()
        if field_name in actual
        and str(expected_value) not in actual[field_name]
        and not (field_name in checkbox_values and _same_state(expected_value, actual[field_name]))
    }
    mismatched_appearances = {
        field_name: sorted(appearances.get(field_name, set()))
        for field_name, expected_value in checkbox_values.items()
        if not _same_state(expected_value, appearances.get(field_name, set()))
    }

    assert missing == []
    assert mismatched == {}
    assert mismatched_appearances == {}
