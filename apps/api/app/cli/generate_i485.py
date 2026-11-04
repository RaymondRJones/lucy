"""Generates an I-485 PDF for a case."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import UUID

from sqlmodel import Session, select

from app.content.i485_sample import build_sample_i485_answers
from app.db.session import create_db_and_tables, engine
from app.models.entities import CaseRecord
from app.services.i485_pdf import (
    DEFAULT_I485_OUTPUT_DIR,
    DEFAULT_I485_TEMPLATE_PATH,
    generate_i485_pdf,
    generate_i485_pdf_from_answers,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a local draft Form I-485 PDF from saved questionnaire answers.")
    parser.add_argument("--case-id", default=None, help="Case ID. If omitted, the latest case is used.")
    parser.add_argument(
        "--template",
        default=str(DEFAULT_I485_TEMPLATE_PATH),
        help="Path to the fillable I-485 PDF template.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output PDF path. Defaults to storage/generated/<case-id>-i-485.pdf.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_I485_OUTPUT_DIR),
        help="Directory for generated I-485 PDFs.",
    )
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Fail unless the I-485 fill preview is ready for PDF generation.",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Generate from built-in safe sample questionnaire answers instead of a database case.",
    )
    return parser


def _latest_case(session: Session) -> CaseRecord | None:
    return session.exec(select(CaseRecord).order_by(CaseRecord.created_at.desc())).first()


def _case_or_exit(session: Session, raw_case_id: str | None) -> CaseRecord:
    if raw_case_id:
        case = session.get(CaseRecord, UUID(raw_case_id))
    else:
        case = _latest_case(session)
    if not case:
        raise SystemExit("No case found. Pass --case-id or create/ingest a case first.")
    return case


def main() -> None:
    args = build_parser().parse_args()
    if args.sample:
        sample_case_id = UUID("00000000-0000-0000-0000-000000000485")
        output_path = (
            Path(args.output)
            if args.output
            else Path(args.output_dir) / "sample-i-485.pdf"
        )
        result = generate_i485_pdf_from_answers(
            case_id=sample_case_id,
            answers=build_sample_i485_answers(),
            template_path=Path(args.template),
            output_path=output_path,
            output_dir=Path(args.output_dir),
            allow_incomplete=not args.require_ready,
        )
        print(_result_json(result))
        return

    create_db_and_tables()
    with Session(engine) as session:
        case = _case_or_exit(session, args.case_id)
        result = generate_i485_pdf(
            session=session,
            case_id=case.id,
            template_path=Path(args.template),
            output_path=Path(args.output) if args.output else None,
            output_dir=Path(args.output_dir),
            allow_incomplete=not args.require_ready,
        )
    print(_result_json(result))


def _result_json(result) -> str:
    return json.dumps(
        {
            "case_id": str(result.case_id),
            "generated_pdf": str(result.output_path),
            "template_pdf": str(result.template_path),
            "generation_status": result.generation_status,
            "ready_for_pdf_generation": result.ready_for_pdf_generation,
            "field_count": result.field_count,
            "text_field_count": result.text_field_count,
            "checkbox_field_count": result.checkbox_field_count,
            "mapped_question_count": result.mapped_question_count,
            "unmapped_answer_count": result.unmapped_answer_count,
            "missing_required_count": result.missing_required_count,
            "blocking_flag_count": result.blocking_flag_count,
            "outside_niche_flag_count": result.outside_niche_flag_count,
            "low_confidence_count": result.low_confidence_count,
            "warnings": result.warnings,
            "unmapped_answered_questions": result.unmapped_answered_questions,
            "missing_template_fields": result.missing_template_fields,
        },
        indent=2,
    )


if __name__ == "__main__":
    main()
