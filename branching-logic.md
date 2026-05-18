# I-485 Ingestion App: Branching Logic + TurboTax-Style UI Product Spec

> **Scope:** Form I-485, Application to Register Permanent Residence or Adjust Status, with TurboTax-style guided intake, eligibility routing, document checklist generation, PDF-fill preparation, and human review flags.  
> **Primary MVP path:** First-time marriage-based adjustment of status for a foreign spouse of a U.S. citizen who is physically present in the United States after lawful admission or parole.  
> **Important:** This is a product/engineering spec, not legal advice. Any app should clearly instruct users to consult a qualified immigration attorney for complex facts, inadmissibility issues, removal history, fraud/misrepresentation concerns, criminal history, or status violations.

---

## 1. Product Goals

The app should behave like TurboTax:

1. Ask one simple question at a time.
2. Hide irrelevant sections automatically.
3. Explain confusing immigration terms in plain English.
4. Generate a dynamic checklist of evidence.
5. Flag high-risk answers before the user files.
6. Produce a clean review screen before PDF generation.
7. Make the user feel guided, not abandoned with a raw government form.

---

## 2. Top-Level Flow

```text
Start
  -> User Type / Case Type
  -> Eligibility Pre-Screen
  -> Current Immigration Situation
  -> Personal Information
  -> Address History
  -> Immigration History
  -> Family / Marriage Information
  -> Public Charge Questions
  -> Inadmissibility / Security Questions
  -> Employment / Education / Financial Snapshot
  -> Required Evidence Checklist
  -> Forms Bundle Recommendation
  -> Review + Risk Flags
  -> Generate Packet / Export
```

---

## 3. Main Case-Type Branching

### 3.1 Ask: “What is the basis for your green card application?”

Options:

- Spouse of U.S. citizen
- Parent of U.S. citizen age 21+
- Unmarried child under 21 of U.S. citizen
- Other family-based category
- Employment-based category
- Asylee/refugee adjustment
- Special immigrant category
- Diversity visa
- Registry
- Cuban Adjustment Act
- VAWA
- T visa / U visa
- Other / unsure

### Branch Logic

```yaml
if basis == "spouse_of_us_citizen":
  route: marriage_based_us_citizen_flow
  likely_forms:
    - I-485
    - I-130 if not already filed
    - I-130A
    - I-864
    - I-765 optional
    - I-131 optional
    - I-693 usually required with I-485
    - G-1145 optional

elif basis in ["parent_of_us_citizen", "child_under_21_of_us_citizen"]:
  route: immediate_relative_flow
  likely_forms:
    - I-485
    - I-130 if not already filed
    - I-864
    - I-765 optional
    - I-131 optional
    - I-693 usually required with I-485

elif basis == "employment_based":
  route: employment_based_flow
  ask_priority_date_and_visa_bulletin_questions: true
  require_attorney_review_recommended: true

elif basis in ["vawa", "t_visa", "u_visa", "asylee_refugee", "special_immigrant"]:
  route: protected_or_special_category_flow
  show_warning: "This case type has special rules. The app can help organize information, but attorney/legal nonprofit review is strongly recommended."

elif basis == "unsure":
  route: eligibility_wizard
  block_pdf_generation_until_basis_selected: true
```

---

## 4. Eligibility Pre-Screen Logic

### 4.1 Physical Presence

Ask: “Is the applicant currently inside the United States?”

```yaml
if applicant_inside_us == false:
  outcome: not_i485_path
  message: "Form I-485 is generally for adjustment of status from inside the United States. You may need consular processing instead."
  stop_or_redirect: consular_processing_info
else:
  continue: true
```

### 4.2 Entry Type

Ask: “How did the applicant last enter the United States?”

Options:

- Entered with visa and was inspected/admitted
- Entered with ESTA/Visa Waiver Program
- Paroled into the U.S.
- Entered without inspection
- Unsure

