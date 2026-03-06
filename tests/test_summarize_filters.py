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


if __name__ == "__main__":
    unittest.main()
