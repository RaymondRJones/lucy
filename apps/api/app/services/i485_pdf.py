from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
import textwrap
from typing import Any
from uuid import UUID

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, TextStringObject
from sqlmodel import Session

from app.content.admission_classes import CLASS_OF_ADMISSION_OPTIONS, normalize_class_of_admission
from app.content.i485_questionnaire import all_i485_questions
from app.core.config import settings
from app.services.i485 import (
    build_i485_form_fill_preview,
    conditional_required_i485_question_ids,
    evaluate_i485_answers,
    get_i485_state,
)


DEFAULT_I485_TEMPLATE_PATH = Path("blank-immigration-documents/i-485.pdf")
DEFAULT_I485_OUTPUT_DIR = settings.generated_dir
PART14_ADDITIONAL_INFO_FIELDS = {
    "P14_Line2_AdditionalInfo[0]",
    "P14_Line3_AdditionalInfo[0]",
    "P14_Line4_AdditionalInfo[0]",
    "P14_Line5_AdditionalInfo[0]",
}
PART14_ADDITIONAL_INFO_DA = "/CourierNewPS-BoldMT 7.00 Tf 0 g"
PART14_ADDITIONAL_INFO_WRAP_WIDTH = 92
PART14_ADDITIONAL_INFO_MAX_LINES = 10
FAMILY_STATUS_FIELD = "Pt9Line57_HouseholdSize[0]"
# Character limits come from rendering the 09/18/26 template; longer text clips, so it moves to Part 14.
FAMILY_STATUS_MAX_CHARS = 38
SKILL_ROW_FIELDS = tuple(f"TextField{row}[0]" for row in range(1, 9))
SKILL_ROW_MAX_CHARS = 76
BENEFIT_ROW_LIMIT = 4
BENEFIT_NAME_MAX_CHARS = 20
BENEFIT_REASON_MAX_CHARS = 11
SEE_PART14 = "See Part 14"

QUESTION_BY_ID = {question["id"]: question for question in all_i485_questions()}

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
STATE_CHOICE_FIELDS = {
    "Pt1Line10_State[0]",
    "Pt1Line18_State[0]",
    "Pt1Line18_CurrentState[0]",
    "Pt1Line18_PriorState[0]",
    "Pt1Line18_RecentState[0]",
    "P4Line7_State[0]",
    "P4Line8_State[0]",
    "P6Line8_State[0]",
}

TEXT_FIELD_MAP: dict[str, tuple[str, ...]] = {
    "beneficiary_a_number": tuple(
        ["Pt2Line2_AlienNumber[0]"] + [f"Pt1Line4_AlienNumber[{index}]" for index in range(25)]
    ),
    "beneficiary_last_name": (
        "Pt1Line1_FamilyName[0]",
        "P1Line12_FamilyName[0]",
        "Pt2Line2_FamilyName[0]",
        "Pt1Line1_FamilyName[1]",
    ),
    "beneficiary_first_name": (
        "Pt1Line1_GivenName[0]",
        "P1Line13_GivenName[0]",
        "Pt2Line2_GivenName[0]",
        "Pt1Line1_GivenName[1]",
    ),
    "beneficiary_middle_name": ("Pt1Line1_MiddleName[0]", "Pt2Line2_MiddleName[0]", "Pt1Line1_MiddleName[1]"),
    "beneficiary_date_of_birth": ("Pt1Line3_DOB[0]", "Pt1Line2_DOB[0]"),
    "beneficiary_city_of_birth": ("Pt1Line7_CityTownOfBirth[0]",),
    "beneficiary_country_of_birth": ("Pt1Line7_CountryOfBirth[0]",),
    "beneficiary_country_of_citizenship": ("Pt1Line8_CountryofCitizenshipNationality[0]",),
    "beneficiary_uscis_online_account_number": ("Pt1Line9_USCISAccountNumber[0]",),
    "beneficiary_passport_number": ("Pt1Line10_PassportNum[0]",),
    "beneficiary_passport_expiration": ("Pt1Line10_ExpDate[0]",),
    "beneficiary_passport_country": ("Pt1Line10_Passport[0]",),
    "beneficiary_visa_number": ("Pt1Line10_VisaNum[0]",),
    "beneficiary_visa_issued_on": ("Pt1Line10_NonImmDate[0]",),
    "beneficiary_last_arrival_city": ("Pt1Line10_CityTown[0]",),
    "beneficiary_last_arrival_state": ("Pt1Line10_State[0]",),
    "beneficiary_last_arrival_date": ("Pt1Line10_DateofArrival[0]",),
    "beneficiary_class_of_admission": ("Pt1Line12_Status[0]",),
    "beneficiary_i94_number": ("P1Line12_I94[0]",),
    "beneficiary_status_expires_on": ("Pt1Line12_Date[0]",),
    "beneficiary_current_immigration_status": ("Pt1Line14_Status[0]",),
    "beneficiary_current_status_expires_on": ("Pt1Line15_Date[0]",),
    "beneficiary_current_address_line1": ("Pt1Line18_StreetNumberName[0]",),
    "beneficiary_current_city": ("Pt1Line18_CityOrTown[0]",),
    "beneficiary_current_state": ("Pt1Line18_State[0]",),
    "beneficiary_current_zip": ("Pt1Line18_ZipCode[0]",),
    "beneficiary_address_since": ("Pt1Line18_Date[0]",),
    "beneficiary_ssn": ("Pt1Line19_SSN[0]",),
    "i485_underlying_petition_receipt": ("Pt2Line2_Receipt[0]",),
    "i485_priority_date": ("Pt2Line2_Date[0]",),
    "beneficiary_current_employer_or_school": ("Pt4Line7_EmployerName[2]",),
    "beneficiary_current_occupation": ("Pt4Line7_EmployerName[1]",),
    "parent1_last_name": ("Pt5Line1_FamilyName[0]",),
    "parent1_first_name": ("Pt5Line1_GivenName[0]",),
    "parent1_middle_name": ("Pt5Line1_MiddleName[0]",),
    "parent1_date_of_birth": ("Pt5Line3_DateofBirth[0]",),
    "parent1_country_of_birth": ("Pt5Line5_CityTownOfBirth[0]",),
    "parent2_last_name": ("Pt5Line6_FamilyName[0]",),
    "parent2_first_name": ("Pt5Line6_GivenName[0]",),
    "parent2_middle_name": ("Pt5Line6_MiddleName[0]",),
    "parent2_date_of_birth": ("Pt5Line8_DateofBirth[0]",),
    "parent2_country_of_birth": ("Pt5Line10_CityTownOfBirth[0]",),
    "beneficiary_marriage_count": ("Pt6Line3_TimesMarried[0]",),
    "petitioner_last_name": ("Pt6Line4_FamilyName[0]",),
    "petitioner_first_name": ("Pt6Line4_GivenName[0]",),
    "petitioner_middle_name": ("Pt6Line4_MiddleName[0]",),
    "petitioner_date_of_birth": ("Pt5Line8_DateofBirth[1]",),
    "petitioner_country_of_birth": ("Pt6Line7_Country[0]",),
    "marriage_place_city": ("Pt6Line10_CityTownOfBirth[0]",),
    "marriage_place_state": ("Pt6Line10_State[0]",),
    "marriage_place_country": ("Pt6Line10_Country[0]",),
    "marriage_date": ("Pt5Line8_DateofBirth[2]",),
    "children_count": ("Pt6Line1_TotalChildren[0]",),
    "beneficiary_height_feet": ("Pt7Line3_HeightFeet[0]",),
    "beneficiary_height_inches": ("Pt7Line3_HeightInches[0]",),
    "beneficiary_phone": ("Pt3Line3_DaytimePhoneNumber1[0]",),
    "beneficiary_mobile_phone": ("Pt3Line4_MobileNumber1[0]",),
    "beneficiary_email": ("Pt3Line5_Email[0]",),
    "petitioner_a_number": ("Pt6Line5_AlienNumber[0]",),
    "highest_grade_completed": ("Pt9Line61_diploma[0]",),
    "status_before_evading_service": ("Pt9Line86_Nationality[0]",),
}

DATE_QUESTION_IDS = {
    "beneficiary_date_of_birth",
    "beneficiary_passport_expiration",
    "beneficiary_visa_issued_on",
    "beneficiary_last_arrival_date",
    "beneficiary_status_expires_on",
    "beneficiary_current_status_expires_on",
    "beneficiary_address_since",
    "i485_priority_date",
    "parent1_date_of_birth",
    "parent2_date_of_birth",
    "petitioner_date_of_birth",
    "marriage_date",
}

A_NUMBER_QUESTION_IDS = {"beneficiary_a_number", "petitioner_a_number"}
PHONE_QUESTION_IDS = {"beneficiary_phone", "beneficiary_mobile_phone"}