```yaml
if entry_type == "visa_admitted":
  collect:
    - passport_number
    - travel_document_number_if_any
    - date_of_last_arrival
    - place_of_last_arrival
    - class_of_admission
    - i94_number
  risk: low_to_normal

elif entry_type == "esta_vwp":
  collect same as visa_admitted
  risk_flag: "Visa Waiver Program adjustment can have special considerations. Review recommended."

elif entry_type == "paroled":
  collect:
    - parole_document_type
    - date_paroled
    - place_paroled
    - parole_expiration
    - i94_number_if_any
  risk_flag: "Parole-based adjustment depends on category. Review recommended."

elif entry_type == "entered_without_inspection":
  risk_flag: "Entry without inspection may make I-485 unavailable unless an exception applies, such as 245(i), parole, VAWA, or another special rule. Attorney review strongly recommended."
  branch_to: advanced_eligibility_review

elif entry_type == "unsure":
  ask_upload:
    - passport_biographic_page
    - visa_page
    - I-94
    - entry_stamp
  block_final_packet: true
```

### 4.3 Current Status

Ask: “What is the applicant’s current or most recent immigration status?”

Options:

- B-2 visitor
- F-1 student
- H-1B
- L-1
- J-1
- K-1
- TPS
- Asylum pending
- Parolee
- Out of status
- Overstayed visa
- Unsure

```yaml
if basis == "spouse_of_us_citizen" and entry_type in ["visa_admitted", "paroled", "esta_vwp"]:
  if status in ["out_of_status", "overstayed"]:
    show_note: "Immediate relatives of U.S. citizens may still be eligible despite some overstays or unauthorized employment, but facts matter."
    continue_with_warning: true

if status == "J-1":
  ask: "Are you subject to the 2-year home residency requirement, INA 212(e)?"
  if yes:
    risk_flag: "J-1 212(e) issue. Waiver may be required before adjustment. Attorney review required."

if status == "K-1":
  ask: "Did you marry the U.S. citizen petitioner who filed the K-1?"
  if yes:
    route: k1_adjustment_flow
  if no:
    risk_flag: "K-1 entrant generally must adjust through the original K-1 petitioner. Attorney review required."
```

---

## 5. I-130 Relationship Status Branching

Ask: “Has a Form I-130 already been filed for this applicant?”

Options:

- No, we want to file I-130 and I-485 together
- Yes, it is pending
- Yes, it was approved
- Yes, it was denied
- Unsure

```yaml
if i130_status == "not_filed":
  bundle_mode: concurrent_filing
  require:
    - I-130
    - I-130A if spouse case
    - relationship_evidence
  ask_petitioner_questions: true

elif i130_status == "pending":
  bundle_mode: i485_based_on_pending_i130
  require:
    - I-797C receipt notice for I-130
    - marriage_certificate if spouse case
    - proof_petitioner_status
    - relationship_evidence_recommended
  ask:
    - i130_receipt_number
    - i130_filing_date

elif i130_status == "approved":
  bundle_mode: i485_based_on_approved_i130
  require:
    - I-797 approval notice
    - proof_petitioner_status
    - relationship_evidence_recommended
  ask:
    - i130_approval_date
    - receipt_number

elif i130_status == "denied":
  hard_warning: "A denied I-130 may prevent approval of I-485 unless corrected, appealed, refiled, or another basis exists. Attorney review required."
  block_auto_packet: true

elif i130_status == "unsure":
  ask_upload:
    - USCIS notices
    - receipt notices
    - approval notices
  block_final_packet_until_status_known: true
```

---

## 6. Personal Information Branching

### 6.1 Names

Ask:

- Current legal name
- Other names ever used
- Name at birth
- Maiden name
- Nicknames used in legal/immigration records

```yaml
if has_other_names == true:
  repeat other_name objects:
    - family_name
    - given_name
    - middle_name
    - reason_used
    - dates_used_optional
else:
  map to form as "None" or leave per form instruction logic
```

UI Feature:

- “Where this appears” preview: show user the exact I-485 section being populated.
- Name consistency checker: compare passport, birth certificate, marriage certificate, I-94, visa, prior USCIS notices.

### 6.2 Biographic Info

Collect:

- Sex
- Date of birth
- City/town/village of birth
- Country of birth
- Country of citizenship/nationality
- A-number, if any
- USCIS online account number, if any

```yaml
if a_number_known == false:
  show_helper: "You may find an A-Number on prior USCIS notices, EAD cards, green cards, or immigration court documents."

if country_of_birth != country_of_citizenship:
  ask_reason_optional: "Were you born in one country but are a citizen of another?"
```

---

## 7. Address Logic

