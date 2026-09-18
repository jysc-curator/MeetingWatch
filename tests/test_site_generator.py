import json
from pathlib import Path


def _site_generator_source() -> str:
    workflow = Path(".github/workflows/site.yml").read_text(encoding="utf-8").splitlines()
    job_marker = next(
        index
        for index, line in enumerate(workflow)
        if line.strip() == "- name: Generate index.html from data/meetings.json"
    )
    start = next(
        index
        for index in range(job_marker, len(workflow))
        if workflow[index].strip() == "python - <<'PY'"
    )
    end = next(
        index
        for index in range(start + 1, len(workflow))
        if workflow[index] == "          PY"
    )
    return "\n".join(line[10:] if len(line) >= 10 else "" for line in workflow[start + 1 : end])


def test_generated_homepage_hides_past_static_records_and_uses_data_timestamp(tmp_path, monkeypatch):
    generator_source = _site_generator_source()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "meetings.json").write_text(
        json.dumps(
            {
                "generated_at_utc": "2099-01-01T12:00:00Z",
                "last_checked_mt": "2099-01-01 05:00 MST",
                "meetings": [
                    {"id": "past", "date": "2020-01-01", "city": "Past City"},
                    {"id": "future", "date": "2099-01-02", "city": "Future City"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (data_dir / "history.json").write_text(
        json.dumps({"retention_days": 60, "meetings": []}), encoding="utf-8"
    )

    monkeypatch.chdir(tmp_path)
    exec(compile(generator_source, "site-generator", "exec"), {})

    html = (tmp_path / "_site" / "index.html").read_text(encoding="utf-8")
    assert "Future City" in html
    assert "Past City" not in html
    assert 'data-run-ts="2099-01-01T12:00:00Z"' in html
    assert "const upcomingItems = items.filter" in html
    assert "staticList.style.display = 'none'" in html
