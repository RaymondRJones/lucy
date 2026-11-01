"""Builds and generates Forms I-130, I-130A, and G-1145."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject

from app.content.admission_classes import i130_class_of_admission_code
from app.core.config import settings
from app.services.case_facts import value_is_answered
from app.services.pdf_fields import (
    OVERLONG_WARNING,
    add_unit_fields,
    as_pdf_date,
    employment_continuation_line,
    entry_has_content,
    field_length_warning,
    fill_continuation_slots,
    normalize_us_state,
    overlong_field_names,
    set_checkbox_values,
    set_text_values,
    template_field_names,
    unprintable_character_warning,
    use_saved_appearances,
    without_notes,
)

DEFAULT_FAMILY_OUTPUT_DIR = settings.generated_dir
DEFAULT_FAMILY_TEMPLATE_PATHS = {
    "g1145": Path("blank-immigration-documents/g-1145.pdf"),
    "i130": Path("blank-immigration-documents/i-130.pdf"),
    "i130a": Path("blank-immigration-documents/i-130a.pdf"),
}

I130_DATE_FIELD_KEYS = {
    "petitioner_date_of_birth",
    "petitioner_physical_address_from",
    "petitioner_physical_address_to",
    "petitioner_prior_address_from",
    "petitioner_prior_address_to",
    "marriage_date",
    "petitioner_spouse1_marriage_ended",
    "petitioner_parent1_date_of_birth",
    "petitioner_parent2_date_of_birth",
    "petitioner_naturalization_certificate_date",
    "petitioner_lpr_date_of_admission",
    "petitioner_current_employment_from",
    "petitioner_current_employment_to",
    "petitioner_prior_employment_from",
    "petitioner_prior_employment_to",
    "beneficiary_date_of_birth",
    "beneficiary_spouse1_marriage_ended",
    "beneficiary_spouse2_marriage_ended",
    "beneficiary_last_arrival_date",
    "beneficiary_status_expires_on",
    "beneficiary_current_status_expires_on",
    "beneficiary_passport_expiration",
    "beneficiary_current_employment_from",
    "beneficiary_immigration_proceedings_date",
    "beneficiary_last_shared_address_from",
    "beneficiary_last_shared_address_to",
    "prior_i130_date_filed",
}

I130A_DATE_FIELD_KEYS = {
    "parent1_date_of_birth",
    "parent2_date_of_birth",
    "beneficiary_address_since",
    "beneficiary_current_address_since",
    "beneficiary_current_employment_from",
    "beneficiary_current_employment_to",
}

I130_TEXT_FIELD_MAP: dict[str, tuple[str, ...]] = {
    "petitioner_a_number": ("Pt2Line1_AlienNumber[0]",),
    "petitioner_uscis_online_account_number": ("Pt2Line2_USCISOnlineActNumber[0]",),
    "petitioner_last_name": ("Pt2Line4a_FamilyName[0]",),
    "petitioner_first_name": ("Pt2Line4b_GivenName[0]",),
    "petitioner_middle_name": ("Pt2Line4c_MiddleName[0]",),
    "petitioner_other_last_name": ("Pt2Line5a_FamilyName[0]",),
    "petitioner_other_first_name": ("Pt2Line5b_GivenName[0]",),
    "petitioner_other_middle_name": ("Pt2Line5c_MiddleName[0]",),
    "petitioner_city_of_birth": ("Pt2Line6_CityTownOfBirth[0]",),
    "petitioner_date_of_birth": ("Pt2Line8_DateofBirth[0]",),
    "petitioner_country_of_birth": ("Pt2Line7_CountryofBirth[0]",),
    "petitioner_social_security_number": ("Pt2Line11_SSN[0]",),
    "petitioner_mailing_in_care_of": ("Pt2Line10_InCareofName[0]",),
    "petitioner_current_address_line1": ("Pt2Line10_StreetNumberName[0]",),
    "petitioner_current_city": ("Pt2Line10_CityOrTown[0]",),
    "petitioner_current_province": ("Pt2Line10_Province[0]",),
    "petitioner_current_postal_code": ("Pt2Line10_PostalCode[0]",),
    "petitioner_current_state": ("Pt2Line10_State[0]",),
    "petitioner_current_zip": ("Pt2Line10_ZipCode[0]",),
    "petitioner_current_country": ("Pt2Line10_Country[0]",),
    "petitioner_physical_address_line1": ("Pt2Line12_StreetNumberName[0]",),
    "petitioner_physical_city": ("Pt2Line12_CityOrTown[0]",),
    "petitioner_physical_state": ("Pt2Line12_State[0]",),
    "petitioner_physical_zip": ("Pt2Line12_ZipCode[0]",),
    "petitioner_physical_province": ("Pt2Line12_Province[0]",),
    "petitioner_physical_postal_code": ("Pt2Line12_PostalCode[0]",),
    "petitioner_physical_country": ("Pt2Line12_Country[0]",),
    "petitioner_physical_address_from": ("Pt2Line13a_DateFrom[0]",),
    "petitioner_physical_address_to": ("Pt2Line13b_DateTo[0]",),
    "petitioner_prior_address_line1": ("Pt2Line14_StreetNumberName[0]",),
    "petitioner_prior_city": ("Pt2Line14_CityOrTown[0]",),
    "petitioner_prior_state": ("Pt2Line14_State[0]",),
    "petitioner_prior_zip": ("Pt2Line14_ZipCode[0]",),
    "petitioner_prior_province": ("Pt2Line14_Province[0]",),
    "petitioner_prior_postal_code": ("Pt2Line14_PostalCode[0]",),
    "petitioner_prior_country": ("Pt2Line14_Country[0]",),
    "petitioner_prior_address_from": ("Pt2Line15a_DateFrom[0]",),
    "petitioner_prior_address_to": ("Pt2Line15b_DateTo[0]",),
    "petitioner_phone": ("Pt6Line3_DaytimePhoneNumber[0]",),
    "petitioner_mobile_phone": ("Pt6Line4_MobileNumber[0]",),
    "petitioner_email": ("Pt6Line5_Email[0]",),
    "petitioner_marriage_count": ("Pt2Line16_NumberofMarriages[0]",),
    "marriage_date": ("Pt2Line18_DateOfMarriage[0]", "Pt4Line19_DateOfMarriage[0]"),
    # USCIS names this template field without the "2" used by the rest of Part 2.
    "petitioner_spouse1_last_name": ("PtLine20a_FamilyName[0]",),
    "petitioner_spouse1_first_name": ("Pt2Line20b_GivenName[0]",),
    "petitioner_spouse1_middle_name": ("Pt2Line20c_MiddleName[0]",),
    "petitioner_spouse1_marriage_ended": ("Pt2Line21_DateMarriageEnded[0]",),
    "marriage_place_city": ("Pt2Line19a_CityTown[0]", "Pt4Line20a_CityTown[0]"),
    "marriage_place_state": ("Pt2Line19b_State[0]", "Pt4Line20b_State[0]"),
    "marriage_place_province": ("Pt2Line19c_Province[0]", "Pt4Line20c_Province[0]"),
    "marriage_place_country": ("Pt2Line19d_Country[0]", "Pt4Line20d_Country[0]"),
    "petitioner_parent1_last_name": ("Pt2Line24_FamilyName[0]",),
    "petitioner_parent1_first_name": ("Pt2Line24_GivenName[0]",),
    "petitioner_parent1_middle_name": ("Pt2Line24_MiddleName[0]",),
    "petitioner_parent1_date_of_birth": ("Pt2Line25_DateofBirth[0]",),
    "petitioner_parent1_country_of_birth": ("Pt2Line27_CountryofBirth[0]",),
    "petitioner_parent1_city_of_residence": ("Pt2Line28_CityTownOrVillageOfResidence[0]",),
    "petitioner_parent1_country_of_residence": ("Pt2Line29_CountryOfResidence[0]",),
    "petitioner_parent2_last_name": ("Pt2Line30a_FamilyName[0]",),
    "petitioner_parent2_first_name": ("Pt2Line30b_GivenName[0]",),
    "petitioner_parent2_middle_name": ("Pt2Line30c_MiddleName[0]",),
    "petitioner_parent2_date_of_birth": ("Pt2Line31_DateofBirth[0]",),
    "petitioner_parent2_country_of_birth": ("Pt2Line33_CountryofBirth[0]",),
    "petitioner_parent2_city_of_residence": ("Pt2Line34_CityTownOrVillageOfResidence[0]",),
    "petitioner_parent2_country_of_residence": ("Pt2Line35_CountryOfResidence[0]",),
    "petitioner_naturalization_certificate_number": ("Pt2Line37a_CertificateNumber[0]",),
    "petitioner_naturalization_certificate_place": ("Pt2Line37b_PlaceOfIssuance[0]",),
    "petitioner_naturalization_certificate_date": ("Pt2Line37c_DateOfIssuance[0]",),
    "petitioner_lpr_class_of_admission": ("Pt2Line40a_ClassOfAdmission[0]",),
    "petitioner_lpr_date_of_admission": ("Pt2Line40b_DateOfAdmission[0]",),
    "petitioner_lpr_admission_city": ("Pt2Line40d_CityOrTown[0]",),
    "petitioner_lpr_admission_state": ("Pt2Line40e_State[0]",),
    "petitioner_current_employer": ("Pt2Line40_EmployerOrCompName[0]",),
    "petitioner_current_employer_address_line1": ("Pt2Line41_StreetNumberName[0]",),
    "petitioner_current_employer_city": ("Pt2Line41_CityOrTown[0]",),
    "petitioner_current_employer_state": ("Pt2Line41_State[0]",),
    "petitioner_current_employer_zip": ("Pt2Line41_ZipCode[0]",),
    "petitioner_current_employer_province": ("Pt2Line41_Province[0]",),
    "petitioner_current_employer_postal_code": ("Pt2Line41_PostalCode[0]",),
    "petitioner_current_employer_country": ("Pt2Line41_Country[0]",),
    "petitioner_current_occupation": ("Pt2Line42_Occupation[0]",),
    "petitioner_current_employment_from": ("Pt2Line43a_DateFrom[0]",),
    "petitioner_current_employment_to": ("Pt2Line43b_DateTo[0]",),
    "petitioner_prior_employer": ("Pt2Line44_EmployerOrOrgName[0]",),
    "petitioner_prior_employer_address_line1": ("Pt2Line45_StreetNumberName[0]",),
    "petitioner_prior_employer_city": ("Pt2Line45_CityOrTown[0]",),
    "petitioner_prior_employer_state": ("Pt2Line45_State[0]",),
    "petitioner_prior_employer_zip": ("Pt2Line45_ZipCode[0]",),
    "petitioner_prior_employer_province": ("Pt2Line45_Province[0]",),
    "petitioner_prior_employer_postal_code": ("Pt2Line45_PostalCode[0]",),
    "petitioner_prior_employer_country": ("Pt2Line45_Country[0]",),
    "petitioner_prior_occupation": ("Pt2Line46_Occupation[0]",),
    "petitioner_prior_employment_from": ("Pt2Line47a_DateFrom[0]",),
    "petitioner_prior_employment_to": ("Pt2Line47b_DateTo[0]",),
    "beneficiary_a_number": ("Pt4Line1_AlienNumber[0]",),
    "beneficiary_uscis_online_account_number": ("Pt4Line2_USCISOnlineActNumber[0]",),
    "beneficiary_social_security_number": ("Pt4Line3_SSN[0]",),
    "beneficiary_last_name": ("Pt4Line4a_FamilyName[0]",),
    "beneficiary_first_name": ("Pt4Line4b_GivenName[0]",),
    "beneficiary_middle_name": ("Pt4Line4c_MiddleName[0]",),
    "beneficiary_other_last_name": ("P4Line5a_FamilyName[0]",),
    "beneficiary_other_first_name": ("Pt4Line5b_GivenName[0]",),
    "beneficiary_other_middle_name": ("Pt4Line5c_MiddleName[0]",),
    "beneficiary_city_of_birth": ("Pt4Line7_CityTownOfBirth[0]",),
    "beneficiary_country_of_birth": ("Pt4Line8_CountryOfBirth[0]",),
    "beneficiary_date_of_birth": ("Pt4Line9_DateOfBirth[0]",),
    "beneficiary_current_address_line1": ("Pt4Line11_StreetNumberName[0]",),
    "beneficiary_current_city": ("Pt4Line11_CityOrTown[0]",),
    "beneficiary_current_state": ("Pt4Line11_State[0]",),
    "beneficiary_current_zip": ("Pt4Line11_ZipCode[0]",),
    "beneficiary_current_province": ("Pt4Line11_Province[0]",),
    "beneficiary_current_postal_code": ("Pt4Line11_PostalCode[0]",),
    "beneficiary_current_country": ("Pt4Line11_Country[0]",),
    "beneficiary_intended_us_address_line1": ("Pt4Line12a_StreetNumberName[0]",),
    "beneficiary_intended_us_city": ("Pt4Line12c_CityOrTown[0]",),
    "beneficiary_intended_us_state": ("Pt4Line12d_State[0]",),
    "beneficiary_intended_us_zip": ("Pt4Line12e_ZipCode[0]",),
    "beneficiary_foreign_address_line1": ("Pt4Line13_StreetNumberName[0]",),
    "beneficiary_foreign_city": ("Pt4Line13_CityOrTown[0]",),
    "beneficiary_foreign_province": ("Pt4Line13_Province[0]",),
    "beneficiary_foreign_postal_code": ("Pt4Line13_PostalCode[0]",),
    "beneficiary_foreign_country": ("Pt4Line13_Country[0]",),
    "beneficiary_phone": ("Pt4Line14_DaytimePhoneNumber[0]",),
    "beneficiary_mobile_phone": ("Pt4Line15_MobilePhoneNumber[0]",),
    "beneficiary_email": ("Pt4Line16_EmailAddress[0]",),
    "beneficiary_marriage_count": ("Pt4Line17_NumberofMarriages[0]",),
    "beneficiary_spouse1_last_name": ("Pt4Line16a_FamilyName[0]",),
    "beneficiary_spouse1_first_name": ("Pt4Line16b_GivenName[0]",),
    "beneficiary_spouse1_middle_name": ("Pt4Line16c_MiddleName[0]",),
    "beneficiary_spouse1_marriage_ended": ("Pt4Line17_DateMarriageEnded[0]",),
    "beneficiary_spouse2_last_name": ("Pt4Line18a_FamilyName[0]",),
    "beneficiary_spouse2_first_name": ("Pt4Line18b_GivenName[0]",),
    "beneficiary_spouse2_middle_name": ("Pt4Line18c_MiddleName[0]",),
    "beneficiary_spouse2_marriage_ended": ("Pt4Line17_DateMarriageEnded[1]",),
    "beneficiary_class_of_admission": ("Pt4Line21a_ClassOfAdmission[0]",),
    "beneficiary_i94_number": ("Pt4Line21b_ArrivalDeparture[0]",),
    "beneficiary_last_arrival_date": ("Pt4Line21c_DateOfArrival[0]",),
    "beneficiary_status_expires_on": ("Pt4Line21d_DateExpired[0]",),
    "beneficiary_current_status_expires_on": ("Pt4Line21d_DateExpired[0]",),
    "beneficiary_passport_number": ("Pt4Line22_PassportNumber[0]",),
    "beneficiary_travel_document_number": ("Pt4Line23_TravelDocNumber[0]",),
    "beneficiary_passport_country": ("Pt4Line24_CountryOfIssuance[0]",),
    "beneficiary_passport_expiration": ("Pt4Line25_ExpDate[0]",),
    "beneficiary_current_employer_or_school": ("Pt4Line26_NameOfCompany[0]",),
    "beneficiary_current_employer_address_line1": ("Pt4Line26_StreetNumberName[0]",),
    "beneficiary_current_employer_city": ("Pt4Line26_CityOrTown[0]",),
    "beneficiary_current_employer_state": ("Pt4Line26_State[0]",),
    "beneficiary_current_employer_zip": ("Pt4Line26_ZipCode[0]",),
    "beneficiary_current_employer_province": ("Pt4Line26_Province[0]",),
    "beneficiary_current_employer_postal_code": ("Pt4Line26_PostalCode[0]",),
    "beneficiary_current_employer_country": ("Pt4Line26_Country[0]",),
    "beneficiary_current_employment_from": ("Pt4Line27_DateEmploymentBegan[0]",),
    "beneficiary_immigration_proceedings_city": ("Pt4Line55a_CityOrTown[0]",),
    "beneficiary_immigration_proceedings_state": ("Pt4Line55b_State[0]",),
    "beneficiary_immigration_proceedings_date": ("Pt4Line56_Date[0]",),
    "beneficiary_native_last_name": ("Pt4Line55a_FamilyName[0]",),
    "beneficiary_native_first_name": ("Pt4Line55b_GivenName[0]",),
    "beneficiary_native_middle_name": ("Pt4Line55c_MiddleName[0]",),
    "beneficiary_native_address_line1": ("Pt4Line56_StreetNumberName[0]",),
    "beneficiary_native_city": ("Pt4Line56_CityOrTown[0]",),
    "beneficiary_native_province": ("Pt4Line56_Province[0]",),
    "beneficiary_native_postal_code": ("Pt4Line56_PostalCode[0]",),
    "beneficiary_native_country": ("Pt4Line56_Country[0]",),
    "beneficiary_last_shared_address_line1": ("Pt4Line57_StreetNumberName[0]",),
    "beneficiary_last_shared_city": ("Pt4Line57_CityOrTown[0]",),
    "beneficiary_last_shared_state": ("Pt4Line57_State[0]",),
    "beneficiary_last_shared_zip": ("Pt4Line57_ZipCode[0]",),
    "beneficiary_last_shared_province": ("Pt4Line57_Province[0]",),
    "beneficiary_last_shared_postal_code": ("Pt4Line57_PostalCode[0]",),
    "beneficiary_last_shared_country": ("Pt4Line57_Country[0]",),
    "beneficiary_last_shared_address_from": ("Pt4Line58a_DateFrom[0]",),
    "beneficiary_last_shared_address_to": ("Pt4Line58b_DateTo[0]",),
    "beneficiary_adjustment_city": ("Pt4Line60a_CityOrTown[0]",),
    "beneficiary_adjustment_state": ("Pt4Line60b_State[0]",),
    "beneficiary_consular_city": ("Pt4Line61a_CityOrTown[0]",),
    "beneficiary_consular_province": ("Pt4Line61b_Province[0]",),
    "beneficiary_consular_country": ("Pt4Line61c_Country[0]",),
    "prior_i130_last_name": ("Pt5Line2a_FamilyName[0]",),
    "prior_i130_first_name": ("Pt5Line2b_GivenName[0]",),
    "prior_i130_middle_name": ("Pt5Line2c_MiddleName[0]",),
    "prior_i130_city": ("Pt5Line3a_CityOrTown[0]",),
    "prior_i130_state": ("Pt5Line3b_State[0]",),
    "prior_i130_date_filed": ("Pt5Line4_DateFiled[0]",),
    "prior_i130_result": ("Pt5Line5_Result[0]",),
}

I130_CHECKBOX_FIELD_MAP: dict[str, dict[Any, tuple[str, str]]] = {
    "relationship_spouse": {
        True: ("Pt1Line1_Spouse[0]", "/Y"),
        "spouse": ("Pt1Line1_Spouse[0]", "/Y"),
    },
    "petitioner_current_marital_status": {
        "married": ("Pt2Line17_Married[0]", "/Y"),
        "single": ("Pt2Line17_Single[0]", "/Y"),
        "divorced": ("Pt2Line17_Divorced[0]", "/Y"),
        "widowed": ("Pt2Line17_Widowed[0]", "/Y"),
        "separated": ("Pt2Line17_Separated[0]", "/Y"),
        "annulled": ("Pt2Line17_Annulled[0]", "/Y"),
    },
    "beneficiary_current_marital_status": {
        "married": ("Pt4Line18_MaritalStatus[4]", "/M"),
        "single": ("Pt4Line18_MaritalStatus[3]", "/SNM"),
        "divorced": ("Pt4Line18_MaritalStatus[5]", "/D"),
        "widowed": ("Pt4Line18_MaritalStatus[0]", "/W"),
        "separated": ("Pt4Line18_MaritalStatus[2]", "/S"),
        "annulled": ("Pt4Line18_MaritalStatus[1]", "/A"),
    },
    "petitioner_citizenship_status": {
        "us_citizen": ("Pt2Line36_USCitizen[0]", "/Y"),
        "us citizen": ("Pt2Line36_USCitizen[0]", "/Y"),
        "u.s. citizen": ("Pt2Line36_USCitizen[0]", "/Y"),
        "citizen": ("Pt2Line36_USCitizen[0]", "/Y"),
        "lpr": ("Pt2Line36_LPR[0]", "/N"),
    },
    "petitioner_sex": {
        "male": ("Pt2Line9_Male[0]", "/Y"),
        "female": ("Pt2Line9_Female[0]", "/Y"),
    },
    "petitioner_mailing_same_as_physical": {
        True: ("Pt2Line11_Yes[0]", "/Y"),
        False: ("Pt2Line11_No[0]", "/N"),
    },
    "petitioner_parent1_sex": {
        "male": ("Pt2Line26_Male[0]", "/Y"),
        "female": ("Pt2Line26_Female[0]", "/Y"),
    },
    "petitioner_parent2_sex": {
        "male": ("Pt2Line32_Male[0]", "/Y"),
        "female": ("Pt2Line32_Female[0]", "/Y"),
    },
    "petitioner_citizenship_acquired_by": {
        "birth": ("Pt2Line23a_checkbox[0]", "/Y"),
        "naturalization": ("Pt2Line23b_checkbox[0]", "/Y"),
        "parents": ("Pt2Line23c_checkbox[0]", "/Y"),
    },
    "petitioner_has_naturalization_certificate": {
        True: ("Pt2Line36_Yes[0]", "/Y"),
        False: ("Pt2Line36_No[0]", "/N"),
        "yes": ("Pt2Line36_Yes[0]", "/Y"),
        "no": ("Pt2Line36_No[0]", "/N"),
    },
    "petitioner_lpr_gained_through_marriage": {
        True: ("Pt2Line41_Yes[0]", "/Y"),
        False: ("Pt2Line41_No[0]", "/N"),
        "yes": ("Pt2Line41_Yes[0]", "/Y"),
        "no": ("Pt2Line41_No[0]", "/N"),
    },
    "beneficiary_sex": {
        "male": ("Pt4Line9_Male[0]", "/Y"),
        "female": ("Pt4Line9_Female[0]", "/Y"),
    },
    "beneficiary_prior_petition_filed": {
        True: ("Pt4Line10_Yes[0]", "/Y"),
        False: ("Pt4Line10_No[0]", "/N"),
        "yes": ("Pt4Line10_Yes[0]", "/Y"),
        "no": ("Pt4Line10_No[0]", "/N"),
        "unknown": ("Pt4Line10_Unknown[0]", "/U"),
    },
    "beneficiary_ever_in_united_states": {
        True: ("Pt4Line20_Yes[0]", "/Y"),
        False: ("Pt4Line20_No[0]", "/Y"),
        "yes": ("Pt4Line20_Yes[0]", "/Y"),
        "no": ("Pt4Line20_No[0]", "/Y"),
    },
    "beneficiary_ever_in_immigration_proceedings": {
        True: ("Pt4Line28_Yes[0]", "/Y"),
        False: ("Pt4Line28_No[0]", "/Y"),
        "yes": ("Pt4Line28_Yes[0]", "/Y"),
        "no": ("Pt4Line28_No[0]", "/Y"),
    },
    "beneficiary_immigration_proceedings_type": {
        "removal": ("Pt4Line54_Removal[0]", "/Y"),
        "exclusion": ("Pt4Line54_Exclusion[0]", "/Y"),
        "rescission": ("Pt4Line54_Rescission[0]", "/Y"),
        "judicial": ("Pt4Line54_JudicialProceedings[0]", "/Y"),
        "judicial_proceedings": ("Pt4Line54_JudicialProceedings[0]", "/Y"),
    },
}

I130_UNIT_FIELD_MAP: dict[str, tuple[str, str, str, str]] = {
    "petitioner_current_address_line2": (
        "Pt2Line10_Unit[0]",
        "Pt2Line10_Unit[1]",
        "Pt2Line10_Unit[2]",
        "Pt2Line10_AptSteFlrNumber[0]",
    ),
    "petitioner_physical_address_line2": (
        "Pt2Line12_Unit[0]",
        "Pt2Line12_Unit[1]",
        "Pt2Line12_Unit[2]",
        "Pt2Line12_AptSteFlrNumber[0]",
    ),
    "petitioner_prior_address_line2": (
        "Pt2Line14_Unit[0]",
        "Pt2Line14_Unit[1]",
        "Pt2Line14_Unit[2]",
        "Pt2Line14_AptSteFlrNumber[0]",
    ),
    "petitioner_current_employer_address_line2": (
        "Pt2Line41_Unit[0]",
        "Pt2Line41_Unit[1]",
        "Pt2Line41_Unit[2]",
        "Pt2Line41_AptSteFlrNumber[0]",
    ),
    "petitioner_prior_employer_address_line2": (
        "Pt2Line45_Unit[0]",
        "Pt2Line45_Unit[1]",
        "Pt2Line45_Unit[2]",
        "Pt2Line45_AptSteFlrNumber[0]",
    ),
    "beneficiary_current_address_line2": (
        "Pt4Line11_Unit[0]",
        "Pt4Line11_Unit[1]",
        "Pt4Line11_Unit[2]",
        "Pt4Line11_AptSteFlrNumber[0]",
    ),
    "beneficiary_intended_us_address_line2": (
        "Pt4Line12b_Unit[0]",
        "Pt4Line12b_Unit[1]",
        "Pt4Line12b_Unit[2]",
        "Pt4Line12b_AptSteFlrNumber[0]",
    ),
    "beneficiary_foreign_address_line2": (
        "Pt4Line13_Unit[0]",
        "Pt4Line13_Unit[1]",
        "Pt4Line13_Unit[2]",
        "Pt4Line13_AptSteFlrNumber[0]",
    ),
    "beneficiary_current_employer_address_line2": (
        "Pt4Line26_Unit[0]",
        "Pt4Line26_Unit[1]",
        "Pt4Line26_Unit[2]",
        "Pt4Line26_AptSteFlrNumber[0]",
    ),
    "beneficiary_native_address_line2": (
        "Pt4Line56_Unit[0]",
        "Pt4Line56_Unit[1]",
        "Pt4Line56_Unit[2]",
        "Pt4Line56_AptSteFlrNumber[0]",
    ),
    "beneficiary_last_shared_address_line2": (
        "Pt4Line57_Unit[0]",
        "Pt4Line57_Unit[1]",
        "Pt4Line57_Unit[2]",
        "Pt4Line57_AptSteFlrNumber[0]",
    ),
}

I130A_TEXT_FIELD_MAP: dict[str, tuple[str, ...]] = {
    "beneficiary_a_number": ("Pt1Line1_AlienNumber[0]",),
    "beneficiary_last_name": ("Pt1Line3a_FamilyName[0]",),
    "beneficiary_first_name": ("Pt1Line3b_GivenName[0]",),
    "beneficiary_middle_name": ("Pt1Line3c_MiddleName[0]",),
    # Items 10-23 of edition 04/01/24 describe the beneficiary's parents, despite the template's field names.
    "parent1_last_name": ("Pt1Line10_FamilyName[0]",),
    "parent1_first_name": ("Pt1Line10_GivenName[0]",),
    "parent1_middle_name": ("Pt1Line10_MiddleName[0]",),
    "parent1_date_of_birth": ("Pt1Line11_DateofBirth[0]",),
    "parent1_city_of_birth": ("Pt1Line12CityTownOfBirth[0]",),
    "parent1_country_of_birth": ("Pt1Line13_CountryofBirth[0]",),
    "parent1_city_of_residence": ("Pt1Line14_CountryofBirth[0]",),
    "parent1_country_of_residence": ("Pt1Line15_CountryofResidence[0]",),
    "parent2_last_name": ("Pt1Line16_FamilyName[0]",),
    "parent2_first_name": ("Pt1Line16_GivenName[0]",),
    "parent2_middle_name": ("Pt1Line16_MiddleName[0]",),
    "parent2_date_of_birth": ("Pt1Line17_DateofBirth[0]",),
    "parent2_city_of_birth": ("Pt1Line18_CityTownOfBirth[0]",),
    "parent2_country_of_birth": ("Pt1Line19_CountryofBirth[0]",),
    "parent2_city_of_residence": ("Pt1Line20_CityTownVillageofRes[0]",),
    "parent2_country_of_residence": ("Pt1Line21_CountryofResidence[0]",),
    "beneficiary_current_address_line1": ("Pt1Line4a_StreetNumberName[0]",),
    "beneficiary_current_city": ("Pt1Line4c_CityOrTown[0]",),
    "beneficiary_current_state": ("Pt1Line4d_State[0]",),
    "beneficiary_current_zip": ("Pt1Line4e_ZipCode[0]",),
    "beneficiary_current_country": ("Pt1Line4h_Country[0]",),
    "beneficiary_address_since": ("Pt1Line5a_DateFrom[0]",),
    "beneficiary_current_address_since": ("Pt1Line5a_DateFrom[0]",),
    "beneficiary_current_employer_or_school": ("Pt2Line1_EmployerOrCompName[0]",),
    "beneficiary_current_employer_address_line1": ("Pt2Line2a_StreetNumberName[0]",),
    "beneficiary_current_employer_city": ("Pt2Line2c_CityOrTown[0]",),
    "beneficiary_current_employer_state": ("Pt2Line2d_State[0]",),
    "beneficiary_current_employer_zip": ("Pt2Line2e_ZipCode[0]",),
    "beneficiary_current_employer_country": ("Pt2Line2h_Country[0]",),
    "beneficiary_current_occupation": ("Pt2Line3_Occupation[0]",),
    "beneficiary_current_employment_from": ("Pt2Line4a_DateFrom[0]",),
    "beneficiary_current_employment_to": ("Pt2Line4b_DateTo[0]",),
    "beneficiary_phone": ("Pt4Line3_DaytimePhoneNumber1[0]",),
    "beneficiary_mobile_phone": ("Pt4Line4_MobileNumber1[0]",),
    "beneficiary_email": ("Pt4Line5_Email[0]",),
}

I130A_CHECKBOX_FIELD_MAP: dict[str, dict[Any, tuple[str, str]]] = {
    "parent1_sex": {
        "male": ("Pt1Line12_Male[0]", "/Y"),
        "female": ("Pt1Line12_Female[0]", "/Y"),
    },
    "parent2_sex": {
        "male": ("Pt1Line19_Male[0]", "/Y"),
        "female": ("Pt1Line19_Female[0]", "/Y"),
    },
}

I130A_UNIT_FIELD_MAP: dict[str, tuple[str, str, str, str]] = {
    "beneficiary_current_address_line2": (
        "Pt1Line4b_Unit[0]",
        "Pt1Line4b_Unit[1]",
        "Pt1Line4b_Unit[2]",
        "Pt1Line4b_AptSteFlrNumber[0]",
    ),
    "beneficiary_current_employer_address_line2": (
        "Pt2Line2b_Unit[0]",
        "Pt2Line2b_Unit[1]",
        "Pt2Line2b_Unit[2]",
        "Pt2Line2b_AptSteFlrNumber[0]",
    ),
}

I130A_PRIOR_ADDRESS_FIELD_MAP = {
    "line1": "Pt1Line6a_StreetNumberName[0]",
    "city": "Pt1Line6c_CityOrTown[0]",
    "state": "Pt1Line6d_State[0]",
    "zip": "Pt1Line6e_ZipCode[0]",
    "province": "Pt1Line6f_Province[0]",
    "postal_code": "Pt1Line6g_PostalCode[0]",
    "country": "Pt1Line6h_Country[0]",
    "from": "Pt1Line7a_DateFrom[0]",
    "to": "Pt1Line7b_DateTo[0]",
}

# Items 8 and 9 of edition 04/01/24: last address outside the United States of more than one year.
I130A_FOREIGN_ADDRESS_FIELD_MAP = {
    "line1": "Pt1Line8a_StreetNumberName[0]",
    "city": "Pt1Line8c_CityOrTown[0]",
    "province": "Pt1Line8d_Province[0]",
    "postal_code": "Pt1Line8e_PostalCode[0]",
    "country": "Pt1Line8f_Country[0]",
    "from": "Pt1Line9a_DateFrom[0]",
    "to": "Pt1Line9b_DateTo[0]",
}

G1145_TEXT_FIELD_MAP: dict[str, tuple[str, ...]] = {
    "beneficiary_last_name": ("LastName[0]",),
    "beneficiary_first_name": ("FirstName[0]",),
    "beneficiary_middle_name": ("MiddleName[0]",),
    "beneficiary_email": ("Email[0]",),
    "beneficiary_mobile_phone": ("MobilePhoneNumber[0]",),
    "beneficiary_phone": ("MobilePhoneNumber[0]",),
    "g1145_last_name": ("LastName[0]",),
    "g1145_first_name": ("FirstName[0]",),
    "g1145_middle_name": ("MiddleName[0]",),
    "g1145_email": ("Email[0]",),
    "g1145_mobile_phone": ("MobilePhoneNumber[0]",),
}


@dataclass(frozen=True)
class FamilyPdfFieldPayload:
    form_code: str
    text_values: dict[str, str]
    checkbox_values: dict[str, str]
    mapped_fields: list[dict[str, Any]]
    missing_template_fields: list[str]


@dataclass(frozen=True)
class GeneratedFamilyPdf:
    case_id: UUID
    form_key: str
    form_code: str
    output_path: Path
    template_path: Path
    field_count: int
    text_field_count: int
    checkbox_field_count: int
    mapped_field_count: int
    missing_template_fields: list[str]
    warnings: list[str]


def _normalize_choice(value: Any) -> Any:
    if isinstance(value, str):
        return " ".join(value.strip().lower().replace("-", " ").split())
    return value


def _as_pdf_value(field_key: str, value: Any, date_field_keys: set[str]) -> str:
    if field_key in date_field_keys:
        return as_pdf_date(value)
    # State fields on these forms are dropdowns of two-letter codes.
    if field_key.endswith("_state"):
        return normalize_us_state(value)
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (int, float)):
        return str(value)
    return str(value).strip()


def _first_marriage_count() -> str:
    return "1"


def without_zip_postal_aliases(values: dict[str, Any]) -> dict[str, Any]:
    """Returns values without postal codes that only repeat the ZIP code."""
    # Case-fact aliases copy a ZIP code into the postal code key, but the forms keep Postal Code for foreign addresses.
    normalized = dict(values)
    for prefix in ("beneficiary_current", "petitioner_current"):
        postal_key = f"{prefix}_postal_code"
        if value_is_answered(normalized.get(postal_key)) and normalized.get(postal_key) == normalized.get(f"{prefix}_zip"):
            normalized.pop(postal_key)
    return normalized


I130_CLASS_NOT_OFFERED_WARNING = (
    "Part 4, Item 21.a was left blank because the class of admission answer does not match an option on the form. "
    "Choose the matching option by hand before filing."
)


def i130_class_of_admission_not_offered(values: dict[str, Any]) -> bool:
    """Returns whether an answer has no matching I-130 Item 21.a option."""
    answer = values.get("beneficiary_class_of_admission")
    return value_is_answered(answer) and not i130_class_of_admission_code(answer)


def _normalized_i130_values(values: dict[str, Any]) -> dict[str, Any]:
    normalized = without_zip_postal_aliases(values)
    # Item 21.a is a dropdown that accepts only its USCIS options, for example B2.
    if value_is_answered(normalized.get("beneficiary_class_of_admission")):
        normalized["beneficiary_class_of_admission"] = i130_class_of_admission_code(
            normalized["beneficiary_class_of_admission"]
        )
    if normalized.get("first_marriage_for_both") is True:
        normalized.setdefault("petitioner_marriage_count", _first_marriage_count())
        normalized.setdefault("beneficiary_marriage_count", _first_marriage_count())
    if value_is_answered(normalized.get("marriage_date")):
        normalized.setdefault("relationship_spouse", True)
        normalized.setdefault("petitioner_current_marital_status", "married")
        normalized.setdefault("beneficiary_current_marital_status", "married")
    if value_is_answered(normalized.get("beneficiary_location")):
        beneficiary_location = _normalize_choice(normalized.get("beneficiary_location"))
        if beneficiary_location in {"usa", "us", "u s", "united states", "united states of america"}:
            normalized.setdefault("beneficiary_adjustment_city", normalized.get("beneficiary_current_city"))
            normalized.setdefault("beneficiary_adjustment_state", normalized.get("beneficiary_current_state"))
    return normalized


def _field_values_for_text_map(
    *,
    text_values: dict[str, str],
    mapped_fields: list[dict[str, Any]],
    values: dict[str, Any],
    field_map: dict[str, tuple[str, ...]],
    date_field_keys: set[str],
) -> None:
    for field_key, field_names in field_map.items():
        value = values.get(field_key)
        if not value_is_answered(value):
            continue
        pdf_value = _as_pdf_value(field_key, value, date_field_keys)
        for field_name in field_names:
            text_values[field_name] = pdf_value
        mapped_fields.append(
            {
                "field_key": field_key,
                "pdf_fields": list(field_names),
            }
        )


def _field_values_for_checkbox_map(
    *,
    checkbox_values: dict[str, str],
    mapped_fields: list[dict[str, Any]],
    values: dict[str, Any],
    field_map: dict[str, dict[Any, tuple[str, str]]],
) -> None:
    for field_key, choices in field_map.items():
        value = values.get(field_key)
        if not value_is_answered(value):
            continue
        selected = choices.get(_normalize_choice(value))
        if not selected:
            continue
        field_name, appearance = selected
        checkbox_values[field_name] = appearance
        mapped_fields.append(
            {
                "field_key": field_key,
                "pdf_fields": [field_name],
            }
        )


def _field_values_for_unit_map(
    *,
    text_values: dict[str, str],
    checkbox_values: dict[str, str],
    mapped_fields: list[dict[str, Any]],
    values: dict[str, Any],
    field_map: dict[str, tuple[str, str, str, str]],
) -> None:
    for field_key, unit_fields in field_map.items():
        value = values.get(field_key)
        if not value_is_answered(value):
            continue
        before = set(text_values) | set(checkbox_values)
        add_unit_fields(
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
            mapped_fields.append(
                {
                    "field_key": field_key,
                    "pdf_fields": selected_fields,
                }
            )


def _append_missing_template_fields(
    *,
    text_values: dict[str, str],
    checkbox_values: dict[str, str],
    available_fields: set[str] | None,
) -> list[str]:
    if not available_fields:
        return []
    filled_fields = set(text_values) | set(checkbox_values)
    return sorted(filled_fields - available_fields)


def _add_i130a_prior_address(
    *,
    values: dict[str, Any],
    text_values: dict[str, str],
    checkbox_values: dict[str, str],
    mapped_fields: list[dict[str, Any]],
) -> None:
    raw = values.get("beneficiary_prior_address_history")
    if not isinstance(raw, list) or not raw or not isinstance(raw[0], dict):
        return
    address = raw[0]
    before = set(text_values) | set(checkbox_values)
    add_unit_fields(
        text_values=text_values,
        checkbox_values=checkbox_values,
        value=address.get("line2"),
        apt_field="Pt1Line6b_Unit[0]",
        ste_field="Pt1Line6b_Unit[1]",
        flr_field="Pt1Line6b_Unit[2]",
        number_field="Pt1Line6b_AptSteFlrNumber[0]",
    )
    used_fields: list[str] = []
    for source_key, field_name in I130A_PRIOR_ADDRESS_FIELD_MAP.items():
        value = address.get(source_key)
        if not value_is_answered(value):
            continue
        text_values[field_name] = as_pdf_date(value) if source_key in {"from", "to"} else str(value).strip()
        used_fields.append(field_name)
    used_fields.extend(sorted((set(text_values) | set(checkbox_values)) - before))
    if used_fields:
        mapped_fields.append(
            {
                "field_key": "beneficiary_prior_address_history",
                "pdf_fields": sorted(used_fields),
            }
        )


def _add_i130a_foreign_address(
    *,
    values: dict[str, Any],
    text_values: dict[str, str],
    checkbox_values: dict[str, str],
    mapped_fields: list[dict[str, Any]],
) -> None:
    address = values.get("beneficiary_recent_foreign_address")
    if not isinstance(address, dict):
        return
    before = set(text_values) | set(checkbox_values)
    add_unit_fields(
        text_values=text_values,
        checkbox_values=checkbox_values,
        value=address.get("line2"),
        apt_field="Pt1Line8b_Unit[0]",
        ste_field="Pt1Line8b_Unit[1]",
        flr_field="Pt1Line8b_Unit[2]",
        number_field="Pt1Line8b_AptSteFlrNumber[0]",
    )
    for source_key, field_name in I130A_FOREIGN_ADDRESS_FIELD_MAP.items():
        value = address.get(source_key)
        if value_is_answered(value):
            text_values[field_name] = as_pdf_date(value) if source_key in {"from", "to"} else str(value).strip()
    used_fields = sorted((set(text_values) | set(checkbox_values)) - before)
    if used_fields:
        mapped_fields.append({"field_key": "beneficiary_recent_foreign_address", "pdf_fields": used_fields})


I130A_EMPLOYER_ROWS = (
    {
        "name": "Pt2Line1_EmployerOrCompName[0]",
        "line1": "Pt2Line2a_StreetNumberName[0]",
        "city": "Pt2Line2c_CityOrTown[0]",
        "state": "Pt2Line2d_State[0]",
        "zip": "Pt2Line2e_ZipCode[0]",
        "province": "Pt2Line2f_Province[0]",
        "postal_code": "Pt2Line2g_PostalCode[0]",
        "country": "Pt2Line2h_Country[0]",
        "occupation": "Pt2Line3_Occupation[0]",
        "from": "Pt2Line4a_DateFrom[0]",
        "to": "Pt2Line4b_DateTo[0]",
    },
    {
        "name": "Pt2Line5_EmployerOrCompName[0]",
        "line1": "Pt2Line6_StreetNumberName[0]",
        "city": "Pt2Line6_CityOrTown[0]",
        "state": "Pt2Line6_State[0]",
        "zip": "Pt2Line6_ZipCode[0]",
        "province": "Pt2Line6_Province[0]",
        "postal_code": "Pt2Line6_PostalCode[0]",
        "country": "Pt2Line6_Country[0]",
        "occupation": "Pt2Line7_Occupation[0]",
        "from": "Pt2Line8a_DateFrom[0]",
        "to": "Pt2Line8b_DateTo[0]",
    },
)
I130A_EMPLOYER_UNIT_ROWS = (
    ("Pt2Line2b_Unit[0]", "Pt2Line2b_Unit[1]", "Pt2Line2b_Unit[2]", "Pt2Line2b_AptSteFlrNumber[0]"),
    ("Pt2Line6_Unit[0]", "Pt2Line6_Unit[1]", "Pt2Line6_Unit[2]", "Pt2Line6_AptSteFlrNumber[0]"),
)
I130A_PART7_SLOTS = tuple(
    (f"Pt7Line{line}a_PageNumber[0]", f"Pt7Line{line}b_PartNumber[0]", f"Pt7Line{line}c_ItemNumber[0]", f"Pt7Line{line}d_AdditionalInfo[0]")
    for line in range(3, 8)
)
# 10pt Courier in a 234 x 180 point box.
I130A_PART7_WRAP_WIDTH = 38
I130A_PART7_MAX_LINES = 14


def _same_employer(entry: dict[str, Any], name: str) -> bool:
    return str(entry.get("name") or "").strip().casefold() == name.strip().casefold()


def _add_i130a_employment_history(
    *,
    values: dict[str, Any],
    text_values: dict[str, str],
    checkbox_values: dict[str, str],
    mapped_fields: list[dict[str, Any]],
) -> None:
    raw = values.get("beneficiary_employment_history")
    if isinstance(raw, list):
        answered = [entry for entry in raw if isinstance(entry, dict) and value_is_answered(entry)]
        # Free text saved before the list was structured has no row, so it continues in Part 7.
        note_only = [entry for entry in answered if not entry_has_content(without_notes(entry))]
        entries = [entry for entry in answered if entry_has_content(without_notes(entry))]
        # The questions about the current employer are more specific, so they take the first row and
        # the history's entry for that employer only fills its gaps. Every other job keeps a place.
        current_name = text_values.get(I130A_EMPLOYER_ROWS[0]["name"], "")
        if current_name:
            matching = [entry for entry in entries if _same_employer(entry, current_name)]
            first = matching[0] if matching else {}
            entries = [first, *[entry for entry in entries if entry is not first]]
        continuation = "\n".join(
            employment_continuation_line(entry) for entry in [*entries[len(I130A_EMPLOYER_ROWS) :], *note_only]
        )
    else:
        entries = []
        continuation = str(raw or "").strip()
    if not entries and not continuation:
        return
    # Left unmapped when it does not fit, so the review screen reports the history that did not make it onto the form.
    continuation_fields = fill_continuation_slots(
        text_values=text_values,
        slots=I130A_PART7_SLOTS,
        page_number="2",
        part_number="2",
        item_number="1",
        text=continuation,
        wrap_width=I130A_PART7_WRAP_WIDTH,
        max_lines=I130A_PART7_MAX_LINES,
    )
    if continuation_fields is None:
        return
    used_fields = list(continuation_fields)
    for entry, row, unit_row in zip(entries, I130A_EMPLOYER_ROWS, I130A_EMPLOYER_UNIT_ROWS, strict=False):
        for source_key, field_name in row.items():
            value = entry.get(source_key)
            if not value_is_answered(value) or field_name in text_values:
                continue
            if source_key in {"from", "to"}:
                text_values[field_name] = as_pdf_date(value)
            elif source_key == "state":
                text_values[field_name] = normalize_us_state(value)
            else:
                text_values[field_name] = str(value).strip()
            used_fields.append(field_name)
        # An answered current-employer unit already chose a box and number. A second call would check another box.
        if unit_row[3] in text_values:
            continue
        before = set(text_values) | set(checkbox_values)
        add_unit_fields(
            text_values=text_values,
            checkbox_values=checkbox_values,
            value=entry.get("line2"),
            apt_field=unit_row[0],
            ste_field=unit_row[1],
            flr_field=unit_row[2],
            number_field=unit_row[3],
        )
        used_fields.extend(sorted((set(text_values) | set(checkbox_values)) - before))
    mapped_fields.append({"field_key": "beneficiary_employment_history", "pdf_fields": sorted(used_fields)})


def build_i130_pdf_field_payload(
    values: dict[str, Any],
    available_fields: set[str] | None = None,
) -> FamilyPdfFieldPayload:
    """Returns the PDF field values and mapping report for an I-130."""
    normalized = _normalized_i130_values(values)
    text_values: dict[str, str] = {}
    checkbox_values: dict[str, str] = {}
    mapped_fields: list[dict[str, Any]] = []

    _field_values_for_text_map(
        text_values=text_values,
        mapped_fields=mapped_fields,
        values=normalized,
        field_map=I130_TEXT_FIELD_MAP,
        date_field_keys=I130_DATE_FIELD_KEYS,
    )
    _field_values_for_checkbox_map(
        checkbox_values=checkbox_values,
        mapped_fields=mapped_fields,
        values=normalized,
        field_map=I130_CHECKBOX_FIELD_MAP,
    )
    _field_values_for_unit_map(
        text_values=text_values,
        checkbox_values=checkbox_values,
        mapped_fields=mapped_fields,
        values=normalized,
        field_map=I130_UNIT_FIELD_MAP,
    )

    return FamilyPdfFieldPayload(
        form_code="form_i130",
        text_values=text_values,
        checkbox_values=checkbox_values,
        mapped_fields=mapped_fields,
        missing_template_fields=_append_missing_template_fields(
            text_values=text_values,
            checkbox_values=checkbox_values,
            available_fields=available_fields,
        ),
    )


def build_i130a_pdf_field_payload(
    values: dict[str, Any],
    available_fields: set[str] | None = None,
) -> FamilyPdfFieldPayload:
    """Returns the PDF field values and mapping report for an I-130A."""
    values = without_zip_postal_aliases(values)
    text_values: dict[str, str] = {}
    checkbox_values: dict[str, str] = {}
    mapped_fields: list[dict[str, Any]] = []

    _field_values_for_text_map(
        text_values=text_values,
        mapped_fields=mapped_fields,
        values=values,
        field_map=I130A_TEXT_FIELD_MAP,
        date_field_keys=I130A_DATE_FIELD_KEYS,
    )
    _field_values_for_checkbox_map(
        checkbox_values=checkbox_values,
        mapped_fields=mapped_fields,
        values=values,
        field_map=I130A_CHECKBOX_FIELD_MAP,
    )
    _field_values_for_unit_map(
        text_values=text_values,
        checkbox_values=checkbox_values,
        mapped_fields=mapped_fields,
        values=values,
        field_map=I130A_UNIT_FIELD_MAP,
    )
    _add_i130a_prior_address(
        values=values,
        text_values=text_values,
        checkbox_values=checkbox_values,
        mapped_fields=mapped_fields,
    )
    _add_i130a_foreign_address(
        values=values,
        text_values=text_values,
        checkbox_values=checkbox_values,
        mapped_fields=mapped_fields,
    )
    _add_i130a_employment_history(
        values=values,
        text_values=text_values,
        checkbox_values=checkbox_values,
        mapped_fields=mapped_fields,
    )

    return FamilyPdfFieldPayload(
        form_code="form_i130a",
        text_values=text_values,
        checkbox_values=checkbox_values,
        mapped_fields=mapped_fields,
        missing_template_fields=_append_missing_template_fields(
            text_values=text_values,
            checkbox_values=checkbox_values,
            available_fields=available_fields,
        ),
    )


def build_g1145_pdf_field_payload(
    values: dict[str, Any],
    available_fields: set[str] | None = None,
) -> FamilyPdfFieldPayload:
    """Returns the PDF field values and mapping report for a G-1145."""
    text_values: dict[str, str] = {}
    mapped_fields: list[dict[str, Any]] = []

    _field_values_for_text_map(
        text_values=text_values,
        mapped_fields=mapped_fields,
        values=values,
        field_map=G1145_TEXT_FIELD_MAP,
        date_field_keys=set(),
    )

    return FamilyPdfFieldPayload(
        form_code="form_g1145",
        text_values=text_values,
        checkbox_values={},
        mapped_fields=mapped_fields,
        missing_template_fields=_append_missing_template_fields(
            text_values=text_values,
            checkbox_values={},
            available_fields=available_fields,
        ),
    )


def _pdf_writer_from_reader(reader: PdfReader) -> PdfWriter:
    try:
        return PdfWriter(clone_from=reader)
    except ValueError:
        root = reader.trailer.get("/Root", {})
        if hasattr(root, "pop"):
            root.pop(NameObject("/Metadata"), None)
        try:
            return PdfWriter(clone_from=reader)
        except ValueError:
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            acroform = root.get("/AcroForm") if hasattr(root, "get") else None
            if acroform:
                writer._root_object.update({NameObject("/AcroForm"): acroform})
            return writer


def _generate_family_pdf_from_payload(
    *,
    case_id: UUID,
    form_key: str,
    payload: FamilyPdfFieldPayload,
    template_path: Path,
    output_path: Path | None = None,
    output_dir: Path = DEFAULT_FAMILY_OUTPUT_DIR,
    extra_warnings: tuple[str, ...] = (),
) -> GeneratedFamilyPdf:
    if not template_path.exists():
        raise ValueError(f"{payload.form_code} PDF template not found: {template_path}")

    reader = PdfReader(template_path)
    writer = _pdf_writer_from_reader(reader)
    use_saved_appearances(writer)
    set_text_values(writer, payload.text_values)
    set_checkbox_values(writer, payload.checkbox_values)

    final_output_path = output_path or output_dir / f"{case_id}-{form_key}.pdf"
    final_output_path.parent.mkdir(parents=True, exist_ok=True)
    with final_output_path.open("wb") as handle:
        writer.write(handle)

    warnings = [
        "Review every generated value against the source documents before filing.",
        "The generated PDF is not legal advice and must be printed, reviewed, and signed in ink where required.",
    ]
    if payload.missing_template_fields:
        warnings.append("Some mapped PDF fields were not present in the selected template.")
    warnings.extend(field_length_warning(reader, payload.text_values))
    warnings.extend(unprintable_character_warning(writer))
    overflowing = overlong_field_names(reader, payload.text_values)
    if overflowing:
        warnings.append(OVERLONG_WARNING + ", ".join(overflowing))
    warnings.extend(extra_warnings)

    return GeneratedFamilyPdf(
        case_id=case_id,
        form_key=form_key,
        form_code=payload.form_code,
        output_path=final_output_path,
        template_path=template_path,
        field_count=len(payload.text_values) + len(payload.checkbox_values),
        text_field_count=len(payload.text_values),
        checkbox_field_count=len(payload.checkbox_values),
        mapped_field_count=len(payload.mapped_fields),
        missing_template_fields=payload.missing_template_fields,
        warnings=warnings,
    )


def generate_i130_pdf(
    *,
    case_id: UUID,
    values: dict[str, Any],
    template_path: Path | None = None,
    output_path: Path | None = None,
    output_dir: Path = DEFAULT_FAMILY_OUTPUT_DIR,
) -> GeneratedFamilyPdf:
    """Writes an I-130 PDF."""
    final_template_path = template_path or DEFAULT_FAMILY_TEMPLATE_PATHS["i130"]
    if not final_template_path.exists():
        raise ValueError(f"form_i130 PDF template not found: {final_template_path}")
    reader = PdfReader(final_template_path)
    payload = build_i130_pdf_field_payload(values, template_field_names(reader))
    return _generate_family_pdf_from_payload(
        case_id=case_id,
        form_key="i130",
        payload=payload,
        template_path=final_template_path,
        output_path=output_path,
        output_dir=output_dir,
        extra_warnings=(I130_CLASS_NOT_OFFERED_WARNING,) if i130_class_of_admission_not_offered(values) else (),
    )


def generate_i130a_pdf(
    *,
    case_id: UUID,
    values: dict[str, Any],
    template_path: Path | None = None,
    output_path: Path | None = None,
    output_dir: Path = DEFAULT_FAMILY_OUTPUT_DIR,
) -> GeneratedFamilyPdf:
    """Writes an I-130A PDF."""
    final_template_path = template_path or DEFAULT_FAMILY_TEMPLATE_PATHS["i130a"]
    if not final_template_path.exists():
        raise ValueError(f"form_i130a PDF template not found: {final_template_path}")
    reader = PdfReader(final_template_path)
    payload = build_i130a_pdf_field_payload(values, template_field_names(reader))
    return _generate_family_pdf_from_payload(
        case_id=case_id,
        form_key="i130a",
        payload=payload,
        template_path=final_template_path,
        output_path=output_path,
        output_dir=output_dir,
    )


def generate_g1145_pdf(
    *,
    case_id: UUID,
    values: dict[str, Any],
    template_path: Path | None = None,
    output_path: Path | None = None,
    output_dir: Path = DEFAULT_FAMILY_OUTPUT_DIR,
) -> GeneratedFamilyPdf:
    """Writes a G-1145 PDF."""
    final_template_path = template_path or DEFAULT_FAMILY_TEMPLATE_PATHS["g1145"]
    if not final_template_path.exists():
        raise ValueError(f"form_g1145 PDF template not found: {final_template_path}")
    reader = PdfReader(final_template_path)
    payload = build_g1145_pdf_field_payload(values, template_field_names(reader))
    return _generate_family_pdf_from_payload(
        case_id=case_id,
        form_key="g1145",
        payload=payload,
        template_path=final_template_path,
        output_path=output_path,
        output_dir=output_dir,
    )