### 7.1 Mailing Address

Ask: “Where should USCIS send mail?”

```yaml
if mailing_address_has_care_of == true:
  collect care_of_name

validate:
  - street required
  - city required
  - state required if US address
  - ZIP required if US address
  - country required if foreign address
```

### 7.2 Physical Address

Ask: “Is your physical address the same as your mailing address?”

```yaml
if physical_same_as_mailing == true:
  copy mailing to physical
else:
  collect physical_address
```

### 7.3 Five-Year Address History

Rule: Collect physical addresses for everywhere the applicant lived during the last 5 years, current address first.

```yaml
address_history_required_years: 5
sort_order: current_to_oldest

for each address:
  collect:
    - street
    - apartment/suite/floor
    - city
    - state/province
    - ZIP/postal_code
    - country
    - from_date
    - to_date or present

validation:
  - no gaps greater than 30 days
  - no overlapping ranges unless user confirms temporary housing explanation
  - current address must have "present" end date
  - if address outside US, use province/postal_code/country fields
```

Special UX:

- Timeline bar visual showing 5-year coverage.
- Gap detector: “You have a gap from March 2023 to June 2023. Where were you living?”
- “Temporary stay vs. residence” explainer.

Branch:

```yaml
if user_says_bounced_between_family_homes == true:
  ask:
    - where_did_you_sleep_most_nights
    - approximate_dates
    - can_you_group_under_family_home
  show_note: "Use best truthful physical residence history. Short visits may not be residences, but long stays usually should be disclosed."
```

---

## 8. Recent Immigration History Logic

### 8.1 Last Arrival

Ask:

- Date of last arrival
- Place of last arrival
- Status at last arrival
- I-94 number
- Passport number
- Travel document number, if any
- Passport expiration date
- Country that issued passport/travel document

```yaml
if i94_available == false:
  show_i94_lookup_instructions: true
  allow_manual_no_i94_reason:
    - Canadian land entry
    - old entry
    - lost record
    - parole document instead
    - unsure
```

### 8.2 Class of Admission

```yaml
if class_of_admission_known == false:
  ask_upload_i94: true
  show_helper: "Class of Admission is often shown as B2, B-2, F1, H1B, etc. Use the format shown on your I-94 or entry record."
```

### 8.3 Passport / Travel Document

```yaml
if last_entry_used_passport == true:
  require passport fields
else:
  ask travel_document_fields
```

---

## 9. Prior Applications / Immigration Proceedings

Ask: “Have you ever applied for an immigrant visa at a U.S. Embassy or Consulate?”

```yaml
if prior_immigrant_visa_application == true:
  collect:
    - city
    - country
    - decision
    - date_of_decision
  if decision in ["refused", "denied"]:
    risk_flag: "Prior immigrant visa refusal/denial may require careful review."
```

Ask: “Have you ever been in removal, exclusion, rescission, or deportation proceedings?”

```yaml
if removal_history == true:
  collect:
    - proceeding_type
    - location
    - dates
    - outcome
    - documents
  risk_flag: "Immigration court/removal history. Attorney review required."
  block_self_file_recommendation: true
```

Ask: “Have you ever been ordered removed, deported, or excluded?”

```yaml
if prior_order == true:
  hard_warning: true
  attorney_review_required: true
```

---

## 10. Employment History Logic

Rule: Collect employment history for the required lookback period used by the current I-485 form/instructions.

Fields:

- Employer name
- Employer address
- Occupation
- Start date
- End date or present

```yaml
employment_history:
  allow_unemployed_periods: true
  allow_student_periods: true
  allow_self_employed: true

validation:
  - current employment marked present if active
  - date ranges should not be impossible
  - employer address required unless unemployed/student/homemaker
```

Branch:

```yaml
if unauthorized_employment == true:
  if basis == "spouse_of_us_citizen":
    warning: "Some unauthorized employment may be forgiven for immediate relatives of U.S. citizens, but answer all questions truthfully."
  else:
    risk_flag: "Unauthorized employment can affect adjustment eligibility. Attorney review recommended."
```

TurboTax UX:

- “Add another job” cards.
- “I was unemployed” button.
- Gap detector for employment history if required.

---

## 11. Parent Information Logic

Collect for each parent:

