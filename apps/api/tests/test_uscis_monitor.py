from __future__ import annotations

from pathlib import Path
from urllib.error import URLError

from app.content.fee_schedule import FILING_FEES_SOURCE_URL
from app.content.packet_mailing import ADDRESS_SOURCES_LAST_REVIEWED, I130_FILING_ADDRESS_SOURCE_URL
from app.services import uscis_monitor
from app.services.uscis_monitor import check_uscis_updates, parse_edition_date, parse_last_reviewed, render_report


def _form_page(edition: str) -> bytes:
    return f"<div>Edition Date</div> <div> <time>{edition}</time> .</div>".encode()


def _reviewed_page(iso_date: str) -> bytes:
    year, month, day = iso_date.split("-")
    return f"<span>Last Reviewed/Updated:</span> {month}/{day}/{year}".encode()


def _current_site(tmp_path: Path) -> tuple[dict[str, bytes], Path]:
    pages = {
        url: _form_page(edition) for url, (_label, edition) in uscis_monitor._expected_editions().items()
    }
    pages.update({url: _reviewed_page(date) for url, date in ADDRESS_SOURCES_LAST_REVIEWED.items()})
    pages[FILING_FEES_SOURCE_URL] = _reviewed_page(uscis_monitor.FILING_FEES_SOURCE_LAST_REVIEWED)
    template = tmp_path / "i-485.pdf"
    template.write_bytes(b"blank form")
    pages[uscis_monitor.USCIS_FORMS_PDF_URL.format(name="i-485.pdf")] = b"blank form"
    return pages, tmp_path


def test_parses_the_labelled_edition_not_alerts_about_old_editions() -> None:
    page = b"<p>We reject the prior form (edition date: 09/04/26).</p><h2>Edition Date</h2><p>09/18/26 .</p>"

    assert parse_edition_date(page) == "09/18/26"


def test_parses_last_reviewed_date_to_iso() -> None:
    assert parse_last_reviewed(b"<b>Last Reviewed/Updated:</b>\n 10/07/2026") == "2026-10-07"


def test_matching_site_reports_nothing(tmp_path) -> None:
    pages, templates = _current_site(tmp_path)

    report = check_uscis_updates(fetch=pages.__getitem__, templates_dir=templates)

    assert report.changes == []
    assert report.unreadable == []
    assert report.checked == len(pages)


def test_new_edition_changed_address_page_and_template_are_all_reported(tmp_path) -> None:
    pages, templates = _current_site(tmp_path)
    pages["https://www.uscis.gov/i-485"] = _form_page("12/01/26")
    pages[I130_FILING_ADDRESS_SOURCE_URL] = _reviewed_page("2026-12-01")
    pages[uscis_monitor.USCIS_FORMS_PDF_URL.format(name="i-485.pdf")] = b"revised form"

    report = check_uscis_updates(fetch=pages.__getitem__, templates_dir=templates)

    assert {finding.kind for finding in report.changes} == {"edition", "address_page", "template"}
    rendered = render_report(report)
    assert "`09/18/26`, USCIS now shows `12/01/26`" in rendered
    assert "Recheck every stored lockbox address" in rendered


def test_blocked_or_redesigned_pages_are_unreadable_not_silently_fine(tmp_path) -> None:
    pages, templates = _current_site(tmp_path)
    pages["https://www.uscis.gov/i-485"] = b"<html>Access denied</html>"

    def fetch(url: str) -> bytes:
        if url == "https://www.uscis.gov/g-1450":
            raise URLError("blocked")
        return pages[url]

    report = check_uscis_updates(fetch=fetch, templates_dir=templates)

    assert report.changes == []
    assert {finding.url for finding in report.unreadable} == {
        "https://www.uscis.gov/i-485",
        "https://www.uscis.gov/g-1450",
    }
    assert "## Could not check" in render_report(report)
