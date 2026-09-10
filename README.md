# Diana

Map app for the Belgian ONFF nature reserves (Belgian Flora & Fauna, part of WWFF)
with live WWFF spots. A PWA on an open-source base map, which works offline and can
be embedded in a website.

Code: MIT. Data: not free — see [LICENSE](LICENSE).

This is the **public** repository: the app, the data, the workflows, and the
Worker's code. The ONFF source KMZ lives in a separate, **private**
repository (`diana-source`) — see [source/README.md](source/README.md) and
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for why. Putting all of this
online from scratch is covered in [docs/INSTALL.md](docs/INSTALL.md); the
short orientation on what runs where is in [DEPLOY.md](DEPLOY.md).

## Documentation

Detailed documentation per audience is in [`docs/`](docs/):

| Document | Who for | Contents |
|---|---|---|
| [docs/INSTALL.md](docs/INSTALL.md) | whoever sets Diana up somewhere new | building the whole thing from zero — organisation, repositories, permissions, the Worker — with a checkpoint after every step |
| [docs/DEVELOPER.md](docs/DEVELOPER.md) | developers | cloning the repo, the two GitHub Actions workflows, generating `data/*.json` — automatically and by hand |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | developers/administrators | where every data source comes from, which APIs are involved, which folders the app reads |
| [docs/ADMIN.md](docs/ADMIN.md) | administrators | publishing a new ONFF release, using the admin screen in the app, troubleshooting |
| [docs/MAINTENANCE.md](docs/MAINTENANCE.md) | whoever keeps Diana running | every credential in the project — where it lives, what breaks if it expires, how to replace it, and how to add a new administrator |
| [docs/SPOTLINE.md](docs/SPOTLINE.md) | developers/administrators | the Cloudflare Worker that proxies WWFF's Spotline API, and why it has to exist |
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | users | platforms, installing as an app, every screen explained, embedding, and the **limitations** (everything local, no synchronisation between devices) |

This `README.md` and `DEPLOY.md` remain the shortest route for anyone already
familiar with the repo; the `docs/` folder is the full explanation for each of
the audiences above.

---

## What is in this repo

```
source/           empty by default — the real KMZ lives in the private
                  diana-source repo; see source/README.md
build/            the conversion from KMZ to the data files the app loads       ← build time
data/             the result — this is what the app fetches
overrides.json    manual corrections that survive every new release
web/              the web application itself                                    ← runtime
worker/           the Cloudflare Worker that proxies WWFF Spotline — see docs/SPOTLINE.md
docs/             the full documentation set — see the table above
_site/            what gets published (made by build/site.sh, not in git)
.github/          the two Actions that build the data and publish the site
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

The bottom bar covers Map, Spots, self-spotting, announcing an activation,
an activation Session, the activation Heatmap, the band-plan Rules, and
Settings — every screen explained in full in
[docs/USER_GUIDE.md §3](docs/USER_GUIDE.md#3-the-screens). Seven languages
(English, Dutch, French, German, Danish, Italian, Spanish, Portuguese), and a service
worker that keeps everything available offline.

Self-spotting and announcing an activation both go through a small
Cloudflare Worker that holds WWFF's API key server-side — the app itself has
no server, so that key can't live in it. A plain form-post fallback exists
for when the Worker is unreachable. See
[docs/SPOTLINE.md](docs/SPOTLINE.md) for the whole story, including why
that's necessary at all.

Reference numbers are on by default. They come from a separate point source with one
point per reference: put them on the polygon layer and MapLibre draws a label per
polygon part — and ONFF-0329 consists of 67 separate parcels.

**URL parameters** (also for the embed on the blogspot):

| Parameter | What |
|---|---|
| `?lang=nl\|fr\|en\|de\|da\|it\|es\|pt` | force the language; by default it follows the browser only if you explicitly choose "Follow the browser" in Settings — otherwise it's English |
| `?ref=ONFF-0104` | zoom straight in on one area |
| `?prov=limburg` | zoom in on a province |
| `?spots=1` | switch the live-spots map layer on right away |
| `?world=1` | switch the "other WWFF areas worldwide" map layer on right away |
| `?embed=1` | hide the app chrome for an iframe |
| `?admin=1` | show the admin screen (also: tap the logo five times) |

```html
<iframe src="https://diana-onff.github.io/?embed=1&prov=antwerpen&lang=en&spots=1"
        width="100%" height="600" style="border:0" loading="lazy"></iframe>
```

Full parameter reference and a live example:
[docs/USER_GUIDE.md §5](docs/USER_GUIDE.md#5-embedding-diana-on-another-page).

**Two external, third-party sources**, each with a visible fallback if it's
unreachable rather than a silent gap: live spots and the agenda come from
`spots.wwff.co`, and the heatmap from a published ONFF Google Sheet, falling
back to `data/onff-activity.json` when that sheet can't be reached. Both are
plain cross-origin reads — confirmed working, no proxy needed for reading.
*Writing* (self-spotting, announcing) is the part that needs the Worker
above, because that's the part that needs the API key. Full detail in
[docs/ARCHITECTURE.md §2](docs/ARCHITECTURE.md#2-where-the-apps-own-data-comes-from).

---

## Publishing a new ONFF release

Two equivalent ways to do this — a plain upload on github.com, or Diana's own
in-app Admin panel — both ending at the same pull request, with a diff report
and a preview link to look at before you merge. Merging **is** publishing;
closing (or reverting an already-merged one) discards it. An area that has
disappeared from a release is not an error but real information — ONFF does
retire references — which is why it's always shown in the report, never
applied silently.

The full walkthrough, including the Admin panel's step-by-step upload flow,
is [docs/ADMIN.md §1](docs/ADMIN.md#1-publishing-a-new-onff-release).

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
  [docs/ADMIN.md](docs/ADMIN.md#31-a-reference-with-no-boundary).
