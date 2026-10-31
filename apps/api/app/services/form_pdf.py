from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject
from sqlmodel import Session

from app.content.admission_classes import normalize_class_of_admission
from app.content.supplemental_forms import all_supplemental_form_questions, get_supplemental_form_config
from app.core.config import settings
from app.services.family_pdf import _without_zip_postal_aliases, build_i130_pdf_field_payload, build_i130a_pdf_field_payload
from app.services.form_ingestion import (
    build_form_answer_proposals_from_case_data,
    build_form_fill_preview,
    get_form_state,
    normalize_form_key,
)
from app.services.i485 import build_i485_intake_projection, get_i485_state
from app.services.intake import get_merged_case_intake
from app.services.i485_pdf import (
    _add_unit_fields,
    _set_checkbox_values,
    _use_saved_appearances,
    _set_text_values,
    _template_field_names,
)


DEFAULT_FORM_OUTPUT_DIR = settings.generated_dir

DATE_QUESTION_IDS = {
    "beneficiary_date_of_birth",
    "beneficiary_last_arrival_date",
    "beneficiary_passport_expiration",
    "petitioner_date_of_birth",
    "i131_intended_departure_date",
    "i131_prior_reentry_refugee_document_date",
    "i131_prior_advance_parole_date",
}

NON_PDF_CONTROL_QUESTIONS = {
    "applicant_reviewed_certification",
    "beneficiary_adjustment_path",
    "beneficiary_current_marital_status",
    "beneficiary_employment_history",
    "beneficiary_has_ssn",
    "beneficiary_marriage_count",
    "first_marriage_for_both",
    "i131_physical_same_as_mailing",
    "i864_sponsoring_family_members",
    "sponsor_reviewed_contract",
    "interpreter_used",
    "preparer_used",
    "additional_information_needed",
}

US_STATE_NAME_TO_CODE = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "districtofcolumbia": "DC",
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
    "newhampshire": "NH",
    "newjersey": "NJ",
    "newmexico": "NM",
    "newyork": "NY",
    "northcarolina": "NC",
    "northdakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhodeisland": "RI",
    "southcarolina": "SC",
    "southdakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "westvirginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
    "armedforcesamericas": "AA",
    "armedforceseurope": "AE",
    "armedforcespacific": "AP",
    "americansamoa": "AS",
    "federatedstatesofmicronesia": "FM",
    "guam": "GU",
    "marshallislands": "MH",
    "northernmarianaislands": "MP",
    "puertorico": "PR",
    "palau": "PW",
    "usvirginislands": "VI",
}

US_STATE_CODES = set(US_STATE_NAME_TO_CODE.values())
STATE_QUESTION_IDS = {
    "beneficiary_mailing_state",
    "beneficiary_physical_state",
    "petitioner_current_state",
}

PHONE_QUESTION_IDS = {
    "beneficiary_phone",
    "beneficiary_mobile_phone",
    "petitioner_phone",
    "petitioner_mobile_phone",
}

