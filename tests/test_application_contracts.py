"""Cross-file contracts catch configuration gaps that syntax tests cannot."""
import json
import re
import unittest
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]

class ApplicationContractsTests(unittest.TestCase):
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

    def test_moderation_workflow_accepts_all_collector_categories(self):
        workflow=(ROOT/'.github/workflows/manage-posts.yml').read_text()
        options=re.search(r'options: \[(news[^\]]+)\]',workflow).group(1).replace(' ','').split(',')
        self.assertEqual(set(options),{'news','agenda','alerts','services','culture','sports','commerce','politics','social'})
        editing=(ROOT/'.github/workflows/edit-own-content.yml').read_text()
        self.assertIn('git add data/moderation.json',editing)

if __name__=='__main__': unittest.main()
