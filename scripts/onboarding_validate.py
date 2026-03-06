#!/usr/bin/env python3
import argparse
import json
import sys
import subprocess
from urllib.parse import urlparse

ALLOWED_PLATFORMS = {"agendasuite", "civicclerk"}
ALLOWED_TEMPLATES = {"agendasuite", "civicclerk"}


def err(msg, errs):
    errs.append(msg)


def valid_tz(tz: str) -> bool:
    return isinstance(tz, str) and tz.startswith("America/")


def valid_url(u: str) -> bool:
    try:
        p = urlparse(u)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False


def dry_fetch(url: str, timeout=15):
    # Use curl here for consistency with CI/runtime environments where
    # python ssl cert stores can differ.
    cmd = [
        "curl",
        "-sS",
        "-I",
        "--max-time",
        str(timeout),
        "-A",
        "MeetingWatch-Onboarding-Validator/1.0",
        url,
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or "curl failed")

    status = 0
    ctype = ""
    for line in (p.stdout or "").splitlines():
        l = line.strip()
        if l.startswith("HTTP/"):
            parts = l.split()
            if len(parts) >= 2 and parts[1].isdigit():
                status = int(parts[1])
        if l.lower().startswith("content-type:"):
            ctype = l.split(":", 1)[1].strip()
    return status or 200, ctype


def validate_city(c):
    errors = []
    required = ["city", "platform", "timezone", "source_url", "parser_template", "enabled"]
    for k in required:
        if k not in c:
            err(f"missing required field: {k}", errors)

    if c.get("platform") not in ALLOWED_PLATFORMS:
        err(f"platform must be one of {sorted(ALLOWED_PLATFORMS)}", errors)
    if c.get("parser_template") not in ALLOWED_TEMPLATES:
        err(f"parser_template must be one of {sorted(ALLOWED_TEMPLATES)}", errors)
    if c.get("platform") and c.get("parser_template") and c.get("platform") != c.get("parser_template"):
        err("platform and parser_template should match for template onboarding", errors)
    if not valid_tz(c.get("timezone", "")):
        err("timezone must be an America/* zone", errors)
    if not valid_url(c.get("source_url", "")):
        err("source_url must be a valid http(s) URL", errors)

    # approval gate: enabled city requires explicit approval ticket string
    if c.get("enabled") is True and not str(c.get("approval_ticket", "")).strip():
        err("enabled=true requires non-empty approval_ticket", errors)

    return errors


def main():
    ap = argparse.ArgumentParser(description="Validate MeetingWatch city onboarding config")
    ap.add_argument("--config", default="config/cities.example.json")
    ap.add_argument("--dry-run", action="store_true", help="Fetch source_url to verify reachability")
    args = ap.parse_args()

    try:
        with open(args.config, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"failed to load config: {e}"}))
        return 2

    cities = payload.get("cities", [])
    if not isinstance(cities, list) or not cities:
        print(json.dumps({"ok": False, "error": "cities must be a non-empty array"}))
        return 2

    results = []
    all_ok = True
    for c in cities:
        city_name = c.get("city", "<unknown>")
        errors = validate_city(c)
        dry = None
        if args.dry_run and not errors:
            try:
                status, ctype = dry_fetch(c["source_url"])
                dry = {"status": status, "content_type": ctype}
                if status >= 400:
                    errors.append(f"dry-run fetch returned HTTP {status}")
            except Exception as e:
                errors.append(f"dry-run fetch failed: {e}")
        ok = len(errors) == 0
        if not ok:
            all_ok = False
        results.append({"city": city_name, "ok": ok, "errors": errors, "dry_run": dry})

    out = {"ok": all_ok, "results": results}
    print(json.dumps(out, indent=2))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
