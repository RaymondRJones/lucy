from __future__ import annotations

from sqlmodel import Session, SQLModel, create_engine

from app.models.entities import CaseRecord
from app.services.intake import get_merged_case_intake
from app.services.prescreen import evaluate_prescreen, save_prescreen_answers


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def create_case(session: Session) -> CaseRecord:
    case = CaseRecord(case_name="Prescreen case", workflow_type="marriage_concurrent")
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


def test_prescreen_branches_to_i130_when_not_filed():
    evaluation = evaluate_prescreen(
        {
            "petitioner_citizenship_status": "us_citizen",
            "relationship_spouse": True,
            "beneficiary_location": "usa",
            "last_entry_type": "visa_admitted",
            "first_marriage_for_both": True,
            "has_children": False,
            "i130_filing_status": "not_filed",
            "wants_i765": True,
            "wants_i131": False,
        }
    )

    assert "form_i130" in evaluation["included_forms"]
    assert "form_i130a" in evaluation["included_forms"]
    assert "form_i131" not in evaluation["included_forms"]
    assert any(item["form_code"] == "i130_receipt_notice" for item in evaluation["eliminated_forms"])
    assert any(item["question_id"] == "i130_receipt_number" for item in evaluation["eliminated_questions"])


def test_prescreen_branches_to_receipt_when_i130_pending_and_flags_unusual_answers():
    evaluation = evaluate_prescreen(
        {
            "petitioner_citizenship_status": "lpr",
            "relationship_spouse": True,
            "beneficiary_location": "usa",
            "last_entry_type": "visa_admitted",
            "first_marriage_for_both": False,
            "has_children": True,
            "i130_filing_status": "pending",
            "wants_i765": False,
            "wants_i131": True,
        }
    )

    assert "form_i130" not in evaluation["included_forms"]
    assert "form_i130a" not in evaluation["included_forms"]
    assert "form_i131" in evaluation["included_forms"]
    assert any(item["form_code"] == "form_i130" for item in evaluation["eliminated_forms"])
    assert {flag["code"] for flag in evaluation["flags"]} >= {
        "outside_happy_path_petitioner_not_us_citizen",
        "outside_happy_path_prior_marriage",
        "outside_happy_path_children_in_case",
    }


def test_save_prescreen_projects_answers_into_intake():
    session = make_session()
    case = create_case(session)

    state = save_prescreen_answers(
        session,
        case.id,
        {
            "petitioner_citizenship_status": "us_citizen",
            "relationship_spouse": True,
            "beneficiary_location": "usa",
            "last_entry_type": "visa_admitted",
            "last_entry_details": {
                "i94_number": "123456789A1",
                "class_of_admission": "B-2",
                "last_arrival_date": "2025-04-10",
                "last_arrival_place": "Miami, FL",
            },
            "current_address_snapshot": {
                "line1": "123 Sample Street",
                "line2": "Apt 4B",
                "city": "Oakland",
                "state": "CA",
                "postal_code": "94612",
                "date_from": "2025-04-15",
                "mailing_same_as_physical": True,
                "lived_here_five_years": True,
            },
            "first_marriage_for_both": True,
            "i130_filing_status": "pending",
            "wants_i765": True,
        },
    )
    session.commit()

    merged = get_merged_case_intake(session, case.id)
    assert state["answers"]["i130_filing_status"] == "pending"
    assert merged["petitioner_citizenship_status"] == "us_citizen"
    assert merged["relationship_spouse"] is True
    assert merged["beneficiary_current_marital_status"] == "married"
    assert merged["beneficiary_entered_us_legally"] is True
    assert merged["beneficiary_i94_number"] == "123456789A1"
    assert merged["beneficiary_class_of_admission"] == "B-2"
    assert merged["beneficiary_last_arrival_place"] == "Miami, FL"
    assert merged["beneficiary_last_arrival_city"] == "Miami"
    assert merged["beneficiary_last_arrival_state"] == "FL"
    assert merged["beneficiary_current_address_city"] == "Oakland"
    assert merged["beneficiary_current_city"] == "Oakland"
    assert merged["beneficiary_current_address_postal_code"] == "94612"
    assert merged["beneficiary_current_zip"] == "94612"
    assert merged["beneficiary_current_address_since"] == "2025-04-15"
    assert merged["beneficiary_address_since"] == "2025-04-15"
    assert merged["beneficiary_mailing_city"] == "Oakland"
    assert merged["i130_already_filed"] is True


def test_prescreen_uses_branching_logic_specific_entry_and_status_flags():
    evaluation = evaluate_prescreen(
        {
            "case_basis": "usc_spouse",
            "petitioner_citizenship_status": "us_citizen",
            "relationship_spouse": True,
            "beneficiary_location": "usa",
            "last_entry_type": "esta_vwp",
            "current_status": "j1",
            "j1_212e_subject": "yes",
            "i130_filing_status": "pending",
        }
    )

    assert any(flag["code"] == "entry_type_review_recommended" for flag in evaluation["flags"])
    assert any(flag["code"] == "j1_212e_review_required" for flag in evaluation["flags"])
    assert evaluation["status"] == "blocked_needs_review"


def test_prescreen_flags_multiselect_and_review_petition_branch():
    evaluation = evaluate_prescreen(
        {
            "case_basis": "usc_spouse",
            "petitioner_citizenship_status": "us_citizen",
            "relationship_spouse": True,
            "beneficiary_location": "usa",
            "last_entry_type": "entered_without_inspection",
            "i130_filing_status": "denied_revoked_withdrawn",
            "bona_fide_evidence_categories": ["mostly_photos_chats_affidavits"],
            "immigration_violations": ["unlawful_entry"],
        }
    )

    assert evaluation["status"] == "blocked_needs_review"
    assert evaluation["included_forms"] == []
    assert {flag["code"] for flag in evaluation["flags"]} >= {
        "outside_happy_path_entry_review",
        "i130_status_needs_review",
        "marriage_evidence_needs_strengthening",
        "immigration_history_review",
    }


def test_prescreen_pauses_forms_when_i130_status_is_unknown():
    evaluation = evaluate_prescreen(
        {
            "case_basis": "usc_spouse",
            "petitioner_citizenship_status": "us_citizen",
            "relationship_spouse": True,
            "beneficiary_location": "usa",
            "last_entry_type": "visa_admitted",
            "i130_filing_status": "unknown",
        }
    )

    assert evaluation["status"] == "blocked_needs_review"
    assert evaluation["included_forms"] == []
    assert any(item["form_code"] == "form_i485" for item in evaluation["eliminated_forms"])