TEXT_FIELD_MAP: dict[str, dict[str, tuple[str, ...]]] = {
    "i765": {
        "beneficiary_last_name": ("Line1a_FamilyName[0]",),
        "beneficiary_first_name": ("Line1b_GivenName[0]",),
        "beneficiary_middle_name": ("Line1c_MiddleName[0]",),
        "beneficiary_mailing_in_care_of": ("Line4a_InCareofName[0]",),
        "beneficiary_mailing_address_line1": ("Line4b_StreetNumberName[0]",),
        "beneficiary_mailing_city": ("Pt2Line5_CityOrTown[0]",),
        "beneficiary_mailing_state": ("Pt2Line5_State[0]",),
        "beneficiary_mailing_zip": ("Pt2Line5_ZipCode[0]",),
        "beneficiary_physical_address_line1": ("Pt2Line7_StreetNumberName[0]",),
        "beneficiary_physical_city": ("Pt2Line7_CityOrTown[0]",),
        "beneficiary_physical_state": ("Pt2Line7_State[0]",),
        "beneficiary_physical_zip": ("Pt2Line7_ZipCode[0]",),
        "beneficiary_a_number": ("Line7_AlienNumber[0]",),
        "beneficiary_uscis_online_account_number": ("Line8_ElisAccountNumber[0]",),
        "beneficiary_social_security_number": ("Line12b_SSN[0]",),
        "beneficiary_city_of_birth": ("Line18a_CityTownOfBirth[0]",),
        "beneficiary_state_province_of_birth": ("Line18b_CityTownOfBirth[0]",),
        "beneficiary_country_of_birth": ("Line18c_CountryOfBirth[0]",),
        "beneficiary_country_of_citizenship": ("Line17a_CountryOfBirth[0]",),
        "beneficiary_date_of_birth": ("Line19_DOB[0]",),
        "beneficiary_i94_number": ("Line20a_I94Number[0]",),
        "beneficiary_passport_number": ("Line20b_Passport[0]",),
        "beneficiary_passport_country": ("Line20d_CountryOfIssuance[0]",),
        "beneficiary_passport_expiration": ("Line20e_ExpDate[0]",),
        "beneficiary_last_arrival_date": ("Line21_DateOfLastEntry[0]",),
        "beneficiary_last_arrival_place": ("place_entry[0]",),
        "beneficiary_class_of_admission": ("Line23_StatusLastEntry[0]",),
        "beneficiary_current_immigration_status": ("Line24_CurrentStatus[0]",),
        "i765_eligibility_category": ("section_1[0]", "section_2[0]", "section_3[0]"),
        "beneficiary_phone": ("Pt3Line3_DaytimePhoneNumber1[0]",),
        "beneficiary_mobile_phone": ("Pt3Line4_MobileNumber1[0]",),
        "beneficiary_email": ("Pt3Line5_Email[0]",),
    },
    "i864": {
        "petitioner_last_name": ("P4_Line1a_FamilyName[0]", "P4_Line1a_FamilyName[1]"),
        "petitioner_first_name": ("P4_Line1b_GivenName[0]", "P4_Line1b_GivenName[1]"),
        "petitioner_middle_name": ("P4_Line1c_MiddleName[0]", "P4_Line1c_MiddleName[1]"),
        "petitioner_mailing_in_care_of": ("P4_Line2a_InCareOf[0]",),
        "petitioner_current_address_line1": ("P4_Line2b_StreetNumberName[0]",),
        "petitioner_current_city": ("P4_Line2e_CityOrTown[0]",),
        "petitioner_current_state": ("P4_Line2f_State[0]",),
        "petitioner_current_zip": ("P4_Line2g_ZipCode[0]",),
        "petitioner_country_of_domicile": ("P4_Line5_CountryOfDomicile[0]",),
        "petitioner_date_of_birth": ("P4_Line6_DateOfBirth[0]",),
        "petitioner_city_of_birth": ("P4_Line7_CityofBirth[0]",),
        "petitioner_social_security_number": ("P4_Line10_SocialSecurityNumber[0]",),
        "beneficiary_last_name": ("P2_Line1a_FamilyName[0]",),
        "beneficiary_first_name": ("P2_Line1b_GivenName[0]",),
        "beneficiary_middle_name": ("P2_Line1c_MiddleName[0]",),
        "beneficiary_mailing_address_line1": ("P2_Line2_StreetNumberName[0]",),
        "beneficiary_mailing_city": ("P2_Line2_CityOrTown[0]",),
        "beneficiary_mailing_state": ("P2_Line2_State[0]",),
        "beneficiary_mailing_zip": ("P2_Line2_ZipCode[0]",),
        "beneficiary_country_of_citizenship": ("P2_Line3_CountryCitizenship[0]",),
        "beneficiary_date_of_birth": ("P2_Line4_DateOfBirth[0]",),
        "beneficiary_a_number": ("P2_Line5_AlienNumber[0]", "P2_Line5_AlienNumber[1]", "P4_Line12_AlienNumber[1]"),
        "beneficiary_phone": ("P2_Line7_DaytimePhoneNumber[0]",),
        "i864_total_immigrants": ("P3_Line28_TotalNumberofImmigrants[0]",),
        "household_size": ("Override[0]",),
        "i864_sponsor_married_count": ("P5_Line3_Married[0]",),
        "i864_dependent_children_count": ("P5_Line4_DependentChildren[0]",),
        "i864_other_dependents_count": ("P5_Line5_OtherDependents[0]",),
        "i864_prior_sponsored_immigrants_count": ("P5_Line6_Sponsors[0]",),
        "i864_household_members_combining_income_count": ("P5_Line7_SameResidence[0]",),
        "petitioner_current_occupation": ("P6_Line1a_NameofEmployer[0]",),
        "petitioner_current_employer": ("P6_Line1a1_NameofEmployer[0]",),
        "annual_income": ("P6_Line2_TotalIncome[0]",),
        "i864_household_income": ("P6_Line15_TotalHouseholdIncome[0]",),
        "i864_tax_year_1": ("P6_Line19a_TaxYear[0]",),
        "i864_tax_income_1": ("P6_Line19a_TotalIncome[0]",),
        "i864_tax_year_2": ("P6_Line19b_TaxYear[0]",),
        "i864_tax_income_2": ("P6_Line19b_TotalIncome[0]",),
        "i864_tax_year_3": ("P6_Line19c_TaxYear[0]",),
        "i864_tax_income_3": ("P6_Line19c_TotalIncome[0]",),
        "i864_cash_assets": ("P7_Line1_BalanceofAccounts[0]",),
        "i864_total_assets": ("P7_Line4_Total[0]", "P7_Line10_TotalValueAssets[0]"),
        "petitioner_phone": ("P8_Line3_DaytimeTelephoneNumber[0]",),
        "petitioner_mobile_phone": ("P8_Line4_MobileTelephoneNumber[0]",),
        "petitioner_email": ("P7Line7_EmailAddress[0]",),
    },
    "i131": {
        "i131_i485_receipt_number": ("form1[0].P1[0].P1_Line5A[0]",),
        "beneficiary_last_name": ("form1[0].P4[0].Part2_Line1_FamilyName[0]",),
        "beneficiary_first_name": ("form1[0].P4[0].Part2_Line1_GivenName[0]",),
        "beneficiary_middle_name": ("form1[0].P4[0].Part2_Line1_MiddleName[0]",),
        "beneficiary_mailing_in_care_of": ("Part2_Line3_InCareofName[0]",),
        "beneficiary_mailing_address_line1": ("Part2_Line3_StreetNumberName[0]",),
        "beneficiary_mailing_city": ("Part2_Line3_CityTown[0]",),
        "beneficiary_mailing_state": ("Part2_Line3_State[0]",),
        "beneficiary_mailing_zip": ("Part2_Line3_ZipCode[0]",),
        "beneficiary_mailing_province": ("Part2_Line3_Province[0]",),
        "beneficiary_mailing_postal_code": ("Part2_Line3_PostalCode[0]",),
        "beneficiary_mailing_country": ("Part2_Line3_Country[0]",),
        "beneficiary_physical_address_line1": ("Part2_Line4_StreetNumberName[0]",),
        "beneficiary_physical_city": ("Part2_Line4_CityTown[0]",),
        "beneficiary_physical_state": ("Part2_Line4_State[0]",),
        "beneficiary_physical_zip": ("Part2_Line4_ZipCode[0]",),
        "beneficiary_a_number": ("Part2_Line5_AlienNumber[0]",),
        "beneficiary_country_of_birth": ("Part2_Line6_CountryOfBirth[0]",),
        "beneficiary_country_of_citizenship": ("Part2_Line7_CountryOfCitizenshiporNationality[0]",),
        "beneficiary_date_of_birth": ("Part2_Line9_DateOfBirth[0]",),
        "beneficiary_social_security_number": ("Part2_Line10_SSN[0]",),
        "beneficiary_uscis_online_account_number": ("Part2_Line11_USCISOnlineAcctNumber[0]",),
        "beneficiary_class_of_admission": ("Part2_Line12_ClassofAdmission[0]",),
        "beneficiary_i94_number": ("Part2_Line13_I94RecordNo[0]",),
        "beneficiary_i94_expiration": ("Part2_Line14_I94ExpDate[0]",),
        "beneficiary_height_feet": ("P3_Line3_HeightFeet[0]",),
        "beneficiary_height_inches": ("P3_Line3_HeightInches[0]",),
        "beneficiary_weight_pounds": (
            "P3_Line4_Pound1[0]",
            "P3_Line4_Pound2[0]",
            "P3_Line4_Pound3[0]",
        ),
        "i131_prior_reentry_refugee_document_date": ("P4_Line2b_DateIssued[0]",),
        "i131_prior_reentry_refugee_document_disposition": ("P4_Line2c_Disposition[0]",),
        "i131_prior_advance_parole_date": ("P4_Line3b_DateIssued[0]",),
        "i131_prior_advance_parole_disposition": ("P4_Line3c_Disposition[0]",),
        "i131_processing_city": ("P4_Line7b_CityOrTown[0]",),
        "i131_processing_country": ("P4_Line7b_Country[0]",),
        "i131_intended_departure_date": ("P7_Line1_DateOfDeparture[0]",),
        "i131_travel_purpose": ("P7_Line2_Purpose[0]",),
        "i131_countries_to_visit": ("P7_Line3_ListCountries[0]",),
        "i131_expected_trip_length": ("P7_Line5_ExpectedLengthTrip[0]",),
        "beneficiary_phone": ("Part10_Line1_DayPhone[0]",),
        "beneficiary_mobile_phone": ("Part10_Line2_MobilePhone[0]",),
        "beneficiary_email": ("Part10_Line3_Email[0]",),
    },
}

