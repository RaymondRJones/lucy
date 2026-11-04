"""USCIS requirement metadata with sources and verification dates."""

from __future__ import annotations

VERIFIED_ON = "2026-04-27"
I131_REQUIREMENTS_VERIFIED_ON = "2026-04-29"
I485_I864_REQUIREMENTS_VERIFIED_ON = "2026-10-30"


def _evidence(
    checklist_code: str,
    label: str,
    necessity: str,
    requirement_type: str,
    notes: str,
    conditional_note: str | None = None,
) -> dict[str, str]:
    payload = {
        "checklist_code": checklist_code,
        "label": label,
        "necessity": necessity,
        "requirement_type": requirement_type,
        "notes": notes,
    }
    if conditional_note:
        payload["conditional_note"] = conditional_note
    return payload


GENERAL_USCIS_RULES = [
    {
        "code": "concurrent_filing",
        "label": "Concurrent filing",
        "verified_on": VERIFIED_ON,
        "official_url": "https://www.uscis.gov/green-card/green-card-processes-and-procedures/concurrent-filing-of-form-i-485",
        "summary": "Immediate relatives of U.S. citizens may file Form I-130 and Form I-485 together when otherwise eligible.",
        "important_notes": [
            "USCIS treats the forms as concurrently filed when they are mailed together or when Form I-485 is filed while the immigrant petition is still pending.",
            "A spouse of a U.S. citizen falls in the immediate-relative category, so visa availability is not numerically capped.",
        ],
        "fee_url": None,
    },
    {
        "code": "paper_payment_handling",
        "label": "Paper filing payment handling",
        "verified_on": VERIFIED_ON,
        "official_url": "https://www.uscis.gov/forms/filing-fees",
        "summary": "USCIS requires the correct current fee and warns that multiple forms should not share a single combined payment.",
        "important_notes": [
            "Before mailing, confirm the live USCIS fee calculator or fee schedule for every form in the packet.",
            "USCIS warns that it may reject a package when multiple forms are submitted with a single combined payment.",
        ],
        "fee_url": "https://www.uscis.gov/feecalculator",
    },
]

