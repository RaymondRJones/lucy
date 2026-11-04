# Rules Engine

## Purpose

The Phase 1 rules layer powers two workflows:

- checklist generation
- packet QA and readiness scoring

## Inputs

- merged intake state
- happy-path prescreen answers and their branch projection, aligned to the MVP path in `branching-logic.md`
  and including single-answer gates, multi-select risk screens, and grouped answer blocks
- isolated I-485 questionnaire answers and their `i485_projection` intake step
- isolated I-130, I-130A, I-765, I-131, and I-864 questionnaire answers and their `{form_key}_projection` intake steps
- derived case facts
- upload metadata
- extracted document fields from supported packet uploads
- checklist completion state

## Implementation pattern

The backend rules layer now uses small ordered rule engines instead of placing workflow policy directly
inside route or service functions.

- `apps/api/app/services/rules/core.py` defines the shared `Rule`, `RuleResult`, and `RuleEngine`
  primitives.
- `apps/api/app/services/rules/case_facts.py` derives normalized workflow, I-130 branch, optional-form,
  evidence-readiness, and escalation facts from merged intake.
- `apps/api/app/services/rules/prescreen.py` owns prescreen question visibility, branch elimination,
  included forms, next steps, and happy-path status rules.
- `apps/api/app/services/rules/checklist.py` turns checklist templates plus derived facts into explicit
  checklist decisions: applicability, progress status, upload counts, form grouping, and USCIS requirement
  metadata.
- `apps/api/app/services/rules/qa.py` runs QA checks in a stable order so source-backed mismatch rules can
  establish trusted comparison sources before fallback upload-quality rules run.
- `apps/api/app/services/rules/questionnaire.py` evaluates source-dated form questionnaires, including
  required-answer counts, mapped source-of-truth fields, risk flags, page summaries, and readiness labels for
  I-485 and supplemental form ingestion.
- `apps/api/app/services/rules/filing_validation.py` provides the form-validator registry/dispatch engine used
  by the filing-validation API, replacing long form-code conditionals with ordered validation rules. The actual
  form-specific validators live in `apps/api/app/services/filing_validators/`, one module per form or form family.

The route/service modules still coordinate persistence, transactions, and API response shape. Workflow truth
should continue moving into rule classes or source-dated content rather than being duplicated in JSX or route
handlers.

## Current fact derivation

The API derives stable booleans from intake data, including:

- petitioner U.S. citizenship
- spouse already in the U.S.
- lawful entry flag
- concurrent filing eligibility
- whether Form I-130 has not been filed yet or was already filed
- whether the saved I-130 branch should pause for review because the petition was denied, revoked,
  withdrawn, or unknown
- wants `I-765`
- wants `I-131`
- translation need
- identity, address, entry details, relationship evidence signals, sponsor support snapshot, public-charge
  readiness, and review flags projected from the guided prescreen when the user answers those screens
- employment-income flag
- escalation triggers such as criminal history or prior denials

## Checklist generation

Checklist templates live in `apps/api/app/content/checklist_rules.py`.

Each template defines:

- code
- category
- label
- owner role
- description
- why-needed content
- what-to-save-now content
- default applicability
- required fact flags

The generator:

1. merges intake state
2. derives case facts
3. evaluates applicability for every template
4. preserves or updates completion state
5. updates upload counts and checklist metadata
6. attaches form-packet relationships so the UI can show which checklist items support which USCIS forms

The checklist now chooses the family-petition branch from `i130_filing_status`:

- `not_filed`: Forms I-130 and I-130A remain applicable so the user can prepare them in Lucy.
- `pending` or `approved`: I-130/I-130A draft tasks are eliminated and receipt/approval evidence becomes applicable.
- `denied_revoked_withdrawn` or `unknown`: the prescreen marks the branch for review before generated
  document actions should be trusted.

Entry branching follows the same MVP boundary:

- normal visa admission continues without a branch flag
- ESTA/VWP or parole can continue but stays visible as a review-suggested flag
- entered without inspection, crewman/transit, or unknown entry creates a critical review flag

