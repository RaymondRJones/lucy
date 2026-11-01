from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from pypdf import PdfReader
import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.content.supplemental_forms import (
    SUPPLEMENTAL_FORM_CONFIGS,
    all_supplemental_form_questions,
)
from app.models.entities import CaseRecord
from app.services.form_ingestion import (
    build_form_fill_preview,
    build_form_intake_projection,
    evaluate_form_answers,
    import_form_answers_from_case_data,
    save_form_page_answers,
)
from app.services.form_pdf import build_form_pdf_field_payload, generate_form_pdf, generate_form_pdf_from_answers
from app.services.i485 import save_i485_page_answers
from app.services.intake import get_merged_case_intake, upsert_intake_step


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def create_case(session: Session) -> CaseRecord:
    case = CaseRecord(case_name="Supplemental form case", workflow_type="marriage_concurrent")
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


def sample_i765_answers() -> dict[str, object]:
    return {
        "beneficiary_last_name": "Sample",
        "beneficiary_first_name": "Avery",
        "beneficiary_middle_name": "Maria",
        "i765_reason_for_applying": "initial_permission",
        "beneficiary_other_names": "",
        "beneficiary_mailing_in_care_of": "",
        "beneficiary_mailing_address_line1": "123 Sample Street",
        "beneficiary_mailing_address_line2": "Apt 4B",
        "beneficiary_mailing_city": "Oakland",
        "beneficiary_mailing_state": "CA",
        "beneficiary_mailing_zip": "94612",
        "i765_physical_same_as_mailing": True,
        "beneficiary_physical_address_line1": "",
        "beneficiary_physical_city": "",
        "beneficiary_physical_state": "",
        "beneficiary_physical_zip": "",
        "beneficiary_a_number": "",
        "beneficiary_uscis_online_account_number": "",
        "beneficiary_sex": "female",
        "beneficiary_current_marital_status": "married",
        "i765_previously_filed": False,
        "beneficiary_has_ssn": False,
        "beneficiary_social_security_number": "",
        "beneficiary_city_of_birth": "Bogota",
        "beneficiary_state_province_of_birth": "Cundinamarca",
        "beneficiary_country_of_birth": "Colombia",
        "beneficiary_country_of_citizenship": "Colombia",
        "beneficiary_date_of_birth": "1998-06-14",
        "beneficiary_i94_number": "123456789A1",
        "beneficiary_passport_number": "X1234567",
        "beneficiary_passport_country": "Colombia",
        "beneficiary_passport_expiration": "2030-08-01",
        "beneficiary_last_arrival_date": "2025-04-10",
        "beneficiary_last_arrival_place": "Miami, FL",
        "beneficiary_class_of_admission": "B-2",
        "beneficiary_current_immigration_status": "B-2 visitor",
        "i765_eligibility_category": "c9_pending_i485",
        "i765_arrested_or_convicted": False,
        "beneficiary_phone": "0000000100",
        "beneficiary_mobile_phone": "",
        "beneficiary_email": "avery.sample@example.com",
        "applicant_reviewed_certification": True,
        "interpreter_used": False,
        "preparer_used": False,
        "additional_information_needed": False,
    }


def sample_i131_answers() -> dict[str, object]:
    return {
        "i131_application_type": "advanced_parole_i485_pending",
        "i131_i485_receipt_number": "",
        "beneficiary_last_name": "Sample",
        "beneficiary_first_name": "Avery",
        "beneficiary_middle_name": "Maria",
        "beneficiary_other_names": "",
        "beneficiary_mailing_in_care_of": "Avery Sample",
        "beneficiary_mailing_address_line1": "123 Sample Street",
        "beneficiary_mailing_address_line2": "Apt 4B",
        "beneficiary_mailing_city": "Oakland",
        "beneficiary_mailing_state": "CA",
        "beneficiary_mailing_zip": "94612",
        "beneficiary_mailing_country": "United States",
        "i131_physical_same_as_mailing": True,
        "beneficiary_physical_address_line1": "",
        "beneficiary_physical_city": "",
        "beneficiary_physical_state": "",
        "beneficiary_physical_zip": "",
        "beneficiary_a_number": "",
        "beneficiary_country_of_birth": "Colombia",
        "beneficiary_country_of_citizenship": "Colombia",
        "beneficiary_sex": "female",
        "beneficiary_date_of_birth": "1998-06-14",
        "beneficiary_social_security_number": "",
        "beneficiary_uscis_online_account_number": "",
        "beneficiary_class_of_admission": "B-2",
        "beneficiary_i94_number": "123456789A1",
        "beneficiary_i94_expiration": "2026-10-10",
        "beneficiary_ethnicity": "hispanic_or_latino",
        "beneficiary_race_primary": "white",
        "beneficiary_height_feet": 5,
        "beneficiary_height_inches": 4,
        "beneficiary_weight_pounds": 135,
        "beneficiary_eye_color": "brown",
        "beneficiary_hair_color": "black",
        "i131_removal_proceedings": False,
        "i131_prior_reentry_refugee_document": False,
        "i131_prior_advance_parole": False,
        "i131_replacement_request": False,
        "i131_processing_location": "domestic_address",
        "i131_intended_departure_date": "2026-11-03",
        "i131_travel_purpose": "Visit family",
        "i131_countries_to_visit": "Colombia",
        "i131_trip_count": "multiple",
        "i131_expected_trip_length": 14,
        "beneficiary_phone": "0000000100",
        "beneficiary_mobile_phone": "",
        "beneficiary_email": "avery.sample@example.com",
        "applicant_reviewed_certification": True,
        "interpreter_used": False,
        "preparer_used": False,
        "additional_information_needed": False,
    }


def sample_i864_answers() -> dict[str, object]:
    return {
        "i864_sponsor_basis": "petitioner",
        "petitioner_last_name": "Petitioner",
        "petitioner_first_name": "Jordan",
        "petitioner_middle_name": "Lee",
        "petitioner_mailing_in_care_of": "",
        "petitioner_current_address_line1": "123 Sample Street",
        "petitioner_current_address_line2": "Apt 4B",
        "petitioner_current_city": "Oakland",
        "petitioner_current_state": "CA",
        "petitioner_current_zip": "94612",
        "i864_physical_same_as_mailing": True,
        "petitioner_country_of_domicile": "United States",
        "petitioner_date_of_birth": "1996-09-04",
        "petitioner_country_of_birth": "United States",
        "petitioner_social_security_number": "000000000",
        "petitioner_citizenship_status": "us_citizen",
        "spouse_us_military": False,
        "beneficiary_last_name": "Sample",
        "beneficiary_first_name": "Avery",
        "beneficiary_middle_name": "Maria",
        "beneficiary_mailing_address_line1": "123 Sample Street",
        "beneficiary_mailing_city": "Oakland",
        "beneficiary_mailing_state": "CA",
        "beneficiary_mailing_zip": "94612",
        "beneficiary_country_of_citizenship": "Colombia",
        "beneficiary_date_of_birth": "1998-06-14",
        "beneficiary_a_number": "",
        "beneficiary_phone": "0000000100",
        "i864_only_principal_immigrant": True,
        "i864_sponsoring_family_members": False,
        "i864_total_immigrants": 1,
        "household_size": 2,
        "i864_sponsor_married_count": 0,
        "i864_dependent_children_count": 0,
        "i864_other_dependents_count": 0,
        "i864_prior_sponsored_immigrants_count": 0,
        "i864_household_members_combining_income_count": 0,
        "employment_status": "employed",
        "petitioner_current_occupation": "Engineer",
        "petitioner_current_employer": "Sample Employer",
        "annual_income": 95000,
        "i864_household_income": 95000,
        "i864_filed_recent_tax_return": True,
        "i864_tax_year_1": 2025,
        "i864_tax_income_1": 94000,
        "i864_tax_year_2": 2024,
        "i864_tax_income_2": 91000,
        "i864_tax_year_3": 2023,
        "i864_tax_income_3": 88000,
        "i864_cash_assets": 25000,
        "i864_total_assets": 25000,
        "petitioner_phone": "0000000101",
        "petitioner_mobile_phone": "",
        "petitioner_email": "jordan.petitioner@example.com",
        "sponsor_reviewed_contract": True,
        "interpreter_used": False,
        "preparer_used": False,
        "additional_information_needed": False,
    }


