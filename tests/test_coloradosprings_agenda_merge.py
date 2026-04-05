import unittest

from scraper.coloradosprings_legistar import _merge_duplicate_meetings


class TestColoradoSpringsAgendaMerge(unittest.TestCase):
    def test_merge_prefers_agenda_record_for_same_slot(self):
        records = [
            {
                "city_or_body": "Colorado Springs — City Council",
                "meeting_type": "City Council Meeting",
                "date": "2026-04-06",
                "start_time_local": "9:00 AM",
                "location": "Council Chambers Special Meeting to appoint 2nd District City Council Member",
                "agenda_url": None,
                "agenda_summary": [],
                "status": "Scheduled",
            },
            {
                "city_or_body": "Colorado Springs — City Council",
                "meeting_type": "City Council Meeting",
                "date": "2026-04-06",
                "start_time_local": "9:00 AM",
                "location": "Council Chambers",
                "agenda_url": "https://example.com/agenda.pdf",
                "agenda_summary": ["Item A"],
                "status": "Scheduled",
            },
        ]

        merged = _merge_duplicate_meetings(records)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["agenda_url"], "https://example.com/agenda.pdf")
        self.assertTrue(merged[0]["agenda_summary"])


if __name__ == "__main__":
    unittest.main()
