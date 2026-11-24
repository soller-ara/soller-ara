"""Diagnostics must be GET-only and never expose account tokens."""
from contextlib import redirect_stdout
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from scripts import diagnose_facebook_link_readonly as diag


class DiagnosticTests(unittest.TestCase):
    def test_graph_request_is_get_and_auth_stays_in_header(self):
        opener = MagicMock()
        response = opener.open.return_value.__enter__.return_value
        response.status = 200
        response.read.return_value = b'{"id":"test"}'
        with patch.object(diag, 'build_opener', return_value=opener):
            result = diag.graph_get('', {'id': 'https://www.instagram.com/p/Test/'}, 'private-test-token')
        req = opener.open.call_args.args[0]
        self.assertEqual(req.get_method(), 'GET')
        self.assertIsNone(req.data)
        self.assertNotIn('private-test-token', req.full_url)
        self.assertEqual(req.get_header('Authorization'), 'Bearer private-test-token')
        self.assertTrue(result['ok'])

    def test_graph_paths_cannot_target_other_accounts_or_publishing_edges(self):
        with patch.object(diag, 'build_opener') as network:
            for path in ['123_456/attachments', diag.PAGE_ID+'/feed', 'me/photos', 'media_publish']:
                with self.subTest(path=path), self.assertRaises(ValueError):
                    diag.graph_get(path, {}, 'test')
            network.assert_not_called()

    def test_explicit_provider_error_preserves_trace_and_redacts_token(self):
        error = {'error': {'message': 'Failure private-token', 'code': 1500,
                           'error_subcode': 1611248, 'fbtrace_id': 'trace-example'}}
        opener = MagicMock()
        opener.open.side_effect = HTTPError('https://graph.facebook.com/', 400, 'Bad Request',
                                           {}, BytesIO(json.dumps(error).encode()))
        with patch.object(diag, 'build_opener', return_value=opener):
            result = diag.graph_get('', {'id': 'https://www.instagram.com/p/Test/'}, 'private-token')
        self.assertEqual(result['error']['error_subcode'], 1611248)
        self.assertEqual(result['error']['fbtrace_id'], 'trace-example')
        self.assertNotIn('private-token', json.dumps(result))

    def test_redirects_never_forward_authorization(self):
        self.assertIsNone(diag.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.test/'))

    def test_public_probe_reads_html_only_and_never_sends_a_token(self):
        opener = MagicMock()
        response = opener.open.return_value.__enter__.return_value
        response.status = 200
        response.read.return_value = b'<meta property="og:image" content="https://cdn.test/image.jpg"><meta property="og:type" content="article">'
        with patch.object(diag, 'build_opener', return_value=opener):
            result = diag.public_metadata('https://www.instagram.com/p/Test/?igsh=tracking')
        req = opener.open.call_args.args[0]
        self.assertEqual(req.get_method(), 'GET')
        self.assertIsNone(req.get_header('Authorization'))
        self.assertEqual(opener.open.call_count, 1)
        self.assertEqual(result['image_host'], 'cdn.test')
        self.assertTrue(result['has_image'])

    def test_public_probe_refuses_unrelated_sites_and_private_endpoints(self):
        with patch.object(diag, 'build_opener') as network:
            for url in ['https://other.test/p/Test/', 'http://www.instagram.com/p/Test/',
                        'https://www.instagram.com/accounts/login/']:
                with self.subTest(url=url), self.assertRaises(ValueError):
                    diag.public_metadata(url)
            network.assert_not_called()

    def test_image_summary_does_not_download_or_expose_image_url(self):
        result = diag.attachment_summary({'type':'link', 'media': {'image': {
            'src':'https://cdn.test/photo.jpg?signature=private', 'width':1080, 'height':1350}}})
        self.assertTrue(result['has_image'])
        self.assertEqual(result['image_size'], [1080, 1350])
        self.assertNotIn('signature', json.dumps(result))

    def test_report_redacts_both_tokens_before_output(self):
        report = {'field':'user-token-secret and page-token-secret'}
        encoded = diag.safe_json(report, ('user-token-secret', 'page-token-secret'))
        self.assertNotIn('user-token-secret', encoded)
        self.assertNotIn('page-token-secret', encoded)

    def test_missing_token_stops_without_network(self):
        with patch.dict(os.environ, {'META_ACCESS_TOKEN':''}), patch.object(diag,'graph_get') as network:
            with redirect_stdout(StringIO()):
                self.assertEqual(diag.main(), 2)
            network.assert_not_called()

    def test_full_report_compares_four_original_and_clean_urls_without_publication(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'data').mkdir()
            posts = [{'id':identifier, 'original_url':f'https://www.instagram.com/p/Post{i}/?igsh=ref'}
                     for i, identifier in enumerate(diag.POST_IDS)]
            entries = [{'post_id':identifier, 'platform':'facebook', 'status':'success',
                        'remote_id':f'{diag.PAGE_ID}_{i+1}'} for i, identifier in enumerate(diag.POST_IDS)]
            (root/'data/manual_posts.json').write_text(json.dumps({'posts':posts}))
            (root/'data/social_publish_log.json').write_text(json.dumps({'entries':entries}))
            summary = root/'summary.md'
            def provider(path, params, token):
                if path=='me/accounts':
                    return {'ok':True,'data':{'data':[{'id':diag.PAGE_ID,'name':'Sóller Ara',
                                                        'access_token':'test-page-secret','tasks':['CREATE_CONTENT']}]}}
                if path=='me/permissions':
                    return {'ok':True,'data':{'data':[{'permission':'pages_read_engagement','status':'granted'}]}}
                if path.endswith('/attachments'):
                    return {'ok':True,'data':{'data':[{'type':'link','media':{'image':{'src':'https://cdn.test/one.jpg'}}}]}}
                return {'ok':True,'data':{'id':'example'}}
            before = {p.name:p.read_bytes() for p in (root/'data').iterdir()}
            output = StringIO()
            with patch.object(diag,'ROOT',root), patch.dict(os.environ,{
                    'META_ACCESS_TOKEN':'test-user-secret','GITHUB_STEP_SUMMARY':str(summary)}), \
                 patch.object(diag,'graph_get',side_effect=provider) as graph, \
                 patch.object(diag,'public_metadata',return_value={'has_image':True}) as public, \
                 redirect_stdout(output):
                self.assertEqual(diag.main(),0)
            self.assertEqual(graph.call_count,18)  # accounts + permissions + 8 URL reads + 8 own-post reads
            self.assertEqual(public.call_count,8)
            cases = [json.loads(line.removeprefix('LINK_DIAGNOSTIC ')) for line in output.getvalue().splitlines()
                     if line.startswith('LINK_DIAGNOSTIC ')]
            self.assertEqual(len(cases),4)
            self.assertTrue(all(len(case['urls'])==2 for case in cases))
            self.assertTrue(all('?' not in case['urls'][1]['url'] for case in cases))
            text = output.getvalue()+summary.read_text()
            self.assertNotIn('test-user-secret',text)
            self.assertNotIn('test-page-secret',text)
            self.assertEqual(before,{p.name:p.read_bytes() for p in (root/'data').iterdir()})


if __name__ == '__main__':
    unittest.main()
