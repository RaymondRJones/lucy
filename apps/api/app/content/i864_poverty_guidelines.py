from __future__ import annotations

from typing import Literal


I864P_VERSION = "i864p-2025"
I864P_VERIFIED_ON = "2026-04-28"
I864P_EFFECTIVE_ON = "2025-03-01"
I864P_LAST_REVIEWED_BY_USCIS = "2025-02-28"
I864P_OFFICIAL_URL = "https://www.uscis.gov/i-864p"

I864P_SOURCES = [
    {
        "label": "USCIS Form I-864P, 2025 HHS Poverty Guidelines for Affidavit of Support",
        "url": I864P_OFFICIAL_URL,
        "verified_on": I864P_VERIFIED_ON,
        "notes": (
            "USCIS listed the 2025 HHS Poverty Guidelines as effective beginning March 1, 2025 "
            "and last reviewed/updated February 28, 2025 when checked."
        ),
    }
]

I864P_REGION_BY_STATE = {
    "AK": "alaska",
    "HI": "hawaii",
}

I864P_CONTIGUOUS_STATES_AND_TERRITORIES = {
    "AL",
    "AR",
    "AZ",
    "CA",
    "CO",
    "CT",
    "DC",
    "DE",
    "FL",
    "GA",
    "GU",
    "IA",
    "ID",
    "IL",
    "IN",
    "KS",
    "KY",
    "LA",
    "MA",
    "MD",
    "ME",
    "MI",
    "MN",
    "MO",
    "MP",
    "MS",
    "MT",
    "NC",
    "ND",
    "NE",
    "NH",
    "NJ",
    "NM",
    "NV",
    "NY",
    "OH",
    "OK",
    "OR",
    "PA",
    "PR",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VA",
    "VI",
    "VT",
    "WA",
    "WI",
    "WV",
    "WY",
}

I864P_GUIDELINES = {
    "contiguous": {
        "label": "48 contiguous states, DC, Puerto Rico, U.S. Virgin Islands, Guam, and CNMI",
        "thresholds": {
            2: {"100": 21150, "125": 26437},
            3: {"100": 26650, "125": 33312},
            4: {"100": 32150, "125": 40187},
            5: {"100": 37650, "125": 47062},
            6: {"100": 43150, "125": 53937},
            7: {"100": 48650, "125": 60812},
            8: {"100": 54150, "125": 67687},
        },
        "additional": {"100": 5500, "125": 6875},
    },
    "alaska": {
        "label": "Alaska",
        "thresholds": {
            2: {"100": 26430, "125": 33037},
            3: {"100": 33310, "125": 41637},
            4: {"100": 40190, "125": 50237},
            5: {"100": 47070, "125": 58837},
            6: {"100": 53950, "125": 67437},
            7: {"100": 60830, "125": 76037},
            8: {"100": 67710, "125": 84637},
        },
        "additional": {"100": 6880, "125": 8600},
    },
    "hawaii": {
        "label": "Hawaii",
        "thresholds": {
            2: {"100": 24320, "125": 30400},
            3: {"100": 30650, "125": 38312},
            4: {"100": 36980, "125": 46225},
            5: {"100": 43310, "125": 54137},
            6: {"100": 49640, "125": 62050},
            7: {"100": 55970, "125": 69962},
            8: {"100": 62300, "125": 77875},
        },
        "additional": {"100": 6330, "125": 7913},
    },
}


def i864p_region_for_state(state: str | None) -> Literal["contiguous", "alaska", "hawaii"] | None:
    if state is None:
        return None
    normalized = state.strip().upper()
    if normalized in I864P_REGION_BY_STATE:
        return I864P_REGION_BY_STATE[normalized]  # type: ignore[return-value]
    if normalized in I864P_CONTIGUOUS_STATES_AND_TERRITORIES:
        return "contiguous"
    return None


def i864p_required_income(
    household_size: int,
    *,
    region: Literal["contiguous", "alaska", "hawaii"] = "contiguous",
    active_duty_sponsoring_spouse_or_child: bool = False,
) -> int:
    if household_size < 2:
        household_size = 2
    column = "100" if active_duty_sponsoring_spouse_or_child else "125"
    region_table = I864P_GUIDELINES[region]
    if household_size <= 8:
        return int(region_table["thresholds"][household_size][column])
    return int(region_table["thresholds"][8][column]) + (
        (household_size - 8) * int(region_table["additional"][column])
    )
