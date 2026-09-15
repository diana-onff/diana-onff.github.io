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

# ------------------------------------------------------------------- the data
#
# What the app really loads. This list used to be written out by hand, in the
# Belgium-only filenames from before Diana had a manifest — and it stayed that
# way when the build moved to one folder per country. The result was invisible
# for Belgium and total for everyone else: data/countries.json and data/zones/
# were built correctly, merged, and sitting on main, and still never reached the
# published site. The app then found no manifest at all, fell back to "assume
# Belgium, under the old names", and a second country could not exist no matter
# how often it was rebuilt. Germany was live for a day before anyone could say
# why it was not.
#
# Hence: copy what the build writes, and check it against the manifest rather
# than against a list in this script. A list in this script is the thing that
# went wrong.
#
# (Every copy is an 'if' rather than '[ … ] && cp' — with set -e the script
# would stop at a false test otherwise.)

# The manifest, and the per-country files it points at. Together these are what
# makes more than one country possible; without them the app has nothing to go on.
if [ -f data/countries.json ]; then
  cp data/countries.json "$OUT/data/"
fi
if [ -d data/zones ]; then
  cp -r data/zones "$OUT/data/"
fi

# Shared by every country: provenance, the worldwide programme list, and the
# worldwide points layer. The last two only exist after a build that could
# actually reach the WWFF directory.
for gedeeld in data/meta.json data/wwff-programs.json data/wwff-world.geojson; do
  if [ -f "$gedeeld" ]; then
    cp "$gedeeld" "$OUT/data/"
  fi
done

# Belgium under the names it had before the manifest existed. The build no longer
# writes these — they are a safety net for a visitor whose installed service
# worker still asks for them, and for a data set older than the manifest. They
# drift further out of date with every build that does not touch them, so they
# may be deleted from the repository once nobody is on that old shell any more;
# nothing here breaks when they go, which is exactly why this is an 'if' now and
# not the unconditional cp it used to be.
for oud in data/onff.geojson data/onff-index.json data/onff-points.geojson data/onff-activity.json; do
  if [ -f "$oud" ]; then
    cp "$oud" "$OUT/data/"
  fi
done

# Nothing may be promised that is not published. A zones/<country>.geojson that
# the manifest names but that is not in the output is a 404 at exactly the
# moment someone in the field switches to that country — and it is silent until
# then, which is how this went unnoticed for a day. Checked against the manifest
# itself, so a future change to the build's layout is followed automatically.
if [ -f "$OUT/data/countries.json" ]; then
  python3 - "$OUT" <<'PY'
import json, pathlib, sys

data = pathlib.Path(sys.argv[1]) / "data"
manifest = json.loads((data / "countries.json").read_text(encoding="utf-8"))
landen = manifest.get("countries") or []
ontbreekt = [f"{c.get('program', '?')}: {pad}"
             for c in landen
             for pad in (c.get("files") or {}).values()
             if not (data / pad).is_file()]
if ontbreekt:
    sys.exit("site.sh: the manifest names files that are not being published:\n  "
             + "\n  ".join(ontbreekt))
print("countries published: " + (", ".join(c.get("program", "?") for c in landen) or "none"))
PY
else
  echo "site.sh: no data/countries.json — publishing the pre-manifest layout only" >&2
fi

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

# The placeholder lives in js/core.js: first index.html, then app.js, and since
# the split per screen it is core.js. Rather than name that file here, every .js
# under js/ is searched — move the constant to another file and this keeps
# working. The count over all of them together is checked and must be exactly 1:
# a silent failure here means the app keeps showing "dev" for months without
# anyone noticing, and two hits would mean the constant is declared twice.
treffers = [p for p in sorted((uit / "js").glob("*.js"))
            if "'__DIANA_BUILD__'" in p.read_text(encoding="utf-8")]
aantal = sum(p.read_text(encoding="utf-8").count("'__DIANA_BUILD__'") for p in treffers)
if aantal != 1:
    namen = ", ".join(p.name for p in treffers) or "no file"
    sys.exit(f"site.sh: placeholder __DIANA_BUILD__ found {aantal}x under js/ ({namen}), expected 1")
js = treffers[0]
tekst = js.read_text(encoding="utf-8")
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
