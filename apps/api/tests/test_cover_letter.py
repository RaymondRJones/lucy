from __future__ import annotations

from datetime import date
from uuid import uuid4

from pypdf import PdfReader

from app.services.cover_letter import build_cover_letter_lines, generate_cover_letter_pdf


def test_cover_letter_lines_include_case_identifiers_and_packet_index():
    lines = build_cover_letter_lines(
        values={
            "petitioner_first_name": "Jordan",
            "petitioner_last_name": "Petitioner",
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Garcia",
            "beneficiary_current_address_line1": "123 Sample Street",
            "beneficiary_current_city": "Oakland",
            "beneficiary_current_state": "CA",
            "beneficiary_current_zip": "94612",
            "i130_receipt_number": "IOE1234567890",
        },
        sections=[
            {"label": "Payment", "items": ["Form G-1450 payment for Form I-485"]},
            {"label": "I-485 section", "items": ["Form I-485", "Beneficiary passport biographic page"]},
        ],
        lockbox_address_lines=["USCIS", "Attn: AOS", "P.O. Box 805887", "Chicago, IL 60680"],
        generated_on=date(2026, 4, 30),
    )

    joined = "\n".join(lines)

    assert "April 30, 2026" in joined
    assert "123 Sample Street" in joined
    assert "Oakland, CA 94612" in joined
    assert "U.S. Citizenship and Immigration Services" in joined
    assert "Chicago, IL 60680" in joined
    assert "RE: Form I-485 Adjustment of Status (Marriage-Based)" in joined
    assert "Applicant (Beneficiary): Avery Garcia" in joined
    assert "Petitioner (U.S. Citizen Spouse): Jordan Petitioner" in joined
    assert "I-130 Receipt Number: IOE1234567890" in joined
    assert "Dear Sir or Madam," in joined
    assert "Contents of Submission" in joined
    assert "1. Payment" in joined
    assert "2. Form I-485 (Application to Adjust Status)" in joined
    assert "Form G-1450 payment for Form I-485" in joined
    assert "X________________________________" in joined
    assert "[Signature]" not in joined


def test_cover_letter_lines_use_receipt_placeholder_when_missing():
    lines = build_cover_letter_lines(values={}, sections=[], generated_on=date(2026, 4, 30))
    joined = "\n".join(lines)

    assert "[Your Address]" in joined
    assert "[Lockbox Address - depends on your filing location]" in joined
    assert "Applicant (Beneficiary): [insert beneficiary name]" in joined
    assert "Petitioner (U.S. Citizen Spouse): [insert petitioner name]" in joined
    assert "I-130 Receipt Number: [insert Form I-130 receipt number]" in joined


def test_generate_cover_letter_pdf_writes_extractable_review_draft(tmp_path):
    result = generate_cover_letter_pdf(
        case_id=uuid4(),
        values={
            "petitioner_first_name": "Jordan",
            "petitioner_last_name": "Petitioner",
            "beneficiary_first_name": "Avery",
            "beneficiary_last_name": "Garcia",
            "i130_receipt_number": "IOE1234567890",
        },
        sections=[{"label": "I-864 section", "items": ["Form I-864", "Most recent tax return"]}],
        output_dir=tmp_path,
    )

    reader = PdfReader(result.output_path)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert result.output_path.exists()
    assert result.output_path.name.endswith("-cover-letter.pdf")
    assert "RE: Form I-485 Adjustment of Status (Marriage-Based)" in text
    assert "Dear Sir or Madam" in text
    assert "IOE1234567890" in text
    assert "Form I-864 (Affidavit of Support)" in text
    assert "X________________________________" in text
    assert "[Signature]" not in text
    assert result.warnings == [
        "Cover letter: confirm the Form I-130 status and receipt number, and hand-sign if you use the draft.",
    ]


def test_cover_letter_does_not_call_a_denied_petition_pending():
    joined = "\n".join(
        build_cover_letter_lines(
            values={"i130_filing_status": "denied_revoked_withdrawn"},
            sections=[],
            generated_on=date(2026, 11, 1),
        )
    )

    assert "pending" not in joined
    assert "[state the current status of the Form I-130 before filing]" in " ".join(joined.split())
