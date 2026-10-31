#!/usr/bin/env bash
# Content-level liveness check for Pages-via-Actions. Compares the SHA-256 of the SERVED
# article body to the SHA-256 of the rendered (approved) article body. Exits non-zero on any
# mismatch or persistent non-200 so the dependent social release HOLDS. BASE = deploy page_url.
set -uo pipefail
: "${BASE:?set BASE to the Pages deploy page_url}"
bodyhash() { python3 - "$1" <<'P'
import sys
s=open(sys.argv[1],encoding='utf-8').read()
a=s.index('<div class="art-body">')+len('<div class="art-body">'); b=s.index('</div></article>')
import hashlib; print('sha256:'+hashlib.sha256(s[a:b].strip().encode()).hexdigest())
P
}
fail=0
for f in writing/*.html; do
  slug=$(basename "$f" .html); want=$(bodyhash "$f"); url="${BASE%/}/writing/$slug.html"
  ok=0
  for try in 1 2 3 4 5; do
    code=$(curl -s -o served.html -w '%{http_code}' "$url?cb=$RANDOM") || true
    if [ "$code" = "200" ]; then
      got=$(bodyhash served.html)
      if [ "$got" = "$want" ]; then echo "LIVE-VERIFIED $slug: served body == approved body ($got)"; ok=1; break
      else echo "VerifyFailed $slug: 200 but body mismatch (served $got want $want)"; fail=1; break; fi
    fi
    echo "  $slug try $try: http $code (propagation lag, retry)"; sleep 15
  done
  [ "$ok" = 0 ] && { echo "HOLD $slug: never verified"; fail=1; }
done
[ "$fail" = 0 ] && echo "ALL ARTICLES LIVE-VERIFIED -> dependent social may release" \
               || { echo "HOLD social: not independently verified"; exit 1; }
