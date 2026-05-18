# Branching Engine Redesign

0. Product flow structure

Use this top-level flow:

Start
  → Case Type
  → Eligibility Gate
  → Risk Screening
  → Required Forms
  → I-485 Data Collection
  → Evidence Builder
  → Review / Warnings
  → Packet Assembly
  → Final Export
1. Case Type Branch
Q: What is your basis for green card?
Branch A — U.S. citizen spouse

Proceed to marriage-based AOS workflow.

IF petitioner_status = U.S. citizen
AND relationship = spouse
THEN category = Immediate Relative / Spouse of U.S. Citizen
Branch B — green card holder spouse

Allow, but add visa bulletin / priority date logic.

IF petitioner_status = lawful permanent resident
AND relationship = spouse
THEN category = Family Preference F2A
REQUIRE visa availability check
Branch C — parent / child / sibling / employment / asylum / other

For MVP:

IF category != U.S. citizen spouse
THEN show "not supported yet" OR "attorney review required"
2. Physical Presence Gate
Q: Is the applicant currently inside the United States?
Yes

Continue.

No
STOP: I-485 is generally for adjustment inside the U.S.
Suggest consular processing flow instead.
3. Existing Petition Branch
Q: Has Form I-130 already been filed?
No, not filed
Generate concurrent filing packet:
- I-130
- I-130A
- I-485
- I-864
- I-693
- optional I-765
- optional I-131
Yes, pending
Ask for I-797 receipt notice.
Require:
- I-130 receipt number
- receipt notice copy
- petitioner/beneficiary match check
Yes, approved
Ask for I-130 approval notice.
Require:
- approval notice copy
- priority date
Denied / revoked / withdrawn
STOP: attorney review required.
4. Entry / Inspection Branch
Q: How did the applicant last enter the U.S.?
Entered with visa / ESTA / parole
Eligible path likely possible.
Collect:
- I-94
- passport biographic page
- visa page
- entry stamp if available
- travel history
Entered without inspection
Attorney review required.
Possible 245(i), parole-in-place, waiver, consular processing issues.
Crewman, transit without visa, J-1 2-year rule, K-1 issue
Flag as high-risk.
Require attorney review.
5. Current Status Branch
Q: What is your current immigration status?

Options:

B-2 visitor
F-1 student
H-1B
J-1
K-1
ESTA/VWP
Overstay
No current status
Other
U.S. citizen spouse + inspected entry

For immediate relatives, overstay/unauthorized work is often not fatal, but still collect it honestly.

IF spouse_of_USC = true
AND inspected_or_paroled = true
THEN continue but collect violations
LPR spouse / employment / other
IF not immediate_relative
AND overstay OR unauthorized_work OR status violation
THEN attorney review
6. Marriage Validity Branch
Q: Are you legally married?
Yes

Collect:

- marriage certificate
- date/place of marriage
- prior marriages for both spouses
- divorce/death records for all prior marriages
No
STOP: cannot file spouse-based I-485 yet.
Married less than 2 years
Flag: likely conditional green card if approved before 2-year anniversary.
Married 2+ years
Flag: likely 10-year green card if approved after 2-year anniversary.
7. Bona Fide Marriage Evidence Branch

Ask:

Do you have joint evidence?

Evidence categories:

Strong:
- joint lease / mortgage
- joint bank account
- joint insurance
- joint tax return
- shared utilities
- shared car/health/renters insurance
- children together

Medium:
- authorized user credit card
- shared subscriptions
- travel together
- photos with family/friends
- mail to same address
- emergency contact records

Weak but useful:
- affidavits
- chats/call logs
- gift receipts
- social media

Logic:

IF 3+ strong items
THEN evidence strength = strong

IF 1-2 strong + several medium
THEN evidence strength = acceptable

IF mostly photos/chats/affidavits
THEN evidence strength = weak; recommend adding joint financial/residential evidence
8. Address History Branch

For I-485, collect address history.

Ask: Where have you physically lived during the required lookback period?

Logic:

IF applicant stayed with family/friends temporarily
THEN collect as address if they physically lived/slept there

IF applicant traveled briefly/vacationed
THEN do not list as residence

IF overlap exists
THEN ask if one was mailing address and one was physical residence

IF gap exists
THEN force user to fill missing dates

