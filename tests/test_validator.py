"""Regression tests for tools/validator.py (Dean ruling 2026-11-02, social card image approvals).
Run: python3 -m unittest discover -s tests -v
Each case builds a throwaway repo in a temp dir, signs approvals with a throwaway Ed25519 key using
the same canonical bytes the Approval Service signs, and runs the real validator as CI does."""
import hashlib, io, json, os, shutil, subprocess, sys, tempfile, unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
VALIDATOR = os.path.join(REPO, 'tools', 'validator.py')
sys.path.insert(0, os.path.join(REPO, 'tools'))
from validator import canonical  # noqa: E402

# Bytes produced by the Approval Service's own canon() (worker.mjs, JavaScript) for GOLDEN_STMT.
# If this ever differs from validator.canonical(), every non-ASCII approval would fail. Do not edit.
GOLDEN_STMT = {"kind": "social", "author": "Ryan Phelan", "destination": "Ryan Phelan’s page — LinkedIn 🙂",
               "note": "curly “quotes”, ‘apostrophes’, em — dash, emoji 🚀🙂", "id": "x", "nonce": "n1"}
GOLDEN_JS_HEX = ("7b22617574686f72223a225279616e205068656c616e222c2264657374696e6174696f6e223a225279616e205068"
                 "656c616ee2809973207061676520e28094204c696e6b6564496e20f09f9982222c226964223a2278222c226b696e"
                 "64223a22736f6369616c222c226e6f6e6365223a226e31222c226e6f7465223a226375726c7920e2809c71756f74"
                 "6573e2809d2c20e2809861706f7374726f70686573e280992c20656d20e2809420646173682c20656d6f6a6920f0"
                 "9f9a80f09f9982227d")

POST_TEXT = "It’s free — and it takes ten minutes. 🙂\nTry the Clarity Gap Diagnostic."


def png(w=1080, h=1350, color=(20, 40, 60)):
    b = io.BytesIO(); Image.new('RGB', (w, h), color).save(b, 'PNG'); return b.getvalue()


class Repo:
    def __init__(self):
        self.root = tempfile.mkdtemp(prefix='bv-')
        self.key = Ed25519PrivateKey.generate()
        os.makedirs(os.path.join(self.root, 'keys'))
        os.makedirs(os.path.join(self.root, 'content', 'blog'))
        os.makedirs(os.path.join(self.root, 'images', 'social'))
        with open(os.path.join(self.root, 'keys', 'pub.pem'), 'wb') as f:
            f.write(self.key.public_key().public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))

    def write(self, rel, data):
        p = os.path.join(self.root, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'wb') as f:
            f.write(data if isinstance(data, bytes) else data.encode('utf-8'))
        return rel

    def image(self, data=None):
        data = data or png(); h = hashlib.sha256(data).hexdigest()
        return self.write(f'images/social/{h}.png', data), h

    def approve(self, slug, stmt, sign_bytes=None):
        sig = self.key.sign(sign_bytes if sign_bytes is not None else canonical(stmt))
        rel = f'content/blog/{slug}.approval.json'
        self.write(rel, json.dumps({**stmt, 'sig': sig.hex()}, ensure_ascii=False))
        return rel

    def run(self, approval, changed):
        r = subprocess.run([sys.executable, VALIDATOR, '--approval', approval, '--pubkey', 'keys/pub.pem',
                            '--changed', ','.join(changed), '--root', self.root],
                           capture_output=True, text=True)
        return r.returncode, (r.stdout + r.stderr).strip()

    def cleanup(self): shutil.rmtree(self.root, ignore_errors=True)


def social(img_rel, img_sha, **over):
    s = {'schema': 'blogpub/approval/v1', 'kind': 'social', 'author': 'Ryan Phelan', 'id': 'social-1',
         'slug': 'social-2026-11-05-linkedin', 'nonce': 'nonce-1', 'channel': 'linkedin',
         'destination': 'Ryan Phelan — LinkedIn profile', 'publish_time': '2026-11-05T15:00:00Z',
         'timezone': 'America/Chicago',
         'postTextHash': 'sha256:' + hashlib.sha256(POST_TEXT.encode('utf-8')).hexdigest(),
         'approved_at': '2026-11-02T16:00:00Z', 'assets': [{'path': img_rel, 'sha256': img_sha}]}
    s.update(over)
    return {k: v for k, v in s.items() if v is not None}


