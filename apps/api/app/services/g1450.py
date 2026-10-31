from __future__ import annotations

import json
from dataclasses import dataclass
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import UUID

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, BooleanObject, DictionaryObject, NameObject
from sqlmodel import Session, select

from app.content.fee_schedule import G1450_FORM_FEES, G1450_PAYMENT_NOTE
from app.models.entities import CaseChecklistItem, CaseRecord
from app.services.intake import get_merged_case_intake
from app.services.i485_pdf import _defined_appearance

CARD_TYPE_APPEARANCES = {
    "visa": ("CreditCardTypeChBx[0]", NameObject("/V")),
    "mastercard": ("CreditCardTypeChBx[1]", NameObject("/MC")),
    "master card": ("CreditCardTypeChBx[1]", NameObject("/MC")),
    "american express": ("CreditCardTypeChBx[2]", NameObject("/A")),
    "amex": ("CreditCardTypeChBx[2]", NameObject("/A")),
    "discover": ("CreditCardTypeChBx[3]", NameObject("/D")),
}

G1450_REQUESTOR_ROLE_BY_CHECKLIST_CODE = {
    "form_i130": "petitioner",
    "form_i485": "beneficiary",
    "form_i765": "beneficiary",
    "form_i131": "beneficiary",
}


@dataclass(frozen=True)
class GeneratedG1450:
    output_path: Path
    authorized_amount: str
    template_path: Path
    source_json_path: Path | None = None
    checklist_code: str | None = None
    form_code: str | None = None
    filing_category: str | None = None


@dataclass(frozen=True)
class G1450PaymentOption:
    checklist_code: str
    form_code: str
    label: str
    filing_category: str
    paper_fee: str
    source_url: str
    verified_on: str
    source_edition: str
    is_payable: bool


@dataclass(frozen=True)
class G1450PacketPlan:
    case_id: UUID
    generated: list[GeneratedG1450]
    skipped: list[dict[str, Any]]
    total_authorized_amount: str
    payment_note: str