Validation:

No date gaps.
No impossible overlaps unless explained.
Current address must match where applicant lives now.
Mailing address can differ.
9. Travel History Branch

Collect:

- last arrival date
- port of entry
- status/class of admission
- I-94 number
- passport used
- every trip outside U.S. during relevant period

Logic:

IF no I-94 found
THEN prompt user to retrieve from CBP I-94 site

IF class = B2, B-2, WT, F1, H1B, etc.
THEN normalize display to USCIS-style where possible

IF applicant left after I-130/I-485 issue
THEN attorney review if I-485 already filed or unlawful presence issue
10. Intent / B-2 Visitor Risk Branch

Important for your app:

Q: At the time of last entry, did you intend to permanently immigrate?

Do not coach fraud. Use risk language.

IF entered on B-2/ESTA and married/filed soon after entry
THEN flag "possible immigrant intent / misrepresentation concern"
Ask:
- Were you already married?
- Was I-130 already filed?
- Did you tell CBP you were visiting temporarily?
- Did plans change after arrival?
- How many days after entry did you marry/file?

Risk:

0-30 days after entry = high review
31-90 days = medium/high review
90+ days = lower but still fact-specific

Output:

If high-risk, recommend attorney review before filing.
11. Criminal History Branch

Ask broad, form-aligned questions.

Have you ever been arrested, cited, charged, convicted, detained, or had a criminal case anywhere in the world?
No

Continue.

Yes

Collect:

- date
- country/state
- charge
- outcome
- certified court disposition
- police records

Risk:

Any arrest/charge/conviction = attorney review.
DUI, drugs, theft, domestic violence, fraud, prostitution, weapons, immigration fraud = high-risk.
12. Immigration Violations Branch

Ask:

Have you ever:
- overstayed?
- worked without authorization?
- claimed to be a U.S. citizen?
- voted?
- used fake documents?
- been removed/deported?
- missed immigration court?
- had visa denied?
- had prior I-485 denied?

Logic:

False claim to U.S. citizenship = critical attorney review.
Prior removal/deportation = critical attorney review.
Unauthorized work/overstay + USC spouse = continue with warning.
Unauthorized work/overstay + non-USC category = attorney review.
13. Public Charge / I-864 Branch

For marriage-based cases, require I-864. USCIS describes I-864 as the form showing the immigrant has adequate financial support and is not likely to rely on the U.S. government.

Q: Is the petitioner willing to sponsor the applicant?
Yes

Collect:

- petitioner income
- household size
- most recent tax transcript
- W-2/1099/pay stubs
- proof of U.S. citizenship/LPR status
- domicile in U.S.
Income sufficient
I-864 only
Income insufficient
Ask for:
- household member I-864A, OR
- joint sponsor I-864
Petitioner has no income
Still require petitioner I-864.
Also require joint sponsor.
14. Medical I-693 Branch

USCIS currently says if you are required to submit I-693, you must submit it with I-485.

Q: Do you have sealed I-693 from civil surgeon?
Yes
Add to packet.
Warn: do not open sealed envelope.
No
Block final packet or show critical warning:
"Schedule civil surgeon before filing."
K visa with recent overseas medical
Ask date of overseas medical.
If within allowed window, may only need vaccination supplement / special handling.
Recommend attorney/civil surgeon confirmation.
15. Work Permit I-765 Branch
Q: Do you want work authorization while I-485 is pending?
Yes

Generate I-765.

Category usually: (c)(9) pending adjustment applicant

Collect:

- SSN preference
- prior EADs
- passport photos
- identity docs
No

Skip.

16. Travel Permit I-131 Branch
Q: Do you want permission to travel while I-485 is pending?
Yes

Generate I-131 / advance parole.

Warn:

Do not travel internationally while I-485 is pending unless advance parole is approved or attorney confirms exception.
Has unlawful presence / prior removal / status issue
Attorney review before travel.
17. Children Branch
Q: Does applicant have children?

Collect for each child:

- full name
- DOB
- country of birth
- A-number if any
- immigration status
- whether child is also applying

Logic:

IF child also adjusting
THEN separate I-485 packet may be needed.
IF stepchild relationship created before child turned 18
THEN possible family derivative/stepchild path.
ELSE attorney review.
18. Prior Marriages Branch

