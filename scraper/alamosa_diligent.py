# scraper/alamosa_diligent.py
from __future__ import annotations

import os
from datetime import datetime, date
from zoneinfo import ZoneInfo
import re
from typing import List, Dict, Optional
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright, Page, BrowserContext

from .utils import make_meeting, summarize_pdf_if_any

PORTAL_URL = "https://cityofalamosa.community.diligentoneplatform.com/Portal/MeetingSchedule.aspx"
ALAMOSA_TZ = "America/Denver"
WANTED_TYPES = ("CITY COUNCIL REGULAR MEETING", "CITY COUNCIL SPECIAL MEETING", "CITY COUNCIL WORK SESSION")


def _parse_date_token(text: str) -> Optional[date]:
    candidates = [
        "%b %d %Y", "%b %d, %Y",
        "%B %d %Y", "%B %d, %Y",
    ]
    for fmt in candidates:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_sidebar_meeting_text(raw_text: str) -> Optional[Dict]:
    """
    Parse a non-linked sidebar meeting entry (agenda not yet posted) into a card.
    """
    txt = _norm_space(raw_text)
    up = txt.upper()

    mtg_type = None
    for t in WANTED_TYPES:
        if t in up:
            mtg_type = t.title()
            break
    if not mtg_type:
        return None

    m = re.search(r"\b([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})\b", txt)
    if not m:
        return None
    date_obj = _parse_date_token(m.group(1))
    if not date_obj or date_obj < _today_denver():
        return None

    tm = re.search(r"\b(\d{1,2}:\d{2}\s*[AP]M)\b", txt, re.I)
    time_str = _norm_space(tm.group(1)).upper() if tm else None

    slug_type = re.sub(r"[^a-z0-9]+", "-", mtg_type.lower()).strip("-")
    source = f"{PORTAL_URL}#nolink-{date_obj.isoformat()}-{slug_type}"

    return make_meeting(
        city_or_body="Alamosa",
        meeting_type=mtg_type,
        date=date_obj.isoformat(),
        start_time_local=time_str,
        status="Scheduled",
        location=None,
        agenda_url=None,
        agenda_summary=[],
        source=source,
    )


def _today_denver() -> date:
    return datetime.now(ZoneInfo(ALAMOSA_TZ)).date()