USCIS_REQUIREMENTS = [
    {
        "code": "form_i130",
        "label": "Form I-130",
        "accepted_edition": "04/01/24",
        "verified_on": VERIFIED_ON,
        "official_url": "https://www.uscis.gov/i-130",
        "summary": "Petition for Alien Relative used by a U.S. citizen or lawful permanent resident to establish the qualifying relationship.",
        "important_notes": [
            "For a spouse beneficiary, USCIS says Form I-130A must also be submitted.",
            "For Part 4, USCIS says the petitioner should choose only one path: adjustment of status inside the United States or consular processing abroad.",
        ],
        "fee_url": "https://www.uscis.gov/feecalculator?form=i-130",
        "initial_evidence": [
            _evidence(
                "form_i130",
                "Completed Form I-130",
                "required",
                "form",
                "The family-based petition itself.",
            ),
            _evidence(
                "form_i130a",
                "Form I-130A for the spouse beneficiary",
                "required",
                "form",
                "USCIS requires the spouse beneficiary supplement when petitioning for a husband or wife.",
            ),
            _evidence(
                "petitioner_citizenship_proof",
                "Petitioner proof of U.S. citizenship or status",
                "required",
                "identity_document",
                "Examples on the USCIS I-130 page include a U.S. birth certificate, unexpired U.S. passport, naturalization or citizenship certificate, CRBA, or green card evidence for an LPR petitioner.",
            ),
            _evidence(
                "marriage_certificate",
                "Marriage certificate",
                "required",
                "civil_document",
                "Proof of the qualifying marital relationship.",
            ),
            _evidence(
                "prior_marriage_termination_records",
                "Proof any prior marriages legally ended",
                "conditional",
                "civil_document",
                "Use divorce decrees, annulment orders, or death certificates for each prior marriage.",
                "Only needed if either spouse had a prior marriage.",
            ),
            _evidence(
                "joint_lease",
                "Shared residence evidence",
                "recommended",
                "marriage_evidence",
                "One common form of bona fide marriage evidence listed by USCIS.",
            ),
            _evidence(
                "utility_bills",
                "Shared utility bills or household bills",
                "recommended",
                "marriage_evidence",
                "Recent shared household evidence can supplement stronger joint documents such as a lease or bank account.",
            ),
            _evidence(
                "joint_bank_statement",
                "Shared financial evidence",
                "recommended",
                "marriage_evidence",
                "Documentation showing combined financial resources is one of the marriage-evidence examples USCIS lists.",
            ),
            _evidence(
                "photos_together",
                "Relationship photos",
                "recommended",
                "marriage_evidence",
                "Photos are not always required, but they can help tell the story of the relationship.",
            ),
            _evidence(
                "affidavits",
                "Affidavits from people who know the marriage",
                "recommended",
                "marriage_evidence",
                "Optional third-party affidavits can support bona fide marriage evidence when used carefully.",
            ),
        ],
    },
    {
        "code": "form_i130a",
        "label": "Form I-130A",
        "accepted_edition": "04/01/24",
        "verified_on": VERIFIED_ON,
        "official_url": "https://www.uscis.gov/i-130",
        "summary": "Supplemental spouse-beneficiary information that USCIS expects with a spouse-based Form I-130 filing.",
        "important_notes": [
            "USCIS lists Form I-130A together with Form I-130 on the spouse-beneficiary filing flow.",
            "If the spouse beneficiary lives abroad, USCIS still expects the form even though the signature rule is different.",
        ],
        "fee_url": None,
        "initial_evidence": [
            _evidence(
                "form_i130a",
                "Completed Form I-130A",
                "required",
                "form",
                "This supplement captures the spouse beneficiary's address, employment, and biographic history.",
            ),
        ],
    },
    {
        "code": "form_i485",
        "label": "Form I-485",
        "accepted_edition": "09/18/26",
        "verified_on": I485_I864_REQUIREMENTS_VERIFIED_ON,
        "official_url": "https://www.uscis.gov/i-485",
        "summary": "Application to adjust status inside the United States.",
        "important_notes": [
            "USCIS says it rejects the 01/20/25 and 09/04/26 editions if postmarked or electronically submitted on or after Sept. 18, 2026, with no grace period.",
            "The 09/18/26 edition revises the Part 9 public charge questions, including Item 63 on any means-tested public benefit, and renumbers later Part 9 items.",
            "USCIS says where to file depends on the eligibility category and directs applicants to the I-485 filing-address page.",
            "Lockbox filings may not immediately display an A-Number on the receipt notice because of a USCIS process change.",
        ],
        "fee_url": "https://www.uscis.gov/feecalculator?form=i-485",
        "initial_evidence": [
            _evidence(
                "form_i485",
                "Completed Form I-485",
                "required",
                "form",
                "The adjustment-of-status application itself.",
            ),
            _evidence(
                "beneficiary_passport_photos",
                "Two passport-style photos",
                "required",
                "identity_document",
                "The USCIS I-485 initial-evidence checklist for immediate relatives lists two passport-style photographs.",
            ),
            _evidence(
                "beneficiary_passport_bio",
                "Government-issued photo ID",
                "required",
                "identity_document",
                "Lucy tracks the beneficiary passport biographic page as the clearest government-issued photo-ID upload.",
            ),
            _evidence(
                "beneficiary_birth_certificate",
                "Birth certificate",
                "required",
                "civil_document",
                "If the birth certificate is unavailable or nonexistent, USCIS allows alternate evidence plus proof of unavailability.",
            ),
            _evidence(
                "translation_certification",
                "Certified English translation for non-English civil records",
                "conditional",
                "civil_document",
                "USCIS requires a full English translation and translator certification when a supporting civil document is not in English.",
                "Only needed when at least one required civil record is not in English.",
            ),
            _evidence(
                "beneficiary_i94",
                "Inspection and admission or parole documentation",
                "required",
                "identity_document",
                "A copy of the Form I-94 or comparable inspection/parole evidence is standard initial evidence for most immediate-relative adjustment filings.",
            ),
            _evidence(
                "beneficiary_visa_or_entry_stamp",
                "Passport visa page or admission stamp",
                "recommended",
                "identity_document",
                "Helpful supporting entry evidence when available.",
            ),
            _evidence(
                "medical_exam_i693",
                "Form I-693 medical exam packet",
                "required",
                "medical_document",
                "USCIS says Form I-693, or a permitted partial I-693 when applicable, must be submitted with Form I-485.",
            ),
            _evidence(
                "i130_receipt_notice",
                "Form I-797 receipt notice for pending Form I-130",
                "conditional",
                "case_status",
                "When Form I-485 is filed after the spouse petition has already been submitted, include the pending Form I-130 receipt notice as the immigrant-category basis.",
                "Needed when the I-130 is already pending instead of being included in the same paper packet.",
            ),
        ],
    },
    {
        "code": "form_i693",
        "label": "Form I-693",
        "accepted_edition": "01/20/25",
        "verified_on": VERIFIED_ON,
        "official_url": "https://www.uscis.gov/i-693",
        "summary": "Medical examination and vaccination record used with adjustment-of-status filings.",
        "important_notes": [
            "Effective Dec. 2, 2024, USCIS says applicants who need Form I-693 must submit it, or a permitted partial Form I-693, together with Form I-485.",
            "If the civil surgeon signs on or after July 3, 2025, USCIS says it accepts only the 01/20/25 edition.",
        ],
        "fee_url": None,
        "initial_evidence": [
            _evidence(
                "medical_exam_i693",
                "Completed Form I-693 packet",
                "required",
                "medical_document",
                "The sealed medical exam packet, or a permitted partial I-693 when USCIS instructions allow one.",
            ),
            _evidence(
                "medical_exam_supporting_records",
                "Vaccination or medical records for the civil surgeon",
                "recommended",
                "medical_support",
                "Helpful preparation evidence for the appointment, but not a substitute for the final I-693 packet.",
            ),
        ],
    },
    {
        "code": "form_i864",
        "label": "Form I-864",
        "accepted_edition": "08/24/26",
        "verified_on": I485_I864_REQUIREMENTS_VERIFIED_ON,
        "official_url": "https://www.uscis.gov/i-864",
        "summary": "Affidavit of Support that documents the sponsor's financial ability to support the intending immigrant.",
        "important_notes": [
            "USCIS says it only accepts the 08/24/26 edition beginning Oct. 1, 2026, and will not process the 10/17/24 edition postmarked or electronically submitted on or after that date.",
            "The 08/24/26 edition adds a sponsor authorization for USCIS to obtain consumer report information. USCIS says sponsors with a credit or security freeze should respond promptly to any request to release it.",
            "USCIS says sponsors should include the most recent federal income tax return and related income evidence or explain why a return was not required.",
            "If a supporting document is not in English, USCIS says a full English translation and translator certification must be included.",
        ],
        "fee_url": "https://www.uscis.gov/feecalculator?form=i-864",
        "initial_evidence": [
            _evidence(
                "form_i864",
                "Completed Form I-864",
                "required",
                "form",
                "The affidavit of support itself.",
            ),
            _evidence(
                "sponsor_tax_return",
                "Most recent federal income tax return",
                "required",
                "financial_document",
                "USCIS lists the most recent federal income tax return and related tax evidence as core initial evidence, or an explanation of why no return was required.",
            ),
            _evidence(
                "sponsor_w2_1099",
                "W-2s or 1099s for the most recent tax year",
                "recommended",
                "financial_document",
                "Include related income statements when using a full tax return rather than an IRS transcript.",
            ),
            _evidence(
                "sponsor_pay_stubs",
                "Recent pay stubs",
                "recommended",
                "financial_document",
                "Recent pay records can help prove that the sponsor's current income is ongoing.",
            ),
            _evidence(
                "employment_verification_letter",
                "Employment verification letter",
                "recommended",
                "financial_document",
                "An employer letter can reinforce current income and job continuity when useful.",
            ),
        ],
    },
    {
        "code": "form_i765",
        "label": "Form I-765",
        "accepted_edition": "08/21/25",
        "verified_on": VERIFIED_ON,
        "official_url": "https://www.uscis.gov/i-765",
        "summary": "Application for employment authorization while the adjustment case is pending.",
        "important_notes": [
            "The live USCIS form page showed the 08/21/25 accepted edition when verified on April 27, 2026.",
            "USCIS says the filing address depends on the eligibility category and, when filed with another paper form, applicants should follow the other form's filing location rules.",
        ],
        "fee_url": "https://www.uscis.gov/feecalculator?form=i-765",
        "initial_evidence": [
            _evidence(
                "form_i765",
                "Completed Form I-765",
                "required",
                "form",
                "The employment authorization application itself.",
            ),
            _evidence(
                "beneficiary_i94",
                "Form I-94 or comparable arrival/travel-document evidence",
                "required",
                "identity_document",
                "The USCIS initial-evidence checklist includes the Form I-94, a printout of the electronic I-94, passport, or other travel document as general supporting evidence.",
            ),
            _evidence(
                "beneficiary_passport_bio",
                "Passport or other travel-document identity page",
                "required",
                "identity_document",
                "This workspace tracks the passport biographic page as the clearest shared identity and travel-document upload.",
            ),
            _evidence(
                "form_i485",
                "Underlying Form I-485 filing or pending I-485 evidence",
                "conditional",
                "case_status",
                "For category (c)(9), USCIS says applicants filing later should include evidence of a pending Form I-485 such as the receipt notice.",
                "When filing Form I-765 together with Form I-485, the packet itself can satisfy this underlying-case requirement.",
            ),
        ],
    },
    {
        "code": "form_i131",
        "label": "Form I-131",
        "accepted_edition": "01/20/25",
        "verified_on": I131_REQUIREMENTS_VERIFIED_ON,
        "official_url": "https://www.uscis.gov/i-131",
        "summary": "Application for travel documents, including advance parole when tied to a pending adjustment case.",
        "important_notes": [
            "USCIS says fees changed for certain cases after July 22, 2025 and instructs applicants to use the current fee schedule.",
            "USCIS says applicants filing multiple paper forms should pay each fee separately.",
            "Form I-131 Instructions edition 01/20/25 were checked on 2026-04-29 for the pending-I-485 advance parole evidence notes used by this app.",
        ],
        "fee_url": "https://www.uscis.gov/feecalculator?form=i-131",
        "initial_evidence": [
            _evidence(
                "form_i131",
                "Completed Form I-131",
                "required",
                "form",
                "The advance parole application itself.",
            ),
            _evidence(
                "beneficiary_passport_photos",
                "Two passport-style photos",
                "required",
                "identity_document",
                "The Form I-131 instructions say applicants in the United States filing for an advance parole document must submit two identical passport-style photographs.",
            ),
            _evidence(
                "beneficiary_passport_bio",
                "Official photo identity document",
                "required",
                "identity_document",
                "The Form I-131 instructions say all applications must include a copy of an official photo identity document showing photo, name, and date of birth; examples include a passport identity page, EAD, driver's license, permanent resident card, or other official identity document.",
            ),
            _evidence(
                "beneficiary_i94",
                "Current status or I-94 evidence",
                "required",
                "identity_document",
                "For advance parole applicants in the United States, the Form I-131 instructions say to attach a copy of any USCIS document showing current status, if any, and the form itself asks for class of admission and I-94 details when applicable.",
            ),
            _evidence(
                "travel_explanation_i131",
                "Travel explanation and supporting evidence",
                "required",
                "travel_evidence",
                "The Form I-131 instructions say advance parole applicants should explain the circumstances warranting travel and provide supporting evidence of the reason for the trip.",
            ),
            _evidence(
                "form_i485",
                "Underlying Form I-485 filing or pending I-485 evidence",
                "conditional",
                "case_status",
                "For the pending-I-485 advance parole path, USCIS instructions refer to the Form I-485 filing or receipt as the underlying basis.",
                "If Form I-131 is being filed later instead of in the same packet as Form I-485, use the I-485 receipt notice or other pending-case evidence.",
            ),
        ],
    },
    {
        "code": "form_g1145",
        "label": "Form G-1145",
        "accepted_edition": "09/26/14",
        "verified_on": VERIFIED_ON,
        "official_url": "https://www.uscis.gov/g-1145",
        "summary": "Optional e-notification sheet clipped to the front of a paper packet.",
        "important_notes": [
            "USCIS says this form can be clipped to the front of the filing packet to request text or email receipt notice updates.",
            "USCIS states that previous editions may still be used.",
        ],
        "fee_url": None,
        "initial_evidence": [
            _evidence(
                "form_g1145",
                "Completed Form G-1145",
                "recommended",
                "form",
                "Optional e-notification sheet clipped to the front of a paper-filed packet.",
            ),
        ],
    },
]

for requirement in USCIS_REQUIREMENTS:
    derived_codes: list[str] = []
    for evidence in requirement.get("initial_evidence", []):
        checklist_code = evidence.get("checklist_code")
        if checklist_code and checklist_code not in derived_codes:
            derived_codes.append(checklist_code)
    requirement["related_checklist_codes"] = derived_codes


USCIS_REQUIREMENT_BY_CHECKLIST_CODE = {
    requirement["related_checklist_codes"][0]: requirement
    for requirement in USCIS_REQUIREMENTS
    if requirement["related_checklist_codes"]
}

USCIS_REQUIREMENTS_BY_CHECKLIST_CODE: dict[str, list[dict[str, object]]] = {}
FORM_CODES_BY_CHECKLIST_CODE: dict[str, list[str]] = {}

for requirement in USCIS_REQUIREMENTS:
    for checklist_code in requirement["related_checklist_codes"]:
        USCIS_REQUIREMENTS_BY_CHECKLIST_CODE.setdefault(checklist_code, []).append(requirement)
        FORM_CODES_BY_CHECKLIST_CODE.setdefault(checklist_code, []).append(str(requirement["code"]))
