from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import UUID

from sqlmodel import Session

from app.db.session import create_db_and_tables, engine
from app.models.entities import CaseRecord
from app.services.g1450 import generate_case_g1450_packet, generate_g1450_pdf


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a local Form G-1450 PDF from a credit-card JSON file."
    )
    parser.add_argument(
        "--case-id",
        default=None,
        help="Case ID used in the default output filename. If omitted, the latest case is used.",
    )
    parser.add_argument(
        "--card-json",
        default="local-card-info.json",
        help="Path to the credit-card JSON payload.",
    )
    parser.add_argument(
        "--template",
        default="blank-immigration-documents/g-1450.pdf",
        help="Path to the fillable G-1450 PDF template.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output PDF path for --single mode.",
    )
    parser.add_argument(
        "--output-dir",
        default="storage/generated",
        help="Directory for case packet G-1450 PDFs.",
    )
    parser.add_argument(
        "--amount",
        default=None,
        help="Amount override for --single mode. Otherwise uses authorized_amount from the JSON file.",
    )
    parser.add_argument(
        "--single",
        action="store_true",
        help="Generate one generic G-1450 instead of one per payable case form.",
    )
    return parser


def _latest_case(session: Session) -> CaseRecord | None:
    from sqlmodel import select

    return session.exec(select(CaseRecord).order_by(CaseRecord.created_at.desc())).first()


def _resolve_case_id(raw_case_id: str | None) -> UUID:
    create_db_and_tables()
    with Session(engine) as session:
        if raw_case_id:
            case = session.get(CaseRecord, UUID(raw_case_id))
        else:
            case = _latest_case(session)
        if not case:
            raise SystemExit("No case found. Pass --case-id or create/ingest a case first.")
        return case.id


def main() -> None:
    args = build_parser().parse_args()
    case_id = _resolve_case_id(args.case_id)
    if args.single:
        output_path = (
            Path(args.output)
            if args.output
            else Path(args.output_dir) / f"{case_id}-g-1450.pdf"
        )
        result = generate_g1450_pdf(
            card_json_path=Path(args.card_json),
            template_path=Path(args.template),
            output_path=output_path,
            amount_override=args.amount,
        )
        print(
            json.dumps(
                {
                    "case_id": str(case_id),
                    "generated_pdf": str(result.output_path),
                    "authorized_amount": result.authorized_amount,
                    "template": str(result.template_path),
                    "source_json": str(result.source_json_path),
                    "note": "Review USCIS fees and hand-sign/review the generated form before mailing.",
                },
                indent=2,
            )
        )
        return

    create_db_and_tables()
    with Session(engine) as session:
        packet = generate_case_g1450_packet(
            session=session,
            case_id=case_id,
            card_json_path=Path(args.card_json),
            template_path=Path(args.template),
            output_dir=Path(args.output_dir),
        )
    print(
        json.dumps(
            {
                "case_id": str(case_id),
                "generated": [
                    {
                        "form_code": result.form_code,
                        "checklist_code": result.checklist_code,
                        "filing_category": result.filing_category,
                        "authorized_amount": result.authorized_amount,
                        "generated_pdf": str(result.output_path),
                    }
                    for result in packet.generated
                ],
                "skipped": packet.skipped,
                "total_authorized_amount": packet.total_authorized_amount,
                "payment_note": packet.payment_note,
                "note": "Review USCIS fees and hand-sign/review every generated G-1450 before mailing.",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
