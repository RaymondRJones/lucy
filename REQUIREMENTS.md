# Marriage-Based Immigration SaaS
## Project Requirements Document

## Overview

This project is a SaaS application for U.S. citizens petitioning for their foreign spouse through the marriage-based green card process, focused on first-time marriage cases and concurrent filing of:

- I-130
- I-130A
- I-485
- I-864
- Optional related forms later:
  - I-765
  - I-131
  - G-1145

The Phase 1 product will support two core workflows:

1. Personalized checklist generator
2. Packet completeness / QA checker

The goal is to help users save money, reduce mistakes, and feel confident filing without hiring a $3,000 immigration lawyer.

---

## Phase 1 Product Goals

### Core user outcomes

- Understand whether they likely qualify for a standard marriage-based filing flow
- Get a personalized checklist of forms, documents, fees, and supporting evidence
- Upload and organize required documents
- Validate packet completeness before mailing
- Catch common filing mistakes early
- Get plain-language, calm explanations of issues
- Know what to do next

### Non-goals for Phase 1

- Legal advice
- Attorney-client relationship
- Full legal strategy for complicated cases
- USCIS filing submission directly through the app
- Automated final legal opinions
- Coverage of all immigration categories

---

## Primary User Persona

### Main user

- U.S. citizen
- Married for the first time
- Wants to sponsor foreign spouse
- Spouse is already in the U.S.
- Wants to avoid paying a private immigration attorney
- Needs help with forms, evidence, document prep, and packet review

### Secondary user

- Foreign spouse
- Needs shared access to upload documents and complete profile details

---

## Target Use Cases

1. User answers intake questions and receives a personalized filing checklist
2. User sees which forms apply to their case
3. User receives a custom list of required civil documents
4. User receives a list of recommended bona fide marriage evidence
5. User uploads documents to the portal
6. System checks for missing items
7. System flags signature/date/edition/fee issues
8. System produces a packet readiness score
9. System explains red flags in plain language
10. User downloads packet preparation instructions

---

## Recommended Tech Stack

## Frontend

- Next.js
- TypeScript
- React
- Tailwind CSS
- shadcn/ui or another accessible UI component library
- React Hook Form
- Zod for form validation
- Zustand or Redux Toolkit for client state if needed

## Backend

- Python
- FastAPI
- Pydantic
- SQLAlchemy or SQLModel
- Alembic for migrations

## Database

- PostgreSQL

## File Storage

- AWS S3 or Cloudflare R2

## Authentication

- NextAuth.js, Clerk, or Auth0

## OCR / Document Parsing

- AWS Textract
- Google Document AI
- Azure Document Intelligence
- Tesseract as fallback for low-cost OCR experimentation

## Background Jobs

- Celery + Redis
or
- RQ + Redis

## Payments

- Stripe

## Analytics

- PostHog
or
- Plausible

## Error Monitoring

- Sentry

## Infrastructure / Hosting

### Frontend hosting
- Vercel

### Backend hosting
- Railway
- Render
- Fly.io
or
- AWS ECS / Lambda if scaling later

### Database hosting
- Neon
- Supabase
- RDS

---

## System Architecture

## High-level components

1. Next.js web app
2. Python API service
3. PostgreSQL database
4. File storage bucket
5. OCR/document analysis service
6. Background job queue
7. Admin dashboard
8. Email/notification service

## Primary data flow

1. User signs up
2. User completes intake questionnaire
3. Python backend evaluates answers against checklist rules
4. Frontend displays personalized checklist
5. User uploads supporting documents
6. OCR/parsing jobs process uploaded files
7. QA engine checks packet completeness and common issues
8. User receives issue list, explanations, and readiness score

---

## Functional Requirements

## Module 1: Intake Questionnaire

### Requirements

- Multi-step guided intake flow
- Save progress
- Support spouse collaboration
- Conditional branching based on answers
- Plain-language prompts
- Mobile-friendly UX

### Intake topics

- Petitioner citizenship status
- Marriage date
- First marriage confirmation
- Beneficiary location
- Whether beneficiary entered legally
- Current immigration status
- Address history
- Employment history
- Prior immigration filings
- Children
- Financial sponsorship basics
- Household size
- Country of birth
- Country-specific document needs
- Translation needs

### Validation rules

- Required fields must be enforced
- Date formats normalized
- Name fields standardized
- Country values standardized
- Relationship logic checked for contradictions

---

## Module 2: Personalized Checklist Generator

### Requirements

- Generate case-specific checklist from intake data
- Separate checklist into:
  - forms
  - identity documents
  - civil documents
  - financial documents
  - marriage evidence
  - optional items
  - later-stage items
- Mark items as:
  - required
  - recommended
  - conditional
  - not applicable