def article(repo, slug='a-post', with_image=None):
    body = "---\ntitle: \"A post\"\nslug: a-post\n---\nHello.\n"
    md = repo.write(f'content/blog/{slug}.md', body)
    s = {'schema': 'blogpub/approval/v1', 'author': 'Ryan Phelan', 'id': 'art-1', 'slug': slug,
         'contentHash': 'sha256:' + hashlib.sha256(body.encode()).hexdigest(),
         'publish_time': '2026-11-03T13:00:00Z', 'approved_at': '2026-11-02T16:00:00Z', 'nonce': 'n-art'}
    if with_image: s['assets'] = [{'path': with_image[0], 'sha256': with_image[1]}]
    return md, s


class Encoding(unittest.TestCase):
    def test_canonical_matches_signer_bytes_for_unicode(self):
        self.assertEqual(canonical(GOLDEN_STMT).hex(), GOLDEN_JS_HEX)

    def test_ascii_statements_unchanged(self):
        s = {'slug': 'a', 'contentHash': 'sha256:' + '0' * 64, 'author': 'Ryan Phelan', 'n': 'x'}
        self.assertEqual(canonical(s), json.dumps(s, sort_keys=True, separators=(',', ':')).encode())

    def test_unicode_approval_validates(self):
        r = Repo()
        try:
            rel, h = r.image()
            ap = r.approve('social-2026-11-05-linkedin', social(rel, h, destination='Ryan Phelan’s page — LinkedIn 🙂'))
            code, out = r.run(ap, [ap, rel]); self.assertEqual(code, 0, out)
        finally: r.cleanup()

    def test_old_escaped_encoding_is_rejected(self):
        r = Repo()
        try:
            rel, h = r.image(); s = social(rel, h, destination='Ryan Phelan’s page — LinkedIn 🙂')
            old = json.dumps(s, sort_keys=True, separators=(',', ':')).encode()   # pre-fix form
            ap = r.approve('social-2026-11-05-linkedin', s, sign_bytes=old)
            code, out = r.run(ap, [ap, rel]); self.assertNotEqual(code, 0); self.assertIn('approval-signature-invalid', out)
        finally: r.cleanup()


class ArticleBackwardCompat(unittest.TestCase):
    def test_article_only(self):
        r = Repo()
        try:
            md, s = article(r); ap = r.approve('a-post', s)
            code, out = r.run(ap, [ap, md]); self.assertEqual(code, 0, out); self.assertIn('(article)', out)
        finally: r.cleanup()

    def test_article_with_card(self):
        r = Repo()
        try:
            rel, h = r.image(); md, s = article(r, with_image=(rel, h)); ap = r.approve('a-post', s)
            code, out = r.run(ap, [ap, md, rel]); self.assertEqual(code, 0, out)
        finally: r.cleanup()

    def test_article_kind_without_contentHash_rejected(self):
        r = Repo()
        try:
            rel, h = r.image()
            s = {'schema': 'blogpub/approval/v1', 'author': 'Ryan Phelan', 'id': 'x', 'slug': 'x', 'nonce': 'n',
                 'publish_time': '2026-11-03T13:00:00Z', 'assets': [{'path': rel, 'sha256': h}]}
            ap = r.approve('x', s)
            code, out = r.run(ap, [ap, rel]); self.assertNotEqual(code, 0); self.assertIn('article-approval-missing-contentHash', out)
        finally: r.cleanup()


