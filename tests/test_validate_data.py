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


def test_verified_editorial_briefing_requires_evidence_and_provenance():
    meetings, history = _payloads()
    meetings["meetings"][0].update(
        {
            "agenda_briefing_status": "verified",
            "agenda_briefing": {
                "overview": "A decision is scheduled.",
                "items": [
                    {
                        "headline": "Decision",
                        "action": "Council will consider it.",
                        "why_it_matters": "It changes city policy.",
                        "evidence": "consider the ordinance",
                        "priority": "top",
                    }
                ],
            },
            "agenda_briefing_provenance": {"validation": "source-grounded"},
        }
    )
    assert validate_payloads(
        meetings, history, now_utc=NOW, max_age_hours=36, min_active=1
    ) == []


def test_unverified_editorial_content_cannot_leak_into_public_data():
    meetings, history = _payloads()
    meetings["meetings"][0].update(
        {
            "agenda_briefing_status": "quality-gate-failed",
            "agenda_summary": ["Unverified claim"],
        }
    )
    errors = validate_payloads(
        meetings, history, now_utc=NOW, max_age_hours=36, min_active=1
    )
    assert any("unverified legacy summary must be empty" in error for error in errors)


def test_source_coverage_counts_and_horizon_are_validated():
    meetings, history = _payloads()
    meetings["meetings"][0]["city"] = "Colorado Springs"
    meetings["source_coverage"] = {
        "policy": {
            "basis": "officially-published-dates-only",
            "horizon_days": 120,
            "inferred_recurring_dates": False,
        },
        "warnings": [],
        "sources": {
            city: {
                "scrape_status": "ok",
                "published_card_count": 1 if city == "Colorado Springs" else 0,
                "agenda_published_count": 0,
                "agenda_pending_count": 1 if city == "Colorado Springs" else 0,
                "scheduled_from": "2026-09-19" if city == "Colorado Springs" else None,
                "scheduled_through": "2026-09-19" if city == "Colorado Springs" else None,
            }
            for city in (
                "Alamosa",
                "Colorado Springs",
                "El Paso County",
                "Pueblo",
                "Salida",
                "Trinidad",
            )
        },
    }

    assert validate_payloads(
        meetings, history, now_utc=NOW, max_age_hours=36, min_active=1
    ) == []

    meetings["source_coverage"]["sources"]["Colorado Springs"][
        "agenda_pending_count"
    ] = 0
    errors = validate_payloads(
        meetings, history, now_utc=NOW, max_age_hours=36, min_active=1
    )
    assert any("agenda_pending_count does not match" in error for error in errors)