- Legal name
- Name at birth, if different
- Date of birth
- Country of birth
- Current city/country of residence
- Whether deceased

```yaml
if parent_deceased == true:
  ask date_of_death_optional_or_if_form_requires
  disable current residence fields if not needed
```

UX:

- “I don’t know” option, but require explanation if field is mandatory.
- Highlight that unknown should not be guessed.

---

## 12. Marital History Logic

Ask: “What is the applicant’s current marital status?”

Options:

- Single, never married
- Married
- Divorced
- Widowed
- Annulled
- Legally separated

```yaml
if basis == "spouse_of_us_citizen":
  require marital_status == "married"
  collect current_spouse_details
  require marriage_certificate

if applicant_has_prior_marriages == true:
  repeat prior_spouse objects:
    - name
    - date_of_birth_optional
    - date_marriage_started
    - date_marriage_ended
    - place_marriage_ended
    - how_marriage_ended
    - divorce_decree_or_death_certificate

if petitioner_has_prior_marriages == true and basis == "spouse_of_us_citizen":
  require petitioner_prior_marriage_termination_documents
```

Branch:

```yaml
if no_proof_prior_marriage_ended == true:
  blocker: "Cannot safely prepare packet without proof all prior marriages legally ended."
```

---

## 13. Children Logic

Ask: “Does the applicant have any children?”

```yaml
if has_children == true:
  repeat child objects:
    - full_name
    - date_of_birth
    - country_of_birth
    - relationship
    - A-number if any
    - applying_with_applicant?

if child_is_applying_derivative == true:
  generate_child_i485_task: true
  ask principal_applicant_info_for_derivative
```

For immediate relative spouse of U.S. citizen:

```yaml
if basis == "spouse_of_us_citizen" and child_not_child_of_petitioner:
  show_note: "Stepchild eligibility may depend on whether the marriage occurred before the child turned 18."
  ask:
    - child_age_at_marriage
    - petitioner_relationship_to_child
```

---

## 14. Public Charge Logic

Public charge is one of the most important guided sections because incomplete answers can cause rejection or delays.

Ask: “Are you exempt from the public charge ground of inadmissibility?”

```yaml
if category in public_charge_exempt_categories:
  route: public_charge_exempt_flow
  ask_exemption_basis
else:
  route: public_charge_subject_flow
  require_all_public_charge_questions_answered: true
```

Potential exempt categories may include certain humanitarian categories, depending on current rules.

### Public Charge Subject Flow

Collect:

- Household size
- Annual household income
- Assets, if needed
- Liabilities/debts
- Education level
- Occupational skills
- Certifications/licenses
- Health insurance status
- Receipt of certain public benefits, if applicable

```yaml
if subject_to_public_charge == true:
  require:
    - household_size
    - income
    - education
    - employment_skills
    - health_insurance_answer
    - public_benefits_answers

if missing_any_public_charge_required_field:
  hard_block_submission_review: true
```

UX:

- Dedicated “Public Charge completeness meter.”
- Plain-English helper: “This does not mean you are automatically denied. USCIS uses this section to evaluate whether someone is likely to become primarily dependent on the government.”
- Red warning if any public charge field is skipped.

---

## 15. Affidavit of Support Logic: I-864

For marriage-based U.S. citizen cases, ask:

- Is the petitioner a U.S. citizen?
- Is the petitioner domiciled in the United States?
- Petitioner household size
- Petitioner income
- Most recent tax return availability
- W-2/1099 availability
- Current employment evidence

```yaml
if basis in family_based_categories_requiring_i864:
  require_form_i864: true

if petitioner_income >= required_threshold:
  sponsor_status: likely_sufficient
  checklist:
    - I-864
    - tax transcript or tax return
    - W-2/1099 if applicable
    - pay stubs
    - employment letter optional/recommended

elif petitioner_income < required_threshold:
  ask:
    - assets_available
    - joint_sponsor_available
  if joint_sponsor_available:
    require_joint_sponsor_i864: true
  else:
    risk_flag: "Sponsor income may be insufficient. Need assets, joint sponsor, or attorney review."
```

UX:

- Sponsor income calculator.
- Household-size builder.
- Dynamic checklist for joint sponsor.
- “Why this matters” explainer.

---

## 16. Medical Exam Logic: I-693

