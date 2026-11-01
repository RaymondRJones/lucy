from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.content.i485_questionnaire import I485_PART_GUIDANCE, I485_QUESTIONNAIRE, I485_VERIFIED_ON, all_i485_questions
from app.content.i485_sample import build_sample_i485_answers
from app.models.entities import CaseRecord, IntakeResponse, UploadedDocument
from app.services.i485 import (
    build_i485_answer_proposals_from_case_data,
    build_i485_form_fill_preview,
    build_i485_intake_projection,
    evaluate_i485_answers,
    import_i485_answers_from_case_data,
    import_i485_answers_from_upload,
    merge_i485_answer_sources,
    merge_i485_answers,
    save_i485_page_answers,
)
from app.services.i485_pdf import build_i485_pdf_field_payload, generate_i485_pdf, generate_i485_pdf_from_answers
from app.services.intake import get_merged_case_intake, upsert_intake_step


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def create_case(session: Session) -> CaseRecord:
    case = CaseRecord(case_name="I-485 questionnaire case", workflow_type="marriage_concurrent")
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


def test_i485_questionnaire_has_fourteen_pages_and_source_mappings():
    assert len(I485_QUESTIONNAIRE) == 14
    assert len(all_i485_questions()) > 100
    assert all(page["questions"] for page in I485_QUESTIONNAIRE)
    assert all(question["pdf_ref"] for question in all_i485_questions())
    assert all(question["plain_language"] for question in all_i485_questions())
    assert all(question["deep_explanation"] for question in all_i485_questions())
    assert all(question["teaching_source"]["label"] == "USCIS Form I-485 instructions" for question in all_i485_questions())
    assert all(question["teaching_source"]["url"].startswith("https://www.uscis.gov/") for question in all_i485_questions())
    assert all(question["teaching_source"]["fetched_on"] == I485_VERIFIED_ON for question in all_i485_questions())
    assert set(I485_PART_GUIDANCE) == {f"Part {part_number}" for part_number in range(1, 15)}
    assert all(
        I485_PART_GUIDANCE[question["pdf_ref"].split(",", 1)[0]] in question["deep_explanation"]
        for question in all_i485_questions()
        if question["pdf_ref"].split(",", 1)[0] in I485_PART_GUIDANCE
    )
    assert not any("transcript" in question["deep_explanation"].lower() for question in all_i485_questions())
    assert not any("walkthrough" in question["deep_explanation"].lower() for question in all_i485_questions())
    assert not any("video" in question["deep_explanation"].lower() for question in all_i485_questions())
    assert not any("applicant's applicant" in question["plain_language"].lower() for question in all_i485_questions())
    assert not any(question["plain_language"].startswith("Enter the information requested") for question in all_i485_questions())
    additional_info_question = next(
        question for question in all_i485_questions() if question["id"] == "additional_information_needed"
    )
    assert additional_info_question["plain_language"].startswith("Answer yes only if an I-485 answer")
    assert "page, part, item number" in additional_info_question["deep_explanation"]
    employment_question = next(question for question in all_i485_questions() if question["id"] == "beneficiary_employment_history")
    assert employment_question["answer_type"] == "employment_history_list"
    assert employment_question["form_entry_limit"] == 1
    assert employment_question["overflow_pdf_ref"] == "Part 14, Additional Information"
    foreign_address_question = next(
        question for question in all_i485_questions() if question["id"] == "beneficiary_recent_foreign_address"
    )
    assert foreign_address_question["answer_type"] == "address"
    assert foreign_address_question["entry_fields"]
    foreign_employment_question = next(
        question for question in all_i485_questions() if question["id"] == "beneficiary_foreign_employer_or_school"
    )
    assert foreign_employment_question["answer_type"] == "employment_history_list"
    assert foreign_employment_question["entry_fields"]
    eye_color_question = next(question for question in all_i485_questions() if question["id"] == "beneficiary_eye_color")
    hair_color_question = next(question for question in all_i485_questions() if question["id"] == "beneficiary_hair_color")
    assert eye_color_question["answer_type"] == "single_check"
    assert hair_color_question["answer_type"] == "single_check"
    assert {option["value"] for option in eye_color_question["options"]} == {
        "black",
        "blue",
        "brown",
        "gray",
        "green",
        "hazel",
    }


