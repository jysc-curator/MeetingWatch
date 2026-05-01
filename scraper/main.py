import json
from datetime import datetime
from pathlib import Path

from .utils import now_mt

RETENTION_DAYS = 60


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
            active.append(meeting)
            continue
        if mdate < today:
            expired.append(meeting)
        else:
            active.append(meeting)
    return active, expired


def _dedupe_keep_latest(meetings: list[dict]) -> list[dict]:
    deduped = {}
    for meeting in meetings:
        deduped[_meeting_key(meeting)] = meeting
    return list(deduped.values())


def _apply_retention(meetings: list[dict], cutoff, today):
    kept = []
    for meeting in meetings:
        mdate = _parse_date(meeting.get("date"))
        # History should include only past meetings within retention window.
        # Exclude future/today records from history.
        if mdate is None:
            kept.append(meeting)
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
    try:
        meetings.extend(parse_legistar())
    except Exception as e:
        print("Legistar error:", e)
    try:
        meetings.extend(parse_bocc())
    except Exception as e:
        print("BOCC error:", e)
    try:
        meetings.extend(parse_pueblo())
    except Exception as e:
        print("Pueblo error:", e)
    try:
        meetings.extend(parse_trinidad())
    except Exception as e:
        print("Trinidad error:", e)
    try:
        meetings.extend(parse_alamosa())
    except Exception as e:
        print("Alamosa error:", e)
    try:
        meetings.extend(parse_salida())
    except Exception as e:
        print("Salida error:", e)

    repo_root = Path(__file__).resolve().parents[1]
    data_dir = repo_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    out_path = data_dir / "meetings.json"
    history_path = data_dir / "history.json"

    today_mt = now_mt().date()
    cutoff_date = today_mt.fromordinal(today_mt.toordinal() - RETENTION_DAYS)

    previous_active = _load_meetings(out_path)
    existing_history = _load_history(history_path)

    active_from_new, expired_from_new = _split_active_and_expired(meetings, today_mt)
    _, expired_from_previous = _split_active_and_expired(previous_active, today_mt)

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
        "last_checked_mt": now_mt().strftime("%Y-%m-%d %H:%M"),
        "meetings": active_deduped,
    }

    history_out = {
        "last_archived_mt": now_mt().strftime("%Y-%m-%d %H:%M"),
        "retention_days": RETENTION_DAYS,
        "meetings": history_kept,
    }

    out_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    history_path.write_text(json.dumps(history_out, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {len(active_deduped)} active meetings to {out_path}")
    print(f"Wrote {len(history_kept)} archived meetings to {history_path} (retention {RETENTION_DAYS} days)")


if __name__ == "__main__":
    run()
