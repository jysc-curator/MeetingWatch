import unittest
from datetime import date

from scraper.main import _preserve_upcoming_salida_on_scrape_gaps


class TestSalidaPreserveOnGap(unittest.TestCase):
    def test_preserve_upcoming_salida_when_new_run_has_none(self):
        previous = [
            {
                "id": "salida-2026-04-06-ws",
                "city": "Salida",
                "meeting_type": "City Council Work Session",
                "date": "2026-04-06",
                "status": "Canceled",
                "source": "https://salidaco.portal.civicclerk.com/",
            }
        ]
        new_active = [
            {"id": "co-1", "city": "Colorado Springs", "meeting_type": "City Council Meeting", "date": "2026-04-07"}
        ]

        merged = _preserve_upcoming_salida_on_scrape_gaps(
            new_active=new_active,
            previous_active=previous,
            today=date(2026, 4, 4),
        )

        self.assertTrue(any(m.get("city") == "Salida" and m.get("stale_from_previous_run") is True for m in merged))

    def test_no_preserve_when_salida_exists_in_new_run(self):
        previous = [
            {"id": "salida-older", "city": "Salida", "meeting_type": "City Council Meeting", "date": "2026-04-06"}
        ]
        new_active = [
            {"id": "salida-new", "city": "Salida", "meeting_type": "City Council Work Session", "date": "2026-04-06"}
        ]

        merged = _preserve_upcoming_salida_on_scrape_gaps(
            new_active=new_active,
            previous_active=previous,
            today=date(2026, 4, 4),
        )

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["id"], "salida-new")


if __name__ == "__main__":
    unittest.main()
