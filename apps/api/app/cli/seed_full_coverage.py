"""Seeds the full-coverage persona, generates every form, and reports which PDF fields stayed blank."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from uuid import UUID

from pypdf import PdfReader
from sqlmodel import Session

from app.content.full_coverage_sample import (
    FULL_COVERAGE_BANK_PAYMENT,
    FULL_COVERAGE_CARD_PAYMENT,
    FULL_COVERAGE_FORM_KEYS,
    FULL_COVERAGE_PRESCREEN_ANSWERS,
    build_full_coverage_form_answers,
    build_full_coverage_i485_answers,
    full_coverage_answers,
)
from app.content.i485_questionnaire import I485_QUESTIONNAIRE
from app.core.config import settings
from app.db.session import create_db_and_tables, engine
from app.models.entities import CaseRecord
from app.services.checklist import generate_checklist
from app.services.family_pdf import generate_g1145_pdf
from app.services.form_ingestion import save_form_page_answers
from app.services.form_pdf import generate_form_pdf
from app.services.g1450 import generate_g1450_pdf_from_payload
from app.services.g1650 import generate_g1650_pdf_from_payload
from app.services.i485 import save_i485_page_answers
from app.services.i485_pdf import DEFAULT_I485_TEMPLATE_PATH, generate_i485_pdf
from app.services.intake import upsert_intake_step
from app.services.prescreen import save_prescreen_answers
from app.services.qa import run_qa

TEMPLATE_DIR = DEFAULT_I485_TEMPLATE_PATH.parent
FORM_FILES = {
    "i485": "i-485.pdf",
    "i130": "i-130.pdf",
    "i130a": "i-130a.pdf",
    "i765": "i-765.pdf",
    "i131": "i-131.pdf",
    "i864": "i-864.pdf",
    "g1145": "g-1145.pdf",
    "g1450": "g-1450.pdf",
    "g1650": "g-1650.pdf",
}
# Preparer, interpreter, and attorney blocks belong to someone other than the applicant.
THIRD_PARTY_FIELD_MARKERS = ("attorney", "accredited representative", "interpreter", "preparer", "volag")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a case whose answers reach every mapped PDF field, then generate and audit each form."
    )
    parser.add_argument("--case-name", default="Full PDF coverage sample (Restrepo)")
    parser.add_argument("--output-dir", default=None, help="Where PDFs, the report, and page images go.")
    parser.add_argument("--render", action="store_true", help="Also render every page to PNG for visual review.")
    parser.add_argument("--dpi", type=int, default=110, help="Resolution for rendered pages.")
    parser.add_argument("--web-base-url", default="http://localhost:3000")
    return parser


def _create_case(session: Session, case_name: str) -> CaseRecord:
    answers = full_coverage_answers()
    case = CaseRecord(
        case_name=case_name,
        workflow_type="marriage_concurrent",
        petitioner_email=answers["petitioner_email"],
        beneficiary_email=answers["beneficiary_email"],
        country_of_focus="CO",
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


def seed_full_coverage_case(session: Session, case: CaseRecord) -> None:
    """Saves the persona's intake, prescreen, I-485, and supplemental form answers on a case."""
    upsert_intake_step(session, case.id, "full_coverage_sample", full_coverage_answers())
    save_prescreen_answers(session, case.id, FULL_COVERAGE_PRESCREEN_ANSWERS)
    i485_answers = build_full_coverage_i485_answers()
    for page in I485_QUESTIONNAIRE:
        page_answers = {question["id"]: i485_answers[question["id"]] for question in page["questions"]}
        save_i485_page_answers(session, case.id, page["id"], page_answers)
    for form_key in FULL_COVERAGE_FORM_KEYS:
        for page_id, page_answers in build_full_coverage_form_answers(form_key).items():
            save_form_page_answers(session, case.id, form_key, page_id, page_answers)
    session.commit()


def generate_full_coverage_pdfs(session: Session, case_id: UUID, output_dir: Path) -> dict[str, dict[str, Any]]:
    """Writes every form for the case as a review draft and returns what each generator reported."""
    output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict[str, Any]] = {}

    i485 = generate_i485_pdf(session=session, case_id=case_id, output_path=output_dir / "i-485.pdf")
    results["i485"] = {
        "path": i485.output_path,
        "generation_status": i485.generation_status,
        "unmapped_answered_questions": i485.unmapped_answered_questions,
        "warnings": i485.warnings,
    }
    for form_key in FULL_COVERAGE_FORM_KEYS:
        result = generate_form_pdf(
            session=session, case_id=case_id, form_key=form_key, output_path=output_dir / FORM_FILES[form_key]
        )
        results[form_key] = {
            "path": result.output_path,
            "generation_status": result.generation_status,
            "unmapped_answered_questions": result.unmapped_answered_questions,
            "warnings": result.warnings,
        }

    g1145 = generate_g1145_pdf(case_id=case_id, values=full_coverage_answers(), output_path=output_dir / "g-1145.pdf")
    results["g1145"] = {"path": g1145.output_path, "warnings": g1145.warnings}
    g1450 = generate_g1450_pdf_from_payload(
        payload=FULL_COVERAGE_CARD_PAYMENT,
        template_path=TEMPLATE_DIR / FORM_FILES["g1450"],
        output_path=output_dir / "g-1450.pdf",
    )
    results["g1450"] = {"path": g1450.output_path, "warnings": []}
    g1650 = generate_g1650_pdf_from_payload(
        payload={**FULL_COVERAGE_BANK_PAYMENT, "authorized_amount": FULL_COVERAGE_CARD_PAYMENT["authorized_amount"]},
        template_path=TEMPLATE_DIR / FORM_FILES["g1650"],
        output_path=output_dir / "g-1650.pdf",
    )
    results["g1650"] = {"path": g1650.output_path, "warnings": []}
    return results


