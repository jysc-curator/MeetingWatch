from datetime import date

from scraper.main import _preserve_upcoming_on_scrape_errors


def test_failed_source_keeps_previously_published_upcoming_meeting():
    previous = [
        {
            "city": "Trinidad",
            "meeting_type": "City Council Regular Meeting",
            "date": "2026-10-06",
            "start_time_local": "6:00 PM",
            "source": "https://www.trinidad.co.gov/agendas",
        }
    ]

    merged = _preserve_upcoming_on_scrape_errors(
        new_active=[],
        previous_active=previous,
        scrape_status={"Trinidad": {"status": "error", "discovered": 0}},
        today=date(2026, 10, 5),
    )

    assert len(merged) == 1
    assert merged[0]["stale_from_previous_run"] is True
    assert merged[0]["stale_reason"] == "source scrape failed"


def test_successful_empty_source_does_not_preserve_removed_meeting():
    previous = [
        {
            "city": "Trinidad",
            "meeting_type": "City Council Regular Meeting",
            "date": "2026-10-06",
            "start_time_local": "6:00 PM",
            "source": "https://www.trinidad.co.gov/agendas",
        }
    ]

    merged = _preserve_upcoming_on_scrape_errors(
        new_active=[],
        previous_active=previous,
        scrape_status={"Trinidad": {"status": "ok", "discovered": 0}},
        today=date(2026, 10, 5),
    )

    assert merged == []