CHECKBOX_FIELD_MAP: dict[str, dict[str, dict[Any, tuple[str, str]]]] = {
    "i765": {
        "i765_reason_for_applying": {
            "initial_permission": ("Part1_Checkbox[0]", "/1"),
            "replacement": ("Part1_Checkbox[1]", "/2"),
            "renewal": ("Part1_Checkbox[2]", "/3"),
        },
        "i765_physical_same_as_mailing": {
            False: ("Part2Line5_Checkbox[0]", "/N"),
            True: ("Part2Line5_Checkbox[1]", "/Y"),
        },
        "beneficiary_sex": {
            "female": ("Line9_Checkbox[0]", "/N"),
            "male": ("Line9_Checkbox[1]", "/Y"),
        },
        "beneficiary_current_marital_status": {
            "widowed": ("Line10_Checkbox[0]", "/Widowed"),
            "divorced": ("Line10_Checkbox[1]", "/Divorced"),
            "single": ("Line10_Checkbox[2]", "/Single"),
            "married": ("Line10_Checkbox[3]", "/Married"),
        },
        "i765_previously_filed": {
            False: ("Line19_Checkbox[0]", "/N"),
            True: ("Line19_Checkbox[1]", "/Y"),
        },
        "i765_arrested_or_convicted": {
            True: ("PtLine29_YesNo[0]", "/Y"),
            False: ("PtLine29_YesNo[1]", "/N"),
        },
    },
    "i864": {
        "i864_sponsor_basis": {
            "petitioner": ("P1_Line1a-f_CB[0]", "/1A"),
            "joint_sponsor": ("P1_Line1a-f_CB[3]", "/1D"),
            "substitute_sponsor": ("P1_Line1a-f_CB[5]", "/1F"),
        },
        "i864_physical_same_as_mailing": {
            True: ("P1_Line3_Checkbox[0]", "/Y"),
            False: ("P1_Line3_Checkbox[1]", "/N"),
        },
        "petitioner_citizenship_status": {
            "us_citizen": ("P4_Line11a_Checkbox[0]", "/A"),
            "us_national": ("P4_Line11b_Checkbox[0]", "/B"),
            "lpr": ("P4_Line11c_Checkbox[0]", "/C"),
        },
        "spouse_us_military": {
            True: ("P4_Line14_Checkboxes[0]", "/Y"),
            False: ("P4_Line14_Checkboxes[1]", "/N"),
        },
        "i864_only_principal_immigrant": {
            True: ("P3_Line1_Checkbox[0]", "/Y"),
            False: ("P3_Line1_Checkbox[1]", "/N"),
        },
        "i864_sponsoring_family_members": {
            True: ("P3_Line2_SponsoringFamily[0]", "/Y"),
        },
        "employment_status": {
            "employed": ("P6_Line1_Checkbox[0]", "/ Y"),
            "self_employed": ("P6_Line4_Checkbox[0]", "/ Y"),
            "retired": ("P6_Line5_Checkbox[0]", "/Y "),
            "unemployed": ("P6_Line6_Checkbox[0]", "/ Y"),
        },
        "i864_filed_recent_tax_return": {
            True: ("P6_Line18a_Checkbox[0]", "/Y"),
            False: ("P6_Line18a_Checkbox[1]", "/N"),
        },
    },
    "i131": {
        "i131_application_type": {
            "advanced_parole_i485_pending": ("form1[0].P1[0].CB_AppType[4]", "/5"),
        },
        "beneficiary_sex": {
            "female": ("Part2_Line8_Gender[0]", "/F"),
            "male": ("Part2_Line8_Gender[1]", "/M"),
        },
        "beneficiary_ethnicity": {
            "not_hispanic_or_latino": ("P3_Line1_Ethnicity[0]", "/NH"),
            "hispanic_or_latino": ("P3_Line1_Ethnicity[1]", "/H"),
        },
        "beneficiary_race_primary": {
            "black": ("P3_Line2_Race_Black[0]", "/B"),
            "pacific_islander": ("P3_Line2_Race_Hawaiian[0]", "/H"),
            "american_indian": ("P3_Line2_Race_American[0]", "/I"),
            "asian": ("P3_Line2_Race_Asian[0]", "/A"),
            "white": ("P3_Line2_Race_White[0]", "/W"),
        },
        "beneficiary_eye_color": {
            "brown": ("P3_Line5_EyeColor[0]", "/BRN"),
            "gray": ("P3_Line5_EyeColor[1]", "/GRY"),
            "maroon": ("P3_Line5_EyeColor[2]", "/MRN"),
            "other": ("P3_Line5_EyeColor[3]", "/OTH"),
            "pink": ("P3_Line5_EyeColor[4]", "/PNK"),
            "hazel": ("P3_Line5_EyeColor[5]", "/HZL"),
            "green": ("P3_Line5_EyeColor[6]", "/GRN"),
            "blue": ("P3_Line5_EyeColor[7]", "/BLU"),
            "black": ("P3_Line5_EyeColor[8]", "/BLK"),
        },
        "beneficiary_hair_color": {
            "bald": ("P3_Line6_HairColor[0]", "/BLD"),
            "blond": ("P3_Line6_HairColor[1]", "/BND"),
            "gray": ("P3_Line6_HairColor[2]", "/GRY"),
            "sandy": ("P3_Line6_HairColor[3]", "/SDY"),
            "other": ("P3_Line6_HairColor[4]", "/OTH"),
            "white": ("P3_Line6_HairColor[5]", "/WHT"),
            "red": ("P3_Line6_HairColor[6]", "/RED"),
            "brown": ("P3_Line6_HairColor[7]", "/BRN"),
            "black": ("P3_Line6_HairColor[8]", "/BLK"),
        },
        "i131_removal_proceedings": {
            True: ("P4_Line1_YesNo[0]", "/Y"),
            False: ("P4_Line1_YesNo[1]", "/N"),
        },
        "i131_prior_reentry_refugee_document": {
            True: ("P4_Line2a_YesNo[0]", "/Y"),
            False: ("P4_Line2a_YesNo[1]", "/N"),
        },
        "i131_prior_advance_parole": {
            True: ("P4_Line3a_YesNo[0]", "/Y"),
            False: ("P4_Line3a_YesNo[1]", "/N"),
        },
        "i131_replacement_request": {
            True: ("P4_Line4_YesNo[0]", "/Y"),
            False: ("P4_Line4_YesNo[1]", "/N"),
        },
        "i131_processing_location": {
            "domestic_address": ("P4_Line7a[1]", "/A"),
            "overseas_office": ("P4_Line7a[0]", "/B"),
        },
        "i131_trip_count": {
            "one": ("P7_Line4_CB[0]", "/O"),
            "multiple": ("P7_Line4_CB[1]", "/M"),
        },
    },
}