def _norm_space(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _parse_meeting_detail_page(context: BrowserContext, meeting_url: str) -> Optional[Dict]:
    """
    Parses a specific meeting detail page in a new, isolated page (tab).
    """
    page = None
    try:
        page = context.new_page()
        print(f"[alamosa] Parsing detail page: {meeting_url}")
        page.goto(meeting_url, wait_until="networkidle")

        header_el = page.locator("h2#ctl00_MainContent_MeetingTitle").first
        # Explicitly wait for the header to be visible before reading it
        header_el.wait_for(timeout=10000)
        
        header_text = _norm_space(header_el.inner_text()).upper()

        mtg_type = None
        for t in WANTED_TYPES:
            if t in header_text:
                mtg_type = t.title()
                break
        if not mtg_type:
            print(f"[alamosa] Skipping: Meeting type '{header_text}' not in WANTED_TYPES.")
            return None

        date_match = re.search(r"-\s+([A-Z]{3}\s+\d{1,2}\s+\d{4})$", header_text)
        if not date_match:
            print(f"[alamosa] Skipping: Could not parse date from header: {header_text}")
            return None
        
        try:
            date_obj = datetime.strptime(date_match.group(1), "%b %d %Y").date()
        except ValueError:
            print(f"[alamosa] Skipping: Could not parse date string from header: '{date_match.group(1)}'")
            return None

        if date_obj < _today_denver():
            print(f"[alamosa] Skipping: Past meeting from {date_obj.isoformat()}")
            return None

        time_el = page.locator("span#meeting-time").first
        time_str = _norm_space(time_el.inner_text()) if time_el.is_visible() else None

        loc_el = page.locator("span#meeting-location").first
        location_str = _norm_space(loc_el.inner_text()) if loc_el.is_visible() else None

        pdf_url, summary = None, []
        pdf_link_el = page.locator("a#document-cover-pdf[href]").first
        if pdf_link_el.is_visible():
            pdf_href = pdf_link_el.get_attribute("href")
            if pdf_href:
                pdf_url = urljoin(page.url, pdf_href)
                print(f"[alamosa] Found agenda PDF: {pdf_url}")
                summary = summarize_pdf_if_any(pdf_url) or []
                if summary:
                    print(f"[alamosa] Successfully generated {len(summary)} summary bullets.")

        return make_meeting(
            city_or_body="Alamosa",
            meeting_type=mtg_type,
            date=date_obj.isoformat(),
            start_time_local=time_str,
            status="Scheduled",
            location=location_str,
            agenda_url=pdf_url,
            agenda_summary=summary,
            source=meeting_url,
        )
    except Exception as e:
        print(f"[alamosa] Error parsing detail page {meeting_url}: {e}")
        return None
    finally:
        if page:
            page.close()


def parse_alamosa() -> List[Dict]:
    """
    Entry point for Alamosa scraper. Finds links on the main schedule page,
    then scrapes each one in a new page context.
    """
    print(f"[alamosa] starting; url: {PORTAL_URL}")
    items: List[Dict] = []
    
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(30000)

        try:
            print(f"[alamosa] Navigating to {PORTAL_URL}")
            page.goto(PORTAL_URL, wait_until="networkidle")

            page.wait_for_selector("#ctl00_RightSidebar", timeout=20000)

            # Collect sidebar meeting entries from all buckets.
            row_selector = "#ctl00_UpcomingMeetings li, #ctl00_RecentMeetings li, #ctl00_TodaysMeetings li"
            rows = page.locator(row_selector).all()
            print(f"[alamosa] Found {len(rows)} sidebar meeting row(s).")

            detail_urls: List[str] = []
            no_link_items: List[Dict] = []

            for row in rows:
                row_text = _norm_space(row.inner_text() or "")
                if not row_text:
                    continue

                a = row.locator("a[href]").first
                href = a.get_attribute("href") if a.count() > 0 else None
                if href:
                    detail_urls.append(urljoin(page.url, href))
                else:
                    parsed = _parse_sidebar_meeting_text(row_text)
                    if parsed:
                        no_link_items.append(parsed)

            detail_urls = list(dict.fromkeys(detail_urls))
            print(f"[alamosa] Found {len(detail_urls)} unique detail URL(s); {len(no_link_items)} no-link upcoming item(s).")

            for url in detail_urls:
                meeting_item = _parse_meeting_detail_page(context, url)
                if meeting_item:
                    items.append(meeting_item)

            items.extend(no_link_items)

        except Exception as e:
            print(f"[alamosa] A critical error occurred during main page scraping: {e}")
        finally:
            if browser.is_connected():
                browser.close()

    # Deduplicate by meeting identity; prefer entries that have an agenda/source detail URL.
    by_key: Dict[tuple, Dict] = {}
    for item in items:
        key = (
            item.get("date") or "",
            item.get("meeting_type") or "",
            item.get("start_time_local") or "",
        )
        prev = by_key.get(key)
        if not prev:
            by_key[key] = item
            continue
        prev_has_agenda = bool(prev.get("agenda_url"))
        curr_has_agenda = bool(item.get("agenda_url"))
        if curr_has_agenda and not prev_has_agenda:
            by_key[key] = item
        elif (not prev.get("source") or "#nolink-" in str(prev.get("source"))) and item.get("source") and "#nolink-" not in str(item.get("source")):
            by_key[key] = item

    final_items = list(by_key.values())
    sorted_items = sorted(final_items, key=lambda d: (d.get("date") or "9999-12-31", d.get("meeting_type") or ""))
    
    print(f"[alamosa] produced {len(sorted_items)} item(s)")
    return sorted_items
