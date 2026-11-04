# API Spec

## Base URL

- Local API: `http://localhost:8000`
- Prefix: `/api/v1`

## Core routes

### Case management

- `POST /cases`
  - create a new packet workspace
- `GET /cases/{case_id}`
  - fetch case summary, participants, marriage snapshot, and counts
- `PATCH /cases/{case_id}`
  - update case-level metadata
- `POST /cases/{case_id}/invite`
  - create a collaborator invitation record

### Intake

- `POST /cases/{case_id}/intake/step`
  - save or replace one intake step payload
- `GET /cases/{case_id}/intake`
  - return step history plus merged intake state
- `POST /cases/{case_id}/intake/submit`
  - validate required intake fields and generate the checklist

### Guided prescreen

- `GET /content/prescreen`
  - return the source-dated happy-path prescreen question map, including USCIS source metadata verified on `2026-05-01`
  - question entries can be single-answer controls, multi-select screens, or `field_group` blocks with per-field mappings for larger intake moments such as entry details and sponsor support
  - the MVP question map follows `branching-logic.md` for the spouse-of-U.S.-citizen path: case basis, physical presence, entry type, current status, I-130 branch, identity, address, marriage, evidence, financial support, medical exam, and high-risk review screens
- `GET /cases/{case_id}/prescreen`
  - return saved prescreen answers, answer-source hints for smart defaults, visible questions, eliminated questions, happy-path flags, included form branches, and eliminated form branches
- `POST /cases/{case_id}/prescreen`
  - save prescreen answers into the isolated `prescreen` intake step, project explainable branch facts into merged intake, and recalculate the branch response
  - if the case already has a checklist, rebuild it so changed answers add or drop items; item completion statuses are kept. The I-485 and supplemental form page saves do the same
  - the I-130 branch keeps Forms I-130 and I-130A active when `i130_filing_status` is `not_filed`; if the petition is already `pending` or `approved`, it eliminates those draft forms and asks for receipt or approval evidence, filing date, or approval date instead
  - if the I-130 answer is denied/revoked/withdrawn or another critical happy-path gate is triggered, the response marks the branch as `blocked_needs_review` and pauses generated form actions
  - entry-type flags distinguish normal visa admission from ESTA/VWP or parole review warnings and entered-without-inspection blockers

### I-485 ingestion questionnaire

- `GET /content/i485-questionnaire`
  - return the source-backed, versioned 14-page I-485 question map, including PDF references, DB mapping metadata,
    and plain-language help fields backed by official USCIS Form I-485 source metadata verified on `2026-10-30`
- `GET /cases/{case_id}/i485-ingestion`
  - return saved I-485 page answers, completion summaries, mapped fields, and risk/outside-niche flags
- `POST /cases/{case_id}/i485-ingestion/page`
  - save one I-485 questionnaire page and update the isolated `i485_projection` intake step for explainable case-field mappings
- `POST /cases/{case_id}/i485-ingestion/import-from-case`
  - pull reviewable I-485 answer proposals from confirmed case intake facts, preserve existing user-entered answers by default, and update mapped projection fields
- `POST /cases/{case_id}/i485-ingestion/import-from-upload`
  - pull reviewable answer proposals from the latest confirmed I-485 upload, preserve existing user-entered answers by default, and update mapped projection fields
- `GET /cases/{case_id}/i485-ingestion/form-fill-preview`
  - return the normalized I-485 target payload, missing required answers, risk blockers, outside-niche blockers, low-confidence PDF fields, and generation status for a future PDF fill step
- `POST /cases/{case_id}/i485-ingestion/generate-pdf`
  - write a local review-draft I-485 PDF from saved questionnaire answers using `blank-immigration-documents/i-485.pdf` by default and return the generated path plus mapped/unmapped field counts
- `GET /cases/{case_id}/generated-pdfs/{filename}`
  - download a generated local PDF for that case from `storage/generated/`; filenames must be case-prefixed and remain inside the generated output directory

### Supplemental form ingestion questionnaires

- `GET /content/forms/{form_key}/questionnaire`
  - return the source-dated question map for supported supplemental forms; currently `i130`, `i130a`, `i765`, `i131`, and `i864`
  - supported maps include non-authoritative `plain_language`, `deep_explanation`, and `teaching_source` help fields
  - I-130 and I-130A maps use official USCIS source metadata rather than transcript-backed teaching notes
