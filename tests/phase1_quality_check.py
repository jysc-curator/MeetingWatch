#!/usr/bin/env python3
"""Issue #2 evidence harness: boilerplate + metadata filtering quality."""
from scraper.summarize import _partition_summary_bullets

SAMPLES = [
    {
        "meeting": {"city": "Pueblo", "date": "2026-03-10", "start_time_local": "6:00 PM", "location": "City Hall"},
        "bullets": [
            "2026-03-10 6:00 PM City Hall",
            "Pledge of Allegiance",
            "Approval of minutes",
            "Public comments",
            "Approve budget appropriation for transit contract",
            "Public hearing on zoning amendment",
        ],
    },
    {
        "meeting": {"city": "Colorado Springs", "date": "2026-03-12", "start_time_local": "1:00 PM", "location": "Council Chambers"},
        "bullets": [
            "Meeting will be held at Council Chambers at 1:00 PM on 2026-03-12",
            "Call to order",
            "Consent calendar",
            "Resolution to award stormwater project contract",
            "Annexation and land use variance request",
        ],
    },
]

CONSEQUENTIAL = ["vote", "ordinance", "resolution", "hearing", "contract", "budget", "zoning", "annexation", "variance"]
ROUTINE_HINTS = ["pledge", "call to order", "minutes", "public comments", "consent", "meeting will be held"]

def is_routine(s: str) -> bool:
    t=s.lower()
    return any(k in t for k in ROUTINE_HINTS)

def is_consequential(s: str) -> bool:
    t=s.lower()
    return any(k in t for k in CONSEQUENTIAL)


def main():
    before_routine = 0
    after_routine = 0
    consequential_before = 0
    consequential_after = 0

    for i,s in enumerate(SAMPLES,1):
        b=s["bullets"]
        kept,_routine=_partition_summary_bullets(b, s["meeting"], max_bullets=12)

        before_routine += sum(1 for x in b if is_routine(x))
        after_routine += sum(1 for x in kept if is_routine(x))

        consequential_before += sum(1 for x in b if is_consequential(x))
        consequential_after += sum(1 for x in kept if is_consequential(x))

        print(f"sample_{i}_before={b}")
        print(f"sample_{i}_after={kept}")

    reduction = (before_routine - after_routine) / before_routine if before_routine else 0.0
    kept_ratio = consequential_after / consequential_before if consequential_before else 1.0

    print(f"routine_reduction={reduction:.3f}")
    print(f"consequential_keep_ratio={kept_ratio:.3f}")
    print(f"pass_routine_reduction={reduction >= 0.40}")
    print(f"pass_consequential_retention={kept_ratio >= 1.0}")

    return 0 if (reduction >= 0.40 and kept_ratio >= 1.0) else 1

if __name__ == "__main__":
    raise SystemExit(main())