Ask: “Do you already have a completed Form I-693 from a USCIS civil surgeon?”

```yaml
if has_i693 == true:
  ask:
    - date_signed_by_civil_surgeon
    - sealed_envelope_or_pdf_upload_status
  require_document: I-693

elif has_i693 == false:
  add_task: "Schedule medical exam with USCIS civil surgeon"
  show_warning: "Many applicants must submit Form I-693 with I-485 under current USCIS requirements."
  mark_packet_incomplete: true

if filing_online == true:
  show_note: "Online filing may require uploading the completed I-693. Follow current USCIS instructions."

if filing_by_mail == true:
  show_note: "For mailed packets, follow current USCIS instructions for submitting the sealed I-693 envelope."
```

UX:

- Civil surgeon finder link area.
- “Do not open sealed envelope unless filing method requires it” warning.
- Medical checklist: vaccine records, ID, passport, prior medical records.

---

## 17. Inadmissibility and Security Question Logic

This section should be a guided yes/no wizard with strong warnings.

### Categories

1. Criminal acts / arrests / convictions
2. Controlled substances
3. Immigration fraud or misrepresentation
4. False claim to U.S. citizenship
5. Prior removals / unlawful presence bars
6. Smuggling
7. Public charge
8. Security / terrorism / espionage
9. Communist or totalitarian party membership
10. Genocide / persecution / torture
11. Prostitution / commercialized vice
12. Polygamy
13. Child abduction / voting / draft issues

Generic pattern:

```yaml
for each inadmissibility_question:
  ask yes_no
  if yes:
    collect explanation
    ask_upload_supporting_documents
    create_risk_flag
    attorney_review_required: true
  if unsure:
    create_risk_flag
    ask_clarifying_questions
    recommend_attorney_review: true
```

### Arrest / Criminal History

```yaml
if ever_arrested_or_cited == true:
  collect:
    - date
    - location
    - charge
    - outcome
    - certified court disposition
  attorney_review_required: true
  block_auto_recommendation_to_file: true
```

### Immigration Fraud / Misrepresentation

```yaml
if prior_false_statement_to_immigration_or_consulate == true:
  hard_warning: "Possible fraud/misrepresentation issue. Attorney review required."
  block_self_file_recommendation: true
```

### False Claim to U.S. Citizenship

```yaml
if false_claim_us_citizen == true:
  hard_warning: "False claim to U.S. citizenship can be extremely serious. Attorney review required."
  block_self_file_recommendation: true
```

### Unlawful Voting

```yaml
if ever_voted_in_us == true:
  ask:
    - election_type
    - date
    - registration_details
    - whether_claimed_citizenship
  attorney_review_required: true
```

---

## 18. Evidence Checklist Logic

### 18.1 Base I-485 Evidence

Always consider:

- Completed I-485
- Filing fee/payment method or fee waiver if applicable
- Passport-style photos, if required by current instructions
- Birth certificate with certified translation if not in English
- Passport biographic page
- Visa page, if any
- Entry stamp, if any
- I-94 record
- I-693 medical exam, if required
- Government-issued ID
- Prior USCIS notices, if any

```yaml
if birth_certificate_language != "English":
  require_certified_translation: true

if no_birth_certificate:
  branch_to_secondary_birth_evidence_flow
```

### 18.2 Marriage-Based Evidence

If spouse of U.S. citizen:

- Marriage certificate
- Proof petitioner is U.S. citizen
  - U.S. passport
  - Naturalization certificate
  - Birth certificate
  - Certificate of citizenship
- Proof prior marriages ended for both spouses
- Bona fide marriage evidence
  - Joint lease/mortgage
  - Joint bank account
  - Joint insurance
  - Joint utility bills
  - Photos together
  - Travel records
  - Affidavits from friends/family
  - Shared subscriptions/memberships
  - Authorized user credit card evidence
  - Mail at shared address

```yaml
if joint_bank_account == false:
  suggest_alternatives:
    - lease together
    - utility bill together
    - insurance beneficiary
    - authorized user card statements
    - shared address mail
    - photos and travel records

if couple_lives_together == false:
  ask_reason
  require_explanation_and_more_evidence: true
```

### 18.3 Pending I-130 Evidence

