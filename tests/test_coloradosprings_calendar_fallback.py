from datetime import date

from scraper.coloradosprings_legistar import _parse_calendar_fallback


def _row(body: str, meeting_date: str, *, agenda: bool = False, note: str = "") -> str:
    agenda_link = '<a href="View.ashx?M=A&ID=42">Agenda</a>' if agenda else "Not available"
    return f"""
    <tr>
      <td>{body}</td><td>{meeting_date}</td><td>calendar</td><td>9:00 AM</td>
      <td>Council Chambers {note}</td><td>Meeting details</td><td>{agenda_link}</td>
    </tr>
    """


def test_calendar_fallback_keeps_official_agenda_less_dates_across_months():
    html = "<table>" + "".join(
        [
            _row("City Council", "09/22/2026"),
            _row("City Council Work Session", "10/12/2026"),
            _row("City Council", "11/24/2026"),
            _row("City Council", "12/08/2026", agenda=True),
            _row("City Council", "02/10/2027"),
            _row("City Planning Commission", "10/14/2026"),
        ]
    ) + "</table>"

    meetings = _parse_calendar_fallback(
        date(2026, 9, 28),
        date(2027, 1, 26),
        html_pages=[html],
    )

    assert [meeting["date"] for meeting in meetings] == [
        "2026-10-12",
        "2026-11-24",
        "2026-12-08",
    ]
    assert meetings[0]["agenda_url"] is None
    assert meetings[-1]["agenda_url"] == (
        "https://coloradosprings.legistar.com/View.ashx?M=A&ID=42"
    )


def test_calendar_fallback_deduplicates_rows_returned_by_multiple_filtered_pages():
    html = "<table>" + _row("City Council", "10/13/2026") + "</table>"

    meetings = _parse_calendar_fallback(
        date(2026, 9, 28),
        date(2027, 1, 26),
        html_pages=[html, html],
    )

    assert len(meetings) == 1


def test_calendar_fallback_preserves_cancellation_status():
    html = (
        "<table>"
        + _row("City Council Work Session", "10/12/2026", note="This meeting has been cancelled")
        + "</table>"
    )

    meetings = _parse_calendar_fallback(
        date(2026, 9, 28),
        date(2027, 1, 26),
        html_pages=[html],
    )

    assert meetings[0]["status"] == "Canceled"
