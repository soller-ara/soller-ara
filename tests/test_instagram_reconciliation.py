from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts import reconcile_instagram_deliveries as repair


class InstagramReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.entry = {"post_id": "article", "platform": "instagram", "status": "verification_required",
                      "post_url": "https://example.test/one", "source": "Local source",
                      "mode": "automatic_collected", "recorded_at": "2026-10-07T10:00:00Z",
                      "error": "old response lost", "retry_requested": True}
        self.media = {"id": "real-id", "caption": "Article\nFont: Local source\nhttps://example.test/one",
                      "permalink": "https://www.instagram.com/p/example/", "timestamp": "2026-10-07T10:00:00Z"}

    def run_repair(self, entries, media, manual=(), public=(), detail=False):
        return repair.reconcile({"entries": entries, "cooldowns": {"instagram_until": "unchanged"}},
                                media, set(manual), set(public), lambda _: detail, "2026-10-17T10:00:00Z")

    def test_exact_receipt_preserves_history_dates_and_is_idempotent(self):
        original = deepcopy(self.entry)
        updated, counts = self.run_repair([self.entry], [self.media])
        entry = updated['entries'][0]
        self.assertEqual(counts['confirmed'], 1)
        self.assertEqual(entry['status'], 'success')
        self.assertEqual(entry['remote_id'], 'real-id')
        self.assertEqual(entry['recorded_at'], original['recorded_at'])
        self.assertEqual(entry['previous_error'], original['error'])
        self.assertFalse(entry['retry_requested'])
        self.assertEqual(self.entry, original)
        again, counts = repair.reconcile(updated, [self.media], set(), set(), lambda _: False, 'later')
        self.assertEqual(again, updated)
        self.assertEqual(counts['confirmed'], 0)

    def test_absence_prefix_different_source_and_ambiguity_do_not_confirm(self):
        for media in [[], [{**self.media, 'caption': self.media['caption'] + '?different=1'}],
                      [{**self.media, 'caption': self.media['caption'].replace('Local source', 'Other')}],
                      [self.media, {**self.media, 'id': 'second-copy'}]]:
            with self.subTest(media=media):
                updated, counts = self.run_repair([self.entry], media)
                self.assertEqual(updated['entries'], [self.entry])
                self.assertEqual(counts['confirmed'], 0)

    def test_deleted_manual_send_is_cancelled_only_when_absent_everywhere(self):
        identifier = 'soller-ara-0123456789abcdef'
        entry = {**self.entry, 'post_id': identifier, 'mode': 'manual', 'status': 'deferred',
                 'post_url': f'https://soller-ara.github.io/soller-ara/noticies/{identifier}.html'}
        for kwargs in [{'manual': [identifier]}, {'public': [identifier]}, {'detail': True}]:
            updated, counts = self.run_repair([entry], [], **kwargs)
            self.assertEqual(updated['entries'][0]['status'], 'deferred')
        updated, counts = self.run_repair([entry], [])
        self.assertEqual(updated['entries'][0]['status'], 'cancelled')
        self.assertFalse(updated['entries'][0]['retry_requested'])
        self.assertEqual(counts['cancelled_removed'], 1)

    def test_existing_success_and_facebook_entries_are_never_changed(self):
        entries = [self.entry, {**self.entry, 'status': 'success', 'remote_id': 'previous'},
                   {**self.entry, 'platform': 'facebook'}]
        updated, counts = self.run_repair(entries, [self.media])
        self.assertEqual(updated['entries'], entries)
        self.assertEqual(counts['confirmed'], 0)

    def test_failed_or_incomplete_meta_read_never_writes_the_log(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root/'data').mkdir()
            for name in ['manual_posts.json', 'posts.json']:
                (root/'data'/name).write_text('{"posts": []}')
            log = root/'data/social_publish_log.json'; text = json.dumps({'entries': [self.entry]}); log.write_text(text)
            with patch.object(repair, 'ROOT', root), patch.object(repair.publisher, 'LOG_FILE', log), \
                 patch.object(repair.publisher, 'discover_accounts', return_value=('', '', 'account', 'soller.ara')), \
                 patch.object(repair.publisher, 'graph', return_value={'data': [], 'paging': {'next': 'more'}}) as graph:
                with self.assertRaises(ValueError):
                    repair.main()
                self.assertEqual(log.read_text(), text)
                self.assertEqual(graph.call_args.kwargs['method'], 'GET')


if __name__ == '__main__':
    unittest.main()
