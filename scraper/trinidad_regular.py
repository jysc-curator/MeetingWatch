# scraper/trinidad_regular.py
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from urllib.parse import urljoin, quote

import requests
from bs4 import BeautifulSoup

from .utils import make_meeting, summarize_pdf_if_any, MT_TZ

# --- Constants ---
# The correct base URL for PDFs, found via browser redirection
BASE_PDF_URL = "https://cms2.revize.com/revize/trinidadco/" 
# The public-facing page where the links are found
BASE_PAGE_URL = "https://www.trinidad.co.gov/government/agendas___minutes/" 
PAGE_BASE_URLS = (
    BASE_PAGE_URL,
    "https://trinidad.co.gov/government/agendas___minutes/",
)
MEETING_TYPE = "City Council Regular Meeting"
HISTORY_LOOKBACK_DAYS = 60
PAGE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "Chrome/140.0.0.0 Safari/537.36 MeetingWatch/2.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# --- Logging ---
log = logging.getLogger(__name__)
if not log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))
    log.addHandler(_h)
log.propagate = False
log.setLevel(logging.INFO)

# --- Scraper ---
def fetch_year_page(year: int) -> BeautifulSoup | None:
    """Fetch an agenda year through either official hostname."""
    errors = []
    for base_url in PAGE_BASE_URLS:
        url = f"{base_url}{year}.php"
        try:
            response = requests.get(url, timeout=30, headers=PAGE_HEADERS)
            if response.status_code == 404:
                log.info(f"Trinidad has not published an agenda page for {year}")
                return None
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except requests.RequestException as exc:
            errors.append(f"{url}: {exc}")

    log.error("Failed to fetch Trinidad agenda page via official hosts: " + "; ".join(errors))
    return None


def parse_trinidad(today: date | None = None) -> list[dict]:
    """
    Scrapes the Trinidad agendas___minutes list page for regular council meetings.
    This replaces the previous calendar-based scraper.
    """
    meetings = []
    today = today or datetime.now(MT_TZ).date()
    cutoff = today - timedelta(days=HISTORY_LOOKBACK_DAYS)

    log.info(f"Scraping Trinidad agendas for {today.year}")
    current_soup = fetch_year_page(today.year)
    if current_soup is None:
        raise RuntimeError(f"Trinidad's {today.year} agenda page is unavailable")

    year_pages = [(today.year, current_soup)]
    optional_years = []
    if cutoff.year != today.year:
        optional_years.append(cutoff.year)
    optional_years.append(today.year + 1)
    for year in optional_years:
        log.info(f"Scraping Trinidad agendas for {year}")
        soup = fetch_year_page(year)
        if soup:
            year_pages.append((year, soup))

    for year, soup in year_pages:
        # Find all tables that look like meeting containers
        tables = soup.find_all("table", style=lambda s: s and "width: 100%" in s)

        for table in tables:
            # Extract date and title text
            info_cell = table.find("td", {"valign": "top", "width": "40%"})
            if not info_cell:
                continue
            
            info_text = " ".join(info_cell.stripped_strings)
            info_match = re.match(
                r"^(?P<date>\d{1,2}/\d{1,2}/\d{2,4})\s+(?P<name>.+)$",
                info_text,
            )
            if not info_match:
                continue

            date_str = info_match.group("date")
            meeting_name = info_match.group("name")

            # Filter for regular meetings
            if "regular meeting" not in meeting_name.lower():
                continue

            # Parse date
            try:
                meeting_date = datetime.strptime(date_str, "%m/%d/%y").date()
            except ValueError:
                log.warning(f"Could not parse date: {date_str}")
                continue

            # Include recent past meetings so a late post or transient source
            # failure can still be repaired through the central history archive.
            if meeting_date < cutoff:
                continue

            # Find agenda link
            agenda_link_tag = table.find("a", string=lambda s: s and "agenda" in s.lower())
            if not agenda_link_tag or not agenda_link_tag.has_attr("href"):
                continue

            href = agenda_link_tag["href"]

            # URL-encode the path part of the href, including any spaces in the filename.
            # The server appears to expect filenames with spaces in them, so we do not sanitize.
            path_part, *query_part = href.split('?', 1)
            safe_path = quote(path_part.strip())
            safe_href = '?'.join([safe_path] + query_part)

            agenda_url = urljoin(BASE_PDF_URL, safe_href)
            
            summary = summarize_pdf_if_any(agenda_url)
            
            source_page_url = f"{BASE_PAGE_URL}{year}.php"

            # Create meeting object
            meeting = make_meeting(
                city_or_body="Trinidad",
                meeting_type=MEETING_TYPE,
                date=meeting_date.isoformat(),
                start_time_local="6:00 PM",  # Time is not on the page, using a reasonable default
                status="Scheduled",
                location="City Council Chambers, City Hall (Trinidad, CO)",
                agenda_url=agenda_url,
                agenda_summary=summary,
                source=source_page_url,
            )
            meetings.append(meeting)

    log.info(f"Found {len(meetings)} recent/upcoming regular meetings for Trinidad.")
    return meetings

if __name__ == "__main__":
    import json
    print(json.dumps(parse_trinidad(), indent=2))
