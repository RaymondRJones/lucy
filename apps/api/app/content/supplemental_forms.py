from __future__ import annotations

from typing import Any

from app.content.admission_classes import CLASS_OF_ADMISSION_OPTIONS, I94_INFO_SOURCE
from app.content.family_questionnaires import (
    FAMILY_FORM_SOURCES,
    FAMILY_FORMS_VERIFIED_ON,
    I130A_OFFICIAL_PDF_URL,
    I130A_QUESTIONNAIRE,
    I130A_QUESTIONNAIRE_VERSION,
    I130_OFFICIAL_PDF_URL,
    I130_OFFICIAL_URL,
    I130_QUESTIONNAIRE,
    I130_QUESTIONNAIRE_VERSION,
)


SUPPLEMENTAL_FORMS_VERIFIED_ON = "2026-04-28"
I765_VERIFIED_ON = "2026-05-09"
I131_VERIFIED_ON = "2026-04-29"
I864_HOUSEHOLD_HELP_VERIFIED_ON = "2026-05-02"
I864_EDITION_VERIFIED_ON = "2026-10-30"

FORM_TEACHING_SOURCES: dict[str, dict[str, str]] = {
    "i131": {
        "label": "I-131 plain-language walkthrough transcript",
        "url": "https://www.youtube.com/watch?v=Ec3HdljZ1nU",
        "transcript_path": "docs/youtube-transcripts/i131/transcript.txt",
        "fetched_on": "2026-04-29",
        "caption_type": "manual",
    },
    "i765": {
        "label": "I-765 plain-language walkthrough transcript",
        "url": "https://www.youtube.com/watch?v=iOiBvBzJD7I",
        "transcript_path": "docs/youtube-transcripts/i765/transcript.txt",
        "fetched_on": "2026-04-29",
        "caption_type": "auto-generated",
    },
    "i864": {
        "label": "I-864 plain-language walkthrough transcript",
        "url": "https://www.youtube.com/watch?v=s06z2X7xI_4",
        "transcript_path": "docs/youtube-transcripts/i864/transcript.txt",
        "fetched_on": "2026-04-29",
        "caption_type": "manual",
    },
}

I765_LAST_ARRIVAL_STATUS_OPTIONS = [
    {"value": "B-2", "label": "B-2 visitor"},
    {"value": "B-1", "label": "B-1 visitor for business"},
    {"value": "F-1", "label": "F-1 student"},
    {"value": "F-2", "label": "F-2 dependent"},
    {"value": "J-1", "label": "J-1 exchange visitor"},
    {"value": "J-2", "label": "J-2 dependent"},
    {"value": "M-1", "label": "M-1 vocational student"},
    {"value": "M-2", "label": "M-2 dependent"},
    {"value": "parolee", "label": "Parolee"},
    {"value": "no status", "label": "No status"},
]

I765_CURRENT_STATUS_OPTIONS = [
    {"value": "B-2 visitor", "label": "B-2 visitor"},
    {"value": "B-1 visitor for business", "label": "B-1 visitor for business"},
    {"value": "F-1 student", "label": "F-1 student"},
    {"value": "F-2 dependent", "label": "F-2 dependent"},
    {"value": "J-1 exchange visitor", "label": "J-1 exchange visitor"},
    {"value": "J-2 dependent", "label": "J-2 dependent"},
    {"value": "M-1 vocational student", "label": "M-1 vocational student"},
    {"value": "M-2 dependent", "label": "M-2 dependent"},
    {"value": "parolee", "label": "Parolee"},
    {"value": "deferred action", "label": "Deferred action"},
    {"value": "no status or category", "label": "No status or category"},
]

