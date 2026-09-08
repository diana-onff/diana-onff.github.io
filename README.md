# Diana

Map app for the Belgian ONFF nature reserves (Belgian Flora & Fauna, part of WWFF)
with live WWFF spots. A PWA on an open-source base map, which works offline and can
be embedded in a website.

Code: MIT. Data: not free — see [LICENSE](LICENSE).

This is the repo. The full plan is in `Diana - Technisch plan v0.6.md`; putting it online is covered in [DEPLOY.md](DEPLOY.md).

## Documentation

Detailed documentation per audience is in [`docs/`](docs/):

| Document | Who for | Contents |
|---|---|---|
| [docs/DEVELOPER.md](docs/DEVELOPER.md) | developers | cloning the repo, the two GitHub Actions workflows, generating `data/*.json` — automatically and by hand |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | developers/administrators | where every data source comes from, which APIs are involved, which folders the app reads |
| [docs/ADMIN.md](docs/ADMIN.md) | administrators | publishing a new ONFF release, using the admin screen in the app, troubleshooting |
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | users | platforms, installing as an app, every screen explained, embedding, and the **limitations** (everything local, no synchronisation between devices) |

This `README.md` and `DEPLOY.md` remain the shortest route for anyone already
familiar with the repo; the `docs/` folder is the full explanation for each of
the four audiences above.

---

## What is in this repo

```
source/           the official ONFF KMZ releases, as they come from the BOS groups.io
build/            the conversion from KMZ to the data files the app loads       ← build time
data/             the result — this is what the app fetches
overrides.json    manual corrections that survive every new release
web/              the web application itself                                    ← runtime
_site/            what gets published (made by build/site.sh, not in git)
.github/          the Action that does all of this automatically on a pull request
```

Two halves that do not get mixed up: `build/` runs on a GitHub runner and never
reaches a user; `web/` is what people open.

## Running the app

A static server is enough — the app has no backend.

```bash
python3 -m http.server 8000        # from the repo root, not from web/
# open http://localhost:8000/web/
```

Starting from inside `web/` does not work: the app fetches `../data/onff.geojson`,
and that falls outside the server root.

Six screens in the bottom bar: **Map** (zones, four map styles, search, area panel,
GPS with "am I inside the zone"), **Spots** (what is active right now plus the
announced schedule, with bearing and distance), **Spot** (spotting yourself via
Spotline), **Session** (an activation session with GPX evidence), **Heatmap**
(colours the map by last activation or number of QSOs) and **Rules** (band plan per
mode). Plus NL/FR/EN and a service worker that keeps everything available offline.

The self-spotting screen takes its validation rules straight from the page code of
`spots.wwff.co/spots/create` (callsign pattern, frequency ranges, a reference of at
least 7 characters, a comment of at most 100 characters) and checks the reference
through their `/api/references/validate` endpoint. Submitting happens as an
**ordinary form post in a new tab** — that is allowed cross-origin, and the user sees
Spotline's own confirmation. That is why this feature needs no proxy at all.

Reference numbers are on by default. They come from a separate point source with one
point per reference: put them on the polygon layer and MapLibre draws a label per
polygon part — and ONFF-0329 consists of 67 separate parcels.

**URL parameters** (also for the embed on the blogspot):

| Parameter | What |
|---|---|
| `?lang=nl\|fr\|en` | force the language; by default it follows the browser |
| `?ref=ONFF-0104` | zoom straight in on one area |
| `?prov=limburg` | zoom in on a province |
| `?spots=1` | switch the spots layer on right away |
| `?embed=1` | hide the app chrome for an iframe |
| `?admin=1` | show the admin screen (also: tap the logo five times) |

```html
<iframe src="https://diana-onff.github.io/?embed=1&prov=antwerpen&lang=nl&spots=1"
        width="100%" height="600" style="border:0" loading="lazy"></iframe>
```

**Two external sources, both with a visible fallback.** The spots come from
`spots.wwff.co` and the heatmap from the published ONFF status sheet. Whether those
two allow a direct connection from the browser (CORS) has not been established yet;
if it does not work, the app says so in as many words and the Worker from the plan
is needed.

---

## Publishing a new ONFF release

This is the whole procedure. No command is involved.

1. Get the new `ONFF_YYYYMMDD.kmz` from the BOS groups.io.
2. On github.com, go to the `source/` folder, click **Add file → Upload files**, drag
   the file in, and pick **Create a new branch for this commit** at the bottom.
   (The file is about 17 MB; the web limit is 25 MiB, so it fits.)
