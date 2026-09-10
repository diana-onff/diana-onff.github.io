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
| `test_heat.py` | heatmap from the sheet and the fallback to the WWFF directory |
| `test_worldpoints.py` | worldwide WWFF areas: on by default, clustering, filtering to one country, layer off/on, and that an embed leaves it off unless `?world=1` |
| `test_spotsalways.py` | that the map opens unasked where you are standing, that spots cannot be switched off, and that only the lines leading to them are toggleable (and stay saved) |
| `test_directory.py` | the build step itself (no browser): impossible coordinates, leaks between the layers, and whether `--strict` really overwrites nothing when the directory is unreachable or truncated |
| `test_spotsfilter.py` | spots filter: worldwide by default, ONFF-only, one country via `wwff-programs.json`, and that the quick filter and Settings stay in sync and survive a reload |
| `test_spot.py` | reporting a spot yourself: reference checking, check-then-send, and every answer the Worker can give (201, 400, 409, 429, 503, unreachable) |
| `test_agenda.py` | announcing an activation: the date rules, local time going out as UTC, the PIN kept on the device, and all three ways into the screen |
| `test_visual.py` | that the screens actually look right, by taking and inspecting screenshots |
| `test_split.py` | that `web/js/*.js` stays loadable: every file has a `<script>` tag, every file is in `SHELL_FILES`, nothing throws at load, and the files can still see each other's declarations |
| `test_gps_accuracy.py` | "am I inside this zone?" treats the GPS's reported accuracy the same way on both sides of a boundary — just outside by less than the accuracy is "too close to call", exactly like just inside already was |

The style-switch test in `test_swipe.py` is the most important one: that is where
the bug lived that made all our own layers disappear one by one after
`map.setStyle()`.

`test_split.py` is the one to run after touching anything under `web/js/`. Those
files are plain scripts sharing one global scope, in a fixed order — nothing in
the language enforces that, so this test does. See `docs/DEVELOPER.md`.
