# Developer guide

How to get the repository running on your own machine, how the three GitHub
Actions workflows fit together, and how `data/*.json` actually gets made —
both the automatic way and the manual one.

This is the *build-time* half of Diana. For what happens at *runtime* (the
app itself, its data sources, its APIs) see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 1. Repository layout

```
diana/
├─ source/            empty on purpose: the KMZ files live in the private repo diana-source
├─ build/             KMZ → GeoJSON conversion, and the other build scripts  ← build-time
│  ├─ kmz2geojson.py  the conversion, one country per run
│  ├─ conditions.py   fetches the space weather numbers (conditions.yml)
│  ├─ radiozones.py   builds web/geo/radio-zones.json by hand, see MAINTENANCE.md §7
│  ├─ paginabasis.sh  the site's base URL, shared by the workflows
│  ├─ requirements.txt
│  ├─ site.sh         assembles the publishable folder (excludes source/)
│  └─ tests/          browser and build tests, see build/tests/README.md
├─ data/              the output — what the app actually loads
│  ├─ countries.json       the manifest: which countries have boundaries, and which files
│  │                       each is made of. Merged per build, never rewritten. Without it
│  │                       the app knows of no country but Belgium
│  ├─ zones/               one set per country, named after the programme in lower case
│  │  ├─ onff.geojson         the boundaries
│  │  ├─ onff-points.geojson  references with no boundary, as Points
│  │  ├─ onff-activity.json   QSO count + last activation per reference
│  │  ├─ onff-index.json      lightweight index, no geometry
│  │  └─ dlff.geojson … the same again for every other country
│  ├─ wwff-programs.json    every WWFF programme worldwide → its country (for the spots filter)
│  ├─ wwff-world.geojson    every active WWFF reference worldwide, as bare points (the blue
│  │                        dots); the app hides the ones of the country it has loaded
│  ├─ wwff-activity.json    QSO count of every WWFF reference worldwide (0 = ATNO)
│  ├─ sites/<prog>.json     the directory's website link per reference, for "More info"
│  ├─ meta.json
│  └─ onff*.json/geojson    the same Belgian files under their pre-manifest names, at the top
│                           level. No longer written by the build; a fallback for an old
│                           service worker, and safe to delete once nobody is on one
├─ overrides.json     manual name corrections, keyed by reference number
├─ web/               the web application itself                  ← runtime
│  ├─ index.html      the markup, and the <script> tags in the order they must run
│  ├─ css/app.css     every style, one file (see below)
│  ├─ js/             the logic, one file per screen or concern — see below
│  ├─ geo/            radio-zones.json (CQ/ITU zones, ITU regions) and its NOTICE.txt
│  ├─ kmz-guide.pdf   the KMZ format guide for coordinators
│  ├─ manifest.webmanifest
│  ├─ sw.js           service worker (offline cache)
│  └─ vendor/         MapLibre GL JS, vendored locally (not a CDN)
├─ worker/            the Cloudflare Worker in front of WWFF Spotline (SPOTLINE.md)
├─ docs/              this documentation set
└─ .github/workflows/
   ├─ build-data.yml  the conversion: on a pull request, on request from the Admin panel, nightly
   ├─ pages.yml       publishes to GitHub Pages (with PR previews)
   └─ conditions.yml  space weather for the Conditions tab, twice an hour
```

The split that matters: **`build/` runs on a GitHub-hosted runner and never
reaches a visitor's browser.** `web/` is the only thing a user ever loads.
Nothing in `build/` is shipped as part of the site.

### `web/css/app.css` — one file, already sectioned

Still a single file: at under 450 lines it does not carry the weight `app.js`
did, and splitting it up would trade "everything is in one place" for "which
of five files is `.btn` in" without solving a real problem. It already has
section comments (`/* ---------- topbar ---------- */` and so on) marking
each screen's styles, so if it ever does grow past this, the cut lines are
already there. It moved into its own folder mainly so it sits next to `js/`
instead of loose in `web/` — the one thing that changed on the move was the
splash screen's `url("start.jpg")`, which needed `../` in front of it.

### `web/js/` — one file per screen, and why the order is not negotiable

