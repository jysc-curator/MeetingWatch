import json

import scraper.summarize as summarizer
from scraper.main import _attach_previous_verified_editorial
from scraper.summarize import SummaryResult


def _meeting(**overrides):
    meeting = {
        "city": "Colorado Springs",
        "meeting_type": "City Council Work Session",
        "date": "2026-10-15",
        "start_time_local": "9:00 AM",
        "status": "Scheduled",
    }
    meeting.update(overrides)
    return meeting


def test_previous_verified_briefing_is_attached_to_same_meeting():
    previous = _meeting(
        agenda_briefing_status="verified",
        agenda_briefing={"overview": "Budget work session.", "items": [{"headline": "Budget"}]},
        agenda_briefing_provenance={"validation": "source-grounded"},
        agenda_summary=["Consider the 2027 budget."],
    )
    current = _meeting(agenda_url="https://example.test/replacement.pdf")

    result = _attach_previous_verified_editorial([current], [previous])

    carried = result[0]["_previous_verified_editorial"]
    assert carried["agenda_briefing_status"] == "verified"
    assert carried["agenda_briefing"]["items"][0]["headline"] == "Budget"


def test_previous_briefing_is_not_attached_to_canceled_meeting():
    previous = _meeting(
        agenda_briefing_status="verified",
        agenda_briefing={"items": [{"headline": "Budget"}]},
    )
    current = _meeting(status="Canceled")

    result = _attach_previous_verified_editorial([current], [previous])

    assert "_previous_verified_editorial" not in result[0]


def test_summarizer_carries_verified_briefing_through_source_outage(
    monkeypatch, tmp_path
):
    prior_briefing = {
        "overview": "Council will discuss the 2027 budget.",
        "items": [
            {
                "headline": "2027 budget work session",
                "action": "Council will discuss the 2027 budget.",
                "why_it_matters": "The discussion shapes spending priorities.",
                "priority": "top",
                "category": "money",
                "agenda_item": "2.A",
                "source_page": 1,
                "key_facts": ["File 26-437"],
                "evidence": "City Council 2027 Budget Work Session",
            }
        ],
        "routine_items": [],
    }
    meeting = _meeting(
        agenda_url="https://example.test/missing.pdf",
        _previous_verified_editorial={
            "agenda_briefing_status": "verified",
            "agenda_briefing": prior_briefing,
            "agenda_briefing_provenance": {
                "status": "verified",
                "validation": "source-grounded",
                "source_url": "https://example.test/prior.pdf",
            },
            "agenda_summary": ["Council will discuss the 2027 budget."],
            "agenda_summary_routine": [],
            "agenda_summary_source": "pdf",
            "agenda_summary_chars": 800,
        },
    )
    input_path = tmp_path / "meetings.json"
    output_dir = tmp_path / "audit"
    input_path.write_text(json.dumps({"meetings": [meeting]}), encoding="utf-8")
    monkeypatch.setattr(
        summarizer,
        "summarize_meeting",
        lambda *_args, **_kwargs: SummaryResult(
            False,
            "source-unavailable",
            "pdf: HTTP 404",
            {},
            "https://example.test/missing.pdf",
            None,
            0,
            None,
            None,
            None,
        ),
    )

    assert summarizer.main(
        ["--input", str(input_path), "--out", str(output_dir)]
    ) == 0

    published = json.loads(input_path.read_text(encoding="utf-8"))["meetings"][0]
    assert published["agenda_briefing_status"] == "verified"
    assert published["agenda_briefing"] == prior_briefing
    assert published["agenda_briefing_provenance"]["freshness"] == "carried-forward"
    assert published["agenda_briefing_provenance"]["source_check_status"] == "source-unavailable"
    assert "_previous_verified_editorial" not in published
