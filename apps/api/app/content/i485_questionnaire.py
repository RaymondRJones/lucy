from __future__ import annotations

from typing import Any

from app.content.admission_classes import CLASS_OF_ADMISSION_OPTIONS, I94_INFO_SOURCE


I485_QUESTIONNAIRE_VERSION = "i485-09-18-26-marriage-v2"
I485_VERIFIED_ON = "2026-10-30"
I485_OFFICIAL_URL = "https://www.uscis.gov/i-485"
I485_OFFICIAL_PDF_URL = "https://www.uscis.gov/sites/default/files/document/forms/i-485.pdf"
I485_OFFICIAL_INSTRUCTIONS_URL = "https://www.uscis.gov/sites/default/files/document/forms/i-485instr.pdf"
I485_LOCAL_REFERENCE_PDF = "MARRIAGE_EVIDENCE/I-485/Sample-Form-I-485.pdf"

I485_SOURCES: list[dict[str, str]] = [
    {
        "label": "USCIS Form I-485 landing page",
        "url": I485_OFFICIAL_URL,
        "verified_on": I485_VERIFIED_ON,
        "notes": "USCIS page listed edition 09/18/26 with no grace period; the 01/20/25 and 09/04/26 editions are rejected if postmarked on or after Sept. 18, 2026.",
    },
    {
        "label": "USCIS Form I-485 PDF",
        "url": I485_OFFICIAL_PDF_URL,
        "verified_on": I485_VERIFIED_ON,
        "notes": "Official blank form source for regenerating question and coordinate maps.",
    },
    {
        "label": "USCIS Form I-485 Instructions PDF",
        "url": I485_OFFICIAL_INSTRUCTIONS_URL,
        "verified_on": I485_VERIFIED_ON,
        "notes": "Official USCIS instructions used as the primary source for plain-language tooltip guidance.",
    },
    I94_INFO_SOURCE,
    {
        "label": "Local filled I-485 reference PDF",
        "url": I485_LOCAL_REFERENCE_PDF,
        "verified_on": I485_VERIFIED_ON,
        "notes": "Flattened local PDF used only as an extraction-layout reference; do not edit the source file.",
    },
]

I485_TOOLTIP_SOURCE: dict[str, str] = {
    "label": "USCIS Form I-485 instructions",
    "url": I485_OFFICIAL_INSTRUCTIONS_URL,
    "fetched_on": I485_VERIFIED_ON,
}

I485_PART_GUIDANCE: dict[str, str] = {
    "Part 1": (
        "Part 1 identifies the applicant and the most recent U.S. entry. USCIS compares these answers with passports, "
        "visas, I-94 records, prior USCIS records, and address history, so use document-based answers and flag any mismatch."
    ),
    "Part 2": (
        "Part 2 tells USCIS why the applicant is eligible to file I-485. In this MVP's happy path, the expected answer is "
        "principal applicant in the spouse-of-U.S.-citizen family category; other categories should be treated as review flags."
    ),
    "Part 3": (
        "Part 3 asks whether the applicant is required to submit Form I-864 or qualifies for a narrow exemption. Most "
        "marriage-based applicants need Form I-864 from the petitioning spouse or sponsor."
    ),
    "Part 4": (
        "Part 4 collects prior immigrant visa/permanent residence history and five-year employment, education, unemployment, "
        "or retirement activity. Avoid gaps; if one printed line is not enough, preserve the rest for Part 14."
    ),
    "Part 5": (
        "Part 5 is about the applicant's parents. USCIS uses it for identity and background matching, so names, birth dates, "
        "and countries should come from reliable family or civil records when available."
    ),
    "Part 6": (
        "Part 6 covers marital history and the current spouse. In this workflow the expected facts are currently married, "
        "first marriage, and spouse is a U.S. citizen; prior marriages or different status should be surfaced for review."
    ),
    "Part 7": (
        "Part 7 asks for all living children, not only children immigrating with the applicant. Include children anywhere in "
        "the world and use Part 14 if the form does not have enough space."
    ),
    "Part 8": (
        "Part 8 is biographic information used for identification. Answer using ordinary current physical characteristics "
        "and the form's listed options rather than trying to match a passport exactly if the passport does not contain that field."
    ),
    "Part 9": (
        "Part 9 is a long eligibility and admissibility section. Read every question literally, answer truthfully, and treat "
        "yes answers about immigration violations, criminal history, public charge, security, or fraud as review-sensitive."
    ),
    "Part 10": (
        "Part 10 is the applicant's contact information, certification, and signature section. The draft can prepare the text, "
        "but the paper filing still needs the applicant's proper signature before mailing."
    ),
    "Part 11": (
        "Part 11 is for interpreter information if someone translated the questions or answers for the applicant. If no one "
        "interpreted, this section is normally not used."
    ),
    "Part 12": (
        "Part 12 is for someone who prepared the application other than the applicant. It is separate from the spouse simply "
        "helping gather documents, unless that person actually prepared the form for the applicant."
    ),
    "Part 13": (
        "Part 13 contains preparer signature details on the USCIS form edition. Use it only when a preparer section is required "
        "and keep the name, address, and signature workflow complete."
    ),
    "Part 14": (
        "Part 14 is for extra space and explanations. A useful continuation identifies the page, part, item number, and the "
        "specific facts needed to understand the original answer."
    ),
}

