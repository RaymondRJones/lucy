from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import UUID

from app.db.session import create_db_and_tables, engine
from app.services.ingestion import ingest_evidence_directory
from sqlmodel import Session


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest an existing marriage-evidence directory into the Lucy case workspace."
    )
    parser.add_argument(
        "--path",
        default="MARRIAGE_EVIDENCE",
        help="Path to the evidence directory to scan.",
    )
    parser.add_argument(
        "--case-id",
        default=None,
        help="Existing case ID to update. If omitted, a new case will be created.",
    )
    parser.add_argument(
        "--case-name",
        default=None,
        help="Optional case name when creating a new case.",
    )
    parser.add_argument(
        "--web-base-url",
        default="http://localhost:3000",
        help="Base URL for the web app used in the summary output.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    directory = Path(args.path).resolve()
    if not directory.exists():
        raise SystemExit(f"Evidence directory not found: {directory}")

    create_db_and_tables()
    with Session(engine) as session:
        summary = ingest_evidence_directory(
            session=session,
            directory=directory,
            case_id=UUID(args.case_id) if args.case_id else None,
            case_name=args.case_name,
        )

    case_url = f"{args.web_base_url.rstrip('/')}/?caseId={summary['case_id']}"
    print(json.dumps(summary, indent=2))
    print(f"\nOpen the case in the web UI: {case_url}")


if __name__ == "__main__":
    main()
