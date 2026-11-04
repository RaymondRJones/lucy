"""Seeded applicant profiles for PDF regression tests.

Every attribute draws from its own pool, so a field wired to the wrong attribute shows up as a wrong
value instead of passing by coincidence. All people, identifiers, and accounts here are fictional.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import random
from typing import Any

from app.content.i485_sample import build_sample_i485_answers
from app.content.supplemental_forms import get_supplemental_form_config

PROFILE_SEEDS = tuple(range(8))
SUPPLEMENTAL_FORM_KEYS = ("i765", "i131", "i864", "i130", "i130a")

BENEFICIARY_NAMES = [
    ("Núñez", "José", "Ángel"),
    ("O'Connor", "Siobhan", ""),
    ("Nguyen-Tran", "Minh", "Thi"),
    ("Kowalski", "Zofia", "Anna"),
    ("Okafor", "Chidi", ""),
    ("Santos", "Maria Clara", "Reyes"),
    ("Haddad", "Rami", "Elias"),
    ("Ferreira", "Inês", ""),
]
PETITIONER_NAMES = [
    ("Whitfield", "Harper", "Lynn"),
    ("Delacroix", "Marcus", ""),
    ("Yamamoto", "Kenji", "Ray"),
    ("Ibrahim", "Layla", "Noor"),
    ("Bergstrom", "Erik", ""),
    ("Castellano", "Gina", "Marie"),
    ("Abernathy", "Theo", "James"),
    ("Mbeki", "Thandi", ""),
]
# country, birth city, province, postal code, street
ORIGINS = [
    ("Mexico", "Guadalajara", "Jalisco", "44100", "Avenida Vallarta 1200"),
    ("Philippines", "Cebu City", "Cebu", "6000", "12 Osmena Boulevard"),
    ("Poland", "Krakow", "Malopolskie", "30-001", "ul. Florianska 7"),
    ("Nigeria", "Enugu", "Enugu State", "400001", "5 Ogui Road"),
    ("Vietnam", "Hue", "Thua Thien", "530000", "9 Le Loi Street"),
    ("Ireland", "Galway", "Connacht", "H91 A0A0", "3 Shop Street"),
    ("Brazil", "Recife", "Pernambuco", "50000-000", "Rua da Aurora 44"),
    ("Lebanon", "Tripoli", "North Governorate", "1300", "21 Azmi Street"),
]
# street, city, state code, full state name, ZIP
US_ADDRESSES = [
    ("810 Juniper Court", "Madison", "WI", "Wisconsin", "53703"),
    ("2215 Harbor Drive", "Tampa", "FL", "Florida", "33602"),
    ("47 Quarry Lane", "Burlington", "VT", "Vermont", "05401"),
    ("1600 Canyon Road", "Santa Fe", "NM", "New Mexico", "87501"),
    ("390 Birch Hollow", "Duluth", "MN", "Minnesota", "55802"),
    ("5512 Magnolia Way", "Savannah", "GA", "Georgia", "31401"),
    ("72 Foundry Street", "Pittsburgh", "PA", "Pennsylvania", "15222"),
    ("918 Sequoia Terrace", "Eugene", "OR", "Oregon", "97401"),
    ("1341 Prairie Avenue", "Omaha", "NE", "Nebraska", "68102"),
    ("66 Lighthouse Road", "Portland", "ME", "Maine", "04101"),
]
EMPLOYERS = [
    ("Northwind Logistics", "Dispatcher"),
    ("Lakeshore Dental Group", "Hygienist"),
    ("Cobalt Software LLC", "Developer"),
    ("Riverbend Hospital", "Nurse"),
    ("Granite Peak Builders", "Estimator"),
    ("Blue Heron Bakery", "Manager"),
]
SCHOOLS = [
    ("Westfield Technical College", "Student"),
    ("Harmon State University", "Student"),
]
CLASSES_OF_ADMISSION = [
    ("B-2", "B-2 visitor"),
    ("B-1", "B-1 visitor for business"),
    ("F-1", "F-1 student"),
    ("B-2", "B-2 visitor"),
]
UNITS = [("Apt 4B", "4B"), ("Ste 210", "210"), ("Fl 3", "3"), ("", "")]
CARD_TYPES = [
    ("Visa", "4242424242424242"),
    ("Mastercard", "5555444433332222"),
    ("Discover", "6011000990139424"),
]


@dataclass(frozen=True)
class Profile:
    seed: int
    answers: dict[str, Any]
    petitioner_unit: tuple[str, str]
    beneficiary_unit: tuple[str, str]
    prior_unit: tuple[str, str]
    state_written_as_name: bool

    def __getitem__(self, key: str) -> Any:
        return self.answers[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.answers.get(key, default)


def _date_between(rng: random.Random, start: date, end: date) -> str:
    return (start + timedelta(days=rng.randrange((end - start).days))).isoformat()


def _digits(rng: random.Random, length: int) -> str:
    return "".join(rng.choice("123456789") for _ in range(length))


def _phone(rng: random.Random) -> str:
    return f"{rng.randint(201, 989)}{rng.randint(201, 989)}{rng.randint(1000, 9999)}"


def build_profile(seed: int) -> Profile:
    rng = random.Random(f"lucy-pdf-profile-{seed}")
    beneficiary_last, beneficiary_first, beneficiary_middle = BENEFICIARY_NAMES[seed % len(BENEFICIARY_NAMES)]
    petitioner_last, petitioner_first, petitioner_middle = PETITIONER_NAMES[seed % len(PETITIONER_NAMES)]
    country, birth_city, province, postal, foreign_street = ORIGINS[seed % len(ORIGINS)]
    parent_country, parent_city, *_ = ORIGINS[(seed + 3) % len(ORIGINS)]
    beneficiary_street, beneficiary_city, beneficiary_state, beneficiary_state_name, beneficiary_zip = US_ADDRESSES[
        seed % len(US_ADDRESSES)
    ]
    petitioner_street, petitioner_city, petitioner_state, _, petitioner_zip = US_ADDRESSES[(seed + 2) % len(US_ADDRESSES)]
    prior_street, prior_city, prior_state, _, prior_zip = US_ADDRESSES[(seed + 5) % len(US_ADDRESSES)]
    employer_street, employer_city, employer_state, _, employer_zip = US_ADDRESSES[(seed + 7) % len(US_ADDRESSES)]
    sponsor_employer, sponsor_occupation = EMPLOYERS[seed % len(EMPLOYERS)]
    work_name, work_role = EMPLOYERS[(seed + 3) % len(EMPLOYERS)] if seed % 2 else SCHOOLS[seed % 4 // 2]
    admission_class, current_status = CLASSES_OF_ADMISSION[seed % len(CLASSES_OF_ADMISSION)]
    beneficiary_unit = UNITS[seed % len(UNITS)]
    petitioner_unit = UNITS[(seed + 1) % len(UNITS)]
    prior_unit = UNITS[(seed + 2) % len(UNITS)]
    state_written_as_name = seed % 2 == 1

    annual_income = rng.randrange(62000, 140000, 500)
    has_a_number = seed % 3 == 0
    has_ssn = seed % 2 == 0
    beneficiary_sex = "female" if seed % 2 else "male"
    weight = rng.choice([98, 112, 135, 158, 204])
    ssn = _digits(rng, 9) if has_ssn else ""

    answers = build_sample_i485_answers()
    beneficiary_address = {
        "line1": beneficiary_street,
        "line2": beneficiary_unit[0],
        "city": beneficiary_city,
        "state": beneficiary_state,
        "zip": beneficiary_zip,
        "country": "United States",
    }
    petitioner_address = {
        "line1": petitioner_street,
        "line2": petitioner_unit[0],
        "city": petitioner_city,
        "state": petitioner_state,
        "zip": petitioner_zip,
        "country": "United States",
    }
    answers.update(
        {
            "beneficiary_last_name": beneficiary_last,
            "beneficiary_first_name": beneficiary_first,
            "beneficiary_middle_name": beneficiary_middle,
            "beneficiary_date_of_birth": _date_between(rng, date(1975, 1, 1), date(2000, 1, 1)),
            "beneficiary_sex": beneficiary_sex,
            "beneficiary_city_of_birth": birth_city,
            "beneficiary_state_province_of_birth": province,
            "beneficiary_country_of_birth": country,
            "beneficiary_country_of_citizenship": country,
            "beneficiary_has_a_number": has_a_number,
            "beneficiary_a_number": _digits(rng, 9) if has_a_number else "",
            "beneficiary_has_ssn": has_ssn,
            "beneficiary_social_security_number": ssn,
            "beneficiary_ssn": ssn,
            "beneficiary_wants_ssn": not has_ssn,
            "beneficiary_uscis_online_account_number": _digits(rng, 12) if seed % 4 == 0 else "",
            "beneficiary_passport_number": f"P{_digits(rng, 8)}",
            "beneficiary_passport_expiration": _date_between(rng, date(2028, 1, 1), date(2034, 1, 1)),
            "beneficiary_passport_country": country,
            "beneficiary_visa_number": f"V{_digits(rng, 7)}",
            "beneficiary_visa_issued_on": _date_between(rng, date(2022, 1, 1), date(2024, 1, 1)),
            "beneficiary_last_arrival_city": "Chicago",
            "beneficiary_last_arrival_state": "IL",
            "beneficiary_last_arrival_place": "Chicago, IL",
            "beneficiary_last_arrival_date": _date_between(rng, date(2024, 2, 1), date(2025, 2, 1)),
            "beneficiary_class_of_admission": admission_class,
            "beneficiary_current_immigration_status": current_status,
            "beneficiary_i94_number": f"{_digits(rng, 9)}A{rng.randint(1, 9)}",
            "beneficiary_i94_expiration": _date_between(rng, date(2027, 1, 1), date(2028, 1, 1)),
            "beneficiary_status_expires_on": _date_between(rng, date(2027, 1, 1), date(2028, 1, 1)),
            "beneficiary_current_status_expires_on": _date_between(rng, date(2027, 1, 1), date(2028, 1, 1)),
            "beneficiary_current_address": beneficiary_address,
            "beneficiary_current_address_line1": beneficiary_street,
            "beneficiary_current_address_line2": beneficiary_unit[0],
            "beneficiary_current_city": beneficiary_city,
            "beneficiary_current_state": beneficiary_state_name if state_written_as_name else beneficiary_state,
            "beneficiary_current_zip": beneficiary_zip,
            "beneficiary_current_country": "United States",
            "beneficiary_address_since": _date_between(rng, date(2025, 3, 1), date(2025, 9, 1)),
            "beneficiary_mailing_address_line1": beneficiary_street,
            "beneficiary_mailing_address_line2": beneficiary_unit[0],
            "beneficiary_mailing_city": beneficiary_city,
            "beneficiary_mailing_state": beneficiary_state_name if state_written_as_name else beneficiary_state,
            "beneficiary_mailing_zip": beneficiary_zip,
            "beneficiary_mailing_country": "United States",
            "beneficiary_prior_address_history": [
                {
                    "line1": prior_street,
                    "line2": prior_unit[0],
                    "city": prior_city,
                    "state": prior_state,
                    "zip": prior_zip,
                    "country": "United States",
                    "from": "2023-01-01",
                    "to": "2025-02-28",
                }
            ],
            "beneficiary_recent_foreign_address": {
                "line1": foreign_street,
                "city": birth_city,
                "province": province,
                "postal_code": postal,
                "country": country,
                "from": "2019-01-01",
                "to": "2022-12-31",
            },
            "beneficiary_current_employer_or_school": work_name,
            "beneficiary_current_occupation": work_role,
            "beneficiary_employment_history": [
                {
                    "activity_type": "school" if work_role == "Student" else "employment",
                    "name": work_name,
                    "occupation": work_role,
                    "line1": employer_street,
                    "city": employer_city,
                    "state": employer_state,
                    "zip": employer_zip,
                    "country": "United States",
                    "from": "2025-03-01",
                    "to": "",
                }
            ],
            "beneficiary_foreign_employer_or_school": f"Instituto de {birth_city}",
            "petitioner_ethnicity": "not_hispanic_or_latino",
            "petitioner_race": ["white"],
            "petitioner_height_feet": 5,
            "petitioner_height_inches": 10,
            "petitioner_weight_pounds": 170,
            "petitioner_eye_color": "brown",
            "petitioner_hair_color": "black",
            "petitioner_filed_prior_petition": False,
            "parent1_last_name": f"{beneficiary_last}a",
            "parent1_first_name": "Lucia",
            "parent1_middle_name": "Pilar" if seed % 2 else "",
            "parent1_name_at_birth": f"Lucia {beneficiary_last}a",
            "parent1_date_of_birth": _date_between(rng, date(1945, 1, 1), date(1960, 1, 1)),
            "parent1_sex": "female",
            "parent1_city_of_birth": parent_city,
            "parent1_country_of_birth": parent_country,
            "parent1_city_of_residence": birth_city,
            "parent1_country_of_residence": country,
            "parent2_last_name": f"{beneficiary_last}o",
            "parent2_first_name": "Tomas",
            "parent2_middle_name": "Ivan" if seed % 3 else "",
            "parent2_name_at_birth": f"Tomas {beneficiary_last}o",
            "parent2_date_of_birth": _date_between(rng, date(1940, 1, 1), date(1944, 12, 1)),
            "parent2_sex": "male",
            "parent2_city_of_birth": province,
            "parent2_country_of_birth": country,
            "parent2_city_of_residence": parent_city,
            "parent2_country_of_residence": parent_country,
            "petitioner_last_name": petitioner_last,
            "petitioner_first_name": petitioner_first,
            "petitioner_middle_name": petitioner_middle,
            "petitioner_date_of_birth": _date_between(rng, date(1970, 1, 1), date(1995, 1, 1)),
            "petitioner_sex": "male" if beneficiary_sex == "female" else "female",
            "petitioner_city_of_birth": "Boise",
            "petitioner_country_of_birth": "United States",
            "petitioner_country_of_domicile": "United States",
            "petitioner_social_security_number": _digits(rng, 9),
            "petitioner_current_address": petitioner_address,
            "petitioner_current_address_line1": petitioner_street,
            "petitioner_current_address_line2": petitioner_unit[0],
            "petitioner_current_city": petitioner_city,
            "petitioner_current_state": petitioner_state,
            "petitioner_current_zip": petitioner_zip,
            "petitioner_current_country": "United States",
            "petitioner_mailing_same_as_physical": True,
            "petitioner_physical_address_line1": petitioner_street,
            "petitioner_physical_address_line2": petitioner_unit[0],
            "petitioner_physical_city": petitioner_city,
            "petitioner_physical_state": petitioner_state,
            "petitioner_physical_zip": petitioner_zip,
            "petitioner_physical_country": "United States",
            "petitioner_physical_address_from": _date_between(rng, date(2021, 1, 1), date(2023, 1, 1)),
            "petitioner_phone": _phone(rng),
            "petitioner_mobile_phone": _phone(rng),
            "petitioner_email": f"{petitioner_first.lower()}.{seed}@example.com",
            "petitioner_current_employer": sponsor_employer,
            "petitioner_current_occupation": sponsor_occupation,
            "petitioner_current_employer_country": "United States",
            "petitioner_current_employment_from": _date_between(rng, date(2018, 1, 1), date(2021, 1, 1)),
            "petitioner_marriage_count": 1,
            "petitioner_current_marital_status": "married",
            "petitioner_spouse1_last_name": beneficiary_last,
            "petitioner_spouse1_first_name": beneficiary_first,
            "petitioner_spouse1_middle_name": beneficiary_middle,
            "beneficiary_spouse1_last_name": petitioner_last,
            "beneficiary_spouse1_first_name": petitioner_first,
            "beneficiary_spouse1_middle_name": petitioner_middle,
            "petitioner_parent1_last_name": f"{petitioner_last}son",
            "petitioner_parent1_first_name": "Ruth",
            "petitioner_parent1_date_of_birth": _date_between(rng, date(1945, 1, 1), date(1960, 1, 1)),
            "petitioner_parent1_sex": "female",
            "petitioner_parent1_country_of_birth": "United States",
            "petitioner_parent2_last_name": f"{petitioner_last}berg",
            "petitioner_parent2_first_name": "Saul",
            "petitioner_parent2_date_of_birth": _date_between(rng, date(1940, 1, 1), date(1944, 12, 1)),
            "petitioner_parent2_sex": "male",
            "petitioner_parent2_country_of_birth": "United States",
            "marriage_date": _date_between(rng, date(2025, 3, 1), date(2025, 9, 1)),
            "marriage_place_city": "Reno",
            "marriage_place_state": "NV",
            "marriage_place_country": "United States",
            "first_marriage_for_both": True,
            "relationship_spouse": True,
            "beneficiary_phone": _phone(rng),
            "beneficiary_mobile_phone": _phone(rng),
            "beneficiary_email": f"applicant.{seed}@example.org",
            "beneficiary_ethnicity": "hispanic_or_latino" if seed % 2 else "not_hispanic_or_latino",
            "beneficiary_race": [rng.choice(["white", "asian", "black"])],
            "beneficiary_race_primary": "white",
            "beneficiary_height_feet": rng.randint(4, 6),
            "beneficiary_height_inches": rng.randint(0, 11),
            "beneficiary_weight_pounds": weight,
            "beneficiary_eye_color": rng.choice(["brown", "blue", "green", "hazel"]),
            "beneficiary_hair_color": rng.choice(["black", "brown", "blond", "gray"]),
            "household_size": 2,
            "highest_education": rng.choice(["high_school", "associate", "bachelor", "master"]),
            "certifications_licenses_skills": f"{work_role} certificate\nFluent in the language of {country}",
            "public_charge_family_status": "Married; household of two",
            "annual_income": annual_income,
            "i130_filing_status": "not_filed",
            # Supplemental controls for the standard concurrent marriage path.
            "wants_i765": True,
            "wants_i131": True,
            "needs_translation": False,
            "beneficiary_ever_in_united_states": True,
            "beneficiary_ever_in_immigration_proceedings": False,
            "beneficiary_prior_petition_filed": "no",
            "beneficiary_adjustment_path": True,
            "beneficiary_adjustment_city": beneficiary_city,
            "beneficiary_adjustment_state": beneficiary_state,
            "i765_reason_for_applying": "initial_permission",
            "i765_physical_same_as_mailing": True,
            "i765_previously_filed": False,
            "i765_eligibility_category": "c9_pending_i485",
            "i765_arrested_or_convicted": False,
            "i131_application_type": "advanced_parole_i485_pending",
            "i131_physical_same_as_mailing": True,
            "i131_removal_proceedings": False,
            "i131_prior_reentry_refugee_document": False,
            "i131_prior_advance_parole": False,
            "i131_replacement_request": False,
            "i131_processing_location": "domestic_address",
            "i131_intended_departure_date": _date_between(rng, date(2027, 2, 1), date(2027, 6, 1)),
            "i131_travel_purpose": f"Visit family in {birth_city} during the pending adjustment.",
            "i131_countries_to_visit": country,
            "i131_trip_count": "one",
            "i131_expected_trip_length": rng.randint(7, 30),
            "i864_sponsor_basis": "petitioner",
            "i864_physical_same_as_mailing": True,
            "i864_only_principal_immigrant": True,
            "i864_sponsoring_family_members": False,
            "i864_total_immigrants": 1,
            "i864_sponsor_married_count": 0,
            "i864_dependent_children_count": 0,
            "i864_other_dependents_count": 0,
            "i864_prior_sponsored_immigrants_count": 0,
            "i864_household_members_combining_income_count": 0,
            "employment_status": "employed",
            "i864_household_income": annual_income,
            "i864_filed_recent_tax_return": True,
            "i864_tax_year_1": 2025,
            "i864_tax_income_1": annual_income - 1000,
            "i864_tax_year_2": 2024,
            "i864_tax_income_2": annual_income - 3000,
            "i864_tax_year_3": 2023,
            "i864_tax_income_3": annual_income - 5000,
            "i864_cash_assets": rng.randrange(4000, 30000, 250),
            "i864_total_assets": rng.randrange(30000, 90000, 250),
            "sponsor_reviewed_contract": True,
            "applicant_reviewed_certification": True,
            "g1145_last_name": beneficiary_last,
            "g1145_first_name": beneficiary_first,
            "g1145_middle_name": beneficiary_middle,
        }
    )
    answers.update(
        {
            "petitioner_a_number": "",
            "petitioner_uscis_online_account_number": _digits(rng, 12),
            "petitioner_other_last_name": f"{petitioner_last}-Hale",
            "petitioner_other_first_name": petitioner_first,
            "petitioner_mailing_in_care_of": f"{petitioner_first} {petitioner_last}",
            "beneficiary_mailing_in_care_of": f"{petitioner_first} {petitioner_last}",
            "petitioner_prior_address_line1": employer_street,
            "petitioner_prior_city": employer_city,
            "petitioner_prior_state": employer_state,
            "petitioner_prior_zip": employer_zip,
            "petitioner_prior_country": "United States",
            "petitioner_prior_address_from": "2018-01-01",
            "petitioner_prior_address_to": "2020-12-31",
            "petitioner_current_employer_address_line1": employer_street,
            "petitioner_current_employer_city": employer_city,
            "petitioner_current_employer_state": employer_state,
            "petitioner_current_employer_zip": employer_zip,
            "petitioner_prior_employer": "Cedar Ridge Outfitters",
            "petitioner_prior_employer_address_line1": prior_street,
            "petitioner_prior_employer_city": prior_city,
            "petitioner_prior_employer_state": prior_state,
            "petitioner_prior_employer_zip": prior_zip,
            "petitioner_prior_employer_country": "United States",
            "petitioner_prior_occupation": "Clerk",
            "petitioner_prior_employment_from": "2014-06-01",
            "petitioner_prior_employment_to": "2017-12-31",
            "petitioner_parent1_middle_name": "Ann",
            "petitioner_parent1_city_of_residence": "Boise",
            "petitioner_parent1_country_of_residence": "United States",
            "petitioner_parent2_middle_name": "Lee",
            "petitioner_parent2_city_of_residence": "Helena",
            "petitioner_parent2_country_of_residence": "United States",
            "petitioner_citizenship_acquired_by": "birth",
            "beneficiary_other_last_name": f"{beneficiary_last}-Vega",
            "beneficiary_other_first_name": beneficiary_first,
            "beneficiary_native_last_name": beneficiary_last,
            "beneficiary_native_first_name": beneficiary_first,
            "beneficiary_native_address_line1": foreign_street,
            "beneficiary_native_city": birth_city,
            "beneficiary_native_province": province,
            "beneficiary_native_postal_code": postal,
            "beneficiary_native_country": country,
            "beneficiary_foreign_address_line1": foreign_street,
            "beneficiary_foreign_city": birth_city,
            "beneficiary_foreign_province": province,
            "beneficiary_foreign_postal_code": postal,
            "beneficiary_foreign_country": country,
            "beneficiary_intended_us_address_line1": petitioner_street,
            "beneficiary_intended_us_city": petitioner_city,
            "beneficiary_intended_us_state": petitioner_state,
            "beneficiary_intended_us_zip": petitioner_zip,
            "beneficiary_last_shared_address_line1": petitioner_street,
            "beneficiary_last_shared_city": petitioner_city,
            "beneficiary_last_shared_state": petitioner_state,
            "beneficiary_last_shared_zip": petitioner_zip,
            "beneficiary_last_shared_country": "United States",
            "beneficiary_last_shared_address_from": "2025-09-01",
            "beneficiary_current_employer_address_line1": employer_street,
            "beneficiary_current_employer_city": employer_city,
            "beneficiary_current_employer_state": employer_state,
            "beneficiary_current_employer_zip": employer_zip,
            "beneficiary_current_employer_country": "United States",
            "beneficiary_current_employment_from": "2025-03-01",
            "beneficiary_travel_document_number": f"T{_digits(rng, 7)}",
            "i131_i485_receipt_number": f"IOE{_digits(rng, 10)}",
        }
    )
    # Odd seeds report a physical address that differs from the mailing address.
    if seed % 2:
        answers.update(
            {
                "i765_physical_same_as_mailing": False,
                "i131_physical_same_as_mailing": False,
                "beneficiary_physical_address_line1": prior_street,
                "beneficiary_physical_city": prior_city,
                "beneficiary_physical_state": prior_state,
                "beneficiary_physical_zip": prior_zip,
            }
        )
    answers["g1145_email"] = answers["beneficiary_email"]
    answers["g1145_mobile_phone"] = answers["beneficiary_mobile_phone"]
    return Profile(
        seed=seed,
        answers=answers,
        petitioner_unit=petitioner_unit,
        beneficiary_unit=beneficiary_unit,
        prior_unit=prior_unit,
        state_written_as_name=state_written_as_name,
    )


def form_answers(profile: Profile, form_key: str) -> dict[str, dict[str, Any]]:
    """Answers by questionnaire page. A required question without a profile value stays blank and fails readiness."""
    pages: dict[str, dict[str, Any]] = {}
    for page in get_supplemental_form_config(form_key)["pages"]:
        pages[page["id"]] = {
            question["id"]: profile.answers[question["id"]]
            for question in page["questions"]
            if question["id"] in profile.answers
        }
    return pages


def card_payment_payload(profile: Profile) -> dict[str, Any]:
    card_type, card_number = CARD_TYPES[profile.seed % len(CARD_TYPES)]
    return {
        "cardholder_name": f"{profile['petitioner_first_name']} {profile['petitioner_last_name']}",
        "credit_card_type": card_type,
        "credit_card_number": card_number,
        "expiration_month": str(profile.seed % 12 + 1),
        "expiration_year": str(2029 + profile.seed),
        "security_code": str(100 + profile.seed),
        "billing_address": {
            "street_1": profile["petitioner_current_address_line1"],
            "street_2": "Ste 12",
            "city": profile["petitioner_current_city"],
            "state": profile["petitioner_current_state"],
            "postal_code": profile["petitioner_current_zip"],
        },
        "daytime_phone_number": profile["petitioner_phone"],
        "email": profile["petitioner_email"],
        "authorized_amount": str(1000 + profile.seed),
        "applicant_name": f"{profile['beneficiary_first_name']} {profile['beneficiary_last_name']}",
    }


def bank_payment_payload(profile: Profile) -> dict[str, Any]:
    return {
        "account_ownership": "personal",
        "account_type": "savings" if profile.seed % 2 else "checking",
        "account_holder_name": f"{profile['petitioner_first_name']} {profile['petitioner_last_name']}",
        "business_name": "",
        "bank_name": f"{profile['petitioner_current_city']} Credit Union",
        "routing_number": "021000021",
        "account_number": f"00{profile.seed}1234567",
        "applicant_name": f"{profile['beneficiary_first_name']} {profile['beneficiary_last_name']}",
    }
