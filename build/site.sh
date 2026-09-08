#!/usr/bin/env bash
# Builds the directory that gets published. Anything not in here does not go online.
#
# Important: source/ is deliberately left out. The ONFF KMZ is distributed by ONFF
# through a groups.io behind membership; that file has no business sitting on a
# public URL unasked.
#
# This is also where the version stamp is set. That happens at build time on
# purpose and not in the repo: a number you have to bump by hand sooner or later
# stands still — and then the app lies about what you are running. The commit hash
# is always right, without anyone having to think about it.
set -euo pipefail

OUT="${1:-_site}"
rm -rf "$OUT"
mkdir -p "$OUT/data"

cp -r web/. "$OUT/"
cp data/onff.geojson data/onff-index.json data/meta.json "$OUT/data/"
# From the WWFF directory, so only present after a build that could fetch it.
# (As an 'if', not as '[ … ] && cp' — with set -e the script would stop there otherwise.)
for extra in data/onff-points.geojson data/onff-activity.json data/wwff-programs.json data/wwff-world.geojson; do
  if [ -f "$extra" ]; then
    cp "$extra" "$OUT/data/"
  fi
done

# --------------------------------------------------------------- version stamp
# Inside an Action the hash is in GITHUB_SHA; locally we ask git itself. If
# neither works (an unpacked zip with no .git), then "lokaal" is a more honest
# answer than a made-up number.
SHA="${GITHUB_SHA:-}"
if [ -z "$SHA" ]; then
  SHA="$(git rev-parse HEAD 2>/dev/null || true)"
fi
KORT="${SHA:0:7}"
[ -n "$KORT" ] || KORT="lokaal"

# Date of the commit itself, not of the moment of building: build the same point
# twice and the same stamp ought to come out.
DATUM="$(git log -1 --format=%cd --date=format:'%d/%m/%Y' 2>/dev/null || date -u +'%d/%m/%Y')"
BUILD="$KORT · $DATUM"

# The app reads this as the constant BUILD. Python instead of sed, because a
# silent failure here goes unnoticed for months — and because the number of
# replacements can be checked.
python3 - "$OUT" "$BUILD" <<'PY'
import pathlib, sys

uit, build = pathlib.Path(sys.argv[1]), sys.argv[2]

# Since the split-up the placeholder lives in app.js and no longer in index.html.
# The count is checked and must be exactly 1: a silent failure here means the app
# keeps showing "dev" for months without anyone noticing.
js = uit / "app.js"
tekst = js.read_text(encoding="utf-8")
aantal = tekst.count("'__DIANA_BUILD__'")
if aantal != 1:
    sys.exit(f"site.sh: placeholder __DIANA_BUILD__ found {aantal}x in app.js, expected 1")
js.write_text(tekst.replace("'__DIANA_BUILD__'", f"'{build}'"), encoding="utf-8")

# The service worker gets its own cache name per build. That way it clears out
# everything from the previous release by itself on activation, and an old version
# in the cache is no longer a matter of patience but of a single reload.
sw = uit / "sw.js"
tekst = sw.read_text(encoding="utf-8")
import re
nieuw, n = re.subn(r"(const VERSION\s*=\s*')[^']*(')",
                   lambda m: m.group(1) + "diana-" + build.split(" ")[0] + m.group(2),
                   tekst, count=1)
if n != 1:
    sys.exit("site.sh: VERSION not found in sw.js")
sw.write_text(nieuw, encoding="utf-8")
print(f"version stamp: {build}")
PY

echo "Published to $OUT:"
find "$OUT" -type f | sed "s|^$OUT/|  |" | sort
