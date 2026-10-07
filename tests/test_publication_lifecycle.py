"""Regression tests use temporary files and mocked Meta calls; never publish."""
import importlib.util
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

def module(name):
    spec = importlib.util.spec_from_file_location('audit_' + name, ROOT / 'scripts' / (name + '.py'))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded

add = module('add_own_post')
edit = module('edit_own_post')
manage = module('manage_posts')
own = module('publish_own_social')
auto = module('publish_collected_social')
prepare = module('prepare_collected_social')

class PublicationLifecycleTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / 'data').mkdir()
        (self.root / 'noticies').mkdir()
        (self.root / 'assets/generated').mkdir(parents=True)
        for mod in (add, edit, manage):
            for key, value in {'ROOT':self.root, 'MANUAL_FILE':self.root/'data/manual.json',
                    'POSTS_FILE':self.root/'data/posts.json','POSTS_JS_FILE':self.root/'data/posts.js',
                    'MODERATION_FILE':self.root/'data/moderation.json','DETAIL_DIR':self.root/'noticies',
                    'GENERATED_DIR':self.root/'assets/generated'}.items():
                if hasattr(mod, key):
                    self.enterContext(patch.object(mod, key, value))
        self.enterContext(patch.object(edit, 'MODERATION_FILE', self.root/'data/moderation.json', create=True))
        self.write(add.MANUAL_FILE, {'posts':[]})
        self.write(add.POSTS_FILE, {'posts':[]})
        self.write(edit.MODERATION_FILE, {'hidden_post_ids':[], 'category_overrides':{}})
        for mod in (add, edit):
            self.enterContext(patch.multiple(mod, TITLE='Títol propi', BODY='Text propi', CATEGORY='agenda',
                create=True, LANGUAGE='ca', SOURCE_NAME='Ajuntament de Deià', ORIGINAL_URL='https://www.facebook.com/story.php?story_fbid=1&id=2',
                IMAGE_URL='', CONTENT_TYPE='social_link', SHOW_IN_NOW=False))
        self.enterContext(patch.object(add, 'CONFIRMATION', 'PUBLICAR'))
        self.enterContext(patch.object(add, 'PUBLISH_KEY', 'same-run'))
        self.enterContext(patch.object(edit, 'CONFIRMATION', 'GUARDAR'))
        self.enterContext(patch.dict(os.environ, {'GITHUB_ENV':str(self.root/'env')}))
        self.card = self.enterContext(patch.object(add, 'generate_social_card', return_value=add.SITE_URL+'/assets/generated/'+add.stable_id_from_key('same-run')+'.jpg'))

    def write(self, path, data):
        path.write_text(json.dumps(data), encoding='utf-8')

    def create(self):
        self.assertEqual(add.main(), 0)
        post = json.loads(add.MANUAL_FILE.read_text())['posts'][-1]
        self.enterContext(patch.object(edit, 'POST_ID', post['id']))
        self.enterContext(patch.object(manage, 'POST_ID', post['id']))
        return post

    def test_workflow_retry_preserves_identity_date_and_content(self):
        before = self.create()
        with patch.object(add, 'TITLE', 'Different retry title'):
            self.assertEqual(add.main(), 0)
        self.assertEqual(json.loads(add.MANUAL_FILE.read_text())['posts'], [before])
        self.card.assert_called_once()
        self.assertEqual((self.root/'env').read_text().count('OWN_POST_ID='), 2)

    def test_manual_lifecycle_keeps_source_review_time_and_updates_feed_time(self):
        review = '2026-10-06T08:00:00+00:00'
        self.write(add.POSTS_FILE, {'posts': [], 'fetched_at': review, 'source_status': [{'ok': True}]})
        self.create()
        with patch.object(edit, 'generate_social_card', return_value='https://example.test/card.jpg'):
            self.assertEqual(edit.main(), 0)
        for operation in (lambda: None, manage.hide, manage.unhide, manage.delete_own):
            operation()
            payload = json.loads(add.POSTS_FILE.read_text())
            self.assertEqual(payload['sources_checked_at'], review)
            self.assertGreater(payload['fetched_at'], review)
            fallback = json.loads(add.POSTS_JS_FILE.read_text().removeprefix('window.SOLLER_ARA_DATA = ').strip().removesuffix(';'))
            self.assertEqual(fallback, payload)

    def test_create_persists_poster_type_and_its_authorized_image(self):
        with patch.multiple(add, CONTENT_TYPE='event_poster', IMAGE_URL='https://example.test/cartell.jpg'):
            post = self.create()
        self.assertEqual(post['content_type'], 'event_poster')
        self.assertTrue(post['image_allowed'])
        self.assertEqual(post['media_url'], 'https://example.test/cartell.jpg')
        self.card.assert_not_called()

    def test_new_detail_page_uses_the_current_brand_asset(self):
        post = self.create()
        html = (self.root/'noticies'/f'{post["id"]}.html').read_text()
        self.assertIn('../assets/brand/logo-soller-ara-web.png', html)
        self.assertNotIn('class="brand-mark" aria-hidden="true">SA', html)

    def test_edit_regenerates_card_and_clears_old_category_override(self):
        post = self.create()
        self.write(edit.MODERATION_FILE, {'hidden_post_ids':[], 'category_overrides':{post['id']:'sports','other':'culture'}})
        with patch.multiple(edit, TITLE='Nou títol', CATEGORY='politics', SOURCE_NAME='Nova font'), \
             patch.object(edit, 'generate_social_card', return_value=post['media_url']) as card:
            self.assertEqual(edit.main(), 0)
        card.assert_called_once_with(post['id'], 'Nou títol', 'politics')
        updated = json.loads(edit.MANUAL_FILE.read_text())['posts'][0]
        self.assertEqual(updated['published_at'], post['published_at'])
        self.assertEqual(updated['media_url'], post['media_url'])
        self.assertEqual(updated['category'], 'politics')
        self.assertNotEqual(updated['source_id'], post['source_id'])
        self.assertFalse(updated['show_in_now'])
        self.assertEqual(json.loads(edit.MODERATION_FILE.read_text())['category_overrides'], {'other':'culture'})

    def test_edit_reference_to_own_clears_origin_and_source(self):
        self.create()
        with patch.multiple(edit, CONTENT_TYPE='own', ORIGINAL_URL='', SOURCE_NAME=''), \
             patch.object(edit, 'generate_social_card', return_value='https://example.test/card.jpg'):
            self.assertEqual(edit.main(), 0)
        post = json.loads(edit.MANUAL_FILE.read_text())['posts'][0]
        self.assertEqual(post['original_url'], '')
        self.assertEqual(post['source_id'], 'soller-ara')
        self.assertEqual(post['content_policy'], 'owned_content')

    def test_blank_link_keeps_reference_without_generated_card(self):
        with patch.multiple(add, TITLE='', BODY=''):
            post = self.create()
        self.assertNotIn('media_url', post)
        self.card.assert_not_called()
        with patch.multiple(edit, TITLE='', BODY=''):
            self.assertEqual(edit.main(), 0)
        self.assertEqual(json.loads(edit.MANUAL_FILE.read_text())['posts'][0]['title'], '')

    def test_restoring_hidden_manual_entry_uses_latest_edit(self):
        post = self.create()
        manage.hide()
        with patch.object(edit, 'TITLE', 'Editat mentre estava ocult'), \
             patch.object(edit, 'generate_social_card', return_value=post['media_url']):
            self.assertEqual(edit.main(), 0)
        self.assertEqual(json.loads(edit.POSTS_FILE.read_text())['posts'], [])
        manage.unhide()
        self.assertEqual(json.loads(edit.POSTS_FILE.read_text())['posts'][0]['title'], 'Editat mentre estava ocult')

    def test_delete_cannot_remove_another_posts_image(self):
        post = self.create()
        other = self.root/'assets/generated/soller-ara-other.jpg'
        other.write_bytes(b'other asset')
        self.write(add.MANUAL_FILE, {'posts':[{**post,'media_url':add.SITE_URL+'/assets/generated/'+other.name}]})
        self.write(edit.MODERATION_FILE, {'category_overrides':{post['id']:'social'}})
        manage.delete_own()
        self.assertTrue(other.exists())
        self.assertEqual(json.loads(edit.MODERATION_FILE.read_text())['category_overrides'], {})
        self.assertEqual(json.loads(add.POSTS_FILE.read_text())['posts'], [])

    def test_corrupt_feed_prevents_manual_write(self):
        add.POSTS_FILE.write_text('broken JSON')
        before = add.MANUAL_FILE.read_text()
        with self.assertRaises(json.JSONDecodeError):
            add.main()
        self.assertEqual(add.MANUAL_FILE.read_text(), before)
        self.card.assert_not_called()

    def test_corrupt_moderation_prevents_edit(self):
        self.create()
        edit.MODERATION_FILE.write_text('broken JSON')
        before = edit.MANUAL_FILE.read_text()
        with self.assertRaises(json.JSONDecodeError):
            edit.main()
        self.assertEqual(edit.MANUAL_FILE.read_text(), before)

    def test_invalid_edit_urls_leave_publication_unchanged(self):
        self.create()
        before = edit.MANUAL_FILE.read_text()
        with patch.object(edit, 'ORIGINAL_URL', 'javascript:alert(1)'):
            self.assertEqual(edit.main(), 2)
        self.assertEqual(edit.MANUAL_FILE.read_text(), before)

class ManualSocialSafetyTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.enterContext(patch.multiple(own, LOG_FILE=self.root/'social.json', POST_ID='manual-1',
                CONFIRMATION='PUBLICAR', TITLE='Title', BODY='Body', ORIGINAL_URL='', SOURCE_NAME='',
                DO_FACEBOOK=True, DO_INSTAGRAM=True, TOKEN='test-only'))
        self.accounts = self.enterContext(patch.object(own, 'discover_accounts', return_value=('page','test-only','ig','soller.ara')))
        self.fb = self.enterContext(patch.object(own, 'publish_facebook', return_value='fb-post'))
        self.ig = self.enterContext(patch.object(own, 'publish_instagram', return_value='ig-post'))

    def write(self, log):
        own.LOG_FILE.write_text(json.dumps(log))

    def test_confirmed_success_survives_later_error(self):
        self.write({'entries':[{'post_id':'manual-1','platform':'facebook','status':'success'},
                               {'post_id':'manual-1','platform':'facebook','status':'error'}]})
        self.assertEqual(own.main(), 0)
        self.fb.assert_not_called()
        self.ig.assert_called_once()

    def test_all_successful_retry_skips_account_discovery(self):
        self.assertEqual(own.main(), 0)
        self.accounts.reset_mock(); self.fb.reset_mock(); self.ig.reset_mock()
        self.assertEqual(own.main(), 0)
        self.accounts.assert_not_called(); self.fb.assert_not_called(); self.ig.assert_not_called()

    def test_instagram_failure_retry_does_not_repeat_facebook(self):
        self.ig.side_effect = RuntimeError('simulated error')
        self.assertEqual(own.main(), 1)
        self.ig.side_effect = None
        self.fb.reset_mock()
        self.assertEqual(own.main(), 0)
        self.fb.assert_not_called()

    def test_rate_limit_pauses_manual_instagram_but_facebook_continues(self):
        self.ig.side_effect = RuntimeError('Application request limit reached [code=4, subcode=2207051]')
        self.assertEqual(own.main(), 0)
        self.fb.assert_called_once()
        self.assertEqual(json.loads(own.LOG_FILE.read_text())['entries'][-1]['status'], 'deferred')
        self.accounts.reset_mock(); self.ig.reset_mock()
        self.assertEqual(own.main(), 0)
        self.accounts.assert_not_called(); self.ig.assert_not_called()

    def test_existing_pause_does_not_block_new_facebook_send(self):
        self.write({'entries':[], 'cooldowns':{'instagram_until':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}})
        self.assertEqual(own.main(), 0)
        self.fb.assert_called_once(); self.ig.assert_not_called()

    def test_rate_limit_does_not_hide_facebook_failure(self):
        self.fb.side_effect = RuntimeError('Facebook failed')
        self.ig.side_effect = RuntimeError('Application request limit reached [code=4]')
        self.assertEqual(own.main(), 1)

    def test_corrupt_log_stops_before_any_meta_request(self):
        own.LOG_FILE.write_text('broken JSON')
        with self.assertRaises(json.JSONDecodeError):
            own.main()
        self.accounts.assert_not_called(); self.fb.assert_not_called(); self.ig.assert_not_called()

    def test_blank_reference_can_be_sent_to_facebook(self):
        with patch.multiple(own, TITLE='', BODY='', ORIGINAL_URL='https://www.facebook.com/story.php?id=1&story_fbid=2', DO_INSTAGRAM=False):
            self.assertEqual(own.main(), 0)
            self.fb.assert_called_once()
            self.assertIn('https://www.facebook.com/', own.source_reference())

    def test_account_discovery_rejects_other_or_ambiguous_page(self):
        real = module("publish_own_social")
        for pages in [[{'id':'1','name':'Other','access_token':'test-only','tasks':['CREATE_CONTENT']}],
                      [{'id':str(i),'name':'Sóller Ara','access_token':'test-only','tasks':['CREATE_CONTENT']} for i in (1,2)]]:
            with patch.object(real, 'graph', return_value={'data':pages}):
                with self.assertRaises(RuntimeError):
                    # Test the real discovery function even though main is mocked.
                    real.discover_accounts()

    def test_instagram_rejects_wrong_username_before_network(self):
        real = module('publish_own_social')
        with patch.object(real, 'graph') as graph:
            with self.assertRaises(RuntimeError):
                real.publish_instagram('ig','different.account','test-only')
            graph.assert_not_called()

    def test_automatic_loader_rejects_corrupt_json_instead_of_resetting(self):
        path=self.root/'invalid.json';path.write_text('broken JSON')
        for mod in (auto,prepare):
            with self.assertRaises(json.JSONDecodeError):
                mod.load_json(path, {'entries':[]})
            path.write_text('{}')
            with self.assertRaises(ValueError):
                mod.load_json(path, {'entries':[]})
            path.write_text('broken JSON')

    def test_old_confirmed_success_is_kept_when_log_is_trimmed(self):
        log={'entries':[{'post_id':'old','platform':'facebook','status':'success'}]+
             [{'post_id':str(i),'platform':'instagram','status':'error'} for i in range(1001)]}
        with patch.object(auto, 'LOG_FILE', self.root/'auto.json'):
            auto.save_log(log)
        self.assertTrue(auto.already_published(log, 'old', 'facebook'))
        self.assertEqual(len(log['entries']),1001)

if __name__ == '__main__':
    unittest.main()
