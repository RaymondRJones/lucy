from __future__ import annotations

from fastapi.testclient import TestClient
from pypdf import PdfReader
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.cli.seed_happy_path import PRESCREEN_ANSWERS
from app.cli.seed_packet_scenarios import SCENARIOS, _create_case, _scenario_answers
from app.db.session import get_session
from app.main import app
from app.models.entities import CaseRecord
from app.services.filing_validation import validate_case_filings
from app.services.form_pdf import generate_form_pdf
from app.services.intake import country_name, get_merged_case_intake, upsert_intake_step
from app.services.packet_assembly import assemble_packet_pdf
from app.services.prescreen import evaluate_prescreen, get_prescreen_state, save_prescreen_answers
from app.services.qa import run_qa


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


def _seeded_case(session: Session, scenario=SCENARIOS[0]) -> CaseRecord:
    answers = _scenario_answers(scenario)
    case = _create_case(session, scenario, answers)
    upsert_intake_step(session, case.id, "scenario", answers)
    save_prescreen_answers(session, case.id, PRESCREEN_ANSWERS)
    return case


def test_blocked_prescreen_stops_a_case_reading_ready():
    session = make_session()
    case = _seeded_case(session)

    state = save_prescreen_answers(session, case.id, {"i130_filing_status": "denied_revoked_withdrawn"})
    issues, summary = run_qa(session, case.id)

    assert state["evaluation"]["status"] == "blocked_needs_review"
    assert summary["label"] == "Not ready"
    assert ("prescreen_i130_status_needs_review", "blocking") in {(issue.code, issue.severity) for issue in issues}


def test_seeded_cases_finish_prescreen_on_the_standard_path():
    session = make_session()
    flagged_on_purpose = {"az-prior-marriage-travel", "wa-public-benefit-history", "il-long-public-charge-answers"}
    for scenario in SCENARIOS:
        evaluation = get_prescreen_state(session, _seeded_case(session, scenario).id)["evaluation"]
        assert evaluation["completion_pct"] == 100, scenario.slug
        expected = "needs_review" if scenario.slug in flagged_on_purpose else "happy_path_ready"
        assert evaluation["status"] == expected, scenario.slug


def test_saved_address_history_clears_the_prescreen_address_flag():
    session = make_session()
    case = _seeded_case(session)
    upsert_intake_step(session, case.id, "address", {"beneficiary_prior_address_history": []})
    assert "address_history_needed" in {flag["code"] for flag in get_prescreen_state(session, case.id)["evaluation"]["flags"]}

    upsert_intake_step(session, case.id, "address", {"beneficiary_prior_address_history": [{"line1": "1 Old Road"}]})

    assert "address_history_needed" not in {flag["code"] for flag in get_prescreen_state(session, case.id)["evaluation"]["flags"]}


def test_saving_a_blocked_prescreen_updates_the_stored_readiness():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    case = _seeded_case(session)
    case.readiness_label = "Ready to print and assemble"
    session.add(case)
    session.commit()
    app.dependency_overrides[get_session] = lambda: session
    try:
        response = TestClient(app).post(
            f"/api/v1/cases/{case.id}/prescreen", json={"answers": {"i130_filing_status": "denied_revoked_withdrawn"}}
        )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    session.refresh(case)
    assert case.readiness_label == "Not ready"


def test_blocked_prescreen_is_named_in_the_packet_warnings(tmp_path):
    session = make_session()
    case = _seeded_case(session)
    save_prescreen_answers(session, case.id, {"i130_filing_status": "denied_revoked_withdrawn"})

    result = assemble_packet_pdf(session=session, case_id=case.id, state_code="CA", output_dir=tmp_path)

    assert any(
        warning.startswith("Prescreen found issues") and "I-130 status needs review" in warning
        for warning in result.warnings
    )
    assert any("Oct. 7, 2026" in warning for warning in result.warnings)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("CO", "Colombia"), ("colombia", "Colombia"), ("US", "United States"), ("Poland", "Poland"), (None, None)],
)
def test_country_name_expands_stored_codes(value, expected):
    assert country_name(value) == expected


@pytest.mark.parametrize("entered", ["Colombia", "CO", "Poland"])
@pytest.mark.parametrize("form_key", ["i130", "i765", "i131"])
def test_forms_prefilled_from_intake_print_the_country_name(tmp_path, form_key, entered):
    session = make_session()
    case = create_case(session)
    upsert_intake_step(session, case.id, "baseline", {"beneficiary_country_of_birth": entered})

    result = generate_form_pdf(session=session, case_id=case.id, form_key=form_key, output_dir=tmp_path, allow_incomplete=True)

    printed = {
        str(field.get("/V"))
        for name, field in PdfReader(result.output_path).get_fields().items()
        if "CountryOfBirth" in name and field.get("/V")
    }
    assert printed == {"Poland" if entered == "Poland" else "Colombia"}


def test_blocked_prescreen_blocks_the_i485_and_i130_validators():
    session = make_session()
    case = _seeded_case(session)
    save_prescreen_answers(session, case.id, {"i130_filing_status": "denied_revoked_withdrawn"})

    report = validate_case_filings(session, case.id, form_codes=["form_i485", "form_i130"])

    assert {
        issue["code"] for form in report["forms"] for issue in form["issues"] if issue["severity"] == "blocking"
    } >= {
        "form_i485_prescreen_i130_status_needs_review",
        "form_i130_prescreen_i130_status_needs_review",
    }


def test_generated_i130a_part_3_carries_the_foreign_employer(tmp_path):
    session = make_session()
    case = create_case(session)
    upsert_intake_step(
        session,
        case.id,
        "baseline",
        {"beneficiary_foreign_employer_or_school": [{"name": "Universidad", "city": "Bogota", "country": "Colombia"}]},
    )

    result = generate_form_pdf(session=session, case_id=case.id, form_key="i130a", output_dir=tmp_path, allow_incomplete=True)

    fields = PdfReader(result.output_path).get_fields()
    printed = {name.split(".")[-1]: field.get("/V") for name, field in fields.items()}
    assert printed["Pt3Line1_EmployerOrCompName[0]"] == "Universidad"
    assert printed["Pt3Line2h_Country[0]"] == "Colombia"


def test_saving_prescreen_refreshes_an_existing_checklist():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    case = _seeded_case(session)
    app.dependency_overrides[get_session] = lambda: session
    try:
        client = TestClient(app)
        client.post(f"/api/v1/cases/{case.id}/checklist/generate")
        before = {item["code"]: item["applicability"] for item in client.get(f"/api/v1/cases/{case.id}/checklist").json()["items"]}
        response = client.post(f"/api/v1/cases/{case.id}/prescreen", json={"answers": {"first_marriage_for_both": False}})
        after = {item["code"]: item["applicability"] for item in client.get(f"/api/v1/cases/{case.id}/checklist").json()["items"]}
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    assert before["prior_marriage_termination_records"] == "not_applicable"
    assert after["prior_marriage_termination_records"] != "not_applicable"
