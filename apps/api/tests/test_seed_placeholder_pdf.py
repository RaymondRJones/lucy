from __future__ import annotations

from pypdf import PdfReader

from app.cli.seed_placeholder_pdf import packet_section_for_checklist_code, write_seed_placeholder_pdf


def test_seed_placeholder_pdf_labels_section_category_and_placeholder(tmp_path):
    output_path = tmp_path / "sample-placeholder.pdf"

    write_seed_placeholder_pdf(
        output_path,
        section="I-485 section",
        category="civil_document",
        label="Beneficiary birth certificate with certified English translation",
        code="beneficiary_birth_certificate",
    )

    text = PdfReader(output_path).pages[0].extract_text()

    assert "[SECTION: I-485 section]" in text
    assert "[CATEGORY: civil_document]" in text
    assert "PLACEHOLDER" in text
    assert "Beneficiary birth certificate" in text
    assert "Checklist code: beneficiary_birth_certificate" in text


def test_packet_section_for_checklist_code_uses_packet_outline_groupings():
    assert packet_section_for_checklist_code("form_i485") == "I-485 section"
    assert packet_section_for_checklist_code("sponsor_tax_return") == "I-864 section"
    assert packet_section_for_checklist_code("medical_exam_i693") == "I-693 medical section"
    assert packet_section_for_checklist_code("form_i765") == "I-765 section"
    assert packet_section_for_checklist_code("form_i131") == "I-131 section"
    assert packet_section_for_checklist_code("beneficiary_i94") == "I-485 / I-765 / I-131 sections"
