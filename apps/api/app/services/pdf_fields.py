"""Field filling, address, and warning helpers shared by every USCIS PDF generator."""

from __future__ import annotations

from datetime import datetime
import re
import textwrap
from typing import Any

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, TextStringObject

from app.services.case_facts import value_is_answered

PART14_ADDITIONAL_INFO_FIELDS = {
    "P14_Line2_AdditionalInfo[0]",
    "P14_Line3_AdditionalInfo[0]",
    "P14_Line4_AdditionalInfo[0]",
    "P14_Line5_AdditionalInfo[0]",
}


PART14_ADDITIONAL_INFO_DA = "/CourierNewPS-BoldMT 7.00 Tf 0 g"


US_STATE_NAME_TO_CODE = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "district of columbia": "DC",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
    "armed forces americas": "AA",
    "armed forces europe": "AE",
    "armed forces pacific": "AP",
    "american samoa": "AS",
    "federated states of micronesia": "FM",
    "guam": "GU",
    "marshall islands": "MH",
    "northern mariana islands": "MP",
    "puerto rico": "PR",
    "palau": "PW",
    "u s virgin islands": "VI",
    "us virgin islands": "VI",
    "virgin islands": "VI",
}


US_STATE_CODES = set(US_STATE_NAME_TO_CODE.values())


def as_pdf_date(value: Any) -> str:
    """Returns a date as MM/DD/YYYY, or the text unchanged if it cannot be parsed."""
    raw = str(value).strip()
    if not raw:
        return ""
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%m/%d/%Y")
        except ValueError:
            continue
    return raw


def normalize_us_state(value: Any) -> str:
    """Returns a two-letter state code, or the text unchanged if it is not a US state."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    upper = raw.upper()
    if upper in US_STATE_CODES:
        return upper
    normalized = " ".join(
        raw.lower().replace(".", " ").replace(",", " ").replace("-", " ").split()
    )
    return US_STATE_NAME_TO_CODE.get(normalized, raw)


def _unit_kind_and_number(value: Any) -> tuple[str, str]:
    raw = str(value or "").strip()
    if not raw:
        return "", ""
    parts = raw.split(maxsplit=1)
    label = parts[0].lower().rstrip(".")
    if label in {"apt", "apartment"}:
        return "apt", parts[1] if len(parts) > 1 else ""
    if label in {"ste", "suite"}:
        return "ste", parts[1] if len(parts) > 1 else ""
    if label in {"fl", "floor"}:
        return "flr", parts[1] if len(parts) > 1 else ""
    return "apt", raw


def add_unit_fields(
    *,
    text_values: dict[str, str],
    checkbox_values: dict[str, str],
    value: Any,
    apt_field: str,
    ste_field: str,
    flr_field: str,
    number_field: str,
) -> None:
    """Fills the number and checks the box for an apartment, suite, or floor answer."""
    unit_kind, unit_number = _unit_kind_and_number(value)
    if not unit_kind:
        return
    text_values[number_field] = unit_number
    if unit_kind == "apt":
        checkbox_values[apt_field] = "/ APT "
    elif unit_kind == "ste":
        checkbox_values[ste_field] = "/ STE "
    elif unit_kind == "flr":
        checkbox_values[flr_field] = "/ FLR "


def join_entry_address(entry: dict[str, Any]) -> str:
    """Returns an entry's address as one line of text."""
    entry = normalized_address_for_pdf(entry)
    parts = [
        entry.get("line1"),
        entry.get("line2"),
        entry.get("city"),
        entry.get("state") or entry.get("province"),
        entry.get("zip") or entry.get("postal_code"),
        entry.get("country"),
    ]
    return ", ".join(str(part).strip() for part in parts if value_is_answered(part))


def employment_continuation_line(entry: dict[str, Any]) -> str:
    """Returns a job as one line for a continuation page."""
    dates = " - ".join(str(entry.get(key, "")).strip() for key in ("from", "to") if value_is_answered(entry.get(key)))
    pieces = [
        str(entry.get("name", "")).strip(),
        str(entry.get("occupation", "")).strip(),
        dates,
        join_entry_address(entry),
    ]
    if value_is_answered(entry.get("financial_support")):
        pieces.append(f"support: {str(entry['financial_support']).strip()}")
    if value_is_answered(entry.get("notes")):
        pieces.append(str(entry["notes"]).strip())
    return " | ".join(piece for piece in pieces if piece)


US_COUNTRY_NAMES = {
    "united states",
    "united states of america",
    "usa",
    "us",
    "u s",
    "u s a",
    "america",
}


def _normalized_country_key(value: Any) -> str:
    return " ".join(str(value or "").lower().replace(".", " ").replace(",", " ").split())