SUPPLEMENTAL_HELP_OVERRIDES: dict[str, dict[str, tuple[str, str]]] = {
    "i131": {
        "i131_application_type": (
            "For family-based adjustment applicants requesting advance parole, use the pending I-485 advance parole category.",
            "The walkthrough says this is application type 5.A for an advance parole document tied to a pending Form I-485. Skip re-entry permit, refugee travel document, TPS travel authorization, and other parole categories unless your case is truly in one of those paths.",
        ),
        "i131_i485_receipt_number": (
            "Enter the I-485 receipt number only if the I-485 was already filed.",
            "If Form I-131 is mailed together with Form I-485, the transcript explains that the applicant will not yet have an I-485 receipt number, so this line is left blank while the category still remains pending I-485 advance parole.",
        ),
        "beneficiary_other_names": (
            "List other official names, spellings, maiden names, or aliases used on records.",
            "The transcript says not to list casual nicknames used only by family or friends. Include names that appeared on applications, identity documents, or official records.",
        ),
        "beneficiary_mailing_in_care_of": (
            "Use this only if another trusted person receives mail for the applicant.",
            "If the applicant personally receives mail at the mailing address, the walkthrough says this can be skipped. Reliable mail matters because notices and travel documents may be sent there.",
        ),
        "i131_physical_same_as_mailing": (
            "Answer whether the applicant's actual residence is the same as the mailing address.",
            "The transcript separates mailing address from physical address. If they are the same, the physical-address section can usually be blank or marked same; if different, provide where the applicant actually lives.",
        ),
        "beneficiary_uscis_online_account_number": (
            "Use the applicant's USCIS online account number, not the petitioner's.",
            "The walkthrough warns that an online I-130 account number may belong to the petitioner. This field asks for the travel-document applicant's own USCIS online account number.",
        ),
        "beneficiary_class_of_admission": (
            "Use the Class of Admission (COA) code from the applicant's latest I-94 or status approval, such as B-2.",
            "If the applicant changed status after arrival, use the most recently issued class and the I-94 tied to that later approval notice. The dropdown includes common choices to avoid typos, but the source record is the authority.",
        ),
        "beneficiary_i94_number": (
            "Enter the I-94 number from the applicant's most recent I-94 record.",
            "The walkthrough notes that a later status approval can include a new I-94. Use the latest relevant I-94, not necessarily the one from first arrival.",
        ),
        "beneficiary_i94_expiration": (
            "Use the authorized-stay expiration from the latest I-94, if there is a date.",
            "For students or others whose I-94 says D/S, the transcript suggests leaving the date field blank in the PDF and writing D/S after printing if needed.",
        ),
        "i131_removal_proceedings": (
            "Answer whether the applicant has been in exclusion, deportation, or removal proceedings.",
            "The transcript flags immigration proceedings as a reason advance parole can be risky or unavailable. A yes answer needs careful review before relying on this standard flow.",
        ),
        "i131_prior_reentry_refugee_document": (
            "Answer whether the applicant previously received a re-entry permit, refugee travel document, or advance parole.",
            "The walkthrough gives DACA advance parole as an example of a prior document that should be disclosed. If yes, capture whether the document is still in the applicant's possession.",
        ),
        "i131_prior_advance_parole": (
            "Answer whether the applicant previously received advance parole.",
            "The walkthrough gives DACA advance parole as an example of a prior document that should be disclosed. If yes, capture when it was issued and what happened to the document.",
        ),
        "i131_replacement_request": (
            "Answer yes only if requesting a replacement or correction of a prior travel document.",
            "The transcript says most first-time family-based advance parole applicants answer no. Replacement questions are for lost, damaged, incorrect, or USCIS-error documents.",
        ),
        "i131_intended_departure_date": (
            "Enter an approximate intended departure date if exact plans are not fixed.",
            "The walkthrough says approximate timing is acceptable for the advance parole travel-plan section. Do not treat advance parole approval as guaranteed travel permission.",
        ),
        "i131_travel_purpose": (
            "Briefly describe why the applicant wants advance parole travel.",
            "For family-based adjustment applicants, the transcript says the short Part 7 purpose is usually enough and separate evidence explaining the reason is generally for other special advance parole categories.",
        ),
        "i131_countries_to_visit": (
            "List the countries the applicant expects to visit.",
            "The walkthrough places this with the intended departure, trip purpose, number of trips, and expected trip length. Keep it practical and consistent with the travel explanation.",
        ),
        "i131_trip_count": (
            "Choose whether the applicant expects one trip or multiple trips.",
            "Advance parole timing can be uncertain, so this should reflect the real expected need rather than a guaranteed itinerary.",
        ),
        "i131_expected_trip_length": (
            "Enter only the number of days for the expected trip length.",
            "The form field is measured in days. Convert weeks or months before entering the answer, for example enter 14 for a two-week trip.",
        ),
        "applicant_reviewed_certification": (
            "Confirm the applicant knows the printed I-131 must be signed in pen before filing.",
            "The walkthrough specifically warns not to sign the paper I-131 electronically or in Adobe. The final mailed form needs an ink signature.",
        ),
        "interpreter_used": (
            "Answer yes only if someone translated or interpreted the I-131 questions for the applicant.",
            "The transcript says the interpreter section is for the person who actually interpreted the form. If no one interpreted the questions, this section can be skipped.",
        ),
        "preparer_used": (
            "Answer yes only if someone other than the applicant prepared the I-131.",
            "The walkthrough separates interpreter help from preparation help. If nobody else completed the form for the applicant, leave the preparer section blank.",
        ),
        "additional_information_needed": (
            "Answer yes only if an I-131 answer needs more room or a written clarification on the continuation page.",
            "The transcript says the continuation page should still have the applicant's name at the top, and A-Number if any, even when no extra information is added. If extra information is needed, identify the page, part, and item number before writing the additional facts.",
        ),
    },
    "i765": {
        "i765_reason_for_applying": (
            "For a first work permit based on adjustment, choose initial permission to accept employment.",
            "The transcript focuses on the C9 adjustment category. Replacement and renewal are different workflows and should be used only when replacing a prior card or renewing permission.",
        ),
        "i765_eligibility_category": (
            "For a pending I-485 adjustment applicant, the expected category is (c)(9).",
            "The transcript emphasizes that category C9 is the adjustment-of-status work-permit category and that the form must show the category correctly, especially when uploading or filing later.",
        ),
        "i765_previously_filed": (
            "Answer whether the applicant has filed I-765 before.",
            "This is separate from whether the applicant filed I-485. If the applicant never had an EAD or work-permit filing before, the standard first-time answer is no.",
        ),
        "beneficiary_uscis_online_account_number": (
            "Use the beneficiary's USCIS online account number, not the petitioner's.",
            "The transcript repeatedly says the I-765 belongs to the beneficiary. If filing through an online account later, use the beneficiary's account.",
        ),
        "beneficiary_i94_number": (
            "Use the I-94 arrival/departure record number that proves lawful admission or parole.",
            "The transcript explains that the most recent I-94 is usually available from CBP online. If the applicant truly has no I-94, gather another document proving lawful admission.",
        ),
        "beneficiary_class_of_admission": (
            "Choose the applicant's immigration status at the most recent U.S. arrival.",
            "USCIS Form I-765 gives examples such as B-2 visitor, F-1 student, or no status. The dropdown stores the matching I-94 class when there is one, then the PDF generator prints the plain-language status USCIS expects.",
        ),
        "beneficiary_current_immigration_status": (
            "Choose the applicant's current immigration status or category.",
            "USCIS Form I-765 gives examples such as B-2 visitor, F-1 student, parolee, deferred action, or no status or category. Use the current status/category as of signing the I-765, not automatically the entry status if it changed.",
        ),
        "beneficiary_last_arrival_place": (
            "Enter the port or place of last entry into the United States.",
            "Keep this consistent with the applicant's I-94 and I-485 arrival facts. This is not necessarily the current city or final destination.",
        ),
        "i765_arrested_or_convicted": (
            "Answer whether the applicant has ever been arrested for or convicted of a crime.",
            "A yes answer is a serious review point. Keep the answer consistent with I-485 criminal-history answers and gather certified dispositions where needed.",
        ),
        "applicant_reviewed_certification": (
            "Confirm the applicant reviewed the certification and knows the filing must be signed.",
            "For paper filing, the form is signed in ink. The transcript discusses electronic submission only for later upload workflows through the beneficiary's USCIS account.",
        ),
        "interpreter_used": (
            "Answer yes only if someone translated or interpreted the I-765 questions for the applicant.",
            "Use the interpreter section only for the person who actually interpreted the form questions. If the applicant understood and completed the form without an interpreter, answer no or leave the interpreter details blank where allowed.",
        ),
        "preparer_used": (
            "Answer yes only if someone other than the applicant prepared the I-765.",
            "The transcript separates reviewing the form from preparing it. If nobody else completed the form for the applicant, the preparer section is not needed.",
        ),
        "additional_information_needed": (
            "Answer yes only if an I-765 answer needs more room on Part 6.",
            "The transcript says all I-765 pages should stay with the uploaded or mailed form, even pages with no extra information. If Part 6 is used, include the page, part, and item number so the extra detail points back to the original answer.",
        ),
    },
    "i864": {
        "i864_sponsor_basis": (
            "Choose the sponsor role for this specific I-864.",
            "The transcript warns that the petitioner must file an I-864 even with zero income or a joint sponsor. Do not mark the petitioner as a joint sponsor; a joint sponsor files a separate I-864.",
        ),
        "petitioner_mailing_in_care_of": (
            "Use this only if someone else receives mail for the sponsor.",
            "If the sponsor can receive mail at the address, the walkthrough says to skip the in-care-of line and start with the street address.",
        ),
        "i864_physical_same_as_mailing": (
            "Answer whether the sponsor actually lives at the mailing address.",
            "The transcript distinguishes mailing address from physical address. If the sponsor uses a PO box or another mailing address, provide the actual residence separately.",
        ),
        "petitioner_country_of_domicile": (
            "The sponsor generally must be domiciled in the United States.",
            "The walkthrough says a sponsor not domiciled in the United States is not eligible unless they can prove domicile or intent to reestablish domicile as required.",
        ),
        "petitioner_citizenship_status": (
            "Only U.S. citizens, U.S. nationals, and lawful permanent residents can sponsor on I-864.",
            "The transcript applies this to petitioning sponsors and joint sponsors. For this app's standard marriage flow, the expected sponsor is the U.S. citizen petitioner.",
        ),
        "spouse_us_military": (
            "Answer active-duty military status only for the petitioning sponsor.",
            "The transcript explains this matters because active-duty petitioning sponsors may have reduced income-threshold rules in certain spouse/child cases.",
        ),
        "beneficiary_country_of_citizenship": (
            "Use the principal immigrant's citizenship or nationality tied to the passport used for the case.",
            "The walkthrough says additional citizenships can be listed in the additional-information section rather than forcing multiple countries into this one field.",
        ),
        "i864_only_principal_immigrant": (
            "Most one-spouse marriage cases answer yes: this affidavit sponsors the principal immigrant listed above.",
            "Happy-path suggestion: answer yes if this I-864 is only for the foreign spouse, with no children or other family members immigrating on this same affidavit. No is mainly for the second of two joint sponsors in a multi-immigrant situation.",
        ),
        "i864_sponsoring_family_members": (
            "Answer yes only for derivative family members immigrating with or near the principal immigrant on the same petition.",
            "Happy-path suggestion: answer no when the only immigrant on this I-864 is the foreign spouse. Do not count relatives with separate petitions here. U.S. citizen spouse and stepchild cases usually have separate petitions, while some K2 or F2A derivatives may be included.",
        ),
        "i864_total_immigrants": (
            "Count the immigrants sponsored on this specific affidavit.",
            "Happy-path suggestion: enter 1 when this I-864 is only sponsoring the foreign spouse. Separate I-130 petitions generally need separate affidavits.",
        ),
        "household_size": (
            "This is the final total after adding the I-864 household-size lines. Do not count the same person twice.",
            "Happy-path suggestion: enter 2 when the household is only the U.S. citizen sponsor and the foreign spouse, with no children, tax dependents, prior sponsored immigrants, or income-contributing household members. This is not just a count of everyone who lives at the address.",
        ),
        "i864_sponsor_married_count": (
            "Usually enter 0 in a U.S.-citizen sponsoring foreign-spouse case, because the immigrant spouse was already counted above.",
            "Happy-path suggestion: enter 0 when the sponsor is married to the foreign spouse being sponsored, because that spouse was already counted as the intending immigrant. Use 1 only when the sponsor has a spouse who was not already counted as an immigrant on this affidavit, such as a joint sponsor's spouse.",
        ),
        "i864_dependent_children_count": (
            "Count the sponsor's dependent children here only if they were not already counted as immigrants sponsored on this affidavit.",
            "Happy-path suggestion: enter 0 if the sponsor has no dependent children. If the sponsor has dependent children, count only children who were not already counted as immigrants on this same affidavit.",
        ),
        "i864_other_dependents_count": (
            "Count other dependents from the sponsor's most recent federal tax return, unless they were already counted above.",
            "Happy-path suggestion: enter 0 if the sponsor has no other dependents on the most recent federal tax return. This is not a free-form count of everyone the sponsor helps financially or everyone living in the home.",
        ),
        "i864_prior_sponsored_immigrants_count": (
            "Count people the sponsor previously sponsored on I-864 or I-864EZ only if the sponsor is still financially responsible for them.",
            "Happy-path suggestion: enter 0 if this is the sponsor's first affidavit of support or no prior sponsored immigrant is still covered by the support obligation. This does not count the foreign spouse in this case.",
        ),
        "i864_household_members_combining_income_count": (
            "Count relatives at the same principal residence only if they are combining income with the sponsor using Form I-864A.",
            "Happy-path suggestion: enter 0 when the U.S. citizen sponsor qualifies using only the sponsor's own income and no household member is signing I-864A.",
        ),
        "employment_status": (
            "Select the sponsor's real current employment situation.",
            "The walkthrough distinguishes employees, contractors, true self-employment, retirement, and unemployment. Self-employment often needs more evidence, so choose it only when it truly applies.",
        ),
        "petitioner_current_occupation": (
            "Enter the sponsor's job title or type of work, not the employer name.",
            "For example, enter Engineer, Teacher, or Store Manager here. The employer name belongs in the separate current employer field, such as Walmart or Sample Robotics Inc.",
        ),
        "petitioner_current_employer": (
            "Enter the sponsor's employer name, not the job title.",
            "For example, enter Walmart or Sample Robotics Inc. here. The sponsor's occupation or job title belongs in the employed-as field.",
        ),
        "annual_income": (
            "Enter the sponsor's estimated current individual annual income for the year of signing.",
            "The transcript says this is not year-to-date income. If unemployed, current individual income is zero, but the petitioner still must submit I-864.",
        ),
        "i864_household_income": (
            "Enter the total of the income lines used in Part 6, not just a tax-return household total.",
            "The transcript flags a common mistake: sponsors who file jointly should not put joint income here unless the spouse or household member is actually contributing income and properly included.",
        ),
        "i864_filed_recent_tax_return": (
            "Answer whether the sponsor filed the most recent required federal tax return.",
            "If no, the sponsor usually needs a clear explanation and evidence of why filing was not required. Tax evidence is central to the I-864 review.",
        ),
        "i864_cash_assets": (
            "Enter cash, savings, and checking assets only if using assets to support the affidavit.",
            "The transcript treats assets as a backup when income is not enough or when the sponsor chooses to rely on assets. Values should be documentable.",
        ),
        "sponsor_reviewed_contract": (
            "Confirm the sponsor understands I-864 is a binding support contract and must be signed.",
            "The transcript presents this as more than a simple form: the sponsor is taking on a financial obligation, so review and signature should be deliberate.",
        ),
        "interpreter_used": (
            "Answer yes only if someone translated or interpreted the I-864 for the sponsor.",
            "Use the interpreter section for the person who actually interpreted the affidavit. If the sponsor read and understood the form without an interpreter, answer no or leave the interpreter details blank where allowed.",
        ),
        "preparer_used": (
            "Answer yes only if someone other than the sponsor prepared the I-864.",
            "The preparer section identifies the person who completed the affidavit for the sponsor. It is separate from a spouse, family member, or helper merely discussing the answers.",
        ),
        "additional_information_needed": (
            "Answer yes only if an I-864 answer needs more room or a written clarification on Part 11.",
            "The transcript uses the additional-information page for details such as extra citizenship information and says to reference the page, part, and item number. Use it to make an answer understandable, not as a place for unrelated evidence.",
        ),
    },
}


