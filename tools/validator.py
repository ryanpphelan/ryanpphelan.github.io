#!/usr/bin/env python3
"""Blog publishing validator (articles + Option A social card images).
Validates ONE signed approval and every file it binds: the article (by contentHash) and each
social card image (by exact SHA-256 in the approval's `assets`). A changed article or image that
no longer matches its signed hash fails. Marketing can submit only content/blog/** and
images/social/<sha256>.png, and only files covered by the approval it carries."""
import sys, json, re, hashlib, argparse, os
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.exceptions import InvalidSignature
try:
    from PIL import Image
    HAVE_PIL = True
except Exception:
    HAVE_PIL = False

ART = re.compile(r'^content/blog/[a-z0-9-]+\.md$')
APR = re.compile(r'^content/blog/[a-z0-9-]+\.approval\.json$')
IMG = re.compile(r'^images/social/[0-9a-f]{64}\.png$')
BANNED = re.compile(r'<script|<iframe|javascript:|onerror=|onload=', re.I)
PNG_MAGIC = b'\x89PNG\r\n\x1a\n'
ALLOWED_DIMS = {(1080, 1350)}
MAX_BYTES = 5 * 1024 * 1024

def chash(p):  # article: normalize CRLF so hashing is platform-independent
    return 'sha256:' + hashlib.sha256(open(p, 'rb').read().replace(b'\r\n', b'\n')).hexdigest()

def validate_image(root, rel, errs):
    p = os.path.join(root, rel)
    data = open(p, 'rb').read()
    ok = True
    if data[:8] != PNG_MAGIC: errs.append(f'{rel}:not-a-png'); ok = False
    if len(data) > MAX_BYTES: errs.append(f'{rel}:too-large:{len(data)}'); ok = False
    if HAVE_PIL:
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

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--approval', required=True)
    ap.add_argument('--pubkey', required=True)
    ap.add_argument('--changed', default='', help='csv of PR-changed files; if set, each must be covered')
    ap.add_argument('--root', default='.')
    ap.add_argument('--ledger', default='')
    a = ap.parse_args(); errs = []; root = a.root
    j = lambda rel: os.path.join(root, rel)

    stmt = json.load(open(j(a.approval)))
    sig = bytes.fromhex(stmt.pop('sig'))
    pub = load_pem_public_key(open(j(a.pubkey), 'rb').read())
    msg = json.dumps(stmt, sort_keys=True, separators=(',', ':')).encode()
    try: pub.verify(sig, msg)
    except InvalidSignature: errs.append('approval-signature-invalid')
    if stmt.get('author') != 'Ryan Phelan': errs.append('author-not-allowed')
    slug = stmt.get('slug', '')
    covered = {a.approval}

    if stmt.get('contentHash'):
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

    for asset in stmt.get('assets', []):
        rel = asset.get('path', ''); covered.add(rel)
        if not IMG.match(rel): errs.append(f'asset-path-not-allowed:{rel}'); continue
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

    if a.ledger:
        key = f"{stmt.get('id')}|{stmt.get('contentHash')}|{stmt.get('nonce')}"
        seen = set(open(a.ledger).read().split('\n')) if os.path.exists(a.ledger) else set()
        if key in seen: errs.append('replay-approval-consumed')

    if errs: print('VALIDATION FAILED:', ';'.join(errs)); sys.exit(1)
    print('VALIDATION OK'); sys.exit(0)

if __name__ == '__main__':
    main()