def load_card_payload(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("G-1450 credit-card JSON must be an object.")
    return payload


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if value is None or str(value).strip() == "":
        raise ValueError(f"Missing required G-1450 credit-card field: {key}")
    return str(value).strip()


def _format_amount(value: Any) -> str:
    amount = _parse_amount(value)
    if amount <= 0:
        raise ValueError("authorized_amount must be greater than zero.")
    return f"{amount:.2f}"


def _parse_amount(value: Any) -> Decimal:
    try:
        amount = Decimal(str(value).replace("$", "").replace(",", "").strip())
    except (InvalidOperation, AttributeError) as exc:
        raise ValueError("authorized_amount must be a valid dollar amount.") from exc
    return amount


def _whole_dollar_amount(value: Any) -> str:
    amount = _parse_amount(value)
    if amount <= 0 or amount != amount.to_integral_value():
        raise ValueError("Payment forms need a whole-dollar amount greater than zero.")
    return str(int(amount))


def _split_name(full_name: str) -> tuple[str, str, str]:
    parts = [part for part in full_name.strip().split() if part]
    if not parts:
        return "", "", ""
    if len(parts) == 1:
        return "", parts[0], ""
    if len(parts) == 2:
        return parts[1], parts[0], ""
    return " ".join(parts[2:]), parts[0], parts[1]


def _person_name(values: dict[str, Any], role: str) -> str:
    parts = [
        str(values.get(f"{role}_first_name") or "").strip(),
        str(values.get(f"{role}_middle_name") or "").strip(),
        str(values.get(f"{role}_last_name") or "").strip(),
    ]
    return " ".join(part for part in parts if part)


def _payload_with_case_requestor_name(
    *,
    session: Session,
    case_id: UUID,
    payload: dict[str, Any],
    checklist_code: str,
) -> dict[str, Any]:
    values = get_merged_case_intake(session, case_id)
    role = G1450_REQUESTOR_ROLE_BY_CHECKLIST_CODE.get(checklist_code, "beneficiary")
    requestor_name = _person_name(values, role)
    if not requestor_name:
        return payload
    updated = dict(payload)
    updated["applicant_name"] = requestor_name
    updated.pop("signature_name", None)
    return updated


def _card_chunks(card_number: str) -> list[str]:
    digits = "".join(character for character in card_number if character.isdigit())
    if len(digits) < 12:
        raise ValueError("credit_card_number must contain at least 12 digits.")
    return [digits[index : index + 4] for index in range(0, 16, 4)]


def _billing_address(payload: dict[str, Any]) -> dict[str, str]:
    raw = payload.get("billing_address")
    if not isinstance(raw, dict):
        raise ValueError("billing_address must be an object.")
    return {
        "street_1": str(raw.get("street_1") or "").strip(),
        "street_2": str(raw.get("street_2") or "").strip(),
        "city": str(raw.get("city") or "").strip(),
        "state": str(raw.get("state") or "").strip(),
        "postal_code": str(raw.get("postal_code") or "").strip(),
    }


def _unit_kind_and_number(street_2: str) -> tuple[str | None, str]:
    normalized = street_2.strip()
    if not normalized:
        return None, ""
    parts = normalized.split(maxsplit=1)
    label = parts[0].lower().rstrip(".")
    unit_number = parts[1] if len(parts) > 1 else normalized
    if label in {"apt", "apartment"}:
        return "CCHolderAptSteFlr_Unit[1]", unit_number
    if label in {"ste", "suite"}:
        return "CCHolderAptSteFlr_Unit[0]", unit_number
    if label in {"fl", "floor"}:
        return "CCHolderAptSteFlr_Unit[2]", unit_number
    return "CCHolderAptSteFlr_Unit[1]", normalized


def _set_checkbox(writer: PdfWriter, field_name: str, appearance: NameObject) -> None:
    for page in writer.pages:
        for annotation_ref in page.get("/Annots", []):
            annotation = annotation_ref.get_object()
            if annotation.get("/T") == field_name:
                defined = _defined_appearance(annotation, appearance)
                annotation.update(
                    {
                        NameObject("/V"): defined,
                        NameObject("/AS"): defined,
                    }
                )


def _use_saved_appearances(writer: PdfWriter) -> None:
    # Viewers that redraw fields print the form's PDF417 barcode as plain text, which scanners cannot read.
    writer._root_object.update(
        {
            NameObject("/AcroForm"): DictionaryObject(
                {
                    NameObject("/NeedAppearances"): BooleanObject(False),
                    NameObject("/Fields"): ArrayObject(),
                }
            )
        }
    )


def generate_g1450_pdf(
    *,
    card_json_path: Path,
    template_path: Path,
    output_path: Path,
    amount_override: str | None = None,
    checklist_code: str | None = None,
    form_code: str | None = None,
    filing_category: str | None = None,
) -> GeneratedG1450:
    payload = load_card_payload(card_json_path)
    return generate_g1450_pdf_from_payload(
        payload=payload,
        template_path=template_path,
        output_path=output_path,
        amount_override=amount_override,
        source_json_path=card_json_path,
        checklist_code=checklist_code,
        form_code=form_code,
        filing_category=filing_category,
    )


def generate_g1450_pdf_from_payload(
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
        raise ValueError(f"G-1450 template PDF not found at {template_path}.")
    cardholder_name = _required_string(payload, "cardholder_name")
    requestor_name = str(
        payload.get("applicant_name") or payload.get("signature_name") or cardholder_name
    ).strip()
    family_name, given_name, middle_name = _split_name(requestor_name)
    cc_family_name, cc_given_name, cc_middle_name = _split_name(cardholder_name)
    billing = _billing_address(payload)
    chunks = _card_chunks(_required_string(payload, "credit_card_number"))
    amount = _format_amount(amount_override or payload.get("authorized_amount"))
    expiration_month = _required_string(payload, "expiration_month").zfill(2)
    expiration_year = _required_string(payload, "expiration_year")
    expiration = f"{expiration_month}/{expiration_year}"
    card_type = _required_string(payload, "credit_card_type").lower()
    selected_card = CARD_TYPE_APPEARANCES.get(card_type)
    if selected_card is None:
        raise ValueError(
            "credit_card_type must be one of: Visa, Mastercard, American Express, Discover."
        )

    unit_field, unit_number = _unit_kind_and_number(billing["street_2"])
    text_values = {
        "FamilyName[0]": family_name,
        "GivenName[0]": given_name,
        "MiddleName[0]": middle_name,
        "CCHolderFamilyName[0]": cc_family_name,
        "CCHolderGivenName[0]": cc_given_name,
        "CCHolderMiddleName[0]": cc_middle_name,
        "Pt1Line2b_StreetNumberName[0]": billing["street_1"],
        "CCHolderAptSteFlrNumber[0]": unit_number,
        "CityOrTown[0]": billing["city"],
        "State[0]": billing["state"],
        "ZipCode[0]": billing["postal_code"],
        "DaytimeTelephoneNumber[0]": str(payload.get("daytime_phone_number") or "").strip(),
        "Email[0]": str(payload.get("email") or "").strip(),
        "CreditCardNumber_1[0]": chunks[0],
        "CreditCardNumber_2[0]": chunks[1],
        "CreditCardNumber_3[0]": chunks[2],
        "CreditCardNumber_4[0]": chunks[3],
        "CreditCardNumber_4[1]": _required_string(payload, "security_code"),
        "ExpirationDate[0]": expiration,
        # Source: https://www.uscis.gov/sites/default/files/document/forms/g-1450instr.pdf,
        # verified 2026-05-09.
        # USCIS says a typewritten name is not an acceptable G-1450 signature.
        "SignatureOfApplicant[0]": "",
        # The form preprints ".00" after this field, so writing cents would print "675.00 .00".
        "AuthorizedPaymentAmt[0]": _whole_dollar_amount(amount),
    }

    reader = PdfReader(template_path)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    _use_saved_appearances(writer)
    for page in writer.pages:
        writer.update_page_form_field_values(page, text_values, auto_regenerate=False)
    _set_checkbox(writer, selected_card[0], selected_card[1])
    if unit_field:
        appearance = {
            "CCHolderAptSteFlr_Unit[0]": NameObject("/ STE "),
            "CCHolderAptSteFlr_Unit[1]": NameObject("/ APT "),
            "CCHolderAptSteFlr_Unit[2]": NameObject("/ FLR "),
        }[unit_field]
        _set_checkbox(writer, unit_field, appearance)

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


def _case_or_error(session: Session, case_id: UUID) -> CaseRecord:
    case = session.get(CaseRecord, case_id)
    if not case:
        raise ValueError(f"Case not found: {case_id}")
    return case


def payable_checklist_items(session: Session, case_id: UUID) -> list[CaseChecklistItem]:
    _case_or_error(session, case_id)
    items = list(
        session.exec(
            select(CaseChecklistItem)
            .where(CaseChecklistItem.case_id == case_id)
            .order_by(CaseChecklistItem.sort_order.asc())
        )
    )
    return [
        item
        for item in items
        if item.code in G1450_FORM_FEES and item.applicability != "not_applicable"
    ]


def get_case_g1450_payment_options(session: Session, case_id: UUID) -> list[G1450PaymentOption]:
    return [_payment_option_for_item(item) for item in payable_checklist_items(session, case_id)]


def _payment_option_for_item(item: CaseChecklistItem) -> G1450PaymentOption:
    fee = G1450_FORM_FEES[item.code]
    return G1450PaymentOption(
        checklist_code=item.code,
        form_code=fee["form_code"],
        label=fee["label"],
        filing_category=fee["filing_category"],
        paper_fee=f"{_parse_amount(fee['paper_fee']):.2f}",
        source_url=fee["source_url"],
        verified_on=fee["verified_on"],
        source_edition=fee["source_edition"],
        is_payable=_parse_amount(fee["paper_fee"]) > 0,
    )


def generate_case_g1450_packet(
    *,
    session: Session,
    case_id: UUID,
    card_json_path: Path,
    template_path: Path,
    output_dir: Path,
    selected_checklist_codes: list[str] | None = None,
) -> G1450PacketPlan:
    payload = load_card_payload(card_json_path)
    return generate_case_g1450_packet_from_payload(
        session=session,
        case_id=case_id,
        payload=payload,
        template_path=template_path,
        output_dir=output_dir,
        selected_checklist_codes=selected_checklist_codes,
        source_json_path=card_json_path,
    )


def generate_case_g1450_packet_from_payload(
    *,
    session: Session,
    case_id: UUID,
    payload: dict[str, Any],
    template_path: Path,
    output_dir: Path,
    selected_checklist_codes: list[str] | None = None,
    source_json_path: Path | None = None,
) -> G1450PacketPlan:
    return generate_case_payment_packet(
        session=session,
        case_id=case_id,
        payload=payload,
        template_path=template_path,
        output_dir=output_dir,
        selected_checklist_codes=selected_checklist_codes,
        source_json_path=source_json_path,
        generate_form=generate_g1450_pdf_from_payload,
        filename_suffix="g-1450",
    )


def generate_case_payment_packet(
    *,
    session: Session,
    case_id: UUID,
    payload: dict[str, Any],
    template_path: Path,
    output_dir: Path,
    selected_checklist_codes: list[str] | None,
    generate_form: Callable[..., GeneratedG1450],
    filename_suffix: str,
    source_json_path: Path | None = None,
) -> G1450PacketPlan:
    items = payable_checklist_items(session, case_id)
    applicable_codes = {item.code for item in items}
    selected_codes = applicable_codes if selected_checklist_codes is None else set(selected_checklist_codes)
    unknown_codes = selected_codes - applicable_codes
    if unknown_codes:
        raise ValueError(
            "Selected payment forms are not applicable to this case: "
            + ", ".join(sorted(unknown_codes))
        )

    generated: list[GeneratedG1450] = []
    skipped: list[dict[str, Any]] = []

    for item in items:
        if item.code not in selected_codes:
            continue
        fee = G1450_FORM_FEES[item.code]
        parsed_amount = _parse_amount(fee["paper_fee"])
        if parsed_amount <= 0:
            skipped.append(
                {
                    "checklist_code": item.code,
                    "form_code": fee["form_code"],
                    "label": fee["label"],
                    "reason": "No USCIS filing fee tracked for this form in the local fee table.",
                    "source_url": fee["source_url"],
                    "verified_on": fee["verified_on"],
                }
            )
            continue
        amount = f"{parsed_amount:.2f}"
        filename = f"{case_id}-{fee['form_code'].lower()}-{filename_suffix}.pdf"
        item_payload = _payload_with_case_requestor_name(
            session=session,
            case_id=case_id,
            payload=payload,
            checklist_code=item.code,
        )
        generated.append(
            generate_form(
                payload=item_payload,
                template_path=template_path,
                output_path=output_dir / filename,
                amount_override=amount,
                source_json_path=source_json_path,
                checklist_code=item.code,
                form_code=fee["form_code"],
                filing_category=fee["filing_category"],
            )
        )

    total = sum(Decimal(result.authorized_amount) for result in generated)
    return G1450PacketPlan(
        case_id=case_id,
        generated=generated,
        skipped=skipped,
        total_authorized_amount=f"{total:.2f}",
        payment_note=G1450_PAYMENT_NOTE,
    )