For applicant and petitioner:

Q: Were you previously married?
Yes

Require:

- divorce decree
- annulment record
- death certificate

Validation:

Current marriage date must be after all prior marriages legally ended.
19. Names Branch
Q: Have you ever used other names?

Examples:

- maiden name
- prior married name
- nickname used legally
- different passport spelling
- accent/spacing variations

Logic:

IF name differs across passport, marriage certificate, birth certificate, I-94
THEN ask for explanation/evidence
20. Birth Certificate Branch
Q: Do you have a birth certificate?
Yes

Check:

- full name
- DOB
- parents’ names
- place of birth
- certified translation if not English
No / incomplete
Ask country-specific issue.
Suggest secondary evidence:
- baptismal record
- school record
- affidavits
- government certificate of nonavailability
21. Military / Groups / Security Branch

Ask yes/no:

Have you ever served in military, police, armed group, political group, intelligence, prison, detention, or security organization?
Yes

Collect details.

Attorney review depending on country, role, and facts.
22. Inadmissibility “Hard Stop” Branches

Any “yes” should route to attorney review:

- criminal conviction
- drug offense
- prostitution-related issue
- immigration fraud/misrepresentation
- false claim to U.S. citizenship
- prior deportation/removal
- unlawful voting
- smuggling someone into U.S.
- terrorism/security-related issue
- persecution/torture involvement
- public charge complexity
- communicable disease / vaccine refusal issue
23. Form Completeness Validation

Before export:

Check:
- no required field blank
- no date gaps
- all Yes answers have explanations
- all foreign-language docs have translations
- passport photos included
- correct edition dates
- signatures present
- payment included
- I-693 included if required
24. Packet Output Branch
Concurrent filing
Packet:
1. Payment
2. Cover letter
3. I-130
4. I-130A
5. I-485
6. I-864
7. I-693 sealed envelope
8. I-765 optional
9. I-131 optional
10. civil documents
11. relationship evidence
I-130 pending
Packet:
1. Payment
2. Cover letter referencing I-130 receipt number
3. I-797 I-130 receipt notice
4. I-485
5. I-864
6. I-693
7. optional I-765
8. optional I-131
9. civil documents
10. relationship evidence if helpful
I-130 approved
Same as pending, but include I-130 approval notice.
25. MVP “Attorney Review” Trigger List

Your app should not try to solve these:

- entered without inspection
- prior removal/deportation
- criminal history
- false claim to U.S. citizenship
- visa fraud/misrepresentation concern
- ESTA/VWP overstay complexity
- J-1 two-year home residency rule
- K-1 married someone other than petitioner
- public charge unusual facts
- petitioner income/domicile problem
- multiple prior immigration denials
- asylum/removal court history
- applicant outside U.S.
- marriage very recent + weak evidence + B-2/ESTA entry
26. Simplified JSON Logic Example
{
  "case_type": {
    "if": "relationship == 'spouse' && petitioner_status == 'US_CITIZEN'",
    "then": "USC_SPOUSE_AOS",
    "else": "UNSUPPORTED_OR_ATTORNEY_REVIEW"
  },
  "presence": {
    "if": "applicant_inside_us == true",
    "then": "continue",
    "else": "consular_processing_not_i485"
  },
  "entry": {
    "if": "last_entry == 'inspected_or_paroled'",
    "then": "continue",
    "else": "attorney_review"
  },
  "i130": {
    "not_filed": ["I-130", "I-130A", "I-485", "I-864", "I-693"],
    "pending": ["I-797_receipt", "I-485", "I-864", "I-693"],
    "approved": ["I-130_approval", "I-485", "I-864", "I-693"],
    "denied": "attorney_review"
  },
  "risk": {
    "criminal_history": "attorney_review",
    "prior_removal": "attorney_review",
    "false_us_citizen_claim": "attorney_review",
    "entered_without_inspection": "attorney_review",
    "b2_or_esta_recent_entry": "risk_warning"
  },
  "optional_forms": {
    "wants_work_permit": "I-765",
    "wants_travel_permit": "I-131"
  }
}

The best MVP: only support clean U.S. citizen spouse cases with inspected entry, no criminal history, no prior removal, no fraud issue, and I-693 ready. Everything else becomes “review needed.”