UNIT_FIELD_MAP: dict[str, dict[str, tuple[str, str, str, str]]] = {
    "i765": {
        "beneficiary_mailing_address_line2": (
            "Pt2Line5_Unit[2]",
            "Pt2Line5_Unit[0]",
            "Pt2Line5_Unit[1]",
            "Pt2Line5_AptSteFlrNumber[0]",
        ),
        "beneficiary_physical_address_line2": (
            "Pt2Line7_Unit[2]",
            "Pt2Line7_Unit[0]",
            "Pt2Line7_Unit[1]",
            "Pt2Line7_AptSteFlrNumber[0]",
        ),
    },
    "i864": {
        "petitioner_current_address_line2": (
            "P4_Line2c_Unit[0]",
            "P4_Line2c_Unit[1]",
            "P4_Line2c_Unit[2]",
            "P4_Line2d_AptSteFlrNumber[0]",
        ),
        "beneficiary_mailing_address_line2": (
            "P2_Line2_Unit[0]",
            "P2_Line2_Unit[1]",
            "P2_Line2_Unit[2]",
            "P2_Line2_AptSteFlrNumber[0]",
        ),
    },
    "i131": {
        "beneficiary_mailing_address_line2": (
            "Part2_Line3_Unit[1]",
            "Part2_Line3_Unit[0]",
            "Part2_Line3_Unit[2]",
            "Part2_Line3_AptSteFlrNumber[0]",
        ),
        "beneficiary_physical_address_line2": (
            "Part2_Line4_Unit[1]",
            "Part2_Line4_Unit[0]",
            "Part2_Line4_Unit[2]",
            "Part2_Line4_AptSteFlrNumber[0]",
        ),
    },
}

