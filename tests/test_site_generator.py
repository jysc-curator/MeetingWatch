import json
from pathlib import Path

from scripts.build_site import build


def _write_data(root: Path, meetings: list[dict]) -> Path:
    data_dir = root / "data"
    data_dir.mkdir()
    (data_dir / "meetings.json").write_text(
        json.dumps(
            {
                "generated_at_utc": "2099-01-01T12:00:00Z",
                "last_checked_mt": "2099-01-01 05:00 MST",
                "meetings": meetings,
            }
        ),
        encoding="utf-8",
    )
    (data_dir / "history.json").write_text(
        json.dumps({"retention_days": 60, "meetings": []}), encoding="utf-8"
    )
    return data_dir


def test_generated_homepage_hides_past_static_records_and_uses_data_timestamp(tmp_path):
    data_dir = _write_data(
        tmp_path,
        [
            {"id": "past", "date": "2020-01-01", "city": "Past City"},
            {"id": "future", "date": "2099-01-02", "city": "Future City"},
        ],
    )
    output_dir = tmp_path / "_site"
    build(data_dir, output_dir)
    page = (output_dir / "index.html").read_text(encoding="utf-8")
    assert "Future City" in page
    assert "Past City" not in page
    assert 'data-run-ts="2099-01-01T12:00:00Z"' in page
    assert "const upcoming=all.filter" in page


def test_structured_briefing_renders_evidence_and_locator(tmp_path):
    data_dir = _write_data(
        tmp_path,
        [
            {
                "id": "future",
                "date": "2099-01-02",
                "city": "Colorado Springs",
                "agenda_briefing_status": "verified",
                "agenda_briefing": {
                    "overview": "Council will consider a major utility bond.",
                    "items": [
                        {
                            "headline": "Utility bond reaches $225 million",
                            "action": "Council will consider issuing up to $225 million in bonds.",
                            "why_it_matters": "The borrowing would finance utility obligations.",
                            "priority": "top",
                            "category": "money",
                            "agenda_item": "8.A",
                            "source_page": 6,
                            "key_facts": ["Up to $225 million"],
                            "evidence": "aggregate principal amount not to exceed $225,000,000",
                        }
                    ],
                    "routine_items": [],
                },
            }
        ],
    )
    output_dir = tmp_path / "_site"
    build(data_dir, output_dir)
    page = (output_dir / "index.html").read_text(encoding="utf-8")
    assert "Utility bond reaches $225 million" in page
    assert "Source evidence" in page
    assert "Agenda item 8.A" in page
    assert "page 6" in page
    assert "Evidence-checked" in page


def test_failed_briefing_is_withheld_instead_of_falling_back(tmp_path):
    data_dir = _write_data(
        tmp_path,
        [
            {
                "id": "future",
                "date": "2099-01-02",
                "city": "Test City",
                "agenda_briefing_status": "quality-gate-failed",
                "agenda_summary": ["An unverified legacy claim"],
            }
        ],
    )
    output_dir = tmp_path / "_site"
    build(data_dir, output_dir)
    page = (output_dir / "index.html").read_text(encoding="utf-8")
    assert "Briefing withheld" in page
    assert "An unverified legacy claim" not in page
