from datetime import date

from scraper.main import (
    _split_active_and_expired,
    _dedupe_keep_latest,
    _apply_retention,
)


def test_split_active_and_expired_by_date():
    meetings = [
        {"id": "past", "date": "2026-01-01", "city": "A", "meeting_type": "Council"},
        {"id": "today", "date": "2026-04-02", "city": "A", "meeting_type": "Council"},
        {"id": "future", "date": "2026-04-10", "city": "A", "meeting_type": "Council"},
        {"id": "unknown", "date": "", "city": "A", "meeting_type": "Council"},
    ]

    active, expired = _split_active_and_expired(meetings, date(2026, 4, 2))

    assert {m["id"] for m in active} == {"today", "future", "unknown"}
    assert {m["id"] for m in expired} == {"past"}


def test_dedupe_keep_latest_prefers_last_value_for_same_id():
    meetings = [
        {"id": "same", "date": "2026-03-01", "city": "A", "meeting_type": "Council", "status": "Scheduled"},
        {"id": "same", "date": "2026-03-01", "city": "A", "meeting_type": "Council", "status": "Completed"},
    ]

    deduped = _dedupe_keep_latest(meetings)

    assert len(deduped) == 1
    assert deduped[0]["status"] == "Completed"


def test_retention_drops_meetings_older_than_cutoff():
    meetings = [
        {"id": "drop", "date": "2026-01-01", "city": "A", "meeting_type": "Council"},
        {"id": "keep", "date": "2026-03-01", "city": "A", "meeting_type": "Council"},
        {"id": "unknown", "date": "", "city": "A", "meeting_type": "Council"},
    ]

    kept = _apply_retention(meetings, date(2026, 2, 1))

    assert {m["id"] for m in kept} == {"keep", "unknown"}
