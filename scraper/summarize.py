# scraper/summarize.py
from __future__ import annotations

import argparse
import json
import os
import re
import textwrap
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

# ---------------------------
# Config via environment
# ---------------------------
MAX_BULLETS = int(os.getenv("PDF_SUMMARY_MAX_BULLETS", "12"))
DEFAULT_MAX_PAGES = int(os.getenv("PDF_SUMMARY_MAX_PAGES", "20"))  # kept for compatibility
DEFAULT_MAX_CHARS = int(os.getenv("PDF_SUMMARY_MAX_CHARS", "50000"))
SUMMARIZER_MODEL = os.getenv("SUMMARIZER_MODEL", "gpt-4o-mini")
DEBUG = os.getenv("PDF_SUMMARY_DEBUG", "0") == "1"

UA = {"User-Agent": "MeetingWatch/1.0 (+https://github.com/human83/MeetingWatch)"}

# ---------------------------
# Utilities
# ---------------------------

# Optional city-level term overrides (JSON string):
# {
#   "Pueblo": {"keep": ["urban renewal"], "drop": ["proclamation"]},
#   "Colorado Springs": {"keep": ["annexation"], "drop": ["ceremonial"]}
# }
_CITY_TERM_OVERRIDES_RAW = os.getenv("CITY_SUMMARY_TERM_OVERRIDES_JSON", "").strip()
try:
    CITY_SUMMARY_TERM_OVERRIDES = json.loads(_CITY_TERM_OVERRIDES_RAW) if _CITY_TERM_OVERRIDES_RAW else {}
except Exception:
    CITY_SUMMARY_TERM_OVERRIDES = {}


def _city_term_override(city: str) -> Tuple[List[str], List[str]]:
    cfg = CITY_SUMMARY_TERM_OVERRIDES.get(city) if isinstance(CITY_SUMMARY_TERM_OVERRIDES, dict) else None
    if not isinstance(cfg, dict):
        return [], []
    keep = [str(x).strip().lower() for x in (cfg.get("keep") or []) if str(x).strip()]
    drop = [str(x).strip().lower() for x in (cfg.get("drop") or []) if str(x).strip()]
    return keep, drop


def _log(msg: str) -> None:
    print(f"[summarize] {msg}", flush=True)

def _slugify(s: str, length: int = 80) -> str:
    s = re.sub(r"\s+", "-", (s or "").strip().lower())
    s = re.sub(r"[^a-z0-9\-_.]+", "", s)
    return s[:length] or "meeting"

def _looks_like_pdf(resp: requests.Response) -> bool:
    ct = (resp.headers.get("Content-Type") or "").lower()
    if "application/pdf" in ct:
        return True
    try:
        return resp.content[:5].startswith(b"%PDF-")
    except Exception:
        return False

def _normalize_ws(text: str) -> str:
    return re.sub(r"[ \t]+\n", "\n", re.sub(r"\r\n?", "\n", text))
    
_BULLET_PREFIX_RE = re.compile(r"^\s*[•\-\*\u2022]\s*")

def _strip_leading_bullet(s: str) -> str:
    # remove any leading bullet-like marker and surrounding spaces
    return _BULLET_PREFIX_RE.sub("", s or "").strip()

_BOILERPLATE_PATTERNS = [
    re.compile(p, re.I)
    for p in [
        r"\bpledge of allegiance\b",
        r"\bcall to order\b",
        r"\broll call\b",
        r"\bapproval of (the )?(agenda|minutes)\b",
        r"\bminutes of (the )?(previous|last) meeting\b",
        r"\bpublic comment(s)?\b",
        r"\badjourn(ment)?\b",
        r"\bconsent calendar\b",
        r"\bagenda items? are subject to change\b",
        r"\bsubject to change in order and timing\b",
        r"\bsubmit comments? on agenda items? via email\b",
        r"\bmeeting will be broadcast live\b",
        r"\bchannel\s*18\b",
        r"\bfacebook live\b",
        r"\bauxiliary aids\b",
        r"\brequest (them|accommodations?) at least\s*\d+\s*hours in advance\b",
        r"\binvocation\b",
        r"\bagenda will be reviewed and approved\b",
        r"\baddendum (to the )?agenda\b",
        r"\bdepartment and committee reports?\b",
        r"\bnon-action items?\b",
        r"\bcouncilmembers? .*open discussion\b",
        r"\belected officials? will provide comments\b",
        r"\bagenda includes a public forum\b",
        r"\bpublic forum for community input\b",
        r"\bchanges? to the agenda will be addressed\b",
        r"\bitems under study will be discussed\b",
        r"\bstaff emergency items? will be addressed\b",
    ]
]


