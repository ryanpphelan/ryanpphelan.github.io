#!/usr/bin/env python3
import sys, json, re, hashlib, argparse
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.exceptions import InvalidSignature
ALLOW=re.compile(r'^content/blog/[a-z0-9-]+\.(md|approval\.json)$')
BANNED=re.compile(r'<script|<iframe|javascript:|onerror=|onload=', re.I)
def chash(p):
    return 'sha256:'+hashlib.sha256(open(p,'rb').read().replace(b'\r\n',b'\n')).hexdigest()
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--content',required=True); ap.add_argument('--approval',required=True)
    ap.add_argument('--pubkey',required=True); ap.add_argument('--changed',required=True,
        help='comma-separated list of files changed in the PR'); ap.add_argument('--ledger',default='')
    a=ap.parse_args(); errs=[]
    changed=[c for c in a.changed.split(',') if c]
    for c in changed:
        if not ALLOW.match(c): errs.append(f'path-not-allowed:{c}')
    body=open(a.content,encoding='utf-8').read().split('\n---\n',1)
    body=body[1] if len(body)>1 else ''
    if BANNED.search(re.sub(r'```prompt.*?```','',body,flags=re.S)): errs.append('raw-html-or-script-in-body')
    stmt=json.load(open(a.approval))
    sig=bytes.fromhex(stmt.pop('sig'))
    pub=load_pem_public_key(open(a.pubkey,'rb').read())
    msg=json.dumps(stmt,sort_keys=True,separators=(',',':')).encode()
    try: pub.verify(sig,msg)
    except InvalidSignature: errs.append('approval-signature-invalid')
    if stmt.get('contentHash')!=chash(a.content): errs.append('content-hash-mismatch')
    if stmt.get('author')!='Ryan Phelan': errs.append('author-not-allowed')
    if a.ledger:
        key=f"{stmt.get('id')}|{stmt.get('contentHash')}|{stmt.get('nonce')}"
        import os
        seen=set(open(a.ledger).read().split('\n')) if os.path.exists(a.ledger) else set()
        if key in seen: errs.append('replay-approval-consumed')
    if errs: print('VALIDATION FAILED:',';'.join(errs)); sys.exit(1)
    print('VALIDATION OK'); sys.exit(0)
if __name__=='__main__': main()
