import json
from datetime import datetime, timezone
from pathlib import Path

from .utils import now_mt

RETENTION_DAYS = 60
SCHEDULE_HORIZON_DAYS = 120
SOURCE_CITIES = (
    "Alamosa",
    "Colorado Springs",
    "El Paso County",
    "Pueblo",
    "Salida",
    "Trinidad",
)


def _parse_date(date_str: str):
    try:
        return datetime.strptime(str(date_str or "").strip(), "%Y-%m-%d").date()
    except Exception:
        return None


def _meeting_key(meeting: dict) -> str:
    mid = str(meeting.get("id") or "").strip()
    if mid:
        return f"id:{mid}"
    city = str(meeting.get("city") or "").strip().lower()
    body = str(meeting.get("body") or "").strip().lower()
    meeting_type = str(meeting.get("meeting_type") or "").strip().lower()
    date = str(meeting.get("date") or "").strip()
    time = str(meeting.get("start_time_local") or "").strip().lower()
    source = str(meeting.get("source") or "").strip().lower()
    return f"fallback:{city}|{body}|{meeting_type}|{date}|{time}|{source}"


def _load_meetings(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        meetings = payload.get("meetings")
        return meetings if isinstance(meetings, list) else []
    except Exception:
        return []


def _load_history(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        meetings = payload.get("meetings")
        return meetings if isinstance(meetings, list) else []
    except Exception:
        return []


def _split_active_and_expired(meetings: list[dict], today):
    active = []
    expired = []
    for meeting in meetings:
        mdate = _parse_date(meeting.get("date"))
        if mdate is None:
            print(f"Skipping meeting with missing/invalid date: {_meeting_key(meeting)}")
            continue
        if mdate < today:
            expired.append(meeting)
        else:
            active.append(meeting)
    return active, expired


def _apply_schedule_horizon(
    meetings: list[dict], *, today, horizon_days: int = SCHEDULE_HORIZON_DAYS
) -> list[dict]:
    """Keep the public upcoming feed useful while honoring source-published dates."""
    horizon = today.fromordinal(today.toordinal() + horizon_days)
    return [
        meeting
        for meeting in meetings
        if (mdate := _parse_date(meeting.get("date"))) is not None
        and today <= mdate <= horizon
    ]


def _source_regression_warnings(
    *, new_active: list[dict], previous_active: list[dict], today
) -> list[str]:
    """Describe suspicious source contractions without inventing replacement meetings."""
    warnings = []
    horizon = today.fromordinal(today.toordinal() + SCHEDULE_HORIZON_DAYS)
    for city in SOURCE_CITIES:
        fresh_dates = [
            parsed
            for meeting in new_active
            if str(meeting.get("city") or "").strip() == city
            and (parsed := _parse_date(meeting.get("date"))) is not None
            and today <= parsed <= horizon
        ]
        previous_dates = [
            parsed
            for meeting in previous_active
            if str(meeting.get("city") or "").strip() == city
            and (parsed := _parse_date(meeting.get("date"))) is not None
            and today <= parsed <= horizon
        ]

        if previous_dates and not fresh_dates:
            warnings.append(
                f"{city}: fresh scrape returned no upcoming meetings; previous data reached "
                f"{max(previous_dates).isoformat()}"
            )
            continue

        # A schedule may naturally roll forward, but it should not silently lose
        # already published dates well inside the public 120-day window.
        if fresh_dates and previous_dates and max(fresh_dates) < max(previous_dates):
            missing_horizon = max(previous_dates)
            if missing_horizon >= today.fromordinal(today.toordinal() + 7):
                warnings.append(
                    f"{city}: published schedule horizon contracted from "
                    f"{missing_horizon.isoformat()} to {max(fresh_dates).isoformat()}"
                )
    return warnings


def _build_source_coverage(
    *, meetings: list[dict], scrape_status: dict[str, dict], warnings: list[str]
) -> dict:
    """Publish a machine-readable audit of each source's observed schedule horizon."""
    sources = {}
    for city in SOURCE_CITIES:
        city_meetings = [
            meeting
            for meeting in meetings
            if str(meeting.get("city") or "").strip() == city
        ]
        dates = sorted(
            parsed.isoformat()
            for meeting in city_meetings
            if (parsed := _parse_date(meeting.get("date"))) is not None
        )
        agenda_count = sum(bool(meeting.get("agenda_url")) for meeting in city_meetings)
        status = scrape_status.get(city, {"status": "not-run", "discovered": 0})
        sources[city] = {
            "scrape_status": status.get("status", "not-run"),
            "fresh_records_discovered": int(status.get("discovered") or 0),
            "published_card_count": len(city_meetings),
            "agenda_published_count": agenda_count,
            "agenda_pending_count": len(city_meetings) - agenda_count,
            "scheduled_from": dates[0] if dates else None,
            "scheduled_through": dates[-1] if dates else None,
        }
    return {
        "policy": {
            "basis": "officially-published-dates-only",
            "horizon_days": SCHEDULE_HORIZON_DAYS,
            "inferred_recurring_dates": False,
        },
        "warnings": warnings,
        "sources": sources,
    }


def _dedupe_keep_latest(meetings: list[dict]) -> list[dict]:
    deduped = {}
    for meeting in meetings:
        deduped[_meeting_key(meeting)] = meeting
    return list(deduped.values())


def _apply_retention(meetings: list[dict], cutoff, today):
    kept = []
    for meeting in meetings:
        mdate = _parse_date(meeting.get("date"))
        if mdate is None:
            continue
        if cutoff <= mdate < today:
            kept.append(meeting)
    return kept


def _preserve_upcoming_salida_on_scrape_gaps(
    *,
    new_active: list[dict],
    previous_active: list[dict],
    today,
    horizon_days: int = 10,
) -> list[dict]:
    """
    Keep near-term upcoming Salida meetings from previous active data if
    a scrape gap causes Salida to disappear in a fresh run.
    """
    has_salida_new = any(str(m.get("city") or "").strip().lower() == "salida" for m in new_active)
    if has_salida_new:
        return new_active

    new_keys = {_meeting_key(m) for m in new_active}
    horizon = today.fromordinal(today.toordinal() + horizon_days)

    carried = []
    for m in previous_active:
        city = str(m.get("city") or "").strip().lower()
        if city != "salida":
            continue
        mdate = _parse_date(m.get("date"))
        if mdate is None:
            continue
        if not (today <= mdate <= horizon):
            continue
        if _meeting_key(m) in new_keys:
            continue
        preserved = dict(m)
        preserved["stale_from_previous_run"] = True
        carried.append(preserved)

    if carried:
        return new_active + carried
    return new_active


def run():
    from .coloradosprings_legistar import parse_legistar
    from .epc_agendasuite import parse_bocc
    from .pueblo_civicclerk import parse_pueblo
    from .trinidad_regular import parse_trinidad
    from .alamosa_diligent import parse_alamosa
    from .salida_civicclerk import parse_salida

    meetings = []
    scrape_status: dict[str, dict] = {}
    scrapers = (
        ("Colorado Springs", "Legistar", parse_legistar),
        ("El Paso County", "BOCC", parse_bocc),
        ("Pueblo", "Pueblo", parse_pueblo),
        ("Trinidad", "Trinidad", parse_trinidad),
        ("Alamosa", "Alamosa", parse_alamosa),
        ("Salida", "Salida", parse_salida),
    )
    for city, label, scraper in scrapers:
        try:
            discovered = scraper()
            meetings.extend(discovered)
            scrape_status[city] = {"status": "ok", "discovered": len(discovered)}
        except Exception as exc:
            print(f"{label} error:", exc)
            scrape_status[city] = {"status": "error", "discovered": 0}

    repo_root = Path(__file__).resolve().parents[1]
    data_dir = repo_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    out_path = data_dir / "meetings.json"
    history_path = data_dir / "history.json"

    checked_mt = now_mt()
    generated_at_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    today_mt = checked_mt.date()
    cutoff_date = today_mt.fromordinal(today_mt.toordinal() - RETENTION_DAYS)

    previous_active = _load_meetings(out_path)
    existing_history = _load_history(history_path)

    active_from_new, expired_from_new = _split_active_and_expired(meetings, today_mt)
    _, expired_from_previous = _split_active_and_expired(previous_active, today_mt)

    active_from_new = _apply_schedule_horizon(active_from_new, today=today_mt)
    coverage_warnings = _source_regression_warnings(
        new_active=active_from_new,
        previous_active=previous_active,
        today=today_mt,
    )
    for warning in coverage_warnings:
        print(f"Source coverage warning: {warning}")

    active_from_new = _preserve_upcoming_salida_on_scrape_gaps(
        new_active=active_from_new,
        previous_active=previous_active,
        today=today_mt,
    )

    history_combined = existing_history + expired_from_previous + expired_from_new
    history_deduped = _dedupe_keep_latest(history_combined)
    history_kept = _apply_retention(history_deduped, cutoff_date, today_mt)
    history_kept.sort(key=lambda m: (str(m.get("date") or ""), str(m.get("city") or ""), str(m.get("meeting_type") or "")), reverse=True)

    active_deduped = _dedupe_keep_latest(active_from_new)
    active_deduped.sort(key=lambda m: (str(m.get("date") or ""), str(m.get("city") or ""), str(m.get("meeting_type") or "")))

    out = {
        "generated_at_utc": generated_at_utc,
        "last_checked_mt": checked_mt.strftime("%Y-%m-%d %H:%M %Z"),
        "source_coverage": _build_source_coverage(
            meetings=active_deduped,
            scrape_status=scrape_status,
            warnings=coverage_warnings,
        ),
        "meetings": active_deduped,
    }

    history_out = {
        "generated_at_utc": generated_at_utc,
        "last_archived_mt": checked_mt.strftime("%Y-%m-%d %H:%M %Z"),
        "retention_days": RETENTION_DAYS,
        "meetings": history_kept,
    }

    out_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    history_path.write_text(json.dumps(history_out, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {len(active_deduped)} active meetings to {out_path}")
    print(f"Wrote {len(history_kept)} archived meetings to {history_path} (retention {RETENTION_DAYS} days)")


if __name__ == "__main__":
    run()