### Checklist examples

- I-130
- I-130A
- I-485
- I-864
- I-765
- I-131
- G-1145
- Birth certificates
- Marriage certificate
- Passport biographic page
- I-94
- Visa page
- Proof of petitioner citizenship
- Tax returns / W-2s / pay stubs
- Joint lease
- Joint bank account
- Photos together
- Affidavits from friends/family
- Certified translations if needed

### Output requirements

- In-app checklist view
- Downloadable PDF
- User completion tracking
- Per-item explanation
- "Why this is needed" helper text
- "What to save now for later" section

---

## Module 3: Document Upload Portal

### Requirements

- Secure document upload
- Support PDF, JPG, JPEG, PNG
- Assign uploads to checklist items
- Versioning for re-uploads
- Document preview
- File size and type restrictions
- Upload status indicators

### Metadata to store

- file ID
- user ID
- case ID
- checklist item ID
- file type
- uploaded timestamp
- OCR status
- review status
- extraction confidence score

---

## Module 4: Packet Completeness / QA Checker

### Requirements

- Validate whether each required checklist item has an uploaded document
- Detect missing required items
- Detect likely wrong file type or empty upload
- Detect outdated form edition if possible
- Detect missing signatures if user confirms unsigned forms or OCR allows it
- Detect missing dates where possible
- Detect fee issues using maintained fee rules
- Detect inconsistent names / dates / addresses across uploaded forms and intake data
- Detect missing translation certification when non-English docs are uploaded
- Detect likely missing sponsor evidence
- Produce packet readiness score
- Produce issue severity labels:
  - blocking
  - important
  - recommended

### Example QA outputs

- Missing petitioner proof of citizenship
- Missing beneficiary birth certificate
- I-864 income evidence not uploaded
- Uploaded marriage certificate appears non-English with no translation attached
- Address mismatch between intake and uploaded form
- Incorrect USCIS form edition may have been uploaded
- Signature missing on I-130
- Fee total may be outdated

---

## Module 5: Rules Engine

### Requirements

- Central rule system for checklist generation and QA logic
- Rules must be easy to update without rewriting frontend code
- Support conditional logic for:
  - concurrent filing eligibility
  - required forms
  - required evidence
  - financial sponsorship rules
  - translation requirements
  - edge-case escalation

### Suggested implementation

- Python-based rules layer
- Store rules in JSON, YAML, or database-backed configuration
- Version rules for auditability
- Add admin interface later for rule editing

---

## Module 6: Country-Specific Civil Document Guidance

### Requirements

- Country-specific document guidance for civil records
- Explain common names for local documents
- Explain whether translations are required
- Explain if alternate evidence may be needed when records are unavailable

### Notes

- This should be educational and organizational, not legal advice
- Ideally linked to trusted source references
- Country library should be structured for easy updates

---

## Module 7: Explanations and UX Content

### Requirements

- Plain-language explanations
- Avoid legal jargon where possible
- Calm tone for red flags
- Clear distinction between:
  - required
  - recommended
  - optional
- Explain consequences of missing items without fear-based language

### Example UX content

- "You’re on track"
- "Here’s what to prepare next"
- "This item is commonly requested"
- "This may be a problem, but it is often fixable"
- "You may want professional legal help for this situation"

---

## Module 8: Shared Spouse Collaboration

### Requirements

- Invite spouse by email
- Shared checklist visibility
- Shared document uploads
- Task ownership assignment
- Activity history

### Collaboration examples

- Petitioner uploads tax returns
- Beneficiary uploads passport and I-94
- Shared progress dashboard

---

## Module 9: Admin Dashboard

### Requirements

- View users and cases
- View checklist generation logs
- View upload and OCR processing status
- View QA issue logs
- Update content and guidance
- Manage fee tables
- Manage form edition references
- Manage country-specific rules
- Manage feature flags

---

## Data Model Requirements

## Core entities

- User
- Case
- Person
- Marriage
- IntakeResponse
- ChecklistItem
- CaseChecklistItem
- UploadedDocument
- OCRExtraction
- QAIssue
- RuleVersion
- Payment
- AuditLog
- Invitation

## Important relationships

- A user can belong to one or more cases
- A case can have multiple participants
- A case has one checklist
- A checklist has many checklist items
- A case has many uploaded documents
- A case has many QA issues

---

## API Requirements

## Public/API routes

### Auth
- sign up
- sign in
- sign out
- password reset

### Case management
- create case
- get case
- update case
- invite collaborator

### Intake
- save intake step
- get intake state
- submit intake

### Checklist
- generate checklist
- get checklist
- update checklist item status

### Uploads
- request upload URL
- confirm upload complete
- list uploads
- delete upload

