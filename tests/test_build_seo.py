"""SEO checks use temporary sites and local Git repositories; no publication."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_seo', ROOT / 'scripts/build_seo.py')
seo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seo)


class Metadata(HTMLParser):
    def __init__(self, document):
        super().__init__()
        self.tags = []
        self.feed(document)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class SeoTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'data').mkdir()
        (self.root / 'noticies').mkdir()
        self.document = ('<!doctype html><html><head><title>Test</title>'
                         '<meta name="description" content="old" />'
                         '<meta property="og:description" content="old" />'
                         '<link rel="canonical" href="https://wrong.test" />'
                         '</head><body><section><p>Visible original content</p></section></body></html>')
        for path in seo.STATIC:
            (self.root / path).write_text(self.document)
        self.posts = []
        self.hidden = []
        self.add_post(1)

    def add_post(self, number, **overrides):
        post = {'id': f'soller-ara-{number:016x}', 'source_type': 'own',
                'title': 'Informació local amb context',
                'summary': 'Informació local detallada amb context per entendre la publicació i consultar la font original. ' * 2,
                'published_at': '2026-09-18T10:00:00+00:00', 'show_in_now': False,
                'original_url': 'https://example.test/source', 'language': 'ca'}
        post.update(overrides)
        self.posts.append(post)
        (self.root / 'noticies' / (post['id'] + '.html')).write_text(self.document)
        return post

    def inventories(self):
        (self.root / 'data/manual_posts.json').write_text(json.dumps({'posts': self.posts}))
        (self.root / 'data/moderation.json').write_text(json.dumps({'hidden_post_ids': self.hidden}))

    def build(self):
        self.inventories()
        return seo.build(self.root)

    def urls(self):
        tree = ET.parse(self.root / 'sitemap.xml')
        return {entry.find(f'{{{seo.NS}}}loc').text: entry.findtext(f'{{{seo.NS}}}lastmod')
                for entry in tree.getroot()}

    def detail(self, post):
        return self.root / 'noticies' / (post['id'] + '.html')

    def git(self, *args, date=None):
        env = dict(os.environ)
        if date:
            env.update(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
        return subprocess.run(['git', *args], cwd=self.root, env=env,
                              capture_output=True, text=True, check=True).stdout

    def test_sitemap_includes_persistent_useful_post_outside_ara_and_static_pages(self):
        result = self.build()
        self.assertEqual(result, {'static': 5, 'publications': 1, 'noindex': 0, 'urls': 6})
        self.assertIn(seo.SITE + '/transparency.html', self.urls())
        self.assertIn(seo.SITE + '/noticies/' + self.detail(self.posts[0]).name, self.urls())
        self.assertIn(self.posts[0]['title'], (self.root / 'enllacos.html').read_text())

    def test_blank_generic_short_hidden_orphan_and_missing_pages_are_excluded(self):
        self.add_post(2, summary='')
        self.add_post(3, title='Publicació de xarxa')
        self.add_post(4, summary='Vegeu l’enllaç https://example.test/' + 'a' * 200)
        hidden = self.add_post(5)
        self.hidden.append(hidden['id'])
        missing = self.add_post(6)
        self.detail(missing).unlink()
        orphan = self.root / 'noticies/orphan.html'
        orphan.write_text(self.document)
        self.assertEqual(self.build()['publications'], 1)
        self.assertEqual(len(self.urls()), 6)
        for path in [self.detail(p) for p in self.posts[1:5]] + [orphan]:
            self.assertIn('noindex,follow', path.read_text())
            self.assertNotIn('application/ld+json', path.read_text())

    def test_metadata_is_escaped_unique_and_does_not_change_visible_body_or_data(self):
        self.posts[0]['summary'] = 'A' * 279 + '& " <script> </script> ' + 'B' * 100
        self.posts[0]['title'] = '</script><img src=x> Informació local'
        self.inventories()
        before = {p: p.read_bytes() for p in (self.root / 'data').glob('*.json')}
        seo.build(self.root)
        document = self.detail(self.posts[0]).read_text()
        self.assertEqual(document.split('</head>')[1], self.document.split('</head>')[1])
        tags = Metadata(document).tags
        descriptions = [attrs['content'] for tag, attrs in tags if tag == 'meta' and attrs.get('name') == 'description']
        self.assertEqual(descriptions, ['A' * 279 + '&'])
        self.assertEqual(len([a for t, a in tags if t == 'link' and a.get('rel') == 'canonical']), 1)
        self.assertEqual(len([a for t, a in tags if t == 'meta' and a.get('name') == 'robots']), 1)
        schema = json.loads(document.split('<script type="application/ld+json">')[1].split('</script>')[0])
        self.assertEqual(schema['@type'], 'WebPage')
        self.assertEqual(schema['datePublished'], self.posts[0]['published_at'])
        self.assertNotIn('dateModified', schema)
        self.assertNotIn('author', schema)
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content)

    def test_repeat_build_is_identical_and_later_edits_and_hiding_are_reflected(self):
        self.build()
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.build()
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content, str(path))
        self.posts[0]['summary'] = ''
        self.build()
        self.assertEqual(len(self.urls()), 5)
        self.assertIn('noindex,follow', self.detail(self.posts[0]).read_text())
        self.posts[0]['summary'] = 'Context local detallat. ' * 10
        self.build()
        self.assertEqual(len(self.urls()), 6)
        self.hidden.append(self.posts[0]['id'])
        self.build()
        self.assertEqual(len(self.urls()), 5)

    def test_lastmod_uses_file_history_not_later_deploy_or_poll_dates(self):
        self.inventories()
        self.git('init')
        self.git('config', 'user.email', 'test@example.test')
        self.git('config', 'user.name', 'Local test')
        self.git('add', '.')
        self.git('commit', '-m', 'Create', date='2026-09-18T10:00:00+00:00')
        (self.root / 'data/posts.json').write_text('{"fetched_at":"2026-10-19T10:00:00Z"}')
        self.git('add', '.')
        self.git('commit', '-m', 'Poll', date='2026-10-19T10:00:00+00:00')
        self.build()
        detail_url = seo.SITE + '/noticies/' + self.detail(self.posts[0]).name
        self.assertEqual(self.urls()[detail_url], '2026-09-18T10:00:00+00:00')
        self.assertEqual(self.urls()[seo.SITE + '/privacy.html'], '2026-09-18T10:00:00+00:00')
        self.assertIsNone(self.urls()[seo.SITE + '/'])
        self.assertIsNone(self.urls()[seo.SITE + '/enllacos.html'])
        # A subsequent actual detail edit must advance its modification date.
        self.git('add', 'noticies')
        self.git('commit', '-m', 'Detail edit', date='2026-10-19T11:00:00+00:00')
        self.assertEqual(seo.last_change(self.root, 'noticies/' + self.detail(self.posts[0]).name), '2026-10-19T11:00:00+00:00')

    def test_invalid_inventory_fails_before_changing_pages(self):
        self.posts.append(dict(self.posts[0]))
        with self.assertRaises(ValueError):
            self.build()
        self.assertEqual(self.detail(self.posts[0]).read_text(), self.document)

    def test_shallow_history_omits_unverifiable_dates(self):
        result = subprocess.CompletedProcess([], 0, stdout='true\n')
        with patch.object(seo.subprocess, 'run', return_value=result) as run:
            self.assertIsNone(seo.last_change(self.root, 'privacy.html'))
        run.assert_called_once()

    def test_every_deployment_builds_after_commit_before_upload_with_full_history(self):
        for name in ['deploy-pages', 'update-sources', 'publish-own-content', 'edit-own-content', 'manage-posts']:
            workflow = (ROOT / f'.github/workflows/{name}.yml').read_text()
            build = workflow.index('run: python3 scripts/build_seo.py')
            upload = workflow.index('uses: actions/upload-pages-artifact@v4')
            self.assertLess(build, upload, name)
            self.assertIn('fetch-depth: 0', workflow[:build], name)
            if name in {'update-sources', 'publish-own-content'}:
                self.assertLess(workflow.index('git push origin HEAD:main'), build, name)


if __name__ == '__main__':
    unittest.main()
