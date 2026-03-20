import unittest

from scraper.coloradosprings_legistar import _normalize_cs_meeting_type


class TestColoradoSpringsMeetingType(unittest.TestCase):
    def test_work_session_detected_from_meeting_type_name(self):
        ev = {
            "EventMeetingTypeName": "City Council Work Session",
            "EventAgendaStatusName": "Final",
        }
        self.assertEqual(_normalize_cs_meeting_type(ev), "City Council Work Session")

    def test_regular_meeting_not_overridden_by_agenda_status(self):
        ev = {
            "EventMeetingTypeName": "City Council",
            "EventAgendaStatusName": "Final",
        }
        self.assertEqual(_normalize_cs_meeting_type(ev), "City Council Meeting")


if __name__ == "__main__":
    unittest.main()