I485_HELP_OVERRIDES: dict[str, tuple[str, str]] = {
    "beneficiary_a_number": (
        "Use the applicant's USCIS Alien Registration Number only if one was already assigned.",
        "USCIS guidance notes that people with prior immigration cases may have an A-Number. If it is shorter than nine digits, USCIS forms often expect leading zeroes so the number fills nine spaces. Do not invent one if USCIS never assigned it.",
    ),
    "beneficiary_other_names": (
        "List every other name the applicant has used since birth.",
        "This includes prior legal names, nicknames used on records, aliases, and different spellings that appear on identity documents, supporting evidence, or prior immigration paperwork. Extra names should be continued in Part 14.",
    ),
    "beneficiary_used_other_dob": (
        "Answer yes if any document or prior application ever used a different date of birth.",
        "USCIS instructions emphasize that even mistakes on old documents should be disclosed and explained. A yes answer usually needs a short Part 14 or supporting-document explanation so the difference is reviewable.",
    ),
    "beneficiary_has_a_number": (
        "This repeats whether USCIS has ever assigned the applicant an A-Number.",
        "If the answer is yes, use the same A-Number consistently. If the applicant has never had a USCIS case that generated one, answer no or leave the number field blank where allowed.",
    ),
    "beneficiary_has_other_a_numbers": (
        "Answer yes if the applicant ever had a different A-Number in another USCIS matter.",
        "Prior immigration files can create more than one A-Number. The purpose is to connect old records to this filing, so disclose any other assigned number rather than only the one used today.",
    ),
    "beneficiary_country_of_citizenship": (
        "Use the citizenship tied to the passport or travel document used for the most recent U.S. entry.",
        "USCIS guidance allows listing additional citizenships in Part 14. This field should not be confused with country of birth; it asks for nationality or citizenship.",
    ),
    "beneficiary_uscis_online_account_number": (
        "Use the applicant's USCIS online account number only if the applicant has one.",
        "This is not the petitioner's online account number. USCIS instructions say an applicant usually has this only after filing a USCIS application online.",
    ),
    "beneficiary_passport_number": (
        "Enter the passport or travel document used for the applicant's most recent U.S. arrival.",
        "USCIS guidance emphasizes that this is about the document used at last entry, even if it is now expired. Do not substitute a newer passport that was never used to enter the United States.",
    ),
    "beneficiary_passport_expiration": (
        "Use the expiration date from the passport or travel document used at last arrival.",
        "Match this to the same document listed in the passport or travel document number field. It may be expired now; the form is asking what was used for that entry.",
    ),
    "beneficiary_passport_country": (
        "Enter the country that issued the passport or travel document used at last arrival.",
        "Keep this tied to the last-entry document, not necessarily the applicant's newest passport or every citizenship the applicant has.",
    ),
    "beneficiary_visa_number": (
        "Use the nonimmigrant visa number from the visa used for the most recent arrival, if there was one.",
        "USCIS guidance points users to the red visa number on many visa foils. If the applicant did not use a visa for the last entry, this may not apply.",
    ),
    "beneficiary_last_arrival_city": (
        "This means the port of entry city, not the final travel destination.",
        "Use the city where the applicant was inspected or arrived into the United States. For flights, that is usually the airport where entry processing happened.",
    ),
    "beneficiary_last_arrival_state": (
        "This is the state for the port of entry used at last arrival.",
        "Pair it with the arrival city. USCIS instructions distinguish this from where the applicant finally traveled or currently lives.",
    ),
    "beneficiary_last_arrival_type": (
        "Choose how the applicant was allowed into the United States at the last entry.",
        "USCIS instructions separate admission with a visa or visa waiver, parole such as advance parole or humanitarian parole, and entry without admission or parole. Entry without inspection is a serious review flag for adjustment cases.",
    ),
    "beneficiary_class_of_admission": (
        "Use the Class of Admission (COA) code from the most recent I-94 or parole record, such as B-2.",
        "This should match the code shown on the I-94 used for the most recent entry or status change. The dropdown includes common choices to avoid typos, but the source record is the authority.",
    ),
    "beneficiary_i94_number": (
        "Enter the most recent I-94 arrival/departure number.",
        "USCIS instructions explain that most applicants retrieve this from CBP online rather than a paper card. Use the latest I-94 if a later status change created a new one.",
    ),
    "beneficiary_last_arrival_first_us_presence": (
        "Answer yes only if the applicant's most recent arrival was also the first time they were ever physically present in the United States.",
        "This is asking about any prior physical presence in the United States, not just prior green card filings, prior long-term stays, or prior entries in the same immigration status. If the applicant lived, studied, visited, or otherwise spent time in the United States before the most recent arrival, answer no.",
    ),
    "beneficiary_status_expires_on": (
        "Use the authorized stay expiration shown on the most recent I-94.",
        "Some applicants, such as certain students, may see D/S instead of a date. If the form cannot accept that directly, preserve the issue for review notes rather than forcing an invented date.",
    ),
    "beneficiary_current_immigration_status": (
        "Describe the applicant's current status if it differs from the status at last arrival.",
        "If the applicant is still in the same status, this may match the I-94 class. If the applicant overstayed, the official I-485 guidance gives examples like visa overstay or out of status.",
    ),
    "beneficiary_current_status_expires_on": (
        "Use the expiration date for the applicant's current status, if there is one.",
        "If the current status came from a later change or extension, use that latest record. Some categories do not show a normal expiration date.",
    ),
    "beneficiary_alien_crewman_visa": (
        "Answer whether the applicant was ever issued a crewman visa.",
        "USCIS form wording identifies this as the C/D crewman visa area. A yes answer can affect adjustment eligibility and deserves careful review.",
    ),
    "beneficiary_joined_vessel_or_aircraft": (
        "Answer whether the applicant entered to work as crew on a vessel or aircraft.",
        "This is separate from ordinary travel by plane or ship. It asks about arriving to join crew work, which can raise adjustment eligibility concerns.",
    ),
    "beneficiary_current_address_line1": (
        "Use the applicant's actual current U.S. physical residence.",
        "USCIS instructions distinguish physical address from mailing address. This should be where the applicant actually lives now, not a foreign address or only a mail pickup address.",
    ),
    "beneficiary_address_since": (
        "Enter when the applicant first began living at the current physical address.",
        "For a recent arrival living with the petitioner, this may be the most recent U.S. arrival date if that is when the applicant started residing there.",
    ),
    "beneficiary_current_address_five_years": (
        "Answer whether this one current address covers the full last five years.",
        "If no, the form needs the directly prior address and Part 14 may be needed for any additional addresses required to cover the full five-year history.",
    ),
    "beneficiary_prior_address_history": (
        "Add prior residences until the applicant's last five years of address history are covered.",
        "The I-485 has limited on-form space. USCIS instructions explain that more addresses should be continued in Part 14 with the page, part, item number, address, and dates lived there.",
    ),
    "beneficiary_recent_foreign_address": (
        "Provide the most recent foreign address where the applicant lived for more than one year, if it was not already listed.",
        "This can go beyond the five-year address history. If the same foreign address already appears in the prior-address list, flag it as duplicate rather than inventing a second version.",
    ),
    "beneficiary_has_ssn": (
        "Answer whether the Social Security Administration has already issued the applicant an SSN.",
        "A Social Security number stays the same for life. If the applicant already has one, do not request or enter a different number.",
    ),
    "beneficiary_wants_ssn": (
        "Answer whether the applicant wants a Social Security card issued through this filing.",
        "USCIS guidance generally supports requesting one if the applicant does not have an SSN. Applicants who already have a restricted card may also request a new card while keeping the same number.",
    ),
    "beneficiary_ssn_disclosure_consent": (
        "If requesting an SSN card, consent allows USCIS and SSA to share the needed information.",
        "USCIS instructions explain that this consent is what lets the applicant avoid a separate Social Security office application for the card.",
    ),
    "i485_in_removal_proceedings": (
        "Answer yes only if this I-485 is being filed with EOIR while the applicant is in immigration court proceedings.",
        "This is not asking about ordinary USCIS filing. Removal, exclusion, rescission, or deportation proceedings are high-stakes and should be reviewed carefully.",
    ),
    "i485_underlying_petition_receipt": (
        "Enter the receipt number for the petition that supports this I-485, if already filed.",
        "For a family case, this is often an I-130 receipt. USCIS guidance notes that if I-130 and I-485 are mailed together and no petition was filed before, this can be blank.",
    ),
    "i485_priority_date": (
        "Use the priority date from the underlying petition receipt notice, if there is one.",
        "USCIS instructions explain that the priority date is usually the date USCIS officially received the petition. Concurrent immediate-relative filings may not have this yet.",
    ),
    "i485_applicant_role": (
        "Principal means the applicant has their own petition; derivative means they are included through another person's case.",
        "USCIS instructions explain that spouses, parents, and children of U.S. citizens usually have separate petitions and are principals. Derivatives still file their own I-485 but follow the principal's category.",
    ),
    "i485_family_category": (
        "Choose the family relationship that is the basis for adjustment.",
        "For this app's standard marriage flow, the expected category is spouse of a U.S. citizen. USCIS instructions warn that selecting the wrong category, multiple categories, or no category can cause rejection.",
    ),
    "i485_employment_based_category": (
        "Answer whether this I-485 is based on an employment immigrant category.",
        "A standard marriage-based packet normally answers no. A yes answer means this is outside Lucy's basic U.S.-citizen-spouse workflow.",
    ),
    "i485_special_category": (
        "Answer whether the filing is based on a special non-family category.",
        "Examples include asylum/refugee, crime-victim, diversity, and other special programs. These are different category paths from ordinary family adjustment.",
    ),
    "i485_245i": (
        "Answer whether the applicant is using INA 245(i) to adjust despite certain entry or filing issues.",
        "Most applicants in this happy-path workflow answer no. A yes answer points to a narrow 245(i) path and should be reviewed carefully.",
    ),
    "i485_cspa": (
        "Answer whether the applicant is relying on the Child Status Protection Act.",
        "USCIS instructions explain this generally protects some children from aging out after a case started before age 21. It is usually not part of a spouse-based adjustment case.",
    ),
    "i485_i864_exemption": (
        "Most family-based applicants are not exempt from Form I-864.",
        "USCIS instructions say the affidavit of support is required in most family cases and that the new I-485 replaced a separate exemption form for the few applicants who truly qualify for an exemption.",
    ),
    "prior_immigrant_visa_application": (
        "Answer yes if the applicant actually submitted an immigrant visa application through consular processing.",
        "USCIS instructions distinguish this from merely having a petition filed. It points to DS-260 submission through consular processing as the kind of prior immigrant visa application this asks about.",
    ),
    "prior_permanent_residence_application": (
        "Answer yes if the applicant previously filed an I-485 or otherwise applied for permanent residence in the United States.",
        "This asks about a prior green card application inside the United States, not a tourist visa or a petition that never became an adjustment filing.",
    ),
    "prior_lpr_status_rescinded": (
        "Answer yes if the applicant once had green card status that was later taken away or rescinded.",
        "USCIS instructions give this as a prior permanent residence history question. It is different from voluntarily abandoning residence or never having been an LPR.",
    ),
    "beneficiary_employment_history": (
        "Cover employment, school, self-employment, unemployment, and retirement for the last five years.",
        "USCIS instructions emphasize that gaps matter. If unemployed or retired, include the source of financial support, and continue extra entries in Part 14 with addresses, dates, occupation or status, and support details when needed.",
    ),
    "beneficiary_foreign_employer_or_school": (
        "List the most recent employer or school outside the United States if it is not already in the five-year history.",
        "If that foreign employer or school is already covered above, the official I-485 guidance says this may be left blank or marked not applicable after printing. If it predates the five-year history, capture it here.",
    ),
    "beneficiary_marriage_count": (
        "Count every marriage, including the current marriage.",
        "USCIS guidance calls out a common mistake: people write zero because they think USCIS asks for prior marriages only. If the applicant is currently married for the first time, the count is one.",
    ),
    "current_spouse_applying_with_beneficiary": (
        "Answer yes only if the spouse is applying as the applicant's derivative on the same underlying case.",
        "For a U.S. citizen or permanent resident petitioner spouse, the answer is normally no. The question is about derivative applicants, not whether the spouse is involved in the packet.",
    ),
    "beneficiary_prior_marriages": (
        "Include any prior marriages and how each legally ended.",
        "USCIS instructions say divorce and death of a prior spouse both count. If there is more than one prior spouse, continue the details in Part 14.",
    ),
    "children_count": (
        "Count all living children anywhere in the world.",
        "USCIS instructions explain this includes minor children, adult children, biological children, legally adopted children, and current stepchildren of any age.",
    ),
    "children_details": (
        "Provide the requested child details for each child counted.",
        "If more room is needed, continue in Part 14. Applying with the applicant usually means the child is a derivative, not simply that the child has their own separate petition.",
    ),
    "organizations_membership": (
        "Answer yes for memberships or associations with groups anywhere in the world.",
        "USCIS instructions give broad examples: professional organizations, unions, political parties, clubs, churches, and similar groups. The purpose is security review, so describe the organization and involvement if yes.",
    ),
    "organizations_details": (
        "If the applicant answered yes to organization membership, describe each organization and the applicant's role or involvement.",
        "USCIS instructions treat this as a security-review section. Include practical details such as organization name, location, membership dates, position or role, and whether the applicant is still involved. Use Part 14 if the form does not have enough room.",
    ),
    "visa_denied": (
        "Answer yes if any U.S. visa application was denied.",
        "USCIS instructions say a yes answer should be explained in Part 14 with what visa was requested, when, and what happened.",
    ),
    "admission_denied": (
        "Answer yes if the applicant was turned away at a U.S. port of entry.",
        "This includes being refused entry at an airport, land border, or other port of entry. Explain a yes answer in Part 14.",
    ),
    "worked_without_authorization": (
        "Answer yes if the applicant ever worked in the United States without employment authorization.",
        "USCIS guidance notes that immediate relatives of U.S. citizens may have certain unauthorized-work issues forgiven, but the form still asks for truthful disclosure and dates/details.",
    ),
    "violated_nonimmigrant_status": (
        "Answer yes if the applicant broke the terms of a nonimmigrant status.",
        "USCIS instructions explain that unauthorized work and visa overstay are common examples. If yes, explain what happened and when in Part 14.",
    ),
    "relief_from_removal": (
        "Answer yes if the applicant ever applied for protection or relief from removal.",
        "USCIS instructions give examples such as asylum, DACA, and TPS. This is broader than only being in court.",
    ),
    "j_exchange_two_year_rule": (
        "Answer based on whether a J visa made the applicant subject to the two-year home-residence requirement.",
        "USCIS guidance points applicants to the J visa page, where this may be noted as 212(e). If yes, the related waiver/compliance questions matter.",
    ),
    "ever_arrested_cited_charged_detained": (
        "Answer yes for arrests, citations, charges, detentions, or diversion anywhere.",
        "Read this broadly: citations can include traffic tickets, and expunged, sealed, or cleared records may still need disclosure. A yes answer should trigger careful evidence review and often attorney review.",
    ),
    "ever_committed_crime": (
        "Answer whether the applicant ever committed a crime, even without arrest or conviction.",
        "This is intentionally broader than court records. USCIS guidance advises careful reading of every criminal-history question and professional help when there are complications.",
    ),
    "ever_pled_or_convicted": (
        "Answer yes for guilty pleas or convictions.",
        "USCIS instructions warn that some guilty pleas can have immigration consequences even if the criminal case seemed minor, so a yes answer should not be handled casually.",
    ),
    "criminal_explanations": (
        "Use this box to explain any yes answer in the criminal-history section and to track court disposition records.",
        "For each yes answer, keep the explanation tied to the exact incident: what happened, when and where it happened, the charge or citation, the final outcome, and what official records are available. Treat this area as a professional-review trigger when facts are not simple.",
    ),
    "weapons_training_or_violence": (
        "Answer yes if the applicant had weapons or military-type training or participated in listed violent activity.",
        "USCIS guidance notes that some countries require military training. Required service can still make the truthful answer yes, with an explanation in Part 14.",
    ),
    "military_police_armed_group": (
        "Answer whether the applicant served in military, police, armed groups, or weapon-using groups.",
        "USCIS instructions group this with security questions that need careful reading and explanation when the answer is yes, especially where service was compulsory.",
    ),
    "public_charge_exempt_category": (
        "For family-based I-130 adjustment, most applicants are subject to public charge and should not select an exemption.",
        "USCIS instructions explain this asks whether the category is exempt, not whether the applicant is likely to become a public charge. Family, employment, and diversity categories are generally subject to the public charge questions.",
    ),
    "household_size": (
        "Count the people whose income, assets, and liabilities are included in Items 58-60.",
        "The I-485 instructions say a household size given in Item 57 should include any individuals whose income, assets, and liabilities are reported in Items 58-60. This count may differ from the Form I-864 household size.",
    ),
    "public_charge_family_status": (
        "Describe the applicant's family status in your own words, such as who is in the household.",
        "Item 57 is now a written description instead of a number. If this is left blank, Lucy drafts it from the marital status and household size answers so you can review it. Long descriptions continue in Part 14.",
    ),
    "annual_household_income_band": (
        "Choose the band for the household's annual income, leaving out any income from means-tested public benefits.",
        "The I-485 instructions allow income provided to the household from outside sources, such as alimony or child support. They say to exclude means-tested public benefit income and income from illegal activities. Keep the answer consistent with the facts and documents.",
    ),
    "household_assets_band": (
        "Choose the band for assets owned by members of the household.",
        "The I-485 instructions give examples such as bank deposits, annuities, stocks, bonds, mutual funds, certificates of deposit, retirement accounts, educational accounts, and real estate. Assets not owned by household members may not be included.",
    ),
    "household_liabilities_band": (
        "Choose the band for debts owed by members of the household, both secured and unsecured.",
        "The I-485 instructions give examples such as mortgages, car loans, unpaid child or spousal support, unpaid taxes, and current credit card balances.",
    ),
    "certifications_licenses_skills": (
        "List each skill on its own line, including workforce skills, training, occupational licenses, foreign languages, and certificates.",
        "The I-485 instructions ask for all skills in Item 62, including licenses, foreign language skills, and certificates for skilled trades or completed occupational programs. The form has eight rows; Lucy continues any extra lines in Part 14.",
    ),
    "received_means_tested_public_benefit": (
        "Answer yes if the applicant has ever received, or is currently receiving, any means-tested public benefit.",
        "This edition asks about any means-tested public benefit, past or current at filing, not only the cash assistance and long-term care named on the prior edition. An earlier answer to the old question does not carry over. The form instructions do not list the programs, so review the USCIS Policy Manual (Volume 8, Part G) or ask a qualified legal professional if unsure which programs count.",
    ),
    "means_tested_benefit_history": (
        "For each benefit, give the name, start and end dates, dollar amount if applicable, and the reason it was received.",
        "The I-485 instructions ask for a detailed explanation of why each benefit was received, such as job loss, long-term illness, or insufficient income. The form has four rows and a narrow Reason column, so Lucy continues long reasons and extra benefits in Part 14.",
    ),
    "unlawful_presence_after_1997": (
        "Answer whether the applicant had unlawful presence after April 1, 1997, including visa overstay.",
        "USCIS instructions explain that overstay generally begins the day after the I-94 authorized-stay date. If currently overstaying, details may run to present and should be reviewed carefully.",
    ),
    "illegal_reentry_after_unlawful_presence_or_removal": (
        "Answer whether the applicant left after unlawful presence or removal and then reentered or tried to reenter without admission.",
        "USCIS instructions distinguish this from ordinary unlawful presence. This question is about a later attempted or actual entry without inspection after specific prior immigration problems.",
    ),
    "beneficiary_phone": (
        "Provide a reliable phone number for the applicant.",
        "USCIS guidance notes that if daytime and mobile are the same, users often repeat it or leave one blank where allowed. If the applicant has no U.S. number, a petitioner's number may be used for contact.",
    ),
    "applicant_reviewed_certification": (
        "Confirm the applicant reviewed the certification and knows the final filed form needs an original signature.",
        "USCIS instructions say the applicant signs after printing, typically in black pen. This app can generate a draft, but the paper filing still needs the proper signature workflow.",
    ),
    "interpreter_used": (
        "Answer yes if someone translated or interpreted the form questions for the applicant.",
        "USCIS instructions say a petitioner can be the interpreter if they actually interpreted the questions. Interpreter details belong in the interpreter section.",
    ),
    "preparer_used": (
        "Answer yes if someone other than the applicant prepared the form.",
        "If another person completed the form for the applicant, the preparer section should identify that person. This is separate from merely discussing the form.",
    ),
    "additional_information_needed": (
        "Answer yes only if an I-485 answer needs more room or a written explanation in Part 14.",
        "Use Part 14 for extra names, addresses, employment history, denials, status violations, unlawful-presence dates, and other explanations. A useful Part 14 note identifies the page, part, item number, and the extra facts needed to understand the original answer. If every answer fits and nothing needs explanation, answer no.",
    ),
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


def _default_i485_help(
    question_id: str,
    label: str,
    answer_type: str,
    *,
    required: bool,
    pdf_ref: str,
    risk_code: str | None,
) -> tuple[str, str]:
    applicant_note = "Answer for the green card applicant, not the U.S. citizen petitioner, unless the question specifically asks about the spouse or petitioner."
    required_note = "This section expects an answer." if required else "If it truly does not apply, leave it blank or flag it for review notes."

    if question_id.startswith("parent"):
        return (
            _person_question_prompt(label, "applicant's biological or adoptive parent", ("parent 1 ", "parent 2 ")),
            "USCIS instructions say the parent section is about the applicant's parents, not step-parents, and either parent can be listed first. If a birth date is truly unknown, avoid guessing and flag it for review.",
        )
    if question_id.startswith("petitioner_") or question_id == "spouse_us_military":
        return (
            _person_question_prompt(
                label,
                "current spouse",
                ("current spouse ",),
            ),
            f"For a marriage-based case, {required_note.lower()} Keep spouse identity, citizenship, address, marriage place, and marriage date consistent across the I-130, I-485, civil records, and supporting evidence.",
        )
    if question_id.startswith("marriage_place_"):
        return (
            f"This asks for the {_clean_field_label(label, ('place of current marriage: ',))} where the current marriage took place.",
            f"For a marriage-based case, {required_note.lower()} Keep the marriage place consistent across the I-130, I-485, civil marriage record, and supporting evidence.",
        )
    if question_id.startswith("marriage_"):
        return (
            "This asks for the date the applicant and current spouse legally married.",
            f"For a marriage-based case, {required_note.lower()} Keep the marriage date consistent across the I-130, I-485, civil marriage record, and supporting evidence.",
        )
    if question_id.startswith("children_"):
        return (
            "This asks for the child details required for every child who fits the form's definition.",
            "USCIS instructions explain that all living children anywhere in the world can matter, including adult children and current stepchildren. Use Part 14 if the form runs out of room.",
        )
    if question_id.startswith("beneficiary_current_address") or question_id in {
        "beneficiary_current_city",
        "beneficiary_current_state",
        "beneficiary_current_zip",
        "beneficiary_current_address_line2",
    }:
        return (
            "Use the applicant's current U.S. physical residence information.",
            "USCIS distinguishes the place where the applicant actually lives from any separate mailing address. Keep addresses consistent across forms unless there is a clear reason they differ.",
        )
    if question_id.startswith("beneficiary_current_employer") or question_id.startswith("beneficiary_current_occupation"):
        return (
            "Describe the applicant's current or most recent work, school, unemployment, retirement, or support status.",
            "USCIS instructions say the employment and education section must cover the last five years. If the applicant is unemployed or retired, capture how they were financially supported.",
        )
    if question_id.startswith("beneficiary_"):
        return (
            _person_question_prompt(label, "green card applicant", ("applicant ",)),
            f"{applicant_note} {required_note} Match names, dates, documents, contact details, and status facts to the records used in the packet.",
        )
    if risk_code:
        return (
            f"Answer this truthfully for the green card applicant: {_lower_first(label)}",
            "USCIS I-485 guidance treats these eligibility, immigration-history, criminal-history, public-charge, and security questions as review-sensitive. If the truthful answer is yes, preserve dates, facts, and supporting records, then use Part 14 when more explanation is needed.",
        )
    if answer_type in {"boolean", "select", "single_check", "multi_select"}:
        return (
            "Choose the option that best matches the applicant's real situation.",
            f"{required_note} If none of the choices feel right, pause for review rather than forcing an answer; mismatched category or history answers can create filing problems.",
        )
    return (
        f"This asks for the I-485 item labeled: {label}.",
        f"{required_note} Match the answer to supporting records where possible, and use Part 14 if the applicant needs more room or a short explanation.",
    )


def _part_guidance_for_pdf_ref(pdf_ref: str) -> str | None:
    for part_number in range(14, 0, -1):
        part_key = f"Part {part_number}"
        if part_key in pdf_ref:
            return I485_PART_GUIDANCE[part_key]
    return None


def _with_part_guidance(deep_explanation: str, pdf_ref: str) -> str:
    part_guidance = _part_guidance_for_pdf_ref(pdf_ref)
    if not part_guidance or part_guidance in deep_explanation:
        return deep_explanation
    return f"{part_guidance} {deep_explanation}"


def build_i485_help(
    question_id: str,
    label: str,
    answer_type: str,
    *,
    required: bool,
    pdf_ref: str,
    risk_code: str | None,
) -> dict[str, Any]:
    plain_language, deep_explanation = I485_HELP_OVERRIDES.get(
        question_id,
        _default_i485_help(
            question_id,
            label,
            answer_type,
            required=required,
            pdf_ref=pdf_ref,
            risk_code=risk_code,
        ),
    )
    return {
        "plain_language": plain_language,
        "deep_explanation": _with_part_guidance(deep_explanation, pdf_ref),
        "teaching_source": {**I485_TOOLTIP_SOURCE, "pdf_ref": pdf_ref},
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
    entry_fields: list[dict[str, Any]] | None = None,
    form_entry_limit: int | None = None,
    overflow_pdf_ref: str | None = None,
) -> dict[str, Any]:
    explanation = build_i485_help(
        question_id,
        label,
        answer_type,
        required=required,
        pdf_ref=pdf_ref,
        risk_code=risk_code,
    )
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
        "entry_fields": entry_fields or [],
        "form_entry_limit": form_entry_limit,
        "overflow_pdf_ref": overflow_pdf_ref,
        **explanation,
    }


