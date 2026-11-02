"""Single-use approval ledger tests (Dean ruling 2026-11-02). Each case builds a real git repository:
`main` is the protected branch whose history is the ledger, and a PR branch carries the submission.
The real validator runs with --history-ref main, exactly as blog-validate runs it."""
import hashlib, io, json, os, shutil, subprocess, sys, tempfile, unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
VALIDATOR = os.path.join(REPO, 'tools', 'validator.py')
sys.path.insert(0, os.path.join(REPO, 'tools'))
from validator import canonical  # noqa: E402

TEXT = "It’s free — and it takes ten minutes."


def png(seed):
    b = io.BytesIO(); Image.new('RGB', (1080, 1350), (seed, 40, 60)).save(b, 'PNG'); return b.getvalue()


class GitRepo:
    def __init__(self):
        self.root = tempfile.mkdtemp(prefix='ledger-')
        self.key = Ed25519PrivateKey.generate()
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.email', 't@t'); self.git('config', 'user.name', 't')
        self.write('keys/pub.pem', self.key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
        self.write('index.html', '<html></html>')
        self.commit('base')

    def git(self, *args):
        return subprocess.run(['git', '-C', self.root, *args], capture_output=True, text=True, check=True).stdout

    def write(self, rel, data):
        p = os.path.join(self.root, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'wb') as f: f.write(data if isinstance(data, bytes) else data.encode('utf-8'))
        return rel

    def rm(self, rel): self.git('rm', '-q', rel)

    def commit(self, msg):
        self.git('add', '-A'); self.git('commit', '-q', '--allow-empty', '-m', msg)

    def branch(self, name, base='main'): self.git('checkout', '-q', '-B', name, base)

    def merge_to_main(self, name):
        self.git('checkout', '-q', 'main'); self.git('merge', '-q', '--ff-only', name)

    def signed(self, stmt):
        return json.dumps({**stmt, 'sig': self.key.sign(canonical(stmt)).hex()}, ensure_ascii=False)

    def article(self, slug, nonce, body='Hello.'):
        md = f'---\ntitle: "{slug}"\nslug: {slug}\n---\n{body}\n'
        self.write(f'content/blog/{slug}.md', md)
        stmt = {'schema': 'blogpub/approval/v1', 'author': 'Ryan Phelan', 'id': slug, 'slug': slug, 'nonce': nonce,
                'contentHash': 'sha256:' + hashlib.sha256(md.encode()).hexdigest(), 'publish_time': '2026-11-05T13:00:00Z'}
        self.write(f'content/blog/{slug}.approval.json', self.signed(stmt))
        return [f'content/blog/{slug}.approval.json', f'content/blog/{slug}.md']

    def social(self, slug, nonce, seed=1):
        data = png(seed); h = hashlib.sha256(data).hexdigest(); img = self.write(f'images/social/{h}.png', data)
        stmt = {'schema': 'blogpub/approval/v1', 'kind': 'social', 'author': 'Ryan Phelan', 'id': slug, 'slug': slug,
                'nonce': nonce, 'channel': 'linkedin', 'destination': 'LinkedIn: Ryan Phelan',
                'publish_time': '2026-11-04T15:00:00Z', 'timezone': 'America/Chicago',
                'postTextHash': 'sha256:' + hashlib.sha256(TEXT.encode()).hexdigest(),
                'assets': [{'path': img, 'sha256': h}]}
        self.write(f'content/blog/{slug}.approval.json', self.signed(stmt))
        return [f'content/blog/{slug}.approval.json', img]

    def validate(self, approval, changed, history=True):
        args = [sys.executable, VALIDATOR, '--approval', approval, '--pubkey', 'keys/pub.pem',
                '--changed', ','.join(changed), '--root', self.root]
        if history: args += ['--history-ref', 'main']
        r = subprocess.run(args, capture_output=True, text=True)
        return r.returncode, (r.stdout + r.stderr).strip()

    def cleanup(self): shutil.rmtree(self.root, ignore_errors=True)


class Ledger(unittest.TestCase):
    def setUp(self): self.g = GitRepo()
    def tearDown(self): self.g.cleanup()

    def ok(self, approval, changed, **kw):
        code, out = self.g.validate(approval, changed, **kw); self.assertEqual(code, 0, out)

    def replay(self, approval, changed):
        code, out = self.g.validate(approval, changed); self.assertNotEqual(code, 0, out)
        self.assertIn('replay-approval-consumed', out)

    def publish_article(self, slug, nonce):
        self.g.branch('pr-' + slug); files = self.g.article(slug, nonce); self.g.commit('pr')
        self.ok(files[0], files); self.g.merge_to_main('pr-' + slug); return files

    # ---- first use and lifecycle ----
    def test_fresh_article_passes(self):
        self.g.branch('pr'); f = self.g.article('a', 'n-a'); self.g.commit('pr'); self.ok(f[0], f)

    def test_fresh_social_passes(self):
        self.g.branch('pr'); f = self.g.social('s', 'n-s'); self.g.commit('pr'); self.ok(f[0], f)

    def test_failed_or_unmerged_attempt_does_not_consume(self):
        # attempt 1: PR opened, never merged (failed check, closed, or abandoned)
        self.g.branch('pr1'); f = self.g.article('a', 'n-a'); self.g.commit('pr1')
        # attempt 2: the same approval resubmitted on a new PR still passes
        self.g.branch('pr2'); self.g.article('a', 'n-a'); self.g.commit('pr2'); self.ok(f[0], f)

    def test_pr_updated_after_push_still_passes(self):
        self.g.branch('pr'); f = self.g.article('a', 'n-a'); self.g.commit('pr1')
        self.g.commit('pr2 (synchronize)'); self.ok(f[0], f)

    def test_deploy_retry_after_merge_is_allowed(self):
        f = self.publish_article('a', 'n-a')
        # site-publish re-validates what is already on main WITHOUT the replay check: retry works
        self.ok(f[0], [], history=False)

    # ---- replay ----
    def test_second_pr_with_same_article_approval_rejected(self):
        self.publish_article('a', 'n-a')
        self.g.branch('pr2'); f = self.g.article('a', 'n-a', body='Hello.'); self.g.commit('pr2 again')
        # identical files are already on main, so nothing changes; force a new path to submit again
        self.g.git('mv', 'content/blog/a.approval.json', 'content/blog/a2.approval.json'); self.g.commit('rename')
        self.replay('content/blog/a2.approval.json', ['content/blog/a2.approval.json'])

    def test_republishing_a_removed_article_rejected(self):
        f = self.publish_article('a', 'n-a')
        self.g.rm(f[0]); self.g.rm(f[1]); self.g.commit('admin: remove post')
        self.g.branch('pr-republish'); f2 = self.g.article('a', 'n-a'); self.g.commit('republish with old approval')
        self.replay(f2[0], f2)

    def test_reused_social_approval_under_new_slug_rejected(self):
        self.g.branch('pr1'); f = self.g.social('s1', 'n-s'); self.g.commit('pr1'); self.g.merge_to_main('pr1')
        self.g.branch('pr2'); f2 = self.g.social('s2', 'n-s', seed=2); self.g.commit('same nonce, new post')
        self.replay(f2[0], f2)

    def test_removed_social_approval_cannot_return(self):
        self.g.branch('pr1'); f = self.g.social('s1', 'n-s'); self.g.commit('pr1'); self.g.merge_to_main('pr1')
        self.g.rm(f[0]); self.g.commit('admin: remove')
        self.g.branch('pr2'); f2 = self.g.social('s1', 'n-s'); self.g.commit('re-add')
        self.replay(f2[0], f2)

    # ---- legitimate re-approval ----
    def test_updated_article_with_new_approval_passes(self):
        self.publish_article('a', 'n-a')
        self.g.branch('pr-edit'); f = self.g.article('a', 'n-a-v2', body='Hello, edited.'); self.g.commit('edit')
        self.ok(f[0], f)

    def test_republish_removed_post_with_new_approval_passes(self):
        f = self.publish_article('a', 'n-a')
        self.g.rm(f[0]); self.g.rm(f[1]); self.g.commit('admin: remove post')
        self.g.branch('pr-new'); f2 = self.g.article('a', 'n-a-fresh'); self.g.commit('fresh approval')
        self.ok(f2[0], f2)

    # ---- fail closed ----
    def test_missing_nonce_rejected(self):
        self.g.branch('pr'); md = '---\ntitle: "x"\nslug: x\n---\nx\n'; self.g.write('content/blog/x.md', md)
        stmt = {'author': 'Ryan Phelan', 'id': 'x', 'slug': 'x', 'contentHash': 'sha256:' + hashlib.sha256(md.encode()).hexdigest()}
        self.g.write('content/blog/x.approval.json', self.g.signed(stmt)); self.g.commit('pr')
        code, out = self.g.validate('content/blog/x.approval.json', ['content/blog/x.approval.json', 'content/blog/x.md'])
        self.assertNotEqual(code, 0); self.assertIn('approval-missing-nonce', out)

    def test_unreadable_history_fails_closed(self):
        self.g.branch('pr'); f = self.g.article('a', 'n-a'); self.g.commit('pr')
        r = subprocess.run([sys.executable, VALIDATOR, '--approval', f[0], '--pubkey', 'keys/pub.pem', '--changed',
                            ','.join(f), '--root', self.g.root, '--history-ref', 'no-such-branch'], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0); self.assertIn('ledger-unreadable', r.stdout)

    def test_shallow_history_fails_closed(self):
        self.publish_article('a', 'n-a')
        shallow = tempfile.mkdtemp(prefix='ledger-shallow-')
        try:
            subprocess.run(['git', 'clone', '-q', '--depth', '1', 'file://' + self.g.root, shallow], check=True,
                           capture_output=True)
            f = ['content/blog/a.approval.json', 'content/blog/a.md']
            r = subprocess.run([sys.executable, VALIDATOR, '--approval', f[0], '--pubkey', 'keys/pub.pem', '--changed',
                                ','.join(f), '--root', shallow, '--history-ref', 'origin/main'], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0); self.assertIn('ledger-history-incomplete', r.stdout)
        finally:
            shutil.rmtree(shallow, ignore_errors=True)

    def test_existing_production_history_shape(self):
        # mirrors main as of 2026-11-02: three articles added then removed, one social approval live
        for slug, n in (('pipeline-test-post', 'test-c91ba7e6b38e'), ('clarity-gap-activation-test', '15c70487'),
                        ('pipeline-validation-cc90cd2e', 'cc90cd2e')):
            f = self.publish_article(slug, n); self.g.rm(f[0]); self.g.rm(f[1]); self.g.commit('remove')
        for slug, n in (('pipeline-test-post', 'test-c91ba7e6b38e'), ('clarity-gap-activation-test', '15c70487'),
                        ('pipeline-validation-cc90cd2e', 'cc90cd2e')):
            self.g.branch('replay-' + slug); f = self.g.article(slug, n); self.g.commit('replay'); self.replay(f[0], f)


if __name__ == '__main__':
    unittest.main()
