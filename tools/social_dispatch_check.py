#!/usr/bin/env python3
"""Dispatch gate for a social post that carries a card image (Website Build contract for Marketing).

Run immediately before handing a post to the scheduler. Exits 0 only if ALL of these hold:
  1. the approval is a valid kind:"social" approval signed by the Approval Authority key;
  2. the exact post text about to go out hashes to the signed postTextHash;
  3. channel, destination, publish_time and timezone about to be used equal the signed values;
  4. every signed card image is independently verified LIVE on ryanphelan.com (served bytes, cache
     busted, hash to the signed SHA-256).
Any difference is a material change: exit 1, HOLD the post, and request a new approval.
Usage:
  social_dispatch_check.py --approval A.json --pubkey keys/approval-public.pem --text-file post.txt \
     --channel linkedin --destination "..." --publish-time 2026-11-05T15:00:00Z --timezone America/Chicago \
     [--base https://ryanphelan.com]
"""
import argparse, hashlib, json, sys, time, random, urllib.request, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validator import canonical  # same canonical bytes the Approval Service signs
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.exceptions import InvalidSignature


def fetch(url, timeout=20):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, r.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--approval', required=True)
    ap.add_argument('--pubkey', required=True)
    ap.add_argument('--text-file', required=True, help='UTF-8 file holding the exact post text')
    ap.add_argument('--channel', required=True)
    ap.add_argument('--destination', required=True)
    ap.add_argument('--publish-time', required=True)
    ap.add_argument('--timezone', required=True)
    ap.add_argument('--base', default='https://ryanphelan.com')
    ap.add_argument('--tries', type=int, default=3)
    ap.add_argument('--wait', type=float, default=10.0)
    a = ap.parse_args(); errs = []

    stmt = json.load(open(a.approval, encoding='utf-8'))
    sig = bytes.fromhex(stmt.pop('sig', '') or '')
    try: load_pem_public_key(open(a.pubkey, 'rb').read()).verify(sig, canonical(stmt))
    except InvalidSignature: errs.append('approval-signature-invalid')
    if stmt.get('kind') != 'social': errs.append('not-a-social-approval')

    text = open(a.text_file, 'rb').read()
    if 'sha256:' + hashlib.sha256(text).hexdigest() != stmt.get('postTextHash'):
        errs.append('post-text-changed-since-approval')
    for field, now in (('channel', a.channel), ('destination', a.destination),
                       ('publish_time', a.publish_time), ('timezone', a.timezone)):
        if stmt.get(field) != now:
            errs.append(f'{field}-changed-since-approval')

    if errs:  # do not bother checking liveness of an approval that no longer covers this post
        print('HOLD:', ';'.join(errs)); sys.exit(1)

    for asset in stmt.get('assets', []):
        want, url = asset.get('sha256'), f"{a.base.rstrip('/')}/{asset.get('path')}"
        ok = False
        for t in range(a.tries):
            try:
                code, body = fetch(f"{url}?cb={int(time.time())}{random.randint(0, 10**9)}")
                if code == 200 and hashlib.sha256(body).hexdigest() == want: ok = True; break
                if code == 200: errs.append(f'image-served-bytes-differ:{want}'); break
            except Exception:
                pass
            if t < a.tries - 1: time.sleep(a.wait)
        if not ok and not any(want in e for e in errs): errs.append(f'image-not-live:{want}')

    if errs: print('HOLD:', ';'.join(errs)); sys.exit(1)
    print('RELEASE: approval matches the post exactly and every card image is live-verified'); sys.exit(0)


if __name__ == '__main__':
    main()
