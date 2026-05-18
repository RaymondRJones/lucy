# Developer CLI

These commands are for local development and debugging. They read the local SQLite database and local
files in this repository. Do not expose these commands or their outputs as production admin features
until authentication, authorization, secrets handling, and audit controls exist.

## Inspect A Case In The DB

Use the case-inspection CLI when you want to see what Lucy currently knows about a case.

```bash
npm run inspect:case -- --summary
```

The summary uses the most recently created case when `--case-id` is omitted. It prints:

- case ID, name, status, readiness score, and readiness label
- projected `people` rows for petitioner and beneficiary
- high-signal merged intake facts
- missing required intake fields
- counts for checklist items, uploads, QA issues, and audit logs

To inspect a specific case:

```bash
npm run inspect:case -- --case-id 00000000-0000-4000-8000-000000000001 --summary
```

To print the full debug payload:

```bash
npm run inspect:case -- --case-id 00000000-0000-4000-8000-000000000001
```

The full payload includes:

- `case`
- `people`
- `marriage`
- `intake.steps`
- `intake.merged`
- `intake.missing_fields`
- `checklist`
- `uploads` with extracted fields
- `i485_ingestion` with saved questionnaire answers, answer sources, completion, and flags
- `i485_form_fill_preview` with mapped target fields, missing answers, and generation blockers
- `qa_issues`
- recent `audit_logs`

## Inspect A Case Through The API

Start the API first:

```bash
npm run dev:api
```

Then open:

```bash
curl http://127.0.0.1:8000/api/v1/cases/<case-id>/debug
```

For the current imported local case:

```bash
curl http://127.0.0.1:8000/api/v1/cases/00000000-0000-4000-8000-000000000001/debug
```

Use the normal case endpoint when you only need the case summary:

```bash
curl http://127.0.0.1:8000/api/v1/cases/00000000-0000-4000-8000-000000000001
```

## Generate Form G-1450 From Credit-Card JSON

The local G-1450 generator fills the existing PDF template at:

```text
blank-immigration-documents/g-1450.pdf
```

By default it reads:

```text
local-card-info.json
```

and writes one PDF per applicable payable form:

```text
storage/generated/<case-id>-i-130-g-1450.pdf
storage/generated/<case-id>-i-485-g-1450.pdf
storage/generated/<case-id>-i-765-g-1450.pdf
storage/generated/<case-id>-i-131-g-1450.pdf
```

The exact list depends on the generated checklist. For example, I-765 and I-131 are only generated
when those optional forms are applicable to the case.