```yaml
if i130_status == "pending":
  require:
    - I-797C receipt notice
  recommend:
    - copy of I-130 packet if available
    - updated relationship evidence
```

### 18.4 Approved I-130 Evidence

```yaml
if i130_status == "approved":
  require:
    - I-797 approval notice
```

---

## 19. Packet Assembly Logic

### 19.1 Suggested Order for Marriage-Based I-485 Packet When I-130 Is Pending

1. Cover letter
2. G-1145, if using
3. Payment / fee evidence, if mailing
4. Form I-485
5. I-485 supporting documents
6. I-130 receipt notice
7. Proof of petitioner’s U.S. citizenship
8. Marriage certificate
9. Proof prior marriages ended
10. I-864 and financial evidence
11. I-693 medical exam, if required
12. I-765, if filing
13. I-765 supporting documents
14. I-131, if filing
15. I-131 supporting documents
16. Relationship evidence section
17. Additional explanations / Part 14 continuation pages

### 19.2 Cover Letter Generator Logic

```yaml
cover_letter_fields:
  - applicant_name
  - applicant_address
  - date
  - filing_type
  - basis
  - i130_receipt_number_if_pending
  - forms_included
  - evidence_list
  - special_notes

if i130_pending:
  include_sentence: "Applicant is filing Form I-485 based on a pending Form I-130, receipt number [receipt]."

if i693_included:
  include_sentence: "Form I-693 medical examination is included."
```

---

## 20. Review and Risk Flag Engine

### 20.1 Risk Levels

```yaml
risk_levels:
  green:
    meaning: "Typical issue; app can proceed."
  yellow:
    meaning: "User should review carefully; optional attorney review."
  orange:
    meaning: "Complex issue; attorney review recommended."
  red:
    meaning: "High-risk issue; do not recommend self-filing."
```

### 20.2 Red Flags

Trigger red flag if:

- Entry without inspection and no clear exception
- Prior removal/deportation order
- Criminal arrest/conviction history
- Drug-related issue
- False claim to U.S. citizenship
- Immigration fraud/misrepresentation
- J-1 subject to 212(e) without waiver
- Prior denied I-130 or I-485
- Applicant outside U.S.
- Marriage not legally valid
- Prior marriages not legally terminated
- Missing required medical exam where required
- Missing public charge required answers

### 20.3 Yellow/Orange Flags

- Overstay
- Unauthorized employment
- Visa Waiver Program entry
- Inconsistent addresses
- No joint residence evidence
- No financial co-mingling
- Missing birth certificate
- Name mismatch across documents
- Pending asylum/TPS/parole complexities

---

## 21. TurboTax-Style UI Features

### 21.1 Guided Interview

- One question per screen for high-friction areas.
- Grouped cards for repeated data: addresses, jobs, children, prior marriages.
- Plain-language question title.
- Small “Why we ask” expandable explanation.
- “Where this goes on the form” preview.

Example:

```text
Question: What was your class of admission?
Helper: This is the status you were admitted under when you last entered the U.S. It may look like B2, B-2, F1, H1B, or Parolee on your I-94.
CTA: Upload I-94 and we’ll help you find it.
```

### 21.2 Smart Progress Bar

Instead of generic 40% complete, show:

```text
Eligibility       Complete
Identity          Complete
Immigration       Needs I-94
Marriage          2 items missing
Financial Support Needs sponsor income
Medical Exam      Not started
Review            Locked
```

### 21.3 Dynamic Checklist

Every answer updates the checklist.

```yaml
if spouse_case:
  add marriage_certificate
if prior_marriage:
  add divorce_decree
if foreign_language_document:
  add certified_translation
if pending_i130:
  add i130_receipt_notice
if no_joint_bank:
  recommend alternate_bona_fide_marriage_evidence
```

### 21.4 Upload-to-Question Matching

Features:

- Upload passport -> map to passport fields.
- Upload I-94 -> map class of admission, date of arrival, admission until date.
- Upload marriage certificate -> map marriage date/place.
- Upload USCIS receipt -> extract receipt number.

Show confidence:

```text
We found: Class of Admission = B2
Confidence: High
Please confirm before continuing.
```

### 21.5 Error Prevention