def q(
    question_id: str,
    label: str,
    answer_type: str,
    *,
    required: bool = True,
    pdf_ref: str,
    db_path: str | None = None,
    options: list[dict[str, str]] | None = None,
    ideal_answer: Any = None,
    risk_when: Any = None,
    risk_code: str | None = None,
    help_text: str | None = None,
) -> dict[str, Any]:
    return {
        "id": question_id,
        "label": label,
        "answer_type": answer_type,
        "required": required,
        "pdf_ref": pdf_ref,
        "db_path": db_path,
        "options": options or [],
        "ideal_answer": ideal_answer,
        "risk_when": risk_when,
        "risk_code": risk_code,
        "help_text": help_text,
    }


I765_QUESTIONNAIRE: list[dict[str, Any]] = [
    {
        "id": "i765_page_01_identity",
        "title": "Applicant Identity and Filing Reason",
        "pdf_part": "Part 1 and Part 2, Items 1-3",
        "local_pdf_pages": [1],
        "questions": [
            q("beneficiary_last_name", "Applicant family name", "text", pdf_ref="Part 2, Item 1.a", db_path="intake.beneficiary_last_name"),
            q("beneficiary_first_name", "Applicant given name", "text", pdf_ref="Part 2, Item 1.b", db_path="intake.beneficiary_first_name"),
            q("beneficiary_middle_name", "Applicant middle name", "text", required=False, pdf_ref="Part 2, Item 1.c", db_path="intake.beneficiary_middle_name"),
            q(
                "i765_reason_for_applying",
                "Reason for applying",
                "select",
                pdf_ref="Part 1, Item 1",
                ideal_answer="initial_permission",
                risk_when="replacement_or_renewal",
                risk_code="i765_non_initial_request",
                options=[
                    {"value": "initial_permission", "label": "Initial permission to accept employment"},
                    {"value": "replacement", "label": "Replacement of lost, stolen, or incorrect EAD"},
                    {"value": "renewal", "label": "Renewal of permission to accept employment"},
                ],
            ),
            q("beneficiary_other_names", "Other names ever used, if any", "textarea", required=False, pdf_ref="Part 2, Items 2-4", db_path="intake.beneficiary_other_names"),
        ],
    },
    {
        "id": "i765_page_02_addresses",
        "title": "Mailing and Physical Address",
        "pdf_part": "Part 2, Items 5-6",
        "local_pdf_pages": [2],
        "questions": [
            q("beneficiary_mailing_in_care_of", "Mailing address in care of name", "text", required=False, pdf_ref="Part 2, Item 5.a"),
            q("beneficiary_mailing_address_line1", "Mailing street number and name", "text", pdf_ref="Part 2, Item 5.b", db_path="intake.beneficiary_current_address_line1"),
            q("beneficiary_mailing_address_line2", "Mailing apartment, suite, or floor", "text", required=False, pdf_ref="Part 2, Item 5.c", db_path="intake.beneficiary_current_address_line2"),
            q("beneficiary_mailing_city", "Mailing city or town", "text", pdf_ref="Part 2, Item 5.d", db_path="intake.beneficiary_current_city"),
            q("beneficiary_mailing_state", "Mailing state", "text", pdf_ref="Part 2, Item 5.e", db_path="intake.beneficiary_current_state"),
            q("beneficiary_mailing_zip", "Mailing ZIP code", "text", pdf_ref="Part 2, Item 5.f", db_path="intake.beneficiary_current_zip"),
            q("i765_physical_same_as_mailing", "Is the physical address the same as the mailing address?", "boolean", pdf_ref="Part 2, Item 6", ideal_answer=True),
            q("beneficiary_physical_address_line1", "Physical street number and name, if different", "text", required=False, pdf_ref="Part 2, Item 7.a"),
            q("beneficiary_physical_address_line2", "Physical apartment, suite, or floor, if different", "text", required=False, pdf_ref="Part 2, Item 7.b"),
            q("beneficiary_physical_city", "Physical city or town, if different", "text", required=False, pdf_ref="Part 2, Item 7.c"),
            q("beneficiary_physical_state", "Physical state, if different", "text", required=False, pdf_ref="Part 2, Item 7.d"),
            q("beneficiary_physical_zip", "Physical ZIP code, if different", "text", required=False, pdf_ref="Part 2, Item 7.e"),
        ],
    },
    {
        "id": "i765_page_03_biographic",
        "title": "Identifiers and Biographic Information",
        "pdf_part": "Part 2, Items 8-19",
        "local_pdf_pages": [2, 3],
        "questions": [
            q("beneficiary_a_number", "Alien Registration Number, if any", "text", required=False, pdf_ref="Part 2, Item 8", db_path="intake.beneficiary_a_number"),
            q("beneficiary_uscis_online_account_number", "USCIS online account number, if any", "text", required=False, pdf_ref="Part 2, Item 9"),
            q("beneficiary_sex", "Sex", "select", pdf_ref="Part 2, Item 10", db_path="intake.beneficiary_sex", options=[{"value": "female", "label": "Female"}, {"value": "male", "label": "Male"}]),
            q(
                "beneficiary_current_marital_status",
                "Marital status",
                "select",
                pdf_ref="Part 2, Item 11",
                db_path="intake.beneficiary_current_marital_status",
                ideal_answer="married",
                risk_when="not_married",
                risk_code="outside_niche_marital_status",
                options=[
                    {"value": "single", "label": "Single"},
                    {"value": "married", "label": "Married"},
                    {"value": "divorced", "label": "Divorced"},
                    {"value": "widowed", "label": "Widowed"},
                ],
            ),
            q("i765_previously_filed", "Has the applicant previously filed Form I-765?", "boolean", pdf_ref="Part 2, Item 12", ideal_answer=False, risk_when=True, risk_code="i765_prior_filing"),
            q("beneficiary_has_ssn", "Has SSA ever officially issued the applicant a Social Security card?", "boolean", pdf_ref="Part 2, Item 13", db_path="intake.beneficiary_has_ssn"),
            q("beneficiary_social_security_number", "Social Security number, if any", "text", required=False, pdf_ref="Part 2, Item 13.b", db_path="intake.beneficiary_social_security_number"),
            q("beneficiary_city_of_birth", "City/town/village of birth", "text", pdf_ref="Part 2, Item 17.a", db_path="intake.beneficiary_city_of_birth"),
            q("beneficiary_state_province_of_birth", "State or province of birth", "text", required=False, pdf_ref="Part 2, Item 17.b", db_path="intake.beneficiary_birth_department"),
            q("beneficiary_country_of_birth", "Country of birth", "country", pdf_ref="Part 2, Item 17.c", db_path="intake.beneficiary_country_of_birth"),
            q("beneficiary_country_of_citizenship", "Country of citizenship or nationality", "country", pdf_ref="Part 2, Item 18", db_path="intake.beneficiary_country_of_citizenship"),
            q("beneficiary_date_of_birth", "Date of birth", "date", pdf_ref="Part 2, Item 19", db_path="intake.beneficiary_date_of_birth"),
        ],
    },
    {
        "id": "i765_page_04_travel_eligibility",
        "title": "Arrival, Status, and Eligibility Category",
        "pdf_part": "Part 2, Items 20-31",
        "local_pdf_pages": [3],
        "questions": [
            q("beneficiary_i94_number", "Form I-94 arrival-departure record number", "text", pdf_ref="Part 2, Item 20.a", db_path="intake.beneficiary_i94_number"),
            q("beneficiary_passport_number", "Passport number", "text", pdf_ref="Part 2, Item 20.b", db_path="intake.beneficiary_passport_number"),
            q("beneficiary_passport_country", "Country that issued passport", "country", pdf_ref="Part 2, Item 20.d", db_path="intake.beneficiary_passport_country"),
            q("beneficiary_passport_expiration", "Passport expiration date", "date", pdf_ref="Part 2, Item 20.e", db_path="intake.beneficiary_passport_expiration"),
            q("beneficiary_last_arrival_date", "Date of last arrival into the United States", "date", pdf_ref="Part 2, Item 21", db_path="intake.beneficiary_last_arrival_date"),
            q("beneficiary_last_arrival_place", "Place of last arrival into the United States", "text", pdf_ref="Part 2, Item 22"),
            q("beneficiary_class_of_admission", "Immigration status at last arrival", "select", pdf_ref="Part 2, Item 23", db_path="intake.beneficiary_class_of_admission", options=I765_LAST_ARRIVAL_STATUS_OPTIONS),
            q("beneficiary_current_immigration_status", "Current immigration status or category", "select", pdf_ref="Part 2, Item 24", db_path="intake.beneficiary_current_immigration_status", options=I765_CURRENT_STATUS_OPTIONS),
            q(
                "i765_eligibility_category",
                "Eligibility category",
                "select",
                pdf_ref="Part 2, Item 27",
                ideal_answer="c9_pending_i485",
                risk_when="not_c9",
                risk_code="i765_non_c9_category",
                options=[
                    {"value": "c9_pending_i485", "label": "(c)(9) Pending I-485 adjustment applicant"},
                    {"value": "other", "label": "Other category or unsure"},
                ],
            ),
            q("i765_arrested_or_convicted", "Has the applicant ever been arrested for or convicted of any crime?", "boolean", pdf_ref="Part 2, Item 30", ideal_answer=False, risk_when=True, risk_code="criminal_history", db_path="intake.criminal_history"),
        ],
    },
    {
        "id": "i765_page_05_contact_review",
        "title": "Applicant Contact and Review",
        "pdf_part": "Parts 3-6",
        "local_pdf_pages": [4, 5, 6, 7],
        "questions": [
            q("beneficiary_phone", "Applicant daytime phone number", "text", pdf_ref="Part 3, Item 3", db_path="intake.beneficiary_phone"),
            q("beneficiary_mobile_phone", "Applicant mobile phone number", "text", required=False, pdf_ref="Part 3, Item 4"),
            q("beneficiary_email", "Applicant email address", "text", pdf_ref="Part 3, Item 5", db_path="intake.beneficiary_email"),
            q("applicant_reviewed_certification", "Applicant has reviewed the certification and understands the form must be signed", "boolean", pdf_ref="Part 3", ideal_answer=True, risk_when=False, risk_code="unsigned_form_risk"),
            q("interpreter_used", "Was an interpreter used?", "boolean", required=False, pdf_ref="Part 4", ideal_answer=False),
            q("preparer_used", "Was a preparer used?", "boolean", required=False, pdf_ref="Part 5", ideal_answer=False),
            q("additional_information_needed", "Is additional information needed on the continuation page?", "boolean", required=False, pdf_ref="Part 6", ideal_answer=False),
        ],
    },
]