def test_i485_evaluator_flags_criminal_history_and_outside_niche_answers():
    evaluation = evaluate_i485_answers(
        {
            "i485_family_category": "spouse_lpr",
            "beneficiary_marriage_count": 2,
            "ever_committed_crime": True,
            "entered_without_inspection": True,
        }
    )

    codes = {flag["code"] for flag in evaluation["flags"]}

    assert evaluation["readiness"] == "needs_professional_review"
    assert "outside_niche_category" in codes
    assert "outside_niche_prior_marriage" in codes
    assert "criminal_history" in codes
    assert "unlawful_entry" in codes


def test_i485_projection_maps_to_existing_intake_fields():
    projection = build_i485_intake_projection(
        {
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Sample",
            "beneficiary_last_arrival_type": "admitted",
            "beneficiary_last_arrival_city": "Miami",
            "beneficiary_last_arrival_state": "FL",
            "beneficiary_last_arrival_first_us_presence": False,
            "beneficiary_current_address_line1": "123 Sample Street",
            "beneficiary_current_city": "Oakland",
            "beneficiary_current_state": "CA",
            "beneficiary_current_zip": "94612",
            "beneficiary_address_since": "2025-04-15",
            "beneficiary_mailing_same_as_physical": True,
            "beneficiary_ssn": "000000000",
            "beneficiary_race": ["white"],
            "beneficiary_eye_color": "brown",
            "beneficiary_foreign_employer_or_school": [
                {
                    "name": "Universidad Nacional de Colombia",
                    "occupation": "Student",
                    "province": "Caldas",
                    "postal_code": "170003",
                    "country": "Colombia",
                    "from": "2019-05-01",
                    "to": "2025-06-15",
                }
            ],
            "beneficiary_marriage_count": 1,
            "beneficiary_current_marital_status": "married",
            "petitioner_citizenship_status": "us_citizen",
        }
    )

    assert projection["beneficiary_first_name"] == "Avery"
    assert projection["beneficiary_entered_us_legally"] is True
    assert projection["first_marriage_for_both"] is True
    assert projection["beneficiary_current_address_city"] == "Oakland"
    assert projection["beneficiary_current_address_postal_code"] == "94612"
    assert projection["beneficiary_current_address_since"] == "2025-04-15"
    assert projection["beneficiary_last_arrival_place"] == "Miami, FL"
    assert projection["beneficiary_last_arrival_first_us_presence"] is False
    assert projection["beneficiary_mailing_city"] == "Oakland"
    assert projection["beneficiary_social_security_number"] == "000000000"
    assert projection["beneficiary_has_ssn"] is True
    assert projection["beneficiary_race_primary"] == "white"
    assert projection["beneficiary_eye_color"] == "brown"
    assert projection["beneficiary_foreign_employer_or_school"][0]["province"] == "Caldas"
    assert projection["beneficiary_foreign_employer_or_school"][0]["postal_code"] == "170003"
    assert projection["beneficiary_foreign_employer_or_school"][0]["country"] == "Colombia"