def sample_i130_answers() -> dict[str, object]:
    return {
        "relationship_spouse": True,
        "first_marriage_for_both": True,
        "petitioner_a_number": "ANUMBER_SAMPLE_1",
        "petitioner_uscis_online_account_number": "123456789012",
        "petitioner_last_name": "Petitioner",
        "petitioner_first_name": "Jordan",
        "petitioner_middle_name": "Lee",
        "petitioner_other_last_name": "Former",
        "petitioner_other_first_name": "Jordy",
        "petitioner_city_of_birth": "San Jose",
        "petitioner_date_of_birth": "1996-09-04",
        "petitioner_country_of_birth": "United States",
        "petitioner_sex": "male",
        "petitioner_mailing_in_care_of": "Jordan Petitioner",
        "petitioner_current_address_line1": "222 Petitioner Road",
        "petitioner_current_address_line2": "Apt 9",
        "petitioner_current_city": "Oakland",
        "petitioner_current_state": "CA",
        "petitioner_current_zip": "94612",
        "petitioner_current_country": "United States",
        "petitioner_mailing_same_as_physical": True,
        "petitioner_physical_address_line1": "222 Petitioner Road",
        "petitioner_physical_address_line2": "Apt 9",
        "petitioner_physical_city": "Oakland",
        "petitioner_physical_state": "CA",
        "petitioner_physical_zip": "94612",
        "petitioner_physical_country": "United States",
        "petitioner_physical_address_from": "2024-01-01",
        "petitioner_prior_address_line1": "111 Prior Lane",
        "petitioner_prior_city": "Berkeley",
        "petitioner_prior_state": "CA",
        "petitioner_prior_zip": "94704",
        "petitioner_prior_country": "United States",
        "petitioner_prior_address_from": "2020-01-01",
        "petitioner_prior_address_to": "2023-12-31",
        "petitioner_social_security_number": "000000001",
        "petitioner_marriage_count": 1,
        "petitioner_current_marital_status": "married",
        "petitioner_spouse1_first_name": "Avery",
        "petitioner_spouse1_middle_name": "Maria",
        "petitioner_parent1_last_name": "Parentone",
        "petitioner_parent1_first_name": "Casey",
        "petitioner_parent1_date_of_birth": "1969-02-03",
        "petitioner_parent1_sex": "female",
        "petitioner_parent1_country_of_birth": "United States",
        "petitioner_parent1_city_of_residence": "San Jose",
        "petitioner_parent1_country_of_residence": "United States",
        "petitioner_parent2_last_name": "Parenttwo",
        "petitioner_parent2_first_name": "Morgan",
        "petitioner_parent2_date_of_birth": "1968-03-04",
        "petitioner_parent2_sex": "male",
        "petitioner_parent2_country_of_birth": "United States",
        "petitioner_parent2_city_of_residence": "San Jose",
        "petitioner_parent2_country_of_residence": "United States",
        "petitioner_citizenship_status": "us_citizen",
        "petitioner_citizenship_acquired_by": "birth",
        "petitioner_has_naturalization_certificate": False,
        "petitioner_current_employer": "Sample Employer",
        "petitioner_current_employer_address_line1": "500 Market Street",
        "petitioner_current_employer_address_line2": "Suite 12",
        "petitioner_current_employer_city": "San Francisco",
        "petitioner_current_employer_state": "CA",
        "petitioner_current_employer_zip": "94105",
        "petitioner_current_employer_country": "United States",
        "petitioner_current_occupation": "Engineer",
        "petitioner_current_employment_from": "2022-05-01",
        "petitioner_phone": "0000000101",
        "petitioner_mobile_phone": "0000000103",
        "petitioner_email": "jordan.petitioner@example.com",
        "beneficiary_a_number": "ANUMBER_SAMPLE_2",
        "beneficiary_uscis_online_account_number": "987654321098",
        "beneficiary_last_name": "Sample",
        "beneficiary_first_name": "Avery",
        "beneficiary_middle_name": "Maria",
        "beneficiary_other_last_name": "Earlier",
        "beneficiary_other_first_name": "Ava",
        "beneficiary_date_of_birth": "1998-06-14",
        "beneficiary_city_of_birth": "Bogota",
        "beneficiary_country_of_birth": "Colombia",
        "beneficiary_sex": "female",
        "beneficiary_prior_petition_filed": "no",
        "beneficiary_social_security_number": "000000000",
        "beneficiary_current_address_line1": "123 Sample Street",
        "beneficiary_current_address_line2": "Apt 4B",
        "beneficiary_current_city": "Oakland",
        "beneficiary_current_state": "CA",
        "beneficiary_current_zip": "94612",
        "beneficiary_current_country": "United States",
        "beneficiary_intended_us_address_line1": "123 Sample Street",
        "beneficiary_intended_us_address_line2": "Apt 4B",
        "beneficiary_intended_us_city": "Oakland",
        "beneficiary_intended_us_state": "CA",
        "beneficiary_intended_us_zip": "94612",
        "beneficiary_foreign_address_line1": "10 Old Road",
        "beneficiary_foreign_city": "Bogota",
        "beneficiary_foreign_province": "Cundinamarca",
        "beneficiary_foreign_postal_code": "110111",
        "beneficiary_foreign_country": "Colombia",
        "beneficiary_phone": "0000000100",
        "beneficiary_mobile_phone": "0000000102",
        "beneficiary_email": "avery.sample@example.com",
        "beneficiary_marriage_count": 1,
        "beneficiary_current_marital_status": "married",
        "beneficiary_spouse1_last_name": "Petitioner",
        "beneficiary_spouse1_first_name": "Jordan",
        "beneficiary_spouse1_middle_name": "Lee",
        "marriage_date": "2025-07-20",
        "marriage_place_city": "Oakland",
        "marriage_place_state": "CA",
        "marriage_place_country": "United States",
        "beneficiary_ever_in_united_states": True,
        "beneficiary_class_of_admission": "B-2",
        "beneficiary_i94_number": "123456789A1",
        "beneficiary_last_arrival_date": "2025-04-10",
        "beneficiary_status_expires_on": "2026-10-10",
        "beneficiary_passport_number": "X1234567",
        "beneficiary_travel_document_number": "",
        "beneficiary_passport_country": "Colombia",
        "beneficiary_passport_expiration": "2030-08-01",
        "beneficiary_current_employer_or_school": "Laney College",
        "beneficiary_current_employer_address_line1": "900 Fallon Street",
        "beneficiary_current_employer_city": "Oakland",
        "beneficiary_current_employer_state": "CA",
        "beneficiary_current_employer_zip": "94607",
        "beneficiary_current_employer_country": "United States",
        "beneficiary_current_employment_from": "2025-08-15",
        "beneficiary_ever_in_immigration_proceedings": False,
        "beneficiary_native_last_name": "Sample",
        "beneficiary_native_first_name": "Avery",
        "beneficiary_native_address_line1": "10 Old Road",
        "beneficiary_native_city": "Bogota",
        "beneficiary_native_province": "Cundinamarca",
        "beneficiary_native_postal_code": "110111",
        "beneficiary_native_country": "Colombia",
        "beneficiary_last_shared_address_line1": "123 Sample Street",
        "beneficiary_last_shared_address_line2": "Apt 4B",
        "beneficiary_last_shared_city": "Oakland",
        "beneficiary_last_shared_state": "CA",
        "beneficiary_last_shared_zip": "94612",
        "beneficiary_last_shared_country": "United States",
        "beneficiary_last_shared_address_from": "2025-08-01",
        "beneficiary_adjustment_city": "Oakland",
        "beneficiary_adjustment_state": "CA",
        "beneficiary_adjustment_path": True,
    }