I131_QUESTIONNAIRE: list[dict[str, Any]] = [
    {
        "id": "i131_page_01_type_identity",
        "title": "Application Type and Applicant Name",
        "pdf_part": "Part 1, Items 5.A and Part 2, Items 1-2",
        "local_pdf_pages": [1, 4, 5],
        "questions": [
            q(
                "i131_application_type",
                "Application type",
                "select",
                pdf_ref="Part 1, Item 5.A",
                ideal_answer="advanced_parole_i485_pending",
                risk_when="not_i485_advance_parole",
                risk_code="i131_not_i485_advance_parole",
                options=[
                    {
                        "value": "advanced_parole_i485_pending",
                        "label": "Advance parole document for applicant inside the United States with a pending Form I-485",
                    },
                    {"value": "other", "label": "Other I-131 travel document or parole request"},
                ],
            ),
            q(
                "i131_i485_receipt_number",
                "Form I-485 receipt number, if already filed",
                "text",
                required=False,
                pdf_ref="Part 1, Item 5.A",
                db_path="intake.i485_receipt_number",
                help_text="May be blank for a concurrent packet draft, but needed if filing I-131 after I-485.",
            ),
            q("beneficiary_last_name", "Applicant family name", "text", pdf_ref="Part 2, Item 1.a", db_path="intake.beneficiary_last_name"),
            q("beneficiary_first_name", "Applicant given name", "text", pdf_ref="Part 2, Item 1.b", db_path="intake.beneficiary_first_name"),
            q("beneficiary_middle_name", "Applicant middle name", "text", required=False, pdf_ref="Part 2, Item 1.c", db_path="intake.beneficiary_middle_name"),
            q("beneficiary_other_names", "Other names ever used, if any", "textarea", required=False, pdf_ref="Part 2, Item 2", db_path="intake.beneficiary_other_names"),
        ],
    },
    {
        "id": "i131_page_02_addresses_status",
        "title": "Address, Identifiers, and Admission",
        "pdf_part": "Part 2, Items 3-14",
        "local_pdf_pages": [5, 6, 7],
        "questions": [
            q("beneficiary_mailing_in_care_of", "Mailing address in care of name", "text", required=False, pdf_ref="Part 2, Item 3.a"),
            q("beneficiary_mailing_address_line1", "Mailing street number and name", "text", pdf_ref="Part 2, Item 3.b", db_path="intake.beneficiary_current_address_line1"),
            q("beneficiary_mailing_address_line2", "Mailing apartment, suite, or floor", "text", required=False, pdf_ref="Part 2, Item 3.c", db_path="intake.beneficiary_current_address_line2"),
            q("beneficiary_mailing_city", "Mailing city or town", "text", pdf_ref="Part 2, Item 3.d", db_path="intake.beneficiary_current_city"),
            q("beneficiary_mailing_state", "Mailing state", "text", pdf_ref="Part 2, Item 3.e", db_path="intake.beneficiary_current_state"),
            q("beneficiary_mailing_zip", "Mailing ZIP code", "text", pdf_ref="Part 2, Item 3.f", db_path="intake.beneficiary_current_zip"),
            q("beneficiary_mailing_country", "Mailing country", "country", pdf_ref="Part 2, Item 3.i"),
            q("i131_physical_same_as_mailing", "Is the physical address the same as the mailing address?", "boolean", pdf_ref="Part 2, Item 4", ideal_answer=True),
            q("beneficiary_physical_address_line1", "Physical street number and name, if different", "text", required=False, pdf_ref="Part 2, Item 4.b"),
            q("beneficiary_physical_city", "Physical city or town, if different", "text", required=False, pdf_ref="Part 2, Item 4.d"),
            q("beneficiary_physical_state", "Physical state, if different", "text", required=False, pdf_ref="Part 2, Item 4.e"),
            q("beneficiary_physical_zip", "Physical ZIP code, if different", "text", required=False, pdf_ref="Part 2, Item 4.f"),
            q("beneficiary_a_number", "Alien Registration Number, if any", "text", required=False, pdf_ref="Part 2, Item 5", db_path="intake.beneficiary_a_number"),
            q("beneficiary_country_of_birth", "Country of birth", "country", pdf_ref="Part 2, Item 6", db_path="intake.beneficiary_country_of_birth"),
            q("beneficiary_country_of_citizenship", "Country of citizenship or nationality", "country", pdf_ref="Part 2, Item 7", db_path="intake.beneficiary_country_of_citizenship"),
            q("beneficiary_sex", "Sex", "select", pdf_ref="Part 2, Item 8", db_path="intake.beneficiary_sex", options=[{"value": "female", "label": "Female"}, {"value": "male", "label": "Male"}]),
            q("beneficiary_date_of_birth", "Date of birth", "date", pdf_ref="Part 2, Item 9", db_path="intake.beneficiary_date_of_birth"),
            q("beneficiary_social_security_number", "Social Security number, if any", "text", required=False, pdf_ref="Part 2, Item 10", db_path="intake.beneficiary_social_security_number"),
            q("beneficiary_uscis_online_account_number", "USCIS online account number, if any", "text", required=False, pdf_ref="Part 2, Item 11"),
            q("beneficiary_class_of_admission", "Class of Admission (COA), such as B-2", "select", pdf_ref="Part 2, Item 12", db_path="intake.beneficiary_class_of_admission", options=CLASS_OF_ADMISSION_OPTIONS),
            q("beneficiary_i94_number", "Form I-94 arrival-departure record number", "text", pdf_ref="Part 2, Item 13", db_path="intake.beneficiary_i94_number"),
            q("beneficiary_i94_expiration", "Date authorized stay expires, if any", "date", required=False, pdf_ref="Part 2, Item 14", db_path="intake.beneficiary_status_expires_on"),
        ],
    },
    {
        "id": "i131_page_03_biographic",
        "title": "Biographic Information",
        "pdf_part": "Part 3",
        "local_pdf_pages": [7],
        "questions": [
            q("beneficiary_ethnicity", "Ethnicity", "select", pdf_ref="Part 3, Item 1", db_path="intake.beneficiary_ethnicity", options=[{"value": "hispanic_or_latino", "label": "Hispanic or Latino"}, {"value": "not_hispanic_or_latino", "label": "Not Hispanic or Latino"}]),
            q(
                "beneficiary_race_primary",
                "Race",
                "select",
                pdf_ref="Part 3, Item 2",
                db_path="intake.beneficiary_race_primary",
                options=[
                    {"value": "asian", "label": "Asian"},
                    {"value": "black", "label": "Black or African American"},
                    {"value": "american_indian", "label": "American Indian or Alaska Native"},
                    {"value": "pacific_islander", "label": "Native Hawaiian or Other Pacific Islander"},
                    {"value": "white", "label": "White"},
                ],
            ),
            q("beneficiary_height_feet", "Height in feet", "number", required=False, pdf_ref="Part 3, Item 3", db_path="intake.beneficiary_height_feet"),
            q("beneficiary_height_inches", "Height in inches", "number", required=False, pdf_ref="Part 3, Item 3", db_path="intake.beneficiary_height_inches"),
            q("beneficiary_weight_pounds", "Weight in pounds", "number", required=False, pdf_ref="Part 3, Item 4", db_path="intake.beneficiary_weight_pounds"),
            q(
                "beneficiary_eye_color",
                "Eye color",
                "select",
                pdf_ref="Part 3, Item 5",
                db_path="intake.beneficiary_eye_color",
                options=[
                    {"value": "black", "label": "Black"},
                    {"value": "blue", "label": "Blue"},
                    {"value": "brown", "label": "Brown"},
                    {"value": "gray", "label": "Gray"},
                    {"value": "green", "label": "Green"},
                    {"value": "hazel", "label": "Hazel"},
                    {"value": "maroon", "label": "Maroon"},
                    {"value": "pink", "label": "Pink"},
                    {"value": "other", "label": "Unknown or other"},
                ],
            ),
            q(
                "beneficiary_hair_color",
                "Hair color",
                "select",
                pdf_ref="Part 3, Item 6",
                db_path="intake.beneficiary_hair_color",
                options=[
                    {"value": "bald", "label": "Bald"},
                    {"value": "black", "label": "Black"},
                    {"value": "blond", "label": "Blond"},
                    {"value": "brown", "label": "Brown"},
                    {"value": "gray", "label": "Gray"},
                    {"value": "red", "label": "Red"},
                    {"value": "sandy", "label": "Sandy"},
                    {"value": "white", "label": "White"},
                    {"value": "other", "label": "Unknown or other"},
                ],
            ),
        ],
    },
    {
        "id": "i131_page_04_processing_history",
        "title": "Processing History",
        "pdf_part": "Part 4",
        "local_pdf_pages": [7, 8, 9],
        "questions": [
            q("i131_removal_proceedings", "Has the applicant been in exclusion, deportation, removal, or rescission proceedings?", "boolean", pdf_ref="Part 4, Item 1", ideal_answer=False, risk_when=True, risk_code="i131_removal_proceedings"),
            q("i131_prior_reentry_refugee_document", "Has the applicant ever been issued a reentry permit or refugee travel document?", "boolean", pdf_ref="Part 4, Item 2.a", ideal_answer=False, risk_when=True, risk_code="i131_prior_travel_document"),
            q("i131_prior_reentry_refugee_document_date", "Date issued for the last reentry permit or refugee travel document", "date", required=False, pdf_ref="Part 4, Item 2.b"),
            q("i131_prior_reentry_refugee_document_disposition", "Disposition of the last reentry permit or refugee travel document", "text", required=False, pdf_ref="Part 4, Item 2.c"),
            q("i131_prior_advance_parole", "Has the applicant ever been issued an advance parole document?", "boolean", pdf_ref="Part 4, Item 3.a", ideal_answer=False),
            q("i131_prior_advance_parole_date", "Date issued for the last advance parole document", "date", required=False, pdf_ref="Part 4, Item 3.b"),
            q("i131_prior_advance_parole_disposition", "Disposition of the last advance parole document", "text", required=False, pdf_ref="Part 4, Item 3.c"),
            q("i131_replacement_request", "Is this a replacement request?", "boolean", pdf_ref="Part 4, Item 4", ideal_answer=False, risk_when=True, risk_code="i131_replacement_request"),
            q(
                "i131_processing_location",
                "Where should a travel document be sent if applicable?",
                "select",
                required=False,
                pdf_ref="Part 4, Item 7",
                ideal_answer="domestic_address",
                options=[
                    {"value": "domestic_address", "label": "U.S. address listed in Part 2"},
                    {"value": "overseas_office", "label": "U.S. embassy, consulate, USCIS international office, or DHS office overseas"},
                ],
            ),
            q("i131_processing_city", "Overseas processing city, if applicable", "text", required=False, pdf_ref="Part 4, Item 7.b"),
            q("i131_processing_country", "Overseas processing country, if applicable", "country", required=False, pdf_ref="Part 4, Item 7.b"),
        ],
    },
    {
        "id": "i131_page_05_proposed_travel",
        "title": "Proposed Travel",
        "pdf_part": "Part 7",
        "local_pdf_pages": [10],
        "questions": [
            q("i131_intended_departure_date", "Intended departure date", "date", pdf_ref="Part 7, Item 1", db_path="intake.i131_intended_departure_date"),
            q("i131_travel_purpose", "Purpose of trip", "textarea", pdf_ref="Part 7, Item 2", db_path="intake.i131_travel_purpose"),
            q("i131_countries_to_visit", "Countries to visit", "textarea", pdf_ref="Part 7, Item 3", db_path="intake.i131_countries_to_visit"),
            q(
                "i131_trip_count",
                "How many trips should the document cover?",
                "select",
                pdf_ref="Part 7, Item 4",
                options=[
                    {"value": "one", "label": "One trip"},
                    {"value": "multiple", "label": "More than one trip"},
                ],
            ),
            q("i131_expected_trip_length", "Expected length of trip (in days)", "number", pdf_ref="Part 7, Item 5", db_path="intake.i131_expected_trip_length"),
        ],
    },
    {
        "id": "i131_page_06_contact_review",
        "title": "Applicant Contact and Review",
        "pdf_part": "Parts 10-13",
        "local_pdf_pages": [11, 12, 13, 14],
        "questions": [
            q("beneficiary_phone", "Applicant daytime phone number", "text", required=False, pdf_ref="Part 10, Item 1", db_path="intake.beneficiary_phone"),
            q("beneficiary_mobile_phone", "Applicant mobile phone number", "text", required=False, pdf_ref="Part 10, Item 2"),
            q("beneficiary_email", "Applicant email address", "text", pdf_ref="Part 10, Item 3", db_path="intake.beneficiary_email"),
            q("applicant_reviewed_certification", "Applicant has reviewed the certification and understands the form must be signed", "boolean", pdf_ref="Part 10", ideal_answer=True, risk_when=False, risk_code="unsigned_form_risk"),
            q("interpreter_used", "Was an interpreter used?", "boolean", required=False, pdf_ref="Part 11", ideal_answer=False),
            q("preparer_used", "Was a preparer used?", "boolean", required=False, pdf_ref="Part 12", ideal_answer=False),
            q("additional_information_needed", "Is additional information needed on the continuation page?", "boolean", required=False, pdf_ref="Part 13", ideal_answer=False),
        ],
    },
]


