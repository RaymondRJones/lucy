"""Compares stored form editions, fees, and templates with live USCIS pages."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from app.services.uscis_monitor import check_uscis_updates, render_report

EXIT_NO_CHANGES = 0
EXIT_CHANGES = 1
EXIT_UNREADABLE = 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare stored USCIS editions, dates, and templates with live USCIS pages.")
    parser.add_argument("--report", default=None, help="Optional path for a Markdown copy of the report.")
    args = parser.parse_args()

    report = check_uscis_updates()
    rendered = render_report(report)
    print(rendered)
    if args.report:
        Path(args.report).write_text(rendered, encoding="utf-8")
    if report.changes:
        return EXIT_CHANGES
    return EXIT_UNREADABLE if report.unreadable else EXIT_NO_CHANGES


if __name__ == "__main__":
    sys.exit(main())