def sample_i130a_answers() -> dict[str, object]:
    return {
        "beneficiary_last_name": "Sample",
        "beneficiary_first_name": "Avery",
        "beneficiary_middle_name": "Maria",
        "parent1_last_name": "Sample",
        "parent1_first_name": "Rosa",
        "parent1_middle_name": "Elena",
        "parent1_date_of_birth": "1972-03-03",
        "parent1_sex": "female",
        "parent1_city_of_birth": "Bogota",
        "parent1_country_of_birth": "Colombia",
        "parent1_city_of_residence": "Medellin",
        "parent1_country_of_residence": "Colombia",
        "parent2_last_name": "Sample",
        "parent2_first_name": "Carlos",
        "parent2_middle_name": "Luis",
        "parent2_date_of_birth": "1970-11-20",
        "parent2_sex": "male",
        "parent2_city_of_birth": "Cali",
        "parent2_country_of_birth": "Colombia",
        "parent2_city_of_residence": "Cartagena",
        "parent2_country_of_residence": "Colombia",
        "beneficiary_current_address_line1": "123 Sample Street",
        "beneficiary_current_address_line2": "Apt 4B",
        "beneficiary_current_city": "Oakland",
        "beneficiary_current_state": "CA",
        "beneficiary_current_zip": "94612",
        "beneficiary_current_country": "United States",
        "beneficiary_address_since": "2025-08-01",
        "beneficiary_prior_address_history": [
            {
                "line1": "10 Old Road",
                "city": "Bogota",
                "country": "Colombia",
                "from": "2020-01-01",
                "to": "2025-07-31",
            }
        ],
        "beneficiary_current_employer_or_school": "Laney College",
        "beneficiary_current_occupation": "Student",
        "beneficiary_employment_history": "Student from 2020-present",
        "beneficiary_current_marital_status": "married",
        "beneficiary_marriage_count": 1,
        "beneficiary_phone": "0000000100",
        "beneficiary_email": "avery.sample@example.com",
    }


def test_supplemental_questionnaires_are_source_dated():
    assert set(SUPPLEMENTAL_FORM_CONFIGS) == {"i130", "i130a", "i765", "i131", "i864"}
    for form_key, config in SUPPLEMENTAL_FORM_CONFIGS.items():
        assert config["verified_on"] in {"2026-04-28", "2026-04-29", "2026-05-01", "2026-05-09"}
        assert config["official_url"].startswith("https://www.uscis.gov/")
        assert len(config["pages"]) >= 3
        assert all(question["pdf_ref"] for question in all_supplemental_form_questions(form_key))
        assert all(question["plain_language"] for question in all_supplemental_form_questions(form_key))
        assert all(question["deep_explanation"] for question in all_supplemental_form_questions(form_key))
        teaching_sources = [question["teaching_source"] for question in all_supplemental_form_questions(form_key)]
        if form_key in {"i130", "i130a"}:
            assert all(source is None for source in teaching_sources)
        else:
            assert all(source["transcript_path"] for source in teaching_sources)
        assert not any(
            "applicant's applicant" in question["plain_language"].lower()
            for question in all_supplemental_form_questions(form_key)
        )
        assert not any(
            question["plain_language"].startswith("Enter the requested")
            for question in all_supplemental_form_questions(form_key)
        )
        additional_info_question = next(
            (
                question
                for question in all_supplemental_form_questions(form_key)
                if question["id"] == "additional_information_needed"
            ),
            None,
        )
        if additional_info_question:
            assert additional_info_question["plain_language"].startswith(f"Answer yes only if an {config['form_code']} answer")
            assert "page, part" in additional_info_question["deep_explanation"]

    i765_questions = {question["id"]: question for question in all_supplemental_form_questions("i765")}
    assert i765_questions["beneficiary_class_of_admission"]["label"] == "Immigration status at last arrival"
    assert i765_questions["beneficiary_class_of_admission"]["answer_type"] == "select"
    assert i765_questions["beneficiary_class_of_admission"]["options"][0] == {
        "value": "B-2",
        "label": "B-2 visitor",
    }
    assert i765_questions["beneficiary_current_immigration_status"]["label"] == "Current immigration status or category"
    assert i765_questions["beneficiary_current_immigration_status"]["answer_type"] == "select"
    assert {
        option["value"]
        for option in i765_questions["beneficiary_current_immigration_status"]["options"]
    } >= {"B-2 visitor", "F-1 student", "parolee", "deferred action", "no status or category"}