I864_QUESTIONNAIRE: list[dict[str, Any]] = [
    {
        "id": "i864_page_01_basis_sponsor",
        "title": "Sponsor Basis and Name",
        "pdf_part": "Parts 1-2",
        "local_pdf_pages": [1],
        "questions": [
            q(
                "i864_sponsor_basis",
                "Basis for filing Form I-864",
                "select",
                pdf_ref="Part 1, Item 1",
                ideal_answer="petitioner",
                risk_when="not_petitioner",
                risk_code="i864_joint_or_substitute_sponsor",
                options=[
                    {"value": "petitioner", "label": "I am the petitioner"},
                    {"value": "joint_sponsor", "label": "Joint sponsor"},
                    {"value": "substitute_sponsor", "label": "Substitute sponsor"},
                    {"value": "other", "label": "Other or unsure"},
                ],
            ),
            q("petitioner_last_name", "Sponsor family name", "text", pdf_ref="Part 2, Item 1.a", db_path="intake.petitioner_last_name"),
            q("petitioner_first_name", "Sponsor given name", "text", pdf_ref="Part 2, Item 1.b", db_path="intake.petitioner_first_name"),
            q("petitioner_middle_name", "Sponsor middle name", "text", required=False, pdf_ref="Part 2, Item 1.c", db_path="intake.petitioner_middle_name"),
        ],
    },
    {
        "id": "i864_page_02_sponsor_address_status",
        "title": "Sponsor Address, Birth, and Status",
        "pdf_part": "Part 2, Items 2-14",
        "local_pdf_pages": [2],
        "questions": [
            q("petitioner_mailing_in_care_of", "Sponsor mailing address in care of name", "text", required=False, pdf_ref="Part 2, Item 2.a", db_path="intake.petitioner_mailing_in_care_of"),
            q("petitioner_current_address_line1", "Sponsor mailing street number and name", "text", pdf_ref="Part 2, Item 2.b", db_path="intake.petitioner_current_address_line1"),
            q("petitioner_current_address_line2", "Sponsor mailing apartment, suite, or floor", "text", required=False, pdf_ref="Part 2, Item 2.c", db_path="intake.petitioner_current_address_line2"),
            q("petitioner_current_city", "Sponsor mailing city or town", "text", pdf_ref="Part 2, Item 2.e", db_path="intake.petitioner_current_city"),
            q("petitioner_current_state", "Sponsor mailing state", "text", pdf_ref="Part 2, Item 2.f", db_path="intake.petitioner_current_state"),
            q("petitioner_current_zip", "Sponsor mailing ZIP code", "text", pdf_ref="Part 2, Item 2.g", db_path="intake.petitioner_current_zip"),
            q("i864_physical_same_as_mailing", "Is the sponsor's physical address the same as mailing address?", "boolean", pdf_ref="Part 2, Item 3", ideal_answer=True),
            q("petitioner_country_of_domicile", "Sponsor country of domicile", "country", pdf_ref="Part 2, Item 5", db_path="intake.petitioner_country_of_domicile", ideal_answer="United States", risk_when="not_united_states", risk_code="i864_domicile_review"),
            q("petitioner_date_of_birth", "Sponsor date of birth", "date", pdf_ref="Part 2, Item 6", db_path="intake.petitioner_date_of_birth"),
            q("petitioner_country_of_birth", "Sponsor country of birth", "country", pdf_ref="Part 2, Item 7", db_path="intake.petitioner_country_of_birth"),
            q("petitioner_social_security_number", "Sponsor Social Security number", "text", pdf_ref="Part 2, Item 10", db_path="intake.petitioner_social_security_number"),
            q(
                "petitioner_citizenship_status",
                "Sponsor immigration/citizenship status",
                "select",
                pdf_ref="Part 2, Item 11",
                db_path="intake.petitioner_citizenship_status",
                ideal_answer="us_citizen",
                risk_when="not_us_citizen",
                risk_code="outside_niche_spouse_not_us_citizen",
                options=[
                    {"value": "us_citizen", "label": "U.S. citizen"},
                    {"value": "us_national", "label": "U.S. national"},
                    {"value": "lpr", "label": "Lawful permanent resident"},
                ],
            ),
            q("spouse_us_military", "Is the sponsor on active duty in the U.S. Armed Forces or Coast Guard?", "boolean", required=False, pdf_ref="Part 2, Item 14", ideal_answer=False),
        ],
    },
    {
        "id": "i864_page_03_principal_immigrant",
        "title": "Principal Immigrant",
        "pdf_part": "Part 3",
        "local_pdf_pages": [3],
        "questions": [
            q("beneficiary_last_name", "Principal immigrant family name", "text", pdf_ref="Part 3, Item 1.a", db_path="intake.beneficiary_last_name"),
            q("beneficiary_first_name", "Principal immigrant given name", "text", pdf_ref="Part 3, Item 1.b", db_path="intake.beneficiary_first_name"),
            q("beneficiary_middle_name", "Principal immigrant middle name", "text", required=False, pdf_ref="Part 3, Item 1.c", db_path="intake.beneficiary_middle_name"),
            q("beneficiary_mailing_address_line1", "Principal immigrant mailing street number and name", "text", pdf_ref="Part 3, Item 2", db_path="intake.beneficiary_mailing_address_line1"),
            q("beneficiary_mailing_address_line2", "Principal immigrant mailing apartment, suite, or floor", "text", required=False, pdf_ref="Part 3, Item 2", db_path="intake.beneficiary_mailing_address_line2"),
            q("beneficiary_mailing_city", "Principal immigrant mailing city or town", "text", pdf_ref="Part 3, Item 2", db_path="intake.beneficiary_mailing_city"),
            q("beneficiary_mailing_state", "Principal immigrant mailing state", "text", pdf_ref="Part 3, Item 2", db_path="intake.beneficiary_mailing_state"),
            q("beneficiary_mailing_zip", "Principal immigrant mailing ZIP code", "text", pdf_ref="Part 3, Item 2", db_path="intake.beneficiary_mailing_zip"),
            q("beneficiary_country_of_citizenship", "Principal immigrant country of citizenship", "country", pdf_ref="Part 3, Item 3", db_path="intake.beneficiary_country_of_citizenship"),
            q("beneficiary_date_of_birth", "Principal immigrant date of birth", "date", pdf_ref="Part 3, Item 4", db_path="intake.beneficiary_date_of_birth"),
            q("beneficiary_a_number", "Principal immigrant A-Number, if any", "text", required=False, pdf_ref="Part 3, Item 5", db_path="intake.beneficiary_a_number"),
            q("beneficiary_phone", "Principal immigrant daytime phone number", "text", required=False, pdf_ref="Part 3, Item 7", db_path="intake.beneficiary_phone"),
        ],
    },
    {
        "id": "i864_page_04_household",
        "title": "Sponsored Immigrants and Household Size",
        "pdf_part": "Parts 4-5",
        "local_pdf_pages": [3, 4, 5],
        "questions": [
            q("i864_only_principal_immigrant", "Is the sponsor sponsoring only the principal immigrant listed above?", "boolean", pdf_ref="Part 4, Item 1", ideal_answer=True, risk_when=False, risk_code="i864_multiple_immigrants"),
            q("i864_sponsoring_family_members", "Is the sponsor also sponsoring family members immigrating with the principal immigrant?", "boolean", pdf_ref="Part 4, Item 2", ideal_answer=False, risk_when=True, risk_code="i864_multiple_immigrants"),
            q("i864_total_immigrants", "Total number of immigrants sponsored on this affidavit", "number", pdf_ref="Part 4, Item 28", ideal_answer=1, risk_when="not_1", risk_code="i864_multiple_immigrants"),
            q("household_size", "Total I-864 household size", "number", pdf_ref="Part 5, Item 8", db_path="intake.household_size"),
            q("i864_sponsor_married_count", "Spouse count, if not already counted", "number", required=False, pdf_ref="Part 5, Item 3"),
            q("i864_dependent_children_count", "Dependent children count", "number", required=False, pdf_ref="Part 5, Item 4"),
            q("i864_other_dependents_count", "Other tax dependents count", "number", required=False, pdf_ref="Part 5, Item 5"),
            q("i864_prior_sponsored_immigrants_count", "Prior sponsored immigrants still supported count", "number", required=False, pdf_ref="Part 5, Item 6"),
            q("i864_household_members_combining_income_count", "Household members combining income count", "number", required=False, pdf_ref="Part 5, Item 7"),
        ],
    },
    {
        "id": "i864_page_05_income_assets_taxes",
        "title": "Employment, Income, Taxes, and Assets",
        "pdf_part": "Parts 6-7",
        "local_pdf_pages": [5, 6, 7, 8],
        "questions": [
            q(
                "employment_status",
                "Sponsor employment status",
                "select",
                pdf_ref="Part 6, Items 1-6",
                db_path="intake.employment_status",
                ideal_answer="employed",
                risk_when="unemployed",
                risk_code="i864_income_review",
                options=[
                    {"value": "employed", "label": "Employed"},
                    {"value": "self_employed", "label": "Self-employed"},
                    {"value": "retired", "label": "Retired"},
                    {"value": "unemployed", "label": "Unemployed"},
                ],
            ),
            q("petitioner_current_occupation", "Sponsor occupation or job title", "text", required=False, pdf_ref="Part 6, Item 1", db_path="intake.petitioner_current_occupation"),
            q("petitioner_current_employer", "Current employer name", "text", required=False, pdf_ref="Part 6, Item 2", db_path="intake.petitioner_current_employer"),
            q("annual_income", "Sponsor current individual annual income", "number", pdf_ref="Part 6, Item 7", db_path="intake.annual_income", risk_when="zero_or_less", risk_code="i864_income_review"),
            q("i864_household_income", "Total household income", "number", pdf_ref="Part 6, Item 15"),
            q("i864_filed_recent_tax_return", "Has the sponsor filed a Federal income tax return for the most recent tax year?", "boolean", pdf_ref="Part 6, Item 18", ideal_answer=True, risk_when=False, risk_code="i864_tax_review"),
            q("i864_tax_year_1", "Most recent tax year", "number", pdf_ref="Part 6, Item 19.a"),
            q("i864_tax_income_1", "Total income for most recent tax year", "number", pdf_ref="Part 6, Item 19.a"),
            q("i864_tax_year_2", "Second most recent tax year", "number", required=False, pdf_ref="Part 6, Item 19.b"),
            q("i864_tax_income_2", "Total income for second most recent tax year", "number", required=False, pdf_ref="Part 6, Item 19.b"),
            q("i864_tax_year_3", "Third most recent tax year", "number", required=False, pdf_ref="Part 6, Item 19.c"),
            q("i864_tax_income_3", "Total income for third most recent tax year", "number", required=False, pdf_ref="Part 6, Item 19.c"),
            q("i864_cash_assets", "Sponsor cash, savings, and checking account asset value", "number", required=False, pdf_ref="Part 7, Item 1"),
            q("i864_total_assets", "Total value of assets used, if any", "number", required=False, pdf_ref="Part 7, Items 4 and 10"),
        ],
    },
    {
        "id": "i864_page_06_contact_review",
        "title": "Sponsor Contact and Review",
        "pdf_part": "Parts 8-11",
        "local_pdf_pages": [9, 10, 11, 12],
        "questions": [
            q("petitioner_phone", "Sponsor daytime phone number", "text", pdf_ref="Part 8, Item 3", db_path="intake.petitioner_phone"),
            q("petitioner_mobile_phone", "Sponsor mobile phone number", "text", required=False, pdf_ref="Part 8, Item 4", db_path="intake.petitioner_mobile_phone"),
            q("petitioner_email", "Sponsor email address", "text", pdf_ref="Part 8, Item 5", db_path="intake.petitioner_email"),
            q("sponsor_reviewed_contract", "Sponsor has reviewed the contract, including the consumer report authorization, and understands the form must be signed", "boolean", pdf_ref="Part 8", ideal_answer=True, risk_when=False, risk_code="unsigned_form_risk"),
            q("interpreter_used", "Was an interpreter used?", "boolean", required=False, pdf_ref="Part 9", ideal_answer=False),
            q("preparer_used", "Was a preparer used?", "boolean", required=False, pdf_ref="Part 10", ideal_answer=False),
            q("additional_information_needed", "Is additional information needed on the continuation page?", "boolean", required=False, pdf_ref="Part 11", ideal_answer=False),
        ],
    },
]