CHECKBOX_FIELD_MAP: dict[str, dict[Any, tuple[str, str]]] = {
    "beneficiary_used_other_dob": {True: ("Pt1Line3_YN[0]", "/Y"), False: ("Pt1Line3_YN[1]", "/N")},
    "beneficiary_has_a_number": {True: ("Pt1Line4_YN[0]", "/Y"), False: ("Pt1Line4_YN[1]", "/N")},
    "beneficiary_has_other_a_numbers": {True: ("Pt1Line5_YN[0]", "/Y"), False: ("Pt1Line5_YN[1]", "/N")},
    "beneficiary_sex": {"female": ("Pt1Line6_CB_Sex[0]", "/F"), "male": ("Pt1Line6_CB_Sex[1]", "/M")},
    "beneficiary_last_arrival_first_us_presence": {True: ("Pt1Line13_YN[0]", "/Y"), False: ("Pt1Line13_YN[1]", "/N")},
    "beneficiary_current_address_five_years": {True: ("Pt1Line18_last5yrs_YN[0]", "/Y"), False: ("Pt1Line18_last5yrs_YN[1]", "/N")},
    "beneficiary_mailing_same_as_physical": {True: ("Pt1Line18_YN[0]", "/Y"), False: ("Pt1Line18_YN[1]", "/N")},
    "i485_applicant_role": {
        "principal": ("Pt2Line2_CB[0]", "/1fA"),
        "derivative": ("Pt2Line2_CB[1]", "/1fB"),
    },
    "i485_i864_exemption": {
        "40_quarters": ("Pt3Line1_CB[0]", "/0"),
        "child_citizenship": ("Pt3Line1_CB[1]", "/1"),
        "widow_i360": ("Pt3Line1_CB[2]", "/2"),
        "vawa_self_petitioner": ("Pt3Line1_CB[3]", "/3"),
        "not_required_by_statute": ("Pt3Line1_CB[4]", "/4"),
        "not_requesting_exemption": ("Pt3Line1_CB[5]", "/5"),
    },
    "i485_family_category": {
        "spouse_us_citizen": ("Pt2Line3a_CB[0]", "/3a0"),
        "child_us_citizen": ("Pt2Line3a_CB[1]", "/3a1"),
        "parent_us_citizen": ("Pt2Line3a_CB[2]", "/3a2"),
        "spouse_lpr": ("Pt2Line3a_CB[9]", "/3a9"),
    },
    "beneficiary_current_marital_status": {
        "divorced": ("Pt6Line1_MaritalStatus[0]", "/3"),
        "single": ("Pt6Line1_MaritalStatus[1]", "/1"),
        "widowed": ("Pt6Line1_MaritalStatus[2]", "/4"),
        "married": ("Pt6Line1_MaritalStatus[3]", "/2"),
        "annulled": ("Pt6Line1_MaritalStatus[4]", "/5"),
        "separated": ("Pt6Line1_MaritalStatus[5]", "/7"),
    },
    "beneficiary_ethnicity": {
        "hispanic_or_latino": ("Pt7Line1_Ethnicity[0]", "/H"),
        "not_hispanic_or_latino": ("Pt7Line1_Ethnicity[1]", "/N"),
    },
    "beneficiary_eye_color": {
        "blue": ("Pt7Line5_Eyecolor[0]", "/BU"),
        "black": ("Pt7Line5_Eyecolor[1]", "/BL"),
        "brown": ("Pt7Line5_Eyecolor[2]", "/BN"),
        "gray": ("Pt7Line5_Eyecolor[3]", "/GR"),
        "green": ("Pt7Line5_Eyecolor[4]", "/GN"),
        "hazel": ("Pt7Line5_Eyecolor[5]", "/HA"),
    },
    "beneficiary_hair_color": {
        "bald": ("Pt7Line6_Haircolor[0]", "/NH"),
        "black": ("Pt7Line6_Haircolor[1]", "/BL"),
        "blond": ("Pt7Line6_Haircolor[2]", "/BN"),
        "brown": ("Pt7Line6_Haircolor[3]", "/BR"),
        "gray": ("Pt7Line6_Haircolor[4]", "/GR"),
        "red": ("Pt7Line6_Haircolor[5]", "/RD"),
        "sandy": ("Pt7Line6_Haircolor[6]", "/SA"),
        "white": ("Pt7Line6_Haircolor[7]", "/WH"),
    },
    "annual_household_income_band": {
        "0_27000": ("Pt9Line53_CB[0]", "/A"),
        "27001_52000": ("Pt9Line53_CB[1]", "/B"),
        "52001_85000": ("Pt9Line53_CB[2]", "/C"),
        "85001_141000": ("Pt9Line53_CB[3]", "/D"),
        "over_141000": ("Pt9Line53_CB[4]", "/E"),
    },
    "household_assets_band": {
        "0_18400": ("Pt9Line59_CB[0]", "/A"),
        "18401_136000": ("Pt9Line59_CB[1]", "/B"),
        "136001_321400": ("Pt9Line59_CB[2]", "/C"),
        "321401_707100": ("Pt9Line59_CB[3]", "/D"),
        "over_707100": ("Pt9Line59_CB[4]", "/E"),
    },
    "household_liabilities_band": {
        "0": ("Pt9Line60_CB[0]", "/A"),
        "1_10100": ("Pt9Line60_CB[1]", "/B"),
        "10101_57700": ("Pt9Line60_CB[2]", "/C"),
        "57701_186800": ("Pt9Line60_CB[3]", "/D"),
        "over_186800": ("Pt9Line60_CB[4]", "/E"),
    },
    "highest_education": {
        "less_than_high_school": ("Pt9Line61_CB[0]", "/C"),
        "some_college": ("Pt9Line61_CB[1]", "/1"),
        "high_school": ("Pt9Line61_CB[2]", "/2"),
        "associate": ("Pt9Line61_CB[3]", "/3"),
        "master": ("Pt9Line61_CB[4]", "/4"),
        "professional": ("Pt9Line61_CB[5]", "/5"),
        "doctorate": ("Pt9Line61_CB[6]", "/6"),
        "bachelor": ("Pt9Line61_CB[7]", "/7"),
    },
    "public_charge_exempt_category": {
        "not_exempt_complete_questions": ("Pt9Line56_CB[23]", "/23"),
    },
    "spouse_us_military": {False: ("Pt5Line2_YNNA[0]", "/N"), True: ("Pt5Line2_YNNA[1]", "/Y")},
    "current_spouse_applying_with_beneficiary": {False: ("Pt6Line11_YN[0]", "/N"), True: ("Pt6Line11_YN[1]", "/Y")},
}

# Answers saved against the 01/20/25 edition that no longer have a field on the current form.
RETIRED_QUESTION_IDS = {
    "received_cash_benefits",
    "received_long_term_institutionalization",
    "public_charge_benefit_details",
    # Combined questions split into one question per form item.
    "controlled_substance_trafficking",
    "prostitution_or_commercialized_vice",
    "foreign_government_religious_freedom",
    "human_trafficking",
    "espionage_sabotage_export_overthrow",
    "weapons_training_or_violence",
    "military_police_armed_group",
    "persecution_or_child_soldiers",
    "illegal_reentry_after_unlawful_presence_or_removal",
    "polygamy_child_custody_voting_tax_armed_forces",
}

NON_PDF_CONTROL_QUESTIONS = {
    "i485_employment_based_category",
    "i485_special_category",
    "petitioner_citizenship_status",
    "applicant_reviewed_certification",
    "interpreter_used",
    "preparer_used",
    "additional_information_needed",
}

MULTI_CHECKBOX_FIELD_MAP: dict[str, dict[Any, tuple[tuple[str, str], ...]]] = {
    "beneficiary_race": {
        "asian": (("Pt7Line2_Race[0]", "/AS"),),
        "white": (("Pt7Line2_Race[1]", "/WH"),),
        "black": (("Pt7Line2_Race[2]", "/BL"),),
        "american_indian": (("Pt7Line2_Race[3]", "/AI"),),
        "pacific_islander": (("Pt7Line2_Race[4]", "/HW"),),
    }
}

