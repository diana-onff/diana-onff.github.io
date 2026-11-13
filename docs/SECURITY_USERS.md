# Diana for security-minded users

What Diana loads, from where, and why. Written for people who run a script
blocker, a strict content blocker or their own firewall rules, and want to
allow exactly what Diana needs and nothing more.

## If Diana stays on the start screen

Diana is a web app: without JavaScript nothing in it runs. When a blocker
stops every script, the start screen stays up. Since v2.2.11 a box appears on
it after 20 seconds saying so (that box needs no script itself; 10 seconds
in v2.2.11, which on a very weak connection could show it for nothing on a
first visit). If only the map library is blocked, Diana's own scripts notice
and show the box at once.

1. Allow scripts for **diana-onff.github.io** only. Not `github.io` and not
   `github.com`: Diana needs neither.
2. **Reload the page.** Press **F5** or **Ctrl+R** (Mac: **Cmd+R**). On a phone,
   pull the page down or tap the browser's reload button. Most blockers only
   apply a new rule to a page that is loaded again: without reloading, the old
   block stays in place, even after you clicked "Trust".
3. Still stuck? A second extension may block as well (an ad blocker, a privacy
   extension). Switch them off one at a time for this site to find which one.
4. Diana starts but the map stays empty? See "Map worker" below.

## Scripts

Every script Diana needs comes from diana-onff.github.io itself:

| File | What it is |
|---|---|
| `vendor/maplibre-gl.js` | MapLibre GL JS 4.7.1, the map library. A copy on Diana's own site, not loaded from a CDN |
| `js/*.js` | Diana's own code, 24 files, loaded as ordinary script files |
| `sw.js` | the service worker that keeps Diana working offline |

There are no inline scripts in the page, and Diana's own code uses no `eval`
or `new Function`.

One exception, and only with your consent: if you answer "Yes, I'll help" to
anonymous statistics (welcome screen, or Settings → Privacy), Diana adds the
counting script of **Umami** from `cloud.umami.is`. Answer no, or block that
domain, and Diana works exactly the same.

## Map worker

MapLibre draws the map in a background worker that it starts from a `blob:`
address made by the page itself. A blocker or policy that refuses `blob:`
workers (`worker-src`) lets Diana start, but the map stays blank. Allow
`blob:` workers for diana-onff.github.io.

## Network requests (no scripts)

What Diana fetches as data, apart from its own files:

| Host | Why | When |
|---|---|---|
| `tiles.openfreemap.org` | map style, map tiles and the fonts of the map labels (OpenStreetMap data) | always, for the map |
| `spots.wwff.co` | live spots and the agenda; your own spot or announcement goes to Spotline | Spots and Agenda screens |
| `diana-spotline.diana-onff.workers.dev` | the Diana relay that passes your spot or announcement on to Spotline | only when you send a spot or announcement |
| `raw.githubusercontent.com` | space weather numbers for Field info → Conditions | Conditions tab |
| `cloud.umami.is` | anonymous visit count | only if you said yes to statistics |
| `api.github.com` | publishing new area files | only the Admin screen, with your own token |

Links you tap yourself (the WWFF rules PDF and log search on `wwff.co`, a
reserve's website, GitHub) open in a new tab and load nothing in Diana itself.

Your position is never sent anywhere. See the Privacy screen in the app
(Settings → Privacy) for the full statement.
