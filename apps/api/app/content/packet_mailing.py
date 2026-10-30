from __future__ import annotations

from typing import Any


PACKET_MAILING_VERIFIED_ON = "2026-10-30"
PACKET_MAILING_SOURCE_LAST_REVIEWED = "2024-10-11"
PACKET_MAILING_SOURCE_URL = (
    "https://www.uscis.gov/forms/all-forms/"
    "uscis-lockbox-filing-locations-chart-for-certain-family-based-forms"
)
I130_FILING_ADDRESS_SOURCE_URL = "https://www.uscis.gov/i-130-addresses"
I765_FILING_ADDRESS_SOURCE_URL = "https://www.uscis.gov/i-765-addresses"
I131_FILING_ADDRESS_SOURCE_URL = "https://www.uscis.gov/i-131-addresses"
I485_FILING_ADDRESS_SOURCE_URL = (
    "https://www.uscis.gov/forms/all-forms/"
    "direct-filing-addresses-for-form-i-485-application-to-register-permanent-residence-or-adjust-status"
)

LOCATION_LABELS = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "DC": "District of Columbia",
    "FL": "Florida",
    "GA": "Georgia",
    "GU": "Guam",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "MP": "Commonwealth of the Northern Mariana Islands",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "PR": "Puerto Rico",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VI": "U.S. Virgin Islands",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
}

LOCATION_ALIASES = {
    label.lower(): code for code, label in LOCATION_LABELS.items()
}
LOCATION_ALIASES.update(
    {
        "northern mariana islands": "MP",
        "commonwealth of northern mariana islands": "MP",
        "cnmi": "MP",
        "us virgin islands": "VI",
        "u.s. virgin islands": "VI",
        "virgin islands": "VI",
        "washington dc": "DC",
        "washington, dc": "DC",
    }
)

LOCKBOXES: dict[str, dict[str, Any]] = {
    "dallas": {
        "lockbox": "USCIS Dallas Lockbox",
        "usps_address_lines": [
            "USCIS",
            "Attn: AOS",
            "P.O. Box 650288",
            "Dallas, TX 75265-0288",
        ],
        "private_carrier_address_lines": [
            "USCIS",
            "Attn: AOS (Box 650288)",
            "2501 S. State Hwy. 121 Business",
            "Suite 400",
            "Lewisville, TX 75067-8003",
        ],
    },
    "elgin": {
        "lockbox": "USCIS Elgin Lockbox",
        "usps_address_lines": [
            "USCIS",
            "Attn: AOS",
            "P.O. Box 4109",
            "Carol Stream, IL 60197-4109",
        ],
        "private_carrier_address_lines": [
            "USCIS",
            "Attn: AOS (Box 4109)",
            "2500 Westfield Drive",
            "Elgin, IL 60124-7836",
        ],
    },
    "phoenix": {
        "lockbox": "USCIS Phoenix Lockbox",
        "usps_address_lines": [
            "USCIS",
            "Attn: AOS",
            "P.O. Box 20500",
            "Phoenix, AZ 85036-0500",
        ],
        "private_carrier_address_lines": [
            "USCIS",
            "Attn: AOS (Box 20500)",
            "2108 E. Elliot Rd.",
            "Tempe, AZ 85284-1806",
        ],
    },
    "chicago": {
        "lockbox": "USCIS Chicago Lockbox",
        "usps_address_lines": [
            "USCIS",
            "Attn: AOS",
            "P.O. Box 805887",
            "Chicago, IL 60680",
        ],
        "private_carrier_address_lines": [
            "USCIS",
            "Attn: AOS (Box 805887)",
            "131 S. Dearborn St., 3rd Floor",
            "Chicago, IL 60603-5517",
        ],
    },
}

LOCKBOX_BY_LOCATION = {
    "TX": "dallas",
    "DE": "elgin",
    "GA": "elgin",
    "IN": "elgin",
    "IA": "elgin",
    "KS": "elgin",
    "MD": "elgin",
    "MI": "elgin",
    "MS": "elgin",
    "MO": "elgin",
    "NE": "elgin",
    "NY": "elgin",
    "NC": "elgin",
    "ND": "elgin",
    "PA": "elgin",
    "SD": "elgin",
    "VA": "elgin",
    "WV": "elgin",
    "WI": "elgin",
    "AL": "phoenix",
    "AK": "phoenix",
    "AZ": "phoenix",
    "AR": "phoenix",
    "CO": "phoenix",
    "HI": "phoenix",
    "ID": "phoenix",
    "KY": "phoenix",
    "LA": "phoenix",
    "MT": "phoenix",
    "NV": "phoenix",
    "NM": "phoenix",
    "OK": "phoenix",
    "OR": "phoenix",
    "TN": "phoenix",
    "UT": "phoenix",
    "WA": "phoenix",
    "WY": "phoenix",
    "CA": "chicago",
    "MP": "chicago",
    "CT": "chicago",
    "DC": "chicago",
    "FL": "chicago",
    "GU": "chicago",
    "IL": "chicago",
    "ME": "chicago",
    "MA": "chicago",
    "MN": "chicago",
    "NH": "chicago",
    "NJ": "chicago",
    "OH": "chicago",
    "PR": "chicago",
    "RI": "chicago",
    "SC": "chicago",
    "VI": "chicago",
    "VT": "chicago",
}

PRIVATE_CARRIER_VALUES = {"private", "fedex", "ups", "dhl", "carrier"}


def normalize_mailing_location(value: str | None) -> str | None:
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    upper = raw.upper()
    if upper in LOCATION_LABELS:
        return upper
    return LOCATION_ALIASES.get(" ".join(raw.lower().split()))


def mailing_recommendation_for_location(value: str | None, carrier: str = "usps") -> dict[str, Any] | None:
    location_code = normalize_mailing_location(value)
    if location_code is None:
        return None
    lockbox_key = LOCKBOX_BY_LOCATION.get(location_code)
    if lockbox_key is None:
        return None

    lockbox = LOCKBOXES[lockbox_key]
    carrier_key = "private" if carrier.lower() in PRIVATE_CARRIER_VALUES else "usps"
    address_key = "private_carrier_address_lines" if carrier_key == "private" else "usps_address_lines"
    return {
        "location_code": location_code,
        "location_label": LOCATION_LABELS[location_code],
        "carrier": carrier_key,
        "lockbox": lockbox["lockbox"],
        "address_lines": lockbox[address_key],
        "usps_address_lines": lockbox["usps_address_lines"],
        "private_carrier_address_lines": lockbox["private_carrier_address_lines"],
        "source_url": PACKET_MAILING_SOURCE_URL,
        "related_source_urls": [
            I485_FILING_ADDRESS_SOURCE_URL,
            I130_FILING_ADDRESS_SOURCE_URL,
            I765_FILING_ADDRESS_SOURCE_URL,
            I131_FILING_ADDRESS_SOURCE_URL,
        ],
        "source_last_reviewed": PACKET_MAILING_SOURCE_LAST_REVIEWED,
        "verified_on": PACKET_MAILING_VERIFIED_ON,
        "note": (
            "For family-based Forms I-130, I-131, I-485, I-765, I-824, or I-864, "
            "USCIS routes the packet by where the filer lives and the delivery method. "
            "After its Oct. 7, 2026 filing-location update, the USCIS address pages for Forms I-130, I-485, I-765, "
            "and I-131 still send these family-based filings to this lockbox chart, checked 2026-10-30. "
            "The separate addresses USCIS lists for Form I-130 filed alone do not apply to this packet. "
            "Verify the live USCIS pages again before mailing."
        ),
    }