The I-485 packet checklist also tracks W-2/1099 support and utility/household bill evidence so packet
assembly can follow `i-485-complete-package-req.md` without silently merging unrelated uploads. When the
I-130 is already pending, the receipt notice stays required and core relationship evidence uploads
(`marriage_certificate`, `photos_together`, `joint_bank_statement`, and `joint_lease`) are grouped under
the I-485 packet so users can add updated bona fide-marriage evidence without preparing a duplicate I-130.

## Packet assembly

The printable packet compiler follows the local order reference in `i-485-complete-package-req.md`
and scanner-friendly USCIS mail guidance:
I-485 packet payments first when present, then the generated cover letter/table of contents, G-1145,
I-485 evidence, I-864 evidence, I-693, I-765, and I-131. Payment PDFs can be generated from the G-1450 service during packet assembly, or supplied as confirmed `payment_g1450` uploads when the user
brings their own signed Form G-1450. I-130 and I-130A petition materials are skipped for the
pending-I-130 path and reported in the manifest instead of being silently merged.
When `i130_filing_status` is `not_filed`, the packet is a concurrent filing: it adds the Form I-130 fee to the payment
set and ends with an I-130 section holding Forms I-130 and I-130A, petitioner and beneficiary photos, citizenship proof,
the marriage certificate, prior-marriage records, and the single copy of bona fide marriage evidence. USCIS sets no
order between Forms I-130 and I-485, so section placement follows `i-485-complete-package-req.md`. Photos and civil
documents repeat because each filing needs its own copy. A blank status keeps the I-485-only packet and adds a warning.
A freshly generated payment form replaces any uploaded payment PDF, which is reported as skipped so fees are not paid twice.
Bank-account payment uses the same flow through Form G-1650, with one payment form per payable filing and one payment
method per packet (verified 2026-10-30, https://www.uscis.gov/g-1650). The `payment_g1450` checklist code is kept for
stored cases and now covers either form. Previously generated G-1450 and G-1650 PDFs are not auto-merged because stale payment PDFs can contain outdated
applicant/requestor data.
When packet assembly is run with `include_supporting_evidence=false`, uploaded supporting evidence is
excluded from the merged PDF so the user can print a forms/payment-only draft while preserving the
uploaded evidence records on the case.
The generated PDF uses plain letter-size section index pages for major form/evidence segments instead
of physical tabs, binders, folders, sticky notes, or other separators that can slow scanning.

## QA checks

The QA pass currently flags:

- missing required checklist items
- missing translation support for non-English uploads
- higher-risk intake answers that should trigger legal escalation
- source-prioritized mismatches across uploaded forms and civil records for shared facts such as names, marriage dates, admission details, and current addresses
- mismatches between saved intake facts and uploaded document fields for names, date of birth, country
  of birth, immigration status, I-94 number, and current address
- likely missing prior-address history when a recent current address is detected but no prior address section is found in the extracted form text
- likely missing prior-address history when intake says the current address started less than five
  years ago and neither intake nor uploaded forms include prior address history
- I-485 questionnaire answers that indicate the case is outside the standard first-marriage,
  U.S.-citizen-spouse niche or that raise potentially serious inadmissibility/legal-review concerns
- I-485 ingestion flags are surfaced in packet QA so the main readiness score cannot ignore blocking
  I-485 risk answers or important outside-niche answers
- I-765, I-131, and I-864 ingestion pages evaluate their own completion and form-generation blockers; shared
  mapped fields are projected into intake, while deeper QA integration remains a follow-up
- I-130 and I-130A use the same isolated supplemental-form pattern when the prescreen branch says the spouse
  petition has not been filed yet
- Smart defaults use the backend intake projection plus direct field aliases for repeated facts across I-130,
  I-130A, I-485, I-765, and I-131, such as current address variants, last-arrival place versus city/state,
  SSN wording, and reusable biographic fields
- fallback name mismatches when upload metadata conflicts with intake data and no stronger uploaded source of truth is available
- unsigned-form flags when upload metadata marks a form as unsigned
- missing user confirmation for current fee and form-edition review

## Filing validation extension API

The filing validation API is a form-level preflight layer for source-of-truth DB records and saved form answers.
It is intentionally separate from persisted packet QA:

- `POST /cases/{case_id}/filing-validation` runs without deleting or rewriting `qa_issues`
- `form_i485` validation uses the source-dated I-485 questionnaire map, saved answer provenance, and blank PDF
  field names from `blank-immigration-documents/i-485.pdf`
- `form_i485` currently flags missing required answers, risk/outside-niche answers, low-confidence extracted
  answers, blank-template field mismatches, unmapped answered required fields, five-year address-history gaps,
  and mismatches between I-485 answers and the merged case source of truth
- The I-485 question map models repeatable prior-address and five-year employment/school/unemployment history
  as structured entry lists with on-form capacity metadata and Part 14 overflow review guidance; the PDF draft
  maps the first employment-history entry to Part 4 Item 7 and continuation entries to Part 14 draft fields.
- The I-485 question map follows the 09/18/26 edition (verified 2026-10-30, https://www.uscis.gov/i-485). Item 57 is a
  written family status, drafted from marital status and household size when left blank. Item 63 asks about any
  means-tested public benefit, and a yes makes the Item 64 benefit table required. Answers saved to the prior
  `received_cash_benefits`, `received_long_term_institutionalization`, and `public_charge_benefit_details` questions
  are retained but never carried over, so existing cases show Item 63 as missing until it is answered. Text too long
  for a form field moves to Part 14, and text that does not fit in Part 14 is reported as an unmapped answer.
- Each Part 9 yes/no question answers exactly one form item (`apps/api/tests/test_i485_form_mapping.py` matches every
  question's item number against the template's own field wording). Answers saved to the earlier combined questions, such
  as `human_trafficking` or `weapons_training_or_violence`, are retained but never carried over, because a combined "no"
  would attest to items the applicant was not asked. Existing cases show the individual items as missing until answered.
- The form's follow-ups are required only when they apply: Items 29, 35.b, 40, 20, 21, 75 and 84, other dates of birth and
  A-Numbers, grade completed, children, prior marriages, and organizations.
- Part 3 ticks one box from `i485_i864_exemption`. Other names, other dates of birth, other A-Numbers, prior marriages,
  children, and organizations are structured `entry_list` answers that fill their form rows. An entry that is extra or too
  long moves whole to Part 14, and free text saved before these were structured is copied to Part 14 unchanged.
  `criminal_explanations` is filed in Part 14 against Items 22-41.
- If Part 14 cannot hold prior addresses, employment history, or these lists, the answer is reported as unmapped instead of
  being dropped. Text fields too long for their box are named in the generation warnings on I-485, I-130, I-130A, I-765,
  I-131, I-864, and G-1145.
- I-765 Items 2-4 and I-131 Part 2 Item 2 take other names as "Family name, Given name Middle name", one per line. Lines
  without a comma go to the additional information section as written, since the family name cannot be identified.
- I-130A employment history fills Employer 1 and 2 when structured and otherwise goes to Part 7. The more specific current
  employer answers win over the history's first row.
- Missing required I-485 answers are a blocking QA issue, so a case with a started I-485 cannot read as ready to print. The
  stored readiness label updates the next time QA runs.
- Other names entered on the I-485 are shared through intake and proposed to the I-765 and I-131 as one name per line.
- Free text saved on a list entry before it was structured is shown on the entry and prints in Part 14, on every I-485 list.
  It does not keep the entry's structured fields off the form, and it does not put "See Part 14" in the next row, because only
  a whole entry moved to Part 14 gets that pointer. If Part 14 cannot hold the note, the row still prints and the question is
  reported as unmapped.
- I-485 Part 1 Items 12 and 14 print the class label for a recognized class, including spaced forms such as `B 2`. A description
  too long for the 20-character box collapses to its class. A shorter answer such as `F-1 OPT` keeps its wording.
- I-130 Part 4 Item 21.a is a dropdown that accepts only the codes in `I130_CLASS_OF_ADMISSION_CODES`, read from the blank form.
  An answer with no matching option, such as `TN` (the form offers `TN1` and `TN2`), is left blank with a generation warning and
  a `form_i130_class_of_admission_not_offered` validation issue. Lucy does not guess the option.
- A history entry supplies current-employer details only when it names the current employer. With no current employer answer,
  it supplies them only when it is the single open entry, and then it supplies the name too. On the I-130A the current employer
  takes the first row, other jobs keep their rows or continue in Part 7, and an answered unit is not replaced by the history's.
- The I-130A, I-765, and I-131 validators read facts from saved I-485 answers when intake lacks them, as import and generation
  do. Facts already in intake are kept, so cross-form mismatch checks still compare them with the I-485.
- Not yet on the generated forms: I-485 Parts 11-12 interpreter and preparer details, and I-130A Part 3 employment outside
  the United States.
- `form_i130` is supported as a partial validator for petitioner citizenship, core relationship facts,
  first-marriage scope, adjustment-of-status path selection, tracked citizenship/marriage supporting evidence,
  and source-dated core question metadata; blank I-130 PDFs are auto-detected from `blank-immigration-documents/`
  when present, with first-pass PDF fill-payload coverage for core mapped facts and cross-form mismatch checks
  against saved I-485 answers and extracted uploaded I-130 values
- `form_i130a` is supported as a partial validator for beneficiary biographic facts, current address,
  five-year address history, employment history, simple first-marriage scope, and source-dated core question
  metadata; blank I-130A PDFs are auto-detected from `blank-immigration-documents/` when present, with first-pass
  PDF fill-payload coverage for core mapped facts and cross-form mismatch checks against saved I-485 answers and
  extracted uploaded I-130/I-130A values
- `form_i864` currently performs a sponsor preflight for identity, address, household size, employment,
  annual income, source-dated I-864P threshold comparison, and required tax evidence, backed by USCIS
  requirement metadata and USCIS Form I-864P content verified on 2026-04-28
- `form_g1145` is supported as an optional validator for e-notification name, email, and mobile phone fields,
  using the local blank G-1145 PDF for field-count inspection
- `form_i765` is supported as an optional partial validator for the adjustment-pending `(c)(9)` path, checking
  core beneficiary identity/travel facts, current address, tracked I-94/passport evidence, and I-485 basis presence
- `form_i131` is supported as an optional partial validator for the pending-I-485 advance parole path, checking
  core beneficiary identity/admission facts, proposed travel facts, tracked passport-photo, official photo-ID,
  I-94/status, and travel-explanation evidence, I-485 basis presence, and first-pass PDF field-map coverage
- unsupported requested forms return structured roadmap issues instead of silently passing

## Upload linking

Uploads are no longer assumed to satisfy only one checklist item.

- A combined `I-130` packet can satisfy both `form_i130` and `form_i130a` when the supplemental spouse section is detected in the same PDF.
- A translated birth-certificate upload can satisfy both `beneficiary_birth_certificate` and `translation_certification`.
- The UI uses these linked codes to build per-form packet milestones and clearer “what is still missing” summaries.

## Readiness scoring

The score is intentionally conservative and non-legal:

- starts from required completion percentage
- subtracts weighted penalties for blocking, important, and recommended issues
- maps to `Not ready`, `Almost ready`, `Ready for final review`, or `Ready to print and assemble`

## Production follow-ups

- move rules into YAML or DB-managed content
- add fee and form-edition references sourced from official USCIS data
- plug OCR extraction into `uploaded_documents.extracted_fields`
- add admin editing, versioning, and audit views
- add a reviewed regeneration workflow for I-485 question maps when USCIS publishes a new form edition
- expand filing validation with source-dated question/PDF field maps for I-130, I-130A, I-765, I-131, G-1145,
  and a full I-864 poverty-guideline and supporting-evidence validator
