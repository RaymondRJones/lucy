from __future__ import annotations

DISCLAIMERS = [
    "This software is not a law firm.",
    "No attorney-client relationship is created by using this product.",
    "The information in this workspace is for educational and organizational purposes only.",
    "For legal advice, users should consult a licensed immigration attorney.",
]

ESCALATION_TRIGGERS = [
    "unlawful entry",
    "removal or deportation history",
    "criminal history",
    "prior immigration denials",
    "marriage fraud concerns",
    "inconsistent identity records",
    "affidavit of support complexity",
    "missing key civil records under unusual circumstances",
]

EXPLANATION_CONTENT = {
    "issue_severity_help": {
        "blocking": "This should be fixed before the packet is mailed.",
        "important": "This may not stop the packet from being assembled, but it deserves attention before filing.",
        "recommended": "This can strengthen the packet or reduce confusion later.",
    },
    "readiness_labels": {
        "Not ready": "Core required items or blocking issues still need attention.",
        "Almost ready": "The packet structure is mostly in place, but a few meaningful gaps remain.",
        "Ready for final review": "Most of the packet is assembled and only lighter follow-up remains.",
        "Ready to print and assemble": "The packet appears organized for a last human review before printing.",
    },
    "disclaimers": DISCLAIMERS,
    "escalation_triggers": ESCALATION_TRIGGERS,
}

FEE_TABLE = {
    "reference_mode": "user_confirmed",
    "verification_required": True,
    "last_reviewed": None,
    "note": "This MVP intentionally avoids hard-coding filing fees as authoritative legal content. Ask users to confirm the current USCIS fee schedule before mailing.",
    "items": [
        {
            "code": "review_current_fees",
            "label": "Confirm the current USCIS filing fee schedule for every form in the packet.",
            "source": "User-confirmed in intake for now.",
        }
    ],
}

FORM_EDITIONS = {
    "reference_mode": "user_confirmed",
    "verification_required": True,
    "last_reviewed": None,
    "note": "Seed content only. In production, replace this with admin-managed form edition references sourced from official USCIS pages.",
    "items": [
        {"form": "I-130", "status": "Confirm before filing"},
        {"form": "I-130A", "status": "Confirm before filing"},
        {"form": "I-485", "status": "Confirm before filing"},
        {"form": "I-864", "status": "Confirm before filing"},
        {"form": "I-765", "status": "Confirm before filing"},
        {"form": "I-131", "status": "Confirm before filing"},
        {"form": "G-1145", "status": "Confirm before filing"},
    ],
}