YES_NO = [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}]

US_STATE_OPTIONS = [
    {"value": "AL", "label": "Alabama"},
    {"value": "AK", "label": "Alaska"},
    {"value": "AZ", "label": "Arizona"},
    {"value": "AR", "label": "Arkansas"},
    {"value": "CA", "label": "California"},
    {"value": "CO", "label": "Colorado"},
    {"value": "CT", "label": "Connecticut"},
    {"value": "DE", "label": "Delaware"},
    {"value": "DC", "label": "District of Columbia"},
    {"value": "FL", "label": "Florida"},
    {"value": "GA", "label": "Georgia"},
    {"value": "HI", "label": "Hawaii"},
    {"value": "ID", "label": "Idaho"},
    {"value": "IL", "label": "Illinois"},
    {"value": "IN", "label": "Indiana"},
    {"value": "IA", "label": "Iowa"},
    {"value": "KS", "label": "Kansas"},
    {"value": "KY", "label": "Kentucky"},
    {"value": "LA", "label": "Louisiana"},
    {"value": "ME", "label": "Maine"},
    {"value": "MD", "label": "Maryland"},
    {"value": "MA", "label": "Massachusetts"},
    {"value": "MI", "label": "Michigan"},
    {"value": "MN", "label": "Minnesota"},
    {"value": "MS", "label": "Mississippi"},
    {"value": "MO", "label": "Missouri"},
    {"value": "MT", "label": "Montana"},
    {"value": "NE", "label": "Nebraska"},
    {"value": "NV", "label": "Nevada"},
    {"value": "NH", "label": "New Hampshire"},
    {"value": "NJ", "label": "New Jersey"},
    {"value": "NM", "label": "New Mexico"},
    {"value": "NY", "label": "New York"},
    {"value": "NC", "label": "North Carolina"},
    {"value": "ND", "label": "North Dakota"},
    {"value": "OH", "label": "Ohio"},
    {"value": "OK", "label": "Oklahoma"},
    {"value": "OR", "label": "Oregon"},
    {"value": "PA", "label": "Pennsylvania"},
    {"value": "RI", "label": "Rhode Island"},
    {"value": "SC", "label": "South Carolina"},
    {"value": "SD", "label": "South Dakota"},
    {"value": "TN", "label": "Tennessee"},
    {"value": "TX", "label": "Texas"},
    {"value": "UT", "label": "Utah"},
    {"value": "VT", "label": "Vermont"},
    {"value": "VA", "label": "Virginia"},
    {"value": "WA", "label": "Washington"},
    {"value": "WV", "label": "West Virginia"},
    {"value": "WI", "label": "Wisconsin"},
    {"value": "WY", "label": "Wyoming"},
    {"value": "AA", "label": "Armed Forces Americas"},
    {"value": "AE", "label": "Armed Forces Europe"},
    {"value": "AP", "label": "Armed Forces Pacific"},
    {"value": "AS", "label": "American Samoa"},
    {"value": "FM", "label": "Federated States of Micronesia"},
    {"value": "GU", "label": "Guam"},
    {"value": "MH", "label": "Marshall Islands"},
    {"value": "MP", "label": "Northern Mariana Islands"},
    {"value": "PR", "label": "Puerto Rico"},
    {"value": "PW", "label": "Palau"},
    {"value": "VI", "label": "U.S. Virgin Islands"},
]

