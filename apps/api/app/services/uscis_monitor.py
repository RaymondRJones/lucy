from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import hashlib
import html
from pathlib import Path
import re
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.content.fee_schedule import (
    FEE_SCHEDULE_EDITION,
    FILING_FEES_SOURCE_LAST_REVIEWED,
    FILING_FEES_SOURCE_URL,
    G1450_FORM_EDITION,
    G1650_FORM_EDITION,
)
from app.content.packet_mailing import ADDRESS_SOURCES_LAST_REVIEWED
from app.content.uscis_requirements import USCIS_REQUIREMENTS
from app.core.config import REPO_ROOT

BLANK_FORMS_DIR = REPO_ROOT / "blank-immigration-documents"
USCIS_FORMS_PDF_URL = "https://www.uscis.gov/sites/default/files/document/forms/{name}"
USER_AGENT = "LucyFormEditionCheck/1.0 (+https://github.com/RaymondRJones/lucy)"
FETCH_ATTEMPTS = 3
FETCH_TIMEOUT_SECONDS = 40

Fetch = Callable[[str], bytes]


@dataclass(frozen=True)
class MonitorFinding:
    kind: str
    subject: str
    url: str
    expected: str | None = None
    found: str | None = None


@dataclass
class MonitorReport:
    changes: list[MonitorFinding]
    unreadable: list[MonitorFinding]
    checked: int


def fetch_url(url: str) -> bytes:
    for attempt in range(1, FETCH_ATTEMPTS + 1):
        try:
            with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=FETCH_TIMEOUT_SECONDS) as response:
                return response.read()
        except (URLError, TimeoutError):
            if attempt == FETCH_ATTEMPTS:
                raise
            time.sleep(attempt * 5)
    raise AssertionError("unreachable")


def _page_text(content: bytes) -> str:
    text = re.sub(r"(?s)<script.*?</script>|<style.*?</style>", " ", content.decode("utf-8", "ignore"))
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text)))


def parse_edition_date(content: bytes) -> str | None:
    # USCIS's labelled "Edition Date" section. Alerts about old editions read "edition date:" and do not match.
    match = re.search(r"Edition Date\s+(\d{2}/\d{2}/\d{2})", _page_text(content))
    return match.group(1) if match else None


def parse_last_reviewed(content: bytes) -> str | None:
    match = re.search(r"Last Reviewed/Updated:\s*(\d{2}/\d{2}/\d{4})", _page_text(content))
    return datetime.strptime(match.group(1), "%m/%d/%Y").strftime("%Y-%m-%d") if match else None


def _expected_editions() -> dict[str, tuple[str, str]]:
    # Keyed by page URL so forms sharing a page, like I-130 and I-130A, are read once.
    pages = {
        requirement["official_url"]: (requirement["label"], requirement["accepted_edition"])
        for requirement in USCIS_REQUIREMENTS
        if requirement.get("accepted_edition")
    }
    pages["https://www.uscis.gov/g-1450"] = ("Form G-1450", G1450_FORM_EDITION)
    pages["https://www.uscis.gov/g-1650"] = ("Form G-1650", G1650_FORM_EDITION)
    pages["https://www.uscis.gov/g-1055"] = ("Form G-1055 fee schedule", FEE_SCHEDULE_EDITION)
    return pages


def _check_page(
    report: MonitorReport,
    fetch: Fetch,
    parse: Callable[[bytes], str | None],
    kind: str,
    subject: str,
    url: str,
    expected: str,
) -> None:
    report.checked += 1
    try:
        found = parse(fetch(url))
    except (URLError, TimeoutError) as exc:
        report.unreadable.append(MonitorFinding(kind, subject, url, expected, f"Could not fetch: {exc}"))
        return
    if found is None:
        report.unreadable.append(MonitorFinding(kind, subject, url, expected, "Date not found on the page"))
    elif found != expected:
        report.changes.append(MonitorFinding(kind, subject, url, expected, found))


def _check_template(report: MonitorReport, fetch: Fetch, template: Path) -> None:
    report.checked += 1
    url = USCIS_FORMS_PDF_URL.format(name=template.name)
    try:
        live = fetch(url)
    except (URLError, TimeoutError) as exc:
        report.unreadable.append(MonitorFinding("template", template.name, url, None, f"Could not fetch: {exc}"))
        return
    stored_hash = hashlib.sha256(template.read_bytes()).hexdigest()
    live_hash = hashlib.sha256(live).hexdigest()
    if stored_hash != live_hash:
        report.changes.append(MonitorFinding("template", template.name, url, stored_hash[:12], live_hash[:12]))


def check_uscis_updates(fetch: Fetch = fetch_url, templates_dir: Path = BLANK_FORMS_DIR) -> MonitorReport:
    report = MonitorReport(changes=[], unreadable=[], checked=0)
    for url, (label, edition) in _expected_editions().items():
        _check_page(report, fetch, parse_edition_date, "edition", label, url, edition)
    for url, last_reviewed in ADDRESS_SOURCES_LAST_REVIEWED.items():
        _check_page(report, fetch, parse_last_reviewed, "address_page", "Filing address page", url, last_reviewed)
    _check_page(
        report,
        fetch,
        parse_last_reviewed,
        "fee_page",
        "Filing fees page",
        FILING_FEES_SOURCE_URL,
        FILING_FEES_SOURCE_LAST_REVIEWED,
    )
    for template in sorted(templates_dir.glob("*.pdf")):
        _check_template(report, fetch, template)
    return report


KIND_GUIDANCE = {
    "edition": "New form edition. Replace the template, update field maps, and update the accepted edition and rejection dates.",
    "address_page": "The page changed. Recheck every stored lockbox address against it, then update the stored date.",
    "fee_page": "The page changed. Recheck fees against Form G-1055, then update the stored date.",
    "template": "The PDF differs from the stored template, even if the edition did not change. Compare fields and text.",
}


def render_report(report: MonitorReport) -> str:
    lines = [f"Checked {report.checked} USCIS sources.", ""]
    if report.changes:
        lines.append("## Changes")
        for finding in report.changes:
            lines.append(
                f"- **{finding.subject}**: stored `{finding.expected}`, USCIS now shows `{finding.found}`. "
                f"{KIND_GUIDANCE[finding.kind]} {finding.url}"
            )
        lines.append("")
    if report.unreadable:
        lines.append("## Could not check")
        lines.extend(f"- **{item.subject}**: {item.found}. {item.url}" for item in report.unreadable)
        lines.append("")
    if not report.changes and not report.unreadable:
        lines.append("No differences found.")
    return "\n".join(lines).rstrip() + "\n"
