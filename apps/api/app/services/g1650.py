from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from uuid import UUID

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject
from sqlmodel import Session

from app.services.g1450 import (
    G1450PacketPlan,
    GeneratedG1450,
    _parse_amount,
    _set_checkbox,
    _set_need_appearances,
    _split_name,
    generate_case_payment_packet,
)

# Field names come from the 06/03/25 template, verified 2026-10-30 at https://www.uscis.gov/g-1650.
# The applicant and account holder name fields share short names, so these use qualified names.
APPLICANT_FIELDS = "form1[0].PG1[0].sfApplicantPetitionerName[0]"
HOLDER_FIELDS = "form1[0].PG1[0].sfBankAccountHolderInfo[0]"
BANK_FIELDS = "form1[0].PG1[0].sfBankAccountInformation[0]"

# The template reuses credit-card names and tooltips for these boxes; choices follow their printed labels.
ACCOUNT_OWNERSHIP_CHECKBOXES = {
    "business": ("CB_AccountType[0]", NameObject("/B")),
    "personal": ("CB_AccountType[1]", NameObject("/P")),
}
ACCOUNT_TYPE_CHECKBOXES = {
    "checking": ("CB_CreditCardType[1]", NameObject("/V")),
    "savings": ("CB_CreditCardType[0]", NameObject("/MC")),
}


def _clean_string(payload: dict[str, Any], key: str) -> str:
    return str(payload.get(key) or "").strip()


def _digits(value: str) -> str:
    return re.sub(r"[\s-]", "", value)


def _routing_checksum_is_valid(routing_number: str) -> bool:
    weights = (3, 7, 1) * 3
    return sum(weight * int(digit) for weight, digit in zip(weights, routing_number)) % 10 == 0


def validate_g1650_payload(payload: dict[str, Any]) -> None:
    ownership = _clean_string(payload, "account_ownership").lower()
    if ownership not in ACCOUNT_OWNERSHIP_CHECKBOXES:
        raise ValueError("account_ownership must be personal or business.")
    if ownership == "business" and not _clean_string(payload, "business_name"):
        raise ValueError("business_name is required for a business account.")
    if ownership == "personal" and not _clean_string(payload, "account_holder_name"):
        raise ValueError("account_holder_name is required for a personal account.")
    if _clean_string(payload, "account_type").lower() not in ACCOUNT_TYPE_CHECKBOXES:
        raise ValueError("account_type must be checking or savings.")
    if not _clean_string(payload, "bank_name"):
        raise ValueError("bank_name is required.")
    routing_number = _digits(_clean_string(payload, "routing_number"))
    if not re.fullmatch(r"\d{9}", routing_number) or not _routing_checksum_is_valid(routing_number):
        raise ValueError("routing_number must be a valid 9-digit U.S. bank routing number.")
    if not re.fullmatch(r"\d{4,17}", _digits(_clean_string(payload, "account_number"))):
        raise ValueError("account_number must be 4 to 17 digits.")


def _whole_dollar_amount(value: Any) -> str:
    # The form preprints ".00" after the amount, so it can only state whole dollars.
    amount = _parse_amount(value)
    if amount <= 0 or amount != amount.to_integral_value():
        raise ValueError("Form G-1650 needs a whole-dollar amount greater than zero.")
    return str(int(amount))


def generate_g1650_pdf_from_payload(
    *,
    payload: dict[str, Any],
    template_path: Path,
    output_path: Path,
    amount_override: str | None = None,
    source_json_path: Path | None = None,
    checklist_code: str | None = None,
    form_code: str | None = None,
    filing_category: str | None = None,
) -> GeneratedG1450:
    if not template_path.exists():
        raise ValueError(f"G-1650 template PDF not found at {template_path}.")
    validate_g1650_payload(payload)
    amount = _whole_dollar_amount(amount_override or payload.get("authorized_amount"))
    holder_name = _clean_string(payload, "account_holder_name")
    family_name, given_name, middle_name = _split_name(_clean_string(payload, "applicant_name") or holder_name)
    holder_family, holder_given, holder_middle = _split_name(holder_name)
    # USCIS requires the account holder's own signature, so the signature field stays blank.
    text_values = {
        f"{APPLICANT_FIELDS}.GivenName[0]": given_name,
        f"{APPLICANT_FIELDS}.MiddleName[0]": middle_name,
        f"{APPLICANT_FIELDS}.FamilyName[0]": family_name,
        f"{HOLDER_FIELDS}.GivenName[0]": holder_given,
        f"{HOLDER_FIELDS}.MiddleName[0]": holder_middle,
        f"{HOLDER_FIELDS}.FamilyName[0]": holder_family,
        f"{BANK_FIELDS}.BusinessName[0]": _clean_string(payload, "business_name"),
        f"{BANK_FIELDS}.AuthorizedPaymentAmt[0]": amount,
        f"{BANK_FIELDS}.RoutingNumber[0]": _digits(_clean_string(payload, "routing_number")),
        f"{BANK_FIELDS}.AccountNumber[0]": _digits(_clean_string(payload, "account_number")),
        f"{BANK_FIELDS}.BankName[0]": _clean_string(payload, "bank_name"),
    }

    # Clone rather than copy pages: qualified field names rely on the template's field hierarchy.
    writer = PdfWriter(clone_from=PdfReader(template_path))
    _set_need_appearances(writer)
    for page in writer.pages:
        writer.update_page_form_field_values(page, text_values)
    for field_name, appearance in (
        ACCOUNT_OWNERSHIP_CHECKBOXES[_clean_string(payload, "account_ownership").lower()],
        ACCOUNT_TYPE_CHECKBOXES[_clean_string(payload, "account_type").lower()],
    ):
        _set_checkbox(writer, field_name, appearance)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as handle:
        writer.write(handle)

    return GeneratedG1450(
        output_path=output_path,
        authorized_amount=amount,
        template_path=template_path,
        source_json_path=source_json_path,
        checklist_code=checklist_code,
        form_code=form_code,
        filing_category=filing_category,
    )


def generate_case_g1650_packet_from_payload(
    *,
    session: Session,
    case_id: UUID,
    payload: dict[str, Any],
    template_path: Path,
    output_dir: Path,
    selected_checklist_codes: list[str] | None = None,
) -> G1450PacketPlan:
    return generate_case_payment_packet(
        session=session,
        case_id=case_id,
        payload=payload,
        template_path=template_path,
        output_dir=output_dir,
        selected_checklist_codes=selected_checklist_codes,
        generate_form=generate_g1650_pdf_from_payload,
        filename_suffix="g-1650",
    )