These were a single `app.js` of nearly 5800 lines until it was cut apart along
the section headings that were already in it. Files added since (the wizard,
the conditions, the privacy page and others) follow the same pattern. The
table is in `<script>` order:

| File | What lives in it |
|---|---|
| `core.js` | `$()`, `APP_VERSION`, the build stamp, the splash screen, `remember()`/`recall()`, `escH()` |
| `radiogeo.js` | locator ↔ coordinates, distance and bearing, used by many screens |
| `i18n-strings.js` | the `STR` tables: eight languages, and by far the biggest file |
| `i18n.js` | picking a language, `t()`, `applyLang()`, `rerender()` |
| `map-data.js` | the manifest, the zone/index/activity state and everything that loads it, `selectedRefInfo()` |
| `map.js` | the MapLibre map, all layers, selection, the detail panel (boundary, point, blue dot), search, the popovers |
| `spots.js` | the Spotline feed, filters, the list, arcs, the spot detail, the agenda tab |
| `install.js` | the "put Diana on your device" flow |
| `gestures.js` | swipe-down-to-close on the bottom panels |
| `nav.js` | the bottom bar and switching between full screens |
| `settings.js` | Settings, the locator field, the country, and where the map opens |
| `privacy.js` | the welcome screen (location, anonymous statistics) and the Privacy page |
| `releases.js` | "What's new": the release notes, in Dutch and English |
| `admin.js` | the whole admin screen: GitHub API, upload, pull request, cleanup, embed code |
| `self-spot.js` | spotting yourself through the Worker, with the old form post as fallback |
| `agenda.js` | announcing an activation, and your own PIN list |
| `rules.js` | the band plan and the Rules screen |
| `rules-text.js` | the WWFF rule texts shown on the Rules screen |
| `nearby.js` | Field info, Areas tab: the closest references and their activation history |
| `nearinfo.js` | Field info, Location tab: locator, zones, region, position details |
| `conditions.js` | Field info, Conditions tab: Kp, SFI, band bars, storm rule |
| `offline.js` | service worker registration, the update flow |
| `geo.js` | point-in-polygon, `bestFix()`/`locate()`, the status card, the locate button |
| `wizard.js` | the setup wizard and the tour after the first start |

They are **ordinary scripts, not ES modules**, so they share one global scope
exactly as the single file did — what `core.js` declares is what `spots.js`
sees, with no imports or exports anywhere. `defer` keeps them in document
order and runs them after the page is parsed, so the order of the `<script>`
tags in `index.html` *is* the order of the old file.

That has three consequences worth knowing before you touch anything here:

- **Append at the end of a file; do not move a line between files** without
  checking whether it runs at load time. A `function` declaration is hoisted
  only within its own file now: a handler assigned at load time in one file
  to a function declared in a later file is `undefined` at that moment. Wrap
  it in an arrow (`() => later()`) so the name is looked up when it runs.
- **A new file has to be added in three places**: a `<script>` tag in
  `index.html`, an entry in `SHELL_FILES` in `sw.js`, and this table. Forget
  the second and the app works online and is broken offline, which you find
  out in the woods with no signal.
- **The build stamp** (`'__DIANA_BUILD__'` in `core.js`) is replaced by
  `build/site.sh`, which searches every file under `js/` and stops the build
  unless it finds it exactly once.

---

## 2. Cloning and running locally

```bash
git clone https://github.com/<owner>/<repo>.git
cd <repo>
python3 -m http.server 8000
# open http://localhost:8000/web/
```

Start the server **from the repository root**, not from `web/`. The app
requests `./data/countries.json` (published layout) and falls back to
`../data/countries.json` (repository layout); starting the server inside
`web/` puts `data/` outside the server root and both requests 404.

No build step, no `npm install`, no bundler. `web/index.html` is a single
static file; MapLibre GL JS is vendored under `web/vendor/` so the app has no
external runtime dependency and genuinely works offline.

To also regenerate the data locally, see §4.

---

## 3. The three GitHub Actions workflows

### `build-data.yml` — convert KMZ to GeoJSON

