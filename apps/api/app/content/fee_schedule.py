"""USCIS fee schedule used for payment forms."""

from __future__ import annotations

FEE_SCHEDULE_VERIFIED_ON = "2026-10-30"
# Current editions listed at https://www.uscis.gov/g-1450 and https://www.uscis.gov/g-1650, verified 2026-10-30.
G1450_FORM_EDITION = "02/06/26"
G1650_FORM_EDITION = "06/03/25"
FEE_SCHEDULE_EDITION = "10/26/26"
FEE_SCHEDULE_SOURCE_URL = "https://www.uscis.gov/sites/default/files/document/forms/g-1055.pdf"
FILING_FEES_SOURCE_URL = "https://www.uscis.gov/forms/filing-fees"
FILING_FEES_SOURCE_LAST_REVIEWED = "2026-02-12"

G1450_FORM_FEES = {
    "form_i130": {
        "form_code": "I-130",
        "label": "Form I-130",
        "paper_fee": "675.00",
        "filing_category": "General filing, paper filing",
        "source_url": FEE_SCHEDULE_SOURCE_URL,
        "verified_on": FEE_SCHEDULE_VERIFIED_ON,
        "source_edition": FEE_SCHEDULE_EDITION,
    },
    "form_i485": {
        "form_code": "I-485",
        "label": "Form I-485",
        "paper_fee": "1440.00",
        "filing_category": "General filing, applicant over age 14, paper filing",
        "source_url": FEE_SCHEDULE_SOURCE_URL,
        "verified_on": FEE_SCHEDULE_VERIFIED_ON,
        "source_edition": FEE_SCHEDULE_EDITION,
    },
    "form_i765": {
        "form_code": "I-765",
        "label": "Form I-765",
        "paper_fee": "260.00",
        "filing_category": "Paper filing with paid Form I-485 filed on or after April 1, 2024 and pending",
        "source_url": FEE_SCHEDULE_SOURCE_URL,
        "verified_on": FEE_SCHEDULE_VERIFIED_ON,
        "source_edition": FEE_SCHEDULE_EDITION,
    },
    "form_i131": {
        "form_code": "I-131",
        "label": "Form I-131",
        "paper_fee": "630.00",
        "filing_category": "Advance parole document for individuals inside the United States with pending Form I-485, paper filing",
        "source_url": FEE_SCHEDULE_SOURCE_URL,
        "verified_on": FEE_SCHEDULE_VERIFIED_ON,
        "source_edition": FEE_SCHEDULE_EDITION,
    },
    "form_i130a": {
        "form_code": "I-130A",
        "label": "Form I-130A",
        "paper_fee": "0.00",
        "filing_category": "Supplemental spouse-beneficiary form submitted with Form I-130",
        "source_url": "https://www.uscis.gov/i-130",
        "verified_on": FEE_SCHEDULE_VERIFIED_ON,
        "source_edition": FEE_SCHEDULE_EDITION,
    },
    "form_i864": {
        "form_code": "I-864",
        "label": "Form I-864",
        "paper_fee": "0.00",
        "filing_category": "General filing",
        "source_url": FEE_SCHEDULE_SOURCE_URL,
        "verified_on": FEE_SCHEDULE_VERIFIED_ON,
        "source_edition": FEE_SCHEDULE_EDITION,
    },
    "medical_exam_i693": {
        "form_code": "I-693",
        "label": "Form I-693",
        "paper_fee": "0.00",
        "filing_category": "Medical exam form submitted with Form I-485",
        "source_url": "https://www.uscis.gov/i-693",
        "verified_on": FEE_SCHEDULE_VERIFIED_ON,
        "source_edition": FEE_SCHEDULE_EDITION,
    },
    "form_g1145": {
        "form_code": "G-1145",
        "label": "Form G-1145",
        "paper_fee": "0.00",
        "filing_category": "Optional e-notification request",
        "source_url": "https://www.uscis.gov/g-1145",
        "verified_on": FEE_SCHEDULE_VERIFIED_ON,
        "source_edition": FEE_SCHEDULE_EDITION,
    },
}

G1450_PAYMENT_NOTE = (
    "USCIS says mailed forms are paid by card with Form G-1450 or by U.S. bank account with Form G-1650; "
    "paper payment requires a Form G-1651 exemption. USCIS recommends paying each filing fee separately, "
    "so Lucy creates a separate payment PDF for each payable form. Sources verified 2026-10-30: "
    "https://www.uscis.gov/g-1650 and https://www.uscis.gov/forms/filing-guidance/tips-for-filing-forms-by-mail."
)