- `GET /cases/{case_id}/forms/{form_key}/ingestion`
  - return saved page answers, completion summaries, mapped fields, and risk/outside-niche flags for that form
- `POST /cases/{case_id}/forms/{form_key}/ingestion/page`
  - save one supplemental form questionnaire page and update the isolated `{form_key}_projection` intake step for explainable case-field mappings
- `POST /cases/{case_id}/forms/{form_key}/ingestion/import-from-case`
  - pull reviewable answers from the merged case intake and prior form projections, preserving existing user-entered supplemental form answers by default
- `GET /cases/{case_id}/forms/{form_key}/ingestion/form-fill-preview`
  - return the normalized target payload, missing required answers, blockers, low-confidence fields, and generation status for the selected form
- `POST /cases/{case_id}/forms/{form_key}/ingestion/generate-pdf`
  - write a local review-draft PDF using the matching template from `blank-immigration-documents/` by default and return generated path, download URL, and mapped/unmapped field counts

### Packet assembly

- `POST /cases/{case_id}/packet-assembly/generate`
  - generate available form review-draft PDFs, merge them with confirmed uploaded PDFs, write `storage/generated/{case_id}-full-packet.pdf`, and save `storage/generated/{case_id}-full-packet-manifest.json`
  - form fields are flattened into the packet's pages so answers and barcodes print in every PDF viewer, which makes the packet non-editable; generate standalone form PDFs for editing
  - request body:
    - `state_code`: optional U.S. state or territory code used for family-based USCIS lockbox routing
    - `carrier`: `usps` or `private`; private maps to FedEx/UPS/DHL delivery addresses
    - `include_upload_ids`: optional upload ID allowlist; omitted means all confirmed case uploads are considered
    - `include_supporting_evidence`: defaults to `true`; when `false`, uploaded supporting evidence PDFs are excluded so the output can be used as a forms/payment-only print draft
    - `include_generated_forms`: defaults to `true`
    - `allow_incomplete`: defaults to `true` so draft form PDFs can be generated for review
    - `g1450_payment`: optional one-request card payload for generating I-485 packet payment PDFs during assembly; card details are not saved
    - `g1650_payment`: optional one-request bank payload that generates Form G-1650 payment PDFs instead; a request with both `g1450_payment` and `g1650_payment` is rejected
    - `g1450_selected_checklist_codes`: optional payment checklist-code allowlist for the I-485 packet payment set
  - generated packet PDFs follow scanner-friendly USCIS mail guidance: I-485-centered payment PDFs appear first when available or generated, then the generated cover letter/table of contents, then G-1145, the I-485 section, the I-864 section, the I-693 medical section, I-765 when applicable, and I-131 when applicable; I-130 and I-130A can now be prepared as review-draft PDFs through form ingestion, but this packet compiler remains I-485-centered and does not yet merge those petition drafts into the assembly output
  - generated packets add plain letter-size section index pages for major form/evidence segments such as I-485, I-864, I-765, and I-131, rather than relying on physical tabs, binders, folders, sticky notes, or other scanner-hostile separators
  - when `i130_filing_status` is `not_filed`, the packet also includes an I-130 section and the `form_i130` payment
  - payment PDF inclusion is limited to the I-485 packet payment set (`form_i485`, `form_i765`, and `form_i131` when applicable/payable, plus `form_i130` for a concurrent filing); G-1450 payment PDFs are generated only when fresh card details are included in the packet assembly request, and a confirmed uploaded `payment_g1450` PDF is accepted as the Payment section when the user brings their own signed Form G-1450; stale previously generated payment PDFs are not auto-merged
  - uploaded files are merged only when they are confirmed, part of the I-485 packet document order from `i-485-complete-package-req.md`, stored as PDFs, and readable by `pypdf` or the local PDF normalization fallback; when generated forms are included, uploaded copies of generated forms such as I-485/I-864/I-765/I-131/G-1145 are skipped to avoid duplicate forms; shared identity/I-94/photo uploads are included once in the packet rather than repeated under I-765/I-131; unreadable, non-PDF, incomplete, unmapped, and I-130/I-130A petition uploads are returned in `skipped_documents`
  - response includes the PDF download URL, manifest JSON download URL, total page count, included/skipped document lists, warnings, and a mailing recommendation when `state_code` matches the USCIS family-based lockbox chart
  - manifest JSON includes generated date, selected location/carrier, total pages, included/skipped document metadata, warnings, mailing recommendation, USCIS lockbox source last-reviewed date, scanner-friendly printing guidance, app verification date, and USCIS mail-assembly guidance sources verified on `2026-05-09`
  - mailing-address content is sourced from the USCIS Lockbox Filing Locations Chart for Certain Family-Based Forms, last reviewed by USCIS on `2024-10-11` and app-verified on `2026-04-30`