I864_HOUSEHOLD_DEFAULT_TEXT_VALUES = {
    "P5_Line2_Yourself[0]": "1",
    "P5_Line3_Married[0]": "0",
    "P5_Line4_DependentChildren[0]": "0",
    "P5_Line5_OtherDependents[0]": "0",
    "P5_Line6_Sponsors[0]": "0",
    "P5_Line7_SameResidence[0]": "0",
}


@dataclass(frozen=True)
class FormPdfFieldPayload:
    text_values: dict[str, str]
    checkbox_values: dict[str, str]
    mapped_questions: list[dict[str, Any]]
    unmapped_answered_questions: list[dict[str, Any]]
    missing_template_fields: list[str]


@dataclass(frozen=True)
class GeneratedFormPdf:
    case_id: UUID
    form_key: str
    output_path: Path
    template_path: Path
    generation_status: str
    ready_for_pdf_generation: bool
    field_count: int
    text_field_count: int
    checkbox_field_count: int
    mapped_question_count: int
    unmapped_answer_count: int
    missing_required_count: int
    blocking_flag_count: int
    outside_niche_flag_count: int
    low_confidence_count: int
    warnings: list[str]
    mapped_questions: list[dict[str, Any]]
    unmapped_answered_questions: list[dict[str, Any]]
    missing_template_fields: list[str]