| Trigger | What happens |
|---|---|
| Pull request touching `source/**.kmz`, `overrides.json`, or `build/**` | Runs `kmz2geojson.py` per country, commits the regenerated data to the PR branch, and posts (or updates) one PR comment with a diff report |
| `workflow_dispatch` with a `branch` input (the Admin panel) | Builds with the KMZ from `incoming/<country>/` in the private repo and puts the result on that branch; `main` is untouched. The panel then opens the pull request and puts the diff report in its description |
| `schedule`: every night at **02:17 UTC** (off the full hour, when GitHub starts scheduled runs late) | Runs the same conversion, for every country, against the newest KMZ already in `source/<country>/` of the private repo, so the only thing that can actually change is whatever the WWFF directory itself changed since yesterday (new/renamed/retired references, updated QSO counts) — never a boundary, since those only come from a KMZ. The script runs with `--strict`, so an unreachable **or truncated** directory aborts the build instead of degrading; a **"Check the output"** step then re-checks the *content* (zone count, and how many directory references were actually read) rather than merely whether the files are non-empty. Only past both does it commit — **directly to `main`**, no pull request — retrying the push up to three times with a rebase if `main` moved meanwhile. On failure, cancellation, or a run skipped for a missing KMZ, an **"Open an issue or add to it"** step opens a GitHub issue (or comments on the existing one) labelled `diana-nachtelijke-build` |
| `workflow_dispatch` without a branch | Same as the nightly run, on demand from the Actions tab |

