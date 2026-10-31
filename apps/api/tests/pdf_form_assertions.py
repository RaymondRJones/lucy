from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

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
        if field_name in actual and str(expected_value) not in actual[field_name]
    }
    mismatched_appearances = {
        field_name: sorted(appearances.get(field_name, set()))
        for field_name, expected_value in checkbox_values.items()
        if str(expected_value) not in appearances.get(field_name, set())
    }

    assert missing == []
    assert mismatched == {}
    assert mismatched_appearances == {}


@dataclass(frozen=True)
class PdfWidget:
    page: int
    name: str
    full_name: str
    field_type: str
    value: str
    appearance_state: str
    on_states: frozenset[str]
    tooltip: str
    max_length: int | None
    options: tuple[str, ...]
    appearance_text: str


def _inherited(annotation: Any, key: str) -> Any:
    current = annotation
    for _ in range(16):
        if current is None:
            return None
        value = current.get(key)
        if value is not None:
            return value
        parent = current.get("/Parent")
        current = parent.get_object() if parent else None
    return None


def _appearance_stream(annotation: Any) -> Any:
    normal = (annotation.get("/AP") or {}).get("/N")
    return normal.get_object() if normal is not None else None


def _option_values(annotation: Any) -> tuple[str, ...]:
    values = []
    for option in _inherited(annotation, "/Opt") or []:
        option = option.get_object() if hasattr(option, "get_object") else option
        values.append(str(option[0] if isinstance(option, list) else option))
    return tuple(values)


def read_pdf_widgets(path: Path) -> list[PdfWidget]:
    widgets: list[PdfWidget] = []
    for page_number, page in enumerate(PdfReader(path).pages, start=1):
        for annotation_ref in page.get("/Annots") or []:
            annotation = annotation_ref.get_object()
            name = str(annotation.get("/T") or "")
            if annotation.get("/Subtype") != "/Widget" or not name:
                continue
            field_type = str(_inherited(annotation, "/FT") or "")
            stream = _appearance_stream(annotation)
            on_states: frozenset[str] = frozenset()
            appearance_text = ""
            if field_type == "/Btn" and stream is not None:
                on_states = frozenset(str(key) for key in stream.keys() if str(key) != "/Off")
            elif stream is not None and hasattr(stream, "get_data"):
                appearance_text = stream.get_data().decode("latin-1")
            raw_value = _inherited(annotation, "/V")
            max_length = _inherited(annotation, "/MaxLen")
            widgets.append(
                PdfWidget(
                    page=page_number,
                    name=name,
                    full_name=_annotation_full_name(annotation) or name,
                    field_type=field_type,
                    value="" if raw_value is None else str(raw_value),
                    appearance_state=str(annotation.get("/AS") or ""),
                    on_states=on_states,
                    tooltip=" ".join(str(annotation.get("/TU") or "").split()),
                    max_length=int(max_length) if max_length is not None else None,
                    options=_option_values(annotation),
                    appearance_text=appearance_text,
                )
            )
    return widgets


def _is_barcode(widget: PdfWidget) -> bool:
    return "BarCode" in widget.name


def filled_text_values(widgets: list[PdfWidget]) -> dict[str, str]:
    return {
        widget.full_name: widget.value
        for widget in widgets
        if widget.field_type in {"/Tx", "/Ch"} and widget.value.strip() and not _is_barcode(widget)
    }


def checked_boxes(widgets: list[PdfWidget]) -> dict[str, str]:
    return {
        widget.full_name: widget.appearance_state
        for widget in widgets
        if widget.field_type == "/Btn" and widget.appearance_state not in {"", "/Off"}
    }


def assert_widgets_will_print(widgets: list[PdfWidget]) -> None:
    """A value stored in /V is not enough: USCIS receives what the saved appearance draws on paper."""
    problems: list[str] = []
    for widget in widgets:
        if _is_barcode(widget):
            continue
        label = f"p{widget.page} {widget.name}"
        if widget.field_type == "/Btn":
            if widget.appearance_state not in {"", "/Off"} and widget.appearance_state not in widget.on_states:
                problems.append(f"{label}: state {widget.appearance_state!r} is not one of {sorted(widget.on_states)}")
            continue
        if not widget.value.strip():
            continue
        if widget.max_length is not None and len(widget.value) > widget.max_length:
            problems.append(f"{label}: {len(widget.value)} characters exceeds the {widget.max_length} limit")
        if widget.field_type == "/Ch" and widget.options and widget.value not in widget.options:
            problems.append(f"{label}: {widget.value!r} is not a dropdown option")
        if widget.field_type == "/Tx" and not re.search(r"\bT[jJ]\b", widget.appearance_text):
            problems.append(f"{label}: {widget.value!r} has no drawn text")
    assert problems == []


DATE_TOOLTIP = re.compile(r"2[- ]digit month", re.IGNORECASE)
US_DATE = re.compile(r"(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])/\d{4}")
LEAKED_VALUE = re.compile(r"^(True|False|None)$|Sample response|\{'|\['|\d{4}-\d{2}-\d{2}")


def assert_widget_values_are_formatted(widgets: list[PdfWidget]) -> None:
    problems: list[str] = []
    for widget in widgets:
        if _is_barcode(widget) or not widget.value.strip() or widget.field_type not in {"/Tx", "/Ch"}:
            continue
        label = f"p{widget.page} {widget.name}"
        if DATE_TOOLTIP.search(widget.tooltip) and widget.value != "PRESENT" and not US_DATE.fullmatch(widget.value):
            problems.append(f"{label}: date {widget.value!r} is not MM/DD/YYYY")
        if LEAKED_VALUE.search(widget.value):
            problems.append(f"{label}: raw value {widget.value!r}")
    assert problems == []
