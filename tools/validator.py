#!/usr/bin/env python3
"""Blog publishing validator (articles, article card images, and social card images).
Validates ONE signed approval and every file it binds.

Two approval kinds:
  article (no `kind`, or kind "article"): binds an article by contentHash, plus optional card images.
  social  (kind "social"): binds a social post by postTextHash, channel, destination, publish_time
          and timezone, plus one or more card images. No article. The post text itself is never
          committed; only its SHA-256 is signed.

A changed article, image, or approval field no longer matches its signature and fails. Marketing
can submit only content/blog/** and images/social/<sha256>.png, and only files covered by the one
approval it carries.

Canonical form: keys sorted, no whitespace, UTF-8 (non-ASCII NOT escaped). This is byte-identical to
the Approval Service's canon() (JavaScript JSON.stringify), which is what is actually signed."""
import sys, json, re, hashlib, argparse, os, subprocess
from datetime import datetime
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.exceptions import InvalidSignature
try:
    from PIL import Image
    HAVE_PIL = True
except Exception:
    HAVE_PIL = False
try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except Exception:  # pragma: no cover
    ZoneInfo = None

ART = re.compile(r'^content/blog/[a-z0-9-]+\.md$')
APR = re.compile(r'^content/blog/[a-z0-9-]+\.approval\.json$')
IMG = re.compile(r'^images/social/[0-9a-f]{64}\.png$')
SHA = re.compile(r'^sha256:[0-9a-f]{64}$')
HEX64 = re.compile(r'^[0-9a-f]{64}$')
TOKEN = re.compile(r'^[a-z0-9][a-z0-9_.-]{0,63}$')   # channel name, e.g. linkedin
ISO_TIME = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})$')
BANNED = re.compile(r'<script|<iframe|javascript:|onerror=|onload=', re.I)
PNG_MAGIC = b'\x89PNG\r\n\x1a\n'
ALLOWED_DIMS = {(1080, 1350)}
MAX_BYTES = 5 * 1024 * 1024
SOCIAL_REQUIRED = ('id', 'nonce', 'channel', 'destination', 'publish_time', 'timezone', 'postTextHash')