def _value_is_answered(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _as_pdf_date(value: Any) -> str:
    raw = str(value).strip()
    if not raw:
        return ""
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%m/%d/%Y")
        except ValueError:
            continue
    return raw


def _normalize_us_state_code(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    upper = raw.upper()
    if upper in US_STATE_CODES:
        return upper
    return US_STATE_NAME_TO_CODE.get("".join(character for character in raw.lower() if character.isalpha()), "")


def _as_pdf_phone(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    digits = "".join(character for character in raw if character.isdigit())
    return digits or raw


def _as_pdf_positive_integer(value: Any) -> str:
    if isinstance(value, bool):
        return ""
    if isinstance(value, int):
        return str(value) if value > 0 else ""
    if isinstance(value, str):
        raw = value.strip()
        return raw if raw.isdigit() and int(raw) > 0 else ""
    return ""


def _as_three_weight_digits(value: Any) -> str:
    digits = "".join(character for character in str(value) if character.isdigit())
    if not digits:
        return ""
    return digits.zfill(3)[-3:]


def _as_i765_immigration_status(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    normalized = normalize_class_of_admission(raw)
    raw_lower = raw.lower().replace("-", "").replace(" ", "")
    if normalized == "B-2" or raw_lower in {"visitor", "b2", "b2visitor"}:
        return "B-2 visitor"
    if raw_lower == "parolee":
        return "parolee"
    if raw_lower in {"nostatus", "nostatusorcategory"}:
        return "no status or category" if "category" in raw_lower else "no status"
    labels = {
        "B-1": "B-1 visitor for business",
        "F-1": "F-1 student",
        "F-2": "F-2 dependent",
        "J-1": "J-1 exchange visitor",
        "J-2": "J-2 dependent",
        "M-1": "M-1 vocational student",
        "M-2": "M-2 dependent",
    }
    if normalized in labels:
        return labels[normalized]
    return raw if " " in raw else normalized


def _as_pdf_value(question_id: str, value: Any) -> str:
    if question_id == "beneficiary_class_of_admission":
        return normalize_class_of_admission(value)
    if question_id == "i131_expected_trip_length":
        return _as_pdf_positive_integer(value)
    if question_id in STATE_QUESTION_IDS:
        return _normalize_us_state_code(value) or str(value).strip()
    if question_id in PHONE_QUESTION_IDS:
        return _as_pdf_phone(value)
    if question_id == "i765_eligibility_category" and value == "c9_pending_i485":
        return "c"
    if question_id in DATE_QUESTION_IDS:
        return _as_pdf_date(value)
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (int, float)):
        return str(value)
    return str(value).strip()


def _fill_i765_eligibility_category(
    value: Any,
    text_values: dict[str, str],
    mapped_fields: list[str],
) -> None:
    if value == "c9_pending_i485":
        parts = ("c", "9", "")
    elif value == "other":
        parts = ("", "", "")
    else:
        return
    for field_name, part in zip(("section_1[0]", "section_2[0]", "section_3[0]"), parts, strict=True):
        text_values[field_name] = part
        mapped_fields.append(field_name)


def build_form_pdf_field_payload(
    form_key: str,
    answers: dict[str, Any],
    available_fields: set[str] | None = None,
) -> FormPdfFieldPayload:
    normalized_form_key = normalize_form_key(form_key)
    question_by_id = {question["id"]: question for question in all_supplemental_form_questions(normalized_form_key)}
    if normalized_form_key in {"i130", "i130a"}:
        family_payload = (
            build_i130_pdf_field_payload(answers, available_fields)
            if normalized_form_key == "i130"
            else build_i130a_pdf_field_payload(answers, available_fields)
        )
        mapped_question_ids = {
            entry["field_key"] for entry in family_payload.mapped_fields if isinstance(entry.get("field_key"), str)
        }
        mapped_questions = [
            {
                "question_id": entry["field_key"],
                "label": question_by_id.get(entry["field_key"], {}).get("label", entry["field_key"]),
                "pdf_fields": entry["pdf_fields"],
            }
            for entry in family_payload.mapped_fields
            if isinstance(entry.get("field_key"), str)
        ]
        unmapped_answered_questions = []
        # The combined address answer is written through its street, city, state, and ZIP parts.
        if "beneficiary_current_address_line1" in mapped_question_ids:
            mapped_question_ids.add("beneficiary_current_address")
        for question_id, value in sorted(_without_zip_postal_aliases(answers).items()):
            if question_id in mapped_question_ids or question_id in NON_PDF_CONTROL_QUESTIONS or not _value_is_answered(value):
                continue
            question = question_by_id.get(question_id, {})
            unmapped_answered_questions.append(
                {
                    "question_id": question_id,
                    "label": question.get("label", question_id),
                    "pdf_ref": question.get("pdf_ref", ""),
                }
            )
        return FormPdfFieldPayload(
            text_values=family_payload.text_values,
            checkbox_values=family_payload.checkbox_values,
            mapped_questions=mapped_questions,
            unmapped_answered_questions=unmapped_answered_questions,
            missing_template_fields=family_payload.missing_template_fields,
        )

    text_values: dict[str, str] = {}
    checkbox_values: dict[str, str] = {}
    mapped_questions: list[dict[str, Any]] = []
    mapped_question_ids: set[str] = set()

    for question_id, field_names in TEXT_FIELD_MAP.get(normalized_form_key, {}).items():
        value = answers.get(question_id)
        if not _value_is_answered(value):
            continue
        if question_id == "i765_eligibility_category":
            selected_fields: list[str] = []
            _fill_i765_eligibility_category(value, text_values, selected_fields)
            if not selected_fields:
                continue
            field_names = tuple(selected_fields)
        elif normalized_form_key == "i131" and question_id == "beneficiary_weight_pounds":
            digits = _as_three_weight_digits(value)
            if not digits:
                continue
            for field_name, digit in zip(field_names, digits, strict=True):
                text_values[field_name] = digit
        elif normalized_form_key == "i765" and question_id in {
            "beneficiary_class_of_admission",
            "beneficiary_current_immigration_status",
        }:
            pdf_value = _as_i765_immigration_status(value)
            for field_name in field_names:
                text_values[field_name] = pdf_value
        else:
            pdf_value = _as_pdf_value(question_id, value)
            for field_name in field_names:
                text_values[field_name] = pdf_value
        mapped_question_ids.add(question_id)
        mapped_questions.append(
            {
                "question_id": question_id,
                "label": question_by_id.get(question_id, {}).get("label", question_id),
                "pdf_fields": list(field_names),
            }
        )

    for question_id, choices in CHECKBOX_FIELD_MAP.get(normalized_form_key, {}).items():
        value = answers.get(question_id)
        if not _value_is_answered(value):
            continue
        selected = choices.get(value)
        if not selected:
            continue
        field_name, appearance = selected
        checkbox_values[field_name] = appearance
        mapped_question_ids.add(question_id)
        mapped_questions.append(
            {
                "question_id": question_id,
                "label": question_by_id.get(question_id, {}).get("label", question_id),
                "pdf_fields": [field_name],
            }
        )

    for question_id, unit_fields in UNIT_FIELD_MAP.get(normalized_form_key, {}).items():
        value = answers.get(question_id)
        if not _value_is_answered(value):
            continue
        before = set(text_values) | set(checkbox_values)
        _add_unit_fields(
            text_values=text_values,
            checkbox_values=checkbox_values,
            value=value,
            apt_field=unit_fields[0],
            ste_field=unit_fields[1],
            flr_field=unit_fields[2],
            number_field=unit_fields[3],
        )
        selected_fields = sorted((set(text_values) | set(checkbox_values)) - before)
        if selected_fields:
            mapped_question_ids.add(question_id)
            mapped_questions.append(
                {
                    "question_id": question_id,
                    "label": question_by_id.get(question_id, {}).get("label", question_id),
                    "pdf_fields": selected_fields,
                }
            )

    if normalized_form_key == "i864":
        for field_name, value in I864_HOUSEHOLD_DEFAULT_TEXT_VALUES.items():
            text_values.setdefault(field_name, value)

    available = available_fields or set()
    filled_fields = set(text_values) | set(checkbox_values)
    missing_template_fields = sorted(filled_fields - available) if available else []

    unmapped_answered_questions = []
    for question_id, value in sorted(answers.items()):
        if question_id in mapped_question_ids or question_id in NON_PDF_CONTROL_QUESTIONS or not _value_is_answered(value):
            continue
        question = question_by_id.get(question_id, {})
        unmapped_answered_questions.append(
            {
                "question_id": question_id,
                "label": question.get("label", question_id),
                "pdf_ref": question.get("pdf_ref", ""),
            }
        )

    return FormPdfFieldPayload(
        text_values=text_values,
        checkbox_values=checkbox_values,
        mapped_questions=mapped_questions,
        unmapped_answered_questions=unmapped_answered_questions,
        missing_template_fields=missing_template_fields,
    )


def generate_form_pdf_from_answers(
    *,
    case_id: UUID,
    form_key: str,
    answers: dict[str, Any],
    template_path: Path | None = None,
    output_path: Path | None = None,
    output_dir: Path = DEFAULT_FORM_OUTPUT_DIR,
    allow_incomplete: bool = True,
    preview: dict[str, Any] | None = None,
) -> GeneratedFormPdf:
    config = get_supplemental_form_config(form_key)
    normalized_form_key = config["form_key"]
    final_template_path = template_path or Path(config["local_template_pdf"])
    if not final_template_path.exists():
        raise ValueError(f"{config['form_code']} PDF template not found: {final_template_path}")

    preview = preview or {
        "generation_status": "ready_for_user_review",
        "ready_for_pdf_generation": True,
        "missing_required_count": 0,
        "blocking_flag_count": 0,
        "outside_niche_flag_count": 0,
        "low_confidence_count": 0,
    }
    if not allow_incomplete and not preview["ready_for_pdf_generation"]:
        raise ValueError(
            f"{config['form_code']} answers are not ready for PDF generation: {preview['generation_status']}"
        )

    reader = PdfReader(final_template_path)
    available_fields = _template_field_names(reader)
    payload = build_form_pdf_field_payload(normalized_form_key, answers, available_fields)

    try:
        writer = PdfWriter(clone_from=reader)
    except ValueError:
        root = reader.trailer.get("/Root", {})
        if hasattr(root, "pop"):
            root.pop(NameObject("/Metadata"), None)
        try:
            writer = PdfWriter(clone_from=reader)
        except ValueError:
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            acroform = root.get("/AcroForm") if hasattr(root, "get") else None
            if acroform:
                writer._root_object.update({NameObject("/AcroForm"): acroform})
    _use_saved_appearances(writer)
    _set_text_values(writer, payload.text_values)
    _set_checkbox_values(writer, payload.checkbox_values)

    final_output_path = output_path or output_dir / f"{case_id}-{normalized_form_key}.pdf"
    final_output_path.parent.mkdir(parents=True, exist_ok=True)
    with final_output_path.open("wb") as handle:
        writer.write(handle)

    warnings = [
        "Review every generated value against the source documents before filing.",
        "The generated PDF is not legal advice and must be printed, reviewed, and signed in ink where required.",
    ]
    if not preview["ready_for_pdf_generation"]:
        warnings.append(
            f"This is a review draft because generation status is {preview['generation_status']}."
        )
    if payload.unmapped_answered_questions:
        warnings.append("Some answered questionnaire fields do not yet have explicit PDF field mappings.")
    if payload.missing_template_fields:
        warnings.append("Some mapped PDF fields were not present in the selected template.")

    return GeneratedFormPdf(
        case_id=case_id,
        form_key=normalized_form_key,
        output_path=final_output_path,
        template_path=final_template_path,
        generation_status=preview["generation_status"],
        ready_for_pdf_generation=preview["ready_for_pdf_generation"],
        field_count=len(payload.text_values) + len(payload.checkbox_values),
        text_field_count=len(payload.text_values),
        checkbox_field_count=len(payload.checkbox_values),
        mapped_question_count=len({entry["question_id"] for entry in payload.mapped_questions}),
        unmapped_answer_count=len(payload.unmapped_answered_questions),
        missing_required_count=preview["missing_required_count"],
        blocking_flag_count=preview["blocking_flag_count"],
        outside_niche_flag_count=preview["outside_niche_flag_count"],
        low_confidence_count=preview["low_confidence_count"],
        warnings=warnings,
        mapped_questions=payload.mapped_questions,
        unmapped_answered_questions=payload.unmapped_answered_questions,
        missing_template_fields=payload.missing_template_fields,
    )


def generate_form_pdf(
    *,
    session: Session,
    case_id: UUID,
    form_key: str,
    template_path: Path | None = None,
    output_path: Path | None = None,
    output_dir: Path = DEFAULT_FORM_OUTPUT_DIR,
    allow_incomplete: bool = True,
) -> GeneratedFormPdf:
    preview = build_form_fill_preview(session, case_id, form_key)
    state = get_form_state(session, case_id, form_key)
    answers = dict(state["answers"])
    merged = get_merged_case_intake(session, case_id)
    if normalize_form_key(form_key) in {"i765", "i131"}:
        i485_projection = build_i485_intake_projection(get_i485_state(session, case_id)["answers"])
        merged = {**merged, **i485_projection}
    for proposal in build_form_answer_proposals_from_case_data(form_key, merged):
        if not _value_is_answered(answers.get(proposal["question_id"])):
            answers[proposal["question_id"]] = proposal["value"]
    return generate_form_pdf_from_answers(
        case_id=case_id,
        form_key=form_key,
        answers=answers,
        template_path=template_path,
        output_path=output_path,
        output_dir=output_dir,
        allow_incomplete=allow_incomplete,
        preview=preview,
    )