def _widget_fields(path: Path) -> list[dict[str, Any]]:
    fields = []
    for page_number, page in enumerate(PdfReader(path).pages, start=1):
        for annotation_ref in page.get("/Annots") or []:
            annotation = annotation_ref.get_object()
            if annotation.get("/Subtype") != "/Widget":
                continue
            parent = annotation["/Parent"].get_object() if annotation.get("/Parent") else {}
            field_type = annotation.get("/FT") or parent.get("/FT")
            name = str(annotation.get("/T") or parent.get("/T") or "")
            tooltip = " ".join(str(annotation.get("/TU") or parent.get("/TU") or "").split())
            if field_type == "/Btn":
                filled = str(annotation.get("/AS") or "/Off") != "/Off"
            elif field_type in {"/Tx", "/Ch"}:
                value = annotation.get("/V") if annotation.get("/V") is not None else parent.get("/V")
                filled = bool(value is not None and str(value).strip())
            else:
                continue
            read_only = bool(int(annotation.get("/Ff") or parent.get("/Ff") or 0) & 1)
            fields.append(
                {
                    "page": page_number,
                    "name": name,
                    "type": "checkbox" if field_type == "/Btn" else "text",
                    "filled": filled,
                    "read_only": read_only,
                    "tooltip": tooltip,
                }
            )
    return fields


def _blank_reason(field: dict[str, Any]) -> str | None:
    tooltip = field["tooltip"].lower()
    if any(marker in tooltip for marker in THIRD_PARTY_FIELD_MARKERS):
        return "third_party"
    if "signature" in tooltip or "date of signature" in tooltip:
        return "signed_by_hand"
    return None


def coverage_report(results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Counts filled text fields per form and lists the blank ones a reviewer should look at."""
    report: dict[str, Any] = {}
    for form_key, result in results.items():
        fields = _widget_fields(Path(result["path"]))
        text_fields = [field for field in fields if field["type"] == "text"]
        blank = [field for field in text_fields if not field["filled"]]
        expected_blank = [field for field in blank if _blank_reason(field)]
        review_blank = [field for field in blank if not _blank_reason(field)]
        report[form_key] = {
            "path": str(result["path"]),
            "generation_status": result.get("generation_status", "payload"),
            "pages": max((field["page"] for field in fields), default=0),
            "text_fields": len(text_fields),
            "text_fields_filled": len(text_fields) - len(blank),
            "checkboxes_checked": sum(1 for field in fields if field["type"] == "checkbox" and field["filled"]),
            "blank_third_party_or_signature": len(expected_blank),
            "blank_to_review": [
                {"page": field["page"], "field": field["name"], "tooltip": field["tooltip"][:160]}
                for field in review_blank
            ],
            "unmapped_answered_questions": [
                entry["question_id"] for entry in result.get("unmapped_answered_questions", [])
            ],
            "warnings": [warning for warning in result.get("warnings", []) if "not legal advice" not in warning],
        }
    return report


def render_pages(results: dict[str, dict[str, Any]], output_dir: Path, dpi: int) -> list[str]:
    """Renders each generated page to PNG with saved appearances, the way a printer would draw them."""
    import pypdfium2

    image_dir = output_dir / "pages"
    image_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for form_key, result in results.items():
        document = pypdfium2.PdfDocument(str(result["path"]))
        document.init_forms()
        for index in range(len(document)):
            image = document[index].render(scale=dpi / 72, may_draw_forms=True).to_pil()
            path = image_dir / f"{form_key}-p{index + 1:02d}.png"
            image.save(path)
            written.append(str(path))
        document.close()
    return written


def main() -> None:
    args = build_parser().parse_args()
    create_db_and_tables()

    with Session(engine) as session:
        case = _create_case(session, args.case_name)
        seed_full_coverage_case(session, case)
        checklist_items, _ = generate_checklist(session, case.id)
        qa_issues, qa_summary = run_qa(session, case.id)
        output_dir = Path(args.output_dir) if args.output_dir else settings.generated_dir / f"full-coverage-{case.id}"
        results = generate_full_coverage_pdfs(session, case.id, output_dir)

    report = coverage_report(results)
    report_path = output_dir / "coverage-report.json"
    report_path.write_text(json.dumps(report, indent=2))
    images = render_pages(results, output_dir, args.dpi) if args.render else []

    base_url = args.web_base_url.rstrip("/")
    print(
        json.dumps(
            {
                "case_id": str(case.id),
                "case_url": f"{base_url}/?caseId={case.id}",
                "i485_url": f"{base_url}/i485-ingestion?caseId={case.id}",
                "checklist_items": len(checklist_items),
                "qa_issue_count": len(qa_issues),
                "qa_summary": qa_summary,
                "output_dir": str(output_dir),
                "report": str(report_path),
                "rendered_pages": len(images),
                "forms": {
                    form_key: {
                        "status": entry["generation_status"],
                        "text_filled": f"{entry['text_fields_filled']}/{entry['text_fields']}",
                        "checkboxes_checked": entry["checkboxes_checked"],
                        "blank_to_review": len(entry["blank_to_review"]),
                        "unmapped_answers": entry["unmapped_answered_questions"],
                    }
                    for form_key, entry in report.items()
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
