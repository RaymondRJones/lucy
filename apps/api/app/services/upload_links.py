"""Links uploads to the checklist items they satisfy."""

from __future__ import annotations

from typing import Any, Iterable

from app.models.entities import UploadedDocument


def _dedupe_codes(codes: Iterable[str | None]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for code in codes:
        if not code or code in seen:
            continue
        seen.add(code)
        ordered.append(code)
    return ordered


def infer_satisfied_checklist_codes(
    checklist_item_code: str | None,
    extracted_fields: dict[str, Any] | None = None,
    *,
    has_translation: bool = False,
) -> list[str]:
    """Returns the checklist items a document satisfies."""
    raw_codes = (extracted_fields or {}).get("satisfies_checklist_codes", [])
    extra_codes = [
        str(code).strip()
        for code in raw_codes
        if isinstance(code, str) and str(code).strip()
    ] if isinstance(raw_codes, list) else []

    codes = _dedupe_codes([checklist_item_code, *extra_codes])
    if has_translation and "beneficiary_birth_certificate" in codes:
        codes = _dedupe_codes([*codes, "translation_certification"])
    return codes


def satisfied_checklist_codes_for_upload(upload: UploadedDocument) -> list[str]:
    """Returns the checklist items an upload satisfies."""
    return infer_satisfied_checklist_codes(
        upload.checklist_item_code,
        upload.extracted_fields or {},
        has_translation=upload.has_translation,
    )
