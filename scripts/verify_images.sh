#!/usr/bin/env bash
# Independent liveness check for social card images (Pages via Actions). For every approved image
# under images/social/, fetches the SERVED bytes (cache-busted) and confirms their SHA-256 equals the
# content-addressed filename, which is the hash in the signed approval. Exits non-zero on any
# mismatch or persistent non-200, so the deploy job fails and dependent social posts HOLD.
# BASE = deploy page_url. Articles keep their own check (verify_pages.sh); this one is images only.
set -uo pipefail
: "${BASE:?set BASE to the Pages deploy page_url}"
shopt -s nullglob
imgs=(images/social/*.png)
if [ "${#imgs[@]}" = 0 ]; then echo "no social card images; nothing to verify"; exit 0; fi
fail=0
for f in "${imgs[@]}"; do
  want=$(basename "$f" .png)
  url="${BASE%/}/$f"
  ok=0
  for try in 1 2 3 4 5; do
    code=$(curl -s -o served.png -w '%{http_code}' "$url?cb=$RANDOM$RANDOM") || true
    if [ "$code" = "200" ]; then
      got=$(sha256sum served.png | cut -d' ' -f1)
      if [ "$got" = "$want" ]; then echo "LIVE-VERIFIED image $want"; ok=1; break
      else echo "VerifyFailed image $want: 200 but served bytes hash to $got"; fail=1; break; fi
    fi
    echo "  image ${want:0:12} try $try: http $code (propagation lag, retry)"; sleep 15
  done
  [ "$ok" = 0 ] && { echo "HOLD image $want: never verified"; fail=1; }
done
rm -f served.png
[ "$fail" = 0 ] && echo "ALL SOCIAL IMAGES LIVE-VERIFIED -> dependent social may release" \
               || { echo "HOLD social: image not independently verified"; exit 1; }