- `GET /cases/{case_id}/packet-assembly/manifests/{filename}`
  - download a generated packet manifest JSON for that case from `storage/generated/`; filenames must be case-prefixed and remain inside the generated output directory

### Checklist

- `POST /cases/{case_id}/checklist/generate`
  - regenerate the checklist from current intake
- `GET /cases/{case_id}/checklist`
  - list case checklist items and derived facts
- `PATCH /checklist-items/{item_id}`
  - update manual completion status

### Uploads

- `POST /cases/{case_id}/uploads/request`
  - create upload metadata and return a local upload URL
- `POST /uploads/{upload_id}/binary`
  - send the PDF/JPG/JPEG/PNG file; the local MVP default limit is `100 MB` per file
- `POST /uploads/{upload_id}/confirm`
  - finalize metadata such as language, translation flag, and document type
- `GET /cases/{case_id}/uploads`
  - list uploaded files
- `DELETE /uploads/{upload_id}`
  - remove upload metadata and local binary file

### QA

- `POST /cases/{case_id}/qa/run`
  - run the packet completeness and cross-document consistency check
- `GET /cases/{case_id}/qa`
  - fetch existing issues and readiness summary, including source-backed mismatch findings
- `GET /cases/{case_id}/readiness`
  - fetch readiness summary only

### Filing validation

- `POST /cases/{case_id}/filing-validation`
  - validate source-of-truth DB records and saved form-questionnaire answers for filing readiness
  - request body is optional; by default validates `form_i485` and a sponsor preflight for `form_i864`
  - `form_i130` and `form_i130a` can be requested explicitly for partial relationship-petition and spouse-biographic validation
  - `form_i765` can be requested explicitly for partial adjustment-pending `(c)(9)` employment authorization validation
  - `form_i131` can be requested explicitly for partial pending-I-485 advance parole validation, including tracked photo-ID, I-94/status, passport-photo, travel-explanation, and I-485-basis evidence checks
  - `form_g1145` can be requested explicitly for optional e-notification contact validation
  - optional `form_codes` narrows or expands the requested form list
  - optional `template_paths` maps form codes to blank local PDFs for PDF field-name coverage checks
  - default I-130/I-130A template paths are auto-detected from `blank-immigration-documents/` when present
  - response includes per-form issue counts, missing required field alerts, source metadata with verification dates,
    blank-PDF template coverage, source-dated I-130/I-130A core question-map versions, first-pass I-130/I-130A
    PDF fill-payload metadata, cross-form and uploaded-form extraction mismatch findings, assumptions, and a
    roadmap for validators that are planned but not implemented yet
- `GET /content/filing-validation`
  - return validator capabilities, default validation scope, supported form codes, per-form implementation status,
    source metadata, default blank PDF paths, detected blank-PDF field counts, page counts, and file hashes

### Payment form generation

- `GET /cases/{case_id}/g1450/payment-options`
  - return applicable checklist-backed Form G-1450 payment options, including paper-fee amount, source URL,
    source edition, verification date, whether the fee is payable, and whether the local G-1450 template exists
- `POST /cases/{case_id}/g1650/generate`
  - generate one local Form G-1650 PDF for each selected applicable payable checklist form using one-request bank
    details (`account_ownership`, `account_type`, `account_holder_name`, `business_name`, `bank_name`, `routing_number`,
    `account_number`). Amounts are whole dollars because the form preprints `.00`, the signature stays blank, and
    invalid routing numbers return 400. Bank details are not stored in case records or audit logs, but they are printed
    on the generated PDFs in `storage/generated/`. Source verified 2026-10-30: https://www.uscis.gov/g-1650