def test_i864_household_size_help_explains_no_double_counting():
    questions = {question["id"]: question for question in all_supplemental_form_questions("i864")}
    config = SUPPLEMENTAL_FORM_CONFIGS["i864"]

    assert questions["household_size"]["label"] == "Total I-864 household size"
    assert questions["i864_sponsor_married_count"]["label"] == "Spouse count, if not already counted"
    assert "Happy-path suggestion: enter 2" in questions["household_size"]["deep_explanation"]
    assert "Happy-path suggestion: enter 1" in questions["i864_total_immigrants"]["deep_explanation"]
    assert "Happy-path suggestion: answer yes" in questions["i864_only_principal_immigrant"]["deep_explanation"]
    assert "Happy-path suggestion: answer no" in questions["i864_sponsoring_family_members"]["deep_explanation"]
    assert "Usually enter 0" in questions["i864_sponsor_married_count"]["plain_language"]
    assert "Happy-path suggestion: enter 0" in questions["i864_sponsor_married_count"]["deep_explanation"]
    assert "not already counted" in questions["i864_dependent_children_count"]["plain_language"]
    assert "Happy-path suggestion: enter 0" in questions["i864_dependent_children_count"]["deep_explanation"]
    assert "federal tax return" in questions["i864_other_dependents_count"]["plain_language"]
    assert "Happy-path suggestion: enter 0" in questions["i864_other_dependents_count"]["deep_explanation"]
    assert "still financially responsible" in questions["i864_prior_sponsored_immigrants_count"]["plain_language"]
    assert "Happy-path suggestion: enter 0" in questions["i864_prior_sponsored_immigrants_count"]["deep_explanation"]
    assert "I-864A" in questions["i864_household_members_combining_income_count"]["plain_language"]
    assert "Happy-path suggestion: enter 0" in questions["i864_household_members_combining_income_count"]["deep_explanation"]
    assert "not the employer name" in questions["petitioner_current_occupation"]["plain_language"]
    assert "not the job title" in questions["petitioner_current_employer"]["plain_language"]
    assert any(
        source["url"].endswith("/i-864instr.pdf") and source["verified_on"] == "2026-05-02"
        for source in config["sources"]
    )


def test_supplemental_evaluator_flags_outside_niche_answers():
    i765_evaluation = evaluate_form_answers(
        "i765",
        {
            **sample_i765_answers(),
            "i765_eligibility_category": "other",
            "i765_arrested_or_convicted": True,
        },
    )
    i864_evaluation = evaluate_form_answers(
        "i864",
        {
            **sample_i864_answers(),
            "i864_sponsor_basis": "joint_sponsor",
            "petitioner_citizenship_status": "lpr",
        },
    )
    i131_evaluation = evaluate_form_answers(
        "i131",
        {
            **sample_i131_answers(),
            "i131_application_type": "other",
            "i131_removal_proceedings": True,
        },
    )

    assert i765_evaluation["readiness"] == "needs_professional_review"
    assert {flag["code"] for flag in i765_evaluation["flags"]} >= {"i765_non_c9_category", "criminal_history"}
    assert i131_evaluation["readiness"] == "outside_standard_niche"
    assert {flag["code"] for flag in i131_evaluation["flags"]} >= {
        "i131_not_i485_advance_parole",
        "i131_removal_proceedings",
    }
    assert i864_evaluation["readiness"] == "needs_professional_review"
    assert {flag["code"] for flag in i864_evaluation["flags"]} >= {
        "i864_joint_or_substitute_sponsor",
        "outside_niche_spouse_not_us_citizen",
    }


def test_i131_expected_trip_length_must_be_days():
    evaluation = evaluate_form_answers(
        "i131",
        {**sample_i131_answers(), "i131_expected_trip_length": "2 weeks"},
    )

    assert evaluation["readiness"] == "needs_professional_review"
    assert "i131_expected_trip_length_not_days" in {flag["code"] for flag in evaluation["flags"]}


def test_supplemental_projection_maps_reviewed_fields_only():
    projection = build_form_intake_projection(
        "i765",
        {
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Sample",
            "i765_eligibility_category": "c9_pending_i485",
            "i765_arrested_or_convicted": False,
        },
    )

    assert projection["beneficiary_first_name"] == "Avery"
    assert projection["beneficiary_last_name"] == "Sample"
    assert projection["wants_i765"] is True
    assert projection["criminal_history"] is False

    i131_projection = build_form_intake_projection(
        "i131",
        {
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Sample",
            "i131_application_type": "advanced_parole_i485_pending",
            "beneficiary_social_security_number": "000000000",
            "i131_travel_purpose": "Visit family abroad while the I-485 is pending.",
        },
    )

    assert i131_projection["beneficiary_first_name"] == "Avery"
    assert i131_projection["beneficiary_last_name"] == "Sample"
    assert i131_projection["wants_i131"] is True
    assert i131_projection["beneficiary_ssn"] == "000000000"
    assert i131_projection["i131_travel_purpose"] == "Visit family abroad while the I-485 is pending."


def test_supplemental_page_save_stores_isolated_answers_and_projection():
    session = make_session()
    case = create_case(session)

    state = save_form_page_answers(
        session,
        case.id,
        "i864",
        "i864_page_01_basis_sponsor",
        {
            "i864_sponsor_basis": "petitioner",
            "petitioner_first_name": "Jordan",
            "petitioner_last_name": "Petitioner",
        },
        {"petitioner_first_name": True},
    )
    session.commit()

    merged = get_merged_case_intake(session, case.id)
    assert state["answers"]["petitioner_first_name"] == "Jordan"
    assert state["answer_sources"]["petitioner_first_name"]["source_type"] == "user"
    assert state["manual_flags"]["petitioner_first_name"] is True
    assert "i864_page_01_basis_sponsor" in state["saved_pages"]
    assert merged["petitioner_first_name"] == "Jordan"
    assert "answers" not in merged

    updated_state = save_form_page_answers(
        session,
        case.id,
        "i864",
        "i864_page_01_basis_sponsor",
        state["answers"],
        {},
    )
    assert "petitioner_first_name" not in updated_state["manual_flags"]


def test_supplemental_import_from_case_data_prefills_i765_and_preserves_user_answers():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Sample",
            "beneficiary_city_of_birth": "Manizales",
            "beneficiary_country_of_birth": "Colombia",
            "beneficiary_recent_foreign_address": {
                "line1": "Carrera 25 # 65 - 110",
                "city": "Manizales",
                "province": "Caldas",
                "postal_code": "170004",
                "country": "Colombia",
            },
            "beneficiary_current_address_line1": "123 Sample Street",
            "beneficiary_current_city": "Oakland",
            "beneficiary_current_state": "CA",
            "beneficiary_current_zip": "94612",
            "beneficiary_last_arrival_city": "Miami",
            "beneficiary_last_arrival_state": "FL",
            "beneficiary_passport_number": "X1234567",
            "beneficiary_passport_country": "Colombia",
            "beneficiary_passport_expiration": "2030-08-01",
            "beneficiary_last_arrival_date": "2025-04-10",
            "beneficiary_class_of_admission": "B-2",
            "beneficiary_current_immigration_status": "B-2 visitor",
            "i485_family_category": "spouse_us_citizen",
            "wants_i765": True,
        },
    )
    save_form_page_answers(
        session,
        case.id,
        "i765",
        "i765_page_01_identity",
        {"beneficiary_first_name": "User Confirmed"},
    )
    session.commit()

    result = import_form_answers_from_case_data(session, case.id, "i765")

    answers = result["state"]["answers"]
    assert answers["beneficiary_first_name"] == "User Confirmed"
    assert answers["beneficiary_last_name"] == "Sample"
    assert answers["beneficiary_state_province_of_birth"] == "Caldas"
    assert answers["i765_reason_for_applying"] == "initial_permission"
    assert answers["i765_eligibility_category"] == "c9_pending_i485"
    assert answers["beneficiary_last_arrival_place"] == "Miami, FL"
    assert result["skipped_count"] == 1
    assert result["state"]["answer_sources"]["i765_eligibility_category"]["source_type"] == "case_intake"