def canonical(stmt):
    """Exactly the bytes the Approval Service signs."""
    return json.dumps(stmt, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def chash(p):  # article: normalize CRLF so hashing is platform-independent
    return 'sha256:' + hashlib.sha256(open(p, 'rb').read().replace(b'\r\n', b'\n')).hexdigest()


def validate_image(root, rel, errs):
    p = os.path.join(root, rel)
    data = open(p, 'rb').read()
    ok = True
    if data[:8] != PNG_MAGIC: errs.append(f'{rel}:not-a-png'); ok = False
    if len(data) > MAX_BYTES: errs.append(f'{rel}:too-large:{len(data)}'); ok = False
    if HAVE_PIL and ok:
        try:
            Image.open(p).verify()
            im = Image.open(p)
            if im.format != 'PNG': errs.append(f'{rel}:not-png-format:{im.format}'); ok = False
            elif im.size not in ALLOWED_DIMS: errs.append(f'{rel}:bad-dimensions:{im.size}'); ok = False
        except Exception as e:
            errs.append(f'{rel}:unreadable:{e}'); ok = False
    h = hashlib.sha256(data).hexdigest()
    if rel.split('/')[-1][:-4] != h: errs.append(f'{rel}:filename-not-content-hash'); ok = False
    return h if ok else None


def check_social_fields(stmt, errs):
    for k in SOCIAL_REQUIRED:
        v = stmt.get(k)
        if not isinstance(v, str) or not v.strip():
            errs.append(f'social-missing-field:{k}')
    if errs:
        return
    if stmt.get('contentHash'): errs.append('social-must-not-bind-article')
    if not SHA.match(stmt['postTextHash']): errs.append('social-bad-postTextHash')
    if not TOKEN.match(stmt['channel']): errs.append('social-bad-channel')
    if len(stmt['destination']) > 200: errs.append('social-bad-destination')
    if not ISO_TIME.match(stmt['publish_time']):
        errs.append('social-bad-publish_time')
    else:
        try: datetime.fromisoformat(stmt['publish_time'].replace('Z', '+00:00'))
        except ValueError: errs.append('social-bad-publish_time')
    if ZoneInfo is None:
        errs.append('social-timezone-unverifiable')
    else:
        try: ZoneInfo(stmt['timezone'])
        except Exception: errs.append('social-bad-timezone')
    if not stmt.get('assets'): errs.append('social-needs-at-least-one-image')
    if 'postText' in stmt: errs.append('social-raw-text-not-allowed')


def consumed_nonces(root, ref):
    """Single-use ledger, derived from the protected branch's own history.
    An approval is consumed once its file has ever been added or modified on `ref` (the merge is the
    hand-off to publication). Removing the post later does not un-consume it. Nothing outside git
    history is read or written, so there is no state to tamper with or pay for. `ref`'s history is
    protected by the ruleset (no force push, no deletion; only the admin path can rewrite it)."""
    out = subprocess.run(['git', '-C', root, 'log', ref, '--format=@%H', '--diff-filter=AMR', '--name-only',
                          '--', 'content/blog/*.approval.json'], capture_output=True, text=True, check=True).stdout
    seen, commit = set(), None
    for line in out.splitlines():
        if line.startswith('@'): commit = line[1:]; continue
        if not line.strip() or not commit: continue
        blob = subprocess.run(['git', '-C', root, 'show', f'{commit}:{line}'], capture_output=True, text=True)
        if blob.returncode != 0: continue
        try:
            n = json.loads(blob.stdout).get('nonce')
        except Exception:
            continue
        if isinstance(n, str) and n: seen.add(n)
    return seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--approval', required=True)
    ap.add_argument('--pubkey', required=True)
    ap.add_argument('--changed', default='', help='csv of PR-changed files; if set, each must be covered')
    ap.add_argument('--root', default='.')
    ap.add_argument('--ledger', default='')
    ap.add_argument('--history-ref', default='',
                    help='protected branch (e.g. origin/main); approvals already on it are consumed (replay check). '
                         'Used for PR intake only; re-validating what is already on main omits it, so a deploy retry works.')
    a = ap.parse_args(); errs = []; root = a.root
    j = lambda rel: os.path.join(root, rel)

    stmt = json.load(open(j(a.approval), encoding='utf-8'))
    sig = bytes.fromhex(stmt.pop('sig', '') or '')
    pub = load_pem_public_key(open(j(a.pubkey), 'rb').read())
    try: pub.verify(sig, canonical(stmt))
    except InvalidSignature: errs.append('approval-signature-invalid')
    if stmt.get('author') != 'Ryan Phelan': errs.append('author-not-allowed')
    if not isinstance(stmt.get('nonce'), str) or not stmt.get('nonce').strip(): errs.append('approval-missing-nonce')
    slug = stmt.get('slug', '')
    covered = {a.approval}

    kind = stmt.get('kind', 'article')
    if kind == 'article':
        if not stmt.get('contentHash'):
            errs.append('article-approval-missing-contentHash')   # closes the ambiguous image-only path
        else:
            art = f'content/blog/{slug}.md'; covered.add(art)
            if not os.path.exists(j(art)):
                errs.append(f'article-missing:{art}')
            else:
                body = open(j(art), encoding='utf-8').read().split('\n---\n', 1)
                body = body[1] if len(body) > 1 else ''
                if BANNED.search(re.sub(r'```prompt.*?```', '', body, flags=re.S)):
                    errs.append('raw-html-or-script-in-body')
                if stmt['contentHash'] != chash(j(art)):
                    errs.append('content-hash-mismatch')
    elif kind == 'social':
        check_social_fields(stmt, errs)
    else:
        errs.append(f'unknown-approval-kind:{kind}')

    for asset in stmt.get('assets', []):
        rel = asset.get('path', ''); covered.add(rel)
        if not IMG.match(rel): errs.append(f'asset-path-not-allowed:{rel}'); continue
        if not HEX64.match(str(asset.get('sha256', ''))): errs.append(f'asset-bad-sha256:{rel}'); continue
        if not os.path.exists(j(rel)): errs.append(f'asset-missing:{rel}'); continue
        h = validate_image(root, rel, errs)
        if h is not None and h != asset.get('sha256'):
            errs.append(f'asset-hash-mismatch:{rel}')

    if a.changed:
        for c in [x for x in a.changed.split(',') if x]:
            if not (ART.match(c) or APR.match(c) or IMG.match(c)):
                errs.append(f'path-not-allowed:{c}')
            elif c not in covered:
                errs.append(f'changed-file-not-covered-by-approval:{c}')

    if a.history_ref and stmt.get('nonce'):
        try:
            if stmt['nonce'] in consumed_nonces(root, a.history_ref): errs.append('replay-approval-consumed')
        except Exception as e:
            errs.append(f'ledger-unreadable:{e.__class__.__name__}')   # fail closed

    if a.ledger:
        key = f"{stmt.get('id')}|{stmt.get('contentHash') or stmt.get('postTextHash')}|{stmt.get('nonce')}"
        seen = set(open(a.ledger).read().split('\n')) if os.path.exists(a.ledger) else set()
        if key in seen: errs.append('replay-approval-consumed')

    if errs: print('VALIDATION FAILED:', ';'.join(errs)); sys.exit(1)
    print(f'VALIDATION OK ({kind})'); sys.exit(0)


if __name__ == '__main__':
    main()
