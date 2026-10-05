import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from scripts import retry_manual_social as retry


class ManualRetryTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        self.enterContext(patch.multiple(retry, MANUAL_FILE=root/'manual.json', MODERATION_FILE=root/'moderation.json'))
        self.publisher = retry.publisher
        self.enterContext(patch.multiple(self.publisher, LOG_FILE=root/'log.json', TOKEN='test-only',
            POST_ID='', POST_URL='', TITLE='', BODY='', ORIGINAL_URL='', SOURCE_NAME='', IMAGE_URL='',
            DO_FACEBOOK=False, DO_INSTAGRAM=False, CONFIRMATION=''))
        self.accounts = self.enterContext(patch.object(self.publisher,'discover_accounts',return_value=('page','test-only','ig','soller.ara')))
        self.facebook = self.enterContext(patch.object(self.publisher,'publish_facebook'))
        self.instagram = self.enterContext(patch.object(self.publisher,'publish_instagram',return_value='ig-id'))
        self.posts = [{'id':'one','source_type':'own','title':'Latest edited title','summary':'Edited body',
                       'url':'https://example.test/one','media_url':'https://example.test/card.jpg',
                       'original_url':'https://www.facebook.com/story.php?id=1&story_fbid=2','source':'Policia'}]
        self.write(retry.MANUAL_FILE,{'posts':self.posts})
        self.write(retry.MODERATION_FILE,{'hidden_post_ids':[]})
        self.log = {'entries':[{'post_id':'one','platform':'instagram','status':'deferred','retry_requested':True}]}
        self.write(self.publisher.LOG_FILE,self.log)

    def write(self,path,data):
        path.write_text(json.dumps(data))

    def test_successful_retry_uses_latest_manual_content_and_is_not_repeated(self):
        self.assertEqual(retry.main(),0)
        self.instagram.assert_called_once()
        self.facebook.assert_not_called()
        self.assertEqual(self.publisher.TITLE,'Latest edited title')
        self.assertEqual(self.publisher.IMAGE_URL,self.posts[0]['media_url'])
        self.assertEqual(self.publisher.ORIGINAL_URL,self.posts[0]['original_url'])
        self.accounts.reset_mock(); self.instagram.reset_mock()
        self.assertEqual(retry.main(),0)
        self.accounts.assert_not_called(); self.instagram.assert_not_called()

    def test_existing_pause_keeps_pending_without_meta_requests(self):
        self.log['cooldowns']={'instagram_until':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}
        self.write(self.publisher.LOG_FILE,self.log)
        self.assertEqual(retry.main(),0)
        self.accounts.assert_not_called()
        self.assertEqual(json.loads(self.publisher.LOG_FILE.read_text()),self.log)

    def test_new_meta_limit_preserves_first_and_remaining_pending(self):
        self.posts.append({**self.posts[0],'id':'two'})
        self.write(retry.MANUAL_FILE,{'posts':self.posts})
        self.log['entries'].append({**self.log['entries'][0],'post_id':'two'})
        self.write(self.publisher.LOG_FILE,self.log)
        self.instagram.side_effect=RuntimeError('Application request limit reached [code=4, subcode=2207051]')
        self.assertEqual(retry.main(),0)
        self.instagram.assert_called_once()
        log=json.loads(self.publisher.LOG_FILE.read_text())
        self.assertEqual(len(retry.pending_posts(log,self.posts,set())),2)
        self.assertIn('instagram_until',log['cooldowns'])

    def test_hidden_deleted_historical_and_already_successful_posts_are_not_sent(self):
        for case in ['hidden','deleted','historical','success','error']:
            with self.subTest(case=case):
                log=json.loads(json.dumps(self.log))
                if case=='historical': log['entries'][0].pop('retry_requested')
                if case in ['success','error']:
                    log['entries'].append({'post_id':'one','platform':'instagram','status':case})
                self.write(self.publisher.LOG_FILE,log)
                self.write(retry.MANUAL_FILE,{'posts':[] if case=='deleted' else self.posts})
                self.write(retry.MODERATION_FILE,{'hidden_post_ids':['one'] if case=='hidden' else []})
                self.assertEqual(retry.main(),0)
                self.accounts.assert_not_called()

    def test_corrupt_manual_data_stops_before_publication(self):
        retry.MANUAL_FILE.write_text('broken JSON')
        with self.assertRaises(json.JSONDecodeError): retry.main()
        self.accounts.assert_not_called()

    def test_retry_does_not_depend_on_source_age_or_automatic_social_enabled(self):
        self.posts[0]['published_at']='2026-10-04T10:00:00Z'
        self.write(retry.MANUAL_FILE,{'posts':self.posts})
        self.assertEqual(retry.main(),0)
        self.instagram.assert_called_once()
