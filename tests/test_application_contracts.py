"""Cross-file contracts catch configuration gaps that syntax tests cannot."""
import json
import re
import unittest
from pathlib import Path
from urllib.parse import urlparse
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]

class ApplicationContractsTests(unittest.TestCase):
    def test_manual_refresh_preserves_hourly_schedule_and_serializes_social_sends(self):
        refresh=(ROOT/'.github/workflows/update-sources.yml').read_text()
        manual=(ROOT/'.github/workflows/publish-own-content.yml').read_text()
        self.assertIn('cron: "7 * * * *"',refresh)
        self.assertIn('workflow_dispatch:',refresh)
        self.assertIn('python scripts/retry_manual_social.py',refresh)
        for workflow in (refresh,manual):
            self.assertIn('group: "soller-ara-social-publish"',workflow)
            self.assertIn('queue: max',workflow)
            self.assertIn('cancel-in-progress: false',workflow)

    def test_public_feed_and_script_fallback_contain_the_same_data(self):
        payload=json.loads((ROOT/'data/posts.json').read_text())
        script=(ROOT/'data/posts.js').read_text()
        fallback=json.loads(script.removeprefix('window.SOLLER_ARA_DATA = ').strip().removesuffix(';'))
        self.assertEqual(payload, fallback)
        self.assertEqual(payload['post_count'],len(payload['posts']))
        ids=[post['id'] for post in payload['posts']]
        self.assertEqual(len(ids),len(set(ids)))
        hidden=set(json.loads((ROOT/'data/moderation.json').read_text()).get('hidden_post_ids',[]))
        self.assertFalse(hidden.intersection(ids))

    def test_current_manual_pages_and_generated_media_exist(self):
        manual=json.loads((ROOT/'data/manual_posts.json').read_text())['posts']
        for post in manual:
            for field in ('url','media_url'):
                url=post.get(field) or ''
                if url.startswith('https://soller-ara.github.io/soller-ara/'):
                    relative=urlparse(url).path.removeprefix('/soller-ara/')
                    self.assertTrue((ROOT/relative).is_file(),(post['id'],field,relative))

    def test_active_brand_and_manual_images_decode(self):
        images={ROOT/'assets/brand'/name for name in (
            'logo-soller-ara-web.png','favicon-48.png','icon-192.png','icon-512.png',
            'apple-touch-icon.png','avatar-soller-ara-social.png')}
        for post in json.loads((ROOT/'data/manual_posts.json').read_text())['posts']:
            url=post.get('media_url') or ''
            if url.startswith('https://soller-ara.github.io/soller-ara/'):
                images.add(ROOT/urlparse(url).path.removeprefix('/soller-ara/'))
        for path in images:
            with self.subTest(path=path.name), Image.open(path) as image:
                image.verify()

    def test_publish_workflow_forwards_poster_type_and_stable_request_identity(self):
        workflow=(ROOT/'.github/workflows/publish-own-content.yml').read_text()
        self.assertIn('POST_CONTENT_TYPE: ${{ inputs.content_type }}',workflow)
        self.assertIn('PUBLISH_KEY: ${{ github.run_id }}',workflow)
        self.assertIn('PUBLISH_SHOW_IN_NOW: ${{ inputs.show_in_now }}',workflow)

    def test_every_pages_workflow_matches_artifact_name_for_its_attempt(self):
        workflows=list((ROOT/'.github/workflows').glob('*.yml'))
        count=0
        for path in workflows:
            text=path.read_text()
            if 'actions/upload-pages-artifact@' not in text: continue
            count+=1
            self.assertIn('name: github-pages-${{ github.run_attempt }}',text,path.name)
            self.assertIn('artifact_name: github-pages-${{ github.run_attempt }}',text,path.name)
        self.assertGreaterEqual(count,5)

    def test_every_pages_publisher_uses_the_same_non_canceling_queue(self):
        # GitHub Pages refuses a second deployment while another is in progress.
        for path in (ROOT/'.github/workflows').glob('*.yml'):
            text=path.read_text()
            if 'actions/deploy-pages@' not in text:
                continue
            concurrency=re.search(r'^concurrency:\n((?:  .+\n)+)',text,re.M)
            self.assertIsNotNone(concurrency,path.name)
            group=concurrency.group(1)
            self.assertIn('group: "soller-ara-social-publish"',group,path.name)
            self.assertIn('queue: max',group,path.name)
            self.assertIn('cancel-in-progress: false',group,path.name)
            self.assertIn('ref: main',text,path.name)

    def test_every_repository_writer_preserves_and_serializes_pending_requests(self):
        writers=0
        for path in (ROOT/'.github/workflows').glob('*.yml'):
            text=path.read_text()
            if 'contents: write' not in text:
                continue
            writers+=1
            concurrency=re.search(r'^concurrency:\n((?:  .+\n)+)',text,re.M)
            self.assertIsNotNone(concurrency,path.name)
            for setting in ('group: "soller-ara-social-publish"','queue: max','cancel-in-progress: false'):
                self.assertIn(setting,concurrency.group(1),path.name)
            self.assertIn('ref: main',text,path.name)
            self.assertEqual(text.count('runs-on:'),text.count('timeout-minutes:'),path.name)
        self.assertGreaterEqual(writers,6)

    def test_moderation_workflow_accepts_all_collector_categories(self):
        workflow=(ROOT/'.github/workflows/manage-posts.yml').read_text()
        options=re.search(r'options: \[(news[^\]]+)\]',workflow).group(1).replace(' ','').split(',')
        self.assertEqual(set(options),{'news','agenda','alerts','services','culture','sports','commerce','politics','social'})
        editing=(ROOT/'.github/workflows/edit-own-content.yml').read_text()
        self.assertIn('git add data/moderation.json',editing)

if __name__=='__main__': unittest.main()
