"""Country-specific document guidance."""

from __future__ import annotations

COUNTRY_GUIDANCE = {
    "CO": {
        "country_code": "CO",
        "country_name": "Colombia",
        "overview": "For Colombian civil records, plan on collecting legible civil documents and attaching a certified English translation when the original record is in Spanish.",
        "translation_note": "USCIS expects a full English translation certification for any supporting document not written in English.",
        "availability_note": "If a standard civil record is unavailable, the case should be escalated for alternate evidence planning.",
        "documents": [
            {
                "code": "birth_certificate",
                "label": "Beneficiary birth certificate",
                "common_name": "Registro Civil de Nacimiento",
                "category": "civil_documents",
                "translation_required": True,
                "tips": [
                    "Use a complete, legible copy.",
                    "Upload the translation and translation certification together with the original record.",
                ],
            },
            {
                "code": "marriage_certificate",
                "label": "Marriage certificate",
                "common_name": "Registro Civil de Matrimonio or local marriage certificate",
                "category": "civil_documents",
                "translation_required": True,
                "tips": [
                    "Keep the full certificate, not just a summary page.",
                    "If the record is in Spanish, pair it with a certified translation.",
                ],
            },
        ],
        "sources": [
            {
                "label": "Add official country reciprocity and USCIS source links in the admin content layer before production rollout.",
                "url": None,
            }
        ],
    }
}