def test_i485_import_from_case_data_uses_prescreen_aliases_and_preserves_answers():
    session = make_session()
    case = create_case(session)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {
            "case_basis": "usc_spouse",
            "relationship_spouse": True,
            "petitioner_citizenship_status": "us_citizen",
            "first_marriage_for_both": True,
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Sample",
            "beneficiary_last_entry_type": "visa_admitted",
            "beneficiary_last_arrival_place": "Miami, FL",
            "beneficiary_i94_number": "123456789A1",
            "beneficiary_class_of_admission": "B-2",
            "beneficiary_current_address_line1": "123 Sample Street",
            "beneficiary_current_address_city": "Oakland",
            "beneficiary_current_address_state": "CA",
            "beneficiary_current_address_postal_code": "94612",
            "beneficiary_current_address_since": "2025-04-15",
            "beneficiary_mailing_same_as_physical": True,
            "beneficiary_social_security_number": "000000000",
        },
    )
    save_i485_page_answers(
        session,
        case.id,
        "page_01_identity",
        {"beneficiary_first_name": "User Confirmed"},
    )
    session.commit()

    proposals = build_i485_answer_proposals_from_case_data(get_merged_case_intake(session, case.id))
    result = import_i485_answers_from_case_data(session, case.id)

    answers = result["state"]["answers"]
    assert any(proposal["question_id"] == "beneficiary_current_city" for proposal in proposals)
    assert answers["beneficiary_first_name"] == "User Confirmed"
    assert answers["beneficiary_last_name"] == "Sample"
    assert answers["i485_family_category"] == "spouse_us_citizen"
    assert answers["beneficiary_last_arrival_type"] == "admitted"
    assert answers["beneficiary_last_arrival_city"] == "Miami"
    assert answers["beneficiary_last_arrival_state"] == "FL"
    assert answers["beneficiary_current_city"] == "Oakland"
    assert answers["beneficiary_current_zip"] == "94612"
    assert answers["beneficiary_address_since"] == "2025-04-15"
    assert answers["beneficiary_mailing_same_as_physical"] is True
    assert answers["beneficiary_ssn"] == "000000000"
    assert result["skipped_count"] == 1
    assert result["state"]["answer_sources"]["beneficiary_current_city"]["source_type"] == "case_intake"


def test_i485_projection_does_not_infer_first_marriage_false_from_missing_spouse_context():
    projection = build_i485_intake_projection({"beneficiary_marriage_count": 1})

    assert "first_marriage_for_both" not in projection


def test_i485_merge_orders_mixed_naive_and_aware_timestamps():
    case_id = uuid4()
    older = IntakeResponse(
        case_id=case_id,
        step_key="i485_ingestion:older",
        payload={
            "answers": {"beneficiary_first_name": "Old"},
            "answer_sources": {"beneficiary_first_name": {"source_type": "pdf_upload"}},
        },
        updated_at=datetime(2026, 4, 28, 12, 0, 0),
    )
    newer = IntakeResponse(
        case_id=case_id,
        step_key="i485_ingestion:newer",
        payload={
            "answers": {"beneficiary_first_name": "New"},
            "answer_sources": {"beneficiary_first_name": {"source_type": "user"}},
        },
        updated_at=datetime(2026, 4, 28, 12, 1, 0, tzinfo=UTC),
    )

    assert merge_i485_answers([newer, older])["beneficiary_first_name"] == "New"
    assert merge_i485_answer_sources([newer, older])["beneficiary_first_name"]["source_type"] == "user"