Lucy now exposes the same backend generator from `/packet-assembly`: load a case ID, choose the
payable forms in the G-1450 modal, enter card details for that request, and open the generated PDFs from
the result list. Case-based generation derives the applicant/petitioner/requestor name from case intake:
I-485, I-765, and I-131 payment forms use the beneficiary; I-130 payment forms use the petitioner. The
signature line is left blank because USCIS states a typewritten name is not an acceptable G-1450 signature
(verified 2026-05-09 at https://www.uscis.gov/sites/default/files/document/forms/g-1450instr.pdf).
The CLI path below remains useful for local debugging or repeatable fixture testing.

Run packet mode with the latest case:

```bash
npm run generate:g1450
```

Run it for a specific case:

```bash
npm run generate:g1450 -- --case-id 00000000-0000-4000-8000-000000000001
```

Choose an output directory:

```bash
npm run generate:g1450 -- --output-dir storage/generated/payments
```

Use a different JSON file:

```bash
npm run generate:g1450 -- --card-json path/to/local-card-info.json
```

Generate one generic G-1450 instead of the full case payment set:

```bash
npm run generate:g1450 -- --single --amount 675.00
```

Choose the output path for single mode:

```bash
npm run generate:g1450 -- --single --output storage/generated/i-485-g-1450.pdf
```

## Generate A Draft Form I-485 PDF

The local I-485 generator fills the editable template at:

```text
blank-immigration-documents/i-485.pdf
```

It writes the generated review draft to:

```text
storage/generated/<case-id>-i-485.pdf
```

Run it for the latest case:

```bash
npm run generate:i485
```

Run it for a specific case:

```bash
npm run generate:i485 -- --case-id 00000000-0000-4000-8000-000000000001
```

Generate from built-in safe sample questionnaire answers without changing a database case:

```bash
npm run generate:i485 -- --sample --require-ready --output storage/generated/sample-i-485.pdf
```

Create a separate local case with the complete safe sample questionnaire loaded into Lucy:

```bash
npm run seed:i485-sample -- --web-base-url http://localhost:3002
```

Also generate a draft PDF for that sample case:

```bash
npm run seed:i485-sample -- --generate-pdf --web-base-url http://localhost:3002
```

When `--case-id` is provided, the seeder refuses to replace existing I-485 answers unless `--overwrite`
is also provided.

Choose a different output path:

```bash
npm run generate:i485 -- --output storage/generated/i-485-review-draft.pdf
```

By default this command will generate an incomplete review draft and report missing/unmapped fields.
Use `--require-ready` to fail unless the fill preview is fully ready for PDF generation.

## Seed Packet Assembly Scenarios

Create several local packet-assembly test cases with one-page placeholder PDF uploads and generated full packets:

```bash
npm run seed:packet-scenarios
```

The seeded profiles cover:

- California full packet with I-765, I-131, and translation evidence
- Texas packet with I-765 but no I-131, using the private-carrier lockbox address
- Georgia core adjustment packet with no optional I-765/I-131
- Arizona travel-document path with a prior-marriage termination record

By default the command also runs packet assembly for every case and prints each packet URL, output PDF,
page count, included/skipped counts, and USCIS lockbox result. To create the cases without generating
the merged packets:

Seeded upload PDFs are intentionally marked in the center with their packet section, checklist category,
and `PLACEHOLDER` text so final packet previews do not contain visually blank evidence pages.

```bash
npm run seed:packet-scenarios -- --no-generate-packets
```

## Credit-Card JSON Shape

The generator expects this shape:

```json
{
  "form": "G-1450",
  "cardholder_name": "Jane Q. Example",
  "credit_card_type": "Visa",
  "credit_card_number": "4111111111111111",
  "expiration_month": "08",
  "expiration_year": "2028",
  "security_code": "123",
  "billing_address": {
    "street_1": "123 Example St",
    "street_2": "Apt 4B",
    "city": "Los Angeles",
    "state": "CA",
    "postal_code": "90001",
    "country": "USA"
  },
  "daytime_phone_number": "0000000123",
  "authorized_amount": "675.00",
  "applicant_name": "Jane Q. Example",
  "payer_relationship": "Self",
  "date_signed": "2026-04-28"
}
```

Supported `credit_card_type` values:

- `Visa`
- `Mastercard`
- `American Express`
- `Discover`

## Important Limitations

- Packet mode calculates amounts from the local fee table in `apps/api/app/content/fee_schedule.py`.
- The current local fee rows were verified against official USCIS Form G-1055, Fee Schedule, edition
  `04/23/26`, on `2026-04-28`.
- Before mailing, re-confirm the current USCIS fee schedule or fee calculator for every form.
- USCIS warns against combining multiple form fees into one payment when separate payments are
  required. Generate separate G-1450s when the final packet strategy calls for separate payments.
- Review and sign the generated PDF before mailing. This tool is a local preparation aid, not a legal
  or filing guarantee.

## Local Fee Rows Used By Packet Mode

These rows are intentionally centralized so filing amounts are not duplicated around Lucy.

- `I-130`: `$675.00`, general paper filing.
- `I-485`: `$1,440.00`, general paper filing for an applicant over age 14.
- `I-765`: `$260.00`, paper filing with a paid Form I-485 filed on or after April 1, 2024 and pending.
- `I-131`: `$630.00`, paper-filed advance parole document for individuals inside the United States with pending Form I-485.
- `I-130A`, `I-864`, `I-693`, and `G-1145`: tracked as `$0.00`, so packet mode reports them as skipped rather than generating payment forms.
