#!/usr/bin/env bash
# Bouwt de map die gepubliceerd wordt. Alles wat hier niet in staat, komt niet online.
#
# Belangrijk: source/ blijft er bewust buiten. Het ONFF-KMZ wordt door ONFF
# verspreid via een groups.io achter lidmaatschap; dat bestand hoort niet
# ongevraagd op een publieke URL te staan.
#
# Hier wordt ook het versiestempel gezet. Dat gebeurt met opzet bij het bouwen en
# niet in de repo: een nummer dat je met de hand moet ophogen, staat vroeg of laat
# stil — en dan liegt de app over wat je draait. De commit-hash klopt altijd,
# zonder dat iemand eraan hoeft te denken.
set -euo pipefail

OUT="${1:-_site}"
rm -rf "$OUT"
mkdir -p "$OUT/data"

cp -r web/. "$OUT/"
cp data/onff.geojson data/onff-index.json data/meta.json "$OUT/data/"
# Uit de WWFF-directory, dus pas aanwezig na een build die hem kon ophalen.
# (Als 'if', niet als '[ … ] && cp' — met set -e stopt het script daar anders op.)
for extra in data/onff-points.geojson data/onff-activity.json data/wwff-programs.json data/wwff-world.geojson; do
  if [ -f "$extra" ]; then
    cp "$extra" "$OUT/data/"
  fi
done

# ---------------------------------------------------------------- versiestempel
# In een Action staat de hash in GITHUB_SHA; lokaal vragen we het aan git zelf.
# Lukt geen van beide (een uitgepakte zip zonder .git), dan is "lokaal" een
# eerlijker antwoord dan een verzonnen nummer.
SHA="${GITHUB_SHA:-}"
if [ -z "$SHA" ]; then
  SHA="$(git rev-parse HEAD 2>/dev/null || true)"
fi
KORT="${SHA:0:7}"
[ -n "$KORT" ] || KORT="lokaal"

# Datum van de commit zelf, niet van het moment van bouwen: bouw je hetzelfde
# punt twee keer, dan hoort er hetzelfde stempel uit te komen.
DATUM="$(git log -1 --format=%cd --date=format:'%d/%m/%Y' 2>/dev/null || date -u +'%d/%m/%Y')"
BUILD="$KORT · $DATUM"

# De app leest dit als de constante BUILD. Python in plaats van sed, omdat een
# stille mislukking hier maandenlang onopgemerkt blijft — en omdat het aantal
# vervangingen te controleren valt.
python3 - "$OUT" "$BUILD" <<'PY'
import pathlib, sys

uit, build = pathlib.Path(sys.argv[1]), sys.argv[2]

html = uit / "index.html"
tekst = html.read_text(encoding="utf-8")
aantal = tekst.count("'__DIANA_BUILD__'")
if aantal != 1:
    sys.exit(f"site.sh: plaatshouder __DIANA_BUILD__ {aantal}x gevonden in index.html, verwacht 1")
html.write_text(tekst.replace("'__DIANA_BUILD__'", f"'{build}'"), encoding="utf-8")

# De service worker krijgt per build een eigen cachenaam. Daardoor ruimt hij bij
# het activeren vanzelf alles van de vorige uitgave op, en is een oude versie in
# de cache geen kwestie van geduld meer maar van één herlaadbeurt.
sw = uit / "sw.js"
tekst = sw.read_text(encoding="utf-8")
import re
nieuw, n = re.subn(r"(const VERSION\s*=\s*')[^']*(')",
                   lambda m: m.group(1) + "diana-" + build.split(" ")[0] + m.group(2),
                   tekst, count=1)
if n != 1:
    sys.exit("site.sh: VERSION niet gevonden in sw.js")
sw.write_text(nieuw, encoding="utf-8")
print(f"versiestempel: {build}")
PY

echo "Gepubliceerd naar $OUT:"
find "$OUT" -type f | sed "s|^$OUT/|  |" | sort