### QA
- run QA check
- get QA results
- get readiness score

### Content
- get country guidance
- get explanation content
- get fee table
- get form editions

### Billing
- create checkout session
- get subscription status

---

## Non-Functional Requirements

## Security

Because immigration data is highly sensitive, security is critical.

### Requirements

- Encrypt data in transit with HTTPS
- Encrypt sensitive data at rest
- Role-based access control
- Secure file storage permissions
- Audit logging for critical actions
- Signed upload URLs
- Malware scanning for uploads if possible
- Strong password policy or passwordless auth
- MFA for admins
- Data retention and deletion policy
- Privacy policy and consent flows

## Compliance considerations

- Not HIPAA by default, unless handling medical records in a way that triggers more requirements
- Consider SOC 2 readiness if targeting partnerships later
- Follow least-privilege principles
- Avoid unnecessary storage of especially sensitive data

---

## Legal / Product Risk Requirements

### Required disclaimers

- This software is not a law firm
- No attorney-client relationship is created
- Information is for educational and organizational purposes
- Users should seek a licensed immigration attorney for legal advice
- Complex or high-risk cases should be escalated

### Escalation triggers

If user reports any of the following, suggest professional legal help:

- unlawful entry
- removal/deportation history
- criminal history
- prior marriage fraud concerns
- prior immigration denials
- inconsistent identity records
- public charge or affidavit complexity
- missing key civil records with unusual circumstances

---

## OCR / Document Intelligence Requirements

### Goals

- Extract text from uploaded documents
- Detect document type
- Support QA checks and organization

### Potential extracted fields

- full name
- document type
- date of birth
- passport number
- marriage date
- issue date
- expiration date
- address
- USCIS form edition
- signatures presence if technically feasible
- language indicators

### Caveat

OCR should assist, not be treated as perfect. The user must always be able to review and correct extracted values.

---

## Readiness Score Requirements

### Purpose

Give users confidence without making legal promises.

### Inputs

- required checklist completion
- number of blocking issues
- number of important issues
- document upload completion
- consistency checks
- fee and form edition freshness

### Output examples

- Not ready
- Almost ready
- Ready for final review
- Ready to print and assemble

### Important note

Do not imply guaranteed USCIS approval.

---

## Content Requirements

### Need to maintain

- USCIS form edition references
- fee tables
- filing address references
- country-specific civil document guidance
- evidence suggestions
- plain-language help articles
- escalation logic messaging

### Content operations need

- versioning
- timestamps
- source references
- admin-editable content records

---

## Design Requirements

### UX principles

- calm
- trustworthy
- non-intimidating
- mobile-friendly
- plain language
- step-by-step
- progress visible at all times

### UI patterns

- wizard-style onboarding
- progress bars
- checklists with statuses
- document cards
- issue banners with severity
- expandable explanations
- spouse collaboration indicators

---

## Notifications Requirements

### Email / in-app notifications

- welcome email
- collaborator invitation
- checklist ready
- upload processed
- QA complete
- missing required item reminder
- payment confirmation

### Future notifications

- milestone reminders
- filing timeline updates
- notice tracking alerts

---

## Payments and Packaging

### Possible pricing structure

- Free: basic intake and limited checklist preview
- Paid: full personalized checklist
- Premium: QA checker and packet readiness review

### Stripe requirements

- checkout integration
- payment success webhook
- subscription or one-time purchase support
- invoice records

---

## Testing Requirements

## Frontend testing

- unit tests for components
- form validation tests
- e2e flows with Playwright or Cypress

## Backend testing

- unit tests for rules engine
- API integration tests
- OCR pipeline tests
- QA logic tests

## Critical scenarios to test

- simple first-marriage concurrent filing case
- missing required document case
- non-English document requiring translation
- income evidence missing for I-864
- inconsistent address data
- collaborator flow
- payment flow
- retry upload flow

---

## Observability Requirements

- structured backend logging
- API request logs
- OCR processing logs
- QA rule execution logs
- product analytics on funnel steps
- alerting on failed jobs
- Sentry for exceptions

---

## Deployment Requirements

## Environments

- local
- staging
- production

## CI/CD

- GitHub Actions
- test on pull request
- linting
- type checks
- migration checks
- deploy frontend and backend automatically

---

## Suggested Project Structure

```text
project-root/
  apps/
    web/                  # Next.js frontend
    api/                  # Python FastAPI backend
  packages/
    shared-types/         # Shared schemas/types if desired
    ui/                   # Shared UI components if monorepo
  infrastructure/
    docker/
    terraform/
  docs/
    PROJECT_REQUIREMENTS.md
    API_SPEC.md
    DATA_MODEL.md
    RULES_ENGINE.md
