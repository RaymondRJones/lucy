from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import UUID

from sqlmodel import Session

from app.content.i485_questionnaire import I485_QUESTIONNAIRE
from app.content.i485_sample import build_sample_i485_answers
from app.db.session import create_db_and_tables, engine
from app.models.entities import CaseRecord
from app.services.checklist import generate_checklist
from app.services.i485 import get_i485_state, save_i485_page_answers
from app.services.i485_pdf import DEFAULT_I485_OUTPUT_DIR, DEFAULT_I485_TEMPLATE_PATH, generate_i485_pdf
from app.services.qa import run_qa


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create or update a local case with complete safe sample I-485 questionnaire answers."
    )
    parser.add_argument("--case-id", default=None, help="Existing case ID to update. If omitted, a new sample case is created.")
    parser.add_argument("--case-name", default="Sample I-485 complete questionnaire case", help="Case name when creating a new case.")
    parser.add_argument("--overwrite", action="store_true", help="Allow replacing existing I-485 sample answers on an existing case.")
    parser.add_argument("--generate-pdf", action="store_true", help="Generate a draft I-485 PDF after seeding answers.")
    parser.add_argument("--template", default=str(DEFAULT_I485_TEMPLATE_PATH), help="Path to the fillable I-485 PDF template.")
    parser.add_argument("--output-dir", default=str(DEFAULT_I485_OUTPUT_DIR), help="Directory for generated PDFs.")
    parser.add_argument("--web-base-url", default="http://localhost:3000", help="Base web URL used in printed links.")
    return parser


def _case_for_seed(session: Session, *, raw_case_id: str | None, case_name: str) -> tuple[CaseRecord, bool]:
    if raw_case_id:
        case = session.get(CaseRecord, UUID(raw_case_id))
        if not case:
            raise SystemExit(f"Case not found: {raw_case_id}")
        return case, False

    case = CaseRecord(
        case_name=case_name,
        workflow_type="marriage_concurrent",
        petitioner_email="jordan.petitioner@example.com",
        beneficiary_email="avery.sample@example.com",
        country_of_focus="CO",
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return case, True


def main() -> None:
    args = build_parser().parse_args()
    create_db_and_tables()
    answers = build_sample_i485_answers()

    with Session(engine) as session:
        case, created = _case_for_seed(session, raw_case_id=args.case_id, case_name=args.case_name)
        existing_state = get_i485_state(session, case.id)
        if existing_state["saved_pages"] and not created and not args.overwrite:
            raise SystemExit(
                "This case already has I-485 questionnaire answers. Pass --overwrite to replace them, "
                "or omit --case-id to create a separate sample case."
            )

        for page in I485_QUESTIONNAIRE:
            page_answers = {
                question["id"]: answers[question["id"]]
                for question in page["questions"]
                if question["id"] in answers
            }
            save_i485_page_answers(session, case.id, page["id"], page_answers)
        session.commit()

        checklist_items, _ = generate_checklist(session, case.id)
        qa_issues, qa_summary = run_qa(session, case.id)
        state = get_i485_state(session, case.id)

        generated_pdf = None
        if args.generate_pdf:
            result = generate_i485_pdf(
                session=session,
                case_id=case.id,
                template_path=Path(args.template),
                output_dir=Path(args.output_dir),
                allow_incomplete=False,
            )
            generated_pdf = str(result.output_path)

    base_url = args.web_base_url.rstrip("/")
    print(
        json.dumps(
            {
                "case_id": str(case.id),
                "created": created,
                "saved_pages": len(state["saved_pages"]),
                "answered_questions": len(state["answers"]),
                "completion_pct": state["evaluation"]["completion_pct"],
                "readiness": state["evaluation"]["readiness"],
                "checklist_items": len(checklist_items),
                "qa_issues": len(qa_issues),
                "qa_summary": qa_summary,
                "generated_pdf": generated_pdf,
                "case_url": f"{base_url}/?caseId={case.id}",
                "i485_url": f"{base_url}/i485-ingestion?caseId={case.id}",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
