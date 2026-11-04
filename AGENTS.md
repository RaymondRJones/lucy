# AGENTS.md

## Purpose

This repository is a lightweight monorepo for a marriage-based green card packet workspace.

- Product direction lives in `REQUIREMENTS.md`.
- Day-to-day setup and MVP usage live in `README.md`.
- The app is an organizational tool, not legal advice.
- Any USCIS-facing requirement, fee, or form-edition claim must be source-backed and date-stamped.

Start by reading:

1. `REQUIREMENTS.md`
2. `README.md`
3. `docs/API_SPEC.md`
4. `docs/DATA_MODEL.md`
5. `docs/RULES_ENGINE.md`

## Stack

- `apps/api`: FastAPI + SQLModel + SQLite + Pydantic settings + `pypdf`
- `apps/web`: Next.js App Router + React + TypeScript + Tailwind CSS
- Local persistence: `storage/app.db`
- Local uploaded files: `storage/uploads/`
- Source evidence folder: `MARRIAGE_EVIDENCE/`

## How To Run The Project

Preferred root-level commands:

```bash
npm run dev:api
npm run dev:web
```

Expected local UI/API URLs:

- Web: `http://localhost:3000`
- API: `http://localhost:8000`

Frontend environment:

- Set `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` in `apps/web/.env.local`

Evidence ingestion:

```bash
npm run ingest:evidence
```

That command ingests the `MARRIAGE_EVIDENCE/` folder into the local case workspace, extracts supported form data, updates checklist state, and recalculates readiness.

## Test, Lint, And Typecheck Commands

Run the smallest relevant set for the files you changed. For broad or risky changes, run all of them.

```bash
npm run test:api
npm run lint:api
npm run lint:web
npm run typecheck:web
npm run build:web
```

Notes:

- `npm run lint:api` runs Ruff. CI (`.github/workflows/ci.yml`) runs all of these on every pull request, plus a dependency audit.
- `npm run check:uscis` compares stored editions, fee and address review dates, the family-based lockbox table, and blank templates with live USCIS pages. `.github/workflows/uscis-updates.yml` runs it daily and opens an issue on any difference.
- `apps/api/tests/test_print_output.py` renders generated forms at print resolution and decodes every PDF417 barcode. Run it after changing PDF generation or replacing a template.
- Tests write to a temporary directory set up in `apps/api/tests/conftest.py`, never to `storage/`.
- After changing Python dependencies in `apps/api/pyproject.toml`, regenerate `apps/api/requirements-dev.lock` with `uv pip compile apps/api/pyproject.toml --extra dev --universal --python-version 3.13 --no-header --no-annotate -o apps/api/requirements-dev.lock`.
- `npm run build:web` is the main confidence check for frontend integration issues.
- If you change ingestion, checklist, QA, or USCIS content behavior, run `npm run test:api`.

## Coding Conventions

### General

- Prefer small, direct changes that extend the current MVP instead of introducing new abstraction layers.
- Keep code ASCII unless a file already needs Unicode.
- Add comments only when the logic is non-obvious.
- Do not hardcode legal/process truths in multiple places.

### Python / API

- Keep FastAPI route handlers thin.
- Put business rules, case logic, ingestion logic, and readiness logic in `apps/api/app/services/`.
- Put static source-backed reference content in `apps/api/app/content/`.
- Use schemas from `apps/api/app/schemas/common.py` for request/response boundaries.
- Use SQLModel patterns already present in the repo instead of inventing a second persistence style.

### TypeScript / Web

- Reuse the shared API wrapper in `apps/web/lib/api.ts`.
- Reuse shared types in `apps/web/lib/types.ts`.
- Keep UI state and presentation in components, but keep source-of-truth workflow rules in the API.
- Prefer existing React/Next patterns in the repo before adding new client-side state libraries.

## Architecture Rules

- The backend owns workflow truth.
- The frontend displays and edits case state, but should not duplicate checklist or USCIS rules.
- USCIS requirement metadata belongs in `apps/api/app/content/uscis_requirements.py`.
- General checklist rules belong in backend content/services, not in JSX.
- Form/document ingestion belongs in `apps/api/app/cli/` and `apps/api/app/services/ingestion.py`.
- API contracts must stay aligned with `docs/API_SPEC.md` when behavior changes materially.
- Data model changes must stay aligned with `docs/DATA_MODEL.md` when models or relationships change materially.
- Rules/readiness/checklist logic changes must stay aligned with `docs/RULES_ENGINE.md`.

## File And Directory Ownership

Use this as the responsibility map for changes.

