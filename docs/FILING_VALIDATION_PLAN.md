# Filing Validation Extension Plan

Verified on: 2026-04-28

Sources:

- USCIS Form I-485 page: https://www.uscis.gov/i-485
- USCIS Form I-485 PDF: https://www.uscis.gov/sites/default/files/document/forms/i-485.pdf
- USCIS Form I-864 page: https://www.uscis.gov/i-864
- USCIS Form I-864 PDF: https://www.uscis.gov/sites/default/files/document/forms/i-864.pdf
- Local blank PDFs: `blank-immigration-documents/`

## Product Boundary

The filing validation API is a backend-owned preflight layer for a simple marriage-based concurrent filing case:

- petitioner is a U.S. citizen
- beneficiary is in the United States
- beneficiary last entered with inspection/admission or parole
- both spouses are in their first marriage
- no children, prior marriages, criminal history, removal history, fraud, unlawful entry, or other inadmissibility trigger is expected
- Form I-864 is required, not an exemption path

This layer is not legal advice and must not make final eligibility decisions. It should surface missing data, contradictions, unmapped PDF fields, stale or unverified source assumptions, and answers that need human or attorney review.

## API Contract

Current endpoints:

- `GET /api/v1/content/filing-validation`
- `POST /api/v1/cases/{case_id}/filing-validation`

The content endpoint lets the UI discover supported validators, default blank PDF paths, detected PDF field counts, source metadata, and roadmap status.
It also reports blank PDF page counts and SHA-256 hashes so field maps can be tied to the exact local template that was inspected.

The case endpoint validates current DB state and saved form answers without mutating `qa_issues` or readiness score. Its default scope is:

- `form_i485`
- `form_i864`

The request can include:

- `form_codes`: list of validators to run
- `template_paths`: map of form code to a local blank PDF path for field coverage checks

## Validation Output Model

Every validation response should include:

- overall status: `passed`, `review_suggested`, `needs_review`, or `blocked`
- issue counts by severity
- assumptions used by the validator
- per-form status and source metadata
- per-form blank PDF field count
- missing required field count
- structured issues with stable codes
- roadmap entries for planned validators

Issue severities:

- `blocking`: should prevent filing-ready status
- `important`: should be reviewed before generating or filing
- `recommended`: should be checked by a human but may not block a review draft

Issue sources:

- `case_intake`
- `i485_questionnaire`
- `answer_provenance`
- `pdf_field_map`
- `blank_pdf_template`
- `record_consistency`
- `validator_registry`

## Implemented Now

### Form I-485

The I-485 validator uses:

- `apps/api/app/content/i485_questionnaire.py`
- saved `i485_ingestion:*` answers
- saved `i485_projection` case facts
- `apps/api/app/services/i485_pdf.py` PDF field mapping
- the default blank PDF at `blank-immigration-documents/i-485.pdf`

Current checks:

- missing required questionnaire answers
- risk and outside-niche answers
- lower-confidence PDF-extracted answers
- mapped fields missing from the selected blank PDF
- required answered questions without PDF field mappings
- current address less than five years old without prior address history
- I-485 answers that differ from the merged case source of truth

### Form I-864

The I-864 validator is currently a minimal sponsor preflight. It uses existing USCIS requirement metadata and the default blank PDF at `blank-immigration-documents/i-864.pdf`.
It also uses the source-dated 2025 USCIS Form I-864P thresholds in `apps/api/app/content/i864_poverty_guidelines.py`.

Current checks:

- sponsor first name
- sponsor last name
- sponsor address
- sponsor annual income
- sponsor employment status
- household size
- positive numeric income
- source-dated I-864P income threshold comparison by household size and sponsor region
- missing most recent federal tax return upload or no-filing explanation
- recommended current income support when the sponsor is employed but pay stubs/employment letter uploads are absent
- current fee review confirmation

This does not yet replace a full I-864 line-by-line review.

## Implementation Roadmap

### Phase 1: Hardening the Existing Validator

1. Add route-level tests for `POST /cases/{case_id}/filing-validation`.
2. Add route-level tests for `GET /content/filing-validation`.
3. Add UI wiring so the frontend can show form-level blockers separately from packet QA.
4. Normalize issue codes and descriptions so they remain stable for UI filtering and audit logs.
5. Add fixture-based tests for blank PDF field counts so form-edition drift is visible.

### Phase 2: Full I-864 Validation

1. Create `apps/api/app/content/i864_questionnaire.py` with source-dated field metadata.
2. Map sponsor, household, immigrant, income, asset, tax, interpreter, preparer, and signature fields.
3. Add poverty-guideline calculations from source-dated I-864P content. Done for 2025 I-864P table.
4. Validate sponsor household size against the case record. Partially done for minimum household size and threshold lookup.
5. Validate required tax evidence or a no-filing explanation. Done for confirmed tax-return upload or saved explanation.
6. Detect whether a joint sponsor or household member path is being used.
7. Flag missing I-864A when household-member income is used.
8. Add PDF field mappings and template coverage checks.
9. Add tests for income too low, missing tax return, invalid household size, and missing signature workflow.

