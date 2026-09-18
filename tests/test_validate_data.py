from datetime import datetime, timezone

from scripts.validate_data import validate_payloads


NOW = datetime(2026, 9, 18, 18, 0, tzinfo=timezone.utc)


def _payloads():
    meetings = {
        "generated_at_utc": "2026-09-18T17:30:00Z",
        "meetings": [{"id": "future", "date": "2026-09-19"}],
    }
    history = {
        "generated_at_utc": "2026-09-18T17:30:00Z",
        "retention_days": 60,
        "meetings": [{"id": "past", "date": "2026-09-17"}],
    }
    return meetings, history


def test_valid_payloads_pass():
    meetings, history = _payloads()

    assert validate_payloads(
        meetings, history, now_utc=NOW, max_age_hours=36, min_active=1
    ) == []


def test_stale_data_and_past_active_meeting_fail():
    meetings, history = _payloads()
    meetings["generated_at_utc"] = "2026-09-15T17:30:00Z"
    meetings["meetings"][0]["date"] = "2026-09-17"

    errors = validate_payloads(
        meetings, history, now_utc=NOW, max_age_hours=36, min_active=1
    )

    assert any("data is stale" in error for error in errors)
    assert any("is past" in error for error in errors)


def test_invalid_dates_and_expired_history_fail():
    meetings, history = _payloads()
    meetings["meetings"][0]["date"] = ""
    history["meetings"][0]["date"] = "2026-06-01"

    errors = validate_payloads(
        meetings, history, now_utc=NOW, max_age_hours=36, min_active=1
    )

    assert any("missing/invalid date" in error for error in errors)
    assert any("exceeds 60-day retention" in error for error in errors)
