# Lucy

Lucy is a free, open-source, locally run workspace for preparing a happy-path marriage-based Form I-485
packet. It is built for the narrow MVP scenario: a U.S. citizen spouse, a foreign spouse residing in the
United States, and a straightforward spouse adjustment packet that can be assembled, reviewed, printed,
and mailed from your own computer.

Phase 1 is focused on:

- intake and case setup
- personalized checklist generation
- document upload tracking
- packet QA and readiness scoring
- country-specific guidance

The project follows the product direction in [REQUIREMENTS.md](REQUIREMENTS.md) and is organized as a lightweight monorepo:

```text
apps/
  api/    FastAPI rules and case-management service
  web/    Next.js frontend for intake, uploads, and packet review
docs/
  API_SPEC.md
  DATA_MODEL.md
  RULES_ENGINE.md
storage/
  uploads/   local development file storage
```

## Important product note

Lucy is an organizational tool, not legal advice. It helps collect factual answers, organize local files,
generate draft forms, assemble a printable packet, and flag unusual answers for review. The fee table and
form edition content are source-backed where implemented, but users must still review all forms, signatures,
dates, fees, and USCIS instructions before mailing.

## Local development

### API

```bash
cd /path/to/lucy
python3.13 -m venv .venv313
source .venv313/bin/activate
python3.13 -m pip --python .venv313/bin/python install -e .[dev]
npm run dev:api
```

### Web

```bash
cd /path/to/lucy
npm install
npm run dev:web
```

Set `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` in `apps/web/.env.local` when running the UI locally.

### Local Wi-Fi / LAN sharing

For short-lived local testing with other people on the same Wi-Fi network, run the explicit LAN mode:

```bash
npm run dev:lan
```

The command detects your LAN IPv4 address, starts the API on `0.0.0.0:8000`, starts the web app on
`0.0.0.0:3000`, points the frontend at the API on the same host name used in the browser, and opens
CORS only for the LAN web origins plus localhost. It prints a friendly `.local` URL when your machine
advertises one, plus a numeric fallback:

```text
http://your-computer.local:3000
http://192.168.1.23:3000
```

Stop any existing `npm run dev:api` / `npm run dev:web` processes before using LAN mode, or provide
alternate ports:

```bash
npm run dev:lan -- --web-port 3001 --api-port 8001
```

If automatic IP detection chooses the wrong network interface, pass it directly:

```bash
npm run dev:lan -- --host 192.168.1.23
```

If the friendly `.local` name is awkward, override the printed/share name:

```bash
npm run dev:lan -- --name your-computer.local
```

The `.local` name depends on Bonjour/mDNS support on the other device. Apple devices usually handle
it automatically; the numeric fallback works when name lookup does not.

Only use LAN mode on a trusted network. Anyone who can reach the shared URL while it is running may
be able to view or edit local case data in `storage/app.db` and uploaded/generated files.

## Import existing evidence

If you already have a local packet folder, ingest it into the case workspace:

```bash
cd /path/to/lucy
npm run ingest:evidence
```

The command will:

- scan the `MARRIAGE_EVIDENCE` directory
- create or update a case
- import documents into the upload registry
- extract key facts from supported USCIS forms
- seed the I-485 ingestion questionnaire from a detected uploaded Form I-485
- generate the checklist
- run QA and readiness scoring

At the end it prints a case URL such as `http://localhost:3000/?caseId=...` so the imported case opens directly in the UI.

## Inspect local case data

For development/debugging, inspect the latest case or a specific case from the local SQLite database:

```bash
npm run inspect:case -- --summary
npm run inspect:case -- --case-id <case-id>
```

The full output includes saved intake steps, merged intake, projected people/marriage facts, checklist
items, uploads with extracted fields, QA issues, and recent audit logs.

The `/review` page links into checklist-backed G-1450 payment PDF generation and packet assembly. The
`/packet-assembly` page can also generate those payment PDFs during full packet assembly or include a
confirmed uploaded `payment_g1450` PDF when the filer brings their own signed Form G-1450. The same
generator is still available as a local JSON-based debugging command documented in
[docs/DEVELOPER_CLI.md](docs/DEVELOPER_CLI.md).

## What is implemented

- FastAPI service with case, intake, checklist, upload, QA, and content endpoints
- SQLite-backed local persistence using SQLModel
- rules engine for a standard marriage-based concurrent filing flow
- simple `/` start/resume page, `/prescreen` guided branching workspace, `/ingestion` compatibility route, and `/review` checklist/review handoff
- Next.js guided ingestion workspace, aligned to `branching-logic.md`, that branches the happy-path case,
  supports grouped answer blocks and smart defaults, eliminates non-applicable questions/forms, and flags unusual answers for review
- Next.js dashboard for expanded intake, checklist generation, uploads, QA, and Colombia guidance
- isolated `/i485-ingestion` page backed by a source-dated 14-page I-485 questionnaire map, PDF answer import, fill preview, and risk/outside-niche flagging
- stored YouTube teaching transcripts in `docs/youtube-transcripts/` for future plain-language form guidance reference
- isolated `/form-ingestion?form=i130`, `/form-ingestion?form=i130a`, `/form-ingestion?form=i765`, `/form-ingestion?form=i131`, and `/form-ingestion?form=i864` pages backed by source-dated question maps, fill previews, local PDF draft generation, and generated-PDF open links
- public explainer, workflow, pricing, and legal-boundary pages
- backend tests for checklist and QA logic