### Phase 3: I-130 and I-130A

1. Add blank PDFs to `blank-immigration-documents/` if not already present. Done for the current worktree with
   `i-130.pdf` and `i-130a.pdf`; the validator also auto-detects common filename variants.
2. Build source-dated question maps for I-130 and I-130A. Partially done for the simple spouse case and core
   rejection-risk fields.
3. Validate petitioner identity and citizenship facts. Partially done for names and U.S.-citizen simple-case scope.
4. Validate beneficiary identity, address, marriage, and immigration history facts. Partially done for names, birth facts, current address, marriage, and biographic history.
5. Validate first-marriage assumptions and absence of prior spouse sections. Partially done by flagging unconfirmed or non-first-marriage data.
6. Validate adjustment-of-status path is selected instead of consular processing for this simple case. Done for the
   saved/intake simple-case path.
7. Cross-check names, birth dates, marriage date, addresses, and A-number fields against I-485. Partially done for
   shared source-of-truth fields, saved I-485 answers, and extracted uploaded I-130/I-130A values; broader
   document-extraction comparison is still needed.
8. Add explicit I-130/I-130A generated-PDF endpoints once the product needs review drafts for those forms. Done through the shared `/forms/{form_key}/ingestion/generate-pdf` route family for `i130` and `i130a`.

### Phase 4: I-765

1. Build a source-dated I-765 question map from the official USCIS form and instructions. Still needed.
2. Validate category for adjustment-pending employment authorization. Partially done for the expected `(c)(9)` path.
3. Cross-check identity, A-number, I-94, passport, and address fields against I-485. Partially done for saved DB facts and I-485 basis presence.
4. Validate required supporting evidence from the checklist. Done for tracked I-94 and passport biographic page evidence.
5. Add PDF field mappings and blank-template coverage tests. Blank-template coverage is done; explicit fill mapping remains.

### Phase 5: G-1145

1. Add a small source-dated map for name, email, and phone fields. Partially done through the existing USCIS metadata and blank PDF field inspection.
2. Validate e-notification contact info against petitioner or beneficiary preferences. Done for saved name, email, and mobile phone fields.
3. Validate the form is treated as optional/recommended, not required. Done by keeping it outside the default validation scope.
4. Add PDF field mappings and route tests. Route and blank-template tests are done; explicit PDF fill mapping remains.

### Phase 6: I-131

1. Add or refresh the blank I-131 PDF.
2. Build a source-dated I-131 question map.
3. Validate advance parole basis for an adjustment-pending applicant.
4. Validate travel explanation and supporting evidence requirements.
5. Cross-check identity and pending I-485 evidence.
6. Add extra warnings around travel risk and legal-review boundaries.

### Phase 7: Human-Review Workflow

1. Persist validation snapshots when the user intentionally starts final packet review.
2. Store issue resolution notes separately from generated issues.
3. Track which source version and blank PDF hash were used for each snapshot.
4. Allow regenerated validation to show new, resolved, and still-open issues.
5. Keep historical snapshots when USCIS form editions change.

## Blank PDF Regeneration Workflow

For each form:

1. Download the official USCIS PDF.
2. Record URL, verification date, edition date, page count, and file hash.
3. Extract AcroForm field names, field types, page references, and option values.
4. Diff against the previous field manifest.
5. Review changed labels and field names manually.
6. Update the form question map and PDF fill map together.
7. Add or update tests that fail when required mapped fields disappear.

## Testing Strategy

Minimum test coverage by validator:

- service-level missing required field tests
- service-level source-of-truth mismatch tests
- service-level blank template field inspection tests
- route-level request/response tests
- source metadata tests with verification dates
- roadmap response tests for unsupported forms

High-risk tests:

- current address under five years without prior history
- inconsistent names across source-of-truth DB and form answers
- inconsistent marriage dates across forms
- missing sponsor income or tax evidence
- outside-niche filing category
- criminal/removal/fraud/unlawful-entry risk answers

## Data Model Follow-Ups

The current MVP keeps most validation inputs in merged intake and namespaced I-485 answers. Full validation will eventually need first-class or explicitly namespaced records for:

- address history entries
- employment history entries
- sponsor tax evidence
- household members
- joint sponsors
- interpreter/preparer data
- signature confirmation workflow
- form edition and PDF hash snapshots

Until then, validators should report missing model support as roadmap or important issues instead of silently inferring facts.

## Definition of Done for a New Form Validator

A form validator is done when:

- source metadata includes official USCIS URLs and verification date
- the blank PDF field manifest is inspected and tested
- required fields are represented in a question map or rule table
- source-of-truth DB mappings are explicit
- missing required fields produce stable blocking issue codes
- cross-form consistency checks are covered where applicable
- low-confidence extraction or unmapped fill fields are visible
- docs and API spec are updated
- backend tests pass through `npm run test:api`