AUTO_BOOLEAN_FIELD_MAP: dict[str, tuple[str, ...]] = {
    "beneficiary_used_other_dob": ("Pt1Line3_YN[0]", "Pt1Line3_YN[1]"),
    "beneficiary_has_a_number": ("Pt1Line4_YN[0]", "Pt1Line4_YN[1]"),
    "beneficiary_has_other_a_numbers": ("Pt1Line5_YN[0]", "Pt1Line5_YN[1]"),
    "beneficiary_alien_crewman_visa": ("Pt1Line16_YN[0]", "Pt1Line16_YN[1]"),
    "beneficiary_joined_vessel_or_aircraft": ("Pt1Line17_YN[0]", "Pt1Line17_YN[1]"),
    "beneficiary_current_address_five_years": ("Pt1Line18_last5yrs_YN[0]", "Pt1Line18_last5yrs_YN[1]"),
    "beneficiary_has_ssn": ("Pt1Line19_YN[0]", "Pt1Line19_YN[1]"),
    "beneficiary_wants_ssn": ("Pt1Line19_SSA_YN[0]", "Pt1Line19_SSA_YN[1]"),
    "beneficiary_ssn_disclosure_consent": ("Pt1Line19_Consent_YN[0]", "Pt1Line19_Consent_YN[1]"),
    "i485_in_removal_proceedings": ("Pt2Line1_YN[0]", "Pt2Line1_YN[1]"),
    "i485_245i": ("Pt2Line4_CB[0]", "Pt2Line4_CB[1]"),
    "i485_cspa": ("Pt2Line5_CB[0]", "Pt2Line5_CB[1]"),
    "prior_immigrant_visa_application": ("Pt4Line1_YN[0]", "Pt4Line1_YN[1]"),
    "prior_permanent_residence_application": ("Pt4Line5_YN[0]", "Pt4Line5_YN[1]"),
    "prior_lpr_status_rescinded": ("Pt4Line6_YN[0]", "Pt4Line6_YN[1]"),
    "organizations_membership": ("Pt8Line1_YesNo[0]", "Pt8Line1_YesNo[1]"),
    "admission_denied": ("Pt9Line10_YesNo[0]", "Pt9Line10_YesNo[1]"),
    "visa_denied": ("Pt9Line11_YesNo[0]", "Pt9Line11_YesNo[1]"),
    "worked_without_authorization": ("Pt9Line12_YesNo[0]", "Pt9Line12_YesNo[1]"),
    "violated_nonimmigrant_status": ("Pt8Line13_YesNo[0]", "Pt8Line13_YesNo[1]"),
    "removal_proceedings_history": ("Pt8Line18_YesNo[0]", "Pt8Line18_YesNo[1]"),
    "final_removal_order": ("Pt8Line19_YesNo[0]", "Pt8Line19_YesNo[1]"),
    "reinstated_removal_order": ("Pt8Line20_YesNo[0]", "Pt8Line20_YesNo[1]"),
    "voluntary_departure_failed": ("Pt8Line17_YesNo[0]", "Pt8Line17_YesNo[1]"),
    "relief_from_removal": ("Pt8Line23_YesNo[0]", "Pt8Line23_YesNo[1]"),
    "j_exchange_two_year_rule": ("Pt8Line24a_YesNo[0]", "Pt8Line24a_YesNo[1]"),
    "j_foreign_residence_complied": ("Pt8Line24b_YesNo[0]", "Pt8Line24b_YesNo[1]"),
    "j_waiver_granted": ("Pt8Line24c_YesNo[0]", "Pt8Line24c_YesNo[1]"),
    "ever_arrested_cited_charged_detained": ("Pt8Line22_YesNo[0]", "Pt8Line22_YesNo[1]"),
    "ever_committed_crime": ("Pt9Line23_YesNo[0]", "Pt9Line23_YesNo[1]"),
    "ever_pled_or_convicted": ("Pt9Line24_YesNo[0]", "Pt9Line24_YesNo[1]"),
    "ever_punished_by_judge": ("Pt8Line25_YesNo[0]", "Pt8Line25_YesNo[1]"),
    "controlled_substance_violation": ("Pt8Line26_YesNo[0]", "Pt8Line26_YesNo[1]"),
    "controlled_substance_trafficked": ("Pt8Line27_YesNo[0]", "Pt8Line27_YesNo[1]"),
    "controlled_substance_family_benefit": ("Pt8Line28_YesNo[0]", "Pt8Line28_YesNo[1]"),
    "controlled_substance_family_benefit_knowledge": ("Pt8Line29_YesNo[0]", "Pt8Line29_YesNo[1]"),
    "prostitution_engaged": ("Pt8Line30_YesNo[0]", "Pt8Line30_YesNo[1]"),
    "prostitution_procured": ("Pt8Line31_YesNo[0]", "Pt8Line31_YesNo[1]"),
    "prostitution_proceeds": ("Pt8Line32_YesNo[0]", "Pt8Line32_YesNo[1]"),
    "commercialized_vice_intent": ("Pt8Line33_YesNo[0]", "Pt8Line33_YesNo[1]"),
    "exercised_criminal_immunity": ("Pt8Line34_YesNo[0]", "Pt8Line34_YesNo[1]"),
    "served_as_foreign_government_official": ("Pt8Line35a_YesNo[0]", "Pt8Line35a_YesNo[1]"),
    "religious_freedom_violations": ("Pt8Line35b_YesNo[0]", "Pt8Line35b_YesNo[1]"),
    "sex_trafficking": ("Pt8Line36_YesNo[0]", "Pt8Line36_YesNo[1]"),
    "labor_trafficking": ("Pt8Line37_YesNo[0]", "Pt8Line37_YesNo[1]"),
    "aided_trafficking": ("Pt8Line38_YesNo[0]", "Pt8Line38_YesNo[1]"),
    "trafficking_family_benefit": ("Pt9Line39_YesNo[0]", "Pt9Line39_YesNo[1]"),
    "trafficking_family_benefit_knowledge": ("Pt8Line40_YesNo[0]", "Pt8Line40_YesNo[1]"),
    "money_laundering": ("Pt8Line41_YesNo[0]", "Pt8Line41_YesNo[1]"),
    "intends_espionage_sabotage": ("a_YesNo[0]", "a_YesNo[1]"),
    "intends_export_violation": ("b_YesNo[0]", "b_YesNo[1]"),
    "intends_overthrow": ("Pt8Line42c_YesNo[0]", "Pt8Line42c_YesNo[1]"),
    "intends_other_unlawful_activity": ("Pt8Line42d_YesNo[0]", "Pt8Line42d_YesNo[1]"),
    "weapons_training": ("Pt8Line43a_YesNo[0]", "Pt8Line43a_YesNo[1]"),
    "kidnapping_or_hijacking": ("Pt8Line43b_YesNo[0]", "Pt8Line43b_YesNo[1]"),
    "used_weapon_or_explosive": ("Pt8Line43c_YesNo[0]", "Pt8Line43c_YesNo[1]"),
    "threatened_or_planned_violence": ("Pt8Line43d_YesNo[0]", "Pt8Line43d_YesNo[1]"),
    "incited_violence": ("Pt8Line43e_YesNo[0]", "Pt8Line43e_YesNo[1]"),
    "member_of_violent_group": ("Pt8Line43fYesNo[0]", "Pt8Line43fYesNo[1]"),
    "recruited_for_violent_group": ("Pt8Line43g_YesNo[0]", "Pt8Line43g_YesNo[1]"),
    "supported_violent_activity": ("Pt8Line43h_YesNo[0]", "Pt8Line43h_YesNo[1]"),
    "supported_violent_group": ("Pt8Line43i_YesNo[0]", "Pt8Line43i_YesNo[1]"),
    "intends_violent_activity": ("Pt8Line44_YesNo[0]", "Pt8Line44_YesNo[1]"),
    "endanger_us_security": ("Pt8Line45_YesNo[0]", "Pt8Line45_YesNo[1]"),
    "family_security_activity": ("Pt8Line46_YesNo[0]", "Pt8Line46_YesNo[1]"),
    "weapons_sales_or_transport": ("Pt8Line47_YesNo[0]", "Pt8Line47_YesNo[1]"),
    "detention_or_prison_service": ("Pt8Line48_YesNo[0]", "Pt8Line48_YesNo[1]"),
    "weapon_using_group": ("Pt8Line49_YesNo[0]", "Pt8Line49_YesNo[1]"),
    "military_or_police_service": ("Pt8Line50_YesNo[0]", "Pt8Line50_YesNo[1]"),
    "armed_group_service": ("Pt8Line51_YesNo[0]", "Pt8Line51_YesNo[1]"),
    "communist_totalitarian_party": ("Pt8Line52_YesNo[0]", "Pt8Line52_YesNo[1]"),
    "participated_in_torture": ("Pt8Line53a_YesNo[0]", "Pt8Line53a_YesNo[1]"),
    "participated_in_genocide": ("Pt8Line53b_YesNo[0]", "Pt8Line53b_YesNo[1]"),
    "participated_in_killing": ("Pt8Line53c_YesNo[0]", "Pt8Line53c_YesNo[1]"),
    "participated_in_severe_injury": ("Pt8Line53d_YesNo[0]", "Pt8Line53d_YesNo[1]"),
    "child_soldier_recruitment": ("Pt8Line54_YesNo[0]", "Pt8Line54_YesNo[1]"),
    "child_soldier_use": ("Pt8Line55_YesNo[0]", "Pt8Line55_YesNo[1]"),
    "received_means_tested_public_benefit": ("Pt9Line63_YesNo[0]", "Pt9Line63_YesNo[1]"),
    "failed_to_attend_removal": ("Pt9Line67_YesNo[0]", "Pt9Line67_YesNo[1]"),
    "fraudulent_documents": ("Pt9Line68_YesNo[0]", "Pt9Line68_YesNo[1]"),
    "lied_for_immigration_benefit": ("Pt9Line69_YesNo[0]", "Pt9Line69_YesNo[1]"),
    "false_us_citizen_claim": ("Pt9Line70_YesNo[0]", "Pt9Line70_YesNo[1]"),
    "stowaway": ("Pt9Line71_YesNo[0]", "Pt9Line71_YesNo[1]"),
    "alien_smuggling": ("Pt9Line72_YesNo[0]", "Pt9Line72_YesNo[1]"),
    "document_fraud_civil_penalty": ("Pt9Line73_YesNo[0]", "Pt9Line73_YesNo[1]"),
    "deported_removed_or_departed_after_order": ("Pt9Line74_YesNo[0]", "Pt9Line74_YesNo[1]"),
    "entered_without_inspection": ("Pt9Line75_YesNo[0]", "Pt9Line75_YesNo[1]"),
    "unlawful_presence_after_1997": ("Pt9Line76_YesNo[0]", "Pt9Line76_YesNo[1]"),
    "unlawful_presence_due_to_trafficking": ("Pt9Line77_YesNo[0]", "Pt9Line77_YesNo[1]"),
    "reentry_after_unlawful_presence": ("Pt9Line78a_YesNo[0]", "Pt9Line78a_YesNo[1]"),
    "reentry_after_removal": ("Pt9Line78b_YesNo[0]", "Pt9Line78b_YesNo[1]"),
    "intends_polygamy": ("Pt9Line79_YesNo[0]", "Pt9Line79_YesNo[1]"),
    "accompanying_helpless_person": ("Pt9Line80_YesNo[0]", "Pt9Line80_YesNo[1]"),
    "withheld_child_custody": ("Pt9Line81_YesNo[0]", "Pt9Line81_YesNo[1]"),
    "unlawful_voting": ("Pt9Line82_YesNo[0]", "Pt9Line82_YesNo[1]"),
    "renounced_citizenship_for_tax": ("Pt9Line83_YesNo[0]", "Pt9Line83_YesNo[1]"),
    "armed_forces_exemption": ("Pt9Line84a_YesNo[0]", "Pt9Line84a_YesNo[1]"),
    "armed_forces_discharge": ("Pt9Line84b_YesNo[0]", "Pt9Line84b_YesNo[1]"),
    "desertion_conviction": ("Pt9Line84c_YesNo[0]", "Pt9Line84c_YesNo[1]"),
    "evaded_wartime_service": ("Pt9Line85_YesNo[0]", "Pt9Line85_YesNo[1]"),
}


@dataclass(frozen=True)
class EntryListMapping:
    question_id: str
    entry_label: str
    # Where Part 14 says the continuation belongs.
    page: str
    part: str
    item: str
    rows: tuple[dict[str, str], ...]
    # Character limits come from rendering the 09/18/26 template; longer text clips, so the entry moves to Part 14.
    limits: dict[str, int]
    choices: tuple[dict[str, dict[Any, tuple[str, str]]], ...] = ()


NAME_LIMITS = {"family_name": 28, "given_name": 28, "middle_name": 25}
PRIOR_SPOUSE_HOW_ENDED = {
    "spouse_deceased": ("Pt6Line19_MaritalStatus[0]", "/3"),
    "annulled": ("Pt6Line19_MaritalStatus[1]", "/1"),
    "other": ("Pt6Line19_MaritalStatus[2]", "/4"),
    "divorced": ("Pt6Line19_MaritalStatus[3]", "/2"),
}


def _child_row(line: int) -> dict[str, str]:
    return {
        "family_name": f"Pt7Line{line}_FamilyName[0]",
        "given_name": f"Pt7Line{line}_GivenName[0]",
        "middle_name": f"Pt7Line{line}_MiddleName[0]",
        "a_number": f"Pt7Line{line}_AlienNumber[0]",
        "date_of_birth": f"Pt7Line{line}_DateofBirth[0]",
        "country_of_birth": f"Pt7Line{line}_Country[0]",
        "relationship": f"Pt7Line{line}_Relationship[0]",
    }


def _child_choices(line: int) -> dict[str, dict[Any, tuple[str, str]]]:
    return {"applying_separately": {False: (f"Pt7Line{line}_YN[0]", "/N"), True: (f"Pt7Line{line}_YN[1]", "/Y")}}


ENTRY_LIST_MAPPINGS = (
    EntryListMapping(
        question_id="beneficiary_other_names",
        entry_label="Other name",
        page="1",
        part="1",
        item="2",
        rows=(
            {"family_name": "Pt1Line2_FamilyName[0]", "given_name": "Pt1Line2_GivenName[0]", "middle_name": "Pt1Line2_MiddleName[0]"},
            {"family_name": "Pt1Line2a_FamilyName[0]", "given_name": "Pt1Line2a_GivenName[0]", "middle_name": "Pt1Line2a_MiddleName[0]"},
        ),
        limits=NAME_LIMITS,
    ),
    EntryListMapping(
        question_id="beneficiary_other_dates_of_birth",
        entry_label="Other date of birth",
        page="1",
        part="1",
        item="3",
        rows=({"date_of_birth": "Pt1Line3A_OtherDOB[0]"}, {"date_of_birth": "Pt1Line3B_OtherDOB[0]"}),
        limits={},
    ),
    EntryListMapping(
        question_id="beneficiary_other_a_numbers",
        entry_label="Other A-Number",
        page="2",
        part="1",
        item="5",
        rows=({"a_number": "Pt1Line5A_ANumber[0]"}, {"a_number": "Pt1Line5B_ANumber[0]"}),
        limits={"a_number": 9},
    ),
    EntryListMapping(
        question_id="beneficiary_prior_marriages",
        entry_label="Prior spouse",
        page="11",
        part="6",
        item="11",
        rows=(
            {
                "family_name": "Pt6Line12_FamilyName[0]",
                "given_name": "Pt6Line12_GivenName[0]",
                "middle_name": "Pt6Line12_MiddleName[0]",
                "date_of_birth": "Pt5Line8_DateofBirth[3]",
                "country_of_birth": "Pt6Line14_Country[0]",
                "citizenship_country": "Pt6Line15_Country[0]",
                "marriage_date": "Pt6Line16_DateofBirth[0]",
                "marriage_city": "Pt6Line10_CityTownOfBirth[1]",
                "marriage_state": "Pt6Line10_State[1]",
                "marriage_country": "Pt6Line10_Country[1]",
                "end_date": "Pt6Line16_DateofBirth[1]",
                "end_city": "Pt6Line18_CityTownOfBirth[0]",
                "end_state": "Pt6Line18_State[0]",
                "end_country": "Pt6Line18_Country[0]",
                "how_ended_other": "Pt6Line19_HowMarriageEndedOther[0]",
            },
        ),
        limits={
            **NAME_LIMITS,
            "country_of_birth": 39,
            "citizenship_country": 39,
            "marriage_city": 41,
            "marriage_state": 41,
            "marriage_country": 41,
            "end_city": 41,
            "end_state": 41,
            "end_country": 41,
            "how_ended_other": 36,
        },
        choices=({"how_ended": PRIOR_SPOUSE_HOW_ENDED},),
    ),
    EntryListMapping(
        question_id="children_details",
        entry_label="Child",
        page="12",
        part="7",
        item="3",
        rows=(_child_row(2), _child_row(3)),
        limits={**NAME_LIMITS, "a_number": 9, "country_of_birth": 41, "relationship": 34},
        choices=(_child_choices(2), _child_choices(3)),
    ),
    EntryListMapping(
        question_id="organizations_details",
        entry_label="Organization",
        page="14",
        part="9",
        item="9",
        rows=(
            {
                "name": "Pt9Line2_Organization1[0]",
                "city": "Pt9Line3_CityTownOfBirth[0]",
                "state": "Pt9Line3_State[0]",
                "country": "Pt9Line3_Country[0]",
                "nature": "Pt9Line4_FamilyName[0]",
                "involvement": "Pt9Line4_Involvement[0]",
                "date_from": "Pt9Line5_DateFrom[0]",
                "date_to": "Pt9Line5_DateTo[0]",
            },
            {
                "name": "Pt9Line6_Organization2[0]",
                "city": "Pt9Line7_CityTownOfBirth[0]",
                "state": "Pt9Line7_State[0]",
                "country": "Pt9Line7_Country[0]",
                "nature": "Pt9Line8_FamilyName[0]",
                "involvement": "Pt9Line8_Involvement[0]",
                "date_from": "Pt9Line9_DateFrom[0]",
                "date_to": "Pt9Line9_DateTo[0]",
            },
        ),
        limits={"name": 56, "city": 41, "state": 41, "country": 41, "nature": 85, "involvement": 85},
    ),
)
ENTRY_DATE_KEYS = {"date_of_birth", "marriage_date", "end_date", "date_from", "date_to"}


