"""Simulated manual Facebook link shares: no Meta account is contacted."""
import json
from io import BytesIO
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
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
            POST_URL='https://soller-ara.github.io/soller-ara/noticies/manual-reference.html',
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

    def test_explicit_invalid_url_falls_back_to_existing_web_entry_once(self):
        self.graph.side_effect = [publisher.MetaGraphError('The url you supplied is invalid', 1500, 1611248),
                                  {'id': 'page_fallback'}]
        self.assertEqual(publisher.main(), 0)
        self.assertEqual(self.graph.call_count, 2)
        original, fallback = [call.kwargs['params'] for call in self.graph.call_args_list]
        self.assertEqual(original['link'], self.original)
        self.assertEqual(fallback['link'], publisher.POST_URL)
        self.assertEqual(fallback['message'], original['message'])
        self.assertIn(self.original, fallback['message'])
        self.assertEqual(set(fallback), {'message', 'link'})
        entry = json.loads(self.log_file.read_text())['entries'][-1]
        self.assertEqual((entry['status'], entry['remote_id']), ('success', 'page_fallback'))
        self.assertEqual(publisher.main(), 0)
        self.assertEqual(self.graph.call_count, 2)
        self.instagram.assert_not_called()

    def test_fallback_failure_is_not_retried(self):
        self.graph.side_effect = [publisher.MetaGraphError('Invalid URL', 1500, 1611248),
                                  publisher.MetaGraphError('Rejected fallback', 1500, 1611248)]
        self.assertEqual(publisher.main(), 1)
        self.assertEqual(self.graph.call_count, 2)
        entries = json.loads(self.log_file.read_text())['entries']
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[-1]['status'], 'error')
        self.assertIn('Rejected fallback', entries[-1]['error'])

    def test_network_permission_and_other_rejections_never_trigger_fallback(self):
        failures = [TimeoutError('Uncertain delivery'),
                    publisher.MetaGraphError('Permission denied', 200, None),
                    publisher.MetaGraphError('Expired token', 190, None),
                    publisher.MetaGraphError('Application request limit', 4, None),
                    publisher.MetaGraphError('Another rejection', 1500, 999),
                    RuntimeError('Invalid URL [code=1500, subcode=1611248]')]
        for failure in failures:
            with self.subTest(failure=str(failure)):
                self.graph.reset_mock()
                self.graph.side_effect = failure
                self.assertEqual(publisher.main(), 1)
                self.graph.assert_called_once()

    def test_missing_receipt_never_triggers_fallback(self):
        self.graph.return_value = {}
        self.assertEqual(publisher.main(), 1)
        self.graph.assert_called_once()
        self.assertEqual(json.loads(self.log_file.read_text())['entries'][-1]['status'], 'error')

    def test_own_article_or_unsafe_fallback_is_never_retried(self):
        cases = [{'CONTENT_TYPE': 'own'}, {'CONTENT_TYPE': 'event_poster'},
                 {'POST_URL': ''}, {'POST_URL': 'https://example.test/noticies/reference.html'},
                 {'POST_URL': self.original}, {'ORIGINAL_URL': ''}]
        for values in cases:
            with self.subTest(values=values), patch.multiple(publisher, **values):
                self.graph.reset_mock()
                self.graph.side_effect = publisher.MetaGraphError('Invalid URL', 1500, 1611248)
                with self.assertRaises(publisher.MetaGraphError):
                    publisher.publish_facebook('page', 'test-only-page')
                self.graph.assert_called_once()


class GraphRejectionTests(unittest.TestCase):
    def test_api_error_preserves_structured_code_without_exposing_token(self):
        payload = {'error': {'message': 'The url you supplied is invalid',
                             'code': 1500, 'error_subcode': 1611248}}
        rejection = HTTPError('https://graph.facebook.com/v26.0/page/feed', 400, 'Bad Request',
                              {}, BytesIO(json.dumps(payload).encode()))
        with patch.object(publisher, 'urlopen', side_effect=rejection):
            with self.assertRaises(publisher.MetaGraphError) as caught:
                publisher.graph('page/feed', method='POST', params={'link':'https://example.test'},
                                token='test-only-secret')
        self.assertEqual((caught.exception.code, caught.exception.subcode), (1500, 1611248))
        self.assertNotIn('test-only-secret', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
