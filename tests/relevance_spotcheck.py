#!/usr/bin/env python3
"""
Issue #3 spot-check harness.

Runs a curated sample set to estimate:
1) high-signal pick precision (target >=80%)
2) routine false-positive reduction vs first-come baseline
"""
from scraper.summarize import _partition_summary_bullets

SAMPLES = [
    {
        "meeting": {"city": "Pueblo", "date": "2026-03-10", "start_time_local": "6:00 PM", "location": "City Hall"},
        "bullets": [
            "General announcements and recognitions.",
            "Approve ordinance for downtown zoning amendment.",
            "Public comments.",
            "Budget appropriation for stormwater contract.",
            "Pledge of Allegiance.",
        ],
        "expected_keywords": ["ordinance", "zoning", "budget", "contract"],
    },
    {
        "meeting": {"city": "Colorado Springs", "date": "2026-03-12", "start_time_local": "1:00 PM", "location": "Council Chambers"},
        "bullets": [
            "Call to order.",
            "Resolution approving grant funding for transit safety program.",
            "Consent calendar.",
            "Annexation and land use variance request for district 4.",
            "Adjournment.",
        ],
        "expected_keywords": ["resolution", "grant", "annexation", "land use", "variance"],
    },
    {
        "meeting": {"city": "El Paso County", "date": "2026-03-13", "start_time_local": "9:00 AM", "location": "County Hall"},
        "bullets": [
            "Meeting logistics and channel information.",
            "Intergovernmental agreement renewal for emergency services.",
            "Public hearing on fee schedule amendment.",
            "Approval of minutes.",
            "Ceremonial proclamation.",
        ],
        "expected_keywords": ["intergovernmental", "agreement", "hearing", "fee", "amendment"],
    },
]


def score_precision(kept, expected_keywords):
    if not kept:
        return 0.0
    hits = 0
    for b in kept:
        t = b.lower()
        if any(k in t for k in expected_keywords):
            hits += 1
    return hits / len(kept)


def main():
    precisions = []
    routine_baseline = 0
    routine_scored = 0

    for s in SAMPLES:
        meeting = s["meeting"]
        bullets = s["bullets"]
        expected = [k.lower() for k in s["expected_keywords"]]

        kept, routine = _partition_summary_bullets(bullets, meeting, max_bullets=3)
        precisions.append(score_precision(kept, expected))

        # naive baseline: first 3 bullets after removing empties
        baseline = [b for b in bullets if b.strip()][:3]
        baseline_routine = sum(1 for b in baseline if b in routine or any(x in b.lower() for x in ["call to order", "consent", "pledge", "adjourn", "minutes", "ceremonial", "public comments"]))
        scored_routine = sum(1 for b in kept if any(x in b.lower() for x in ["call to order", "consent", "pledge", "adjourn", "minutes", "ceremonial", "public comments"]))
        routine_baseline += baseline_routine
        routine_scored += scored_routine

    avg_precision = sum(precisions) / len(precisions)
    reduction = (routine_baseline - routine_scored) / routine_baseline if routine_baseline else 0.0

    print(f"avg_precision={avg_precision:.3f}")
    print(f"routine_false_positive_reduction={reduction:.3f}")

    # Target checks from issue acceptance
    ok_precision = avg_precision >= 0.80
    ok_reduction = reduction > 0.0
    print(f"pass_precision={ok_precision}")
    print(f"pass_reduction={ok_reduction}")

    return 0 if (ok_precision and ok_reduction) else 1


if __name__ == "__main__":
    raise SystemExit(main())
