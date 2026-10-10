from datetime import date

import requests
from bs4 import BeautifulSoup

import scraper.trinidad_regular as trinidad


OCTOBER_HTML = """
<html><body>
  <table style="width: 100%; border-top: solid 1px #CCCCCC;">
    <tr>
      <td valign="top" width="40%">10/06/26 Regular Meeting</td>
      <td><a href="Document Center/Agenda &amp; Minutes/Government/2026/10.6.26 Reg Meeting Agenda.pdf?t=123">Agenda</a></td>
    </tr>
  </table>
  <table style="width: 100%; border-top: solid 1px #CCCCCC;">
    <tr>
      <td valign="top" width="40%">07/01/26 Regular Meeting</td>
      <td><a href="old.pdf">Agenda</a></td>
    </tr>
  </table>
</body></html>
"""


def test_parser_backfills_recent_meeting_into_central_history(monkeypatch):
    monkeypatch.setattr(
        trinidad,
        "fetch_year_page",
        lambda year: BeautifulSoup(OCTOBER_HTML, "html.parser") if year == 2026 else None,
    )
    monkeypatch.setattr(trinidad, "summarize_pdf_if_any", lambda _url: [])

    meetings = trinidad.parse_trinidad(today=date(2026, 10, 10))

    assert [meeting["date"] for meeting in meetings] == ["2026-10-06"]
    assert meetings[0]["agenda_url"].endswith(
        "Document%20Center/Agenda%20%26%20Minutes/Government/2026/10.6.26%20Reg%20Meeting%20Agenda.pdf?t=123"
    )


def test_fetch_uses_non_www_official_fallback_and_browser_headers(monkeypatch):
    calls = []

    class Response:
        def __init__(self, status_code, text=""):
            self.status_code = status_code
            self.text = text

        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.HTTPError(f"HTTP {self.status_code}")

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        if "www.trinidad.co.gov" in url:
            return Response(403)
        return Response(200, OCTOBER_HTML)

    monkeypatch.setattr(trinidad.requests, "get", fake_get)

    soup = trinidad.fetch_year_page(2026)

    assert soup is not None
    assert len(calls) == 2
    assert calls[1][0].startswith("https://trinidad.co.gov/")
    assert "Mozilla/5.0" in calls[0][1]["headers"]["User-Agent"]


def test_current_year_source_failure_is_not_reported_as_zero_meetings(monkeypatch):
    monkeypatch.setattr(trinidad, "fetch_year_page", lambda _year: None)

    try:
        trinidad.parse_trinidad(today=date(2026, 10, 10))
    except RuntimeError as exc:
        assert "agenda page is unavailable" in str(exc)
    else:
        raise AssertionError("Expected a source failure to propagate")
