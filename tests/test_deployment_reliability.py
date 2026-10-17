from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DeploymentReliabilityTests(unittest.TestCase):
    def test_collection_has_no_second_workflow_run_deployment(self):
        deploy = (ROOT / '.github/workflows/deploy-pages.yml').read_text()
        self.assertNotIn('workflow_run:', deploy)
        self.assertIn('workflow_dispatch:', deploy)
        self.assertIn('paths-ignore:', deploy)
        for path in ['sources.json', 'social_distribution.json', 'scripts/update_sources.py']:
            self.assertIn(f'"{path}"', deploy)

    def test_all_publication_deployments_share_a_bounded_retry_and_lock(self):
        for name in ['deploy-pages', 'update-sources', 'publish-own-content', 'edit-own-content', 'manage-posts']:
            workflow = (ROOT / f'.github/workflows/{name}.yml').read_text()
            self.assertIn('uses: ./.github/actions/deploy-pages-reliable', workflow, name)
            self.assertNotIn('uses: actions/deploy-pages@', workflow, name)
            self.assertIn('group: "soller-ara-social-publish"', workflow, name)
            self.assertIn('cancel-in-progress: false', workflow, name)
        action = (ROOT / '.github/actions/deploy-pages-reliable/action.yml').read_text()
        self.assertEqual(action.count('uses: actions/deploy-pages@v4'), 3)
        self.assertNotIn('publish_own_social', action)
        self.assertNotIn('publish_collected_social', action)
        self.assertIn('exit 1', action)

    def test_collection_remains_hourly_and_social_sends_follow_deployment(self):
        workflow = (ROOT / '.github/workflows/update-sources.yml').read_text()
        self.assertIn('cron: "7 * * * *"', workflow)
        self.assertLess(workflow.index('uses: ./.github/actions/deploy-pages-reliable'),
                        workflow.index('run: python scripts/publish_collected_social.py'))


if __name__ == '__main__':
    unittest.main()