def test_i485_pdf_payload_maps_known_questionnaire_answers():
    payload = build_i485_pdf_field_payload(
        {
            "beneficiary_last_name": "Sample",
            "beneficiary_first_name": "Avery",
            "beneficiary_middle_name": "Marie",
            "beneficiary_date_of_birth": "2001-11-23",
            "beneficiary_a_number": "000000000",
            "beneficiary_i94_number": "987654321A1",
            "beneficiary_sex": "female",
            "beneficiary_last_arrival_state": "California",
            "beneficiary_current_state": "CAlifornia",
            "beneficiary_current_address_line2": "3103",
            "beneficiary_mailing_same_as_physical": False,
            "beneficiary_mailing_address": {
                "in_care_of": "Avery Sample",
                "line1": "999 Mailbox Road",
                "line2": "Suite 5",
                "city": "Sacramento",
                "state": "California",
                "zip": "95814",
            },
            "beneficiary_current_address_five_years": False,
            "beneficiary_prior_address_history": [
                {"line1": "456 Prior Avenue", "city": "Sunnyvale", "state": "California", "from": "2025-03-15"},
                {"line1": "101 Older Street", "city": "San Jose", "state": "CA", "from": "2023-03-15", "to": "2025-03-14"},
            ],
            "beneficiary_recent_foreign_address": {
                "line1": "789 Calle Falsa",
                "city": "Bogota",
                "country": "Colombia",
                "from": "2020-01-01",
                "to": "2022-12-31",
            },
            "beneficiary_has_ssn": True,
            "beneficiary_ssn": "000000000",
            "i485_family_category": "spouse_us_citizen",
            "beneficiary_current_marital_status": "married",
            "petitioner_current_address": {
                "line1": "222 Spouse Street",
                "line2": "Apt 9",
                "city": "Los Angeles",
                "state": "California",
                "zip": "90012",
                "country": "United States",
            },
            "beneficiary_eye_color": "brown",
            "beneficiary_hair_color": "black",
            "ever_committed_crime": False,
        }
    )

    assert payload.text_values["Pt1Line1_FamilyName[0]"] == "Sample"
    assert payload.text_values["P1Line12_FamilyName[0]"] == "Sample"
    assert payload.text_values["P1Line13_GivenName[0]"] == "Avery"
    assert payload.text_values["P1Line12_I94[0]"] == "987654321A1"
    assert payload.text_values["Pt2Line2_FamilyName[0]"] == "Sample"
    assert payload.text_values["Pt2Line2_GivenName[0]"] == "Avery"
    assert payload.text_values["Pt2Line2_MiddleName[0]"] == "Marie"
    assert payload.text_values["Pt2Line2_AlienNumber[0]"] == "000000000"
    assert payload.text_values["Pt1Line3_DOB[0]"] == "11/23/2001"
    assert payload.text_values["Pt1Line2_DOB[0]"] == "11/23/2001"
    assert payload.text_values["Pt1Line10_State[0]"] == "CA"
    assert payload.text_values["Pt1Line18_State[0]"] == "CA"
    assert payload.text_values["Pt1Line18US_AptSteFlrNumber[0]"] == "3103"
    assert payload.checkbox_values["Pt1Line18US_Unit[2]"] == "/ APT "
    assert payload.checkbox_values["Pt1Line18_YN[1]"] == "/N"
    assert payload.text_values["Pt1Line18_CurrentStreetNumberName[0]"] == "999 Mailbox Road"
    assert payload.text_values["Pt1Line18_CurrentState[0]"] == "CA"
    assert payload.text_values["Pt1Line18_PriorDateFrom[0]"] == "03/15/2025"
    assert payload.text_values["Pt1Line18_PriorState[0]"] == "CA"
    assert payload.text_values["Pt9Line3a_PageNumber[0]"] == "4"
    assert payload.text_values["Pt9Line3b_PartNumber[0]"] == "1"
    assert payload.text_values["Pt9Line3c_ItemNumber[0]"] == "18"
    assert "Prior address 2:" in payload.text_values["P14_Line2_AdditionalInfo[0]"]
    assert "Street: 101 Older Street" in payload.text_values["P14_Line2_AdditionalInfo[0]"]
    assert "State: CA" in payload.text_values["P14_Line2_AdditionalInfo[0]"]
    assert "State or province" not in payload.text_values["P14_Line2_AdditionalInfo[0]"]
    assert "From: 03/15/2023" in payload.text_values["P14_Line2_AdditionalInfo[0]"]
    assert payload.text_values["Pt1Line18_RecentStreetName[0]"] == "789 Calle Falsa"
    assert payload.text_values["Pt1Line18_RecentDateTo[0]"] == "12/31/2022"
    assert payload.text_values["Pt1Line19_SSN[0]"] == "000000000"
    assert payload.checkbox_values["Pt1Line6_CB_Sex[0]"] == "/F"
    assert payload.checkbox_values["Pt2Line3a_CB[0]"] == "/3a0"
    assert payload.checkbox_values["Pt6Line1_MaritalStatus[3]"] == "/2"
    assert payload.text_values["Part6Line8_StreetName[0]"] == "222 Spouse Street"
    assert payload.text_values["P6Line8_State[0]"] == "CA"
    assert payload.text_values["P6Line8_Number[0]"] == "9"
    assert payload.checkbox_values["P6Line8_Unit[0]"] == "/ APT "
    assert payload.checkbox_values["Pt7Line5_Eyecolor[2]"] == "/BN"
    assert payload.checkbox_values["Pt7Line6_Haircolor[1]"] == "/BL"
    assert any(entry["question_id"] == "ever_committed_crime" for entry in payload.unmapped_answered_questions)