SUPPLEMENTAL_FORM_CONFIGS: dict[str, dict[str, Any]] = {
    "i130": {
        "form_key": "i130",
        "form_code": "I-130",
        "title": "Petition for Alien Relative",
        "version": I130_QUESTIONNAIRE_VERSION,
        "verified_on": FAMILY_FORMS_VERIFIED_ON,
        "official_url": I130_OFFICIAL_URL,
        "official_pdf_url": I130_OFFICIAL_PDF_URL,
        "local_template_pdf": "blank-immigration-documents/i-130.pdf",
        "sources": [
            *FAMILY_FORM_SOURCES,
            {
                "label": "Local blank I-130 PDF",
                "url": "blank-immigration-documents/i-130.pdf",
                "verified_on": FAMILY_FORMS_VERIFIED_ON,
                "notes": "Local editable template used for development PDF field mapping.",
            },
        ],
        "pages": I130_QUESTIONNAIRE,
    },
    "i130a": {
        "form_key": "i130a",
        "form_code": "I-130A",
        "title": "Supplemental Information for Spouse Beneficiary",
        "version": I130A_QUESTIONNAIRE_VERSION,
        "verified_on": FAMILY_FORMS_VERIFIED_ON,
        "official_url": I130_OFFICIAL_URL,
        "official_pdf_url": I130A_OFFICIAL_PDF_URL,
        "local_template_pdf": "blank-immigration-documents/i-130a.pdf",
        "sources": [
            *FAMILY_FORM_SOURCES,
            {
                "label": "Local blank I-130A PDF",
                "url": "blank-immigration-documents/i-130a.pdf",
                "verified_on": FAMILY_FORMS_VERIFIED_ON,
                "notes": "Local editable template used for development PDF field mapping.",
            },
        ],
        "pages": I130A_QUESTIONNAIRE,
    },
    "i765": {
        "form_key": "i765",
        "form_code": "I-765",
        "title": "Application for Employment Authorization",
        "version": "i765-08-21-25-local-v1",
        "verified_on": I765_VERIFIED_ON,
        "official_url": "https://www.uscis.gov/i-765",
        "official_pdf_url": "https://www.uscis.gov/sites/default/files/document/forms/i-765.pdf",
        "local_template_pdf": "blank-immigration-documents/i-765.pdf",
        "sources": [
            {
                "label": "USCIS Form I-765 landing page",
                "url": "https://www.uscis.gov/i-765",
                "verified_on": I765_VERIFIED_ON,
                "notes": "Official form page checked for source context; verify current edition before filing.",
            },
            {
                "label": "Local blank I-765 PDF",
                "url": "blank-immigration-documents/i-765.pdf",
                "verified_on": I765_VERIFIED_ON,
                "notes": "Local editable template used for development PDF field mapping.",
            },
            I94_INFO_SOURCE,
        ],
        "pages": I765_QUESTIONNAIRE,
    },
    "i131": {
        "form_key": "i131",
        "form_code": "I-131",
        "title": "Application for Travel Documents, Parole Documents, and Arrival/Departure Records",
        "version": "i131-01-20-25-local-v1",
        "verified_on": I131_VERIFIED_ON,
        "official_url": "https://www.uscis.gov/i-131",
        "official_pdf_url": "https://www.uscis.gov/sites/default/files/document/forms/i-131.pdf",
        "local_template_pdf": "blank-immigration-documents/i-131.pdf",
        "sources": [
            {
                "label": "USCIS Form I-131 landing page",
                "url": "https://www.uscis.gov/i-131",
                "verified_on": I131_VERIFIED_ON,
                "notes": "USCIS page listed edition 01/20/25 when checked; verify current edition and fees before filing.",
            },
            {
                "label": "USCIS Form I-131 Instructions PDF",
                "url": "https://www.uscis.gov/sites/default/files/document/forms/i-131instr.pdf",
                "verified_on": I131_VERIFIED_ON,
                "notes": "Official instructions checked for pending-I-485 advance parole evidence, identity document, I-94/status, travel explanation, and passport-style photo requirements.",
            },
            {
                "label": "Local blank I-131 PDF",
                "url": "blank-immigration-documents/i-131.pdf",
                "verified_on": I131_VERIFIED_ON,
                "notes": "Local editable template used for development PDF field mapping.",
            },
            I94_INFO_SOURCE,
        ],
        "pages": I131_QUESTIONNAIRE,
    },
    "i864": {
        "form_key": "i864",
        "form_code": "I-864",
        "title": "Affidavit of Support Under Section 213A of the INA",
        "version": "i864-10-17-24-v1",
        "verified_on": SUPPLEMENTAL_FORMS_VERIFIED_ON,
        "official_url": "https://www.uscis.gov/i-864",
        "official_pdf_url": "https://www.uscis.gov/sites/default/files/document/forms/i-864.pdf",
        "local_template_pdf": "blank-immigration-documents/i-864.pdf",
        "sources": [
            {
                "label": "USCIS Form I-864 landing page",
                "url": "https://www.uscis.gov/i-864",
                "verified_on": I864_EDITION_VERIFIED_ON,
                "notes": "USCIS page listed edition 08/24/26, the only edition it accepts beginning Oct. 1, 2026.",
            },
            {
                "label": "USCIS Form I-864 instructions",
                "url": "https://www.uscis.gov/sites/default/files/document/forms/i-864instr.pdf",
                "verified_on": I864_HOUSEHOLD_HELP_VERIFIED_ON,
                "notes": "Used for Part 5 household-size guidance and the no-double-counting explanation.",
            },
            {
                "label": "Local blank I-864 PDF",
                "url": "blank-immigration-documents/i-864.pdf",
                "verified_on": I864_EDITION_VERIFIED_ON,
                "notes": "Local editable template used for development PDF field mapping.",
            },
        ],
        "pages": I864_QUESTIONNAIRE,
    },
}


