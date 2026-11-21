"""Source-only CI contract assertions; no GitHub credentials or calls."""
from pathlib import Path
import re
import unittest

CI = Path(__file__).resolve().parents[1] / '.github' / 'workflows' / 'source-ci.yml'


class CiWorkflowTests(unittest.TestCase):
    def test_source_workflow_present_and_push_dispatch_supported(self):
        text = CI.read_text(encoding='utf-8')
        self.assertRegex(text, r'(?m)^on:\s*$')
        for event in ('push:', 'pull_request:', 'workflow_dispatch:'):
            self.assertIn(event, text)
        self.assertIn('branches: [main]', text)

    def test_matrix_covers_windows_and_linux(self):
        text = CI.read_text(encoding='utf-8')
        self.assertIn('os: [ubuntu-latest, windows-latest]', text)
        self.assertIn("python-version: '3.13'", text)
        self.assertIn("node-version: '22'", text)
        self.assertIn('run: python tools/check.py', text)

    def test_read_only_permissions_and_no_publication(self):
        text = CI.read_text(encoding='utf-8')
        self.assertRegex(text, r'(?m)^permissions:\s*\n  contents: read\s*$')
        self.assertIn('persist-credentials: false', text)
        forbidden = ('actions/create-release', 'softprops/action-gh-release',
                     'docker/build-push-action', 'git push', 'gh release create',
                     'npm publish', 'secrets.', 'id-token: write',
                     'contents: write', 'actions/deploy-pages')
        for value in forbidden:
            self.assertNotIn(value, text)

    def test_exact_sha_output_check(self):
        text = CI.read_text(encoding='utf-8')
        self.assertIn('git rev-parse HEAD', text)
        self.assertIn('${GITHUB_SHA}', text)
        self.assertIn('test "$(git rev-parse HEAD)" = "${GITHUB_SHA}"', text)


if __name__ == '__main__':
    unittest.main()
