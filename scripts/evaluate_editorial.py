"""Run the production editorial contract against local agenda PDFs.

This is a manual evaluation harness; it makes live API calls and never mutates
published datasets. Example:
    python -m scripts.evaluate_editorial tmp/pdfs/*.pdf
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scraper.summarize import (
    SUMMARIZER_MODEL,
    _call_openai,
    _extract_text_from_pdf_bytes,
    _validate_briefing,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdfs", nargs="+", type=Path)
    args = parser.parse_args()
    failed = False
    for path in args.pdfs:
        source = _extract_text_from_pdf_bytes(path.read_bytes())
        raw, method = _call_openai(source, SUMMARIZER_MODEL)
        briefing, errors = _validate_briefing(raw, source)
        result = {
            "file": str(path),
            "model": SUMMARIZER_MODEL,
            "method": method,
            "valid": not errors,
            "errors": errors,
            "briefing": briefing,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        failed = failed or bool(errors)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