ADDRESS_HISTORY_FIELDS: list[dict[str, Any]] = [
    {"key": "line1", "label": "Street number and name", "type": "text", "required": True},
    {"key": "line2", "label": "Apt, suite, or floor", "type": "text", "required": False},
    {"key": "city", "label": "City or town", "type": "text", "required": True},
    {"key": "state", "label": "State", "type": "select", "required": False, "options": US_STATE_OPTIONS},
    {"key": "province", "label": "Province", "type": "text", "required": False},
    {"key": "zip", "label": "ZIP code", "type": "text", "required": False},
    {"key": "postal_code", "label": "Postal code", "type": "text", "required": False},
    {"key": "country", "label": "Country", "type": "country", "required": True},
    {"key": "from", "label": "From", "type": "date", "required": True},
    {"key": "to", "label": "To", "type": "date", "required": False},
]

MAILING_ADDRESS_FIELDS: list[dict[str, Any]] = [
    {"key": "in_care_of", "label": "In care of name", "type": "text", "required": False},
    {"key": "line1", "label": "Street number and name", "type": "text", "required": True},
    {"key": "line2", "label": "Apt, suite, or floor", "type": "text", "required": False},
    {"key": "city", "label": "City or town", "type": "text", "required": True},
    {"key": "state", "label": "State", "type": "select", "required": True, "options": US_STATE_OPTIONS},
    {"key": "zip", "label": "ZIP code", "type": "text", "required": True},
]

SPOUSE_ADDRESS_FIELDS: list[dict[str, Any]] = [
    {"key": "line1", "label": "Street number and name", "type": "text", "required": True},
    {"key": "line2", "label": "Apt, suite, or floor", "type": "text", "required": False},
    {"key": "city", "label": "City or town", "type": "text", "required": True},
    {"key": "state", "label": "State", "type": "select", "required": False, "options": US_STATE_OPTIONS},
    {"key": "province", "label": "Province", "type": "text", "required": False},
    {"key": "zip", "label": "ZIP code", "type": "text", "required": False},
    {"key": "postal_code", "label": "Postal code", "type": "text", "required": False},
    {"key": "country", "label": "Country", "type": "country", "required": True},
]

EMPLOYMENT_HISTORY_FIELDS: list[dict[str, Any]] = [
    {
        "key": "activity_type",
        "label": "Activity type",
        "type": "select",
        "required": True,
        "options": [
            {"value": "employment", "label": "Employment"},
            {"value": "self_employment", "label": "Self-employment"},
            {"value": "unemployment", "label": "Unemployment"},
            {"value": "retirement", "label": "Retirement"},
            {"value": "school", "label": "School"},
        ],
    },
    {"key": "name", "label": "Employer, company, or school name", "type": "text", "required": False},
    {"key": "occupation", "label": "Occupation or status", "type": "text", "required": True},
    {"key": "line1", "label": "Street number and name", "type": "text", "required": False},
    {"key": "line2", "label": "Apt, suite, or floor", "type": "text", "required": False},
    {"key": "city", "label": "City or town", "type": "text", "required": False},
    {"key": "state", "label": "State", "type": "select", "required": False, "options": US_STATE_OPTIONS},
    {"key": "province", "label": "Province", "type": "text", "required": False},
    {"key": "zip", "label": "ZIP code", "type": "text", "required": False},
    {"key": "postal_code", "label": "Postal code", "type": "text", "required": False},
    {"key": "country", "label": "Country", "type": "country", "required": False},
    {"key": "from", "label": "From", "type": "date", "required": True},
    {"key": "to", "label": "To", "type": "date", "required": False},
    {"key": "financial_support", "label": "Financial support source if unemployed or retired", "type": "text", "required": False},
    {"key": "outside_us", "label": "Outside the United States", "type": "boolean", "required": False},
    {"key": "notes", "label": "Review notes", "type": "textarea", "required": False},
]

OTHER_NAME_FIELDS: list[dict[str, Any]] = [
    {"key": "family_name", "label": "Family name (last name)", "type": "text", "required": True},
    {"key": "given_name", "label": "Given name (first name)", "type": "text"},
    {"key": "middle_name", "label": "Middle name", "type": "text"},
]

OTHER_DOB_FIELDS: list[dict[str, Any]] = [
    {"key": "date_of_birth", "label": "Other date of birth", "type": "date", "required": True},
]

OTHER_A_NUMBER_FIELDS: list[dict[str, Any]] = [
    {"key": "a_number", "label": "Other A-Number", "type": "text", "required": True},
]

PRIOR_SPOUSE_FIELDS: list[dict[str, Any]] = [
    {"key": "family_name", "label": "Prior spouse family name (before marriage)", "type": "text", "required": True},
    {"key": "given_name", "label": "Prior spouse given name", "type": "text", "required": True},
    {"key": "middle_name", "label": "Prior spouse middle name", "type": "text"},
    {"key": "date_of_birth", "label": "Prior spouse date of birth", "type": "date", "required": True},
    {"key": "country_of_birth", "label": "Prior spouse country of birth", "type": "country", "required": True},
    {"key": "citizenship_country", "label": "Prior spouse country of citizenship or nationality", "type": "country", "required": True},
    {"key": "marriage_date", "label": "Date of marriage", "type": "date", "required": True},
    {"key": "marriage_city", "label": "Place of marriage: city or town", "type": "text", "required": True},
    {"key": "marriage_state", "label": "Place of marriage: state or province", "type": "text"},
    {"key": "marriage_country", "label": "Place of marriage: country", "type": "country", "required": True},
    {"key": "end_date", "label": "Date marriage legally ended", "type": "date", "required": True},
    {"key": "end_city", "label": "Place marriage legally ended: city or town", "type": "text", "required": True},
    {"key": "end_state", "label": "Place marriage legally ended: state or province", "type": "text"},
    {"key": "end_country", "label": "Place marriage legally ended: country", "type": "country", "required": True},
    {
        "key": "how_ended",
        "label": "How the marriage ended",
        "type": "select",
        "required": True,
        "options": [
            {"value": "divorced", "label": "Divorced"},
            {"value": "spouse_deceased", "label": "Spouse deceased"},
            {"value": "annulled", "label": "Annulled"},
            {"value": "other", "label": "Other"},
        ],
    },
    {"key": "how_ended_other", "label": "If other, explain how the marriage ended", "type": "text"},
]

CHILD_FIELDS: list[dict[str, Any]] = [
    {"key": "family_name", "label": "Child family name", "type": "text", "required": True},
    {"key": "given_name", "label": "Child given name", "type": "text", "required": True},
    {"key": "middle_name", "label": "Child middle name", "type": "text"},
    {"key": "a_number", "label": "Child A-Number, if any", "type": "text"},
    {"key": "date_of_birth", "label": "Child date of birth", "type": "date", "required": True},
    {"key": "country_of_birth", "label": "Child country of birth", "type": "country", "required": True},
    {"key": "relationship", "label": "Relationship to the applicant (for example, biological child, stepchild)", "type": "text", "required": True},
    {"key": "applying_separately", "label": "Is this child also applying now on a separate Form I-485?", "type": "boolean", "required": True},
]

ORGANIZATION_FIELDS: list[dict[str, Any]] = [
    {"key": "name", "label": "Name of organization", "type": "text", "required": True},
    {"key": "city", "label": "City or town", "type": "text", "required": True},
    {"key": "state", "label": "State or province", "type": "text"},
    {"key": "country", "label": "Country", "type": "country", "required": True},
    {"key": "nature", "label": "Nature of the organization, including its purposes and activities", "type": "text", "required": True},
    {"key": "involvement", "label": "Nature of involvement, including role or positions held", "type": "text", "required": True},
    {"key": "date_from", "label": "Membership or involvement from", "type": "date", "required": True},
    {"key": "date_to", "label": "Membership or involvement to", "type": "date"},
]

MEANS_TESTED_BENEFIT_FIELDS: list[dict[str, Any]] = [
    {"key": "benefit_name", "label": "Means-tested public benefit received", "type": "text", "required": True},
    {"key": "start_date", "label": "Start date", "type": "date", "required": True},
    {"key": "end_date", "label": "End date (blank if still receiving)", "type": "date"},
    {"key": "dollar_amount", "label": "Dollar amount (if applicable)", "type": "text"},
    {"key": "reason", "label": "Reason the benefit was received", "type": "textarea", "required": True},
]

FOREIGN_EMPLOYMENT_FIELDS: list[dict[str, Any]] = [
    {"key": "name", "label": "Employer, company, or school name", "type": "text", "required": True},
    {"key": "occupation", "label": "Occupation or status", "type": "text", "required": True},
    {"key": "line1", "label": "Street number and name", "type": "text", "required": False},
    {"key": "line2", "label": "Apt, suite, or floor", "type": "text", "required": False},
    {"key": "city", "label": "City or town", "type": "text", "required": False},
    {"key": "state", "label": "State", "type": "select", "required": False, "options": US_STATE_OPTIONS},
    {"key": "province", "label": "Province", "type": "text", "required": False},
    {"key": "zip", "label": "ZIP code", "type": "text", "required": False},
    {"key": "postal_code", "label": "Postal code", "type": "text", "required": False},
    {"key": "country", "label": "Country", "type": "country", "required": False},
    {"key": "from", "label": "From", "type": "date", "required": True},
    {"key": "to", "label": "To", "type": "date", "required": False},
    {"key": "financial_support", "label": "Financial support source if unemployed or retired", "type": "text", "required": False},
    {"key": "notes", "label": "Review notes", "type": "textarea", "required": False},
]

EYE_COLOR_OPTIONS = [
    {"value": "black", "label": "Black"},
    {"value": "blue", "label": "Blue"},
    {"value": "brown", "label": "Brown"},
    {"value": "gray", "label": "Gray"},
    {"value": "green", "label": "Green"},
    {"value": "hazel", "label": "Hazel"},
]

HAIR_COLOR_OPTIONS = [
    {"value": "bald", "label": "Bald or no hair"},
    {"value": "black", "label": "Black"},
    {"value": "blond", "label": "Blond"},
    {"value": "brown", "label": "Brown"},
    {"value": "gray", "label": "Gray"},
    {"value": "red", "label": "Red"},
    {"value": "sandy", "label": "Sandy"},
    {"value": "white", "label": "White"},
]