- `apps/api/app/api/`: HTTP routes and endpoint wiring
- `apps/api/app/services/`: business logic, checklist generation, intake projection, QA, ingestion
- `apps/api/app/content/`: static reference content, rule tables, USCIS-backed guidance
- `apps/api/app/models/`: SQLModel entities and persistence shapes
- `apps/api/app/schemas/`: API-facing request/response models
- `apps/api/app/db/`: database setup and session lifecycle
- `apps/api/app/cli/`: developer/import commands
- `apps/api/tests/`: backend regression tests
- `apps/web/app/`: app shell and page entry points
- `apps/web/components/`: UI composition and interaction logic
- `apps/web/lib/`: frontend API client and shared TypeScript types
- `docs/`: architecture, data model, API, and rule documentation
- `MARRIAGE_EVIDENCE/`: user-provided source documents
- `storage/`: local runtime state, SQLite DB, and imported uploads

## Do Not Edit Areas

- Do not edit, rename, move, or delete files in `MARRIAGE_EVIDENCE/` unless the user explicitly asks.
- Do not delete or reset `storage/app.db` unless the user explicitly asks.
- Do not bulk-delete or rewrite `storage/uploads/` unless the user explicitly asks.
- Do not hand-edit generated or installed directories such as `node_modules/`, `.next/`, or virtualenv contents.
- Do not casually rewrite USCIS reference content without also updating verification date, source URLs, and any affected checklist/readiness behavior.

## Preferred Libraries And Patterns

- FastAPI for endpoints
- SQLModel for local persistence
- Pydantic/Pydantic Settings for typed backend config
- `pypdf` for PDF parsing and ingestion
- Next.js App Router for the frontend
- TypeScript types centralized in `apps/web/lib/types.ts`
- Shared fetch helpers in `apps/web/lib/api.ts`
- Tailwind utilities for styling instead of introducing a second styling system

Prefer:

- Extending current services over adding parallel service layers
- Adding fields to existing typed contracts over passing loose untyped objects everywhere
- Keeping ingest parsing deterministic and explainable
- Keeping USCIS accuracy claims tied to official URLs and an explicit verification date

Avoid:

- Duplicating workflow logic in both API and UI
- Embedding USCIS rules or fee assumptions directly in frontend components
- Adding new heavy dependencies without a clear need
- Replacing local persistence patterns unless the task explicitly calls for that migration

## Definition Of Done

A change is done when all of the following are true:

- The feature or fix works end-to-end for the intended workflow.
- The relevant validation commands were run successfully.
- No existing local user data was unintentionally overwritten or deleted.
- Any changed API shape, rules behavior, or data model is reflected in the docs when materially needed.
- New USCIS-facing content is source-backed, dated, and phrased carefully.
- Error states are handled clearly enough that the UI does not fail silently.
- The final handoff notes what changed and how it was verified.

Minimum verification by change type:

- API/business-logic change: `npm run test:api`
- Frontend change: `npm run typecheck:web` and `npm run build:web`
- Web UX/presentation change: also run `npm run lint:web` when practical
- Ingestion/rules/QA change: `npm run test:api`, then re-run `npm run ingest:evidence` if the change affects imported case behavior

## PR And Commit Expectations

Commits should be:

- Small and scoped to one concern
- Written in imperative mood
- Clear about the user-facing outcome or internal behavior change

Good commit examples:

- `Add evidence ingest command for existing packet folders`
- `Surface USCIS requirement metadata in case workspace`
- `Fix missing case hydration after imported intake load`

PRs should include:

- What changed
- Why it changed
- Any USCIS/rules/data assumptions
- Verification performed
- Screenshots or API examples when UI/API behavior changed

If a change touches docs, rules, ingestion, or data persistence, call that out explicitly in the PR summary.

## Common Workflow Instructions For The Agent

1. Read the relevant docs and the existing implementation before editing.
2. Prefer root scripts for running the app and tests.
3. Check whether the change belongs in API logic, content, ingestion, or UI before writing code.
4. Preserve user data in `MARRIAGE_EVIDENCE/` and `storage/`.
5. Update backend-first when workflow truth changes.
6. Update the frontend only after the backend contract is clear.
7. Run the smallest meaningful validation set, then broaden it if the change is cross-cutting.
8. If behavior changed materially, update the matching docs in `docs/`.
9. If you touch USCIS accuracy claims, include the official source URL and verification date in code/content.
10. In the final handoff, mention risks, assumptions, and exactly what was verified.

## Project-Specific Guardrails

- Treat immigration workflow accuracy as high-stakes.
- Be explicit about the difference between user-confirmed local data and authoritative USCIS guidance.
- Prefer showing missing evidence clearly rather than inferring completeness from weak signals.
- When ingesting forms, preserve extracted facts only when the mapping is explainable and reviewable.
- If a change could alter checklist completeness or readiness scoring, consider the impact on imported historical cases already stored in `storage/app.db`.