QUESTION_LABEL_STARTERS = (
    "is ",
    "are ",
    "was ",
    "were ",
    "do ",
    "does ",
    "did ",
    "has ",
    "have ",
    "had ",
    "can ",
    "will ",
    "would ",
    "should ",
)


def _lower_first(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return stripped
    return f"{stripped[:1].lower()}{stripped[1:]}"


def _is_question_label(label: str) -> bool:
    normalized = label.strip().lower()
    return label.strip().endswith("?") or normalized.startswith(QUESTION_LABEL_STARTERS)


def _clean_field_label(label: str, prefixes: tuple[str, ...] = ()) -> str:
    cleaned = label.strip().rstrip(".")
    lowered = cleaned.lower()
    for prefix in prefixes:
        if lowered.startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
            break
    return _lower_first(cleaned)


def _person_question_prompt(label: str, subject: str, prefixes: tuple[str, ...] = ()) -> str:
    if _is_question_label(label):
        return f"Answer this for the {subject}: {_lower_first(label)}"
    return f"This asks for the {subject}'s {_clean_field_label(label, prefixes)}."


def _default_supplemental_help(
    form_key: str,
    question_id: str,
    label: str,
    answer_type: str,
    *,
    required: bool,
    risk_code: str | None,
) -> tuple[str, str]:
    form_code = SUPPLEMENTAL_FORM_CONFIGS.get(form_key, {}).get("form_code", form_key.upper())
    required_note = "This section expects an answer." if required else "If it truly does not apply, leave it blank or flag it for review."

    if question_id.startswith("beneficiary_"):
        subject = "principal immigrant" if form_key == "i864" else "applicant"
        context = (
            "Use the same principal immigrant identity and address facts that appear on the immigrant's application and civil records."
            if form_key == "i864"
            else f"Use the same applicant details on Form {form_code}, the I-485, and supporting records."
        )
        return (
            _person_question_prompt(label, subject, ("applicant ", "principal immigrant ")),
            f"Answer for the {subject}, not the petitioner or sponsor unless this question says otherwise. {required_note} {context}",
        )
    if question_id.startswith("petitioner_"):
        return (
            _person_question_prompt(label, "sponsor", ("sponsor ",)),
            f"Answer for the person signing Form {form_code} as sponsor. {required_note} Keep sponsor identity, address, income, and tax facts consistent with evidence.",
        )
    if risk_code:
        return (
            f"Answer this carefully for Form {form_code}: {_lower_first(label)}",
            f"The stored walkthrough for Form {form_code} treats this as a review-sensitive area. A non-standard answer may need extra evidence, official instructions review, or professional review.",
        )
    if answer_type in {"boolean", "select", "multi_select"}:
        return (
            "Choose the option that matches the real facts for this form and this person.",
            f"{required_note} If none of the choices fit, pause and review the official instructions instead of forcing an answer.",
        )
    return (
        f"This asks for the Form {form_code} item labeled: {label}.",
        f"{required_note} Use the stored teaching transcript for plain-language context, but rely on official USCIS instructions for filing requirements.",
    )


def _apply_supplemental_help(form_key: str, config: dict[str, Any]) -> None:
    source = FORM_TEACHING_SOURCES.get(form_key)
    if source:
        config["sources"].append(
            {
                "label": source["label"],
                "url": source["url"],
                "verified_on": source["fetched_on"],
                "notes": (
                    f"Teaching reference fetched with youtube-transcript-api and stored at {source['transcript_path']}. "
                    f"Captions are {source['caption_type']}; not an official USCIS source."
                ),
            }
        )
    overrides = SUPPLEMENTAL_HELP_OVERRIDES.get(form_key, {})
    for page in config["pages"]:
        for question in page["questions"]:
            plain_language, deep_explanation = overrides.get(
                question["id"],
                _default_supplemental_help(
                    form_key,
                    question["id"],
                    question["label"],
                    question["answer_type"],
                    required=bool(question.get("required")),
                    risk_code=question.get("risk_code"),
                ),
            )
            question["plain_language"] = plain_language
            question["deep_explanation"] = deep_explanation
            question["teaching_source"] = {**source, "pdf_ref": question["pdf_ref"]} if source else None


for _form_key, _config in SUPPLEMENTAL_FORM_CONFIGS.items():
    _apply_supplemental_help(_form_key, _config)


def get_supplemental_form_config(form_key: str) -> dict[str, Any]:
    normalized = form_key.lower().replace("-", "")
    if normalized not in SUPPLEMENTAL_FORM_CONFIGS:
        raise KeyError(form_key)
    return SUPPLEMENTAL_FORM_CONFIGS[normalized]


def all_supplemental_form_questions(form_key: str) -> list[dict[str, Any]]:
    config = get_supplemental_form_config(form_key)
    return [question for page in config["pages"] for question in page["questions"]]
