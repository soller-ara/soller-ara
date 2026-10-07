"""The administrative log must retain its history or fail without overwriting it."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import activity_log


class ActivityLogTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "activity.json"
        self.enterContext(patch.object(activity_log, "ACTIVITY_FILE", self.path))

    def test_invalid_history_is_never_replaced(self):
        for text in ("broken JSON", "[]", '{"entries": {}}', '{"entries": [null]}'):
            with self.subTest(text=text):
                self.path.write_text(text)
                with self.assertRaises((ValueError, json.JSONDecodeError)):
                    activity_log.append_activity("publish", area="publications")
                self.assertEqual(self.path.read_text(), text)

    def test_new_log_and_existing_history_are_preserved(self):
        activity_log.append_activity("publish", area="publications", target_id="one")
        first = json.loads(self.path.read_text())["entries"][0]
        activity_log.append_activity("edit", area="publications", target_id="one")
        payload = json.loads(self.path.read_text())
        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["entries"][1], first)
        self.assertEqual(payload["entries"][0]["action"], "edit")

    def test_history_remains_bounded(self):
        self.path.write_text(json.dumps({"entries": [{"id": str(i)} for i in range(250)]}))
        activity_log.append_activity("edit", area="publications")
        self.assertEqual(len(json.loads(self.path.read_text())["entries"]), 250)
