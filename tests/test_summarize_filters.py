import unittest

import scraper.summarize as summarize
from scraper.summarize import _clean_summary_bullets, _partition_summary_bullets


class TestSummaryFiltering(unittest.TestCase):
    def test_drops_boilerplate_and_metadata_duplicates(self):
        meeting = {
            "date": "2026-03-10",
            "start_time_local": "6:00 PM",
            "location": "City Hall",
        }
        bullets = [
            "Pledge of Allegiance",
            "Meeting will be held at City Hall at 6:00 PM on 2026-03-10",
            "Approve contract award for stormwater upgrades",
        ]
        out = _clean_summary_bullets(bullets, meeting, max_bullets=10)
        self.assertEqual(out, ["Approve contract award for stormwater upgrades"])

    def test_deduplicates_and_keeps_substantive(self):
        meeting = {"date": "2026-03-10", "start_time_local": "6:00 PM", "location": "City Hall"}
        bullets = [
            "Approve budget amendment for transit operations",
            "Approve budget amendment for transit operations",
            "Public Comments",
        ]
        out = _clean_summary_bullets(bullets, meeting, max_bullets=10)
        self.assertEqual(out, ["Approve budget amendment for transit operations"])

    def test_drops_common_notice_boilerplate(self):
        meeting = {"date": "2026-03-10", "start_time_local": "6:00 PM", "location": "City Hall"}
        bullets = [
            "All agenda items are subject to change in order and timing.",
            "Citizens can submit comments on agenda items via email before the meeting.",
            "The meeting will be broadcast live on Channel 18 and Facebook Live.",
            "A resolution to approve a downtown housing contract will be considered.",
        ]
        out = _clean_summary_bullets(bullets, meeting, max_bullets=10)
        self.assertEqual(out, ["A resolution to approve a downtown housing contract will be considered."])

    def test_keeps_specific_executive_session_context(self):
        meeting = {"date": "2026-03-10", "start_time_local": "6:00 PM", "location": "City Hall"}
        bullets = [
            "An executive session is scheduled to discuss confidential matters.",
            "The case discussed in executive session is Smith v. City, Case No. 2026CV12345.",
        ]
        out = _clean_summary_bullets(bullets, meeting, max_bullets=10)
        self.assertIn("An executive session is scheduled to discuss confidential matters.", out)
        self.assertIn("The case discussed in executive session is Smith v. City, Case No. 2026CV12345.", out)

    def test_drops_new_routine_patterns(self):
        meeting = {"date": "2026-03-10", "start_time_local": "6:00 PM", "location": "City Hall"}
        bullets = [
            "The agenda includes a public forum for community input.",
            "Changes to the agenda will be addressed at the beginning of the meeting.",
            "Items under study will be discussed during the meeting.",
            "Staff emergency items will be addressed at the start of the meeting.",
            "A contract amendment for road reconstruction will be considered.",
        ]
        out = _clean_summary_bullets(bullets, meeting, max_bullets=10)
        self.assertEqual(out, ["A contract amendment for road reconstruction will be considered."])

    def test_partition_returns_routine_bucket(self):
        meeting = {"date": "2026-03-10", "start_time_local": "6:00 PM", "location": "City Hall"}
        bullets = [
            "Public Comments",
            "A resolution to approve a housing grant will be considered.",
        ]
        kept, routine = _partition_summary_bullets(bullets, meeting, max_bullets=10)
        self.assertEqual(kept, ["A resolution to approve a housing grant will be considered."])
        self.assertEqual(routine, ["Public Comments"])

    def test_short_location_does_not_trigger_metadata_false_positive(self):
        meeting = {"date": "2026-03-10", "start_time_local": "9:00 AM", "location": "Ce"}
        bullets = [
            "Approval of a Purchase Order to Tyler Technologies for annual maintenance totaling $150,623.42.",
        ]
        kept, routine = _partition_summary_bullets(bullets, meeting, max_bullets=10)
        self.assertEqual(len(kept), 1)
        self.assertEqual(routine, [])

    def test_relevance_scoring_prioritizes_high_signal_when_truncated(self):
        meeting = {"date": "2026-03-10", "start_time_local": "6:00 PM", "location": "City Hall"}
        bullets = [
            "General announcements and recognitions.",
            "Approve ordinance for downtown zoning amendment and budget appropriation.",
        ]
        prev = summarize.ENABLE_RELEVANCE_SCORING
        summarize.ENABLE_RELEVANCE_SCORING = True
        try:
            kept, _ = _partition_summary_bullets(bullets, meeting, max_bullets=1)
        finally:
            summarize.ENABLE_RELEVANCE_SCORING = prev
        self.assertEqual(kept, ["Approve ordinance for downtown zoning amendment and budget appropriation."])

    def test_rollback_toggle_preserves_input_order(self):
        meeting = {"date": "2026-03-10", "start_time_local": "6:00 PM", "location": "City Hall"}
        bullets = [
            "General announcements and recognitions.",
            "Approve ordinance for downtown zoning amendment and budget appropriation.",
        ]
        prev = summarize.ENABLE_RELEVANCE_SCORING
        summarize.ENABLE_RELEVANCE_SCORING = False
        try:
            kept, _ = _partition_summary_bullets(bullets, meeting, max_bullets=1)
        finally:
            summarize.ENABLE_RELEVANCE_SCORING = prev
        self.assertEqual(kept, ["General announcements and recognitions."])


if __name__ == "__main__":
    unittest.main()
