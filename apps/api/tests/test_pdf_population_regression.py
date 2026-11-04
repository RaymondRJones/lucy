"""Regression tests that generated USCIS PDFs carry each applicant's own data onto the right lines.

Expected values are written from the USCIS field labels in blank-immigration-documents/, not read from the
generators' field maps, so a mapping that sends good data to the wrong box fails here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from pdf_form_assertions import (
    PdfWidget,
    assert_widget_values_are_formatted,
    assert_widgets_will_print,
    filled_text_values,
    read_pdf_widgets,
)
from pdf_profiles import (
    PROFILE_SEEDS,
    SUPPLEMENTAL_FORM_KEYS,
    Profile,
    bank_payment_payload,
    build_profile,
    card_payment_payload,
    form_answers,
)
from pypdf import PdfReader
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.cli.seed_happy_path import seed_i485, seed_supplemental_form
from app.cli.seed_packet_scenarios import BIRTH_CITY_BY_COUNTRY, SCENARIOS, _create_case, _scenario_answers
from app.content.admission_classes import CLASS_OF_ADMISSION_OPTIONS
from app.content.i485_questionnaire import I485_QUESTIONNAIRE
from app.models.entities import CaseRecord, IntakeResponse
from app.services.family_pdf import (
    G1145_TEXT_FIELD_MAP,
    I130_CHECKBOX_FIELD_MAP,
    I130_TEXT_FIELD_MAP,
    I130_UNIT_FIELD_MAP,
    I130A_CHECKBOX_FIELD_MAP,
    I130A_TEXT_FIELD_MAP,
    I130A_UNIT_FIELD_MAP,
    generate_g1145_pdf,
)
from app.services.form_ingestion import build_form_fill_preview, import_form_answers_from_case_data, save_form_page_answers
from app.services.form_pdf import (
    CHECKBOX_FIELD_MAP,
    TEXT_FIELD_MAP,
    UNIT_FIELD_MAP,
    generate_form_pdf,
    generate_form_pdf_from_answers,
)
from app.services.g1450 import generate_g1450_pdf_from_payload
from app.services.g1650 import generate_g1650_pdf_from_payload
from app.services.i485 import I485_PROJECTION_STEP, save_i485_page_answers
from app.services.i485_pdf import (
    CHECKBOX_FIELD_MAP as I485_CHECKBOX_FIELD_MAP,
)
from app.services.i485_pdf import (
    I485_STATUS_FIELD_LENGTH,
    _immigration_status_label,
    generate_i485_pdf,
)
from app.services.i485_pdf import (
    TEXT_FIELD_MAP as I485_TEXT_FIELD_MAP,
)
from app.services.intake import upsert_intake_step
from app.services.packet_assembly import assemble_packet_pdf
from app.services.pdf_fields import (
    add_unit_fields,
)

TEMPLATE_DIR = Path("blank-immigration-documents")
QUESTIONNAIRE_FORMS = ("i485", *SUPPLEMENTAL_FORM_KEYS)
ALL_FORMS = (*QUESTIONNAIRE_FORMS, "g1145", "g1450", "g1650")
TEMPLATE_BY_FORM = {
    "i485": "i-485.pdf",
    "i765": "i-765.pdf",
    "i131": "i-131.pdf",
    "i864": "i-864.pdf",
    "i130": "i-130.pdf",
    "i130a": "i-130a.pdf",
    "g1145": "g-1145.pdf",
    "g1450": "g-1450.pdf",
    "g1650": "g-1650.pdf",
}
# Values from the shared sample persona; none of them may reach a seeded applicant's forms.
SAMPLE_PERSONA_VALUES = (
    "Avery",
    "Jordan",
    "Bogota",
    "Oakland",
    "Sunnyvale",
    "94612",
    "X1234567",
    "VISA123456",
    "123456789A1",
    "123 Sample Street",
    "456 Prior Avenue",
    "Sample Community College",
    "Sample Robotics",
    "Sample response",
    "Rosa",
    "Carlos",
)


def _mdy(value: str) -> str:
    return datetime.strptime(value, "%Y-%m-%d").strftime("%m/%d/%Y")


@dataclass
class Expected:
    text: dict[str, str] = field(default_factory=dict)
    on: set[str] = field(default_factory=set)
    off: set[str] = field(default_factory=set)

    def unit(self, unit: tuple[str, str], apt: str, ste: str, flr: str, number: str) -> None:
        label, unit_number = unit
        self.text[number] = unit_number
        selected = {"Apt": apt, "Ste": ste, "Fl": flr}.get(label.split(" ")[0])
        boxes = {apt, ste, flr}
        self.on |= {selected} if selected else set()
        self.off |= boxes - ({selected} if selected else set())


I485_STATUS_LABELS = {"B-1": "B-1 Business Visitor", "B-2": "B-2 Visitor", "F-1": "F-1 Student"}
I765_STATUS_LABELS = {"B-1": "B-1 visitor for business", "B-2": "B-2 visitor", "F-1": "F-1 student"}


def expected_i485(p: Profile) -> Expected:
    expected = Expected(
        text={
            "Pt1Line1_FamilyName[0]": p["beneficiary_last_name"],
            "Pt1Line1_GivenName[0]": p["beneficiary_first_name"],
            "Pt1Line1_MiddleName[0]": p["beneficiary_middle_name"],
            "Pt1Line3_DOB[0]": _mdy(p["beneficiary_date_of_birth"]),
            "Pt1Line7_CityTownOfBirth[0]": p["beneficiary_city_of_birth"],
            "Pt1Line7_CountryOfBirth[0]": p["beneficiary_country_of_birth"],
            "Pt1Line8_CountryofCitizenshipNationality[0]": p["beneficiary_country_of_citizenship"],
            "Pt1Line4_AlienNumber[0]": p["beneficiary_a_number"],
            "Pt1Line9_USCISAccountNumber[0]": p["beneficiary_uscis_online_account_number"],
            "Pt1Line10_PassportNum[0]": p["beneficiary_passport_number"],
            "Pt1Line10_ExpDate[0]": _mdy(p["beneficiary_passport_expiration"]),
            "Pt1Line10_Passport[0]": p["beneficiary_passport_country"],
            "Pt1Line10_VisaNum[0]": p["beneficiary_visa_number"],
            "Pt1Line10_NonImmDate[0]": _mdy(p["beneficiary_visa_issued_on"]),
            "Pt1Line10_CityTown[0]": p["beneficiary_last_arrival_city"],
            "Pt1Line10_State[0]": p["beneficiary_last_arrival_state"],
            "Pt1Line10_DateofArrival[0]": _mdy(p["beneficiary_last_arrival_date"]),
            "Pt1Line12_Status[0]": I485_STATUS_LABELS[p["beneficiary_class_of_admission"]],
            "P1Line12_I94[0]": p["beneficiary_i94_number"],
            "Pt1Line12_Date[0]": _mdy(p["beneficiary_status_expires_on"]),
            "Pt1Line14_Status[0]": I485_STATUS_LABELS[p["beneficiary_class_of_admission"]],
            "Pt1Line15_Date[0]": _mdy(p["beneficiary_current_status_expires_on"]),
            "Pt1Line18_StreetNumberName[0]": p["beneficiary_current_address_line1"],
            "Pt1Line18_CityOrTown[0]": p["beneficiary_current_city"],
            "Pt1Line18_ZipCode[0]": p["beneficiary_current_zip"],
            "Pt1Line18_Date[0]": _mdy(p["beneficiary_address_since"]),
            "Pt1Line19_SSN[0]": p["beneficiary_ssn"],
            "Pt1Line18_PriorStreetName[0]": p["beneficiary_prior_address_history"][0]["line1"],
            "Pt1Line18_PriorCity[0]": p["beneficiary_prior_address_history"][0]["city"],
            "Pt1Line18_PriorZipCode[0]": p["beneficiary_prior_address_history"][0]["zip"],
            "Pt1Line18_RecentStreetName[0]": p["beneficiary_recent_foreign_address"]["line1"],
            "Pt1Line18_RecentCity[0]": p["beneficiary_recent_foreign_address"]["city"],
            "Pt1Line18_RecentProvince[0]": p["beneficiary_recent_foreign_address"]["province"],
            "Pt1Line18_RecentCountry[0]": p["beneficiary_recent_foreign_address"]["country"],
            "Pt4Line7_EmployerName[2]": p["beneficiary_current_employer_or_school"],
            "Pt4Line7_EmployerName[1]": p["beneficiary_current_occupation"],
            "Pt5Line1_FamilyName[0]": p["parent1_last_name"],
            "Pt5Line1_GivenName[0]": p["parent1_first_name"],
            "Pt5Line1_MiddleName[0]": p["parent1_middle_name"],
            "Pt5Line3_DateofBirth[0]": _mdy(p["parent1_date_of_birth"]),
            "Pt5Line5_CityTownOfBirth[0]": p["parent1_country_of_birth"],
            "Pt5Line6_FamilyName[0]": p["parent2_last_name"],
            "Pt5Line6_GivenName[0]": p["parent2_first_name"],
            "Pt5Line6_MiddleName[0]": p["parent2_middle_name"],
            "Pt5Line8_DateofBirth[0]": _mdy(p["parent2_date_of_birth"]),
            "Pt5Line10_CityTownOfBirth[0]": p["parent2_country_of_birth"],
            "Pt6Line3_TimesMarried[0]": "1",
            "Pt6Line4_FamilyName[0]": p["petitioner_last_name"],
            "Pt6Line4_GivenName[0]": p["petitioner_first_name"],
            "Pt6Line4_MiddleName[0]": p["petitioner_middle_name"],
            "Pt5Line8_DateofBirth[1]": _mdy(p["petitioner_date_of_birth"]),
            "Pt6Line7_Country[0]": p["petitioner_country_of_birth"],
            "Part6Line8_StreetName[0]": p["petitioner_current_address_line1"],
            "P6Line8_City[0]": p["petitioner_current_city"],
            "P6Line8_State[0]": p["petitioner_current_address"]["state"],
            "P6Line8_ZipCode[0]": p["petitioner_current_zip"],
            "Pt6Line10_CityTownOfBirth[0]": p["marriage_place_city"],
            "Pt6Line10_State[0]": p["marriage_place_state"],
            "Pt5Line8_DateofBirth[2]": _mdy(p["marriage_date"]),
            "Pt7Line3_HeightFeet[0]": str(p["beneficiary_height_feet"]),
            "Pt7Line3_HeightInches[0]": str(p["beneficiary_height_inches"]),
            "Pt3Line3_DaytimePhoneNumber1[0]": p["beneficiary_phone"],
            "Pt3Line5_Email[0]": p["beneficiary_email"],
        },
        on={"Pt1Line6_CB_Sex[1]" if p["beneficiary_sex"] == "male" else "Pt1Line6_CB_Sex[0]"},
        off={"Pt1Line6_CB_Sex[0]" if p["beneficiary_sex"] == "male" else "Pt1Line6_CB_Sex[1]"},
    )
    weight = str(p["beneficiary_weight_pounds"]).zfill(3)
    for index, digit in enumerate(weight, start=1):
        expected.text[f"Pt7Line4_Weight{index}[0]"] = digit
    # The Item 18 state dropdown stores the two-letter code even when intake holds the full state name.
    expected.text["Pt1Line18_State[0]"] = p["beneficiary_current_address"]["state"]
    expected.unit(p.beneficiary_unit, "Pt1Line18US_Unit[2]", "Pt1Line18US_Unit[0]", "Pt1Line18US_Unit[1]", "Pt1Line18US_AptSteFlrNumber[0]")
    expected.unit(
        p.prior_unit,
        "Pt1Line18_PriorAddress_Unit[0]",
        "Pt1Line18_PriorAddress_Unit[1]",
        "Pt1Line18_PriorAddress_Unit[2]",
        "Pt1Line18_PriorAddress_Number[0]",
    )
    expected.unit(p.petitioner_unit, "P6Line8_Unit[0]", "P6Line8_Unit[1]", "P6Line8_Unit[2]", "P6Line8_Number[0]")
    return expected


def expected_i765(p: Profile) -> Expected:
    expected = Expected(
        text={
            "Line1a_FamilyName[0]": p["beneficiary_last_name"],
            "Line1b_GivenName[0]": p["beneficiary_first_name"],
            "Line1c_MiddleName[0]": p["beneficiary_middle_name"],
            "Line4b_StreetNumberName[0]": p["beneficiary_mailing_address_line1"],
            "Pt2Line5_CityOrTown[0]": p["beneficiary_mailing_city"],
            "Pt2Line5_State[0]": p["beneficiary_current_address"]["state"],
            "Pt2Line5_ZipCode[0]": p["beneficiary_mailing_zip"],
            "Line7_AlienNumber[0]": p["beneficiary_a_number"],
            "Line8_ElisAccountNumber[0]": p["beneficiary_uscis_online_account_number"],
            "Line12b_SSN[0]": p["beneficiary_social_security_number"],
            "Line18a_CityTownOfBirth[0]": p["beneficiary_city_of_birth"],
            "Line18b_CityTownOfBirth[0]": p["beneficiary_state_province_of_birth"],
            "Line18c_CountryOfBirth[0]": p["beneficiary_country_of_birth"],
            "Line17a_CountryOfBirth[0]": p["beneficiary_country_of_citizenship"],
            "Line19_DOB[0]": _mdy(p["beneficiary_date_of_birth"]),
            "Line20a_I94Number[0]": p["beneficiary_i94_number"],
            "Line20b_Passport[0]": p["beneficiary_passport_number"],
            "Line20d_CountryOfIssuance[0]": p["beneficiary_passport_country"],
            "Line20e_ExpDate[0]": _mdy(p["beneficiary_passport_expiration"]),
            "Line21_DateOfLastEntry[0]": _mdy(p["beneficiary_last_arrival_date"]),
            "place_entry[0]": p["beneficiary_last_arrival_place"],
            "Line23_StatusLastEntry[0]": I765_STATUS_LABELS[p["beneficiary_class_of_admission"]],
            "Line24_CurrentStatus[0]": I765_STATUS_LABELS[p["beneficiary_class_of_admission"]],
            "section_1[0]": "c",
            "section_2[0]": "9",
            "Pt3Line3_DaytimePhoneNumber1[0]": p["beneficiary_phone"],
            "Pt3Line4_MobileNumber1[0]": p["beneficiary_mobile_phone"],
            "Pt3Line5_Email[0]": p["beneficiary_email"],
        },
    )
    expected.unit(p.beneficiary_unit, "Pt2Line5_Unit[2]", "Pt2Line5_Unit[0]", "Pt2Line5_Unit[1]", "Pt2Line5_AptSteFlrNumber[0]")
    return expected


def expected_i131(p: Profile) -> Expected:
    prefix = "form1[0].P4[0]"
    weight = str(p["beneficiary_weight_pounds"]).zfill(3)
    expected = Expected(
        text={
            f"{prefix}.Part2_Line1_FamilyName[0]": p["beneficiary_last_name"],
            f"{prefix}.Part2_Line1_GivenName[0]": p["beneficiary_first_name"],
            f"{prefix}.Part2_Line1_MiddleName[0]": p["beneficiary_middle_name"],
            "Part2_Line3_StreetNumberName[0]": p["beneficiary_mailing_address_line1"],
            "Part2_Line3_CityTown[0]": p["beneficiary_mailing_city"],
            "Part2_Line3_State[0]": p["beneficiary_current_address"]["state"],
            "Part2_Line3_ZipCode[0]": p["beneficiary_mailing_zip"],
            "Part2_Line3_Country[0]": p["beneficiary_mailing_country"],
            "Part2_Line5_AlienNumber[0]": p["beneficiary_a_number"],
            "Part2_Line6_CountryOfBirth[0]": p["beneficiary_country_of_birth"],
            "Part2_Line7_CountryOfCitizenshiporNationality[0]": p["beneficiary_country_of_citizenship"],
            "Part2_Line9_DateOfBirth[0]": _mdy(p["beneficiary_date_of_birth"]),
            "Part2_Line10_SSN[0]": p["beneficiary_social_security_number"],
            "Part2_Line12_ClassofAdmission[0]": p["beneficiary_class_of_admission"],
            "Part2_Line13_I94RecordNo[0]": p["beneficiary_i94_number"],
            "Part2_Line14_I94ExpDate[0]": _mdy(p["beneficiary_i94_expiration"]),
            "P3_Line3_HeightFeet[0]": str(p["beneficiary_height_feet"]),
            "P3_Line3_HeightInches[0]": str(p["beneficiary_height_inches"]),
            "P3_Line4_Pound1[0]": weight[0],
            "P3_Line4_Pound2[0]": weight[1],
            "P3_Line4_Pound3[0]": weight[2],
            "P7_Line1_DateOfDeparture[0]": _mdy(p["i131_intended_departure_date"]),
            "P7_Line2_Purpose[0]": p["i131_travel_purpose"],
            "P7_Line3_ListCountries[0]": p["i131_countries_to_visit"],
            "P7_Line5_ExpectedLengthTrip[0]": str(p["i131_expected_trip_length"]),
            "Part10_Line1_DayPhone[0]": p["beneficiary_phone"],
            "Part10_Line2_MobilePhone[0]": p["beneficiary_mobile_phone"],
            "Part10_Line3_Email[0]": p["beneficiary_email"],
        },
        on={"Part2_Line8_Gender[1]" if p["beneficiary_sex"] == "male" else "Part2_Line8_Gender[0]"},
    )
    expected.unit(p.beneficiary_unit, "Part2_Line3_Unit[1]", "Part2_Line3_Unit[0]", "Part2_Line3_Unit[2]", "Part2_Line3_AptSteFlrNumber[0]")
    return expected


def expected_i864(p: Profile) -> Expected:
    expected = Expected(
        text={
            "P2_Line1a_FamilyName[0]": p["beneficiary_last_name"],
            "P2_Line1b_GivenName[0]": p["beneficiary_first_name"],
            "P2_Line1c_MiddleName[0]": p["beneficiary_middle_name"],
            "P2_Line2_StreetNumberName[0]": p["beneficiary_mailing_address_line1"],
            "P2_Line2_CityOrTown[0]": p["beneficiary_mailing_city"],
            "P2_Line2_State[0]": p["beneficiary_current_address"]["state"],
            "P2_Line2_ZipCode[0]": p["beneficiary_mailing_zip"],
            "P2_Line3_CountryCitizenship[0]": p["beneficiary_country_of_citizenship"],
            "P2_Line4_DateOfBirth[0]": _mdy(p["beneficiary_date_of_birth"]),
            "P2_Line5_AlienNumber[0]": p["beneficiary_a_number"],
            "P2_Line7_DaytimePhoneNumber[0]": p["beneficiary_phone"],
            "P4_Line1a_FamilyName[0]": p["petitioner_last_name"],
            "P4_Line1b_GivenName[0]": p["petitioner_first_name"],
            "P4_Line1c_MiddleName[0]": p["petitioner_middle_name"],
            "P4_Line2b_StreetNumberName[0]": p["petitioner_current_address_line1"],
            "P4_Line2e_CityOrTown[0]": p["petitioner_current_city"],
            "P4_Line2f_State[0]": p["petitioner_current_state"],
            "P4_Line2g_ZipCode[0]": p["petitioner_current_zip"],
            "P4_Line5_CountryOfDomicile[0]": p["petitioner_country_of_domicile"],
            "P4_Line6_DateOfBirth[0]": _mdy(p["petitioner_date_of_birth"]),
            # USCIS named this field CityofBirth, but Item 7 prints and reads as Country of Birth.
            "P4_Line7_CityofBirth[0]": p["petitioner_country_of_birth"],
            "P4_Line10_SocialSecurityNumber[0]": p["petitioner_social_security_number"],
            "Override[0]": str(p["household_size"]),
            "P6_Line1a_NameofEmployer[0]": p["petitioner_current_occupation"],
            "P6_Line1a1_NameofEmployer[0]": p["petitioner_current_employer"],
            "P6_Line2_TotalIncome[0]": str(p["annual_income"]),
            "P6_Line15_TotalHouseholdIncome[0]": str(p["i864_household_income"]),
            "P6_Line19a_TaxYear[0]": str(p["i864_tax_year_1"]),
            "P6_Line19a_TotalIncome[0]": str(p["i864_tax_income_1"]),
            "P6_Line19b_TaxYear[0]": str(p["i864_tax_year_2"]),
            "P6_Line19b_TotalIncome[0]": str(p["i864_tax_income_2"]),
            "P6_Line19c_TaxYear[0]": str(p["i864_tax_year_3"]),
            "P6_Line19c_TotalIncome[0]": str(p["i864_tax_income_3"]),
            "P7_Line1_BalanceofAccounts[0]": str(p["i864_cash_assets"]),
            "P7_Line10_TotalValueAssets[0]": str(p["i864_total_assets"]),
            "P8_Line3_DaytimeTelephoneNumber[0]": p["petitioner_phone"],
            "P8_Line4_MobileTelephoneNumber[0]": p["petitioner_mobile_phone"],
            "P7Line7_EmailAddress[0]": p["petitioner_email"],
        },
    )
    expected.unit(p.petitioner_unit, "P4_Line2c_Unit[0]", "P4_Line2c_Unit[1]", "P4_Line2c_Unit[2]", "P4_Line2d_AptSteFlrNumber[0]")
    expected.unit(p.beneficiary_unit, "P2_Line2_Unit[0]", "P2_Line2_Unit[1]", "P2_Line2_Unit[2]", "P2_Line2_AptSteFlrNumber[0]")
    return expected


def expected_i130(p: Profile) -> Expected:
    expected = Expected(
        text={
            "Pt2Line4a_FamilyName[0]": p["petitioner_last_name"],
            "Pt2Line4b_GivenName[0]": p["petitioner_first_name"],
            "Pt2Line4c_MiddleName[0]": p["petitioner_middle_name"],
            "Pt2Line6_CityTownOfBirth[0]": p["petitioner_city_of_birth"],
            "Pt2Line7_CountryofBirth[0]": p["petitioner_country_of_birth"],
            "Pt2Line8_DateofBirth[0]": _mdy(p["petitioner_date_of_birth"]),
            "Pt2Line11_SSN[0]": p["petitioner_social_security_number"],
            "Pt2Line10_StreetNumberName[0]": p["petitioner_current_address_line1"],
            "Pt2Line10_CityOrTown[0]": p["petitioner_current_city"],
            "Pt2Line10_State[0]": p["petitioner_current_state"],
            "Pt2Line10_ZipCode[0]": p["petitioner_current_zip"],
            "Pt2Line12_StreetNumberName[0]": p["petitioner_physical_address_line1"],
            "Pt2Line13a_DateFrom[0]": _mdy(p["petitioner_physical_address_from"]),
            "Pt2Line16_NumberofMarriages[0]": "1",
            "Pt2Line18_DateOfMarriage[0]": _mdy(p["marriage_date"]),
            "Pt2Line19a_CityTown[0]": p["marriage_place_city"],
            "Pt2Line19b_State[0]": p["marriage_place_state"],
            # The spouse named on the petition is the beneficiary, including the family name.
            "PtLine20a_FamilyName[0]": p["beneficiary_last_name"],
            "Pt2Line20b_GivenName[0]": p["beneficiary_first_name"],
            "Pt2Line20c_MiddleName[0]": p["beneficiary_middle_name"],
            "Pt2Line24_FamilyName[0]": p["petitioner_parent1_last_name"],
            "Pt2Line24_GivenName[0]": p["petitioner_parent1_first_name"],
            "Pt2Line25_DateofBirth[0]": _mdy(p["petitioner_parent1_date_of_birth"]),
            "Pt2Line30a_FamilyName[0]": p["petitioner_parent2_last_name"],
            "Pt2Line30b_GivenName[0]": p["petitioner_parent2_first_name"],
            "Pt2Line31_DateofBirth[0]": _mdy(p["petitioner_parent2_date_of_birth"]),
            "Pt2Line40_EmployerOrCompName[0]": p["petitioner_current_employer"],
            "Pt2Line42_Occupation[0]": p["petitioner_current_occupation"],
            "Pt4Line1_AlienNumber[0]": p["beneficiary_a_number"],
            "Pt4Line3_SSN[0]": p["beneficiary_social_security_number"],
            "Pt4Line4a_FamilyName[0]": p["beneficiary_last_name"],
            "Pt4Line4b_GivenName[0]": p["beneficiary_first_name"],
            "Pt4Line4c_MiddleName[0]": p["beneficiary_middle_name"],
            "Pt4Line7_CityTownOfBirth[0]": p["beneficiary_city_of_birth"],
            "Pt4Line8_CountryOfBirth[0]": p["beneficiary_country_of_birth"],
            "Pt4Line9_DateOfBirth[0]": _mdy(p["beneficiary_date_of_birth"]),
            "Pt4Line11_StreetNumberName[0]": p["beneficiary_current_address_line1"],
            "Pt4Line11_CityOrTown[0]": p["beneficiary_current_city"],
            "Pt4Line11_State[0]": p["beneficiary_current_address"]["state"],
            "Pt4Line11_ZipCode[0]": p["beneficiary_current_zip"],
            "Pt4Line14_DaytimePhoneNumber[0]": p["beneficiary_phone"],
            "Pt4Line15_MobilePhoneNumber[0]": p["beneficiary_mobile_phone"],
            "Pt4Line16_EmailAddress[0]": p["beneficiary_email"],
            "Pt4Line16a_FamilyName[0]": p["petitioner_last_name"],
            "Pt4Line16b_GivenName[0]": p["petitioner_first_name"],
            # Item 21.a is a dropdown whose USCIS options have no hyphen.
            "Pt4Line21a_ClassOfAdmission[0]": p["beneficiary_class_of_admission"].replace("-", ""),
            "Pt4Line21b_ArrivalDeparture[0]": p["beneficiary_i94_number"],
            "Pt4Line21c_DateOfArrival[0]": _mdy(p["beneficiary_last_arrival_date"]),
            "Pt4Line21d_DateExpired[0]": _mdy(p["beneficiary_status_expires_on"]),
            "Pt4Line22_PassportNumber[0]": p["beneficiary_passport_number"],
            "Pt4Line24_CountryOfIssuance[0]": p["beneficiary_passport_country"],
            "Pt4Line25_ExpDate[0]": _mdy(p["beneficiary_passport_expiration"]),
            "Pt4Line26_NameOfCompany[0]": p["beneficiary_current_employer_or_school"],
            "Pt6Line3_DaytimePhoneNumber[0]": p["petitioner_phone"],
            "Pt6Line4_MobileNumber[0]": p["petitioner_mobile_phone"],
            "Pt6Line5_Email[0]": p["petitioner_email"],
        },
        on={
            "Pt2Line9_Male[0]" if p["petitioner_sex"] == "male" else "Pt2Line9_Female[0]",
            "Pt4Line9_Male[0]" if p["beneficiary_sex"] == "male" else "Pt4Line9_Female[0]",
        },
        off={
            "Pt2Line9_Female[0]" if p["petitioner_sex"] == "male" else "Pt2Line9_Male[0]",
            "Pt4Line9_Female[0]" if p["beneficiary_sex"] == "male" else "Pt4Line9_Male[0]",
        },
    )
    expected.unit(p.petitioner_unit, "Pt2Line10_Unit[0]", "Pt2Line10_Unit[1]", "Pt2Line10_Unit[2]", "Pt2Line10_AptSteFlrNumber[0]")
    expected.unit(p.petitioner_unit, "Pt2Line12_Unit[0]", "Pt2Line12_Unit[1]", "Pt2Line12_Unit[2]", "Pt2Line12_AptSteFlrNumber[0]")
    expected.unit(p.beneficiary_unit, "Pt4Line11_Unit[0]", "Pt4Line11_Unit[1]", "Pt4Line11_Unit[2]", "Pt4Line11_AptSteFlrNumber[0]")
    return expected


def expected_i130a(p: Profile) -> Expected:
    prior = p["beneficiary_prior_address_history"][0]
    foreign = p["beneficiary_recent_foreign_address"]
    expected = Expected(
        text={
            "Pt1Line1_AlienNumber[0]": p["beneficiary_a_number"],
            "Pt1Line3a_FamilyName[0]": p["beneficiary_last_name"],
            "Pt1Line3b_GivenName[0]": p["beneficiary_first_name"],
            "Pt1Line3c_MiddleName[0]": p["beneficiary_middle_name"],
            "Pt1Line4a_StreetNumberName[0]": p["beneficiary_current_address_line1"],
            "Pt1Line4c_CityOrTown[0]": p["beneficiary_current_city"],
            "Pt1Line4d_State[0]": p["beneficiary_current_address"]["state"],
            "Pt1Line4e_ZipCode[0]": p["beneficiary_current_zip"],
            "Pt1Line5a_DateFrom[0]": _mdy(p["beneficiary_address_since"]),
            "Pt1Line6a_StreetNumberName[0]": prior["line1"],
            "Pt1Line6c_CityOrTown[0]": prior["city"],
            "Pt1Line6e_ZipCode[0]": prior["zip"],
            "Pt1Line7a_DateFrom[0]": _mdy(prior["from"]),
            "Pt1Line7b_DateTo[0]": _mdy(prior["to"]),
            # Items 10-16 describe Parent 1, even though USCIS named some fields after the applicant.
            "Pt1Line10_FamilyName[0]": p["parent1_last_name"],
            "Pt1Line10_GivenName[0]": p["parent1_first_name"],
            "Pt1Line10_MiddleName[0]": p["parent1_middle_name"],
            "Pt1Line11_DateofBirth[0]": _mdy(p["parent1_date_of_birth"]),
            "Pt1Line12CityTownOfBirth[0]": p["parent1_city_of_birth"],
            "Pt1Line13_CountryofBirth[0]": p["parent1_country_of_birth"],
            "Pt1Line14_CountryofBirth[0]": p["parent1_city_of_residence"],
            "Pt1Line15_CountryofResidence[0]": p["parent1_country_of_residence"],
            # Items 17-23 describe Parent 2.
            "Pt1Line16_FamilyName[0]": p["parent2_last_name"],
            "Pt1Line16_GivenName[0]": p["parent2_first_name"],
            "Pt1Line16_MiddleName[0]": p["parent2_middle_name"],
            "Pt1Line17_DateofBirth[0]": _mdy(p["parent2_date_of_birth"]),
            "Pt1Line18_CityTownOfBirth[0]": p["parent2_city_of_birth"],
            "Pt1Line19_CountryofBirth[0]": p["parent2_country_of_birth"],
            "Pt1Line20_CityTownVillageofRes[0]": p["parent2_city_of_residence"],
            "Pt1Line21_CountryofResidence[0]": p["parent2_country_of_residence"],
            "Pt1Line8a_StreetNumberName[0]": foreign["line1"],
            "Pt1Line8c_CityOrTown[0]": foreign["city"],
            "Pt1Line8d_Province[0]": foreign["province"],
            "Pt1Line8e_PostalCode[0]": foreign["postal_code"],
            "Pt1Line8f_Country[0]": foreign["country"],
            "Pt1Line9a_DateFrom[0]": _mdy(foreign["from"]),
            "Pt1Line9b_DateTo[0]": _mdy(foreign["to"]),
            "Pt2Line1_EmployerOrCompName[0]": p["beneficiary_current_employer_or_school"],
            "Pt2Line2a_StreetNumberName[0]": p["beneficiary_current_employer_address_line1"],
            "Pt2Line2c_CityOrTown[0]": p["beneficiary_current_employer_city"],
            "Pt2Line2d_State[0]": p["beneficiary_current_employer_state"],
            "Pt2Line2e_ZipCode[0]": p["beneficiary_current_employer_zip"],
            "Pt2Line2h_Country[0]": p["beneficiary_current_employer_country"],
            "Pt2Line3_Occupation[0]": p["beneficiary_current_occupation"],
            "Pt2Line4a_DateFrom[0]": _mdy(p["beneficiary_current_employment_from"]),
            "Pt4Line3_DaytimePhoneNumber1[0]": p["beneficiary_phone"],
            "Pt4Line5_Email[0]": p["beneficiary_email"],
        },
        on={"Pt1Line12_Female[0]", "Pt1Line19_Male[0]"},
        off={"Pt1Line12_Male[0]", "Pt1Line19_Female[0]"},
    )
    expected.unit(p.beneficiary_unit, "Pt1Line4b_Unit[0]", "Pt1Line4b_Unit[1]", "Pt1Line4b_Unit[2]", "Pt1Line4b_AptSteFlrNumber[0]")
    expected.unit(p.prior_unit, "Pt1Line6b_Unit[0]", "Pt1Line6b_Unit[1]", "Pt1Line6b_Unit[2]", "Pt1Line6b_AptSteFlrNumber[0]")
    return expected


def expected_g1145(p: Profile) -> Expected:
    return Expected(
        text={
            "LastName[0]": p["beneficiary_last_name"],
            "FirstName[0]": p["beneficiary_first_name"],
            "MiddleName[0]": p["beneficiary_middle_name"],
            "Email[0]": p["beneficiary_email"],
            "MobilePhoneNumber[0]": p["beneficiary_mobile_phone"],
        }
    )


def expected_g1450(p: Profile) -> Expected:
    payload = card_payment_payload(p)
    number = payload["credit_card_number"]
    box = {"Visa": "CreditCardTypeChBx[0]", "Mastercard": "CreditCardTypeChBx[1]"}.get(payload["credit_card_type"])
    expected = Expected(
        text={
            "FamilyName[0]": p["beneficiary_last_name"],
            "CCHolderFamilyName[0]": p["petitioner_last_name"],
            "CCHolderGivenName[0]": p["petitioner_first_name"],
            "Pt1Line2b_StreetNumberName[0]": p["petitioner_current_address_line1"],
            "CCHolderAptSteFlrNumber[0]": "12",
            "CityOrTown[0]": p["petitioner_current_city"],
            "State[0]": p["petitioner_current_state"],
            "ZipCode[0]": p["petitioner_current_zip"],
            "DaytimeTelephoneNumber[0]": p["petitioner_phone"],
            "Email[0]": p["petitioner_email"],
            "CreditCardNumber_1[0]": number[:4],
            "CreditCardNumber_2[0]": number[4:8],
            "CreditCardNumber_3[0]": number[8:12],
            "CreditCardNumber_4[0]": number[12:],
            "ExpirationDate[0]": f"{int(payload['expiration_month']):02d}/{payload['expiration_year']}",
            "AuthorizedPaymentAmt[0]": payload["authorized_amount"],
        },
        on={"CCHolderAptSteFlr_Unit[0]"},
    )
    if box:
        expected.on.add(box)
    return expected


def expected_g1650(p: Profile) -> Expected:
    payload = bank_payment_payload(p)
    applicant = "form1[0].PG1[0].sfApplicantPetitionerName[0]"
    holder = "form1[0].PG1[0].sfBankAccountHolderInfo[0]"
    bank = "form1[0].PG1[0].sfBankAccountInformation[0]"
    return Expected(
        text={
            f"{applicant}.FamilyName[0]": p["beneficiary_last_name"],
            f"{holder}.FamilyName[0]": p["petitioner_last_name"],
            f"{holder}.GivenName[0]": p["petitioner_first_name"],
            f"{bank}.AuthorizedPaymentAmt[0]": "1440",
            f"{bank}.RoutingNumber[0]": payload["routing_number"],
            f"{bank}.AccountNumber[0]": payload["account_number"],
            f"{bank}.BankName[0]": payload["bank_name"],
        }
    )


EXPECTED_BY_FORM = {
    "i485": expected_i485,
    "i765": expected_i765,
    "i131": expected_i131,
    "i864": expected_i864,
    "i130": expected_i130,
    "i130a": expected_i130a,
    "g1145": expected_g1145,
    "g1450": expected_g1450,
    "g1650": expected_g1650,
}


@dataclass
class GeneratedForm:
    path: Path
    widgets: list[PdfWidget]
    result: Any = None


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _seed_profile_case(session: Session, profile: Profile) -> CaseRecord:
    case = CaseRecord(
        case_name=f"PDF regression profile {profile.seed}",
        workflow_type="marriage_concurrent",
        petitioner_email=profile["petitioner_email"],
        beneficiary_email=profile["beneficiary_email"],
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    upsert_intake_step(session, case.id, "regression_profile", profile.answers)
    for page in I485_QUESTIONNAIRE:
        save_i485_page_answers(
            session,
            case.id,
            page["id"],
            {question["id"]: profile[question["id"]] for question in page["questions"] if question["id"] in profile.answers},
        )
    for form_key in SUPPLEMENTAL_FORM_KEYS:
        for page_id, answers in form_answers(profile, form_key).items():
            save_form_page_answers(session, case.id, form_key, page_id, answers)
    session.commit()
    return case


def _generate_questionnaire_form(session: Session, case_id: Any, form_key: str, output_path: Path, **kwargs: Any) -> Any:
    if form_key == "i485":
        return generate_i485_pdf(session=session, case_id=case_id, output_path=output_path, **kwargs)
    return generate_form_pdf(session=session, case_id=case_id, form_key=form_key, output_path=output_path, **kwargs)


@pytest.fixture(scope="module")
def generated_forms(tmp_path_factory: pytest.TempPathFactory) -> dict[int, dict[str, GeneratedForm]]:
    forms: dict[int, dict[str, GeneratedForm]] = {}
    for seed in PROFILE_SEEDS:
        profile = build_profile(seed)
        output_dir = tmp_path_factory.mktemp(f"profile-{seed}")
        forms[seed] = {}
        with _session() as session:
            case = _seed_profile_case(session, profile)
            for form_key in QUESTIONNAIRE_FORMS:
                path = output_dir / f"{form_key}.pdf"
                # allow_incomplete=False is the "profile is ready" gate these seeds must clear.
                result = _generate_questionnaire_form(session, case.id, form_key, path, allow_incomplete=False)
                forms[seed][form_key] = GeneratedForm(path, read_pdf_widgets(path), result)
        path = output_dir / "g1145.pdf"
        result = generate_g1145_pdf(case_id=uuid4(), values=profile.answers, output_path=path)
        forms[seed]["g1145"] = GeneratedForm(path, read_pdf_widgets(path), result)
        path = output_dir / "g1450.pdf"
        generate_g1450_pdf_from_payload(
            payload=card_payment_payload(profile), template_path=TEMPLATE_DIR / "g-1450.pdf", output_path=path
        )
        forms[seed]["g1450"] = GeneratedForm(path, read_pdf_widgets(path))
        path = output_dir / "g1650.pdf"
        generate_g1650_pdf_from_payload(
            payload=bank_payment_payload(profile),
            template_path=TEMPLATE_DIR / "g-1650.pdf",
            output_path=path,
            amount_override="1440.00",
        )
        forms[seed]["g1650"] = GeneratedForm(path, read_pdf_widgets(path))
    return forms


def _matching_widgets(widgets: list[PdfWidget], field_name: str) -> list[PdfWidget]:
    return [widget for widget in widgets if field_name in {widget.name, widget.full_name}]


def _assert_expected(widgets: list[PdfWidget], expected: Expected) -> None:
    wrong_text: dict[str, tuple[str, list[str]]] = {}
    for field_name, value in expected.text.items():
        matches = _matching_widgets(widgets, field_name)
        actual = sorted({widget.value.strip() for widget in matches})
        if not matches or actual != [str(value).strip()]:
            wrong_text[field_name] = (str(value), actual)
    unchecked = sorted(
        field_name
        for field_name in expected.on
        if not any(widget.appearance_state not in {"", "/Off"} for widget in _matching_widgets(widgets, field_name))
    )
    wrongly_checked = sorted(
        field_name
        for field_name in expected.off
        if any(widget.appearance_state not in {"", "/Off"} for widget in _matching_widgets(widgets, field_name))
    )
    assert wrong_text == {}
    assert unchecked == []
    assert wrongly_checked == []


@pytest.mark.parametrize("seed", PROFILE_SEEDS)
@pytest.mark.parametrize("form_key", ALL_FORMS)
def test_generated_form_carries_this_profiles_data(generated_forms, seed: int, form_key: str):
    form = generated_forms[seed][form_key]

    _assert_expected(form.widgets, EXPECTED_BY_FORM[form_key](build_profile(seed)))


@pytest.mark.parametrize("seed", PROFILE_SEEDS)
@pytest.mark.parametrize("form_key", ALL_FORMS)
def test_generated_form_will_print_correctly(generated_forms, seed: int, form_key: str):
    form = generated_forms[seed][form_key]

    assert_widgets_will_print(form.widgets)
    assert_widget_values_are_formatted(form.widgets)


@pytest.mark.parametrize("seed", PROFILE_SEEDS)
@pytest.mark.parametrize("form_key", QUESTIONNAIRE_FORMS)
def test_ready_profile_generates_without_review_gaps(generated_forms, seed: int, form_key: str):
    result = generated_forms[seed][form_key].result

    assert result.generation_status == "ready_for_user_review"
    assert result.ready_for_pdf_generation is True
    assert result.missing_template_fields == []
    assert result.unmapped_answered_questions == []


@pytest.mark.parametrize("seed", PROFILE_SEEDS)
@pytest.mark.parametrize("form_key", ALL_FORMS)
def test_sample_persona_never_reaches_a_seeded_applicants_form(generated_forms, seed: int, form_key: str):
    leaks = {
        name: value
        for name, value in filled_text_values(generated_forms[seed][form_key].widgets).items()
        if any(sample in value for sample in SAMPLE_PERSONA_VALUES)
    }

    assert leaks == {}


@pytest.mark.parametrize("form_key", ALL_FORMS)
def test_each_seed_fills_a_form_with_its_own_values(generated_forms, form_key: str):
    fills = [frozenset(filled_text_values(generated_forms[seed][form_key].widgets).items()) for seed in PROFILE_SEEDS]

    assert len(set(fills)) == len(PROFILE_SEEDS)
    assert all(len(fill) >= 4 for fill in fills)


def test_profiles_are_reproducible_and_vary_the_axes_that_change_forms():
    assert build_profile(3).answers == build_profile(3).answers
    profiles = [build_profile(seed) for seed in PROFILE_SEEDS]

    assert {profile.beneficiary_unit[0].split(" ")[0] for profile in profiles} == {"Apt", "Ste", "Fl", ""}
    assert {profile["beneficiary_sex"] for profile in profiles} == {"female", "male"}
    assert {profile["beneficiary_class_of_admission"] for profile in profiles} == {"B-1", "B-2", "F-1"}
    assert {bool(profile["beneficiary_a_number"]) for profile in profiles} == {True, False}
    assert {bool(profile["beneficiary_ssn"]) for profile in profiles} == {True, False}
    assert {bool(profile["beneficiary_middle_name"]) for profile in profiles} == {True, False}
    assert {profile.state_written_as_name for profile in profiles} == {True, False}
    assert any(not profile["beneficiary_last_name"].isascii() for profile in profiles)
    assert any("'" in profile["beneficiary_last_name"] for profile in profiles)


# --- Field maps checked against the USCIS tooltip text in the blank templates.

TOOLTIP_RULES: list[tuple[str, str]] = [
    (r"last_name$", r"family name|last name"),
    (r"first_name$", r"given name|first name"),
    (r"middle_name$", r"middle"),
    (r"line1$", r"street"),
    (r"_city$|city_of_birth$|city_of_residence$", r"city|town"),
    (r"_state$", r"state"),
    (r"_zip$", r"zip"),
    (r"postal_code$", r"postal"),
    (r"province$", r"province"),
    (r"country", r"country|citizenship|nationality"),
    (r"date|_from$|_to$|expir|expires|_since$|marriage_ended", r"date|month|expir|mm/dd|present"),
    (r"email", r"e-?mail"),
    (r"phone", r"phone|telephone"),
    (r"social_security|_ssn$", r"social"),
    (r"a_number", r"alien|a-?\.? ?number"),
    (r"passport_number", r"passport"),
    (r"i94_number", r"94|arrival"),
    (r"occupation", r"occupation|employed as"),
    (r"online_account", r"online"),
]
TEXT_MAPS = {
    "i485": I485_TEXT_FIELD_MAP,
    "i765": TEXT_FIELD_MAP["i765"],
    "i131": TEXT_FIELD_MAP["i131"],
    "i864": TEXT_FIELD_MAP["i864"],
    "i130": I130_TEXT_FIELD_MAP,
    "i130a": I130A_TEXT_FIELD_MAP,
    "g1145": G1145_TEXT_FIELD_MAP,
}
CHECKBOX_MAPS = {
    "i485": I485_CHECKBOX_FIELD_MAP,
    "i765": CHECKBOX_FIELD_MAP["i765"],
    "i131": CHECKBOX_FIELD_MAP["i131"],
    "i864": CHECKBOX_FIELD_MAP["i864"],
    "i130": I130_CHECKBOX_FIELD_MAP,
    "i130a": I130A_CHECKBOX_FIELD_MAP,
}
UNIT_MAPS = {
    "i765": UNIT_FIELD_MAP["i765"],
    "i131": UNIT_FIELD_MAP["i131"],
    "i864": UNIT_FIELD_MAP["i864"],
    "i130": I130_UNIT_FIELD_MAP,
    "i130a": I130A_UNIT_FIELD_MAP,
}


# Seeded profiles stay on the standard U.S.-citizen, first-marriage, in-the-U.S. path that clears readiness.
# These answers belong to other paths, so test_every_text_mapping_writes_its_answer_to_the_template covers them.
_FOREIGN_POSTAL_QUESTIONS = {
    f"{prefix}_{part}"
    for prefix in (
        "beneficiary_current",
        "beneficiary_current_employer",
        "beneficiary_last_shared",
        "petitioner_current",
        "petitioner_current_employer",
        "petitioner_physical",
        "petitioner_prior",
        "petitioner_prior_employer",
    )
    for part in ("postal_code", "province")
}
CONDITIONAL_QUESTIONS_NOT_ON_THE_STANDARD_PATH: dict[str, set[str]] = {
    "i485": {"highest_grade_completed", "i485_priority_date", "i485_underlying_petition_receipt", "petitioner_a_number", "status_before_evading_service"},
    "i131": {
        "beneficiary_mailing_postal_code",
        "beneficiary_mailing_province",
        "i131_prior_advance_parole_date",
        "i131_prior_advance_parole_disposition",
        "i131_prior_reentry_refugee_document_date",
        "i131_prior_reentry_refugee_document_disposition",
        "i131_processing_city",
        "i131_processing_country",
    },
    "i130": _FOREIGN_POSTAL_QUESTIONS
    | {
        "beneficiary_consular_city",
        "beneficiary_consular_country",
        "beneficiary_consular_province",
        "beneficiary_immigration_proceedings_city",
        "beneficiary_immigration_proceedings_date",
        "beneficiary_immigration_proceedings_state",
        "beneficiary_last_shared_address_to",
        "beneficiary_native_middle_name",
        "beneficiary_other_middle_name",
        "beneficiary_spouse1_marriage_ended",
        "beneficiary_spouse2_first_name",
        "beneficiary_spouse2_last_name",
        "beneficiary_spouse2_marriage_ended",
        "beneficiary_spouse2_middle_name",
        "marriage_place_province",
        "petitioner_a_number",
        "petitioner_lpr_admission_city",
        "petitioner_lpr_admission_state",
        "petitioner_lpr_class_of_admission",
        "petitioner_lpr_date_of_admission",
        "petitioner_naturalization_certificate_date",
        "petitioner_naturalization_certificate_number",
        "petitioner_naturalization_certificate_place",
        "petitioner_other_middle_name",
        "petitioner_spouse1_marriage_ended",
        "prior_i130_city",
        "prior_i130_date_filed",
        "prior_i130_first_name",
        "prior_i130_last_name",
        "prior_i130_middle_name",
        "prior_i130_result",
        "prior_i130_state",
    },
}


def _template_widgets(form_key: str) -> dict[str, PdfWidget]:
    widgets: dict[str, PdfWidget] = {}
    for widget in read_pdf_widgets(TEMPLATE_DIR / TEMPLATE_BY_FORM[form_key]):
        widgets.setdefault(widget.name, widget)
        widgets.setdefault(widget.full_name, widget)
    return widgets


@pytest.mark.parametrize("form_key", TEXT_MAPS)
def test_text_field_map_matches_uscis_tooltips(form_key: str):
    widgets = _template_widgets(form_key)
    mismatches: dict[str, str] = {}
    for question_id, field_names in TEXT_MAPS[form_key].items():
        for field_name in field_names:
            tooltip = widgets[field_name].tooltip.lower()
            # A person's own identity must never land in a line USCIS labels as a parent's.
            own_identity = re.match(r"^(beneficiary|petitioner)_(?!parent)", question_id)
            wrong_subject = own_identity and re.search(r"\bparent\b", tooltip)
            wrong_kind = any(
                re.search(question_pattern, question_id) and not re.search(tooltip_pattern, tooltip)
                for question_pattern, tooltip_pattern in TOOLTIP_RULES
            )
            if wrong_subject or wrong_kind:
                mismatches[f"{question_id} -> {field_name}"] = tooltip[-90:]

    assert mismatches == {}


@pytest.mark.parametrize("form_key", CHECKBOX_MAPS)
def test_every_mapped_checkbox_uses_a_state_the_template_can_draw(form_key: str):
    widgets = _template_widgets(form_key)
    invalid = {
        f"{question_id}={choice}": (field_name, appearance, sorted(widgets[field_name].on_states))
        for question_id, choices in CHECKBOX_MAPS[form_key].items()
        for choice, (field_name, appearance) in choices.items()
        if appearance not in widgets[field_name].on_states
    }

    assert invalid == {}


@pytest.mark.parametrize("form_key", UNIT_MAPS)
def test_every_mapped_unit_box_is_labeled_for_its_unit_type(form_key: str):
    widgets = _template_widgets(form_key)
    problems: dict[str, Any] = {}
    for apt, ste, flr, number in UNIT_MAPS[form_key].values():
        for label, field_name, tooltip_word in (("Apt 1", apt, "apartment"), ("Ste 1", ste, "suite"), ("Fl 1", flr, "floor")):
            text_values: dict[str, str] = {}
            checkbox_values: dict[str, str] = {}
            add_unit_fields(
                text_values=text_values,
                checkbox_values=checkbox_values,
                value=label,
                apt_field=apt,
                ste_field=ste,
                flr_field=flr,
                number_field=number,
            )
            widget = widgets[field_name]
            if tooltip_word not in widget.tooltip.lower():
                problems[field_name] = f"expected {tooltip_word}: {widget.tooltip[-50:]}"
            # Generation resolves the requested state to the template's spelling by its letters.
            requested = str(checkbox_values.get(field_name)).replace("/", "").strip()
            if requested not in {state.replace("/", "").strip() for state in widget.on_states}:
                problems[field_name] = (checkbox_values.get(field_name), sorted(widget.on_states))

    assert problems == {}


@pytest.mark.parametrize(
    ("form_key", "question_id"),
    [(form_key, question_id) for form_key, choices in CHECKBOX_MAPS.items() for question_id in choices if question_id.endswith("_sex")],
)
def test_sex_checkboxes_match_their_uscis_labels(form_key: str, question_id: str):
    widgets = _template_widgets(form_key)
    choices = CHECKBOX_MAPS[form_key][question_id]

    # "female" contains "male", so the male box must also be free of "female".
    assert "female" in widgets[choices["female"][0]].tooltip.lower()
    male_tooltip = widgets[choices["male"][0]].tooltip.lower()
    assert "male" in male_tooltip and "female" not in male_tooltip


@pytest.mark.parametrize("option", CLASS_OF_ADMISSION_OPTIONS, ids=lambda option: option["value"])
def test_i485_status_label_fits_the_form_for_every_class(option: dict[str, str]):
    for value in (option["value"], option["label"]):
        assert len(_immigration_status_label(value)) <= I485_STATUS_FIELD_LENGTH, value


def test_every_mapped_question_is_exercised_by_a_seed_or_listed_as_conditional(generated_forms):
    unexercised: dict[str, set[str]] = {}
    for form_key, field_map in TEXT_MAPS.items():
        filled = {
            name
            for seed in PROFILE_SEEDS
            for widget in generated_forms[seed][form_key].widgets
            if widget.value.strip()
            for name in (widget.name, widget.full_name)
        }
        missed = {question_id for question_id, field_names in field_map.items() if not set(field_names) & filled}
        if missed:
            unexercised[form_key] = missed

    assert unexercised == CONDITIONAL_QUESTIONS_NOT_ON_THE_STANDARD_PATH


def _round_trip_value(question_id: str, index: int) -> tuple[Any, str]:
    if re.search(r"date|_from$|_to$|expir|expires|_since$|marriage_ended", question_id):
        return "2020-03-14", "03/14/2020"
    if question_id.endswith("_state"):
        return "TX", "TX"
    if question_id.endswith("_phone"):
        return f"555{index:07d}", f"555{index:07d}"
    return f"Q{index}", f"Q{index}"


@pytest.mark.parametrize("form_key", ("i765", "i131", "i864", "i130", "i130a"))
def test_every_text_mapping_writes_its_answer_to_the_template(tmp_path: Path, form_key: str):
    """Reaches the conditional answers that a ready, standard-path profile never fills."""
    # These are written through a derived format or a dropdown, and the seeded profiles assert them directly.
    derived = {
        "beneficiary_class_of_admission",
        "beneficiary_current_immigration_status",
        "beneficiary_height_feet",
        "beneficiary_height_inches",
        "beneficiary_weight_pounds",
        "i131_expected_trip_length",
        "i765_eligibility_category",
        "petitioner_lpr_class_of_admission",
    }
    answers: dict[str, Any] = {}
    printed_by_field: dict[str, str] = {}
    for index, (question_id, field_names) in enumerate(TEXT_MAPS[form_key].items()):
        if question_id in derived:
            continue
        answers[question_id], printed = _round_trip_value(question_id, index)
        # Aliases share a field, and the generator writes the later map entry last.
        printed_by_field.update(dict.fromkeys(field_names, printed))
    path = tmp_path / f"{form_key}.pdf"

    generate_form_pdf_from_answers(case_id=uuid4(), form_key=form_key, answers=answers, output_path=path)

    widgets = read_pdf_widgets(path)
    wrong = {
        field_name: (printed, sorted({widget.value.strip() for widget in _matching_widgets(widgets, field_name)}))
        for field_name, printed in printed_by_field.items()
        if {widget.value.strip() for widget in _matching_widgets(widgets, field_name)} != {printed}
    }
    assert wrong == {}


# --- Forms filled from the applicant's profile alone, before any form-specific page is saved.


@pytest.mark.parametrize("seed", (1, 2))
def test_forms_prefill_from_the_i485_profile_without_form_pages(tmp_path: Path, seed: int):
    profile = build_profile(seed)
    with _session() as session:
        case = CaseRecord(case_name="Profile only", workflow_type="marriage_concurrent")
        session.add(case)
        session.commit()
        session.refresh(case)
        upsert_intake_step(session, case.id, "regression_profile", profile.answers)
        for page in I485_QUESTIONNAIRE:
            save_i485_page_answers(
                session,
                case.id,
                page["id"],
                {question["id"]: profile[question["id"]] for question in page["questions"] if question["id"] in profile.answers},
            )
        session.commit()
        for form_key in SUPPLEMENTAL_FORM_KEYS:
            generate_form_pdf(session=session, case_id=case.id, form_key=form_key, output_path=tmp_path / f"{form_key}.pdf")

    def form_values(form_key: str) -> dict[str, str]:
        return {widget.name: widget.value for widget in read_pdf_widgets(tmp_path / f"{form_key}.pdf")}

    i130a = form_values("i130a")
    assert i130a["Pt1Line10_GivenName[0]"] == profile["parent1_first_name"]
    assert i130a["Pt1Line16_GivenName[0]"] == profile["parent2_first_name"]
    assert i130a["Pt1Line11_DateofBirth[0]"] == _mdy(profile["parent1_date_of_birth"])
    assert i130a["Pt1Line13_CountryofBirth[0]"] == profile["parent1_country_of_birth"]
    i864 = form_values("i864")
    assert i864["P2_Line1a_FamilyName[0]"] == profile["beneficiary_last_name"]
    assert i864["P4_Line7_CityofBirth[0]"] == profile["petitioner_country_of_birth"]
    assert i864["P2_Line2_StreetNumberName[0]"] == profile["beneficiary_mailing_address_line1"]
    assert i864["P2_Line2_AptSteFlrNumber[0]"] == profile.beneficiary_unit[1]
    i130 = form_values("i130")
    assert i130["PtLine20a_FamilyName[0]"] == profile["beneficiary_last_name"]
    assert i130a["Pt1Line8a_StreetNumberName[0]"] == profile["beneficiary_recent_foreign_address"]["line1"]
    history_entry = profile["beneficiary_employment_history"][0]
    assert i130a["Pt2Line2a_StreetNumberName[0]"] == history_entry["line1"]
    assert i130a["Pt2Line4a_DateFrom[0]"] == _mdy(history_entry["from"])
    assert form_values("i765")["Line1a_FamilyName[0]"] == profile["beneficiary_last_name"]
    assert form_values("i131")["Part2_Line3_ZipCode[0]"] == profile["beneficiary_current_zip"]


def test_i130a_prints_parents_for_a_case_saved_before_parents_were_projected(tmp_path: Path):
    profile = build_profile(1)
    with _session() as session:
        case = CaseRecord(case_name="Stored before the I-130A parent fields", workflow_type="marriage_concurrent")
        session.add(case)
        session.commit()
        session.refresh(case)
        for page in I485_QUESTIONNAIRE:
            save_i485_page_answers(
                session,
                case.id,
                page["id"],
                {question["id"]: profile[question["id"]] for question in page["questions"] if question["id"] in profile.answers},
            )
        for step in session.exec(select(IntakeResponse).where(IntakeResponse.case_id == case.id)):
            if step.step_key == I485_PROJECTION_STEP:
                step.payload = {key: value for key, value in step.payload.items() if not key.startswith(("parent1_", "parent2_"))}
                session.add(step)
        session.commit()

        generate_form_pdf(session=session, case_id=case.id, form_key="i130a", output_path=tmp_path / "i130a.pdf")

    widgets = read_pdf_widgets(tmp_path / "i130a.pdf")
    assert _matching_widgets(widgets, "Pt1Line10_GivenName[0]")[0].value == profile["parent1_first_name"]


def test_importing_case_data_clears_i130a_parents_for_a_case_saved_before_they_were_projected():
    profile = build_profile(1)
    with _session() as session:
        case = CaseRecord(case_name="Stored before the I-130A parent fields", workflow_type="marriage_concurrent")
        session.add(case)
        session.commit()
        session.refresh(case)
        for page in I485_QUESTIONNAIRE:
            save_i485_page_answers(
                session,
                case.id,
                page["id"],
                {question["id"]: profile[question["id"]] for question in page["questions"] if question["id"] in profile.answers},
            )
        for step in session.exec(select(IntakeResponse).where(IntakeResponse.case_id == case.id)):
            if step.step_key == I485_PROJECTION_STEP:
                step.payload = {key: value for key, value in step.payload.items() if not key.startswith(("parent1_", "parent2_"))}
                session.add(step)
        session.commit()

        missing_before = {field["question_id"] for field in build_form_fill_preview(session, case.id, "i130a")["missing_required"]}
        import_form_answers_from_case_data(session, case.id, "i130a")
        session.commit()
        missing_after = {field["question_id"] for field in build_form_fill_preview(session, case.id, "i130a")["missing_required"]}

    assert "parent1_first_name" in missing_before
    assert not {question_id for question_id in missing_after if question_id.startswith("parent")}


# --- Answers too long for their USCIS field.


def test_answer_longer_than_its_field_warns_on_every_generator(tmp_path: Path):
    long_email = f"{'very.long.address.' * 3}@example.org"
    profile = build_profile(1)
    answers = {**profile.answers, "beneficiary_email": long_email}
    with _session() as session:
        case = _seed_profile_case(session, Profile(**{**profile.__dict__, "answers": answers}))
        results = [
            _generate_questionnaire_form(session, case.id, form_key, tmp_path / f"{form_key}.pdf")
            for form_key in ("i485", "i765", "i130a")
        ]

    for result in results:
        assert any("may be cut off" in warning and long_email in warning for warning in result.warnings)


@pytest.mark.parametrize("seed", PROFILE_SEEDS)
@pytest.mark.parametrize("form_key", QUESTIONNAIRE_FORMS)
def test_answers_that_fit_do_not_warn_about_length(generated_forms, seed: int, form_key: str):
    assert not any("may be cut off" in warning for warning in generated_forms[seed][form_key].result.warnings)


# --- Characters the form fonts cannot draw.


def test_characters_the_form_font_cannot_draw_warn_instead_of_printing_silently(tmp_path: Path):
    path = tmp_path / "i765.pdf"

    result = generate_form_pdf_from_answers(
        case_id=uuid4(), form_key="i765", answers={"beneficiary_last_name": "Łukasiewicz"}, output_path=path
    )

    assert any("cannot print" in warning and "Łukasiewicz" in warning for warning in result.warnings)


def test_family_form_warns_about_characters_the_font_cannot_draw(tmp_path: Path):
    result = generate_g1145_pdf(
        case_id=uuid4(), values={"beneficiary_last_name": "Łukasiewicz"}, output_path=tmp_path / "g1145.pdf"
    )

    assert any("cannot print" in warning for warning in result.warnings)


@pytest.mark.parametrize("seed", PROFILE_SEEDS)
@pytest.mark.parametrize("form_key", QUESTIONNAIRE_FORMS)
def test_accented_latin_names_print_without_a_warning(generated_forms, seed: int, form_key: str):
    assert not any("cannot print" in warning for warning in generated_forms[seed][form_key].result.warnings)


# --- Readiness gate.


def test_missing_required_answer_blocks_final_generation_but_allows_a_marked_draft(tmp_path: Path):
    profile = build_profile(1)
    with _session() as session:
        case = _seed_profile_case(session, profile)
        pages = form_answers(profile, "i765")
        page_id = next(page_id for page_id, answers in pages.items() if "beneficiary_passport_number" in answers)
        save_form_page_answers(session, case.id, "i765", page_id, {**pages[page_id], "beneficiary_passport_number": ""})
        session.commit()

        with pytest.raises(ValueError, match="not ready for PDF generation"):
            generate_form_pdf(
                session=session, case_id=case.id, form_key="i765", output_path=tmp_path / "final.pdf", allow_incomplete=False
            )
        assert not (tmp_path / "final.pdf").exists()

        draft = generate_form_pdf(
            session=session, case_id=case.id, form_key="i765", output_path=tmp_path / "draft.pdf", allow_incomplete=True
        )

    assert draft.ready_for_pdf_generation is False
    assert draft.missing_required_count == 1
    assert any("review draft" in warning for warning in draft.warnings)
    assert _matching_widgets(read_pdf_widgets(tmp_path / "draft.pdf"), "Line1a_FamilyName[0]")[0].value == profile["beneficiary_last_name"]


def test_risk_answer_blocks_final_generation(tmp_path: Path):
    profile = build_profile(2)
    with _session() as session:
        case = _seed_profile_case(session, profile)
        pages = form_answers(profile, "i765")
        page_id = next(page_id for page_id, answers in pages.items() if "i765_arrested_or_convicted" in answers)
        save_form_page_answers(session, case.id, "i765", page_id, {**pages[page_id], "i765_arrested_or_convicted": True})
        session.commit()

        with pytest.raises(ValueError, match="not ready for PDF generation"):
            generate_form_pdf(
                session=session, case_id=case.id, form_key="i765", output_path=tmp_path / "final.pdf", allow_incomplete=False
            )


def test_missing_i485_required_answer_blocks_final_generation(tmp_path: Path):
    profile = build_profile(1)
    with _session() as session:
        case = _seed_profile_case(session, profile)
        page = next(page for page in I485_QUESTIONNAIRE if any(q["id"] == "beneficiary_passport_number" for q in page["questions"]))
        answers = {q["id"]: profile[q["id"]] for q in page["questions"] if q["id"] in profile.answers}
        save_i485_page_answers(session, case.id, page["id"], {**answers, "beneficiary_passport_number": ""})
        session.commit()

        with pytest.raises(ValueError, match="not ready for PDF generation"):
            generate_i485_pdf(session=session, case_id=case.id, output_path=tmp_path / "final.pdf", allow_incomplete=False)


# --- The seeded developer scenarios.

SCENARIO_BLOCKED_FORMS = {"az-prior-marriage-travel": {"i485", "i130", "i130a"}}


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda scenario: scenario.slug)
def test_seeded_scenario_fills_every_form_with_its_own_identity(tmp_path: Path, scenario):
    answers = _scenario_answers(scenario)
    with _session() as session:
        case = _create_case(session, scenario, answers)
        upsert_intake_step(session, case.id, f"packet_scenario:{scenario.slug}", answers)
        seed_i485(session, case, answers)
        for form_key in SUPPLEMENTAL_FORM_KEYS:
            seed_supplemental_form(session, case, form_key, answers)
        session.commit()

        for form_key in QUESTIONNAIRE_FORMS:
            path = tmp_path / f"{form_key}.pdf"
            result = _generate_questionnaire_form(session, case.id, form_key, path)
            blocked = form_key in SCENARIO_BLOCKED_FORMS.get(scenario.slug, set())
            assert result.ready_for_pdf_generation is not blocked, (form_key, result.generation_status)

            widgets = read_pdf_widgets(path)
            assert_widgets_will_print(widgets)
            assert_widget_values_are_formatted(widgets)
            values = set(filled_text_values(widgets).values())
            assert {scenario.beneficiary_first_name, scenario.beneficiary_last_name} <= values, form_key
            if form_key not in {"i765", "i131", "i130a"}:
                assert scenario.petitioner_first_name in values, form_key
            own_values = {scenario.beneficiary_first_name, scenario.petitioner_first_name, BIRTH_CITY_BY_COUNTRY[scenario.beneficiary_country]}
            for sample_value in {"Sample response", "Avery", "Jordan", "Bogota"} - own_values:
                assert not any(sample_value in value for value in values), (form_key, sample_value)


def test_seeded_scenario_i864_reports_the_scenarios_own_income(tmp_path: Path):
    scenario = next(item for item in SCENARIOS if item.slug == "tx-work-only")
    answers = _scenario_answers(scenario)
    with _session() as session:
        case = _create_case(session, scenario, answers)
        upsert_intake_step(session, case.id, "scenario", answers)
        seed_supplemental_form(session, case, "i864", answers)
        session.commit()
        path = tmp_path / "i864.pdf"
        generate_form_pdf(session=session, case_id=case.id, form_key="i864", output_path=path)

    widgets = read_pdf_widgets(path)
    assert _matching_widgets(widgets, "P6_Line2_TotalIncome[0]")[0].value == str(scenario.annual_income)
    assert _matching_widgets(widgets, "P6_Line15_TotalHouseholdIncome[0]")[0].value == str(scenario.annual_income)


def test_seeded_scenario_i131_is_ready_with_a_numeric_trip_length():
    scenario = next(item for item in SCENARIOS if item.slug == "ca-full-translation")
    answers = _scenario_answers(scenario)
    with _session() as session:
        case = _create_case(session, scenario, answers)
        upsert_intake_step(session, case.id, "scenario", answers)
        seed_i485(session, case, answers)
        seed_supplemental_form(session, case, "i131", answers)
        session.commit()
        preview = build_form_fill_preview(session, case.id, "i131")

    assert preview["generation_status"] == "ready_for_user_review"


# --- The assembled packet.


@pytest.mark.parametrize("seed", PROFILE_SEEDS[:3])
def test_assembled_packet_includes_every_generated_form_with_its_values(tmp_path: Path, seed: int):
    profile = build_profile(seed)
    with _session() as session:
        case = _seed_profile_case(session, profile)
        result = assemble_packet_pdf(session=session, case_id=case.id, state_code="CA", output_dir=tmp_path)

    generated = {
        document["form_key"]: Path(document["path"])
        for document in result.included_documents
        if document["source_type"] == "generated_form"
    }
    try:
        assert set(generated) == {"g1145", "i485", "i864", "i765", "i131", "i130", "i130a"}
        for form_key, path in generated.items():
            _assert_expected(read_pdf_widgets(path), EXPECTED_BY_FORM[form_key](profile))

        # The packet is flattened so every viewer prints it the same, so its values are page text instead of fields.
        packet = PdfReader(result.output_path)
        assert not read_pdf_widgets(result.output_path)
        packet_text = "\n".join(page.extract_text() for page in packet.pages)
        for last_name in (profile["beneficiary_last_name"], profile["petitioner_last_name"], profile["parent1_last_name"]):
            assert last_name in packet_text
        assert len(packet.pages) > sum(len(PdfReader(path).pages) for path in generated.values())
    finally:
        for path in generated.values():
            path.unlink(missing_ok=True)