def _is_us_country(value: Any) -> bool:
    return _normalized_country_key(value) in US_COUNTRY_NAMES


def _looks_foreign_address(value: dict[str, Any]) -> bool:
    country = value.get("country")
    if value_is_answered(country):
        return not _is_us_country(country)
    return any(value_is_answered(value.get(key)) for key in ("province", "postal_code"))


def normalized_address_for_pdf(
    value: dict[str, Any],
    *,
    fallback_country: Any = None,
    force_foreign: bool = False,
) -> dict[str, Any]:
    """Returns a copy of an address with US and foreign fields in the form's expected boxes."""
    normalized = dict(value)
    if not value_is_answered(normalized.get("country")) and value_is_answered(fallback_country):
        if force_foreign or _looks_foreign_address(normalized):
            normalized["country"] = fallback_country

    is_foreign = force_foreign or _looks_foreign_address(normalized)
    if is_foreign:
        state = normalized.get("state")
        if not value_is_answered(normalized.get("province")) and value_is_answered(state):
            state_text = str(state).strip()
            if state_text.upper() not in US_STATE_CODES:
                normalized["province"] = state_text
        normalized["state"] = ""
        normalized["zip"] = ""
    return normalized


def entry_has_content(entry: dict[str, Any]) -> bool:
    """Returns whether a list entry holds an answer. A false checkbox alone does not count."""
    # A false checkbox alone is only the form control's default, not an answer.
    return any(value_is_answered(value) and not isinstance(value, bool) for value in entry.values())


def without_notes(entry: dict[str, Any]) -> dict[str, Any]:
    """Returns a copy of a list entry without its free-text note."""
    return {key: value for key, value in entry.items() if key != "notes"}


def template_field_names(reader: PdfReader) -> set[str]:
    """Returns the names of every form field in a blank PDF."""
    names: set[str] = set()
    for full_name, field in (reader.get_fields() or {}).items():
        names.add(str(full_name))
        field_name = field.get("/T")
        if field_name:
            names.add(str(field_name))
    return names


def annotation_full_name(annotation: Any) -> str | None:
    """Returns a field widget's name, including its parent names."""
    parts: list[str] = []
    current = annotation
    seen: set[int] = set()
    while current:
        marker = id(current)
        if marker in seen:
            break
        seen.add(marker)
        field_name = current.get("/T")
        if field_name:
            parts.append(str(field_name))
        parent = current.get("/Parent")
        if not parent:
            break
        current = parent.get_object()
    if not parts:
        return None
    return ".".join(reversed(parts))


def set_text_values(writer: PdfWriter, values: dict[str, str]) -> None:
    """Writes text answers into the matching form fields."""
    for page in writer.pages:
        page_values = {}
        for annotation_ref in page.get("/Annots", []) or []:
            annotation = annotation_ref.get_object()
            field_name = annotation.get("/T")
            full_name = annotation_full_name(annotation)
            selected_name = full_name if full_name in values else None
            if selected_name is None and field_name and str(field_name) in values:
                selected_name = str(field_name)
            if selected_name and field_name:
                if selected_name in PART14_ADDITIONAL_INFO_FIELDS:
                    annotation.update({NameObject("/DA"): TextStringObject(PART14_ADDITIONAL_INFO_DA)})
                page_values[str(field_name)] = values[selected_name]
        if page_values:
            writer.update_page_form_field_values(page, page_values, auto_regenerate=False)


def defined_appearance(annotation: Any, requested: str) -> NameObject:
    """Returns the widget's spelling of a requested checkbox state."""
    # USCIS templates spell unit states inconsistently ("/ APT ", "/APT ", "/STE"), even within one form.
    # A state the widget does not define does not print, so match on the state's letters.
    appearance = annotation.get("/AP")
    normal = appearance.get_object().get("/N") if appearance else None
    if normal is None or requested in normal.get_object():
        return NameObject(requested)
    wanted = requested.replace("/", "").strip()
    for state in normal.get_object():
        if state.replace("/", "").strip() == wanted:
            return NameObject(state)
    return NameObject(requested)


def set_checkbox_values(writer: PdfWriter, values: dict[str, str]) -> None:
    """Checks the requested checkboxes using each template's own state names."""
    for page in writer.pages:
        for annotation_ref in page.get("/Annots", []) or []:
            annotation = annotation_ref.get_object()
            field_name = annotation.get("/T")
            if not field_name:
                continue
            full_name = annotation_full_name(annotation)
            selected_name = full_name if full_name in values else str(field_name)
            if selected_name not in values:
                continue
            appearance = defined_appearance(annotation, values[selected_name])
            annotation.update(
                {
                    NameObject("/V"): appearance,
                    NameObject("/AS"): appearance,
                }
            )