def test_i485_pdf_payload_maps_structured_employment_history_and_part14_overflow():
    payload = build_i485_pdf_field_payload(
        {
            "beneficiary_employment_history": [
                {
                    "activity_type": "employment",
                    "name": "Acme Studio",
                    "occupation": "Designer",
                    "line1": "1 Main St",
                    "city": "Sunnyvale",
                    "state": "CA",
                    "zip": "94086",
                    "country": "United States",
                    "from": "2025-01-01",
                    "to": "",
                },
                {
                    "activity_type": "school",
                    "name": "Universidad de Ejemplo",
                    "occupation": "Student",
                    "city": "Bogota",
                    "country": "Colombia",
                    "from": "2022-01-15",
                    "to": "2024-12-20",
                    "outside_us": True,
                },
                {
                    "activity_type": "unemployment",
                    "name": "Family support",
                    "occupation": "Unemployed",
                    "financial_support": "Savings and family support",
                    "from": "2021-01-01",
                    "to": "2021-12-31",
                },
            ]
        }
    )

    assert payload.text_values["Pt4Line7_EmployerName[0]"] == "Employer"
    assert payload.text_values["Pt4Line7_EmployerName[2]"] == "Acme Studio"
    assert payload.text_values["Pt4Line7_EmployerName[1]"] == "Designer"
    assert payload.text_values["Pt4Line7_DateFrom[0]"] == "01/01/2025"
    assert payload.text_values["Pt4Line8_EmployerName[0]"] == "Universidad de Ejemplo"
    assert payload.text_values["Pt4Line8_DateTo[0]"] == "12/20/2024"
    assert payload.text_values["Pt9Line3b_PartNumber[0]"] == "4"
    assert "Family support" in payload.text_values["P14_Line2_AdditionalInfo[0]"]
    assert not payload.unmapped_answered_questions


def test_i485_pdf_payload_maps_unemployment_support_and_separate_foreign_school():
    payload = build_i485_pdf_field_payload(
        {
            "beneficiary_employment_history": [
                {
                    "activity_type": "unemployment",
                    "occupation": "Unemployed",
                    "financial_support": "Husband",
                    "from": "2025-07-15",
                    "to": "",
                }
            ],
            "beneficiary_country_of_birth": "Colombia",
            "beneficiary_foreign_employer_or_school": [
                {
                    "name": "Universidad Nacional de Colombia",
                    "occupation": "Student",
                    "line1": "Carrera 27 64 - 60",
                    "city": "Manizales",
                    "province": "Caldas",
                    "postal_code": "170003",
                    "country": "",
                    "from": "2019-05-01",
                    "to": "2025-06-15",
                }
            ],
        }
    )

    assert payload.text_values["Pt4Line7_EmployerName[0]"] == "Unemployed"
    assert "Pt4Line7_EmployerName[2]" not in payload.text_values
    assert payload.text_values["Pt4Line7_EmployerName[1]"] == "Unemployed"
    assert payload.text_values["Part4Line7_StreetName[1]"] == "Husband"
    assert payload.text_values["Pt4Line8_EmployerName[0]"] == "Universidad Nacional de Colombia"
    assert payload.text_values["Pt4Line8_Occupation[0]"] == "Student"
    assert payload.text_values["P4Line8_City[0]"] == "Manizales"
    assert payload.text_values["P4Line8_Province[0]"] == "Caldas"
    assert payload.text_values["P4Line8_PostalCode[0]"] == "170003"
    assert payload.text_values["P4Line8_Country[0]"] == "Colombia"
    assert payload.text_values["Pt4Line8_DateFrom[0]"] == "05/01/2019"
    assert not payload.unmapped_answered_questions


