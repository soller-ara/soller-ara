"""Simulated manual Facebook link shares: no Meta account is contacted."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import publish_own_social as publisher


class FacebookLinkTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.log_file = Path(folder.name) / 'social.json'
        self.original = 'https://www.instagram.com/p/Reference123/?igsh=reference'
        self.enterContext(patch.multiple(publisher, LOG_FILE=self.log_file, TOKEN='test-only',
            CONFIRMATION='PUBLICAR', POST_ID='manual-reference',
            POST_URL='https://example.test/noticies/manual-reference.html',
            TITLE='', BODY='', SOURCE_NAME='Entitat de Sóller', ORIGINAL_URL=self.original,
            CONTENT_TYPE='social_link', DO_FACEBOOK=True, DO_INSTAGRAM=False))
        self.discovery = self.enterContext(patch.object(publisher, 'discover_accounts',
            return_value=('page', 'test-only-page', 'ig', 'soller.ara')))
        self.graph = self.enterContext(patch.object(publisher, 'graph', return_value={'id':'page_remote'}))
        self.instagram = self.enterContext(patch.object(publisher, 'publish_instagram',
            side_effect=AssertionError('Instagram must not be activated by a Facebook share')))

    def test_bare_instagram_reference_shares_original_once_with_attribution(self):
        self.assertEqual(publisher.main(), 0)
        self.graph.assert_called_once()
        args, kwargs = self.graph.call_args
        self.assertEqual(args, ('page/feed',))
        self.assertEqual(kwargs['method'], 'POST')
        self.assertEqual(kwargs['params']['link'], self.original)
        self.assertIn('Entitat de Sóller', kwargs['params']['message'])
        self.assertIn(self.original, kwargs['params']['message'])
        self.assertEqual(set(kwargs['params']), {'message','link'})
        log = json.loads(self.log_file.read_text())
        self.assertEqual(log['entries'][-1]['status'], 'success')
        self.assertEqual(log['entries'][-1]['post_id'], 'manual-reference')
        self.assertEqual(publisher.main(), 0)
        self.graph.assert_called_once()  # Repeating the job uses the existing receipt.
        self.instagram.assert_not_called()

    def test_authored_text_is_preserved_without_reading_the_source(self):
        with patch.multiple(publisher, TITLE='Agenda de Sóller', BODY='Text propi revisat.'):
            self.assertEqual(publisher.main(), 0)
        params = self.graph.call_args.kwargs['params']
        self.assertTrue(params['message'].startswith('Agenda de Sóller\n\nText propi revisat.'))
        self.assertEqual(params['link'], self.original)

    def test_web_only_never_contacts_social_accounts(self):
        with patch.object(publisher, 'DO_FACEBOOK', False):
            self.assertEqual(publisher.main(), 0)
        self.discovery.assert_not_called()
        self.graph.assert_not_called()
        self.assertFalse(self.log_file.exists())

    def test_own_articles_and_authorized_posters_keep_their_own_link(self):
        for content_type, original in [('own',''),('event_poster',self.original)]:
            with self.subTest(content_type=content_type):
                with patch.multiple(publisher, CONTENT_TYPE=content_type, ORIGINAL_URL=original,
                                    TITLE='Titular propi', BODY='Text propi'):
                    publisher.publish_facebook('page', 'test-only-page')
                self.assertEqual(self.graph.call_args.kwargs['params']['link'], publisher.POST_URL)

    def test_facebook_error_is_logged_without_a_false_success_or_blind_retry(self):
        self.graph.side_effect = RuntimeError('Simulated provider rejection')
        self.assertEqual(publisher.main(), 1)
        self.graph.assert_called_once()
        entry = json.loads(self.log_file.read_text())['entries'][-1]
        self.assertEqual(entry['platform'], 'facebook')
        self.assertEqual(entry['status'], 'error')
        self.assertIn('Simulated provider rejection', entry['error'])
        self.instagram.assert_not_called()


if __name__ == '__main__':
    unittest.main()