@dataclass(frozen=True)
class I485PdfFieldPayload:
    text_values: dict[str, str]
    checkbox_values: dict[str, str]
    mapped_questions: list[dict[str, Any]]
    unmapped_answered_questions: list[dict[str, Any]]
    missing_template_fields: list[str]


@dataclass(frozen=True)
class GeneratedI485Pdf:
    case_id: UUID
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
    if isinstance(value, list):
        return any(_value_is_answered(entry) for entry in value)
    if isinstance(value, dict):
        return any(_value_is_answered(entry_value) for entry_value in value.values())
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


def _normalize_us_state(value: Any) -> str:
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


def _digits(value: Any) -> str:
    return "".join(character for character in str(value) if character.isdigit())


def _as_pdf_value(question_id: str, value: Any) -> str:
    if question_id == "beneficiary_class_of_admission":
        return _immigration_status_label(value)
    if question_id == "beneficiary_current_immigration_status":
        return _immigration_status_label(value)
    if question_id in DATE_QUESTION_IDS:
        return _as_pdf_date(value)
    if question_id == "beneficiary_ssn":
        return _digits(value)[:9]
    if question_id in A_NUMBER_QUESTION_IDS:
        return _digits(value)
    if question_id in PHONE_QUESTION_IDS:
        digits = _digits(value)
        return digits[1:] if len(digits) == 11 and digits.startswith("1") else digits
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (int, float)):
        return str(value)
    return str(value).strip()


# Part 1, Items 12 and 14 of edition 09/18/26 hold 20 characters.
I485_STATUS_FIELD_LENGTH = 20


I485_STATUS_LABELS = {
    "B-1": "B-1 Business Visitor",
    "B-2": "B-2 Visitor",
    "F-1": "F-1 Student",
    "F-2": "F-2 Dependent",
    "J-1": "J-1 Exchange Visitor",
    "J-2": "J-2 Dependent",
    "M-1": "M-1 Student",
    "M-2": "M-2 Dependent",
}


