# Browser tests

Playwright tests that run the app in a real (headless) browser, with every
external host intercepted — so no network is needed for them.

```bash
pip install playwright --break-system-packages
python3 -m http.server 8011          # from the repo root
python3 build/tests/test_new.py      # etc.
```

| File | What it guards |
|---|---|
| `test_new.py` | points without a boundary: loading, drawing, panel, search, layer button, and that the GPS test skips them |
| `test_more.py` | language choice (English by default, "follow the browser", staying saved) and the install flow per platform |
| `test_swipe.py` | swiping down to close panels, and whether all our own layers survive six style switches |
| `test_final.py` | that the install bar gives way to an open panel |
| `test_splash.py` | splash screen, version number, the 16 dots, and whether the bottom bar is aligned |
| `test_nearby.py` | the Nearby screen: what it does without a position, distances from a locator and from a GPS fix, the three orderings, tapping through to the map — and above all that its QSO counts are the WWFF directory's real ones, with nothing asked of Google Sheets |
| `test_worldpoints.py` | worldwide WWFF areas: on by default, clustering, that the points follow the one country setting rather than a second dropdown of their own, layer off/on, and that an embed leaves it off unless `?world=1` |
| `test_country.py` | the one country setting: that your callsign decides it until you pick one, that changing it swaps the boundaries while the app is running (checked against what MapLibre is really holding, not only the globals), that the count under the map and Settings follow, that a selection from the country that just left is let go, that a country without boundaries says so and keeps its points, and that choosing a country no longer drags the spots filter along with it |
| `test_spotsalways.py` | that the map opens unasked where you are standing, that spots cannot be switched off, and that only the lines leading to them are toggleable (and stay saved) |
| `test_adminupload.py` | where the admin panel writes in the source repo: that a country must be chosen before anything can be sent, that the upload lands in that country's folder, that publishing moves it to `source/<country>/`, and that a file from before the folders existed still moves correctly. Also the check before the upload: a file belonging to another country closes the send button, a matching one opens it, and a file that cannot be read blocks nothing. GitHub is replaced by a recorder, so no token and no network |
| `test_kmlshapes.py` | the three layouts real WWFF releases come in (no browser): a folder per province (Belgium), one folder for everything (Germany), and a `<Folder>` at the root with no grouping at all (Denmark) — and that a file for the wrong country, a file whose areas carry no number, and a file with no areas are each refused with a reason instead of writing an empty country |
| `test_countries.py` | the per-country build (no browser): that a country lands in its own files, that the manifest is merged rather than rewritten, that building one country leaves another's files untouched byte for byte, that the country just built stops appearing as a bare point, and that a country built earlier still does appear as one — so a second boundaried country never goes invisible to everyone else |
| `test_site.py` | what actually gets published (no browser): builds two countries for real, runs `build/site.sh` over them, and demands that everything `data/countries.json` names is in the output — checked against the manifest, not against a list of filenames. Also that `source/` and every KMZ stay out, that the version stamp and the service worker's cache name are filled in, that a manifest promising a file that is not there stops the publication, and that both a data set older than the manifest and one that has dropped the old filenames entirely still publish. This is the test that was missing: every other file here reads `data/` directly, so nobody ever looked at what `site.sh` produced |
| `test_multicountry.py` | the app with more than one country on board: loading from the manifest, pooling two countries' boundaries, an invented second country standing in for the ones that have no data yet, the fallback to the old Belgian filenames when there is no manifest, and one country failing to load without taking the other down |
| `test_directory.py` | the build step itself (no browser): impossible coordinates, leaks between the layers, and whether `--strict` really overwrites nothing when the directory is unreachable or truncated |
| `test_spotsfilter.py` | spots filter: worldwide by default, ONFF-only, that the quick filter and Settings stay in sync and survive a reload, and that Settings' country picker only ever changes the boundaries — never the spots filter, which is its own choice with its own storage key |
| `test_spot.py` | reporting a spot yourself: reference checking, check-then-send, and every answer the Worker can give (201, 400, 409, 429, 503, unreachable) |
| `test_agenda.py` | announcing an activation: the date rules, local time going out as UTC, the PIN kept on the device, and all three ways into the screen |
| `test_visual.py` | that the screens actually look right, by taking and inspecting screenshots |
| `test_split.py` | that `web/js/*.js` stays loadable: every file has a `<script>` tag, every file is in `SHELL_FILES`, nothing throws at load, and the files can still see each other's declarations |
| `test_gps_watch.py` | how a position is obtained: that a coarse first fix does not get to answer, that the sharp one does, that the watch stays open after answering and a sharper fix which disagrees overturns the verdict (the indoor-wifi case), that ordinary jitter does not, that an accuracy the browser will not state is never read as perfect, that every verdict states the accuracy and draws a ring at that radius, that the readings are judged against each other rather than on the accuracy each claims for itself (a phone scattering sixty metres while reporting ±5 m is caught, a single wild reading is outvoted, a coarse reading does not inflate a sharp one's margin, and walking is not mistaken for scatter), that a cached fix is refused (`maximumAge: 0`), and that nothing falls back to asking once with `getCurrentPosition` |
| `test_gps_accuracy.py` | "am I inside this zone?" treats the GPS's reported accuracy the same way on both sides of a boundary — just outside by less than the accuracy is "too close to call", exactly like just inside already was |
| `test_admin_poll.py` | the admin panel's pull-request card keeps checking on its own: that a push with no Actions run listed yet is not mistaken for "nothing to wait for" (the gap right after a push), that the ordinary poll still takes over once a run appears and stops once one is done, and that coming back to the app after being away — the tab was backgrounded, its timers suspended — is itself treated as a refresh, for the pull request and for the waiting-room cleanup list underneath it |

The style-switch test in `test_swipe.py` is the most important one: that is where
the bug lived that made all our own layers disappear one by one after
`map.setStyle()`.

`test_split.py` is the one to run after touching anything under `web/js/`. Those
files are plain scripts sharing one global scope, in a fixed order — nothing in
the language enforces that, so this test does. See `docs/DEVELOPER.md`.
