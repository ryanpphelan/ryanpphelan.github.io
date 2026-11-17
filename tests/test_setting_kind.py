"""A signed setting approval (Approval Service v3, kind "setting") must never publish anything.
Run: python3 -m unittest discover -s tests -v
The Approval Service signs setting statements with the same key as article and social approvals,
so blog-validate must refuse one presented as the approval for any content."""
import os, sys, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from test_validator import Repo  # noqa: E402

SETTING = {'schema': 'blogpub/approval/v1', 'kind': 'setting', 'author': 'Ryan Phelan',
           'setting': 'editorial_path', 'value': 'director',
           'nonce': '7b0e3f52-6a2e-4b8a-9d61-2f4c8a1e5b90', 'requested_at': '2026-11-13T20:00:00Z',
           'display': "Switch the Marketing Department's editorial path to the Director's path."}


class SettingApprovalNeverPublishes(unittest.TestCase):
    def setUp(self): self.repo = Repo()
    def tearDown(self): self.repo.cleanup()

    def test_setting_approval_refused_alone(self):
        ap = self.repo.approve('setting-1', SETTING)
        code, out = self.repo.run(ap, [ap])
        self.assertNotEqual(code, 0, out)
        self.assertIn('unknown-approval-kind:setting', out)

    def test_setting_approval_refused_with_an_article(self):
        md = self.repo.write('content/blog/a-post.md', '---\ntitle: A\n---\nBody\n')
        ap = self.repo.approve('a-post', SETTING)
        code, out = self.repo.run(ap, [md, ap])
        self.assertNotEqual(code, 0, out)
        self.assertIn('unknown-approval-kind:setting', out)


if __name__ == '__main__':
    unittest.main()
