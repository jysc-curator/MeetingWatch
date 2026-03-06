import unittest

from scraper.summarize import _clean_summary_bullets


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


if __name__ == "__main__":
    unittest.main()