def test_i765_pdf_generation_prefills_birth_province_from_i485_recent_foreign_address(tmp_path: Path):
    session = make_session()
    case = create_case(session)
    save_i485_page_answers(
        session,
        case.id,
        "page_01_identity",
        {
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Sample",
            "beneficiary_city_of_birth": "Manizales",
            "beneficiary_country_of_birth": "Colombia",
            "beneficiary_recent_foreign_address": {
                "line1": "Carrera 25 # 65 - 110",
                "city": "Manizales",
                "province": "Caldas",
                "postal_code": "170004",
                "country": "Colombia",
            },
        },
    )
    session.commit()

    result = generate_form_pdf(
        session=session,
        case_id=case.id,
        form_key="i765",
        output_dir=tmp_path,
        allow_incomplete=True,
    )

    reader = PdfReader(result.output_path)
    for page in reader.pages:
        for annotation_ref in page.get("/Annots") or []:
            annotation = annotation_ref.get_object()
            if str(annotation.get("/T") or "") == "Line18b_CityTownOfBirth[0]":
                assert annotation.get("/V") == "Caldas"
                return
    raise AssertionError("Expected generated I-765 to include state/province of birth")


def test_supplemental_import_from_case_data_prefills_i864_standard_fields():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {
            "petitioner_first_name": "Jordan",
            "petitioner_last_name": "Petitioner",
            "petitioner_citizenship_status": "us_citizen",
            "petitioner_country_of_birth": "US",
            "petitioner_current_address": {
                "line1": "123 Sample Street",
                "line2": "Apt 4B",
                "city": "Oakland",
                "state": "CA",
                "zip": "94612",
            },
            "annual_income": 95000,
            "employment_status": "employed",
            "petitioner_current_occupation": "Engineer",
            "petitioner_current_employer": "Sample Employer",
            "children_count": 0,
            "household_size": 2,
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Sample",
        },
    )
    session.commit()

    result = import_form_answers_from_case_data(session, case.id, "i864")

    answers = result["state"]["answers"]
    assert answers["i864_sponsor_basis"] == "petitioner"
    assert answers["petitioner_first_name"] == "Jordan"
    assert answers["petitioner_current_address_line1"] == "123 Sample Street"
    assert answers["petitioner_country_of_domicile"] == "United States"
    assert answers["i864_total_immigrants"] == 1
    assert answers["i864_sponsor_married_count"] == 0
    assert answers["i864_dependent_children_count"] == 0
    assert answers["i864_other_dependents_count"] == 0
    assert answers["i864_prior_sponsored_immigrants_count"] == 0
    assert answers["i864_household_members_combining_income_count"] == 0
    assert answers["petitioner_current_occupation"] == "Engineer"
    assert answers["petitioner_current_employer"] == "Sample Employer"
    assert answers["i864_household_income"] == 95000
    assert result["imported_count"] >= 10


def test_supplemental_import_from_case_data_prefills_i131_standard_fields():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Sample",
            "beneficiary_current_address_line1": "123 Sample Street",
            "beneficiary_current_address_city": "Oakland",
            "beneficiary_current_address_state": "CA",
            "beneficiary_current_address_postal_code": "94612",
            "beneficiary_date_of_birth": "1998-06-14",
            "beneficiary_country_of_birth": "Colombia",
            "beneficiary_country_of_citizenship": "Colombia",
            "beneficiary_sex": "female",
            "beneficiary_ssn": "000000000",
            "beneficiary_class_of_admission": "B-2",
            "beneficiary_i94_number": "123456789A1",
            "beneficiary_current_status_expires_on": "2026-10-10",
            "beneficiary_ethnicity": "not_hispanic_or_latino",
            "beneficiary_race": ["white"],
            "beneficiary_height_feet": 5,
            "beneficiary_height_inches": 4,
            "beneficiary_weight_pounds": 135,
            "beneficiary_eye_color": "brown",
            "beneficiary_hair_color": "black",
            "wants_i131": True,
        },
    )
    session.commit()

    result = import_form_answers_from_case_data(session, case.id, "i131")

    answers = result["state"]["answers"]
    assert answers["beneficiary_first_name"] == "Avery"
    assert answers["beneficiary_last_name"] == "Sample"
    assert answers["i131_application_type"] == "advanced_parole_i485_pending"
    assert answers["beneficiary_mailing_address_line1"] == "123 Sample Street"
    assert answers["beneficiary_mailing_city"] == "Oakland"
    assert answers["beneficiary_mailing_state"] == "CA"
    assert answers["beneficiary_mailing_zip"] == "94612"
    assert answers["i131_physical_same_as_mailing"] is True
    assert answers["beneficiary_social_security_number"] == "000000000"
    assert answers["beneficiary_i94_expiration"] == "2026-10-10"
    assert answers["beneficiary_race_primary"] == "white"
    assert answers["beneficiary_weight_pounds"] == 135
    assert answers["beneficiary_eye_color"] == "brown"
    assert result["state"]["answer_sources"]["i131_application_type"]["source_type"] == "case_intake"