def _is_boilerplate_bullet(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return True
    return any(rx.search(t) for rx in _BOILERPLATE_PATTERNS)


def _is_metadata_duplicate_bullet(text: str, meeting: Dict[str, Any]) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return True

    date = str(meeting.get("date") or meeting.get("meeting_date") or "").strip().lower()
    time = str(meeting.get("start_time_local") or meeting.get("start_time") or meeting.get("time") or "").strip().lower()
    location = str(meeting.get("location") or "").strip().lower()

    # Avoid false positives from very short location strings (e.g., "Ce").
    location_match = False
    if location and len(location) >= 4:
        location_match = location in t

    looks_like_metadata = (
        (date and date in t)
        or (time and time in t)
        or location_match
        or bool(re.search(r"\b(meeting (will )?be held|located at|at \d{1,2}:\d{2})\b", t))
    )

    if not looks_like_metadata:
        return False

    # Keep content that also contains clear substantive action terms.
    substantive = re.search(
        r"\b(ordinance|resolution|contract|budget|hearing|vote|amend|zoning|bid|award|funding)\b",
        t,
    )
    return not bool(substantive)



_HIGH_SIGNAL_PATTERNS = [
    re.compile(p, re.I)
    for p in [
        r"\b(ordinance|resolution|contract|agreement|procurement|bid|award)\b",
        r"\b(budget|appropriation|funding|grant|fee|tax|bond)\b",
        r"\b(zoning|rezoning|land use|annexation|variance|plat)\b",
        r"\b(public hearing|hearing|appeal|litigation|settlement)\b",
        r"\b(policy|code amendment|amendment|intergovernmental)\b",
    ]
]


def _relevance_score(bullet: str) -> int:
    t = (bullet or '').strip().lower()
    if not t:
        return -999
    score = 0
    for rx in _HIGH_SIGNAL_PATTERNS:
        if rx.search(t):
            score += 3
    if len(t) >= 45:
        score += 1
    if len(t) > 220:
        score -= 1
    return score

def _partition_summary_bullets(
    bullets: List[str], meeting: Dict[str, Any], max_bullets: int = MAX_BULLETS
) -> Tuple[List[str], List[str]]:
    kept_candidates: List[Tuple[int, int, str]] = []
    filtered_routine: List[str] = []
    seen = set()

    city = str(meeting.get("city") or meeting.get("city_or_body") or "").strip()
    keep_terms, drop_terms = _city_term_override(city)

    for i, raw in enumerate(bullets):
        b = _strip_leading_bullet(raw)
        if not b:
            continue

        key = re.sub(r"\s+", " ", b).strip().lower()
        if key in seen:
            continue
        seen.add(key)

        forced_keep = any(t in key for t in keep_terms) if keep_terms else False
        forced_drop = any(t in key for t in drop_terms) if drop_terms else False

        if forced_drop and not forced_keep:
            filtered_routine.append(b)
            continue

        if (not forced_keep) and (_is_boilerplate_bullet(b) or _is_metadata_duplicate_bullet(b, meeting)):
            filtered_routine.append(b)
            continue

        score = _relevance_score(b)
        if forced_keep:
            score += 10
        kept_candidates.append((score, i, b))

    kept_candidates.sort(key=lambda t: (-t[0], t[1]))
    kept = [b for _, _, b in kept_candidates[:max_bullets]]
    return kept, filtered_routine


def _clean_summary_bullets(bullets: List[str], meeting: Dict[str, Any], max_bullets: int = MAX_BULLETS) -> List[str]:
    kept, _ = _partition_summary_bullets(bullets, meeting, max_bullets=max_bullets)
    return kept

# ---------------------------
# PDF text extraction (prefer project helper if present)
# ---------------------------

def _extract_text_from_pdf_bytes(data: bytes) -> str:
    """
    Try project-local pdf_utils first; else fallback to pdfminer.six.
    """
    # 1) Try local helper
    try:
        from scraper import pdf_utils as pu  # type: ignore
        for name in ("extract_text_from_bytes", "extract_text_from_pdf_bytes", "extract_text_from_pdf"):
            fn = getattr(pu, name, None)
            if callable(fn):
                return fn(data) or ""
    except Exception:
        pass

    # 2) Fallback: pdfminer.six
    try:
        from pdfminer.high_level import extract_text
        return extract_text(BytesIO(data)) or ""
    except Exception as e:
        if DEBUG:
            _log(f"pdfminer failed: {e!r}")
        return ""

# ---------------------------
# LLM summarization
# ---------------------------

def bulletify(text: str, max_bullets: int = 10) -> List[str]:
    """
    Very simple fallback bullet generator for when LLM isn't available.
    """
    lines = [ln.strip(" •-*–\t") for ln in _normalize_ws(text).splitlines() if ln.strip()]
    items = []
    for ln in lines:
        if re.search(r"(^|\s)(item|resolution|ordinance|motion|approve|report|agenda)\b", ln, re.I):
            items.append(ln)
    if not items:
        items = lines
    bullets = []
    for ln in items[: max_bullets * 2]:
        if len(ln) > 240:
            ln = ln[:237] + "..."
        bullets.append("• " + ln)
        if len(bullets) >= max_bullets:
            break
    return bullets

def llm_summarize(text: str, model: str = SUMMARIZER_MODEL, max_bullets: int = MAX_BULLETS) -> List[str]:
    """
    Use OpenAI if keys/model present; fallback to bulletify otherwise.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        if DEBUG:
            _log("OPENAI_API_KEY not set; using simple bulletify fallback")
        return bulletify(text, max_bullets=max_bullets)

    try:
        from openai import OpenAI  # type: ignore
        client = OpenAI(api_key=api_key)
        prompt = textwrap.dedent(f"""
        You are a city agenda summarizer for journalists. Extract only high-signal, newsworthy items.
        Prioritize: ordinances/resolutions, contracts/procurements, budget/funding changes, zoning/land-use,
        public hearings, litigation, appointments with impact, and policy changes.
        Exclude routine procedural boilerplate such as: call to order, pledge, approval of minutes,
        public comment instructions, meeting logistics/broadcast notes, and generic agenda housekeeping.
        Return up to {max_bullets} concise bullet points, each a single sentence.

        Agenda:
        ---
        {text[:DEFAULT_MAX_CHARS]}
        ---
        """).strip()

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You create concise bullet points summarizing municipal meeting agendas."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        content = (resp.choices[0].message.content or "").strip()
        raw = [ln.strip() for ln in content.splitlines() if ln.strip()]
        bullets: List[str] = []
        for ln in raw:
            ln = _strip_leading_bullet(ln)
            if ln:
                bullets.append(ln)
        if not bullets:
            bullets = bulletify(text, max_bullets=max_bullets)
        return bullets[:max_bullets]
    except Exception as e:
        if DEBUG:
            _log(f"LLM summarize failed: {e!r}; using fallback")
        return bulletify(text, max_bullets=max_bullets)

# ---------------------------
# Fetch + summarize pipeline
# ---------------------------

@dataclass
class SummaryResult:
    ok: bool
    reason: str
    bullets: List[str]
    used_url: Optional[str]
    used_kind: Optional[str]  # "text" or "pdf"
    chars: int

def _fetch_text_url(url: str) -> Tuple[Optional[str], str]:
    try:
        r = requests.get(url, timeout=60, headers=UA)
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        ct = (r.headers.get("Content-Type") or "").lower()
        if "text/plain" in ct or "json" in ct or "text" in ct:
            txt = r.text
        else:
            try:
                txt = r.content.decode("utf-8", errors="replace")
            except Exception:
                txt = r.text
        return _normalize_ws(txt), ""
    except Exception as e:
        return None, f"fetch error: {e!r}"

def _fetch_pdf_url(url: str) -> Tuple[Optional[str], str]:
    try:
        r = requests.get(url, timeout=90, headers=UA)
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        if not _looks_like_pdf(r):
            return None, f"not a PDF (Content-Type={r.headers.get('Content-Type')})"
        text = _extract_text_from_pdf_bytes(r.content)
        if not text:
            return None, "no extractable text"
        return _normalize_ws(text), ""
    except Exception as e:
        return None, f"fetch error: {e!r}"

def summarize_meeting(meeting: Dict[str, Any]) -> SummaryResult:
    """
    Prefer agenda_text_url; else agenda_url (PDF). Return bullets or reason.
    """
    text_url = (meeting.get("agenda_text_url") or "").strip() or None
    pdf_url = (meeting.get("agenda_url") or "").strip() or None

    # 1) Text stream (best for CivicClerk plainText=true)
    if text_url:
        txt, err = _fetch_text_url(text_url)
        if txt:
            if len(txt) > DEFAULT_MAX_CHARS:
                txt = txt[:DEFAULT_MAX_CHARS]
            bullets = llm_summarize(txt)
            return SummaryResult(True, "", bullets, text_url, "text", len(txt))
        if DEBUG:
            _log(f"Text fetch failed for {text_url}: {err}")

    # 2) PDF stream (accept even without .pdf extension)
    if pdf_url:
        txt, err = _fetch_pdf_url(pdf_url)
        if txt:
            if len(txt) > DEFAULT_MAX_CHARS:
                txt = txt[:DEFAULT_MAX_CHARS]
            bullets = llm_summarize(txt)
            return SummaryResult(True, "", bullets, pdf_url, "pdf", len(txt))
        if DEBUG:
            _log(f"PDF fetch failed for {pdf_url}: {err}")

    return SummaryResult(False, "no agenda_text_url or usable agenda_url", [], text_url or pdf_url, None, 0)

# ---------------------------
# CLI + merge
# ---------------------------

def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

def _write_meta(out_dir: Path, name: str, payload: Dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{name}.meta.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Summarize meeting agendas into bullet points.")
    ap.add_argument("--input", required=True, help="Path to meetings.json")
    ap.add_argument("--out", required=True, help="Directory to write *.meta.json summaries")
    args = ap.parse_args(argv)

    in_path = Path(args.input)
    out_dir = Path(args.out)

    payload = _load_json(in_path)
    meetings: List[Dict[str, Any]] = payload.get("meetings") or []
    _log(f"Loaded {len(meetings)} meetings from {in_path}")

    produced = 0
    merged = 0

    for idx, m in enumerate(meetings):
        title = (m.get("title") or m.get("meeting") or "Meeting").strip()
        date = (m.get("date") or m.get("meeting_date") or "").strip()
        city = (m.get("city") or m.get("city_or_body") or "").strip()
        slug = _slugify(f"{date}-{city}-{title}") or f"m{idx:03d}"

        res = summarize_meeting(m)

        # meta file for debugging / auditing
        meta = {
            "title": title,
            "city": city,
            "date": date,
            "source": m.get("source") or m.get("url"),
            "agenda_url": m.get("agenda_url"),
            "agenda_text_url": m.get("agenda_text_url"),
            "used_url": res.used_url,
            "used_kind": res.used_kind,
            "chars_summarized": res.chars,
            "bullets": res.bullets,
            "ok": res.ok,
            "reason": res.reason,
        }
        _write_meta(out_dir, slug, meta)

        # merge cleaned bullets back into meetings.json for BOTH 'text' and 'pdf'
        if res.ok and res.bullets and res.used_kind in {"text", "pdf"}:
            cleaned, routine = _partition_summary_bullets(res.bullets, m, max_bullets=MAX_BULLETS)
            m["agenda_summary"] = cleaned
            m["agenda_summary_routine"] = routine
            m["agenda_summary_source"] = res.used_kind
            m["agenda_summary_chars"] = res.chars
            merged += 1
            if DEBUG:
                _log(
                    f"✓ {slug}: merged {len(cleaned)}/{len(res.bullets)} bullets ({res.used_kind}); routine_filtered={len(routine)}"
                )
        else:
            if DEBUG:
                _log(f"✗ {slug}: {res.reason}")

        if res.ok and res.bullets:
            produced += 1

    # write back meetings.json (in place)
    _write_json(in_path, payload)

    _log(f"Completed summaries: {produced}/{len(meetings)}; merged into meetings.json: {merged}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