class Social(unittest.TestCase):
    def setUp(self):
        self.r = Repo(); self.rel, self.h = self.r.image()

    def tearDown(self): self.r.cleanup()

    def ok(self, stmt, changed=None):
        ap = self.r.approve('social-2026-11-05-linkedin', stmt)
        return self.r.run(ap, changed if changed is not None else [ap, self.rel])

    def fails(self, stmt, expect, changed=None):
        code, out = self.ok(stmt, changed); self.assertNotEqual(code, 0, out); self.assertIn(expect, out)

    def test_social_positive(self):
        code, out = self.ok(social(self.rel, self.h)); self.assertEqual(code, 0, out); self.assertIn('(social)', out)

    def _tamper(self, field, value):
        s = social(self.rel, self.h); ap = self.r.approve('social-2026-11-05-linkedin', s)
        p = os.path.join(self.r.root, ap)
        with open(p, encoding='utf-8') as f: d = json.load(f)
        d[field] = value
        with open(p, 'w', encoding='utf-8') as f: f.write(json.dumps(d, ensure_ascii=False))
        code, out = self.r.run(ap, [ap, self.rel]); self.assertNotEqual(code, 0); self.assertIn('approval-signature-invalid', out)

    def test_changed_text_hash_invalidates(self): self._tamper('postTextHash', 'sha256:' + hashlib.sha256(b'edited').hexdigest())
    def test_changed_channel_invalidates(self): self._tamper('channel', 'x')
    def test_changed_destination_invalidates(self): self._tamper('destination', 'Someone else')
    def test_changed_time_invalidates(self): self._tamper('publish_time', '2026-11-05T16:00:00Z')
    def test_changed_timezone_invalidates(self): self._tamper('timezone', 'America/New_York')
    def test_changed_image_hash_in_approval_invalidates(self): self._tamper('assets', [{'path': self.rel, 'sha256': '0' * 64}])

    def test_swapped_image_bytes_rejected(self):
        self.r.write(self.rel, png(color=(200, 0, 0)))
        self.fails(social(self.rel, self.h), 'filename-not-content-hash')

    def test_unbound_extra_image_rejected(self):
        extra, _ = self.r.image(png(color=(1, 2, 3)))
        ap = 'content/blog/social-2026-11-05-linkedin.approval.json'
        self.fails(social(self.rel, self.h), 'changed-file-not-covered-by-approval', [ap, self.rel, extra])

    def test_article_file_in_social_pr_rejected(self):
        md = self.r.write('content/blog/social-2026-11-05-linkedin.md', '---\ntitle: x\n---\nx\n')
        ap = 'content/blog/social-2026-11-05-linkedin.approval.json'
        self.fails(social(self.rel, self.h), 'changed-file-not-covered-by-approval', [ap, self.rel, md])

    def test_social_binding_article_rejected(self): self.fails(social(self.rel, self.h, contentHash='sha256:' + '1' * 64), 'social-must-not-bind-article')
    def test_social_without_image_rejected(self): self.fails(social(self.rel, self.h, assets=[]), 'social-needs-at-least-one-image')
    def test_missing_timezone_rejected(self): self.fails(social(self.rel, self.h, timezone=None), 'social-missing-field:timezone')
    def test_missing_destination_rejected(self): self.fails(social(self.rel, self.h, destination=None), 'social-missing-field:destination')
    def test_missing_channel_rejected(self): self.fails(social(self.rel, self.h, channel=None), 'social-missing-field:channel')
    def test_missing_text_hash_rejected(self): self.fails(social(self.rel, self.h, postTextHash=None), 'social-missing-field:postTextHash')
    def test_invalid_timezone_rejected(self): self.fails(social(self.rel, self.h, timezone='Central/Time'), 'social-bad-timezone')
    def test_time_without_offset_rejected(self): self.fails(social(self.rel, self.h, publish_time='2026-11-05 15:00'), 'social-bad-publish_time')
    def test_raw_text_in_statement_rejected(self): self.fails(social(self.rel, self.h, postText=POST_TEXT), 'social-raw-text-not-allowed')
    def test_unknown_kind_rejected(self): self.fails(social(self.rel, self.h, kind='story'), 'unknown-approval-kind')
    def test_wrong_author_rejected(self): self.fails(social(self.rel, self.h, author='Marketing'), 'author-not-allowed')

    def test_wrong_dimensions_rejected(self):
        rel, h = self.r.image(png(1200, 630)); self.fails(social(rel, h), 'bad-dimensions', ['content/blog/social-2026-11-05-linkedin.approval.json', rel])

    def test_non_png_rejected(self):
        b = io.BytesIO(); Image.new('RGB', (1080, 1350)).save(b, 'JPEG'); data = b.getvalue()
        h = hashlib.sha256(data).hexdigest(); rel = self.r.write(f'images/social/{h}.png', data)
        self.fails(social(rel, h), 'not-a-png', ['content/blog/social-2026-11-05-linkedin.approval.json', rel])

    def test_missing_signature_rejected(self):
        ap = 'content/blog/social-2026-11-05-linkedin.approval.json'
        self.r.write(ap, json.dumps(social(self.rel, self.h)))
        code, out = self.r.run(ap, [ap, self.rel]); self.assertNotEqual(code, 0); self.assertIn('approval-signature-invalid', out)


if __name__ == '__main__':
    unittest.main()