def test_supplemental_import_from_case_data_prefills_i130_family_branch_fields():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {
            "relationship_spouse": True,
            "petitioner_a_number": "ANUMBER_SAMPLE_1",
            "petitioner_uscis_online_account_number": "123456789012",
            "petitioner_first_name": "Jordan",
            "petitioner_last_name": "Petitioner",
            "petitioner_middle_name": "Lee",
            "petitioner_city_of_birth": "San Jose",
            "petitioner_date_of_birth": "1996-09-04",
            "petitioner_country_of_birth": "United States",
            "petitioner_sex": "male",
            "petitioner_citizenship_status": "us_citizen",
            "petitioner_current_address": {
                "line1": "222 Petitioner Road",
                "line2": "Apt 9",
                "city": "Oakland",
                "state": "CA",
                "zip": "94612",
                "country": "United States",
            },
            "petitioner_social_security_number": "000000001",
            "petitioner_current_employer": "Sample Employer",
            "petitioner_current_occupation": "Engineer",
            "petitioner_phone": "0000000101",
            "petitioner_email": "jordan.petitioner@example.com",
            "beneficiary_a_number": "ANUMBER_SAMPLE_2",
            "beneficiary_uscis_online_account_number": "987654321098",
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Sample",
            "beneficiary_middle_name": "Maria",
            "beneficiary_date_of_birth": "1998-06-14",
            "beneficiary_sex": "female",
            "beneficiary_city_of_birth": "Bogota",
            "beneficiary_country_of_birth": "Colombia",
            "beneficiary_social_security_number": "000000000",
            "beneficiary_class_of_admission": "B-2",
            "beneficiary_i94_number": "123456789A1",
            "beneficiary_last_arrival_date": "2025-04-10",
            "beneficiary_status_expires_on": "2026-10-10",
            "beneficiary_passport_number": "X1234567",
            "beneficiary_passport_country": "Colombia",
            "beneficiary_passport_expiration": "2030-08-01",
            "beneficiary_current_address_line1": "123 Sample Street",
            "beneficiary_current_address_line2": "Apt 4B",
            "beneficiary_current_address_city": "Oakland",
            "beneficiary_current_address_state": "CA",
            "beneficiary_current_address_postal_code": "94612",
            "beneficiary_location": "usa",
            "beneficiary_phone": "0000000100",
            "beneficiary_mobile_phone": "0000000102",
            "beneficiary_email": "avery.sample@example.com",
            "beneficiary_current_employer_or_school": "Laney College",
            "marriage_date": "2025-07-20",
            "marriage_place_city": "Oakland",
            "marriage_place_state": "CA",
            "marriage_place_country": "United States",
            "first_marriage_for_both": True,
        },
    )
    session.commit()

    result = import_form_answers_from_case_data(session, case.id, "i130")

    answers = result["state"]["answers"]
    assert answers["relationship_spouse"] is True
    assert answers["beneficiary_adjustment_path"] is True
    assert answers["beneficiary_ever_in_united_states"] is True
    assert answers["beneficiary_marriage_count"] == 1
    assert answers["petitioner_marriage_count"] == 1
    assert answers["petitioner_current_marital_status"] == "married"
    assert answers["petitioner_citizenship_status"] == "us_citizen"
    assert answers["petitioner_a_number"] == "ANUMBER_SAMPLE_1"
    assert answers["petitioner_sex"] == "male"
    assert answers["petitioner_current_address_line1"] == "222 Petitioner Road"
    assert answers["petitioner_current_address_line2"] == "Apt 9"
    assert answers["petitioner_current_city"] == "Oakland"
    assert answers["petitioner_social_security_number"] == "000000001"
    assert answers["petitioner_current_employer"] == "Sample Employer"
    assert answers["petitioner_spouse1_first_name"] == "Avery"
    assert answers["petitioner_phone"] == "0000000101"
    assert answers["beneficiary_a_number"] == "ANUMBER_SAMPLE_2"
    assert answers["beneficiary_uscis_online_account_number"] == "987654321098"
    assert answers["beneficiary_sex"] == "female"
    assert answers["beneficiary_current_city"] == "Oakland"
    assert answers["beneficiary_current_zip"] == "94612"
    assert answers["beneficiary_current_country"] == "United States"
    assert answers["beneficiary_social_security_number"] == "000000000"
    assert answers["beneficiary_i94_number"] == "123456789A1"
    assert answers["beneficiary_passport_number"] == "X1234567"
    assert answers["beneficiary_spouse1_first_name"] == "Jordan"
    assert answers["beneficiary_current_employer_or_school"] == "Laney College"
    assert answers["beneficiary_phone"] == "0000000100"
    assert answers["beneficiary_email"] == "avery.sample@example.com"
    assert result["state"]["answer_sources"]["petitioner_current_city"]["source_type"] == "case_intake"


def test_supplemental_import_from_case_data_prefills_i130a_spouse_fields():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Sample",
            "beneficiary_middle_name": "Maria",
            "relationship_spouse": True,
            "parent1_first_name": "Rosa",
            "parent1_date_of_birth": "1972-03-03",
            "parent2_country_of_birth": "Colombia",
            "beneficiary_location": "usa",
            "beneficiary_current_address": {
                "line1": "123 Sample Street",
                "line2": "Apt 4B",
                "city": "Oakland",
                "state": "CA",
                "zip": "94612",
                "country": "United States",
            },
            "beneficiary_current_address_since": "2025-08-01",
            "beneficiary_prior_address_history": [
                {
                    "line1": "10 Old Road",
                    "city": "Bogota",
                    "country": "Colombia",
                    "from": "2020-01-01",
                    "to": "2025-07-31",
                }
            ],
            "beneficiary_current_employer_or_school": "Laney College",
            "beneficiary_current_occupation": "Student",
            "beneficiary_employment_history": "Student from 2020-present",
            "first_marriage_for_both": True,
            "beneficiary_phone": "0000000100",
            "beneficiary_email": "avery.sample@example.com",
        },
    )
    session.commit()

    result = import_form_answers_from_case_data(session, case.id, "i130a")

    answers = result["state"]["answers"]
    assert answers["beneficiary_first_name"] == "Avery"
    assert answers["parent1_first_name"] == "Rosa"
    assert answers["parent1_date_of_birth"] == "1972-03-03"
    assert answers["parent2_country_of_birth"] == "Colombia"
    assert answers["beneficiary_current_address_line1"] == "123 Sample Street"
    assert answers["beneficiary_current_address_line2"] == "Apt 4B"
    assert answers["beneficiary_current_city"] == "Oakland"
    assert answers["beneficiary_current_zip"] == "94612"
    assert answers["beneficiary_current_country"] == "United States"
    assert answers["beneficiary_address_since"] == "2025-08-01"
    assert answers["beneficiary_marriage_count"] == 1
    assert answers["beneficiary_current_marital_status"] == "married"
    assert answers["beneficiary_current_employer_or_school"] == "Laney College"
    assert answers["beneficiary_phone"] == "0000000100"
    assert result["state"]["answer_sources"]["beneficiary_current_city"]["source_type"] == "case_intake"


