import unittest

from scraper.salida_civicclerk import _normalize_salida_status


class TestSalidaCanceledStatus(unittest.TestCase):
    def test_canceled_detected_from_title_variants(self):
        self.assertEqual(_normalize_salida_status("City Council Work Session - CANCELED"), "Canceled")
        self.assertEqual(_normalize_salida_status("City Council Meeting (cancelled)"), "Canceled")

    def test_default_scheduled(self):
        self.assertEqual(_normalize_salida_status("City Council Regular Meeting"), "Scheduled")


if __name__ == "__main__":
    unittest.main()