def fill_continuation_slots(
    *,
    text_values: dict[str, str],
    slots: tuple[tuple[str, str, str, str], ...],
    page_number: str,
    part_number: str,
    item_number: str,
    text: str,
    wrap_width: int,
    max_lines: int,
) -> list[str] | None:
    """Writes text to a form's additional-information slots; None means it does not fit and nothing was written."""
    # Saved appearances do not wrap on their own, so line breaks must be in the value.
    lines = textwrap.wrap(text, width=wrap_width, break_long_words=True, replace_whitespace=False) if text else []
    chunks = ["\n".join(lines[index : index + max_lines]) for index in range(0, len(lines), max_lines)]
    open_slots = [slot for slot in slots if slot[3] not in text_values]
    if len(chunks) > len(open_slots):
        return None
    fields: list[str] = []
    for chunk, (page_field, part_field, item_field, info_field) in zip(chunks, open_slots, strict=False):
        text_values[page_field] = page_number
        text_values[part_field] = part_number
        text_values[item_field] = item_number
        text_values[info_field] = chunk
        fields.extend([page_field, part_field, item_field, info_field])
    return fields


FIELD_MULTILINE_FLAG = 1 << 12


def overlong_field_names(reader: PdfReader, text_values: dict[str, str]) -> list[str]:
    """Fields wider than their box; a printed form clips the overflow. `field_length_warning` covers template limits."""
    overlong: set[str] = set()
    for page in reader.pages:
        for annotation_ref in page.get("/Annots", []) or []:
            annotation = annotation_ref.get_object()
            field_name = str(annotation.get("/T") or "")
            value = text_values.get(field_name) or text_values.get(annotation_full_name(annotation) or "")
            if not value:
                continue
            font_size = re.search(r"([\d.]+)\s+Tf", str(annotation.get("/DA") or ""))
            if (
                annotation.get("/MaxLen") is not None
                or int(annotation.get("/Ff") or 0) & FIELD_MULTILINE_FLAG
                or not font_size
                or not float(font_size.group(1))
            ):
                continue
            left, _, right, _ = (float(number) for number in annotation["/Rect"])
            # Template fields use Courier, whose characters are 0.6 em wide.
            if len(value) > int((right - left - 4) / (0.6 * float(font_size.group(1)))):
                overlong.add(field_name)
    return sorted(overlong)


OVERLONG_WARNING = "Longer than the form's box allows and may print cut off. Check the printed page, and shorten these or use the additional information section: "


def field_length_warning(reader: PdfReader, values: dict[str, str]) -> list[str]:
    """Returns warnings for values longer than their field allows."""
    too_long: dict[str, str] = {}
    for page in reader.pages:
        for annotation_ref in page.get("/Annots", []) or []:
            annotation = annotation_ref.get_object()
            field_name = annotation.get("/T")
            max_length = annotation.get("/MaxLen")
            if not field_name or max_length is None:
                continue
            full_name = annotation_full_name(annotation)
            value = values.get(full_name) if full_name in values else values.get(str(field_name))
            if value is not None and len(value) > int(max_length):
                too_long[str(field_name)] = f"{value!r} ({len(value)} characters, the form allows {int(max_length)})"
    if not too_long:
        return []
    return ["These answers may be cut off when printed: " + "; ".join(too_long.values()) + "."]


def unprintable_character_warning(writer: PdfWriter) -> list[str]:
    """Returns warnings for characters the form's font cannot print."""
    # The form fonts cannot draw every character: the field keeps "Łukasz" but prints "?ukasz".
    unprintable: set[str] = set()
    for page in writer.pages:
        for annotation_ref in page.get("/Annots", []) or []:
            annotation = annotation_ref.get_object()
            value = annotation.get("/V")
            normal_appearance = (annotation.get("/AP") or {}).get("/N")
            if not isinstance(value, str) or value.isascii() or normal_appearance is None:
                continue
            stream = normal_appearance.get_object()
            if hasattr(stream, "get_data") and stream.get_data().count(b"?") > value.count("?"):
                unprintable.add(value)
    if not unprintable:
        return []
    return [
        "These answers contain characters the form cannot print and will show a question mark: "
        + "; ".join(sorted(unprintable))
        + ". Enter them as they should appear on the filing, using the Latin spelling on the passport where one is shown."
    ]


def use_saved_appearances(writer: PdfWriter) -> None:
    """Keeps PDF viewers from redrawing fields, which would break the form's barcode."""
    # Viewers that redraw fields print the form's PDF417 barcode as plain text, which scanners cannot read.
    writer.set_need_appearances_writer(False)
