#!/usr/bin/env bash
# Exercises a deployed Worker against the live Spotline development host.
#
#   bash worker/test/curl.sh https://diana-spotline.<your-subdomain>.workers.dev
#
# Everything here sends "dryrun": true, so Spotline validates but stores
# nothing. Run it once after the first deploy, and again after any change to
# wrangler.toml — that is the file where a wrong value is invisible until
# somebody tries to spot from a hilltop with one bar of signal.
set -uo pipefail

BASE="${1:?usage: curl.sh <worker url>}"
BASE="${BASE%/}"
ORIGIN="https://diana-onff.github.io"

pass=0
fail=0

# $1 what we expect, $2 description, $3.. the curl arguments
check() {
  local want="$1" what="$2"; shift 2
  local out code body
  out="$(curl -sS -w '\n%{http_code}' "$@" 2>&1)"
  code="$(printf '%s' "$out" | tail -n 1)"
  body="$(printf '%s' "$out" | sed '$d')"
  if [ "$code" = "$want" ]; then
    pass=$((pass + 1)); printf '  ✓ %s (%s)\n' "$what" "$code"
  else
    fail=$((fail + 1)); printf '  ✗ %s — expected %s, got %s\n    %s\n' "$what" "$want" "$code" "${body:0:200}"
  fi
}

echo
echo "Worker: $BASE"

echo
echo "[1] is it alive"
check 200 "/status answers" "$BASE/status"
printf '    '; curl -sS "$BASE/status"; echo

echo
echo "[2] CORS"
check 204 "preflight from the app's origin" -X OPTIONS -H "Origin: $ORIGIN" \
  -H 'Access-Control-Request-Method: POST' "$BASE/spot"
check 403 "preflight from somewhere else" -X OPTIONS -H 'Origin: https://evil.example' \
  -H 'Access-Control-Request-Method: POST' "$BASE/spot"

echo
echo "[3] what must be refused before it costs anything"
check 400 "MHz where kHz was meant" -X POST -H 'Content-Type: application/json' -H "Origin: $ORIGIN" \
  -d '{"activator":"ON3VZ/P","spotter":"ON3VZ","frequency_khz":14.285,"mode":"SSB","reference":"ONFF-0104","dryrun":true}' \
  "$BASE/spot"
check 400 "a reference that is not a reference" -X POST -H 'Content-Type: application/json' -H "Origin: $ORIGIN" \
  -d '{"activator":"ON3VZ/P","spotter":"ON3VZ","frequency_khz":14285,"mode":"SSB","reference":"NOPE","dryrun":true}' \
  "$BASE/spot"
check 400 "a mode nobody transmits" -X POST -H 'Content-Type: application/json' -H "Origin: $ORIGIN" \
  -d '{"activator":"ON3VZ/P","spotter":"ON3VZ","frequency_khz":14285,"mode":"TELEPATHY","reference":"ONFF-0104","dryrun":true}' \
  "$BASE/spot"
check 400 "not even JSON" -X POST -H 'Content-Type: application/json' -H "Origin: $ORIGIN" \
  -d 'this is not json' "$BASE/spot"
check 404 "an endpoint that does not exist" -X POST -H 'Content-Type: application/json' -H "Origin: $ORIGIN" \
  -d '{}' "$BASE/whatever"

echo
echo "[4] a real spot, dry"
check 200 "a valid spot is accepted by Spotline" -X POST -H 'Content-Type: application/json' -H "Origin: $ORIGIN" \
  -d '{"activator":"ON3VZ/P","spotter":"ON3VZ","frequency_khz":14285,"mode":"SSB","reference":"ONFF-0104","remarks":"dryrun test","dryrun":true}' \
  "$BASE/spot"

echo
echo "[5] a real agenda entry, dry"
START="$(date -u -d '+2 hours' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v+2H +%Y-%m-%dT%H:%M:%SZ)"
END="$(date -u -d '+4 hours' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v+4H +%Y-%m-%dT%H:%M:%SZ)"
check 200 "a valid announcement is accepted" -X POST -H 'Content-Type: application/json' -H "Origin: $ORIGIN" \
  -d "{\"activator_call\":\"ON3VZ/P\",\"reference\":\"ONFF-0104\",\"utc_start\":\"$START\",\"utc_end\":\"$END\",\"pin\":\"1234\",\"poster\":\"ON3VZ\",\"dryrun\":true}" \
  "$BASE/agenda"
check 400 "an announcement two months out" -X POST -H 'Content-Type: application/json' -H "Origin: $ORIGIN" \
  -d "{\"activator_call\":\"ON3VZ/P\",\"reference\":\"ONFF-0104\",\"utc_start\":\"2027-01-01T10:00:00Z\",\"utc_end\":\"2027-01-01T12:00:00Z\",\"pin\":\"1234\",\"poster\":\"ON3VZ\",\"dryrun\":true}" \
  "$BASE/agenda"

echo
echo "[6] the rate limiter — this is the one that matters"
echo "    ten spots in a row; the first few pass, the rest must come back 429"
limited=0
for i in $(seq 1 10); do
  code="$(curl -sS -o /dev/null -w '%{http_code}' -X POST \
    -H 'Content-Type: application/json' -H "Origin: $ORIGIN" \
    -d '{"activator":"ON3VZ/P","spotter":"ON3VZ","frequency_khz":14285,"mode":"SSB","reference":"ONFF-0104","dryrun":true}' \
    "$BASE/spot")"
  printf '    %2d → %s\n' "$i" "$code"
  [ "$code" = "429" ] && limited=$((limited + 1))
done
if [ "$limited" -gt 0 ]; then
  pass=$((pass + 1)); printf '  ✓ the limiter cut in (%d of 10 refused)\n' "$limited"
else
  fail=$((fail + 1)); printf '  ✗ nothing was refused — check LIMIT_IP_SPOTS and the KV binding\n'
fi

echo
if [ "$fail" -eq 0 ]; then
  printf 'ALL OK — %d passed\n\n' "$pass"
else
  printf 'FAILED — %d passed, %d failed\n\n' "$pass" "$fail"
  exit 1
fi