def test_supplemental_pdf_payload_maps_known_answers():
    i765_payload = build_form_pdf_field_payload("i765", sample_i765_answers())
    i131_payload = build_form_pdf_field_payload("i131", sample_i131_answers())
    i864_payload = build_form_pdf_field_payload("i864", sample_i864_answers())
    i130_payload = build_form_pdf_field_payload("i130", sample_i130_answers())
    i130a_payload = build_form_pdf_field_payload("i130a", sample_i130a_answers())

    assert i765_payload.text_values["Line1a_FamilyName[0]"] == "Sample"
    assert i765_payload.text_values["Line19_DOB[0]"] == "06/14/1998"
    assert i765_payload.text_values["Line18b_CityTownOfBirth[0]"] == "Cundinamarca"
    assert i765_payload.text_values["Line23_StatusLastEntry[0]"] == "B-2 visitor"
    assert i765_payload.text_values["Line24_CurrentStatus[0]"] == "B-2 visitor"
    assert i765_payload.text_values["section_1[0]"] == "c"
    i765_visitor_payload = build_form_pdf_field_payload(
        "i765",
        {
            **sample_i765_answers(),
            "beneficiary_class_of_admission": "B2",
            "beneficiary_current_immigration_status": "VISITOR",
        },
    )
    assert i765_visitor_payload.text_values["Line23_StatusLastEntry[0]"] == "B-2 visitor"
    assert i765_visitor_payload.text_values["Line24_CurrentStatus[0]"] == "B-2 visitor"
    i765_non_code_status_payload = build_form_pdf_field_payload(
        "i765",
        {
            **sample_i765_answers(),
            "beneficiary_class_of_admission": "parolee",
            "beneficiary_current_immigration_status": "no status or category",
        },
    )
    assert i765_non_code_status_payload.text_values["Line23_StatusLastEntry[0]"] == "parolee"
    assert i765_non_code_status_payload.text_values["Line24_CurrentStatus[0]"] == "no status or category"
    assert build_form_pdf_field_payload(
        "i765",
        {**sample_i765_answers(), "beneficiary_phone": "0000001234"},
    ).text_values["Pt3Line3_DaytimePhoneNumber1[0]"] == "0000001234"
    assert build_form_pdf_field_payload(
        "i765",
        {**sample_i765_answers(), "beneficiary_mailing_state": "CAlifornia"},
    ).text_values["Pt2Line5_State[0]"] == "CA"
    assert i765_payload.checkbox_values["Part1_Checkbox[0]"] == "/1"
    assert i765_payload.checkbox_values["PtLine29_YesNo[1]"] == "/N"

    assert i131_payload.text_values["form1[0].P4[0].Part2_Line1_FamilyName[0]"] == "Sample"
    assert i131_payload.text_values["Part2_Line9_DateOfBirth[0]"] == "06/14/1998"
    assert i131_payload.text_values["P3_Line4_Pound1[0]"] == "1"
    assert i131_payload.text_values["P3_Line4_Pound2[0]"] == "3"
    assert i131_payload.text_values["P3_Line4_Pound3[0]"] == "5"
    assert i131_payload.text_values["P7_Line1_DateOfDeparture[0]"] == "11/03/2026"
    assert i131_payload.text_values["P7_Line5_ExpectedLengthTrip[0]"] == "14"
    lightweight_i131_payload = build_form_pdf_field_payload(
        "i131",
        {**sample_i131_answers(), "beneficiary_weight_pounds": "98"},
    )
    assert lightweight_i131_payload.text_values["P3_Line4_Pound1[0]"] == "0"
    assert lightweight_i131_payload.text_values["P3_Line4_Pound2[0]"] == "9"
    assert lightweight_i131_payload.text_values["P3_Line4_Pound3[0]"] == "8"
    assert build_form_pdf_field_payload(
        "i131",
        {**sample_i131_answers(), "beneficiary_class_of_admission": "B2"},
    ).text_values["Part2_Line12_ClassofAdmission[0]"] == "B-2"
    assert build_form_pdf_field_payload(
        "i131",
        {**sample_i131_answers(), "i131_expected_trip_length": "2 weeks"},
    ).text_values["P7_Line5_ExpectedLengthTrip[0]"] == ""
    assert i131_payload.checkbox_values["form1[0].P1[0].CB_AppType[4]"] == "/5"
    assert i131_payload.checkbox_values["P7_Line4_CB[1]"] == "/M"

    assert i864_payload.text_values["P4_Line1a_FamilyName[0]"] == "Petitioner"
    assert i864_payload.text_values["P4_Line6_DateOfBirth[0]"] == "09/04/1996"
    assert i864_payload.text_values["P5_Line2_Yourself[0]"] == "1"
    assert i864_payload.text_values["P5_Line3_Married[0]"] == "0"
    assert i864_payload.text_values["P5_Line4_DependentChildren[0]"] == "0"
    assert i864_payload.text_values["P5_Line5_OtherDependents[0]"] == "0"
    assert i864_payload.text_values["P5_Line6_Sponsors[0]"] == "0"
    assert i864_payload.text_values["P5_Line7_SameResidence[0]"] == "0"
    assert i864_payload.text_values["P6_Line1a_NameofEmployer[0]"] == "Engineer"
    assert i864_payload.text_values["P6_Line1a1_NameofEmployer[0]"] == "Sample Employer"
    assert i864_payload.text_values["P6_Line2_TotalIncome[0]"] == "95000"
    assert build_form_pdf_field_payload(
        "i864",
        {
            key: value
            for key, value in sample_i864_answers().items()
            if key
            not in {
                "i864_sponsor_married_count",
                "i864_dependent_children_count",
                "i864_other_dependents_count",
                "i864_prior_sponsored_immigrants_count",
                "i864_household_members_combining_income_count",
            }
        },
    ).text_values["P5_Line7_SameResidence[0]"] == "0"
    assert i864_payload.checkbox_values["P1_Line1a-f_CB[0]"] == "/1A"
    assert i864_payload.checkbox_values["P6_Line18a_Checkbox[0]"] == "/Y"

    assert i130_payload.text_values["Pt2Line1_AlienNumber[0]"] == "ANUMBER_SAMPLE_1"
    assert i130_payload.text_values["Pt2Line2_USCISOnlineActNumber[0]"] == "123456789012"
    assert i130_payload.text_values["Pt2Line4b_GivenName[0]"] == "Jordan"
    assert i130_payload.text_values["Pt2Line5a_FamilyName[0]"] == "Former"
    assert i130_payload.text_values["Pt2Line10_StreetNumberName[0]"] == "222 Petitioner Road"
    assert i130_payload.text_values["Pt2Line10_InCareofName[0]"] == "Jordan Petitioner"
    assert i130_payload.text_values["Pt2Line11_SSN[0]"] == "000000001"
    assert i130_payload.text_values["Pt2Line12_StreetNumberName[0]"] == "222 Petitioner Road"
    assert i130_payload.text_values["Pt2Line13a_DateFrom[0]"] == "01/01/2024"
    assert i130_payload.text_values["Pt2Line15b_DateTo[0]"] == "12/31/2023"
    assert i130_payload.text_values["Pt2Line16_NumberofMarriages[0]"] == "1"
    assert i130_payload.text_values["Pt2Line20b_GivenName[0]"] == "Avery"
    assert i130_payload.text_values["Pt2Line24_GivenName[0]"] == "Casey"
    assert i130_payload.text_values["Pt2Line40_EmployerOrCompName[0]"] == "Sample Employer"
    assert i130_payload.text_values["Pt2Line42_Occupation[0]"] == "Engineer"
    assert i130_payload.text_values["Pt2Line43a_DateFrom[0]"] == "05/01/2022"
    assert i130_payload.text_values["Pt2Line19a_CityTown[0]"] == "Oakland"
    assert i130_payload.text_values["Pt4Line1_AlienNumber[0]"] == "ANUMBER_SAMPLE_2"
    assert i130_payload.text_values["Pt4Line2_USCISOnlineActNumber[0]"] == "987654321098"
    assert i130_payload.text_values["Pt4Line4b_GivenName[0]"] == "Avery"
    assert i130_payload.text_values["P4Line5a_FamilyName[0]"] == "Earlier"
    assert i130_payload.text_values["Pt4Line3_SSN[0]"] == "000000000"
    assert i130_payload.text_values["Pt4Line16_EmailAddress[0]"] == "avery.sample@example.com"
    assert i130_payload.text_values["Pt4Line16a_FamilyName[0]"] == "Petitioner"
    assert i130_payload.text_values["Pt4Line21b_ArrivalDeparture[0]"] == "123456789A1"
    assert i130_payload.text_values["Pt4Line21c_DateOfArrival[0]"] == "04/10/2025"
    assert i130_payload.text_values["Pt4Line22_PassportNumber[0]"] == "X1234567"
    assert i130_payload.text_values["Pt4Line26_NameOfCompany[0]"] == "Laney College"
    assert i130_payload.text_values["Pt4Line55a_FamilyName[0]"] == "Sample"
    assert i130_payload.text_values["Pt4Line56_StreetNumberName[0]"] == "10 Old Road"
    assert i130_payload.text_values["Pt4Line57_StreetNumberName[0]"] == "123 Sample Street"
    assert i130_payload.text_values["Pt4Line58a_DateFrom[0]"] == "08/01/2025"
    assert i130_payload.text_values["Pt4Line60a_CityOrTown[0]"] == "Oakland"
    assert i130_payload.checkbox_values["Pt1Line1_Spouse[0]"] == "/Y"
    assert i130_payload.checkbox_values["Pt2Line9_Male[0]"] == "/Y"
    assert i130_payload.checkbox_values["Pt2Line11_Yes[0]"] == "/Y"
    assert i130_payload.checkbox_values["Pt2Line17_Married[0]"] == "/Y"
    assert i130_payload.checkbox_values["Pt2Line23a_checkbox[0]"] == "/Y"
    assert i130_payload.checkbox_values["Pt2Line36_No[0]"] == "/N"
    assert i130_payload.checkbox_values["Pt4Line9_Female[0]"] == "/Y"
    assert i130_payload.checkbox_values["Pt4Line10_No[0]"] == "/N"
    assert i130_payload.checkbox_values["Pt4Line20_Yes[0]"] == "/Y"
    assert i130_payload.checkbox_values["Pt4Line28_No[0]"] == "/Y"
    assert i130_payload.text_values["Pt2Line10_AptSteFlrNumber[0]"] == "9"
    assert i130a_payload.text_values["Pt1Line3b_GivenName[0]"] == "Avery"
    assert i130a_payload.text_values["Pt1Line11_DateofBirth[0]"] == "03/03/1972"
    assert i130a_payload.text_values["Pt1Line12CityTownOfBirth[0]"] == "Bogota"
    assert i130a_payload.text_values["Pt1Line15_CountryofResidence[0]"] == "Colombia"
    assert i130a_payload.text_values["Pt2Line1_EmployerOrCompName[0]"] == "Laney College"
    assert i130a_payload.checkbox_values["Pt1Line12_Female[0]"] == "/Y"