def test_i485_pdf_generation_reports_missing_template():
    session = make_session()
    case = create_case(session)

    try:
        generate_i485_pdf(session=session, case_id=case.id, template_path=Path("missing-i-485-template.pdf"))
    except ValueError as exc:
        assert "I-485 PDF template not found" in str(exc)
    else:
        raise AssertionError("Expected missing template error")


def test_sample_i485_answers_are_ready_for_pdf_payload():
    template_path = Path("blank-immigration-documents/i-485.pdf")
    if not template_path.exists():
        pytest.skip("Local editable I-485 template is not present.")
    answers = build_sample_i485_answers()
    result = generate_i485_pdf_from_answers(
        case_id=UUID("00000000-0000-0000-0000-000000000485"),
        answers=answers,
        template_path=template_path,
        output_path=Path("/tmp/sample-i485-test-output.pdf"),
        allow_incomplete=False,
    )

    assert result.generation_status == "ready_for_user_review"
    assert result.missing_required_count == 0
    assert result.blocking_flag_count == 0
    assert result.outside_niche_flag_count == 0
    assert result.unmapped_answer_count == 0
    assert result.field_count > 150


def test_i485_page_save_stores_isolated_answers_and_projection():
    session = make_session()
    case = create_case(session)

    state = save_i485_page_answers(
        session,
        case.id,
        "page_08_marriage_spouse",
        {
            "petitioner_first_name": "Jordan",
            "petitioner_last_name": "Petitioner",
            "petitioner_citizenship_status": "us_citizen",
            "beneficiary_marriage_count": 1,
            "beneficiary_current_marital_status": "married",
            "marriage_date": "2024-05-15",
        },
        {"marriage_date": True},
    )
    session.commit()

    merged = get_merged_case_intake(session, case.id)

    assert state["answers"]["petitioner_first_name"] == "Jordan"
    assert state["answer_sources"]["petitioner_first_name"]["source_type"] == "user"
    assert state["manual_flags"]["marriage_date"] is True
    assert "page_08_marriage_spouse" in state["saved_pages"]
    assert merged["petitioner_first_name"] == "Jordan"
    assert merged["marriage_date"] == "2024-05-15"

    updated_state = save_i485_page_answers(
        session,
        case.id,
        "page_08_marriage_spouse",
        state["answers"],
        {},
    )
    assert "marriage_date" not in updated_state["manual_flags"]


def test_i485_import_from_upload_maps_pdf_fields_to_reviewable_answers():
    session = make_session()
    case = create_case(session)
    upload = UploadedDocument(
        case_id=case.id,
        checklist_item_code="form_i485",
        original_filename="I-485.pdf",
        stored_filename=f"{uuid4()}-I-485.pdf",
        mime_type="application/pdf",
        file_size=45678,
        upload_status="confirmed",
        document_type="form_i485",
        document_language="english",
        requires_translation=False,
        has_translation=False,
        extraction_confidence=0.86,
        extracted_fields={
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Sample",
            "beneficiary_i94_number": "898715649A4",
            "beneficiary_entered_us_legally": True,
            "beneficiary_first_marriage_detected": True,
            "beneficiary_prior_address_history": [{"city": "Sunnyvale"}],
            "petitioner_first_name": "Jordan",
            "petitioner_last_name": "Petitioner",
            "marriage_date": "2024-05-15",
        },
    )
    session.add(upload)
    session.commit()

    result = import_i485_answers_from_upload(session, case.id)
    session.commit()

    answers = result["state"]["answers"]
    sources = result["state"]["answer_sources"]
    merged = get_merged_case_intake(session, case.id)

    assert result["imported_count"] >= 8
    assert answers["beneficiary_first_name"] == "Avery"
    assert answers["beneficiary_last_arrival_type"] == "admitted"
    assert answers["beneficiary_marriage_count"] == 1
    assert answers["beneficiary_current_address_five_years"] is False
    assert sources["beneficiary_i94_number"]["source_type"] == "pdf_upload"
    assert sources["beneficiary_i94_number"]["confidence"] == 0.86
    assert merged["beneficiary_first_name"] == "Avery"
    assert merged["beneficiary_entered_us_legally"] is True