3. The Action runs automatically and puts a report under your pull request:

   > **945 areas** (was 932, +13) · **15 new** · **2 gone** · **7 changed boundary**

   With the lists collapsible and the warnings alongside.
4. Click the preview link to really look at the new map before you publish anything.
5. Does it look right? **Merge** the pull request. That is publishing.
6. Does it not? Close the pull request, or use **Revert** on the merge commit to go
   back to the previous version in one click.

An area that has disappeared is not an error but real information — ONFF does remove
areas. That is why it is in the report, and why it is never applied silently.

That pull request also gets a **preview link** to the map with the new data. Look at
it before you merge — that is the only check there is. See [DEPLOY.md](DEPLOY.md).

---

## Correcting names

The area names in the KMZ contain typos and inconsistent spellings. The script picks
the best variant automatically, but not always the right one. Correct those in
`overrides.json`:

```json
"ONFF-0599": {
  "name": "Carrière de l'Alouette",
  "_why": "KMZ schrijft \"Carriere de 'Alouttel\" — twee typfouten"
}
```

The key is always the **number**, never the name. Add a `_why`, so that three years
from now it is still clear why that correction is there. A pull request on this file
makes the Action run again.

---

## Running it locally

```bash
pip install -r build/requirements.txt
python build/kmz2geojson.py --kmz "source/ONFF 20260101.kmz"
```

Takes about half a minute. Options:

| Option | Default | What for |
|---|---|---|
| `--tolerance` | `0.00005` | simplification in degrees; 0.00005 ≈ 5 m |
| `--decimals` | `5` | rounding of the coordinates; 5 ≈ 1 m |
| `--out` | `data` | output folder |
| `--overrides` | `overrides.json` | corrections file |
| `--report` | `report.md` | where the diff report goes |

---

## The data files

| File | Size | What |
|---|---|---|
| `data/onff.geojson` | 3.7 MB (1.0 MB gzipped) | one MultiPolygon per reference, with name, province, area and whatever attributes are known |
| `data/onff-points.geojson` | small | references that *are* in the WWFF directory but have no boundary in the KMZ, as a point. The app shows them as a dotted ring and deliberately does not run an "am I inside" test on them |
| `data/onff-activity.json` | 39 kB | per reference the number of QSOs and the date of the last activation, from the WWFF directory. The heatmap uses this when the ONFF sheet is unreachable |
| `data/onff-index.json` | 210 kB | the same list without geometry, plus the points. It is *not* loaded by the app — that builds its own index from the two geojson files. Meant for reports and tooling alongside |
| `data/meta.json` | small | provenance: which source file, which release, which settings, and how many references without a boundary have been placed |

That the whole of Belgium fits in one megabyte is the reason Diana needs no tile
server and can work entirely offline.

### What not to expect in the data

Attribute coverage in the KMZ is uneven. Of the 932 areas:

- **565** have a designation (`desig`), **515** an IUCN category, **445** a manager
- **75** a registration number, **81** a region code
- and roughly half have **nothing** beyond a name and a number

Every field is therefore optional. The app has to leave empty fields out, not show
them as a dash. What is always computed and always present: area, centre point,
bounding box and province.

### Known quirks of the source

- The reference number is **not in a field** but in the name of the parent folder, as
  `ONFF-nnnn <name>`. That is why everything works off the number.
- The KMZ contains a Maidenhead grid layer of some 32,700 placemarks. That gets thrown
  away — a grid is cheaper to compute than to ship.
- Underneath it is a WDPA export with the ONFF layer on top; hence the fields in
  capitals (`MANG_AUTH`, `GIS_AREA`, `IUCN_CAT`) alongside the Flemish ones in
  lowercase (`opp_ha`, `inspireid`).
- **Which references exist comes from the WWFF directory**
  (`https://wwff.co/wwff-data/wwff_directory.csv`, refreshed daily, 68,000 references
  worldwide of which 964 are ONFF). The KMZ only says which ones have a *boundary*.
  Of the 948 active ONFF references, 932 have a polygon; the remaining 16 go on the
  map as a **point**, with the coordinate from the directory or from
  `overrides.json` (`"point": [lon, lat]`). Deleted references are not shown. Every
  reference appears exactly once: a polygon always beats a point. See
  [docs/ADMIN.md](docs/ADMIN.md#3-a-reference-with-no-boundary).