def test_i131_generated_pdf_fills_weight_digit_fields(tmp_path):
    template_path = Path("blank-immigration-documents/i-131.pdf")
    if not template_path.exists():
        pytest.skip("Local editable i131 template is not present.")

    output_path = tmp_path / "i131-output.pdf"
    generate_form_pdf_from_answers(
        case_id=uuid4(),
        form_key="i131",
        answers=sample_i131_answers(),
        template_path=template_path,
        output_path=output_path,
        allow_incomplete=False,
        preview={
            "generation_status": "ready_for_user_review",
            "ready_for_pdf_generation": True,
            "missing_required_count": 0,
            "blocking_flag_count": 0,
            "outside_niche_flag_count": 0,
            "low_confidence_count": 0,
        },
    )

    fields = PdfReader(output_path).get_fields() or {}

    def field_value(short_name: str) -> str:
        for field in fields.values():
            if field.get("/T") == short_name:
                return str(field.get("/V") or "")
        return ""

    assert field_value("P3_Line4_Pound1[0]") == "1"
    assert field_value("P3_Line4_Pound2[0]") == "3"
    assert field_value("P3_Line4_Pound3[0]") == "5"


def test_i131_pdf_generation_uses_case_weight_when_form_answer_is_missing(tmp_path):
    template_path = Path("blank-immigration-documents/i-131.pdf")
    if not template_path.exists():
        pytest.skip("Local editable i131 template is not present.")

    session = make_session()
    case = create_case(session)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {
            "beneficiary_weight_pounds": 160,
        },
    )
    session.commit()

    output_path = tmp_path / "i131-output.pdf"
    generate_form_pdf(
        session=session,
        case_id=case.id,
        form_key="i131",
        template_path=template_path,
        output_path=output_path,
        allow_incomplete=True,
    )

    fields = PdfReader(output_path).get_fields() or {}

    def field_value(short_name: str) -> str:
        for field in fields.values():
            if field.get("/T") == short_name:
                return str(field.get("/V") or "")
        return ""

    assert field_value("P3_Line4_Pound1[0]") == "1"
    assert field_value("P3_Line4_Pound2[0]") == "6"
    assert field_value("P3_Line4_Pound3[0]") == "0"


def test_i864_generated_pdf_fills_household_zeroes_and_employment_fields(tmp_path):
    template_path = Path("blank-immigration-documents/i-864.pdf")
    if not template_path.exists():
        pytest.skip("Local editable i864 template is not present.")

    output_path = tmp_path / "i864-output.pdf"
    generate_form_pdf_from_answers(
        case_id=uuid4(),
        form_key="i864",
        answers=sample_i864_answers(),
        template_path=template_path,
        output_path=output_path,
        allow_incomplete=False,
        preview={
            "generation_status": "ready_for_user_review",
            "ready_for_pdf_generation": True,
            "missing_required_count": 0,
            "blocking_flag_count": 0,
            "outside_niche_flag_count": 0,
            "low_confidence_count": 0,
        },
    )

    fields = PdfReader(output_path).get_fields() or {}

    def field_value(short_name: str) -> str:
        for field in fields.values():
            if field.get("/T") == short_name:
                return str(field.get("/V") or "")
        return ""

    assert field_value("P5_Line2_Yourself[0]") == "1"
    assert field_value("P5_Line3_Married[0]") == "0"
    assert field_value("P5_Line4_DependentChildren[0]") == "0"
    assert field_value("P5_Line5_OtherDependents[0]") == "0"
    assert field_value("P5_Line6_Sponsors[0]") == "0"
    assert field_value("P5_Line7_SameResidence[0]") == "0"
    assert field_value("P6_Line1a_NameofEmployer[0]") == "Engineer"
    assert field_value("P6_Line1a1_NameofEmployer[0]") == "Sample Employer"


@pytest.mark.parametrize(
    ("form_key", "answers", "template_name", "minimum_fields"),
    [
        ("i765", sample_i765_answers(), "i-765.pdf", 30),
        ("i131", sample_i131_answers(), "i-131.pdf", 30),
        ("i864", sample_i864_answers(), "i-864.pdf", 40),
        ("i130", sample_i130_answers(), "i-130.pdf", 75),
        ("i130a", sample_i130a_answers(), "i-130a.pdf", 10),
    ],
)
def test_supplemental_pdf_generation_from_sample_answers(
    form_key: str,
    answers: dict[str, object],
    template_name: str,
    minimum_fields: int,
):
    template_path = Path("blank-immigration-documents") / template_name
    if not template_path.exists():
        pytest.skip(f"Local editable {form_key} template is not present.")

    result = generate_form_pdf_from_answers(
        case_id=uuid4(),
        form_key=form_key,
        answers=answers,
        template_path=template_path,
        output_path=Path(f"/tmp/sample-{form_key}-test-output.pdf"),
        allow_incomplete=False,
        preview={
            "generation_status": "ready_for_user_review",
            "ready_for_pdf_generation": True,
            "missing_required_count": 0,
            "blocking_flag_count": 0,
            "outside_niche_flag_count": 0,
            "low_confidence_count": 0,
        },
    )

    assert result.generation_status == "ready_for_user_review"
    assert result.field_count >= minimum_fields
    assert result.output_path.exists()


def test_supplemental_fill_preview_blocks_when_required_answers_are_missing():
    session = make_session()
    case = create_case(session)

    preview = build_form_fill_preview(session, case.id, "i765")

    assert preview["generation_status"] == "incomplete"
    assert preview["missing_required_count"] > 0
