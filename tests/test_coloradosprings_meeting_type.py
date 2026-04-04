import unittest

from scraper.coloradosprings_legistar import (
    _normalize_cs_meeting_type,
    _normalize_cs_status_from_event,
    _normalize_cs_status_from_calendar_row,
)


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

    def test_status_detects_canceled_from_api_fields(self):
        ev = {
            "EventStatusName": "Canceled",
            "EventMeetingTypeName": "City Council",
        }
        self.assertEqual(_normalize_cs_status_from_event(ev), "Canceled")

    def test_status_detects_canceled_from_calendar_row_text(self):
        self.assertEqual(
            _normalize_cs_status_from_calendar_row(
                dept="City Council",
                location_text="Council Chambers",
                row_text="City Council 4/14/2026 CANCELED Meeting details",
            ),
            "Canceled",
        )

    def test_status_defaults_to_scheduled(self):
        ev = {
            "EventAgendaStatusName": "Final",
            "EventMeetingTypeName": "City Council",
        }
        self.assertEqual(_normalize_cs_status_from_event(ev), "Scheduled")


if __name__ == "__main__":
    unittest.main()
