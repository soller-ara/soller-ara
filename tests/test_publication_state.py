import unittest
from datetime import datetime, timezone
from scripts.publication_state import aemet_period, aemet_post_state, alert_can_be_published


class AlertStateTests(unittest.TestCase):
    def test_explicit_aemet_timezone_and_expiry(self):
        text = "De 06:00 05-10-2026 CEST (UTC+2) a 08:59 05-10-2026 CEST (UTC+2)."
        period = aemet_period(text)
        self.assertEqual(period["alert_valid_from"], "2026-10-05T04:00:00+00:00")
        self.assertEqual(period["alert_valid_until"], "2026-10-05T06:59:00+00:00")
        for hour, minute, expected in [(3, 0, "scheduled"), (5, 0, "active"), (6, 59, "expired")]:
            now = datetime(2026, 10, 5, hour, minute, tzinfo=timezone.utc)
            post = aemet_post_state({"summary": text}, in_feed=True, now=now)
            self.assertEqual(post["alert_status"], expected)
            self.assertEqual(alert_can_be_published(post, now), expected != "expired")

    def test_invalid_period_cannot_become_current_warning(self):
        for text in ["", "De 99:00 05-10-2026 CET (UTC+1) a 08:00 05-10-2026 CET (UTC+1)",
                     "De 09:00 05-10-2026 CET (UTC+1) a 08:00 05-10-2026 CET (UTC+1)"]:
            self.assertEqual(aemet_period(text), {})
            self.assertFalse(alert_can_be_published(aemet_post_state({"summary": text}, in_feed=True)))

    def test_removed_live_warning_is_archived_and_not_redistributed(self):
        post = {"alert_valid_until": "2026-10-05T12:00:00+00:00"}
        now = datetime(2026, 10, 5, 8, tzinfo=timezone.utc)
        archived = aemet_post_state(post, in_feed=False, now=now)
        self.assertEqual(archived["alert_status"], "archived")
        self.assertFalse(alert_can_be_published(archived, now))
