# Diana

**Diana Fauna & Flora** is a free map app for WWFF, World Wide Flora & Fauna:
every WWFF reference worldwide, the nature reserves of a country with their
boundaries, and the live spots and announced activations from WWFF Spotline,
with direction and distance from where you are standing. It is a web app
(PWA): it runs in the browser on phone, tablet and computer, can be installed
like an app, works offline with the last data it loaded, and can be embedded
in another website.

Live at **https://diana-onff.github.io/**. A volunteer project, started in
Belgium (ONFF), for every WWFF programme.

Boundaries are loaded today for **Belgium (ONFF), the Netherlands (PAFF),
Germany (DLFF) and Denmark (OZFF)**; every other WWFF reference in the world is
on the map as a point. More countries follow as their area files come in, see
[Adding or updating a country](#adding-or-updating-a-country).

Software: PolyForm Noncommercial 1.0.0 (personal, hobby and club use free,
commercial use not). Data: not free. Both in [LICENSE](LICENSE).

This is the **public** repository: the app, the converted data, the
workflows and the Worker's code. The source KMZ files live in a separate,
**private** repository (`diana-source`), see [source/README.md](source/README.md)
and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for why.

## Documentation

| Document | Who for | Contents |
|---|---|---|
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | users | platforms, installing, the welcome screen and setup wizard, every screen explained, embedding, and the **limitations** (everything stays on the device, nothing syncs) |
| [docs/ADMIN.md](docs/ADMIN.md) | the Diana team | how a country's area file reaches Diana, the in-app Admin panel, the nightly update, troubleshooting |
| [docs/MAINTENANCE.md](docs/MAINTENANCE.md) | whoever keeps Diana running | every credential, the GitHub security settings, adding an administrator, the kill switch, what goes stale |
| [docs/INSTALL.md](docs/INSTALL.md) | whoever sets Diana up somewhere new | the whole thing from zero: organisation, repositories, settings, the Worker, with a checkpoint after every step |
| [docs/DEVELOPER.md](docs/DEVELOPER.md) | developers | repository layout, the scripts in `web/js/`, the three workflows, building the data by hand |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | developers and administrators | where every piece of data comes from, what is stored where, offline behaviour |
| [docs/SPOTLINE.md](docs/SPOTLINE.md) | developers and administrators | the Cloudflare Worker in front of WWFF Spotline, and why it has to exist |
| [worker/README.md](worker/README.md) | whoever deploys the Worker | setting it up, testing it, operating it |
| [build/tests/README.md](build/tests/README.md) | developers | the browser and build tests, one line per test |
| [DEPLOY.md](DEPLOY.md) | anyone | the short orientation: what runs where |
| [web/kmz-guide.pdf](https://diana-onff.github.io/kmz-guide.pdf) | regional coordinators | how to format a country's KMZ, and where to send it |
| [docs/Diana_FaunaFlora_Presentation.pptx](docs/Diana_FaunaFlora_Presentation.pptx) | WWFF programmes and coordinators | the introduction presentation (PowerPoint) |

[PLAN-spotline.md](PLAN-spotline.md) is the original step plan for the
Spotline integration, kept for its history; [docs/SPOTLINE.md](docs/SPOTLINE.md)
describes how it works now.

---

## What is in this repo

```
web/              the web application itself                                  ← runtime
  kmz-guide.pdf   the KMZ format guide for coordinators, published with the site
data/             the converted data the app fetches
build/            the conversion from KMZ to the data files, and the tests     ← build time
overrides.json    manual corrections that survive every new release
worker/           the Cloudflare Worker in front of WWFF Spotline, see docs/SPOTLINE.md
docs/             the documentation set, see the table above
source/           empty on purpose: the real KMZ files live in diana-source
.github/          the three workflows: build the data, publish the site, space weather
_site/            what gets published (made by build/site.sh, not in git)
```

Two halves that do not mix: `build/` runs on a GitHub runner and never reaches
a user; `web/` is what people open.

## The app in one paragraph

The bottom bar has **Map**, **Spots** (on air now, and the agenda), **Spot**
(spot yourself), **Agenda** (announce an activation), **Field info** (nearby
references, your position in radio terms, band conditions), **Rules** (WWFF
rules and the band plan) and **Settings**. A first start shows a welcome
screen (location and anonymous statistics) and a short setup wizard with a
tour. Every reference on the map can be tapped, a blue dot from another
country included, and every panel can spot you or announce an activation
there. Eight languages: English, Dutch, French, German, Danish, Italian,
Spanish and Portuguese. Every screen is explained in
[docs/USER_GUIDE.md](docs/USER_GUIDE.md).

Reading spots and the agenda goes straight to `spots.wwff.co`. Sending a spot
or an announcement goes through a small Cloudflare Worker that holds WWFF's
API key, because a web app without a server cannot keep a key secret. See
[docs/SPOTLINE.md](docs/SPOTLINE.md).

**Privacy:** settings stay in the browser of the device, the GPS position
never leaves it, there are no cookies, and anonymous visit counts (Umami) are
only loaded after an explicit yes. Details on the app's own Privacy page and
in [docs/ARCHITECTURE.md §3](docs/ARCHITECTURE.md#3-whats-stored-where-and-what-never-leaves-the-device).

## Running the app locally

A static server is enough; the app has no backend.

```bash
python3 -m http.server 8000        # from the repo root, not from web/
# open http://localhost:8000/web/
```

Starting from inside `web/` does not work: the app fetches `../data/countries.json`,
and that falls outside the server root.

**URL parameters** (also for embedding):

| Parameter | What |
|---|---|
| `?lang=nl\|fr\|en\|de\|da\|it\|es\|pt` | force the language; without it the app is English unless another language was chosen in Settings |
| `?ref=ONFF-0104` | zoom straight in on one area |
| `?prov=limburg` | zoom in on a region of the loaded country (a Belgian province, for instance) |
| `?spots=0` | hide the live spots, which are otherwise always on, also in an embed |
| `?world=1` | show the other WWFF references worldwide in an embed, where they are off by default |
| `?embed=1` | hide the app chrome for an iframe |
| `?admin=1` | show the Admin screen (also: tap the logo five times). Useless without a token, see docs/ADMIN.md |

```html
<iframe src="https://diana-onff.github.io/?embed=1&prov=antwerpen&lang=en"
        width="100%" height="600" style="border:0" loading="lazy"></iframe>
```

Full reference: [docs/USER_GUIDE.md §5](docs/USER_GUIDE.md#5-embedding-diana-on-another-page).

---

## Adding or updating a country

Regional coordinators do not upload themselves. They e-mail the official area
file (KMZ) of their programme to **wwffmembers@gmail.com**, formatted as in the
[KMZ format guide](https://diana-onff.github.io/kmz-guide.pdf). The Diana team
uploads it through the Admin panel, which opens a pull request with a diff
report and a preview of the map; merging that pull request **is** publishing.
An area that disappears from a release is shown in the report, never applied
silently. The full walkthrough is in [docs/ADMIN.md](docs/ADMIN.md).

## Correcting names

Area names in a KMZ can contain typos. The build picks the best spelling
automatically, but not always the right one. Correct those in
`overrides.json`, keyed on the reference number, never the name, with a `_why`
so that it is still clear years later:

```json
"ONFF-0599": {
  "name": "Carrière de l'Alouette",
  "_why": "KMZ writes \"Carriere de 'Alouttel\": two typos"
}
```

A pull request on this file makes the build run again. Building by hand:
[docs/DEVELOPER.md §4](docs/DEVELOPER.md#4-generating-datajson-manually).

## The data files

| File | What |
|---|---|
| `data/countries.json` | which countries Diana has boundaries for, and which files belong to each. The app reads this first |
| `data/zones/<prog>.geojson` | one MultiPolygon per reference of that country, with name, region, area and whatever attributes the KMZ has |
| `data/zones/<prog>-points.geojson` | references of that country that are in the WWFF directory but have no boundary in the KMZ, as points |
| `data/zones/<prog>-activity.json` | QSO count and last activation per reference of that country, from the WWFF directory |
| `data/zones/<prog>-index.json` | the same list without geometry, for reports and tooling |
| `data/wwff-world.geojson` | every active WWFF reference worldwide as a point (the blue dots) |
| `data/wwff-activity.json` | the QSO count of every WWFF reference worldwide (0 = never activated, ATNO) |
| `data/wwff-programs.json` | every WWFF programme and its country |
| `data/sites/<prog>.json` | the website link per reference, for "More info" |
| `data/meta.json` | provenance: which source file, which release, when it was built |

`<prog>` is the programme in lower case: `onff`, `paff`, `dlff`, `ozff`. Files
directly under `data/` with a country name (such as `data/onff.geojson`) are
leftovers from before the manifest, kept only as a fallback for an old service
worker and no longer updated.

Which references exist comes from the WWFF directory, refreshed every night;
the KMZ only says which ones have a boundary. Every reference appears once: a
polygon always wins over a point.
