from __future__ import annotations

PACKET_ASSEMBLY_GUIDANCE_VERIFIED_ON = "2026-05-09"
PACKET_OUTLINE_SOURCE_PATH = "i-485-complete-package-req.md"

PACKET_ASSEMBLY_GUIDANCE_SOURCES = [
    {
        "label": "USCIS Tips for Filing Forms by Mail",
        "url": "https://www.uscis.gov/forms/filing-guidance/tips-for-filing-forms-by-mail",
        "last_reviewed": "2025-04-24",
        "verified_on": PACKET_ASSEMBLY_GUIDANCE_VERIFIED_ON,
        "use": "Source for mail packet order: payment first, then G-1145 if used, then the filed form, supplements, and supporting documents; also source for cover-letter marking, single-sided letter-size pages, legible copies, translations, and optional support-page numbering.",
    },
    {
        "label": "USCIS Recommendations for Paper Filings to Avoid Scanning Delays",
        "url": "https://www.uscis.gov/newsroom/alerts/recommendations-for-paper-filings-to-avoid-scanning-delays",
        "last_reviewed": "2023-02-24",
        "verified_on": PACKET_ASSEMBLY_GUIDANCE_VERIFIED_ON,
        "use": "Source for scanner-friendly assembly warnings: avoid binders, folders, tabs, sticky notes, staples, duplicate evidence copies, folded pages, albums, scrapbooks, digital media, and unnecessary originals.",
    },
    {
        "label": "USCIS Form G-1450",
        "url": "https://www.uscis.gov/g-1450",
        "last_reviewed": "2024-04-03",
        "verified_on": PACKET_ASSEMBLY_GUIDANCE_VERIFIED_ON,
        "use": "Source for placing Form G-1450 on top of the application, petition, or request when paying by credit card.",
    },
    {
        "label": "USCIS Form G-1650",
        "url": "https://www.uscis.gov/g-1650",
        "last_reviewed": "2026-06-03",
        "verified_on": "2026-10-30",
        "use": "Source for placing Form G-1650 on top of the application, petition, or request when paying from a U.S. bank account.",
    },
    {
        "label": "USCIS Filing Fees",
        "url": "https://www.uscis.gov/forms/filing-fees",
        "last_reviewed": "2025-09-18",
        "verified_on": PACKET_ASSEMBLY_GUIDANCE_VERIFIED_ON,
        "use": "Source for current paper-payment handling guidance and separate payment caution for multiple forms.",
    },
    {
        "label": "USCIS Form I-485 Initial Evidence Checklist",
        "url": "https://www.uscis.gov/forms/filing-guidance/checklist-of-required-initial-evidence-for-form-i-485-for-informational-purposes-only",
        "last_reviewed": None,
        "verified_on": PACKET_ASSEMBLY_GUIDANCE_VERIFIED_ON,
        "use": "Source for the I-485-centered supporting-evidence grouping used by this packet compiler.",
    },
]

I485_PACKET_GENERATED_FORMS = ("g1145", "i485", "i864", "i765", "i131")

I485_PACKET_PAYMENT_CHECKLIST_ORDER = (
    "form_i485",
    "form_i765",
    "form_i131",
)

I485_PACKET_PAYMENT_UPLOAD_CODES = (
    "payment_g1450",
)

I485_PACKET_UPLOAD_ORDER = {
    "payment_g1450": 20,
    "form_g1145": 30,
    "beneficiary_passport_photos": 100,
    "form_i485": 110,
    "beneficiary_passport_bio": 120,
    "beneficiary_visa_or_entry_stamp": 130,
    "beneficiary_i94": 140,
    "beneficiary_birth_certificate": 150,
    "translation_certification": 160,
    "i130_receipt_notice": 170,
    "marriage_certificate": 180,
    "prior_marriage_termination_records": 190,
    "joint_bank_statement": 200,
    "joint_lease": 210,
    "utility_bills": 220,
    "photos_together": 230,
    "affidavits": 240,
    "form_i864": 300,
    "sponsor_tax_return": 310,
    "sponsor_w2_1099": 320,
    "sponsor_pay_stubs": 330,
    "employment_verification_letter": 340,
    "medical_exam_i693": 400,
    "form_i765": 500,
    "form_i131": 700,
    "travel_explanation_i131": 710,
}

I485_PACKET_EXCLUDED_UPLOAD_CODES = {
    "form_i130",
    "form_i130a",
    "petitioner_citizenship_proof",
    "medical_exam_supporting_records",
}

I485_SECTION_UPLOAD_CODES = (
    "beneficiary_passport_photos",
    "form_i485",
    "beneficiary_passport_bio",
    "beneficiary_visa_or_entry_stamp",
    "beneficiary_i94",
    "beneficiary_birth_certificate",
    "translation_certification",
    "i130_receipt_notice",
    "marriage_certificate",
    "prior_marriage_termination_records",
    "joint_bank_statement",
    "joint_lease",
    "utility_bills",
    "photos_together",
    "affidavits",
)

I864_SECTION_UPLOAD_CODES = (
    "form_i864",
    "sponsor_tax_return",
    "sponsor_w2_1099",
    "sponsor_pay_stubs",
    "employment_verification_letter",
)

I765_SECTION_UPLOAD_CODES = (
    "form_i765",
    "beneficiary_passport_photos",
    "beneficiary_passport_bio",
    "beneficiary_i94",
)

I131_SECTION_UPLOAD_CODES = (
    "form_i131",
    "beneficiary_passport_photos",
    "beneficiary_passport_bio",
    "beneficiary_i94",
    "travel_explanation_i131",
)