The nightly run is what makes brand-new WWFF references (and status/QSO
changes) show up without anyone touching the repository, and — unlike a KMZ
upload — it is allowed to publish by itself, since the worst it can do is
place or rename a reference, never draw a wrong boundary. A failed night
raises a GitHub issue rather than failing silently — as does a night that
quietly did nothing at all, because "no KMZ in `source/`" would otherwise look
identical to "nothing to refresh" forever. See
[ADMIN.md §3](ADMIN.md#3-where-the-data-comes-from--and-what-you-actually-have-to-do)
for what that looks like and how GitHub's own notifications get it to you.

The diff report looks like:

> **945 zones** (was 932, +13) · **15 new** · **2 removed** · **7 boundary changed**

with the actual lists collapsed under a `<details>` toggle. A removed zone is
real information — programmes do retire reference numbers — so it is always
surfaced, never silently applied.

The comment is marker-based (`<!-- diana-preview -->`-style), so pushing a
second commit to the same PR *updates* the existing comment instead of
piling up new ones.

### `pages.yml` — publish to GitHub Pages

Deliberately **not** the standard `actions/deploy-pages` action, because that
action has no concept of a pull-request preview — and without a preview,
merging a new KMZ is a leap of faith.

| Trigger | Result |
|---|---|
| push to `main`/`master` | `build/site.sh` output replaces the live site at the repo root of the `gh-pages` branch |
| pull request opened/updated | published to `.../preview/pr-<number>/`, with the link posted as a PR comment |
| pull request closed | that preview folder is deleted |
| `workflow_run` after `build-data.yml` succeeds | publishes whatever that run committed. **This trigger is load-bearing:** a push made with the default `GITHUB_TOKEN` does not start new workflows, so without it the nightly data commit would land on `main` and never be published, and a PR preview would show the dataset from *before* the build. It matches on the workflow's `name:` as a literal string, and GitHub says nothing when it does not match — it read `"Build ONFF data"` for a while after that workflow had been renamed `Build map data`, and silently never fired. Rename one, change the other |
| `workflow_dispatch` | same as a push — mainly useful to bootstrap `gh-pages` the very first time, before it exists |

Requires **Settings → Actions → General → Workflow permissions → "Read and
write permissions"**, set *before* the first run — otherwise the push to
`gh-pages` fails with a 403. Full first-time setup and troubleshooting (a
missing `gh-pages` branch, a `.github/` folder silently dropped by a
drag-and-drop upload, etc.) is in [DEPLOY.md](../DEPLOY.md).

`build/site.sh` assembles `_site/` from `web/` plus the data the app loads —
`data/countries.json`, the whole of `data/zones/`, and the files shared by every
country — and **excludes `source/`**. The KMZ never becomes part of the
published site; it lives in the private repo, and the workflow fetches it
with `SOURCE_TOKEN`. The script also replaces the build stamp and the service
worker's `VERSION`, so every publication is a new version for the app.

This script is a place to be careful. It once listed the Belgium-only filenames
from before the manifest existed, and kept listing them after the build had
moved to `data/zones/`. Nothing failed: Belgium went on working through the
app's own pre-manifest fallback, while every other country was built, merged and
live on `main` and still did not exist as far as the published site was
concerned. Before publishing, the script now checks the output against
`data/countries.json` itself and stops if a file the manifest names is not
there. `build/tests/test_site.py` runs the whole thing end to end — it is the
only test that looks at what is actually published rather than at `data/`.

```
pull request (new KMZ)
        │
        ▼
 build-data.yml ── regenerates data/*.json, comments the diff
        │
        ▼
   pages.yml ── publishes a PR preview at /preview/pr-<n>/
        │
   (human looks at the preview)
        │
      merge
        │
        ▼
   pages.yml ── publishes to the live site
```

From the Admin panel the start is different (the KMZ goes to `incoming/` in
the private repo and the panel starts `build-data.yml` with a branch name),
but from the pull request onwards it is the same picture. See
[ADMIN.md §2](ADMIN.md#2-the-in-app-admin-panel).

### `conditions.yml`: space weather

Twice an hour (`7,37 * * * *`) and on request, `build/conditions.py` fetches
Kp, solar flux, A index and sunspot number from NOAA SWPC and writes
`conditions.json` to a branch of its own, `conditions`, force-pushed so it
always holds one commit. The app reads it from
`raw.githubusercontent.com/<owner>/<repo>/conditions/conditions.json`. Not on
`main` on purpose: every commit there republishes the site and would give the
app a new version 48 times a day. A source that is down keeps its previous
value with its own timestamp; the app warns once the numbers are older than
8 hours. GitHub starts scheduled runs on a best-effort basis, so gaps of a few
hours happen.

---

## 4. Generating `data/*.json` manually

Same script the Action runs, for when you want to check a KMZ before opening
a pull request, or you're iterating on `overrides.json`.

```bash
pip install -r build/requirements.txt --break-system-packages
python build/kmz2geojson.py --kmz "ONFF_20260101.kmz" --program ONFF
```

Takes roughly half a minute for the full Belgian dataset.

| Option | Default | Purpose |
|---|---|---|
| `--kmz` | — | path to the source KMZ (required) |
| `--tolerance` | `0.00005` | polygon simplification, in degrees (≈ 5 m — below typical GPS accuracy) |
| `--decimals` | `5` | coordinate rounding (5 decimals ≈ 1 m) |
| `--out` | `data` | output folder |
| `--overrides` | `overrides.json` | manual name-correction file |
| `--report` | `report.md` | where the diff report is written |
| `--refs-csv` | `https://wwff.co/wwff-data/wwff_directory.csv` | the WWFF directory (URL **or** local path) — the list of which references exist |
| `--program` | `ONFF` | the WWFF programme this KMZ belongs to, one per run. It decides which references are read from the directory, how they are recognised in the KMZ, and the output names (`data/zones/<prog>.*`) |
| `--no-refs` | off | skip the directory entirely — for builds with no network |
| `--strict` | off | exit non-zero if the directory is unreachable **or looks truncated** (fewer rows than expected, or a sharp drop against the previous build) instead of continuing with less data. The nightly run uses this: nothing written beats bad data committed unattended |

The directory is fetched fresh on every build — it is regenerated daily, so
pinning a copy would go stale. Reading is deliberately tolerant: columns are
matched by name (never by position, so a new column in the middle is harmless),
a header row below a title row is found, and a position falls back from
`latitude`/`longitude` to the `iaruLocator` square. If the directory cannot be
read at all, the build **continues** with a warning rather than failing — a
moved file must never block a data release; you just get manual points from
`overrides.json` only that run. In CI the URL can be overridden without touching
code, via a repository variable `ONFF_REFS_CSV`.

### What the script actually does

1. Parses the KML inside the KMZ with `lxml`.
2. Finds the reference number of each placemark. In the ONFF export it is in
   the **folder name**, not a data field (folders named `ONFF-nnnn <name>`);
   other exports carry it elsewhere, and the script looks in names, folders
   and attributes. A file whose references belong to another programme than
   `--program` is refused. See
   [ARCHITECTURE.md](ARCHITECTURE.md#21-the-onff-kmz-one-layer-further-back).
3. Merges every polygon under one reference number into a single
   `MultiPolygon` with `shapely.ops.unary_union` — some references (e.g.
   ONFF-0329) consist of dozens of disconnected parcels.
4. Simplifies geometry (`simplify(tolerance, preserve_topology=True)`) and
   computes geodesic area with `pyproj.Geod`.
5. Picks the best of the (often typo'd, duplicated, or filename-derived)
   candidate names per reference, then applies `overrides.json` on top,
   keyed by reference number — **never by name**, so a correction survives
   the next release even if the source spelling changes again.
6. Writes `data/zones/<prog>.geojson` (full geometry),
   `data/zones/<prog>-index.json` (the same list without geometry, for
   reports and tooling), and `data/meta.json` (provenance: source file,
   release date, settings used).
7. Fetches the WWFF directory (`--refs-csv`), keeps the rows for `--program`,
   drops everything whose `status` is not `active`, and joins it to the polygons
   on the reference number. References with no polygon are written to
   `data/zones/<prog>-points.geojson` as Points — positioned from `overrides.json`
   (`"point": [lon, lat]`, always wins), then the directory's coordinates, then
   its IARU locator. References with none of those are reported, not invented.
   The QSO count and last-activation date of every reference go to
   `data/zones/<program>-activity.json`, which is what Field info and the area
   panel show. Every output of a run is per country and carries the
   programme in its name; `--program` decides which, one country per run. The
   run then merges itself into `data/countries.json` rather than rewriting it —
   see [ARCHITECTURE.md §2.1b](ARCHITECTURE.md#21b-one-country-per-file-and-a-manifest-over-them). Separately — over the **whole** directory, ignoring
   `--program` — every programme code is tallied against its most common
   `country` value and written to `data/wwff-programs.json`; and every active
   reference worldwide is written to `data/wwff-world.geojson` as a bare
   `{ref, name}` Point, the loaded country's own included (the app hides
   those, since it shows their boundaries). Over the whole directory too:
   `data/wwff-activity.json` (QSO count per reference, 0 = ATNO) and
   `data/sites/<prog>.json` (website links for "More info"). These feed the
   spots screen's country filter and ATNO mark, the "other WWFF areas" map
   layer (on by default, see
   [ARCHITECTURE.md §2.1.3](ARCHITECTURE.md#213-other-wwff-areas-worldwide)),
   and the panel of a blue dot.
8. Diffs the new output against the previous release and writes
   `report.md` — new zones, removed zones, boundary changes, and how many
   boundary-less references were placed or left unplaced.

### Correcting a name

Edit `overrides.json`, keyed by reference number, with a `_why` note so the
reason is still legible years later:

```json
"ONFF-0599": {
  "name": "Carrière de l'Alouette",
  "_why": "KMZ has \"Carriere de 'Alouttel\" — two typos"
}
```

A pull request against this file alone re-triggers `build-data.yml`, exactly
like a new KMZ would.

---

## 5. Publishing a new release for a country (short version)

The full walkthrough is in [ADMIN.md §1](ADMIN.md#1-publishing-a-new-release-for-a-country).
In short: a coordinator e-mails the KMZ to wwffmembers@gmail.com → a team
member uploads it in Diana's Admin panel → the file waits in `incoming/` of
the private repo, `build-data.yml` converts it on a branch, the panel opens
a pull request with the diff report, `pages.yml` publishes a preview → look
at the preview → **Publish** (merge) to go live, or **Reject**. No local
checkout is needed.

## 6. Tests

`build/tests/` holds Playwright browser tests and build tests, one script per
feature, each runnable on its own (`python3 build/tests/test_<name>.py`
against a local server on port 8011). [build/tests/README.md](../build/tests/README.md)
lists them, one line each. Known since v2.2.1: one check each in
`test_new.py` ("points really do render"), `test_final.py` ("button in the
panel fully usable again") and `test_worldpoints.py` ("on your own country,
only its points are left") fails on a detail that changed after the test was
written; the app itself is fine there.
