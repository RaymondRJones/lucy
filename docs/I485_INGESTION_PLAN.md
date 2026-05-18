# I-485 Ingestion Microservice Design Plan

Verified on: 2026-05-05

Sources:

- USCIS Form I-485 page: https://www.uscis.gov/i-485
- USCIS Form I-485 PDF: https://www.uscis.gov/sites/default/files/document/forms/i-485.pdf
- USCIS Form I-485 Instructions PDF: https://www.uscis.gov/sites/default/files/document/forms/i-485instr.pdf
- Local reference PDF: `MARRIAGE_EVIDENCE/I-485/Sample-Form-I-485.pdf`

The USCIS page listed Form I-485 edition `01/20/25` and provided the current form and instructions download links when checked. The local I-485 PDF is flattened, so its text is useful for extraction heuristics but not as a reliable fillable-field schema.

## Product Boundary

Build the I-485 workflow as an isolated questionnaire and ingestion surface inside the existing case workspace. It is not legal advice and should not decide eligibility. It should collect answers, map explainable facts into the local case DB, flag answers outside the intended first-marriage U.S.-citizen-spouse niche, and preserve source traceability for every mapped field.

Target profile:

- beneficiary is in the United States
- last entry was inspected/admitted or paroled
- current filing category is spouse of a U.S. citizen
- applicant is the principal applicant
- applicant is married once, to the U.S. citizen spouse
- no criminal, removal, fraud, unlawful-entry, trafficking, security, or other inadmissibility trigger is reported
- Form I-864 is expected rather than an exemption

## 14 Questionnaire Pages

1. Identity, A-Number, and names
2. Birth, citizenship, and travel document
3. Last arrival and I-94
4. Addresses and Social Security
5. Filing category and niche gate
6. Affidavit of Support, prior applications, and work/school
7. Parents
8. Marital history and U.S. citizen spouse
9. Children and biographic information
10. Organizations and immigration history
11. Criminal acts and controlled substances
12. Security, weapons, military, and human rights
13. Public charge household snapshot
14. Illegal entries, miscellaneous conduct, and signature workflow

The canonical page/question map now lives in `apps/api/app/content/i485_questionnaire.py`. Each question includes a stable question ID, answer type, PDF reference, required flag, optional intake DB mapping, ideal answer, risk rule, and official-source-backed plain-English tooltip guidance.

## Architecture

The backend owns the workflow truth. The I-485 microservice stores answers as namespaced `intake_responses` using step keys like `i485_ingestion:page_08_marriage_spouse`, then writes a separate `i485_projection` intake step for facts that already map into the MVP data model.

Current API surface:

- `GET /api/v1/content/i485-questionnaire`
- `GET /api/v1/cases/{case_id}/i485-ingestion`
- `POST /api/v1/cases/{case_id}/i485-ingestion/page`
- `POST /api/v1/cases/{case_id}/i485-ingestion/import-from-upload`
- `GET /api/v1/cases/{case_id}/i485-ingestion/form-fill-preview`

The first endpoint returns the versioned 14-page questionnaire and source metadata. The case endpoints return merged I-485 answers, completion, page summaries, mapped fields, flags, and a normalized fill preview payload.

## Ingestion Pipeline

1. Load the current official blank I-485 PDF from USCIS into a controlled source cache with verification date and hash.
2. Extract page text, form edition, page count, visible labels, checkbox groups, and approximate coordinates.
3. Compare extracted labels against the canonical questionnaire IDs. Store unmapped labels as review tasks rather than guessing.
4. For uploaded filled PDFs, extract text and visible answers. If AcroForm fields exist, prefer field values; otherwise use page-token extraction with confidence scores.
5. Convert extracted values into proposed answers, never silently overwriting user-confirmed answers.
6. Save accepted answers in the I-485 namespace, project explainable facts into `i485_projection`, regenerate checklist/QA, and audit the action.
7. Emit flags for dangerous or outside-niche answers before generating final form-fill payloads.

The MVP import endpoint now pulls answer proposals from the latest confirmed `form_i485` upload and preserves existing answers by default. Imported answers store `answer_sources` with upload ID, filename, extracted field name, confidence, and timestamp so every automated value can be traced back to the PDF.

The MVP fill-preview endpoint is the regeneration contract. It does not produce a final USCIS PDF yet; it returns target keys, values, sources, missing required questions, low-confidence extracted values, and blockers that must be resolved before a PDF generator should run.

## Flagging Model

Flags have two categories:

- `outside_niche`: not necessarily dangerous, but not the intended simple marriage case.
- `risk`: potentially serious facts such as criminal history, immigration fraud, unlawful entry, removal history, trafficking, security, or human-rights issues.

Blocking risk flags should prevent Lucy from presenting the case as standard-ready. Lucy can still organize documents, but the UI should say professional legal review is needed.

## Regeneration Strategy

The canonical questionnaire should be regenerated only from official USCIS PDFs, not from third-party questionnaire pages. A scraper may be useful for competitive analysis, but production question IDs and legal references should come from USCIS materials with verification dates.

Regeneration should produce:

- PDF edition and source hash
- page-level question candidates
- label diffs against the current canonical map
- changed/added/removed question report
- migration suggestions for persisted answer IDs
- test fixtures for known local PDFs

No regenerated question map should replace production content without human review, because small wording changes can alter legal meaning.

## Edge Cases

- flattened PDFs with no field objects
- scans requiring OCR
- mixed old/new edition pages
- missing page numbers or hidden footer edition dates
- multiple names, aliases, or DOBs
- current address less than five years old
- no I-94, parole, crewman, or entry without inspection
- J-1 two-year residence requirement
- prior denials, removal, voluntary departure, or rescission
- arrests with sealed/expunged records
- public charge benefit/institutionalization details
- interpreter/preparer signatures
- Part 14 continuation sheets
