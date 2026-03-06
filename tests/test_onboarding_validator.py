import json
import subprocess
from pathlib import Path


def run_validator(tmp_path, payload, dry=False):
    cfg = tmp_path / "cities.json"
    cfg.write_text(json.dumps(payload), encoding="utf-8")
    cmd = ["python3", "scripts/onboarding_validate.py", "--config", str(cfg)]
    if dry:
        cmd.append("--dry-run")
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout


def test_valid_config_passes(tmp_path):
    payload = {
        "version": 1,
        "cities": [
            {
                "city": "Test City",
                "platform": "agendasuite",
                "timezone": "America/Denver",
                "source_url": "https://example.com",
                "parser_template": "agendasuite",
                "enabled": False,
            }
        ],
    }
    code, out = run_validator(tmp_path, payload)
    assert code == 0
    assert '"ok": true' in out.lower()


def test_enabled_requires_approval_ticket(tmp_path):
    payload = {
        "version": 1,
        "cities": [
            {
                "city": "Test City",
                "platform": "civicclerk",
                "timezone": "America/Denver",
                "source_url": "https://example.com",
                "parser_template": "civicclerk",
                "enabled": True,
            }
        ],
    }
    code, out = run_validator(tmp_path, payload)
    assert code == 1
    assert "approval_ticket" in out
