"""Build the MeetingWatch static site from generated JSON datasets."""

from __future__ import annotations

import argparse
import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List
from urllib.parse import urlparse
from zoneinfo import ZoneInfo


KNOWN_CITIES = ["Alamosa", "Colorado Springs", "El Paso County", "Pueblo", "Salida", "Trinidad"]


def _safe_url(value: Any) -> str:
    value = str(value or "").strip()
    parsed = urlparse(value)
    return html.escape(value, quote=True) if parsed.scheme in {"http", "https"} else ""


def _meeting_date(meeting: Dict[str, Any]) -> str:
    return str(meeting.get("date") or "")


def _is_current(meeting: Dict[str, Any], today: str) -> bool:
    value = _meeting_date(meeting)
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return value >= today


def _static_briefing(meeting: Dict[str, Any]) -> str:
    briefing = meeting.get("agenda_briefing") or {}
    items = briefing.get("items") or []
    if not items:
        status = meeting.get("agenda_briefing_status")
        if status == "not-published":
            return '<p class="empty-note">Agenda not yet published; briefing will appear automatically.</p>'
        if status:
            return '<p class="withheld">Briefing withheld because automated source checks did not pass.</p>'
        return ""
    parts = [f'<p class="overview">{html.escape(str(briefing.get("overview") or ""))}</p>', '<ol class="stories">']
    for item in items:
        locator = []
        if item.get("agenda_item"):
            locator.append(f"Agenda item {html.escape(str(item['agenda_item']))}")
        if item.get("source_page"):
            locator.append(f"page {int(item['source_page'])}")
        parts.append('<li class="story">')
        parts.append(
            f'<div class="story-label">{html.escape(str(item.get("priority") or "notable")).upper()} · '
            f'{html.escape(str(item.get("category") or "other")).replace("-", " ").upper()}</div>'
        )
        parts.append(f'<h3>{html.escape(str(item.get("headline") or ""))}</h3>')
        parts.append(f'<p>{html.escape(str(item.get("action") or ""))}</p>')
        if item.get("why_it_matters"):
            parts.append(f'<p class="why"><strong>Why it matters:</strong> {html.escape(str(item["why_it_matters"]))}</p>')
        facts = item.get("key_facts") or []
        if facts:
            parts.append('<div class="facts">' + "".join(f'<span>{html.escape(str(f))}</span>' for f in facts) + '</div>')
        if item.get("evidence"):
            parts.append('<details class="evidence"><summary>Source evidence</summary>')
            parts.append(f'<blockquote>{html.escape(str(item["evidence"]))}</blockquote>')
            if locator:
                parts.append(f'<div class="locator">{" · ".join(locator)}</div>')
            parts.append('</details>')
        parts.append('</li>')
    parts.append('</ol>')
    return "".join(parts)


def _static_card(meeting: Dict[str, Any]) -> str:
    city = html.escape(str(meeting.get("city") or meeting.get("city_or_body") or "Meeting"))
    title = html.escape(str(meeting.get("title") or meeting.get("meeting_type") or "Public meeting"))
    date = html.escape(_meeting_date(meeting))
    time = html.escape(str(meeting.get("start_time_local") or meeting.get("start_time") or meeting.get("time") or ""))
    agenda = _safe_url(meeting.get("agenda_view_url") or meeting.get("agenda_url"))
    source = _safe_url(meeting.get("source") or meeting.get("url"))
    links = []
    if agenda:
        links.append(f'<a href="{agenda}">Agenda</a>')
    if source:
        links.append(f'<a href="{source}">Official source</a>')
    return (
        '<article class="meeting-card">'
        f'<div class="eyebrow">{date}{(" · " + time) if time else ""}</div>'
        f'<h2>{city}</h2><div class="meeting-title">{title}</div>'
        f'<div class="meeting-links">{" · ".join(links)}</div>'
        f'{_static_briefing(meeting)}'
        '</article>'
    )


def build(data_dir: Path, output_dir: Path) -> Path:
    meetings_path = data_dir / "meetings.json"
    history_path = data_dir / "history.json"
    current_raw = json.loads(meetings_path.read_text(encoding="utf-8"))
    history_raw = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else {"meetings": []}
    current = current_raw if isinstance(current_raw, list) else current_raw.get("meetings", [])
    today = datetime.now(ZoneInfo("America/Denver")).date().isoformat()
    upcoming = sorted((m for m in current if _is_current(m, today)), key=lambda m: (_meeting_date(m), str(m.get("start_time_local") or "")))
    verified = sum(1 for m in upcoming if m.get("agenda_briefing_status") == "verified")
    agendas = sum(1 for m in upcoming if m.get("agenda_url") or m.get("agenda_text_url"))
    generated = str(current_raw.get("generated_at_utc") or "") if isinstance(current_raw, dict) else ""
    checked = str(current_raw.get("last_checked_mt") or generated or "unknown") if isinstance(current_raw, dict) else "unknown"

    output_dir.mkdir(parents=True, exist_ok=True)
    public_data = output_dir / "data"
    public_data.mkdir(parents=True, exist_ok=True)
    (public_data / "meetings.json").write_text(meetings_path.read_text(encoding="utf-8"), encoding="utf-8")
    if history_path.exists():
        (public_data / "history.json").write_text(history_path.read_text(encoding="utf-8"), encoding="utf-8")
    (output_dir / ".nojekyll").touch()

    static_cards = "".join(_static_card(m) for m in upcoming)
    template = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Evidence-backed editorial briefings for upcoming public meetings in southern Colorado.">