def test_i485_import_from_upload_preserves_user_answers_by_default():
    session = make_session()
    case = create_case(session)
    save_i485_page_answers(
        session,
        case.id,
        "page_01_identity",
        {"beneficiary_first_name": "User Confirmed"},
    )
    session.add(
        UploadedDocument(
            case_id=case.id,
            checklist_item_code="form_i485",
            original_filename="I-485.pdf",
            stored_filename=f"{uuid4()}-I-485.pdf",
            mime_type="application/pdf",
            file_size=45678,
            upload_status="confirmed",
            document_type="form_i485",
            document_language="english",
            requires_translation=False,
            has_translation=False,
            extraction_confidence=0.86,
            extracted_fields={"beneficiary_first_name": "PDF Extracted"},
        )
    )
    session.commit()

    result = import_i485_answers_from_upload(session, case.id)

    assert result["state"]["answers"]["beneficiary_first_name"] == "User Confirmed"
    assert result["skipped_count"] == 1


def test_i485_form_fill_preview_blocks_when_required_answers_are_missing():
    session = make_session()
    case = create_case(session)
    save_i485_page_answers(
        session,
        case.id,
        "page_08_marriage_spouse",
        {
            "petitioner_first_name": "Jordan",
            "petitioner_last_name": "Petitioner",
            "petitioner_citizenship_status": "us_citizen",
            "beneficiary_marriage_count": 1,
            "beneficiary_current_marital_status": "married",
        },
    )

    preview = build_i485_form_fill_preview(session, case.id)

    assert preview["generation_status"] == "incomplete"
    assert preview["ready_for_pdf_generation"] is False
    assert preview["field_count"] >= 4
    assert preview["missing_required_count"] > 0
    assert any(field["target_key"] == "form_i485.petitioner_first_name" for field in preview["fields"])


def test_i485_recent_foreign_address_is_required_when_prior_slot_is_us_address():
    session = make_session()
    case = create_case(session)
    save_i485_page_answers(
        session,
        case.id,
        "page_04_addresses_ssn",
        {
            "beneficiary_current_address_line1": "123 Sample Street",
            "beneficiary_current_city": "Oakland",
            "beneficiary_current_state": "CA",
            "beneficiary_current_zip": "94612",
            "beneficiary_address_since": "2025-04-15",
            "beneficiary_current_address_five_years": False,
            "beneficiary_prior_address_history": [
                {
                    "line1": "456 Prior Avenue",
                    "city": "Sunnyvale",
                    "state": "CA",
                    "zip": "94086",
                    "country": "United States",
                    "from": "2023-01-01",
                    "to": "2025-04-14",
                }
            ],
            "beneficiary_has_ssn": False,
        },
    )

    preview = build_i485_form_fill_preview(session, case.id)

    assert preview["generation_status"] == "incomplete"
    assert any(item["question_id"] == "beneficiary_recent_foreign_address" for item in preview["missing_required"])


def test_i485_form_fill_preview_blocks_dangerous_answers():
    session = make_session()
    case = create_case(session)
    save_i485_page_answers(
        session,
        case.id,
        "page_11_criminal_acts",
        {"ever_committed_crime": True},
    )

    preview = build_i485_form_fill_preview(session, case.id)

    assert preview["generation_status"] == "blocked_by_risk"
    assert preview["blocking_flag_count"] == 1
    assert preview["blocking_flags"][0]["code"] == "criminal_history"