- `POST /cases/{case_id}/g1450/generate`
  - generate one local Form G-1450 PDF for each selected applicable payable checklist form using a one-request
    credit-card payload rather than a saved JSON file
  - applicant/petitioner/requestor name is derived from case intake per payment form: I-485, I-765, and I-131
    use the beneficiary; I-130 uses the petitioner; the signature line is left blank for the required signature
    before mailing, based on USCIS G-1450 instructions verified on 2026-05-09 at
    https://www.uscis.gov/sites/default/files/document/forms/g-1450instr.pdf
  - optional `selected_checklist_codes` narrows generation to selected payment forms; omitted means all applicable
    payment forms from the generated checklist
  - card payload is not stored as an intake step or upload; audit logging records only selected form codes,
    generated/skipped counts, and total authorized amount
  - response includes generated PDF paths, local download URLs, skipped zero-fee forms, total authorized amount,
    and the source-dated payment note

### Developer inspection

- `GET /cases/{case_id}/debug`
  - local-development case snapshot with case metadata, people, marriage, intake steps, merged intake,
    checklist items, uploads and extracted fields, I-485 ingestion state, I-485 fill preview, QA issues,
    and recent audit logs

### Content

- `GET /content/countries/{country_code}`
  - country-specific civil document guidance
- `GET /content/explanations`
  - disclaimers, severity help, and escalation guidance
- `GET /content/uscis-requirements`
  - USCIS-source-backed form metadata, accepted editions, official links, and tracked per-form initial-evidence requirements
- `GET /content/fees`
  - seeded fee-reference payload
- `GET /content/form-editions`
  - seeded form-edition payload

## Notes

- The upload workflow intentionally mimics a future signed-URL architecture while staying local for MVP development.
- Upload metadata may satisfy more than one checklist code when one document legitimately covers multiple requirements, such as a combined `I-130`/`I-130A` packet or a translated civil record that also satisfies translation certification.
- The QA layer now cross-references extracted fields from core uploads, prioritizing authoritative forms by field so shared facts such as names, marriage dates, status details, and current addresses can be compared across the packet.
- QA also compares selected saved intake facts against uploaded document fields and flags likely incomplete five-year address history when a recent current-address start date is present without prior address history.
- The frontend now combines `/cases/{case_id}/checklist`, `/cases/{case_id}/uploads`, and `/content/uscis-requirements` to render form-by-form packet milestones.
- Fee and form-edition endpoints are seed content only and should be wired to admin-maintained official references before production use.
- I-485 ingestion answers are stored as namespaced intake steps rather than first-class tables in the MVP. The projection step maps fields with explicit question-level `db_path` metadata and enriches equivalent field-name variants for smart defaults, such as current-address city/state/ZIP, arrival place/city/state, SSN, and biographic fields.
- I-485 question maps include `plain_language`, `deep_explanation`, and `teaching_source` metadata for UI help. The helper copy is a plain-English explanation tied to official USCIS Form I-485 sources, and it does not replace applicant review of the current USCIS instructions.
- I-485 repeatable sections such as prior addresses and five-year employment/school/unemployment history are returned with structured `entry_fields`, `form_entry_limit`, and Part 14 overflow metadata so the UI can collect reviewable entries instead of freeform text blobs.
- I-485 PDF imports store answer provenance per question so extracted values can be reviewed before relying on them for form-fill behavior.
- I-485 PDF generation writes local review drafts to `storage/generated/`; incomplete or unmapped answers remain review warnings and should not be treated as filing-ready output.
- Filing validation is non-persistent in the MVP: it reads current DB records, source-dated content, saved I-485 answers,
  and blank PDF field names, then returns structured issues without replacing the packet QA readiness score.
- I-765, I-131, and I-864 supplemental ingestion reuse the isolated-answer pattern and write local review drafts to `storage/generated/` from editable templates in `blank-immigration-documents/`.
- I-130 and I-130A now use the same supplemental ingestion route family when the prescreen says the spouse petition has not been filed yet.
- G-1450 generation can be run from the UI or local CLI. The UI path sends card details for the generation request only and reuses the same backend fee/checklist logic as the JSON-based CLI path.
