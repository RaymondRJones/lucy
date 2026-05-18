# Data Model

## Persisted tables

### `cases`

- packet workspace shell
- stores top-level status, readiness score, and focus country

### `people`

- one row per case participant
- current roles: `petitioner`, `beneficiary`

### `marriages`

- relationship-level facts
- marriage date, first marriage confirmation, children flag, household size

### `intake_responses`

- versionable step payloads
- merged at runtime into one normalized intake state
- stores expanded factual profile data such as identity, contact details, immigration identifiers,
  address history, employment notes, filing choices, evidence signals, and risk flags
- stores happy-path prescreen answers and branch projections under the `prescreen` step key, including
  `i130_filing_status` for choosing I-130/I-130A preparation versus receipt/approval evidence
- prescreen projection can map grouped answers into stable intake fields, such as I-94 details,
  core identity details, current-address details, I-94/passport details, marriage date/place details,
  sponsor income/household-size facts, public-charge readiness facts, evidence categories, and review flags
- stores isolated I-485 questionnaire page answers under `i485_ingestion:*` step keys and their explicit
  case-field projection under `i485_projection`
- stores isolated I-130, I-130A, I-765, I-131, and I-864 questionnaire page answers under `form_ingestion:{form_key}:*`
  step keys and their explicit case-field projection under `{form_key}_projection`
- enriches merged intake with direct smart-default aliases so small wording differences across prescreen,
  I-485, I-130, I-130A, I-765, and I-131 reuse the same reviewed facts without duplicating workflow rules in the UI
- stores I-485 per-answer provenance in each page payload's `answer_sources` map when answers are pulled
  from an uploaded PDF or entered manually
- excludes raw `i485_ingestion:*` and `form_ingestion:*` page payloads from the normal merged intake state so only reviewed projection fields affect checklist and QA behavior
- remains the source for facts that do not yet have first-class relational columns

### `case_checklist_items`

- generated from rules templates
- stores applicability, completion state, ownership, explanations, and metadata

### `uploaded_documents`

- upload metadata and local storage references
- tracks language, translation requirement, review status, OCR placeholder fields, and version

### `qa_issues`

- generated issue list with severity and checklist linkage

### `invitations`

- spouse or collaborator invitation records

### `audit_logs`

- critical action trail for case changes, uploads, and checklist operations

## Derived relationships

- one case has two primary participant rows
- one case has one marriage row
- one case has many intake steps
- one case has many checklist items
- one case has many uploads
- one case has many QA issues

## Local persistence strategy

- SQLite for local development
- SQLModel models structured so PostgreSQL can be introduced later with minimal route-level changes
