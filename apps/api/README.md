# Lucy API

FastAPI backend for Lucy, the local marriage-based I-485 packet workflow.

## Run

```bash
python3.13 -m venv .venv313
source .venv313/bin/activate
python3.13 -m pip --python .venv313/bin/python install -e .[dev]
uvicorn app.main:app --reload --port 8000
```

## Main capabilities

- case creation and collaboration invites
- intake step persistence and normalization
- personalized checklist generation
- local upload metadata and binary storage
- packet QA and readiness scoring
- country guidance and explanation content

## Evidence ingestion command

```bash
cd /path/to/lucy
./.venv313/bin/python -m app.cli.ingest_evidence --path MARRIAGE_EVIDENCE
```

Optional flags:

- `--case-id <uuid>` to update an existing case
- `--case-name "Sample marriage packet"` to set the name for a newly created case
- `--web-base-url http://localhost:3000` to customize the printed UI link
