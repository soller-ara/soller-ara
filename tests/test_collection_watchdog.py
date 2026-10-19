import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('collection_watchdog', ROOT / 'scripts/check_collection_watchdog.py')
watchdog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watchdog)


class CollectionWatchdogTests(unittest.TestCase):
    now = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)

    def test_only_stale_source_review_allows_collection(self):
        self.assertTrue(watchdog.should_collect({'sources_checked_at': '2026-10-19T09:59:59Z',
                                               'fetched_at': '2026-10-19T12:00:00Z'}, self.now))
        for value in ['2026-10-19T10:00:00Z', '2026-10-19T11:59:59Z', '2026-10-19T14:00:00+02:00']:
            self.assertFalse(watchdog.should_collect({'sources_checked_at': value}, self.now))

    def test_invalid_missing_naive_or_future_review_does_not_allow_collection(self):
        for value in [None, '', 'bad', '2026-10-19T12:06:00Z', '2026-10-19T08:00:00']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                watchdog.should_collect({'sources_checked_at': value, 'fetched_at': '2026-10-19T09:00:00Z'}, self.now)

    def test_a_queued_watchdog_becomes_a_noop_after_a_normal_collection(self):
        payload = {'sources_checked_at': '2026-10-19T08:00:00Z'}
        self.assertTrue(watchdog.should_collect(payload, self.now))
        payload['sources_checked_at'] = '2026-10-19T11:59:00Z'
        self.assertFalse(watchdog.should_collect(payload, self.now))

    def test_workflow_gates_only_watchdog_requests_under_the_same_existing_lock(self):
        workflow = (ROOT / '.github/workflows/update-sources.yml').read_text()
        self.assertIn('cron: "7 * * * *"', workflow)
        self.assertIn('group: "soller-ara-social-publish"', workflow)
        self.assertIn('default: false', workflow)
        self.assertIn('if: ${{ inputs.watchdog == true }}', workflow)
        self.assertIn('needs: watchdog-guard', workflow)
        self.assertIn("needs['watchdog-guard'].result == 'skipped'", workflow)
        self.assertIn("needs['watchdog-guard'].outputs.collect == 'true'", workflow)
        self.assertIn('run: python3 scripts/check_collection_watchdog.py', workflow)
        self.assertIn('ref: main', workflow.split('  update:')[0])


if __name__ == '__main__':
    unittest.main()
