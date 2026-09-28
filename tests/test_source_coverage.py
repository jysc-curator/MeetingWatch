from datetime import date

from scraper.main import (
    SOURCE_CITIES,
    _apply_schedule_horizon,
    _build_source_coverage,
    _source_regression_warnings,
)


def test_global_schedule_horizon_keeps_only_next_120_days():
    meetings = [
        {"city": "Pueblo", "date": "2026-09-28"},
        {"city": "Pueblo", "date": "2027-01-26"},
        {"city": "Pueblo", "date": "2027-01-27"},
    ]

    kept = _apply_schedule_horizon(meetings, today=date(2026, 9, 28))

    assert [meeting["date"] for meeting in kept] == ["2026-09-28", "2027-01-26"]


def test_coverage_records_agenda_pending_and_observed_horizon():
    meetings = [
        {"city": "Colorado Springs", "date": "2026-10-12", "agenda_url": None},
        {
            "city": "Colorado Springs",
            "date": "2026-10-13",
            "agenda_url": "https://example.com/agenda.pdf",
        },
    ]
    statuses = {
        city: {"status": "ok", "discovered": 0}
        for city in SOURCE_CITIES
    }
    statuses["Colorado Springs"]["discovered"] = 2

    coverage = _build_source_coverage(
        meetings=meetings,
        scrape_status=statuses,
        warnings=[],
    )
    springs = coverage["sources"]["Colorado Springs"]

    assert coverage["policy"]["horizon_days"] == 120
    assert springs["published_card_count"] == 2
    assert springs["agenda_published_count"] == 1
    assert springs["agenda_pending_count"] == 1
    assert springs["scheduled_through"] == "2026-10-13"


def test_coverage_warns_when_a_previously_published_schedule_disappears():
    warnings = _source_regression_warnings(
        new_active=[],
        previous_active=[{"city": "Colorado Springs", "date": "2026-12-08"}],
        today=date(2026, 9, 28),
    )

    assert warnings == [
        "Colorado Springs: fresh scrape returned no upcoming meetings; previous data reached 2026-12-08"
    ]
