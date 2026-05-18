from __future__ import annotations

from typing import Any


LEGAL_ENTRY_TO_ARRIVAL_TYPE = {
    "visa_admitted": "admitted",
    "esta_vwp": "admitted",
    "paroled": "paroled",
    "visa_esta_parole": "admitted",
}


def value_is_answered(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(value_is_answered(entry) for entry in value)
    if isinstance(value, dict):
        return any(value_is_answered(entry) for entry in value.values())
    return True


def _copy_first(values: dict[str, Any], target: str, *sources: str) -> None:
    if value_is_answered(values.get(target)):
        return
    for source in sources:
        value = values.get(source)
        if value_is_answered(value):
            values[target] = value
            return


def _mirror_pair(values: dict[str, Any], first: str, second: str) -> None:
    _copy_first(values, first, second)
    _copy_first(values, second, first)


def _compose_current_address(values: dict[str, Any]) -> None:
    parts = [
        values.get("beneficiary_current_address_line1"),
        values.get("beneficiary_current_address_line2"),
        values.get("beneficiary_current_city") or values.get("beneficiary_current_address_city"),
        values.get("beneficiary_current_state") or values.get("beneficiary_current_address_state"),
        values.get("beneficiary_current_zip") or values.get("beneficiary_current_address_postal_code"),
    ]
    if not value_is_answered(values.get("beneficiary_current_address")) and any(value_is_answered(part) for part in parts):
        values["beneficiary_current_address"] = ", ".join(
            str(part).strip() for part in parts if value_is_answered(part)
        )


def _copy_physical_to_mailing(values: dict[str, Any]) -> None:
    if values.get("beneficiary_mailing_same_as_physical") is not True:
        return
    for target, sources in {
        "beneficiary_mailing_address_line1": ("beneficiary_current_address_line1",),
        "beneficiary_mailing_address_line2": ("beneficiary_current_address_line2",),
        "beneficiary_mailing_city": ("beneficiary_current_city", "beneficiary_current_address_city"),
        "beneficiary_mailing_state": ("beneficiary_current_state", "beneficiary_current_address_state"),
        "beneficiary_mailing_zip": ("beneficiary_current_zip", "beneficiary_current_address_postal_code"),
    }.items():
        _copy_first(values, target, *sources)


def _copy_address_object(values: dict[str, Any], source: str, prefix: str) -> None:
    address = values.get(source)
    if not isinstance(address, dict):
        return
    for target_suffix, source_keys in {
        "address_line1": ("line1", "street", "street_number_name"),
        "address_line2": ("line2", "unit", "apt", "apartment"),
        "city": ("city",),
        "state": ("state",),
        "zip": ("zip", "postal_code"),
        "country": ("country",),
    }.items():
        for source_key in source_keys:
            value = address.get(source_key)
            if value_is_answered(value):
                _copy_first(values, f"{prefix}_{target_suffix}", source_key)
                if not value_is_answered(values.get(f"{prefix}_{target_suffix}")):
                    values[f"{prefix}_{target_suffix}"] = value
                break


def _split_arrival_place(values: dict[str, Any]) -> None:
    place = values.get("beneficiary_last_arrival_place")
    if not isinstance(place, str) or "," not in place:
        return
    city, state = (part.strip() for part in place.split(",", 1))
    if city and not value_is_answered(values.get("beneficiary_last_arrival_city")):
        values["beneficiary_last_arrival_city"] = city
    if state and not value_is_answered(values.get("beneficiary_last_arrival_state")):
        values["beneficiary_last_arrival_state"] = state


def _compose_arrival_place(values: dict[str, Any]) -> None:
    if value_is_answered(values.get("beneficiary_last_arrival_place")):
        return
    parts = [
        str(values.get("beneficiary_last_arrival_city") or "").strip(),
        str(values.get("beneficiary_last_arrival_state") or "").strip(),
    ]
    place = ", ".join(part for part in parts if part)
    if place:
        values["beneficiary_last_arrival_place"] = place


def _derive_happy_path_fields(values: dict[str, Any]) -> None:
    last_entry_type = values.get("beneficiary_last_entry_type")
    if last_entry_type in LEGAL_ENTRY_TO_ARRIVAL_TYPE:
        if not value_is_answered(values.get("beneficiary_last_arrival_type")):
            values["beneficiary_last_arrival_type"] = LEGAL_ENTRY_TO_ARRIVAL_TYPE[last_entry_type]
    elif last_entry_type == "entered_without_inspection":
        if not value_is_answered(values.get("beneficiary_last_arrival_type")):
            values["beneficiary_last_arrival_type"] = "without_admission"

    arrival_type = values.get("beneficiary_last_arrival_type")
    if arrival_type in {"admitted", "paroled"}:
        if not value_is_answered(values.get("beneficiary_entered_us_legally")):
            values["beneficiary_entered_us_legally"] = True
    elif arrival_type == "without_admission":
        if not value_is_answered(values.get("beneficiary_entered_us_legally")):
            values["beneficiary_entered_us_legally"] = False
        if not value_is_answered(values.get("unlawful_entry")):
            values["unlawful_entry"] = True

    petitioner_status = values.get("petitioner_citizenship_status")
    case_basis_is_usc_spouse = values.get("case_basis") == "usc_spouse" and (
        not value_is_answered(petitioner_status) or petitioner_status == "us_citizen"
    )
    if case_basis_is_usc_spouse or (
        values.get("relationship_spouse") is True and values.get("petitioner_citizenship_status") == "us_citizen"
    ):
        if not value_is_answered(values.get("i485_family_category")):
            values["i485_family_category"] = "spouse_us_citizen"

    if values.get("relationship_spouse") is True:
        if not value_is_answered(values.get("beneficiary_current_marital_status")):
            values["beneficiary_current_marital_status"] = "married"
        if not value_is_answered(values.get("petitioner_current_marital_status")):
            values["petitioner_current_marital_status"] = "married"
        for target, source in (
            ("beneficiary_spouse1_last_name", "petitioner_last_name"),
            ("beneficiary_spouse1_first_name", "petitioner_first_name"),
            ("beneficiary_spouse1_middle_name", "petitioner_middle_name"),
            ("petitioner_spouse1_first_name", "beneficiary_first_name"),
            ("petitioner_spouse1_middle_name", "beneficiary_middle_name"),
        ):
            _copy_first(values, target, source)
    if values.get("first_marriage_for_both") is True:
        if not value_is_answered(values.get("beneficiary_marriage_count")):
            values["beneficiary_marriage_count"] = 1
        if not value_is_answered(values.get("petitioner_marriage_count")):
            values["petitioner_marriage_count"] = 1

    if values.get("i485_family_category") == "spouse_us_citizen":
        if not value_is_answered(values.get("beneficiary_location")):
            values["beneficiary_location"] = "usa"

    if str(values.get("beneficiary_location") or "").lower() in {"usa", "us", "united_states", "united states"}:
        if not value_is_answered(values.get("beneficiary_ever_in_united_states")):
            values["beneficiary_ever_in_united_states"] = True
        if not value_is_answered(values.get("beneficiary_adjustment_path")):
            values["beneficiary_adjustment_path"] = True
        if not value_is_answered(values.get("beneficiary_current_country")):
            values["beneficiary_current_country"] = "United States"
        if not value_is_answered(values.get("beneficiary_country_of_residence")):
            values["beneficiary_country_of_residence"] = "United States"


def enrich_case_fact_aliases(values: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with semantically equivalent case-field variants populated."""
    enriched = dict(values)

    _copy_address_object(enriched, "beneficiary_current_address", "beneficiary_current")
    _copy_address_object(enriched, "petitioner_current_address", "petitioner_current")

    for first, second in (
        ("beneficiary_current_city", "beneficiary_current_address_city"),
        ("beneficiary_current_state", "beneficiary_current_address_state"),
        ("beneficiary_current_zip", "beneficiary_current_address_postal_code"),
        ("beneficiary_current_zip", "beneficiary_current_postal_code"),
        ("beneficiary_current_country", "beneficiary_current_address_country"),
        ("beneficiary_address_since", "beneficiary_current_address_since"),
        ("beneficiary_status_expires_on", "beneficiary_current_status_expires_on"),
        ("beneficiary_ssn", "beneficiary_social_security_number"),
        ("beneficiary_state_province_of_birth", "beneficiary_birth_department"),
        ("petitioner_current_zip", "petitioner_current_address_postal_code"),
        ("petitioner_current_country", "petitioner_current_address_country"),
    ):
        _mirror_pair(enriched, first, second)

    recent_foreign_address = enriched.get("beneficiary_recent_foreign_address")
    if isinstance(recent_foreign_address, dict) and not value_is_answered(enriched.get("beneficiary_state_province_of_birth")):
        birth_city = str(enriched.get("beneficiary_city_of_birth") or "").strip().lower()
        address_city = str(recent_foreign_address.get("city") or "").strip().lower()
        if birth_city and birth_city == address_city:
            province = recent_foreign_address.get("province") or recent_foreign_address.get("state")
            if value_is_answered(province):
                enriched["beneficiary_state_province_of_birth"] = province
                enriched["beneficiary_birth_department"] = province

    _split_arrival_place(enriched)
    _compose_arrival_place(enriched)
    _derive_happy_path_fields(enriched)

    race = enriched.get("beneficiary_race")
    if isinstance(race, list):
        for entry in race:
            if value_is_answered(entry):
                if not value_is_answered(enriched.get("beneficiary_race_primary")):
                    enriched["beneficiary_race_primary"] = entry
                break
    elif value_is_answered(race):
        if not value_is_answered(enriched.get("beneficiary_race_primary")):
            enriched["beneficiary_race_primary"] = race

    if value_is_answered(enriched.get("beneficiary_race_primary")) and not value_is_answered(enriched.get("beneficiary_race")):
        enriched["beneficiary_race"] = [enriched["beneficiary_race_primary"]]

    if value_is_answered(enriched.get("beneficiary_a_number")) and not value_is_answered(enriched.get("beneficiary_has_a_number")):
        enriched["beneficiary_has_a_number"] = True
    if value_is_answered(enriched.get("beneficiary_ssn")) and not value_is_answered(enriched.get("beneficiary_has_ssn")):
        enriched["beneficiary_has_ssn"] = True

    _compose_current_address(enriched)
    _copy_physical_to_mailing(enriched)

    return enriched