- Date format enforcement.
- No future birth dates.
- Passport expiration cannot be before issue date.
- Address gap detector.
- Employment gap detector if relevant.
- Required yes/no questions cannot be skipped.
- Public charge section cannot be partially complete.
- Conditional explanations required when answer is “Yes” to serious questions.

### 21.6 Review Screen

Sections:

- Form answers preview
- Missing information
- Inconsistencies
- Evidence checklist
- Risk flags
- Generated forms
- Filing instructions

Example:

```text
Before you export:
3 missing required items
2 recommended items
1 attorney review flag
```

### 21.7 Confidence and Complexity Score

```yaml
case_complexity_score:
  0-20: simple
  21-50: moderate
  51-80: complex
  81-100: attorney strongly recommended
```

Factors:

- Clean lawful entry lowers score
- Immediate relative lowers score
- Missing documents increases score
- Criminal/removal/fraud issues sharply increase score
- Prior denials increase score

### 21.8 Human Review Mode

For immigration lawyers or preparers:

- Internal notes per question
- Flag resolution checklist
- Document verification status
- Client-facing missing item request
- Audit trail of changed answers
- PDF field mapping view

### 21.9 Client Portal Features

- Mobile-friendly checklist
- Upload from phone camera
- Document status: Needed / Uploaded / Accepted / Rejected
- Secure messaging per missing item
- Auto-reminders
- Deadline/task board

### 21.10 Explanatory Microcopy

Examples:

```text
A-Number: If you have never had an immigration case before, you may not have one.

I-94: This is your arrival/departure record. It helps prove you were admitted or paroled into the U.S.

Class of Admission: This is the visa/status code from your last U.S. entry, like B2 or F1.

Public Charge: These questions help USCIS evaluate whether you are likely to become primarily dependent on government support.
```

---

## 22. Data Model Sketch

```yaml
Applicant:
  legal_name
  other_names[]
  date_of_birth
  sex
  city_of_birth
  country_of_birth
  citizenship_country
  a_number
  uscis_online_account_number
  ssn
  addresses[]
  immigration_entries[]
  employment_history[]
  parents[]
  marriages[]
  children[]
  inadmissibility_answers[]
  public_charge_profile
  documents[]
  risk_flags[]

Petitioner:
  legal_name
  immigration_status
  proof_of_status_document
  address
  income
  household_size
  tax_documents[]
  prior_marriages[]

Case:
  basis
  i130_status
  receipt_number
  filing_mode
  forms_selected[]
  checklist_items[]
  complexity_score
  review_status
```

---

## 23. Recommended MVP Build Order

### MVP 1: Happy Path Marriage-Based I-485

Support only:

- Applicant inside U.S.
- Married to U.S. citizen
- Lawful admission/parole
- No criminal history
- No removal history
- No fraud/misrepresentation issue
- I-130 pending, approved, or concurrent

Features:

- Guided intake
- I-485 data collection
- I-864 checklist
- I-693 task flow
- Evidence checklist
- Cover letter generator
- PDF export preparation
- Risk flag blocker

### MVP 2: Add I-765 and I-131

- Employment authorization wizard
- Advance parole wizard
- Separate evidence checklists
- Bundle assembly ordering

### MVP 3: Add Lawyer/Preparer Dashboard

- Multi-client dashboard
- Missing docs tracker
- Notes and review status
- Client reminders
- White-label client portal

### MVP 4: Add Complex Categories Carefully

- Employment-based
- Parent/child immediate relatives
- K-1 entrants
- VAWA/humanitarian categories only with expert review

---

## 24. Final Submission Guardrails

Before allowing export, require:

```yaml
required_checks:
  - applicant_inside_us == true
  - basis_selected == true
  - identity_fields_complete == true
  - address_history_complete == true
  - immigration_entry_complete == true
  - public_charge_complete_if_required == true
  - all_required_yes_no_questions_answered == true
  - required_documents_uploaded_or_marked_manual == true
  - red_flags_resolved_or_attorney_review_acknowledged == true
  - user_certifies_truthfulness == true
```

Final certification screen:

```text
You are responsible for reviewing every answer before filing. USCIS forms are signed under penalty of perjury. Do not guess. If any answer is uncertain, pause and verify it before submitting.
```

---

## 25. “Do Not Automate Blindly” Fields

These should always require user confirmation:

- Legal name
- Date of birth
- Country of birth
- Citizenship
- A-number
- I-94 number
- Class of admission
- Date of last arrival
- Immigration violations
- Criminal/security/inadmissibility questions
- Public charge answers
- Signature/certification fields

---

## 26. Best UX Differentiators

The strongest version of this product is not merely “fill out I-485 faster.” It is:

1. **Eligibility triage** before users waste time.
2. **Evidence intelligence** that tells users what they need based on their facts.
3. **Risk detection** that prevents unsafe self-filing.
4. **Plain-English explanations** of confusing immigration terms.
5. **Document-driven autofill** with user confirmation.
6. **Lawyer-ready review mode** for monetization through attorneys or preparers.
7. **Packet assembly clarity** so users know exactly what to mail or upload.

---

## 27. Suggested App Navigation

```text
Dashboard
  - Start / Continue Case
  - Missing Documents
  - Risk Flags
  - Forms Bundle
  - Review Packet
  - Export

Questionnaire
  - Eligibility
  - About You
  - Immigration History
  - Address History
  - Family
  - Financial Support
  - Medical Exam
  - Yes/No Questions

Documents
  - Uploads
  - Required
  - Recommended
  - Rejected / Needs Better Copy

Review
  - Form Preview
  - Evidence Preview
  - Cover Letter
  - Packet Order
  - Final Warnings
```

---

## 28. Monetization-Oriented Feature Ideas

Free tier:

- Eligibility pre-screen
- Basic I-485 checklist
- Basic document checklist

Paid self-serve tier:

- Full guided questionnaire
- PDF export
- Cover letter
- Packet order
- Evidence checklist
- I-765/I-131 add-ons

Premium tier:

- Human review
- Lawyer/preparer review marketplace
- Document review
- Relationship evidence review

B2B lawyer tier:

- Client intake portal
- PDF generation
- Case dashboard
- Missing document automation
- White-label branding
- CRM integrations

---

## 29. Engineering Notes

Recommended architecture:

```yaml
frontend:
  - React / Next.js
  - Step-based form engine
  - Conditional schema rendering
  - Upload UI
  - Review dashboard

backend:
  - FastAPI or Node/Express
  - PostgreSQL
  - S3-compatible document storage
  - Background OCR/document extraction
  - PDF field mapping service

rules_engine:
  - JSON/YAML decision trees
  - versioned by USCIS form edition
  - test suite for scenarios

security:
  - encryption at rest
  - encryption in transit
  - audit logs
  - strict document access controls
  - deletion/export controls
```

---

## 30. Test Scenarios

### Scenario A: Clean Spouse Case, I-130 Pending

```yaml
inside_us: true
basis: spouse_of_us_citizen
entry: B2 admitted
status: overstay
criminal_history: false
removal_history: false
i130_status: pending
outcome: allow_with_normal_warnings
required_docs:
  - I-130 receipt
  - marriage certificate
  - proof US citizenship
  - I-94
  - passport
  - birth certificate + translation if needed
  - I-864
  - I-693
```

### Scenario B: Entered Without Inspection

```yaml
inside_us: true
basis: spouse_of_us_citizen
entry: entered_without_inspection
outcome: red_flag
message: attorney_review_required
block_self_file_recommendation: true
```

### Scenario C: Prior Arrest

```yaml
criminal_history: true
outcome: red_flag
required_docs:
  - certified court disposition
  - police/court records
attorney_review_required: true
```

### Scenario D: Missing Public Charge Answers

```yaml
subject_to_public_charge: true
missing_public_charge_fields: true
outcome: block_review
message: complete_all_public_charge_questions
```

### Scenario E: Prior Marriage Without Divorce Decree

```yaml
prior_marriage: true
termination_document_missing: true
outcome: block_packet
message: proof_of_termination_required
```

### Scenario F: J-1 Subject to 212(e)

```yaml
status: J1
subject_to_212e: true
waiver_obtained: false
outcome: red_flag
attorney_review_required: true
```

---

## 31. Summary

For an I-485 TurboTax-style product, the core product is a **rules-driven intake system** that transforms a terrifying government form into a guided, conditional workflow. The app should not just collect answers. It should detect eligibility issues, build the evidence checklist, prevent missing mandatory sections, and clearly separate simple self-serve cases from cases that require legal review.