<title>MeetingWatch — What local government is deciding next</title>
<style>
:root{--ink:#172033;--muted:#5b6474;--paper:#f5f2ea;--card:#fff;--line:#d8d5cc;--navy:#153a59;--blue:#0b67a3;--gold:#b56b16;--green:#16734a;--red:#a6382e;--shadow:0 10px 28px rgba(23,32,51,.08)}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}a{color:var(--blue);text-underline-offset:3px}a:hover{text-decoration-thickness:2px}button,select,input{font:inherit}
.masthead{background:var(--navy);color:#fff;padding:2.6rem max(1rem,calc((100vw - 1120px)/2));border-bottom:6px solid #d59a3c}.brand{font:800 clamp(2.2rem,6vw,4.2rem)/.95 Georgia,serif;letter-spacing:-.045em}.tagline{max-width:760px;margin:.75rem 0 0;font-size:1.08rem;color:#dbe8f2}.trust{display:flex;flex-wrap:wrap;gap:.55rem;margin-top:1.1rem}.trust span{border:1px solid #ffffff55;border-radius:99px;padding:.26rem .65rem;font-size:.82rem}
main{max-width:1120px;margin:0 auto;padding:1.5rem 1rem 4rem}.statusbar{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--line);border:1px solid var(--line);border-radius:12px;overflow:hidden;box-shadow:var(--shadow)}.stat{background:var(--card);padding:1rem}.stat strong{display:block;font:750 1.55rem/1 Georgia,serif}.stat span{color:var(--muted);font-size:.82rem}.run-meta{color:var(--muted);font-size:.84rem;margin:.7rem .1rem 1.25rem}
.controls{display:grid;grid-template-columns:1fr 1fr 2fr;gap:.8rem;background:#ebe7dc;border:1px solid var(--line);padding:.85rem;border-radius:12px;margin-bottom:1rem;position:sticky;top:.5rem;z-index:10;box-shadow:0 8px 24px #17203312}.controls label{font-size:.75rem;text-transform:uppercase;letter-spacing:.06em;font-weight:750;color:var(--muted)}.controls select,.controls input{display:block;width:100%;margin-top:.25rem;padding:.58rem .65rem;border:1px solid #c8c4b9;border-radius:8px;background:white;color:var(--ink)}
#results,.static-list{display:grid;gap:1rem}.meeting-card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:clamp(1rem,3vw,1.6rem);box-shadow:var(--shadow)}.meeting-head{display:grid;grid-template-columns:1fr auto;gap:1rem;border-bottom:1px solid var(--line);padding-bottom:.9rem;margin-bottom:1rem}.eyebrow,.story-label{font-size:.73rem;letter-spacing:.075em;text-transform:uppercase;color:var(--gold);font-weight:800}.meeting-card h2{font:750 clamp(1.4rem,4vw,2rem)/1.05 Georgia,serif;margin:.18rem 0}.meeting-title{font-weight:650;color:var(--muted)}.meeting-links{font-size:.88rem;margin-top:.35rem}.status-pill{align-self:start;border-radius:99px;padding:.3rem .65rem;font-size:.76rem;font-weight:750;background:#e3f3eb;color:var(--green)}.status-pill.pending{background:#f4ead8;color:#80510d}.status-pill.withheld{background:#f8e1df;color:var(--red)}
.overview{font:600 1.08rem/1.45 Georgia,serif;margin:.2rem 0 1rem;max-width:78ch}.stories{list-style:none;padding:0;margin:0;display:grid;gap:.75rem}.story{border-left:4px solid #aab7c2;background:#f8fafb;padding:.85rem 1rem;border-radius:0 10px 10px 0}.story.top{border-left-color:var(--gold);background:#fffaf1}.story h3{font:750 1.08rem/1.25 Georgia,serif;margin:.15rem 0 .28rem}.story p{margin:.25rem 0;max-width:82ch}.why{color:#384457}.facts{display:flex;flex-wrap:wrap;gap:.35rem;margin-top:.55rem}.facts span{font-size:.76rem;font-weight:750;color:#17496b;background:#e6f1f8;border-radius:99px;padding:.22rem .5rem}.evidence{margin-top:.65rem;border-top:1px dashed #c9cfd4;padding-top:.5rem}.evidence summary{cursor:pointer;color:var(--blue);font-size:.82rem;font-weight:700}.evidence blockquote{margin:.55rem 0 .25rem;padding:.55rem .75rem;border-left:3px solid #9aa7b1;color:#46505f;font:italic .88rem/1.45 Georgia,serif}.locator{font-size:.76rem;color:var(--muted)}.empty-note,.withheld{margin:.8rem 0 0;padding:.7rem .85rem;border-radius:8px;background:#f5efe2;color:#77501a}.withheld{background:#f8e8e6;color:#8c3028}.routine{margin-top:.75rem;color:var(--muted);font-size:.88rem}.empty{text-align:center;background:white;border:1px solid var(--line);border-radius:12px;padding:2rem;color:var(--muted)}footer{max-width:1120px;margin:0 auto;padding:0 1rem 2rem;color:var(--muted);font-size:.82rem}
@media(max-width:720px){.statusbar{grid-template-columns:1fr}.controls{grid-template-columns:1fr;position:static}.meeting-head{grid-template-columns:1fr}.masthead{padding-top:1.8rem}.story{padding:.75rem}}
</style></head><body>
<header class="masthead"><div class="brand">MeetingWatch</div><p class="tagline">What local government is deciding next—ranked, explained, and tied directly to the official agenda.</p><div class="trust"><span>Evidence-linked</span><span>Material amounts checked</span><span>Twice-daily updates</span></div></header>
<main><section class="statusbar" aria-label="Coverage summary"><div class="stat"><strong>__UPCOMING__</strong><span>upcoming meetings</span></div><div class="stat"><strong>__AGENDAS__</strong><span>agendas published</span></div><div class="stat"><strong>__VERIFIED__</strong><span>verified briefings</span></div></section>
<div class="run-meta" data-run-ts="__GENERATED__"><strong>Last checked:</strong> __CHECKED__ <span id="freshness"></span> · <a href="data/meetings.json">Open data</a></div>
<section class="controls" aria-label="Meeting filters"><label>View<select id="view"><option value="upcoming">Upcoming</option><option value="history">Past 60 days</option></select></label><label>Jurisdiction<select id="city"><option value="">All jurisdictions</option></select></label><label>Search<input id="search" type="search" placeholder="Search topics, amounts, places…"></label></section>
<div id="results"></div><noscript><div class="static-list">__STATIC_CARDS__</div></noscript></main>
<footer>MeetingWatch briefings are AI-assisted and automatically validated against official agenda text. Items failing source checks are withheld, not guessed.</footer>
<script>
(async()=>{const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const safe=u=>{try{const x=new URL(String(u||''),location.href);return ['http:','https:'].includes(x.protocol)?esc(x.href):''}catch{return''}};
const [mr,hr]=await Promise.all([fetch('data/meetings.json',{cache:'no-store'}),fetch('data/history.json',{cache:'no-store'}).catch(()=>null)]);const md=await mr.json(),hd=hr?await hr.json():{meetings:[]};const all=Array.isArray(md)?md:(md.meetings||[]),hist=Array.isArray(hd)?hd:(hd.meetings||[]);const today=new Date().toLocaleDateString('en-CA',{timeZone:'America/Denver'});const upcoming=all.filter(m=>/^\d{4}-\d{2}-\d{2}$/.test(m.date||'')&&m.date>=today).sort((a,b)=>(a.date+(a.start_time_local||'')).localeCompare(b.date+(b.start_time_local||'')));const historyItems=hist.filter(m=>/^\d{4}-\d{2}-\d{2}$/.test(m.date||'')&&m.date<today).sort((a,b)=>(b.date+(b.start_time_local||'')).localeCompare(a.date+(a.start_time_local||'')));
const view=document.querySelector('#view'),city=document.querySelector('#city'),search=document.querySelector('#search'),results=document.querySelector('#results');const known=__KNOWN_CITIES__;
function dataset(){return view.value==='history'?historyItems:upcoming}function cities(){const selected=city.value,counts={};dataset().forEach(m=>{const c=(m.city||'').trim();if(c)counts[c]=(counts[c]||0)+1});city.innerHTML='<option value="">All jurisdictions</option>';[...new Set([...known,...Object.keys(counts)])].sort().forEach(c=>city.add(new Option(`${c} (${counts[c]||0})`,c)));city.value=[...city.options].some(o=>o.value===selected)?selected:''}
function locator(item){const bits=[];if(item.agenda_item)bits.push(`Agenda item ${esc(item.agenda_item)}`);if(item.source_page)bits.push(`page ${Number(item.source_page)}`);return bits.join(' · ')}
function briefing(m){const b=m.agenda_briefing||{},items=Array.isArray(b.items)?b.items:[];if(!items.length){if(m.agenda_briefing_status==='not-published')return'<p class="empty-note">Agenda not yet published; briefing will appear automatically.</p>';if(m.agenda_briefing_status)return'<p class="withheld">Briefing withheld because automated source checks did not pass.</p>';const old=Array.isArray(m.agenda_summary)?m.agenda_summary:[];return old.length?'<ul>'+old.map(x=>`<li>${esc(x)}</li>`).join('')+'</ul>':''}
const agenda=safe(m.agenda_view_url||m.agenda_url);const stories=items.map(i=>{const facts=(i.key_facts||[]).map(f=>`<span>${esc(f)}</span>`).join('');const evidence=i.evidence?`<details class="evidence"><summary>Source evidence</summary><blockquote>${esc(i.evidence)}</blockquote><div class="locator">${locator(i)}${agenda?` · <a href="${agenda}" target="_blank" rel="noopener">Official agenda</a>`:''}</div></details>`:'';return`<li class="story ${i.priority==='top'?'top':''}"><div class="story-label">${esc(i.priority||'notable')} · ${esc((i.category||'other').replace('-',' '))}</div><h3>${esc(i.headline)}</h3><p>${esc(i.action)}</p>${i.why_it_matters?`<p class="why"><strong>Why it matters:</strong> ${esc(i.why_it_matters)}</p>`:''}${facts?`<div class="facts">${facts}</div>`:''}${evidence}</li>`}).join('');const routine=(b.routine_items||[]);return`${b.overview?`<p class="overview">${esc(b.overview)}</p>`:''}<ol class="stories">${stories}</ol>${routine.length?`<details class="routine"><summary>Routine items (${routine.length})</summary><ul>${routine.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></details>`:''}`}
function card(m){const agenda=safe(m.agenda_view_url||m.agenda_url),source=safe(m.source||m.url),verified=m.agenda_briefing_status==='verified',pending=m.agenda_briefing_status==='not-published';const status=verified?'Evidence-checked':pending?'Agenda pending':'Briefing withheld';const links=[agenda?`<a href="${agenda}" target="_blank" rel="noopener">Agenda</a>`:'',source?`<a href="${source}" target="_blank" rel="noopener">Official source</a>`:''].filter(Boolean).join(' · ');return`<article class="meeting-card"><div class="meeting-head"><div><div class="eyebrow">${esc(m.date||'')}${m.start_time_local?' · '+esc(m.start_time_local):''}</div><h2>${esc(m.city||m.city_or_body||'Meeting')}</h2><div class="meeting-title">${esc(m.title||m.meeting_type||'Public meeting')}</div><div class="meeting-links">${links}</div></div><span class="status-pill ${verified?'':pending?'pending':'withheld'}">${status}</span></div>${briefing(m)}</article>`}
function render(){const c=city.value,q=search.value.trim().toLowerCase();const shown=dataset().filter(m=>(!c||m.city===c)&&(!q||JSON.stringify(m).toLowerCase().includes(q)));results.innerHTML=shown.length?shown.map(card).join(''):'<div class="empty">No meetings match these filters.</div>';const u=new URL(location.href);u.searchParams.set('view',view.value);c?u.searchParams.set('city',c):u.searchParams.delete('city');q?u.searchParams.set('q',q):u.searchParams.delete('q');history.replaceState({},'',u)}
const u=new URL(location.href);view.value=['upcoming','history'].includes(u.searchParams.get('view'))?u.searchParams.get('view'):'upcoming';cities();city.value=u.searchParams.get('city')||'';search.value=u.searchParams.get('q')||'';view.onchange=()=>{cities();render()};city.onchange=render;search.oninput=render;const stamp=document.querySelector('.run-meta').dataset.runTs,ms=Date.parse(stamp);if(Number.isFinite(ms)){const h=Math.floor((Date.now()-ms)/36e5);document.querySelector('#freshness').textContent=h<1?'· updated within the hour':h<24?`· ${h} hours ago`:`· ${Math.floor(h/24)} days ago`}render()})();
</script></body></html>'''
    page = (
        template.replace("__UPCOMING__", str(len(upcoming)))
        .replace("__AGENDAS__", str(agendas))
        .replace("__VERIFIED__", str(verified))
        .replace("__GENERATED__", html.escape(generated, quote=True))
        .replace("__CHECKED__", html.escape(checked))
        .replace("__STATIC_CARDS__", static_cards)
        .replace("__KNOWN_CITIES__", json.dumps(KNOWN_CITIES))
    )
    output = output_dir / "index.html"
    output.write_text(page, encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data", type=Path)
    parser.add_argument("--output-dir", default="_site", type=Path)
    args = parser.parse_args()
    print(build(args.data_dir, args.output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
