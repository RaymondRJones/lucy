# Filing Validation Todo

Last updated: 2026-05-01

This todo list tracks the remaining extension-API work after the initial I-485, I-864 preflight,
I-130, I-130A, I-765, and G-1145 validators.

## Highest Priority

1. Full I-864 validation
   - Build a source-dated I-864 questionnaire and field map.
   - Validate sponsor household math, immigrant count, tax years, joint sponsor branching, household-member income,
     asset use, I-864A requirements, interpreter/preparer fields, and signature readiness.
   - Add I-864 PDF fill payload coverage and blank-template drift tests.

2. I-765 source map and PDF payload
   - Build a source-dated I-765 question map for the adjustment-pending `(c)(9)` path.
   - Add fill payload generation metadata.
   - Cross-check identity, A-number, I-94, passport, and address facts against I-485 and uploaded extracted values.

3. G-1145 PDF payload
   - Add explicit PDF field mapping for name, email, and mobile phone.
   - Add template coverage tests and optional generated-payload metadata.

## Family Form Follow-Ups

1. Packet assembly for I-130 and I-130A
   - I-130/I-130A now generate review-draft PDFs through the supplemental form ingestion endpoints.
   - The full packet compiler is still I-485-centered and does not yet merge those petition drafts into final assembly.

2. Deeper I-130/I-130A source maps
   - Expand the current source-dated core maps to all form lines.
   - Add prior spouse, parent, address, employment, interpreter, preparer, and additional-information sections.

3. Timeline validation
   - Replace basic five-year checks with true coverage checks for I-130A address and employment history.
   - Flag gaps, overlaps, missing date ranges, and ambiguous current/foreign address history.

## Planned Validators

1. I-131 support
   - Add or refresh the blank I-131 PDF.
   - Build a source-dated I-131 question map.
   - Validate advance parole basis, travel explanation, pending I-485 connection, identity facts, and travel-risk warnings.

2. Validation snapshots
   - Persist validation runs when a user starts final packet review.
   - Store source versions, blank PDF hashes, issue lists, and user resolution notes.

3. Frontend filing-validation UI
   - Add a filing-validation panel that calls `/filing-validation`.
   - Show blockers by form, source metadata, PDF template mismatch warnings, and cross-document mismatches.
