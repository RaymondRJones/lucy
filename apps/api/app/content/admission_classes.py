from __future__ import annotations


I94_INFO_SOURCE = {
    "label": "USCIS Form I-94 information page",
    "url": "https://www.uscis.gov/forms/all-forms/form-i-94-arrivaldeparture-record-information-for-completing-uscis-forms",
    "verified_on": "2026-04-30",
    "notes": "USCIS explains that Form I-94 documents admission and points applicants to CBP for the most recent I-94 record.",
}

CLASS_OF_ADMISSION_OPTIONS = [
    {"value": "B-1", "label": "B-1 temporary visitor for business"},
    {"value": "B-2", "label": "B-2 temporary visitor for pleasure/tourism"},
    {"value": "F-1", "label": "F-1 academic student"},
    {"value": "F-2", "label": "F-2 spouse or child of F-1"},
    {"value": "J-1", "label": "J-1 exchange visitor"},
    {"value": "J-2", "label": "J-2 spouse or child of J-1"},
    {"value": "M-1", "label": "M-1 vocational student"},
    {"value": "M-2", "label": "M-2 spouse or child of M-1"},
    {"value": "H-1B", "label": "H-1B specialty occupation"},
    {"value": "H-4", "label": "H-4 dependent"},
    {"value": "H-2A", "label": "H-2A temporary agricultural worker"},
    {"value": "H-2B", "label": "H-2B temporary nonagricultural worker"},
    {"value": "L-1", "label": "L-1 intracompany transferee"},
    {"value": "L-2", "label": "L-2 dependent"},
    {"value": "L-2S", "label": "L-2S dependent spouse"},
    {"value": "E-1", "label": "E-1 treaty trader"},
    {"value": "E-1S", "label": "E-1S treaty trader spouse"},
    {"value": "E-2", "label": "E-2 treaty investor"},
    {"value": "E-2S", "label": "E-2S treaty investor spouse"},
    {"value": "E-3", "label": "E-3 specialty occupation worker from Australia"},
    {"value": "E-3S", "label": "E-3S spouse of E-3"},
    {"value": "K-1", "label": "K-1 fiance(e) of U.S. citizen"},
    {"value": "K-2", "label": "K-2 child of K-1"},
    {"value": "K-3", "label": "K-3 spouse of U.S. citizen"},
    {"value": "K-4", "label": "K-4 child of K-3"},
    {"value": "O-1", "label": "O-1 extraordinary ability"},
    {"value": "O-3", "label": "O-3 dependent"},
    {"value": "P-1", "label": "P-1 athlete or entertainer"},
    {"value": "P-3", "label": "P-3 artist or entertainer"},
    {"value": "R-1", "label": "R-1 religious worker"},
    {"value": "R-2", "label": "R-2 dependent"},
    {"value": "TN", "label": "TN USMCA professional"},
    {"value": "TD", "label": "TD dependent of TN"},
    {"value": "WB", "label": "WB visa waiver business visitor"},
    {"value": "WT", "label": "WT visa waiver tourist visitor"},
    {"value": "DA", "label": "DA parole class shown on I-94"},
    {"value": "DT", "label": "DT parole class shown on I-94"},
]

_CLASS_OF_ADMISSION_VALUES = {option["value"] for option in CLASS_OF_ADMISSION_OPTIONS}


def normalize_class_of_admission(value: object) -> str:
    raw = str(value or "").strip().upper()
    if not raw:
        return ""
    compact = raw.replace(" ", "").replace("_", "-")
    if compact in _CLASS_OF_ADMISSION_VALUES:
        return compact
    no_hyphen = compact.replace("-", "")
    for option in CLASS_OF_ADMISSION_OPTIONS:
        if option["value"].replace("-", "") == no_hyphen:
            return option["value"]
    return compact


# Options of the I-130 Part 4, Item 21.a dropdown, which accepts nothing else.
# Read from blank-immigration-documents/i-130.pdf on 2026-10-31.
I130_CLASS_OF_ADMISSION_CODES = frozenset(
    """
    1B1 1B2 1B3 1B4 1B5 1BS A1 A2 A3 AS ASD AW B1 B1A B1B B1C B1D B2 BE C1 C2 C3 C4 CC CH CP CW1 CW2 D1 D2 DA DE DT DX
    E1 E2 E2C E3 EAO EWI F1 F2 FSM FUG G1 G2 G3 G4 G5 GB GT H1 H1A H1B H1C H2 H2A H2B H2R H3 H3A H3B H4 HSC I IMM IN
    J1 J1S J2 J2S K1 K2 K3 K4 L1 L1A L1B L2 LZ M1 M2 MIS ML N1 N2 N3 N4 N5 N6 N7 N8 N9 O1 O1A O1B O2 O3 OP
    P1 P1A P1B P1S P2 P2S P3 P3S P4 PAL PAR PI Q1 Q2 Q3 R1 R2 RE RE5 RW S1 S2 S9 SDF ST T1 T2 T3 T4 T5 TB TC TD TN1 TN2
    TWO U1 U2 U3 U4 U5 UN UU V1 V2 V3 WB WD WI WT X
    """.split()
)
_I130_CLASS_ALIASES = {"PAROLE": "PAR", "PAROLEE": "PAR"}


def i130_class_of_admission_code(value: object) -> str:
    """Return the Item 21.a option for an answer, or "" when none can be chosen without guessing."""
    raw = str(value or "").strip()
    candidates = [raw]
    # A class code can lead a description, such as "B-1 visitor for business". A digit tells it from a plain word.
    first_word = raw.split()[0] if raw else ""
    if any(character.isdigit() for character in first_word):
        candidates.append(first_word)
    for candidate in candidates:
        code = normalize_class_of_admission(candidate).replace("-", "")
        code = _I130_CLASS_ALIASES.get(code, code)
        if code in I130_CLASS_OF_ADMISSION_CODES:
            return code
    return ""
