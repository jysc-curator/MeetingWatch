"""Report each official source's observed upcoming schedule horizon."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def _table(coverage: dict) -> str:
    lines = [
        "| Source | Scrape | Cards | Agendas | Pending | Scheduled through |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for city, item in sorted((coverage.get("sources") or {}).items()):
        lines.append(
            f"| {city} | {item.get('scrape_status', 'unknown')} | "
            f"{item.get('published_card_count', 0)} | "
            f"{item.get('agenda_published_count', 0)} | "
            f"{item.get('agenda_pending_count', 0)} | "
            f"{item.get('scheduled_through') or '—'} |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/meetings.json"))
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    coverage = payload.get("source_coverage") or {}
    if not coverage:
        raise SystemExit("source_coverage is missing from the generated dataset")

    report = _table(coverage)
    print(report)

    messages = list(coverage.get("warnings") or [])
    for city, item in (coverage.get("sources") or {}).items():
        if item.get("scrape_status") == "error":
            messages.append(f"{city}: scraper raised an error")

    for message in dict.fromkeys(messages):
        print(f"::warning title=Source schedule coverage::{message}")

    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as summary:
            summary.write("## Source schedule coverage\n\n")
            summary.write(report + "\n")
            if messages:
                summary.write("\n### Warnings\n\n")
                for message in dict.fromkeys(messages):
                    summary.write(f"- {message}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