def _immigration_status_label(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.lower() in {"visitor", "b2 visitor"}:
        return I485_STATUS_LABELS["B-2"]
    known_classes = {option["value"] for option in CLASS_OF_ADMISSION_OPTIONS}
    normalized = normalize_class_of_admission(raw)
    if normalized not in known_classes:
        # A description too long for the box collapses to its class, such as "B-1 visitor for business".
        # A shorter answer keeps its wording, such as "F-1 OPT", unless it only restates the label.
        first_word_class = normalize_class_of_admission(raw.split()[0])
        if len(raw) > I485_STATUS_FIELD_LENGTH or raw.lower() == I485_STATUS_LABELS.get(first_word_class, "").lower():
            normalized = first_word_class
    if normalized in I485_STATUS_LABELS:
        return I485_STATUS_LABELS[normalized]
    if " " not in raw:
        return normalized
    return normalized if normalized in known_classes and len(raw) > I485_STATUS_FIELD_LENGTH else raw


def _parse_pdf_date(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _is_us_address_for_inference(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    country = value.get("country")
    if _value_is_answered(country):
        return _is_us_country(country)
    state = _normalize_us_state(value.get("state"))
    zip_code = str(value.get("zip") or value.get("postal_code") or "").strip()
    return state in US_STATE_CODES and bool(zip_code)


def _infer_last_arrival_first_us_presence(answers: dict[str, Any]) -> bool | None:
    last_arrival_date = _parse_pdf_date(answers.get("beneficiary_last_arrival_date"))
    if last_arrival_date is None:
        return None

    current_address = {
        "country": "United States",
        "state": answers.get("beneficiary_current_state"),
        "zip": answers.get("beneficiary_current_zip"),
        "from": answers.get("beneficiary_address_since"),
    }
    address_candidates = [current_address]
    prior_addresses = answers.get("beneficiary_prior_address_history")
    if isinstance(prior_addresses, list):
        address_candidates.extend(address for address in prior_addresses if isinstance(address, dict))

    for address in address_candidates:
        if not _is_us_address_for_inference(address):
            continue
        address_from = _parse_pdf_date(address.get("from"))
        address_to = _parse_pdf_date(address.get("to"))
        if (address_from and address_from < last_arrival_date) or (address_to and address_to < last_arrival_date):
            return False
    return None


def _normalized_answers_for_pdf(answers: dict[str, Any]) -> dict[str, Any]:
    normalized_answers = dict(answers)
    if "beneficiary_has_a_number" not in normalized_answers and _value_is_answered(normalized_answers.get("beneficiary_a_number")):
        normalized_answers["beneficiary_has_a_number"] = True
    if not _value_is_answered(normalized_answers.get("beneficiary_last_arrival_first_us_presence")):
        inferred_first_presence = _infer_last_arrival_first_us_presence(normalized_answers)
        if inferred_first_presence is not None:
            normalized_answers["beneficiary_last_arrival_first_us_presence"] = inferred_first_presence
    return normalized_answers


def _as_pdf_field_value(*, field_name: str, source_key: str, value: Any) -> str:
    if field_name in STATE_CHOICE_FIELDS:
        return _normalize_us_state(value)
    if source_key in {"from", "to"} or source_key in DATE_QUESTION_IDS:
        return _as_pdf_date(value)
    return _as_pdf_value(source_key, value)


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


def _add_unit_fields(
    *,
    text_values: dict[str, str],
    checkbox_values: dict[str, str],
    value: Any,
    apt_field: str,
    ste_field: str,
    flr_field: str,
    number_field: str,
) -> None:
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


def _add_prior_address_fields(
    *,
    answers: dict[str, Any],
    text_values: dict[str, str],
    checkbox_values: dict[str, str],
    mapped_questions: list[dict[str, Any]],
    mapped_question_ids: set[str],
) -> None:
    raw = answers.get("beneficiary_prior_address_history")
    if not isinstance(raw, list) or not raw or not isinstance(raw[0], dict):
        return
    answered = [entry for entry in raw if isinstance(entry, dict) and _entry_has_content(entry)]
    if not answered:
        return
    entries = [_normalized_address_for_pdf(entry) for entry in answered if _entry_has_content(_without_notes(entry))]
    address = entries[0] if entries else {}
    mapped_fields: list[str] = []
    field_map = {
        "in_care_of": "Pt1Line18_PriorInCareOfName[0]",
        "line1": "Pt1Line18_PriorStreetName[0]",
        "city": "Pt1Line18_PriorCity[0]",
        "state": "Pt1Line18_PriorState[0]",
        "zip": "Pt1Line18_PriorZipCode[0]",
        "province": "Pt1Line18_PriorProvince[0]",
        "postal_code": "Pt1Line18_PriorPostalCode[0]",
        "country": "Pt1Line18_PriorCountry[0]",
        "from": "Pt1Line18_PriorDateFrom[0]",
        "to": "Pt1Line18PriorDateTo[0]",
    }
    for source_key, field_name in field_map.items():
        value = address.get(source_key)
        if _value_is_answered(value):
            text_values[field_name] = _as_pdf_field_value(field_name=field_name, source_key=source_key, value=value)
            mapped_fields.append(field_name)
    before = set(text_values) | set(checkbox_values)
    _add_unit_fields(
        text_values=text_values,
        checkbox_values=checkbox_values,
        value=address.get("line2"),
        apt_field="Pt1Line18_PriorAddress_Unit[0]",
        ste_field="Pt1Line18_PriorAddress_Unit[1]",
        flr_field="Pt1Line18_PriorAddress_Unit[2]",
        number_field="Pt1Line18_PriorAddress_Number[0]",
    )
    after = set(text_values) | set(checkbox_values)
    mapped_fields.extend(sorted(after - before))
    continuation_lines = [
        _address_continuation_text(entry, entry_index) for entry_index, entry in enumerate(entries[1:], start=2)
    ]
    continuation_lines.extend(
        f"Prior address note: {str(entry['notes']).strip()}" for entry in answered if _value_is_answered(entry.get("notes"))
    )
    continuation_text = "\n".join(continuation_lines)
    if continuation_text and not _part14_has_room(text_values, continuation_text):
        # Left unmapped so the review screen reports the addresses that did not make it onto the form.
        return
    mapped_fields.extend(
        _add_part14_continuation(
            text_values=text_values, page_number="4", part_number="1", item_number="18", text=continuation_text
        )
    )
    mapped_question_ids.add("beneficiary_prior_address_history")
    mapped_questions.append(
        {
            "question_id": "beneficiary_prior_address_history",
            "label": QUESTION_BY_ID["beneficiary_prior_address_history"]["label"],
            "pdf_fields": sorted(set(mapped_fields)),
        }
    )


def _list_entries(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict) and _value_is_answered(entry)]


def _join_entry_address(entry: dict[str, Any]) -> str:
    entry = _normalized_address_for_pdf(entry)
    parts = [
        entry.get("line1"),
        entry.get("line2"),
        entry.get("city"),
        entry.get("state") or entry.get("province"),
        entry.get("zip") or entry.get("postal_code"),
        entry.get("country"),
    ]
    return ", ".join(str(part).strip() for part in parts if _value_is_answered(part))


def _address_continuation_text(entry: dict[str, Any], entry_index: int) -> str:
    entry = _normalized_address_for_pdf(entry)
    lines = [f"Prior address {entry_index}:"]
    region_label = None
    region_keys: tuple[str, ...] = ()
    if _value_is_answered(entry.get("state")):
        region_label = "State"
        region_keys = ("state",)
    elif _value_is_answered(entry.get("province")):
        region_label = "Province"
        region_keys = ("province",)

    fields: list[tuple[str, tuple[str, ...]]] = [
        ("Street", ("line1",)),
        ("Apartment/Suite/Floor", ("line2",)),
        ("City or town", ("city",)),
    ]
    if region_label:
        fields.append((region_label, region_keys))
    fields.extend(
        [
            ("ZIP or postal code", ("zip", "postal_code")),
            ("Country", ("country",)),
            ("From", ("from",)),
            ("To", ("to",)),
        ]
    )
    for label, keys in fields:
        value = next((entry.get(key) for key in keys if _value_is_answered(entry.get(key))), None)
        if _value_is_answered(value):
            if label in {"From", "To"}:
                value = _as_pdf_date(value)
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


def _add_part14_continuation(
    *,
    text_values: dict[str, str],
    page_number: str,
    part_number: str,
    item_number: str,
    text: str,
) -> list[str]:
    slots = [
        ("Pt9Line3a_PageNumber[0]", "Pt9Line3b_PartNumber[0]", "Pt9Line3c_ItemNumber[0]", "P14_Line2_AdditionalInfo[0]"),
        ("Pt9Line3a_PageNumber[1]", "Pt9Line3b_PartNumber[1]", "Pt9Line3c_ItemNumber[1]", "P14_Line3_AdditionalInfo[0]"),
        ("Pt9Line3a_PageNumber[2]", "Pt9Line3b_PartNumber[2]", "Pt9Line3c_ItemNumber[2]", "P14_Line4_AdditionalInfo[0]"),
        ("Pt9Line3a_PageNumber[3]", "Pt9Line3b_PartNumber[3]", "Pt9Line3c_ItemNumber[3]", "P14_Line5_AdditionalInfo[0]"),
    ]
    chunks = _part14_text_chunks(text)
    mapped_fields: list[str] = []
    for page_field, part_field, item_field, info_field in slots:
        if info_field in text_values:
            continue
        chunk = chunks.pop(0) if chunks else ""
        if not chunk:
            break
        text_values[page_field] = page_number
        text_values[part_field] = part_number
        text_values[item_field] = item_number
        text_values[info_field] = chunk
        mapped_fields.extend([page_field, part_field, item_field, info_field])
        if not chunks:
            break
    return mapped_fields


def _part14_text_chunks(text: str) -> list[str]:
    wrapped_lines: list[str] = []
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            wrapped_lines.append("")
            continue
        wrapped_lines.extend(
            textwrap.wrap(
                line,
                width=PART14_ADDITIONAL_INFO_WRAP_WIDTH,
                break_long_words=False,
                break_on_hyphens=False,
            )
            or [line]
        )
    return [
        "\n".join(wrapped_lines[index : index + PART14_ADDITIONAL_INFO_MAX_LINES])
        for index in range(0, len(wrapped_lines), PART14_ADDITIONAL_INFO_MAX_LINES)
    ]


def _employment_continuation_line(entry: dict[str, Any]) -> str:
    dates = " - ".join(str(entry.get(key, "")).strip() for key in ("from", "to") if _value_is_answered(entry.get(key)))
    pieces = [
        str(entry.get("name", "")).strip(),
        str(entry.get("occupation", "")).strip(),
        dates,
        _join_entry_address(entry),
    ]
    if _value_is_answered(entry.get("financial_support")):
        pieces.append(f"support: {str(entry['financial_support']).strip()}")
    if _value_is_answered(entry.get("notes")):
        pieces.append(str(entry["notes"]).strip())
    return " | ".join(piece for piece in pieces if piece)


EMPLOYMENT_ACTIVITY_LABELS = {
    "employment": "Employer",
    "self_employment": "Self-employed",
    "school": "School",
    "unemployment": "Unemployed",
    "retirement": "Retired",
}


def _employment_field_value(field_name: str, source_key: str, value: Any) -> str:
    if source_key == "activity_type":
        return EMPLOYMENT_ACTIVITY_LABELS.get(str(value), _as_pdf_value(source_key, value))
    return _as_pdf_field_value(field_name=field_name, source_key=source_key, value=value)


def _employment_entries_from_value(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [entry for entry in value if isinstance(entry, dict) and _value_is_answered(entry)]
    if isinstance(value, dict) and _value_is_answered(value):
        return [value]
    if _value_is_answered(value):
        return [{"name": value}]
    return []


def _add_employment_entry_fields(
    *,
    entry: dict[str, Any],
    text_values: dict[str, str],
    checkbox_values: dict[str, str],
    field_map: dict[str, str],
    unit_fields: tuple[str, str, str, str],
    fallback_country: Any = None,
    force_foreign: bool = False,
) -> list[str]:
    entry = _normalized_address_for_pdf(entry, fallback_country=fallback_country, force_foreign=force_foreign)
    mapped_fields: list[str] = []
    for source_key, field_name in field_map.items():
        value = entry.get(source_key)
        if not _value_is_answered(value):
            continue
        text_values[field_name] = _employment_field_value(field_name, source_key, value)
        mapped_fields.append(field_name)
    _add_unit_fields(
        text_values=text_values,
        checkbox_values=checkbox_values,
        value=entry.get("line2"),
        apt_field=unit_fields[0],
        ste_field=unit_fields[1],
        flr_field=unit_fields[2],
        number_field=unit_fields[3],
    )
    return mapped_fields


def _add_employment_history_fields(
    *,
    answers: dict[str, Any],
    text_values: dict[str, str],
    checkbox_values: dict[str, str],
    mapped_questions: list[dict[str, Any]],
    mapped_question_ids: set[str],
) -> None:
    all_entries = _list_entries(answers.get("beneficiary_employment_history"))
    # An entry that is only free text from before the list was structured has no row, so it continues in Part 14.
    entries = [entry for entry in all_entries if _entry_has_content(_without_notes(entry))]
    mapped_fields: list[str] = []
    outside_entry = None
    if entries:
        mapped_fields = _add_employment_entry_fields(
            entry=entries[0],
            text_values=text_values,
            checkbox_values=checkbox_values,
            field_map={
                "activity_type": "Pt4Line7_EmployerName[0]",
                "name": "Pt4Line7_EmployerName[2]",
                "occupation": "Pt4Line7_EmployerName[1]",
                "line1": "Part4Line7_StreetName[0]",
                "city": "P4Line7_City[0]",
                "state": "P4Line7_State[0]",
                "zip": "P4Line7_ZipCode[0]",
                "province": "P4Line7_Province[0]",
                "postal_code": "P4Line7_PostalCode[0]",
                "country": "P4Line7_Country[0]",
                "from": "Pt4Line7_DateFrom[0]",
                "to": "Pt4Line7_DateTo[0]",
                "financial_support": "Part4Line7_StreetName[1]",
            },
            unit_fields=("P4Line7_Unit[0]", "P4Line7_Unit[1]", "P4Line7_Unit[2]", "P4Line7_Number[0]"),
        )
        outside_entry = next((entry for entry in entries if entry.get("outside_us") is True and entry is not entries[0]), None)

    placed_entries = [entry for entry in (entries[0] if entries else None, outside_entry) if entry is not None]
    overflow_entries = [
        entry
        for entry in all_entries
        if not any(entry is placed for placed in placed_entries) or _value_is_answered(entry.get("notes"))
    ]
    foreign_answer = _employment_entries_from_value(answers.get("beneficiary_foreign_employer_or_school"))
    overflow_entries.extend(entry for entry in foreign_answer if _value_is_answered(entry.get("notes")))
    overflow_text = "\n".join(_employment_continuation_line(entry) for entry in overflow_entries)
    overflow_fits = _part14_has_room(text_values, overflow_text)

    foreign_entry = outside_entry or next(iter(foreign_answer), None)
    if foreign_entry:
        mapped_fields.extend(
            _add_employment_entry_fields(
                entry=foreign_entry,
                text_values=text_values,
                checkbox_values=checkbox_values,
                field_map={
                    "name": "Pt4Line8_EmployerName[0]",
                    "occupation": "Pt4Line8_Occupation[0]",
                    "line1": "P4Line8_StreetName[0]",
                    "city": "P4Line8_City[0]",
                    "state": "P4Line8_State[0]",
                    "zip": "P4Line8_ZipCode[0]",
                    "province": "P4Line8_Province[0]",
                    "postal_code": "P4Line8_PostalCode[0]",
                    "country": "P4Line8_Country[0]",
                    "from": "Pt4Line8_DateFrom[0]",
                    "to": "Pt4Line8_DateTo[0]",
                    "financial_support": "Part4Line8_StreetName[0]",
                },
                unit_fields=("P4Line8_Unit[0]", "P4Line8_Unit[1]", "P4Line8_Unit[2]", "P4Line8_Number[0]"),
                fallback_country=answers.get("beneficiary_country_of_birth") or answers.get("beneficiary_country_of_citizenship"),
                force_foreign=True,
            )
        )
        if _value_is_answered(answers.get("beneficiary_foreign_employer_or_school")) and overflow_fits:
            mapped_question_ids.add("beneficiary_foreign_employer_or_school")
            mapped_questions.append(
                {
                    "question_id": "beneficiary_foreign_employer_or_school",
                    "label": QUESTION_BY_ID["beneficiary_foreign_employer_or_school"]["label"],
                    "pdf_fields": [
                        "Pt4Line8_EmployerName[0]",
                        "Pt4Line8_Occupation[0]",
                        "P4Line8_StreetName[0]",
                        "P4Line8_City[0]",
                        "P4Line8_State[0]",
                        "P4Line8_ZipCode[0]",
                        "P4Line8_Province[0]",
                        "P4Line8_PostalCode[0]",
                        "P4Line8_Country[0]",
                        "Pt4Line8_DateFrom[0]",
                        "Pt4Line8_DateTo[0]",
                        "Part4Line8_StreetName[0]",
                    ],
                }
            )

    if overflow_entries and overflow_fits:
        mapped_fields.extend(
            _add_part14_continuation(
                text_values=text_values,
                page_number="8",
                part_number="4",
                item_number="7",
                text=overflow_text,
            )
        )

    # Left unmapped when it does not fit, so the review screen reports the jobs that did not make it onto the form.
    if all_entries and overflow_fits:
        mapped_question_ids.add("beneficiary_employment_history")
        mapped_questions.append(
            {
                "question_id": "beneficiary_employment_history",
                "label": QUESTION_BY_ID["beneficiary_employment_history"]["label"],
                "pdf_fields": sorted(set(mapped_fields)),
            }
        )


def _split_name(value: Any) -> tuple[str, str, str]:
    parts = [part for part in str(value or "").strip().split() if part]
    if not parts:
        return "", "", ""
    if len(parts) == 1:
        return parts[0], "", ""
    if len(parts) == 2:
        return parts[1], parts[0], ""
    return parts[-1], parts[0], " ".join(parts[1:-1])


def _add_name_at_birth_fields(
    *,
    answers: dict[str, Any],
    text_values: dict[str, str],
    question_id: str,
    family_field: str,
    given_field: str,
    middle_field: str,
    mapped_questions: list[dict[str, Any]],
    mapped_question_ids: set[str],
) -> None:
    value = answers.get(question_id)
    if not _value_is_answered(value):
        return
    family_name, given_name, middle_name = _split_name(value)
    text_values[family_field] = family_name
    text_values[given_field] = given_name
    text_values[middle_field] = middle_name
    mapped_question_ids.add(question_id)
    mapped_questions.append(
        {
            "question_id": question_id,
            "label": QUESTION_BY_ID[question_id]["label"],
            "pdf_fields": [family_field, given_field, middle_field],
        }
    )


def _add_address_fields(
    *,
    value: Any,
    text_values: dict[str, str],
    checkbox_values: dict[str, str],
    field_map: dict[str, str],
    unit_fields: tuple[str, str, str, str] | None = None,
    fallback_country: Any = None,
    force_foreign: bool = False,
) -> list[str]:
    if not isinstance(value, dict):
        return []
    value = _normalized_address_for_pdf(
        value,
        fallback_country=fallback_country,
        force_foreign=force_foreign,
    )
    mapped_fields = []
    for source_key, field_name in field_map.items():
        raw_value = value.get(source_key)
        if _value_is_answered(raw_value):
            text_values[field_name] = _as_pdf_field_value(field_name=field_name, source_key=source_key, value=raw_value)
            mapped_fields.append(field_name)
    if unit_fields:
        before = set(text_values) | set(checkbox_values)
        _add_unit_fields(
            text_values=text_values,
            checkbox_values=checkbox_values,
            value=value.get("line2"),
            apt_field=unit_fields[0],
            ste_field=unit_fields[1],
            flr_field=unit_fields[2],
            number_field=unit_fields[3],
        )
        after = set(text_values) | set(checkbox_values)
        mapped_fields.extend(sorted(after - before))
    return mapped_fields


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
    if _value_is_answered(country):
        return not _is_us_country(country)
    return any(_value_is_answered(value.get(key)) for key in ("province", "postal_code"))


def _normalized_address_for_pdf(
    value: dict[str, Any],
    *,
    fallback_country: Any = None,
    force_foreign: bool = False,
) -> dict[str, Any]:
    normalized = dict(value)
    if not _value_is_answered(normalized.get("country")) and _value_is_answered(fallback_country):
        if force_foreign or _looks_foreign_address(normalized):
            normalized["country"] = fallback_country

    is_foreign = force_foreign or _looks_foreign_address(normalized)
    if is_foreign:
        state = normalized.get("state")
        if not _value_is_answered(normalized.get("province")) and _value_is_answered(state):
            state_text = str(state).strip()
            if state_text.upper() not in US_STATE_CODES:
                normalized["province"] = state_text
        normalized["state"] = ""
        normalized["zip"] = ""
    return normalized


def _part14_has_room(text_values: dict[str, str], text: str) -> bool:
    open_slots = sum(
        1 for field_name in sorted(PART14_ADDITIONAL_INFO_FIELDS) if field_name not in text_values
    )
    return len(_part14_text_chunks(text)) <= open_slots


def _record_mapped_question(
    *,
    question_id: str,
    fields: list[str],
    mapped_questions: list[dict[str, Any]],
    mapped_question_ids: set[str],
) -> None:
    mapped_question_ids.add(question_id)
    mapped_questions.append(
        {
            "question_id": question_id,
            "label": QUESTION_BY_ID[question_id]["label"],
            "pdf_fields": sorted(set(fields)),
        }
    )


def _entries_for_mapping(value: Any) -> list[dict[str, Any]]:
    # Answers saved before these became structured lists are free text, so they can only be copied whole to Part 14.
    raw_entries = value if isinstance(value, list) else [value]
    entries = []
    for raw in raw_entries:
        if isinstance(raw, str) and raw.strip():
            entries.append({"notes": raw.strip()})
        elif isinstance(raw, dict) and _entry_has_content(raw):
            entries.append(raw)
    return entries


def _entry_has_content(entry: dict[str, Any]) -> bool:
    # A false checkbox alone is only the form control's default, not an answer.
    return any(_value_is_answered(value) and not isinstance(value, bool) for value in entry.values())


def _without_notes(entry: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in entry.items() if key != "notes"}


def _entry_has_note_and_fields(entry: dict[str, Any]) -> bool:
    return _value_is_answered(entry.get("notes")) and _entry_has_content(_without_notes(entry))


def _entry_field_value(key: str, value: Any) -> str:
    if key in ENTRY_DATE_KEYS:
        return _as_pdf_date(value)
    if key == "a_number":
        return _digits(value)
    return str(value).strip()


def _entry_fits_row(mapping: EntryListMapping, entry: dict[str, Any], row_index: int) -> bool:
    row = mapping.rows[row_index]
    choices = mapping.choices[row_index] if mapping.choices else {}
    for key, value in entry.items():
        if not _value_is_answered(value):
            continue
        if key in choices:
            if value not in choices[key]:
                return False
        elif key not in row or len(_entry_field_value(key, value)) > mapping.limits.get(key, len(str(value))):
            return False
    return True


def _entry_continuation_text(mapping: EntryListMapping, entry: dict[str, Any]) -> str:
    fields = {field["key"]: field for field in QUESTION_BY_ID[mapping.question_id].get("entry_fields", [])}
    parts = []
    for key, value in entry.items():
        if key == "notes" or not _value_is_answered(value):
            continue
        field = fields.get(key, {})
        option_labels = {option["value"]: option["label"] for option in field.get("options", [])}
        if isinstance(value, bool):
            shown = "Yes" if value else "No"
        else:
            shown = option_labels.get(value) or _entry_field_value(key, value)
        parts.append(f"{field.get('label', key)}: {shown}")
    if _value_is_answered(entry.get("notes")):
        note = str(entry["notes"]).strip()
        parts.append(f"Note: {note}" if parts else note)
    return f"{mapping.entry_label}: " + "; ".join(parts)


def _add_entry_list_fields(
    *,
    answers: dict[str, Any],
    text_values: dict[str, str],
    checkbox_values: dict[str, str],
    mapped_questions: list[dict[str, Any]],
    mapped_question_ids: set[str],
) -> None:
    for mapping in ENTRY_LIST_MAPPINGS:
        entries = _entries_for_mapping(answers.get(mapping.question_id))
        if not entries:
            continue
        placed: list[dict[str, Any]] = []
        overflow: list[dict[str, Any]] = []
        noted: list[dict[str, Any]] = []
        for entry in entries:
            # Free text from before the list was structured has no box, so it must not keep the row off the form.
            row_entry = _without_notes(entry) if _entry_has_note_and_fields(entry) else entry
            if len(placed) < len(mapping.rows) and _entry_fits_row(mapping, row_entry, len(placed)):
                placed.append(row_entry)
                if row_entry is not entry:
                    noted.append(entry)
            else:
                overflow.append(entry)
        overflow_text = "\n".join(_entry_continuation_text(mapping, entry) for entry in overflow)
        # Answers that do not fit stay unmapped so the review screen reports them instead of dropping them.
        if overflow and not _part14_has_room(text_values, overflow_text):
            continue
        continuation_text = "\n".join(_entry_continuation_text(mapping, entry) for entry in [*overflow, *noted])
        # A note must not cost a row that fits, so only the note is left out and reported.
        notes_fit = _part14_has_room(text_values, continuation_text)
        if not notes_fit:
            continuation_text = overflow_text
        fields: list[str] = []
        for row_index, entry in enumerate(placed):
            row = mapping.rows[row_index]
            for key, field_name in row.items():
                if _value_is_answered(entry.get(key)):
                    text_values[field_name] = _entry_field_value(key, entry[key])
                    fields.append(field_name)
            for key, choices in (mapping.choices[row_index] if mapping.choices else {}).items():
                if key in entry and entry[key] in choices:
                    field_name, appearance = choices[entry[key]]
                    checkbox_values[field_name] = appearance
                    fields.append(field_name)
        # Only a whole entry moved to Part 14 gets the pointer. A note on a placed entry would read as another entry.
        if overflow and len(placed) < len(mapping.rows):
            first_key, first_field = next(iter(mapping.rows[len(placed)].items()))
            if mapping.limits.get(first_key, len(SEE_PART14)) >= len(SEE_PART14):
                text_values[first_field] = SEE_PART14
                fields.append(first_field)
        if continuation_text:
            fields.extend(
                _add_part14_continuation(
                    text_values=text_values,
                    page_number=mapping.page,
                    part_number=mapping.part,
                    item_number=mapping.item,
                    text=continuation_text,
                )
            )
        if not notes_fit:
            continue
        _record_mapped_question(
            question_id=mapping.question_id,
            fields=fields,
            mapped_questions=mapped_questions,
            mapped_question_ids=mapped_question_ids,
        )


def _add_criminal_explanations(
    *,
    answers: dict[str, Any],
    text_values: dict[str, str],
    mapped_questions: list[dict[str, Any]],
    mapped_question_ids: set[str],
) -> None:
    explanation = str(answers.get("criminal_explanations") or "").strip()
    if explanation and _part14_has_room(text_values, explanation):
        _record_mapped_question(
            question_id="criminal_explanations",
            fields=_add_part14_continuation(
                text_values=text_values, page_number="15", part_number="9", item_number="22-41", text=explanation
            ),
            mapped_questions=mapped_questions,
            mapped_question_ids=mapped_question_ids,
        )


def _family_status_text(answers: dict[str, Any]) -> str:
    written = str(answers.get("public_charge_family_status") or "").strip()
    if written:
        return written
    parts = []
    marital_status = answers.get("beneficiary_current_marital_status")
    if _value_is_answered(marital_status):
        parts.append(str(marital_status).replace("_", " ").capitalize())
    household_size = answers.get("household_size")
    if _value_is_answered(household_size):
        parts.append(f"household size {household_size}" if parts else f"Household size {household_size}")
    return "; ".join(parts)


def _add_public_charge_fields(
    *,
    answers: dict[str, Any],
    text_values: dict[str, str],
    mapped_questions: list[dict[str, Any]],
    mapped_question_ids: set[str],
) -> None:
    # Answers that do not fit stay unmapped so the review screen reports them instead of dropping them.
    family_status = _family_status_text(answers)
    if family_status:
        continuation: list[str] = []
        if len(family_status) <= FAMILY_STATUS_MAX_CHARS:
            text_values[FAMILY_STATUS_FIELD] = family_status
            fits = True
        elif _part14_has_room(text_values, family_status):
            text_values[FAMILY_STATUS_FIELD] = SEE_PART14
            continuation = _add_part14_continuation(
                text_values=text_values, page_number="19", part_number="9", item_number="57", text=family_status
            )
            fits = True
        else:
            fits = False
        if fits:
            for question_id in ("household_size", "public_charge_family_status"):
                if _value_is_answered(answers.get(question_id)):
                    _record_mapped_question(
                        question_id=question_id,
                        fields=[FAMILY_STATUS_FIELD, *continuation],
                        mapped_questions=mapped_questions,
                        mapped_question_ids=mapped_question_ids,
                    )

    raw_skills = str(answers.get("certifications_licenses_skills") or "")
    skills = [skill.strip() for skill in raw_skills.replace(";", "\n").splitlines() if skill.strip()]
    if skills:
        short_skills = [skill for skill in skills if len(skill) <= SKILL_ROW_MAX_CHARS]
        row_skills = short_skills[: len(SKILL_ROW_FIELDS)]
        overflow = [skill for skill in skills if skill not in row_skills]
        overflow_text = "; ".join(overflow)
        if not overflow or _part14_has_room(text_values, overflow_text):
            fields = list(SKILL_ROW_FIELDS[: len(row_skills)])
            for field_name, skill in zip(SKILL_ROW_FIELDS, row_skills, strict=False):
                text_values[field_name] = skill
            if overflow:
                fields.extend(
                    _add_part14_continuation(
                        text_values=text_values, page_number="19", part_number="9", item_number="62", text=overflow_text
                    )
                )
            _record_mapped_question(
                question_id="certifications_licenses_skills",
                fields=fields,
                mapped_questions=mapped_questions,
                mapped_question_ids=mapped_question_ids,
            )

    all_benefits = _list_entries(answers.get("means_tested_benefit_history"))
    if all_benefits:
        benefits = [entry for entry in all_benefits if _entry_has_content(_without_notes(entry))]
        continuation_lines = []
        for index, entry in enumerate(benefits, start=1):
            name = str(entry.get("benefit_name") or "").strip()
            reason = str(entry.get("reason") or "").strip()
            if index > BENEFIT_ROW_LIMIT or len(name) > BENEFIT_NAME_MAX_CHARS or len(reason) > BENEFIT_REASON_MAX_CHARS:
                continuation_lines.append(
                    f"{name}: {_as_pdf_date(entry.get('start_date'))} to {_as_pdf_date(entry.get('end_date')) or 'present'}; "
                    f"amount {str(entry.get('dollar_amount') or '').strip() or 'N/A'}; reason: {reason}"
                )
        continuation_lines.extend(
            f"Public benefit note: {str(entry['notes']).strip()}" for entry in all_benefits if _value_is_answered(entry.get("notes"))
        )
        continuation_text = "\n".join(continuation_lines)
        if not continuation_lines or _part14_has_room(text_values, continuation_text):
            fields = []
            for row, entry in enumerate(benefits[:BENEFIT_ROW_LIMIT], start=1):
                name = str(entry.get("benefit_name") or "").strip()
                reason = str(entry.get("reason") or "").strip()
                row_values = {
                    1: name if len(name) <= BENEFIT_NAME_MAX_CHARS else SEE_PART14,
                    2: _as_pdf_date(entry.get("start_date")),
                    3: _as_pdf_date(entry.get("end_date")),
                    4: str(entry.get("dollar_amount") or "").strip(),
                    5: reason if len(reason) <= BENEFIT_REASON_MAX_CHARS else SEE_PART14,
                }
                for column, value in row_values.items():
                    if value:
                        field_name = f"Pt8Line68c_Column{column}Row{row}[0]"
                        text_values[field_name] = value
                        fields.append(field_name)
            if continuation_lines:
                fields.extend(
                    _add_part14_continuation(
                        text_values=text_values, page_number="20", part_number="9", item_number="64", text=continuation_text
                    )
                )
            _record_mapped_question(
                question_id="means_tested_benefit_history",
                fields=fields,
                mapped_questions=mapped_questions,
                mapped_question_ids=mapped_question_ids,
            )


def _add_special_fields(
    *,
    answers: dict[str, Any],
    text_values: dict[str, str],
    checkbox_values: dict[str, str],
    mapped_questions: list[dict[str, Any]],
    mapped_question_ids: set[str],
) -> None:
    arrival_type = answers.get("beneficiary_last_arrival_type")
    arrival_checkbox = {
        "admitted": ("Pt2Line11_CB[0]", "/11A"),
        "paroled": ("Pt2Line11_CB[1]", "/11B"),
        "without_admission": ("Pt2Line11_CB[2]", "/11C"),
        "other": ("Pt2Line11_CB[3]", "/11D"),
    }.get(arrival_type)
    arrival_text_field = {
        "admitted": "Pt1Line11_Admitted[0]",
        "paroled": "Pt1Line11_Paroled[0]",
        "other": "Pt1Line11_Other[0]",
    }.get(arrival_type)
    if arrival_checkbox:
        field_name, appearance = arrival_checkbox
        checkbox_values[field_name] = appearance
        selected_fields = [field_name]
        if arrival_text_field:
            arrival_status = (
                answers.get("beneficiary_current_immigration_status")
                or answers.get("beneficiary_class_of_admission")
                or {
                    "admitted": "Inspected and admitted",
                    "paroled": "Inspected and paroled",
                    "other": "Other",
                }[str(arrival_type)]
            )
            text_values[arrival_text_field] = _immigration_status_label(arrival_status)
            selected_fields.append(arrival_text_field)
        mapped_question_ids.add("beneficiary_last_arrival_type")
        mapped_questions.append(
            {
                "question_id": "beneficiary_last_arrival_type",
                "label": QUESTION_BY_ID["beneficiary_last_arrival_type"]["label"],
                "pdf_fields": selected_fields,
            }
        )

    weight = answers.get("beneficiary_weight_pounds")
    if _value_is_answered(weight):
        digits = str(weight).zfill(3)[-3:]
        for field_name, digit in zip(
            ("Pt7Line4_Weight1[0]", "Pt7Line4_Weight2[0]", "Pt7Line4_Weight3[0]"),
            digits,
            strict=True,
        ):
            text_values[field_name] = digit
        mapped_question_ids.add("beneficiary_weight_pounds")
        mapped_questions.append(
            {
                "question_id": "beneficiary_weight_pounds",
                "label": QUESTION_BY_ID["beneficiary_weight_pounds"]["label"],
                "pdf_fields": ["Pt7Line4_Weight1[0]", "Pt7Line4_Weight2[0]", "Pt7Line4_Weight3[0]"],
            }
        )

    petitioner_fields = _add_address_fields(
        value=answers.get("petitioner_current_address"),
        text_values=text_values,
        checkbox_values=checkbox_values,
        field_map={
            "line1": "Part6Line8_StreetName[0]",
            "city": "P6Line8_City[0]",
            "state": "P6Line8_State[0]",
            "zip": "P6Line8_ZipCode[0]",
            "province": "P6Line8_Province[0]",
            "postal_code": "P6Line8_PostalCode[0]",
            "country": "P6Line8_Country[0]",
        },
        unit_fields=("P6Line8_Unit[0]", "P6Line8_Unit[1]", "P6Line8_Unit[2]", "P6Line8_Number[0]"),
    )
    if petitioner_fields:
        mapped_question_ids.add("petitioner_current_address")
        mapped_questions.append(
            {
                "question_id": "petitioner_current_address",
                "label": QUESTION_BY_ID["petitioner_current_address"]["label"],
                "pdf_fields": petitioner_fields,
            }
        )

    mailing_fields = _add_address_fields(
        value=answers.get("beneficiary_mailing_address"),
        text_values=text_values,
        checkbox_values=checkbox_values,
        field_map={
            "in_care_of": "Pt1Line18_CurrentInCareOfName[0]",
            "line1": "Pt1Line18_CurrentStreetNumberName[0]",
            "city": "Pt1Line18_CurrentCityOrTown[0]",
            "state": "Pt1Line18_CurrentState[0]",
            "zip": "Pt1Line18_CurrentZipCode[0]",
        },
        unit_fields=("Pt1Line18_CurrentUnit[0]", "Pt1Line18_CurrentUnit[1]", "Pt1Line18_CurrentUnit[2]", "Pt1Line18_CurrentAptSteFlrNumber[0]"),
    )
    if mailing_fields:
        mapped_question_ids.add("beneficiary_mailing_address")
        mapped_questions.append(
            {
                "question_id": "beneficiary_mailing_address",
                "label": QUESTION_BY_ID["beneficiary_mailing_address"]["label"],
                "pdf_fields": mailing_fields,
            }
        )

    recent_foreign_fields = _add_address_fields(
        value=answers.get("beneficiary_recent_foreign_address"),
        text_values=text_values,
        checkbox_values=checkbox_values,
        field_map={
            "line1": "Pt1Line18_RecentStreetName[0]",
            "city": "Pt1Line18_RecentCity[0]",
            "state": "Pt1Line18_RecentState[0]",
            "zip": "Pt1Line18_RecentZipCode[0]",
            "province": "Pt1Line18_RecentProvince[0]",
            "postal_code": "Pt1Line18_RecentPostalCode[0]",
            "country": "Pt1Line18_RecentCountry[0]",
            "from": "Pt1Line18_RecentDateFrom[0]",
            "to": "Pt1Line18_RecentDateTo[0]",
        },
        unit_fields=("Pt1Line18_RecentUnit[0]", "Pt1Line18_RecentUnit[1]", "Pt1Line18_RecentUnit[2]", "Pt1Line18_RecentNumber[0]"),
        fallback_country=answers.get("beneficiary_country_of_birth") or answers.get("beneficiary_country_of_citizenship"),
        force_foreign=True,
    )
    if recent_foreign_fields:
        mapped_question_ids.add("beneficiary_recent_foreign_address")
        mapped_questions.append(
            {
                "question_id": "beneficiary_recent_foreign_address",
                "label": QUESTION_BY_ID["beneficiary_recent_foreign_address"]["label"],
                "pdf_fields": recent_foreign_fields,
            }
        )

    _add_name_at_birth_fields(
        answers=answers,
        text_values=text_values,
        question_id="parent1_name_at_birth",
        family_field="Pt5Line2_FamilyName[0]",
        given_field="Pt5Line2_GivenName[0]",
        middle_field="Pt5Line2_MiddleName[0]",
        mapped_questions=mapped_questions,
        mapped_question_ids=mapped_question_ids,
    )
    _add_name_at_birth_fields(
        answers=answers,
        text_values=text_values,
        question_id="parent2_name_at_birth",
        family_field="Pt5Line7_FamilyName[0]",
        given_field="Pt5Line7_GivenName[0]",
        middle_field="Pt5Line7_MiddleName[0]",
        mapped_questions=mapped_questions,
        mapped_question_ids=mapped_question_ids,
    )


def build_i485_pdf_field_payload(
    answers: dict[str, Any],
    available_fields: set[str] | None = None,
    button_choices: dict[str, dict[str, str]] | None = None,
) -> I485PdfFieldPayload:
    text_values: dict[str, str] = {}
    checkbox_values: dict[str, str] = {}
    mapped_questions: list[dict[str, Any]] = []
    mapped_question_ids: set[str] = set()

    normalized_answers = _normalized_answers_for_pdf(answers)

    for question_id, field_names in TEXT_FIELD_MAP.items():
        value = normalized_answers.get(question_id)
        if not _value_is_answered(value):
            continue
        for field_name in field_names:
            text_values[field_name] = _as_pdf_field_value(field_name=field_name, source_key=question_id, value=value)
        mapped_question_ids.add(question_id)
        mapped_questions.append(
            {
                "question_id": question_id,
                "label": QUESTION_BY_ID.get(question_id, {}).get("label", question_id),
                "pdf_fields": list(field_names),
            }
        )

    for question_id, choices in CHECKBOX_FIELD_MAP.items():
        value = normalized_answers.get(question_id)
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
                "label": QUESTION_BY_ID.get(question_id, {}).get("label", question_id),
                "pdf_fields": [field_name],
            }
        )

    for question_id, choices in MULTI_CHECKBOX_FIELD_MAP.items():
        value = normalized_answers.get(question_id)
        if not _value_is_answered(value):
            continue
        selected_values = value if isinstance(value, list) else [value]
        selected_fields: list[str] = []
        for selected_value in selected_values:
            for field_name, appearance in choices.get(selected_value, ()):
                checkbox_values[field_name] = appearance
                selected_fields.append(field_name)
        if selected_fields:
            mapped_question_ids.add(question_id)
            mapped_questions.append(
                {
                    "question_id": question_id,
                    "label": QUESTION_BY_ID.get(question_id, {}).get("label", question_id),
                    "pdf_fields": selected_fields,
                }
            )

    for question_id, field_names in AUTO_BOOLEAN_FIELD_MAP.items():
        value = normalized_answers.get(question_id)
        if not isinstance(value, bool):
            continue
        choice_key = "yes" if value else "no"
        selected_fields = []
        for field_name in field_names:
            appearance = (button_choices or {}).get(field_name, {}).get(choice_key)
            if not appearance:
                continue
            checkbox_values[field_name] = appearance
            selected_fields.append(field_name)
        if selected_fields:
            mapped_question_ids.add(question_id)
            mapped_questions.append(
                {
                    "question_id": question_id,
                    "label": QUESTION_BY_ID.get(question_id, {}).get("label", question_id),
                    "pdf_fields": selected_fields,
                }
            )

    _add_unit_fields(
        text_values=text_values,
        checkbox_values=checkbox_values,
        value=normalized_answers.get("beneficiary_current_address_line2"),
        apt_field="Pt1Line18US_Unit[2]",
        ste_field="Pt1Line18US_Unit[0]",
        flr_field="Pt1Line18US_Unit[1]",
        number_field="Pt1Line18US_AptSteFlrNumber[0]",
    )
    if _value_is_answered(normalized_answers.get("beneficiary_current_address_line2")):
        mapped_question_ids.add("beneficiary_current_address_line2")
        mapped_questions.append(
            {
                "question_id": "beneficiary_current_address_line2",
                "label": QUESTION_BY_ID["beneficiary_current_address_line2"]["label"],
                "pdf_fields": ["Pt1Line18US_AptSteFlrNumber[0]"],
            }
        )

    _add_prior_address_fields(
        answers=normalized_answers,
        text_values=text_values,
        checkbox_values=checkbox_values,
        mapped_questions=mapped_questions,
        mapped_question_ids=mapped_question_ids,
    )

    _add_employment_history_fields(
        answers=normalized_answers,
        text_values=text_values,
        checkbox_values=checkbox_values,
        mapped_questions=mapped_questions,
        mapped_question_ids=mapped_question_ids,
    )

    _add_entry_list_fields(
        answers=normalized_answers,
        text_values=text_values,
        checkbox_values=checkbox_values,
        mapped_questions=mapped_questions,
        mapped_question_ids=mapped_question_ids,
    )

    _add_criminal_explanations(
        answers=normalized_answers,
        text_values=text_values,
        mapped_questions=mapped_questions,
        mapped_question_ids=mapped_question_ids,
    )

    _add_public_charge_fields(
        answers=normalized_answers,
        text_values=text_values,
        mapped_questions=mapped_questions,
        mapped_question_ids=mapped_question_ids,
    )

    _add_special_fields(
        answers=normalized_answers,
        text_values=text_values,
        checkbox_values=checkbox_values,
        mapped_questions=mapped_questions,
        mapped_question_ids=mapped_question_ids,
    )

    available = available_fields or set()
    filled_fields = set(text_values) | set(checkbox_values)
    missing_template_fields = sorted(filled_fields - available) if available else []

    unmapped_answered_questions = []
    for question_id, value in sorted(answers.items()):
        if (
            question_id in mapped_question_ids
            or question_id in NON_PDF_CONTROL_QUESTIONS
            or question_id in RETIRED_QUESTION_IDS
            or not _value_is_answered(value)
        ):
            continue
        question = QUESTION_BY_ID.get(question_id, {})
        unmapped_answered_questions.append(
            {
                "question_id": question_id,
                "label": question.get("label", question_id),
                "pdf_ref": question.get("pdf_ref", ""),
            }
        )

    return I485PdfFieldPayload(
        text_values=text_values,
        checkbox_values=checkbox_values,
        mapped_questions=mapped_questions,
        unmapped_answered_questions=unmapped_answered_questions,
        missing_template_fields=missing_template_fields,
    )


def _template_field_names(reader: PdfReader) -> set[str]:
    names: set[str] = set()
    for full_name, field in (reader.get_fields() or {}).items():
        names.add(str(full_name))
        field_name = field.get("/T")
        if field_name:
            names.add(str(field_name))
    return names


def _annotation_full_name(annotation: Any) -> str | None:
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


def _template_button_choices(reader: PdfReader) -> dict[str, dict[str, str]]:
    choices: dict[str, dict[str, str]] = {}
    for page in reader.pages:
        for annotation_ref in page.get("/Annots", []) or []:
            annotation = annotation_ref.get_object()
            field_name = annotation.get("/T")
            if not field_name:
                continue
            appearance = ""
            normal_appearance = (annotation.get("/AP") or {}).get("/N")
            if normal_appearance and hasattr(normal_appearance, "keys"):
                keys = [str(key) for key in normal_appearance.keys() if str(key) != "/Off"]
                appearance = keys[0] if keys else ""
            if not appearance:
                continue
            tooltip = str(annotation.get("/TU") or "").lower()
            field_choices = choices.setdefault(str(field_name), {})
            if "select yes" in tooltip:
                field_choices["yes"] = appearance
            if "select no" in tooltip:
                field_choices["no"] = appearance
    return choices


def _set_text_values(writer: PdfWriter, values: dict[str, str]) -> None:
    for page in writer.pages:
        page_values = {}
        for annotation_ref in page.get("/Annots", []) or []:
            annotation = annotation_ref.get_object()
            field_name = annotation.get("/T")
            full_name = _annotation_full_name(annotation)
            selected_name = full_name if full_name in values else None
            if selected_name is None and field_name and str(field_name) in values:
                selected_name = str(field_name)
            if selected_name and field_name:
                if selected_name in PART14_ADDITIONAL_INFO_FIELDS:
                    annotation.update({NameObject("/DA"): TextStringObject(PART14_ADDITIONAL_INFO_DA)})
                page_values[str(field_name)] = values[selected_name]
        if page_values:
            writer.update_page_form_field_values(page, page_values, auto_regenerate=False)


def _defined_appearance(annotation: Any, requested: str) -> NameObject:
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


def _set_checkbox_values(writer: PdfWriter, values: dict[str, str]) -> None:
    for page in writer.pages:
        for annotation_ref in page.get("/Annots", []) or []:
            annotation = annotation_ref.get_object()
            field_name = annotation.get("/T")
            if not field_name:
                continue
            full_name = _annotation_full_name(annotation)
            selected_name = full_name if full_name in values else str(field_name)
            if selected_name not in values:
                continue
            appearance = _defined_appearance(annotation, values[selected_name])
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
    """Fields wider than their box; a printed form clips the overflow. `_field_length_warning` covers template limits."""
    overlong: set[str] = set()
    for page in reader.pages:
        for annotation_ref in page.get("/Annots", []) or []:
            annotation = annotation_ref.get_object()
            field_name = str(annotation.get("/T") or "")
            value = text_values.get(field_name) or text_values.get(_annotation_full_name(annotation) or "")
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


def _field_length_warning(reader: PdfReader, values: dict[str, str]) -> list[str]:
    too_long: dict[str, str] = {}
    for page in reader.pages:
        for annotation_ref in page.get("/Annots", []) or []:
            annotation = annotation_ref.get_object()
            field_name = annotation.get("/T")
            max_length = annotation.get("/MaxLen")
            if not field_name or max_length is None:
                continue
            full_name = _annotation_full_name(annotation)
            value = values.get(full_name) if full_name in values else values.get(str(field_name))
            if value is not None and len(value) > int(max_length):
                too_long[str(field_name)] = f"{value!r} ({len(value)} characters, the form allows {int(max_length)})"
    if not too_long:
        return []
    return ["These answers may be cut off when printed: " + "; ".join(too_long.values()) + "."]


def _unprintable_character_warning(writer: PdfWriter) -> list[str]:
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


def _use_saved_appearances(writer: PdfWriter) -> None:
    # Viewers that redraw fields print the form's PDF417 barcode as plain text, which scanners cannot read.
    writer.set_need_appearances_writer(False)


def _preview_from_answers(case_id: UUID, answers: dict[str, Any]) -> dict[str, Any]:
    normalized_answers = _normalized_answers_for_pdf(answers)
    evaluation = evaluate_i485_answers(normalized_answers)
    missing_required = []
    conditional_required_ids = conditional_required_i485_question_ids(normalized_answers)
    for question in QUESTION_BY_ID.values():
        if (question.get("required") or question["id"] in conditional_required_ids) and not _value_is_answered(normalized_answers.get(question["id"])):
            missing_required.append(question)
    blocking_flags = [flag for flag in evaluation["flags"] if flag["severity"] == "blocking"]
    outside_niche_flags = [flag for flag in evaluation["flags"] if flag["category"] == "outside_niche"]
    if blocking_flags:
        generation_status = "blocked_by_risk"
    elif outside_niche_flags:
        generation_status = "blocked_outside_standard_niche"
    elif missing_required:
        generation_status = "incomplete"
    else:
        generation_status = "ready_for_user_review"
    return {
        "case_id": str(case_id),
        "generation_status": generation_status,
        "ready_for_pdf_generation": generation_status == "ready_for_user_review",
        "missing_required_count": len(missing_required),
        "blocking_flag_count": len(blocking_flags),
        "outside_niche_flag_count": len(outside_niche_flags),
        "low_confidence_count": 0,
    }


def generate_i485_pdf_from_answers(
    *,
    case_id: UUID,
    answers: dict[str, Any],
    template_path: Path = DEFAULT_I485_TEMPLATE_PATH,
    output_path: Path | None = None,
    output_dir: Path = DEFAULT_I485_OUTPUT_DIR,
    allow_incomplete: bool = True,
    preview: dict[str, Any] | None = None,
) -> GeneratedI485Pdf:
    if not template_path.exists():
        raise ValueError(f"I-485 PDF template not found: {template_path}")

    preview = preview or _preview_from_answers(case_id, answers)
    if not allow_incomplete and not preview["ready_for_pdf_generation"]:
        raise ValueError(
            f"I-485 answers are not ready for PDF generation: {preview['generation_status']}"
        )

    reader = PdfReader(template_path)
    available_fields = _template_field_names(reader)
    button_choices = _template_button_choices(reader)
    payload = build_i485_pdf_field_payload(answers, available_fields, button_choices)

    writer = PdfWriter(clone_from=reader)
    _use_saved_appearances(writer)
    _set_text_values(writer, payload.text_values)
    _set_checkbox_values(writer, payload.checkbox_values)

    final_output_path = output_path or output_dir / f"{case_id}-i-485.pdf"
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
    warnings.extend(_field_length_warning(reader, payload.text_values))
    warnings.extend(_unprintable_character_warning(writer))
    overflowing = overlong_field_names(reader, payload.text_values)
    if overflowing:
        warnings.append(OVERLONG_WARNING + ", ".join(overflowing))

    return GeneratedI485Pdf(
        case_id=case_id,
        output_path=final_output_path,
        template_path=template_path,
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


def generate_i485_pdf(
    *,
    session: Session,
    case_id: UUID,
    template_path: Path = DEFAULT_I485_TEMPLATE_PATH,
    output_path: Path | None = None,
    output_dir: Path = DEFAULT_I485_OUTPUT_DIR,
    allow_incomplete: bool = True,
) -> GeneratedI485Pdf:
    preview = build_i485_form_fill_preview(session, case_id)
    state = get_i485_state(session, case_id)
    return generate_i485_pdf_from_answers(
        case_id=case_id,
        answers=state["answers"],
        template_path=template_path,
        output_path=output_path,
        output_dir=output_dir,
        allow_incomplete=allow_incomplete,
        preview=preview,
    )
