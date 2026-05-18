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