def part9_items(risk_code: str | None, rows: list[tuple[str, str, str]], conditional: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    # One question per form item: a combined answer would attest to items the applicant was never asked.
    return [
        q(
            question_id,
            label,
            "boolean",
            required=question_id not in conditional,
            pdf_ref=f"Part 9, Item {item}",
            ideal_answer=None if question_id in conditional else False,
            risk_when=True if risk_code else None,
            risk_code=risk_code,
        )
        for question_id, item, label in rows
    ]


I485_QUESTIONNAIRE: list[dict[str, Any]] = [
    {
        "id": "page_01_identity",
        "title": "Identity, A-Number, and Names",
        "pdf_part": "Part 1, Items 1-5",
        "local_pdf_pages": [1, 2],
        "questions": [
            q("beneficiary_a_number", "Alien Registration Number, if any", "text", required=False, pdf_ref="Part 1, A-Number", db_path="intake.beneficiary_a_number"),
            q("beneficiary_last_name", "Current legal family name", "text", pdf_ref="Part 1, Item 1", db_path="intake.beneficiary_last_name"),
            q("beneficiary_first_name", "Current legal given name", "text", pdf_ref="Part 1, Item 1", db_path="intake.beneficiary_first_name"),
            q("beneficiary_middle_name", "Current legal middle name", "text", required=False, pdf_ref="Part 1, Item 1", db_path="intake.beneficiary_middle_name"),
            q("beneficiary_other_names", "All other names ever used", "entry_list", required=False, pdf_ref="Part 1, Item 2", entry_fields=OTHER_NAME_FIELDS, form_entry_limit=2, overflow_pdf_ref="Part 14, Additional Information"),
            q("beneficiary_date_of_birth", "Date of birth", "date", pdf_ref="Part 1, Item 3", db_path="intake.beneficiary_date_of_birth"),
            q("beneficiary_used_other_dob", "Has the applicant ever used another date of birth?", "boolean", pdf_ref="Part 1, Item 3", ideal_answer=False, risk_when=True, risk_code="identity_inconsistencies"),
            q("beneficiary_other_dates_of_birth", "Other dates of birth used", "entry_list", required=False, pdf_ref="Part 1, Item 3", entry_fields=OTHER_DOB_FIELDS, form_entry_limit=2, overflow_pdf_ref="Part 14, Additional Information"),
            q("beneficiary_has_a_number", "Has USCIS ever assigned the applicant an A-Number?", "boolean", required=False, pdf_ref="Part 1, Item 4", db_path="intake.beneficiary_has_a_number"),
            q("beneficiary_has_other_a_numbers", "Has the applicant ever used or been assigned another A-Number?", "boolean", required=False, pdf_ref="Part 1, Item 5", ideal_answer=False, risk_when=True, risk_code="identity_inconsistencies"),
            q("beneficiary_other_a_numbers", "Other A-Numbers used or assigned", "entry_list", required=False, pdf_ref="Part 1, Item 5", entry_fields=OTHER_A_NUMBER_FIELDS, form_entry_limit=2, overflow_pdf_ref="Part 14, Additional Information"),
        ],
    },
    {
        "id": "page_02_birth_citizenship",
        "title": "Birth, Citizenship, and Travel Document",
        "pdf_part": "Part 1, Items 6-9",
        "local_pdf_pages": [2],
        "questions": [
            q("beneficiary_sex", "Sex marked on the form", "select", pdf_ref="Part 1, Item 6", db_path="intake.beneficiary_sex", options=[{"value": "female", "label": "Female"}, {"value": "male", "label": "Male"}]),
            q("beneficiary_city_of_birth", "City or town of birth", "text", pdf_ref="Part 1, Item 7", db_path="intake.beneficiary_city_of_birth"),
            q("beneficiary_country_of_birth", "Country of birth", "country", pdf_ref="Part 1, Item 7", db_path="intake.beneficiary_country_of_birth"),
            q("beneficiary_country_of_citizenship", "Country of citizenship or nationality", "country", pdf_ref="Part 1, Item 8", db_path="intake.beneficiary_country_of_citizenship"),
            q("beneficiary_uscis_online_account_number", "USCIS online account number, if any", "text", required=False, pdf_ref="Part 1, Item 8"),
            q("beneficiary_passport_number", "Passport or travel document number used at last arrival", "text", pdf_ref="Part 1, Item 9", db_path="intake.beneficiary_passport_number"),
            q("beneficiary_passport_expiration", "Passport or travel document expiration date", "date", pdf_ref="Part 1, Item 9", db_path="intake.beneficiary_passport_expiration"),
            q("beneficiary_passport_country", "Country that issued the passport or travel document", "country", pdf_ref="Part 1, Item 9", db_path="intake.beneficiary_passport_country"),
            q("beneficiary_visa_number", "Nonimmigrant visa number used during most recent arrival", "text", required=False, pdf_ref="Part 1, Item 9", db_path="intake.beneficiary_visa_number"),
            q("beneficiary_visa_issued_on", "Date the nonimmigrant visa was issued", "date", required=False, pdf_ref="Part 1, Item 9"),
        ],
    },
    {
        "id": "page_03_arrival_i94",
        "title": "Last Arrival and I-94",
        "pdf_part": "Part 1, Items 9-17",
        "local_pdf_pages": [2, 3],
        "questions": [
            q("beneficiary_last_arrival_city", "City or town of last arrival into the United States", "text", pdf_ref="Part 1, Item 9", db_path="intake.beneficiary_last_arrival_city"),
            q("beneficiary_last_arrival_state", "State of last arrival into the United States", "select", required=False, pdf_ref="Part 1, Item 9", db_path="intake.beneficiary_last_arrival_state", options=US_STATE_OPTIONS),
            q("beneficiary_last_arrival_date", "Date of last arrival", "date", pdf_ref="Part 1, Item 9", db_path="intake.beneficiary_last_arrival_date"),
            q("beneficiary_last_arrival_type", "How did the applicant last arrive?", "select", pdf_ref="Part 1, Item 10", db_path="intake.beneficiary_last_arrival_type", ideal_answer="admitted", risk_when="without_admission", risk_code="unlawful_entry", options=[{"value": "admitted", "label": "Inspected and admitted"}, {"value": "paroled", "label": "Inspected and paroled"}, {"value": "without_admission", "label": "Without admission or parole"}, {"value": "other", "label": "Other"}]),
            q("beneficiary_class_of_admission", "Class of Admission (COA) at last arrival, such as B-2", "select", pdf_ref="Part 1, Item 10", db_path="intake.beneficiary_class_of_admission", options=CLASS_OF_ADMISSION_OPTIONS),
            q("beneficiary_i94_number", "Most recent I-94 number", "text", pdf_ref="Part 1, Item 12", db_path="intake.beneficiary_i94_number"),
            q("beneficiary_last_arrival_first_us_presence", "Was the last arrival the applicant's first time physically present in the United States?", "boolean", pdf_ref="Part 1, Item 13", db_path="intake.beneficiary_last_arrival_first_us_presence"),
            q("beneficiary_status_expires_on", "Expiration date of authorized stay on I-94", "date", required=False, pdf_ref="Part 1, Item 12", db_path="intake.beneficiary_status_expires_on"),
            q("beneficiary_current_immigration_status", "Current immigration status", "text", pdf_ref="Part 1, Item 14", db_path="intake.beneficiary_current_immigration_status"),
            q("beneficiary_current_status_expires_on", "Expiration date of current immigration status", "date", required=False, pdf_ref="Part 1, Item 15", db_path="intake.beneficiary_current_status_expires_on"),
            q("beneficiary_alien_crewman_visa", "Has the applicant ever been issued an alien crewman visa?", "boolean", pdf_ref="Part 1, Item 16", ideal_answer=False, risk_when=True, risk_code="crewman_history"),
            q("beneficiary_joined_vessel_or_aircraft", "Did the applicant last arrive to join a vessel/aircraft as crew?", "boolean", pdf_ref="Part 1, Item 17", ideal_answer=False, risk_when=True, risk_code="crewman_history"),
        ],
    },
    {
        "id": "page_04_addresses_ssn",
        "title": "Addresses and Social Security",
        "pdf_part": "Part 1, Items 18-19",
        "local_pdf_pages": [3, 4],
        "questions": [
            q("beneficiary_current_address_line1", "Current U.S. physical street address", "text", pdf_ref="Part 1, Item 18", db_path="intake.beneficiary_current_address_line1"),
            q("beneficiary_current_address_line2", "Apartment, suite, or floor", "text", required=False, pdf_ref="Part 1, Item 18", db_path="intake.beneficiary_current_address_line2"),
            q("beneficiary_current_city", "Current U.S. physical city", "text", pdf_ref="Part 1, Item 18", db_path="intake.beneficiary_current_city"),
            q("beneficiary_current_state", "Current U.S. physical state", "select", pdf_ref="Part 1, Item 18", db_path="intake.beneficiary_current_state", options=US_STATE_OPTIONS),
            q("beneficiary_current_zip", "Current U.S. physical ZIP code", "text", pdf_ref="Part 1, Item 18", db_path="intake.beneficiary_current_zip"),
            q("beneficiary_address_since", "Date first resided at current address", "date", pdf_ref="Part 1, Item 18", db_path="intake.beneficiary_address_since"),
            q("beneficiary_mailing_same_as_physical", "Is this current physical address also the current mailing address?", "boolean", pdf_ref="Part 1, Item 18", db_path="intake.beneficiary_mailing_same_as_physical", ideal_answer=True),
            q(
                "beneficiary_mailing_address",
                "Current mailing address, if different from physical address",
                "address",
                required=False,
                pdf_ref="Part 1, Item 18",
                entry_fields=MAILING_ADDRESS_FIELDS,
                help_text="Complete this only when the current physical address is not also the mailing address.",
            ),
            q("beneficiary_current_address_five_years", "Has the applicant lived at the current address for at least 5 years?", "boolean", pdf_ref="Part 1, Item 18", ideal_answer=True),
            q(
                "beneficiary_prior_address_history",
                "Prior addresses for the last 5 years, if needed",
                "address_list",
                required=False,
                pdf_ref="Part 1, Item 18",
                db_path="intake.beneficiary_prior_address_history",
                entry_fields=ADDRESS_HISTORY_FIELDS,
                form_entry_limit=1,
                overflow_pdf_ref="Part 14, Additional Information",
                help_text="The I-485 has one prior-address slot after the current address section; extra prior addresses should be captured for Part 14 review.",
            ),
            q(
                "beneficiary_recent_foreign_address",
                "Most recent physical address outside the United States where the applicant lived for more than 1 year",
                "address",
                required=False,
                pdf_ref="Part 1, Item 18",
                db_path="intake.beneficiary_recent_foreign_address",
                entry_fields=ADDRESS_HISTORY_FIELDS,
                help_text="Use this only for the most recent qualifying foreign address. Dates should cover the period lived there.",
            ),
            q("beneficiary_has_ssn", "Has SSA ever officially issued the applicant a Social Security card?", "boolean", pdf_ref="Part 1, Item 19", db_path="intake.beneficiary_has_ssn"),
            q("beneficiary_ssn", "U.S. Social Security Number, if SSA has issued one", "text", required=False, pdf_ref="Part 1, Item 19", db_path="intake.beneficiary_ssn"),
            q("beneficiary_wants_ssn", "Does the applicant want SSA to issue a Social Security card?", "boolean", required=False, pdf_ref="Part 1, Item 19"),
            q("beneficiary_ssn_disclosure_consent", "If requesting an SSN, does the applicant consent to SSA disclosure?", "boolean", required=False, pdf_ref="Part 1, Item 19"),
        ],
    },
    {
        "id": "page_05_filing_category",
        "title": "Filing Category and Niche Gate",
        "pdf_part": "Part 2, Items 1-5",
        "local_pdf_pages": [5, 6, 7],
        "questions": [
            q("i485_in_removal_proceedings", "Is the applicant filing with EOIR while in removal, exclusion, rescission, or deportation proceedings?", "boolean", pdf_ref="Part 2, Item 1", ideal_answer=False, risk_when=True, risk_code="removal_history"),
            q("i485_underlying_petition_receipt", "Receipt number of underlying petition, if any", "text", required=False, pdf_ref="Part 2, Item 2", db_path="intake.i130_receipt_number"),
            q("i485_priority_date", "Priority date from underlying petition, if any", "date", required=False, pdf_ref="Part 2, Item 2"),
            q("i485_applicant_role", "Is the applicant principal or derivative?", "select", pdf_ref="Part 2", ideal_answer="principal", risk_when="derivative", risk_code="outside_niche_derivative", options=[{"value": "principal", "label": "Principal applicant"}, {"value": "derivative", "label": "Derivative applicant"}]),
            q("i485_family_category", "Family-based adjustment category", "select", pdf_ref="Part 2, Item 3.a", db_path="intake.i485_family_category", ideal_answer="spouse_us_citizen", risk_when="other", risk_code="outside_niche_category", options=[{"value": "spouse_us_citizen", "label": "Spouse of a U.S. citizen"}, {"value": "child_us_citizen", "label": "Unmarried child under 21 of a U.S. citizen"}, {"value": "parent_us_citizen", "label": "Parent of a U.S. citizen"}, {"value": "spouse_lpr", "label": "Spouse of a lawful permanent resident"}, {"value": "other", "label": "Other category"}]),
            q("i485_employment_based_category", "Is the applicant applying in an employment-based category?", "boolean", pdf_ref="Part 2, Item 3.b", ideal_answer=False, risk_when=True, risk_code="outside_niche_category"),
            q("i485_special_category", "Is the applicant applying in a special immigrant, asylum/refugee, crime victim, diversity, or other non-family category?", "boolean", pdf_ref="Part 2, Items 3.c-3.g", ideal_answer=False, risk_when=True, risk_code="outside_niche_category"),
            q("i485_245i", "Is the applicant applying based on INA section 245(i)?", "boolean", pdf_ref="Part 2, Item 4", ideal_answer=False, risk_when=True, risk_code="outside_niche_245i"),
            q("i485_cspa", "Is the applicant using Child Status Protection Act classification as a child?", "boolean", pdf_ref="Part 2, Item 5", ideal_answer=False, risk_when=True, risk_code="outside_niche_cspa"),
        ],
    },
    {
        "id": "page_06_i864_employment",
        "title": "Employment and Education History",
        "pdf_part": "Part 4, Items 7-8",
        "local_pdf_pages": [8, 9],
        "questions": [
            q("i485_i864_exemption", "Is the applicant requesting an exemption from Form I-864?", "select", pdf_ref="Part 3", ideal_answer="not_requesting_exemption", risk_when="other", risk_code="outside_niche_i864_exemption", options=[{"value": "not_requesting_exemption", "label": "No, Form I-864 is required"}, {"value": "40_quarters", "label": "40 qualifying quarters"}, {"value": "child_citizenship", "label": "Child citizenship exemption"}, {"value": "widow_i360", "label": "Widow or widower of a U.S. citizen (Form I-360)"}, {"value": "vawa_self_petitioner", "label": "VAWA self-petitioner"}, {"value": "not_required_by_statute", "label": "None apply, and Form I-864 is not required by statute"}]),
            q("prior_immigrant_visa_application", "Has the applicant ever applied for an immigrant visa at a U.S. Embassy or Consulate abroad?", "boolean", pdf_ref="Part 4, Item 1", ideal_answer=False, risk_when=True, risk_code="prior_immigration_history"),
            q("prior_permanent_residence_application", "Has the applicant previously applied for permanent residence while in the United States?", "boolean", pdf_ref="Part 4, Item 5", ideal_answer=False, risk_when=True, risk_code="prior_immigration_history"),
            q("prior_lpr_status_rescinded", "Has the applicant ever held lawful permanent resident status that was later rescinded?", "boolean", pdf_ref="Part 4, Item 6", ideal_answer=False, risk_when=True, risk_code="prior_immigration_history"),
            q(
                "beneficiary_employment_history",
                "Employment and educational history for the last 5 years",
                "employment_history_list",
                pdf_ref="Part 4, Item 7",
                db_path="intake.beneficiary_employment_history",
                entry_fields=EMPLOYMENT_HISTORY_FIELDS,
                form_entry_limit=1,
                overflow_pdf_ref="Part 14, Additional Information",
                help_text="USCIS asks for all employment, school, self-employment, unemployment, and retirement history for the last 5 years. Enter the current U.S. status first. For the happy path, use Activity type Unemployment, Occupation or status Unemployed, and Financial support source Husband.",
            ),
            q(
                "beneficiary_foreign_employer_or_school",
                "Most recent employer or school outside the United States",
                "employment_history_list",
                required=False,
                pdf_ref="Part 4, Item 8",
                db_path="intake.beneficiary_foreign_employer_or_school",
                entry_fields=FOREIGN_EMPLOYMENT_FIELDS,
                form_entry_limit=1,
                help_text="Use this for the most recent foreign employer or school if it is not already the current U.S. entry above. For this sample, this is where the Colombia university/school entry belongs.",
            ),
        ],
    },
    {
        "id": "page_07_parents",
        "title": "Parents",
        "pdf_part": "Part 5",
        "local_pdf_pages": [9, 10],
        "questions": [
            q("parent1_last_name", "Parent 1 family name", "text", pdf_ref="Part 5, Item 1"),
            q("parent1_first_name", "Parent 1 given name", "text", pdf_ref="Part 5, Item 1"),
            q("parent1_middle_name", "Parent 1 middle name", "text", required=False, pdf_ref="Part 5, Item 1"),
            q("parent1_name_at_birth", "Parent 1 name at birth, if different", "text", required=False, pdf_ref="Part 5, Item 2"),
            q("parent1_date_of_birth", "Parent 1 date of birth", "date", pdf_ref="Part 5, Item 3"),
            q("parent1_country_of_birth", "Parent 1 country of birth", "country", pdf_ref="Part 5, Item 4"),
            q("parent2_last_name", "Parent 2 family name", "text", pdf_ref="Part 5, Item 5"),
            q("parent2_first_name", "Parent 2 given name", "text", pdf_ref="Part 5, Item 5"),
            q("parent2_middle_name", "Parent 2 middle name", "text", required=False, pdf_ref="Part 5, Item 5"),
            q("parent2_name_at_birth", "Parent 2 name at birth, if different", "text", required=False, pdf_ref="Part 5, Item 6"),
            q("parent2_date_of_birth", "Parent 2 date of birth", "date", pdf_ref="Part 5, Item 7"),
            q("parent2_country_of_birth", "Parent 2 country of birth", "country", pdf_ref="Part 5, Item 8"),
        ],
    },
    {
        "id": "page_08_marriage_spouse",
        "title": "Marital History and U.S. Citizen Spouse",
        "pdf_part": "Part 6",
        "local_pdf_pages": [10, 11],
        "questions": [
            q("beneficiary_current_marital_status", "Current marital status", "select", pdf_ref="Part 6, Item 1", db_path="intake.beneficiary_current_marital_status", ideal_answer="married", risk_when="not_married", risk_code="outside_niche_marital_status", options=[{"value": "married", "label": "Married"}, {"value": "single", "label": "Single, never married"}, {"value": "divorced", "label": "Divorced"}, {"value": "widowed", "label": "Widowed"}, {"value": "separated", "label": "Legally separated"}, {"value": "annulled", "label": "Marriage annulled"}]),
            q("spouse_us_military", "Is the current spouse a member of the U.S. armed forces or Coast Guard?", "boolean", required=False, pdf_ref="Part 6, Item 2"),
            q("beneficiary_marriage_count", "How many times has the applicant been married?", "number", pdf_ref="Part 6, Item 3", db_path="intake.beneficiary_marriage_count", ideal_answer=1, risk_when="not_1", risk_code="outside_niche_prior_marriage"),
            q("petitioner_last_name", "Current spouse family name", "text", pdf_ref="Part 6, Item 4", db_path="intake.petitioner_last_name"),
            q("petitioner_first_name", "Current spouse given name", "text", pdf_ref="Part 6, Item 4", db_path="intake.petitioner_first_name"),
            q("petitioner_middle_name", "Current spouse middle name", "text", required=False, pdf_ref="Part 6, Item 4", db_path="intake.petitioner_middle_name"),
            q("petitioner_a_number", "Current spouse A-Number, if any", "text", required=False, pdf_ref="Part 6, Item 5"),
            q("petitioner_citizenship_status", "Current spouse immigration/citizenship status", "select", pdf_ref="Part 6 and niche gate", db_path="intake.petitioner_citizenship_status", ideal_answer="us_citizen", risk_when="not_us_citizen", risk_code="outside_niche_spouse_not_us_citizen", options=[{"value": "us_citizen", "label": "U.S. citizen"}, {"value": "lpr", "label": "Lawful permanent resident"}, {"value": "other", "label": "Other or unsure"}]),
            q("petitioner_date_of_birth", "Current spouse date of birth", "date", pdf_ref="Part 6, Item 6", db_path="intake.petitioner_date_of_birth"),
            q("petitioner_country_of_birth", "Current spouse country of birth", "country", pdf_ref="Part 6, Item 7", db_path="intake.petitioner_country_of_birth"),
            q(
                "petitioner_current_address",
                "Current spouse physical address",
                "address",
                pdf_ref="Part 6, Item 8",
                db_path="intake.petitioner_current_address",
                entry_fields=SPOUSE_ADDRESS_FIELDS,
            ),
            q("marriage_place_city", "Place of current marriage: city", "text", pdf_ref="Part 6, Item 9", db_path="intake.marriage_place_city"),
            q("marriage_place_state", "Place of current marriage: state or province", "text", pdf_ref="Part 6, Item 9", db_path="intake.marriage_place_state"),
            q("marriage_place_country", "Place of current marriage: country", "country", pdf_ref="Part 6, Item 9", db_path="intake.marriage_place_country"),
            q("marriage_date", "Date of current marriage", "date", pdf_ref="Part 6, Item 9", db_path="intake.marriage_date"),
            q("current_spouse_applying_with_beneficiary", "Is the current spouse applying with the applicant?", "boolean", required=False, pdf_ref="Part 6, Item 10", ideal_answer=False),
            q("beneficiary_prior_marriages", "Prior marriages", "entry_list", required=False, pdf_ref="Part 6, Items 11-18", entry_fields=PRIOR_SPOUSE_FIELDS, form_entry_limit=1, overflow_pdf_ref="Part 14, Additional Information", risk_when="present", risk_code="outside_niche_prior_marriage"),
        ],
    },
    {
        "id": "page_09_children_biographic",
        "title": "Children and Biographic Information",
        "pdf_part": "Parts 7-8",
        "local_pdf_pages": [12, 13],
        "questions": [
            q("children_count", "Total number of living children anywhere in the world", "number", pdf_ref="Part 7, Item 1", db_path="intake.children_count", ideal_answer=0, risk_when="greater_than_0", risk_code="outside_niche_children"),
            q("children_details", "Children", "entry_list", required=False, pdf_ref="Part 7, Items 2-3", entry_fields=CHILD_FIELDS, form_entry_limit=2, overflow_pdf_ref="Part 14, Additional Information"),
            q("beneficiary_ethnicity", "Ethnicity", "select", pdf_ref="Part 8, Item 1", db_path="intake.beneficiary_ethnicity", options=[{"value": "hispanic_or_latino", "label": "Hispanic or Latino"}, {"value": "not_hispanic_or_latino", "label": "Not Hispanic or Latino"}]),
            q("beneficiary_race", "Race selections", "multi_select", pdf_ref="Part 8, Item 2", db_path="intake.beneficiary_race", options=[{"value": "asian", "label": "Asian"}, {"value": "white", "label": "White"}, {"value": "black", "label": "Black or African American"}, {"value": "american_indian", "label": "American Indian or Alaska Native"}, {"value": "pacific_islander", "label": "Native Hawaiian or Other Pacific Islander"}]),
            q("beneficiary_height_feet", "Height: feet", "number", pdf_ref="Part 8, Item 3", db_path="intake.beneficiary_height_feet"),
            q("beneficiary_height_inches", "Height: inches", "number", pdf_ref="Part 8, Item 3", db_path="intake.beneficiary_height_inches"),
            q("beneficiary_weight_pounds", "Weight in pounds", "number", pdf_ref="Part 8, Item 4", db_path="intake.beneficiary_weight_pounds"),
            q("beneficiary_eye_color", "Eye color", "single_check", pdf_ref="Part 8, Item 5", db_path="intake.beneficiary_eye_color", options=EYE_COLOR_OPTIONS),
            q("beneficiary_hair_color", "Hair color", "single_check", pdf_ref="Part 8, Item 6", db_path="intake.beneficiary_hair_color", options=HAIR_COLOR_OPTIONS),
        ],
    },
    {
        "id": "page_10_organizations_immigration",
        "title": "Organizations and Immigration History",
        "pdf_part": "Part 9, Items 1-21",
        "local_pdf_pages": [13, 14],
        "questions": [
            q("organizations_membership", "Has the applicant ever been associated with any organization, association, party, club, society, or similar group?", "boolean", pdf_ref="Part 9, Item 1", ideal_answer=False, risk_when=True, risk_code="organization_history"),
            q("organizations_details", "Organizations", "entry_list", required=False, pdf_ref="Part 9, Items 2-9", entry_fields=ORGANIZATION_FIELDS, form_entry_limit=2, overflow_pdf_ref="Part 14, Additional Information"),
            q("visa_denied", "Has the applicant ever been denied a visa to the United States?", "boolean", pdf_ref="Part 9, Item 11", ideal_answer=False, risk_when=True, risk_code="prior_immigration_denials", db_path="intake.prior_immigration_denials"),
            q("admission_denied", "Has the applicant ever been denied admission to the United States?", "boolean", pdf_ref="Part 9, Item 10", ideal_answer=False, risk_when=True, risk_code="prior_immigration_denials"),
            q("worked_without_authorization", "Has the applicant ever worked in the United States without authorization?", "boolean", pdf_ref="Part 9, Item 12", ideal_answer=False, risk_when=True, risk_code="unauthorized_work"),
            q("violated_nonimmigrant_status", "Has the applicant ever violated the terms of nonimmigrant status?", "boolean", pdf_ref="Part 9, Item 13", ideal_answer=False, risk_when=True, risk_code="status_violation"),
            q("removal_proceedings_history", "Has the applicant ever been in removal, exclusion, rescission, or deportation proceedings?", "boolean", pdf_ref="Part 9, Item 14", ideal_answer=False, risk_when=True, risk_code="removal_history", db_path="intake.removal_history"),
            q("final_removal_order", "Has the applicant ever been issued a final order of exclusion, deportation, or removal?", "boolean", pdf_ref="Part 9, Item 15", ideal_answer=False, risk_when=True, risk_code="removal_history"),
            q("reinstated_removal_order", "Has a prior final removal order ever been reinstated?", "boolean", pdf_ref="Part 9, Item 16", ideal_answer=False, risk_when=True, risk_code="removal_history"),
            q("voluntary_departure_failed", "Was voluntary departure granted but not completed on time?", "boolean", pdf_ref="Part 9, Item 17", ideal_answer=False, risk_when=True, risk_code="removal_history"),
            q("relief_from_removal", "Has the applicant ever applied for relief or protection from removal?", "boolean", pdf_ref="Part 9, Item 18", ideal_answer=False, risk_when=True, risk_code="removal_history"),
            q("j_exchange_two_year_rule", "Has the applicant ever been subject to the J exchange visitor two-year foreign residence requirement?", "boolean", pdf_ref="Part 9, Item 19", ideal_answer=False, risk_when=True, risk_code="j_waiver_needed"),
            q("j_foreign_residence_complied", "If yes to Item 19, has the applicant complied with the foreign residence requirement?", "boolean", required=False, pdf_ref="Part 9, Item 20"),
            q("j_waiver_granted", "If yes to Item 19 and no to Item 20, has the applicant been granted a waiver, or has the Department of State issued a favorable waiver recommendation letter?", "boolean", required=False, pdf_ref="Part 9, Item 21"),
        ],
    },
    {
        "id": "page_11_criminal_acts",
        "title": "Criminal Acts and Controlled Substances",
        "pdf_part": "Part 9, Items 22-41",
        "local_pdf_pages": [14, 15, 16],
        "questions": [
            q("ever_arrested_cited_charged_detained", "Has the applicant ever been arrested, cited, charged, detained, or placed in diversion by law enforcement anywhere?", "boolean", pdf_ref="Part 9, Item 22", ideal_answer=False, risk_when=True, risk_code="criminal_history", db_path="intake.criminal_history"),
            q("ever_committed_crime", "Has the applicant ever committed a crime of any kind, even without arrest or conviction?", "boolean", pdf_ref="Part 9, Item 23", ideal_answer=False, risk_when=True, risk_code="criminal_history"),
            q("ever_pled_or_convicted", "Has the applicant ever pled guilty to or been convicted of a crime or offense?", "boolean", pdf_ref="Part 9, Item 24", ideal_answer=False, risk_when=True, risk_code="criminal_history"),
            q("ever_punished_by_judge", "Has a judge ever ordered punishment or imposed conditions restraining liberty?", "boolean", pdf_ref="Part 9, Item 25", ideal_answer=False, risk_when=True, risk_code="criminal_history"),
            q("controlled_substance_violation", "Has the applicant ever violated or attempted to violate a controlled substance law?", "boolean", pdf_ref="Part 9, Item 26", ideal_answer=False, risk_when=True, risk_code="controlled_substances"),
            *part9_items(
                "controlled_substances",
                [
                    ("controlled_substance_trafficked", "27", "Has the applicant ever trafficked in or benefited from, or knowingly aided, abetted, assisted, conspired or colluded in the illegal trafficking of any controlled substances, such as chemicals, illegal drugs, or narcotics?"),
                    ("controlled_substance_family_benefit", "28", "Is the applicant the spouse, son, or daughter of a person who illicitly trafficked or aided in the illicit trafficking of a controlled substance, and did the applicant obtain, within the last five years, any financial or other benefit from that activity?"),
                    ("controlled_substance_family_benefit_knowledge", "29", "If yes to Item 28, did the applicant know or should the applicant have reasonably known that the benefit resulted from this activity of a spouse or parent?")
                ], conditional=("controlled_substance_family_benefit_knowledge",)
            ),
            *part9_items(
                "commercialized_vice",
                [
                    ("prostitution_engaged", "30", "Has the applicant ever engaged in prostitution, or is the applicant coming to the United States to engage in prostitution?"),
                    ("prostitution_procured", "31", "Has the applicant ever directly or indirectly procured or attempted to procure, or imported prostitutes or persons for the purpose of prostitution?"),
                    ("prostitution_proceeds", "32", "Has the applicant ever received any proceeds or money from prostitution?"),
                    ("commercialized_vice_intent", "33", "Does the applicant intend to engage in illegal gambling or any other form of commercialized vice, such as prostitution, bootlegging, or the sale of child pornography, while in the United States?"),
                    ("exercised_criminal_immunity", "34", "Has the applicant ever exercised immunity (diplomatic or otherwise) to avoid being prosecuted for a criminal offense in the United States?")
                ],
            ),
            q("served_as_foreign_government_official", "Has the applicant ever served as a foreign government official?", "boolean", pdf_ref="Part 9, Item 35.a", ideal_answer=False),
            q("religious_freedom_violations", "If yes to Item 35.a, has the applicant ever been responsible for, enforced, or directly carried out violations of religious freedoms?", "boolean", required=False, pdf_ref="Part 9, Item 35.b", risk_when=True, risk_code="human_rights"),
            *part9_items(
                "trafficking",
                [
                    ("sex_trafficking", "36", "Has the applicant ever induced by force, fraud, or coercion (or otherwise been involved in) the trafficking of another person for commercial sex acts?"),
                    ("labor_trafficking", "37", "Has the applicant ever trafficked a person into involuntary servitude, peonage, debt bondage, or slavery, including recruiting, harboring, transporting, providing, or obtaining a person for labor or services through force, fraud, or coercion?"),
                    ("aided_trafficking", "38", "Has the applicant ever knowingly aided, abetted, assisted, conspired, or colluded with others in trafficking in persons for commercial sex acts or involuntary servitude, peonage, debt bondage, or slavery?"),
                    ("trafficking_family_benefit", "39", "Is the applicant the spouse, son, or daughter of a person who engaged in trafficking in persons, and has the applicant received, within the last five years, any financial or other benefit from that activity?"),
                    ("trafficking_family_benefit_knowledge", "40", "If yes to Item 39, did the applicant know or reasonably should the applicant have known that this benefit resulted from this activity of a spouse or parent?")
                ], conditional=("trafficking_family_benefit_knowledge",)
            ),
            q("money_laundering", "Has the applicant ever engaged in or aided money laundering?", "boolean", pdf_ref="Part 9, Item 41", ideal_answer=False, risk_when=True, risk_code="money_laundering"),
            q("criminal_explanations", "Explanations and dispositions for any yes answer in this section", "textarea", required=False, pdf_ref="Part 14"),
        ],
    },
    {
        "id": "page_12_security_human_rights",
        "title": "Security, Weapons, Military, and Human Rights",
        "pdf_part": "Part 9, Items 42-56",
        "local_pdf_pages": [16, 17, 18],
        "questions": [
            *part9_items(
                "security_related",
                [
                    ("intends_espionage_sabotage", "42.a", "Does the applicant intend to engage in any activity that violates or evades any law relating to espionage (including spying) or sabotage in the United States?"),
                    ("intends_export_violation", "42.b", "Does the applicant intend to engage in any activity in the United States that violates or evades any law prohibiting the export from the United States of goods, technology, or sensitive information?"),
                    ("intends_overthrow", "42.c", "Does the applicant intend to engage in any activity whose purpose includes opposing, controlling, or overthrowing the U.S. Government by force, violence, or other unlawful means while in the United States?"),
                    ("intends_other_unlawful_activity", "42.d", "Does the applicant intend to engage in any other unlawful activity?")
                ],
            ),
            *part9_items(
                "security_related",
                [
                    ("weapons_training", "43.a", "Has the applicant ever received any weapons training, paramilitary training, or other military-type training?"),
                    ("kidnapping_or_hijacking", "43.b", "Has the applicant ever committed kidnapping, assassination, or hijacking or sabotage of a conveyance (including an aircraft, vessel, vehicle, or train)?"),
                    ("used_weapon_or_explosive", "43.c", "Has the applicant ever used a weapon or explosive or any dangerous device with the intent to endanger the safety of another person or people or cause damage to property?"),
                    ("threatened_or_planned_violence", "43.d", "Has the applicant ever threatened, attempted, conspired, prepared, or planned to do any of the things described in Items 43.b - 43.c?"),
                    ("incited_violence", "43.e", "Has the applicant ever incited, under circumstances indicating an intention to cause death or serious bodily harm, any of the activities described in Items 43.b - 43.c?"),
                    ("member_of_violent_group", "43.f", "Has the applicant ever participated in, or been a member of, a group or organization that did any of the activities described in Items 43.b - 43.e?"),
                    ("recruited_for_violent_group", "43.g", "Has the applicant ever recruited members or asked for money or things of value for a group or organization that did any of the activities described in Items 43.b - 43.e?"),
                    ("supported_violent_activity", "43.h", "Has the applicant ever provided money, a thing of value, services or labor, or any other assistance or support for any of the activities described in Items 43.b - 43.e?"),
                    ("supported_violent_group", "43.i", "Has the applicant ever provided money, a thing of value, services or labor, or any other assistance or support for an individual, group, or organization who did any of the activities described in Items 43.b - 43.e?"),
                    ("intends_violent_activity", "44", "Does the applicant intend to engage in any of the activities listed in any part of Items 43.b - 43.e?")
                ],
            ),
            q("endanger_us_security", "Does the applicant intend activity that could endanger the welfare, safety, or security of the United States?", "boolean", pdf_ref="Part 9, Item 45", ideal_answer=False, risk_when=True, risk_code="security_related"),
            q("family_security_activity", "Is the applicant the spouse or child of someone who engaged in listed security activities?", "boolean", pdf_ref="Part 9, Item 46", ideal_answer=False, risk_when=True, risk_code="security_related"),
            q("weapons_sales_or_transport", "Has the applicant sold, provided, transported, or assisted with weapons intended for use against another person?", "boolean", pdf_ref="Part 9, Item 47", ideal_answer=False, risk_when=True, risk_code="security_related"),
            q("detention_or_prison_service", "Has the applicant worked or served where people were detained, or participated in detaining people?", "boolean", pdf_ref="Part 9, Item 48", ideal_answer=False, risk_when=True, risk_code="human_rights"),
            *part9_items(
                "military_or_armed_group",
                [
                    ("weapon_using_group", "49", "Has the applicant ever been a member of, assisted, or participated in any group, unit, or organization of any kind in which the applicant or other persons used any type of weapon against any person or threatened to do so?"),
                    ("military_or_police_service", "50", "Has the applicant ever served in, been a member of, assisted, or participated in any military or police unit?"),
                    ("armed_group_service", "51", "Has the applicant ever served in, been a member of, assisted, or participated in any armed group (a group that carries weapons), for example a paramilitary unit, self-defense unit, vigilante unit, rebel group, or guerrilla group?")
                ],
            ),
            q("communist_totalitarian_party", "Has the applicant ever been affiliated with the Communist Party or any totalitarian party?", "boolean", pdf_ref="Part 9, Item 52", ideal_answer=False, risk_when=True, risk_code="party_affiliation"),
            *part9_items(
                "human_rights",
                [
                    ("participated_in_torture", "53.a", "Has the applicant ever ordered, incited, called for, committed, assisted, helped with, or otherwise participated in torture?"),
                    ("participated_in_genocide", "53.b", "Has the applicant ever ordered, incited, called for, committed, assisted, helped with, or otherwise participated in genocide?"),
                    ("participated_in_killing", "53.c", "Has the applicant ever ordered, incited, called for, committed, assisted, helped with, or otherwise participated in killing, or trying to kill, any person?"),
                    ("participated_in_severe_injury", "53.d", "Has the applicant ever ordered, incited, called for, committed, assisted, helped with, or otherwise participated in intentionally and severely injuring, or trying to injure, any person?"),
                    ("child_soldier_recruitment", "54", "Has the applicant ever recruited, enlisted, conscripted, or used any person under 15 years of age to take part in hostilities or to serve in or help an armed force or group, or attempted or worked with others to do so?"),
                    ("child_soldier_use", "55", "Has the applicant ever used any person under 15 years of age to take part in hostilities, for instance participating in combat or providing services related to combat (such as sabotage or serving as a courier) or providing support services (such as transporting supplies), or attempted or worked with others to do so?")
                ],
            ),
            q("public_charge_exempt_category", "Is the applicant selecting a public charge exempt category?", "select", required=False, pdf_ref="Part 9, Item 56", ideal_answer="not_exempt_complete_questions", options=[{"value": "not_exempt_complete_questions", "label": "No exempt category; complete public charge questions"}, {"value": "asylee_refugee_or_other", "label": "Asylee, refugee, VAWA, U/T, SIJ, Cuban Adjustment, or other exemption"}, {"value": "unsure", "label": "Unsure"}], risk_when="asylee_refugee_or_other", risk_code="outside_niche_category"),
        ],
    },
    {
        "id": "page_13_public_charge",
        "title": "Public Charge Household Snapshot",
        "pdf_part": "Part 9, Items 57-64",
        "local_pdf_pages": [19, 20],
        "questions": [
            q("household_size", "Household size counted in Items 58-60", "number", pdf_ref="Part 9, Item 57", db_path="intake.household_size"),
            q("public_charge_family_status", "Family status in your own words", "textarea", required=False, pdf_ref="Part 9, Item 57"),
            q("annual_household_income_band", "Annual household income band", "select", pdf_ref="Part 9, Item 58", db_path="intake.annual_household_income_band", options=[{"value": "0_27000", "label": "$0-$27,000"}, {"value": "27001_52000", "label": "$27,001-$52,000"}, {"value": "52001_85000", "label": "$52,001-$85,000"}, {"value": "85001_141000", "label": "$85,001-$141,000"}, {"value": "over_141000", "label": "Over $141,000"}]),
            q("household_assets_band", "Total household assets band", "select", pdf_ref="Part 9, Item 59", options=[{"value": "0_18400", "label": "$0-$18,400"}, {"value": "18401_136000", "label": "$18,401-$136,000"}, {"value": "136001_321400", "label": "$136,001-$321,400"}, {"value": "321401_707100", "label": "$321,401-$707,100"}, {"value": "over_707100", "label": "Over $707,100"}]),
            q("household_liabilities_band", "Total household liabilities band", "select", pdf_ref="Part 9, Item 60", options=[{"value": "0", "label": "$0"}, {"value": "1_10100", "label": "$1-$10,100"}, {"value": "10101_57700", "label": "$10,101-$57,700"}, {"value": "57701_186800", "label": "$57,701-$186,800"}, {"value": "over_186800", "label": "Over $186,800"}]),
            q("highest_education", "Highest degree or grade completed", "select", pdf_ref="Part 9, Item 61", options=[{"value": "less_than_high_school", "label": "Less than high school"}, {"value": "high_school", "label": "High school/GED"}, {"value": "some_college", "label": "1+ years college, no degree"}, {"value": "associate", "label": "Associate's degree"}, {"value": "bachelor", "label": "Bachelor's degree"}, {"value": "master", "label": "Master's degree"}, {"value": "professional", "label": "Professional degree"}, {"value": "doctorate", "label": "Doctorate"}]),
            q("highest_grade_completed", "If less than a high school diploma, the highest grade completed", "text", required=False, pdf_ref="Part 9, Item 61"),
            q("certifications_licenses_skills", "Skills, including certifications, licenses, and educational certificates", "textarea", pdf_ref="Part 9, Item 62"),
            q("received_means_tested_public_benefit", "Has the applicant ever received any means-tested public benefit?", "boolean", pdf_ref="Part 9, Item 63", ideal_answer=False, risk_when=True, risk_code="public_charge_benefits"),
            q(
                "means_tested_benefit_history",
                "Means-tested public benefits received",
                "benefit_history_list",
                required=False,
                pdf_ref="Part 9, Item 64",
                entry_fields=MEANS_TESTED_BENEFIT_FIELDS,
                form_entry_limit=4,
                overflow_pdf_ref="Part 14, Additional Information",
            ),
        ],
    },
    {
        "id": "page_14_violations_signature",
        "title": "Illegal Entries, Miscellaneous Conduct, and Signature Workflow",
        "pdf_part": "Part 9, Items 65-84; Parts 10-14",
        "local_pdf_pages": [20, 21, 22, 23, 24],
        "questions": [
            q("failed_to_attend_removal", "Has the applicant ever failed or refused to attend a removal proceeding filed on or after April 1, 1997?", "boolean", pdf_ref="Part 9, Item 65", ideal_answer=False, risk_when=True, risk_code="removal_history"),
            q("fraudulent_documents", "Has the applicant ever submitted altered, fraudulent, or counterfeit documents to obtain an immigration benefit?", "boolean", pdf_ref="Part 9, Item 66", ideal_answer=False, risk_when=True, risk_code="fraud_or_misrepresentation"),
            q("lied_for_immigration_benefit", "Has the applicant ever lied, concealed, or misrepresented information for a U.S. immigration benefit?", "boolean", pdf_ref="Part 9, Item 67", ideal_answer=False, risk_when=True, risk_code="fraud_or_misrepresentation"),
            q("false_us_citizen_claim", "Has the applicant ever falsely claimed to be a U.S. citizen?", "boolean", pdf_ref="Part 9, Item 68", ideal_answer=False, risk_when=True, risk_code="false_us_citizenship"),
            q("stowaway", "Has the applicant ever been a stowaway?", "boolean", pdf_ref="Part 9, Item 69", ideal_answer=False, risk_when=True, risk_code="immigration_violation"),
            q("document_fraud_civil_penalty", "Is the applicant under a final civil penalty order for fraudulent documents?", "boolean", pdf_ref="Part 9, Item 71", ideal_answer=False, risk_when=True, risk_code="fraud_or_misrepresentation"),
            q("alien_smuggling", "Has the applicant ever knowingly encouraged or helped another person enter the United States illegally?", "boolean", pdf_ref="Part 9, Item 70", ideal_answer=False, risk_when=True, risk_code="alien_smuggling"),
            q("entered_without_inspection", "Has the applicant ever entered the United States without inspection and admission or parole?", "boolean", pdf_ref="Part 9, Item 73", db_path="intake.unlawful_entry", ideal_answer=False, risk_when=True, risk_code="unlawful_entry"),
            q("deported_removed_or_departed_after_order", "Has the applicant ever been excluded, deported, removed, or departed after such an order?", "boolean", pdf_ref="Part 9, Item 72", ideal_answer=False, risk_when=True, risk_code="removal_history"),
            q("unlawful_presence_after_1997", "Since April 1, 1997, has the applicant been unlawfully present in the United States?", "boolean", pdf_ref="Part 9, Item 74", ideal_answer=False, risk_when=True, risk_code="unlawful_presence"),
            q("unlawful_presence_due_to_trafficking", "If yes to Item 74, was a severe form of trafficking in persons at least one central reason for the unlawful presence?", "boolean", required=False, pdf_ref="Part 9, Item 75"),
            *part9_items(
                "illegal_reentry",
                [
                    ("reentry_after_unlawful_presence", "76.a", "Since April 1, 1997, has the applicant ever reentered or attempted to reenter the United States without being inspected and admitted or paroled after having been unlawfully present for more than one year in the aggregate on or after April 1, 1997?"),
                    ("reentry_after_removal", "76.b", "Since April 1, 1997, has the applicant ever reentered or attempted to reenter the United States without being inspected and admitted or paroled after having been deported, excluded, or removed from the United States?")
                ],
            ),
            *part9_items(
                "miscellaneous_inadmissibility",
                [
                    ("intends_polygamy", "77", "Does the applicant plan to practice polygamy in the United States?"),
                    ("accompanying_helpless_person", "78", "Is the applicant accompanying a person who is inadmissible and who has been certified by a medical officer as helpless from sickness, mental or physical disability, or infancy, and who requires the applicant's protection or guardianship, as described in INA section 232(c)?"),
                    ("withheld_child_custody", "79", "Has the applicant ever assisted in detaining, retaining, or withholding custody of a U.S. citizen child outside the United States from a person who has been granted custody of the child?"),
                    ("unlawful_voting", "80", "Has the applicant ever voted in violation of any Federal, state, or local constitutional provision, statute, ordinance, or regulation in the United States?"),
                    ("renounced_citizenship_for_tax", "81", "Has the applicant ever renounced U.S. citizenship to avoid being taxed by the United States?"),
                    ("armed_forces_exemption", "82.a", "Has the applicant ever applied for exemption or discharge from training or service in the U.S. armed forces or in the U.S. National Security Training Corps on the ground of being an alien?"),
                    ("armed_forces_discharge", "82.b", "Has the applicant ever been relieved or discharged from such training or service on the ground of being an alien?"),
                    ("desertion_conviction", "82.c", "Has the applicant ever been convicted of desertion from the U.S. armed forces?"),
                    ("evaded_wartime_service", "83", "Has the applicant ever left or remained outside the United States to avoid or evade training or service in the U.S. armed forces in time of war or a period declared by the President to be a national emergency?")
                ],
            ),
            q("status_before_evading_service", "If yes to Item 83, the nationality or immigration status immediately before leaving (for example, U.S. citizen or national, lawful permanent resident, nonimmigrant, parolee)", "text", required=False, pdf_ref="Part 9, Item 84"),
            q("beneficiary_phone", "Applicant daytime or mobile phone number", "text", pdf_ref="Part 10, Items 1-2", db_path="intake.beneficiary_phone"),
            q("beneficiary_mobile_phone", "Applicant mobile phone number, if any", "text", required=False, pdf_ref="Part 10, Item 2"),
            q("beneficiary_email", "Applicant email address", "text", pdf_ref="Part 10, Item 3", db_path="intake.beneficiary_email"),
            q("applicant_reviewed_certification", "Applicant has reviewed the certification and understands signature must be original before filing", "boolean", pdf_ref="Part 10, Item 4", ideal_answer=True, risk_when=False, risk_code="signature_not_confirmed"),
            q("interpreter_used", "Was an interpreter used?", "boolean", required=False, pdf_ref="Part 11"),
            q("preparer_used", "Was a preparer used other than the applicant?", "boolean", required=False, pdf_ref="Part 12"),
            q("additional_information_needed", "Does any answer require Part 14 additional information?", "boolean", required=False, pdf_ref="Part 14", ideal_answer=False, risk_when=True, risk_code="additional_information_needed"),
        ],
    },
]


def all_i485_questions() -> list[dict[str, Any]]:
    return [question for page in I485_QUESTIONNAIRE for question in page["questions"]]
