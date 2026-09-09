# Spotline: sending spots from a page that has no server

Diana can send your own spots to WWFF. This document is about how, and about
the one problem that shapes everything else: WWFF issues a single API key per
application and asks that it be kept server-side, while Diana is a static page
on GitHub Pages and has no server at all.

Anything the page can read, every visitor can read. View source, open the
network tab, and the key is yours. There is no version of "hide it in the
JavaScript" that survives five minutes of attention.

## The shape of the answer

A **Cloudflare Worker** — about four hundred lines, in `worker/` — sits
between the app and Spotline. It is the only thing in the whole project that
ever sees the key. The app talks to the Worker; the Worker talks to WWFF.

```
  the app  ──POST /spot──▶  the Worker  ──POST /api/spots/add──▶  Spotline
 (public)                  (holds the key)        X-API-Key
```

The Worker's code is public and sits in the repository like everything else.
That is fine: the code is not the secret. The key lives only in Cloudflare, put
there once with `wrangler secret put`, readable afterwards by nothing and
nobody — not the dashboard, not wrangler, not a workflow.

**Forwarding is the least interesting thing it does.** Its value is in what it
refuses, and that list is in `worker/README.md` along with the reasoning behind
every number. The short version: unknown fields are dropped rather than passed
on, callsigns and frequencies and modes and references are checked before
anything leaves, one visitor cannot spend the shared budget, Diana as a whole
cannot either, and one KV key stops the entire service within seconds without a
deploy.

## Why reading spots does not go through it

The API WWFF issued has three endpoints — add a spot, store an agenda entry,
validate a reference — and **no endpoint for reading spots**. Diana reads them
from three static JSON files on `spots.wwff.co/static/` instead, as it always
has.

That is not a workaround waiting to be replaced. Those files need no key, so no
proxy sits in the path of something that happens every thirty seconds; they do
not count against the 100-per-minute budget, which is the budget we want to
keep for writing; and they cache, which is what lets the map work with the
aeroplane icon on. Even if a read endpoint appears one day, the static files
remain the better way in.

## What sending actually looks like

Two steps, and deliberately not automatic one after the other.

**Check** sends the spot with `"dryrun": true`. Spotline validates it and
stores nothing. You find out whether the reference is live, whether the
frequency makes sense to them, whether anything is missing — before anything is
public.

**Send** goes out only after a check came back accepted, with the same payload
minus the flag. Any edit to the form closes Send again: an approval of a
frequency you have since changed says nothing about the spot you are about to
send.

Doing both automatically on one press would double the consumption of a budget
shared with every other Spotline client, and nobody would be better off for it.
So the second press is yours to make.

### What comes back, and what the app does with it

| Answer | What the app shows |
|---|---|
| `201` | the spot is on Spotline, with its `spot_id` |
| `409` duplicate | reassurance, not an error — you pressed twice on a bad connection and nothing was posted twice |
| `400` | Spotline's own explanation, verbatim, because they said it better than we could |
| `401` / `500` | a key problem, phrased as ours to fix rather than yours |
| `429` | too many in quick succession, try again shortly |
| `503` with `enabled: false` | spotting through Diana is switched off (see the kill switch) |
| `503` with `limit: "day"` | the daily ceiling of the free tier — the message names the free tier and says to come back tomorrow |
| no answer at all | the Worker cannot be reached |

The last four also offer **the old route**. A `400` deliberately does not: the
old route would refuse the same spot too, it would just not tell you.

### The old route, and why it stays

Before the Worker, self-spotting was a real HTML form posted to
`spots.wwff.co/spots/store` with `target="_blank"`. Form submissions are not
subject to CORS, so this works with no key, no proxy and no cooperation from
anyone's server configuration. It is still in the code, as
`verstuurKlassiek()`.

It appears by itself whenever the Worker cannot help, and it can be made
permanent per device with **"Always send the old way"** in Settings. What it
cannot do is confirm anything: Spotline's own page opens in a new tab and you
read the result there, but the app never learns what happened. That gap is the
entire reason the Worker exists — and the reason this stays a way out rather
than the way.

## Announcing an activation is the same story, at a different address

**Fase 4** added a screen for announcing an activation ahead of time —
"Aankondigen", reached from the Agenda tab of the Spots screen — and it
needed nothing new from the Worker. `buildAgenda()` already existed, written
in Fase 2 against the same API description as spots, so the screen is purely
the front end: the same Check-then-Send pattern, the same `refLookup()` for
the reference field, posted to `{worker}/agenda` instead of `{worker}/spot`.
(That endpoint's own upstream path needed a correction on 2026-09-09 — WWFF's
published docs and their live router disagreed; see `worker/README.md`.)

Two things about it are genuinely different, both because an agenda entry
outlives the moment it is sent. First, the times: the picker shows the
activator's own local clock, and the app converts to UTC before anything
leaves the device — nobody should have to do that arithmetic by hand.
Second, the **PIN**: it is what lets the activator edit or cancel the entry
later, directly on Spotline, and Diana has no part in that later edit. Lose
the PIN and there is no way back in. Diana keeps a local list — reference,
date, PIN — precisely so that "later" doesn't mean "guess". That list is
`localStorage['diana.agendas']`, per device, like everything else in
§"Where the key is" below except the key itself.

There is no old-route fallback for this one. `/spots/store` exists as a real
HTML form because Spotline built it that way; there is no documented
equivalent for agenda entries, so an unreachable Worker here is just an
error to retry, not a second path.

## Checking references without asking anyone

There is a `GET /api/references/validate`, and Diana does not use it. Calling
it while somebody types costs requests from the shared budget and is slower
than the alternative, which is that we already have the data.

`refLookup()` answers from `data/`:

| The reference | What we can say |
|---|---|
| wrong shape | rejected, certainly — same rule as the Worker applies |
| unknown programme | rejected, certainly — this catches the common prefix typo |
| `ONFF-…` we have | accepted, **with the name of the reserve** |
| `ONFF-…` we do not have | rejected, certainly — the 946 are all of them |
| another programme, world layer loaded | judged against `wwff-world.geojson` |
| another programme, world layer not loaded | the programme's country, and an explicit "not checked here" |

That last row matters. Loading nine megabytes to validate a text field would be
a poor trade, so in that case we say what we know and let Spotline have the
last word — rather than rejecting something we have no grounds to reject.

Note that ONFF references are looked up in **two** files: `onff.geojson` for
the areas with a boundary and `onff-points.geojson` for the point-only ones. A
reference without a polygon is still a perfectly valid reference, and checking
only the first file would reject a handful of real ones.

## Operating it

Everything below is `worker/README.md` in one-line form; go there for the
detail.

**Stopping everything**, within seconds, without a deploy:

```
npx wrangler kv key put --binding DIANA_KV switch off --remote
```

Every request then gets a 503 the app knows how to explain, and the old route
appears by itself. Back on with `kv key delete` on the same key.

**Going back to the test host** is one line in `worker/wrangler.toml` —
`WWFF_BASE` — plus a deploy. That is the first thing to try if sending looks
wrong in a way that is not obviously the app's fault.

**Watching it:** `npx wrangler tail`. You will see event names and counts, and
nothing else. No callsigns, no positions, no remarks — deliberately, and
`worker/test/routing.mjs` asserts it, along with the more important claim that
the key appears in the upstream header and in no response, no log line and no
KV value.

## The limits, and where the numbers come from

WWFF's own ceiling is roughly 100 requests a minute and 1000 an hour, shared
with every other Spotline client. Diana sits far below that on purpose: running
into our own ceiling inconveniences one person, while emptying WWFF's is
everybody's outage.

| Limit | Value | What it is for |
|---|---|---|
| `LIMIT_IP_SPOTS` / `LIMIT_IP_WINDOW` | 8 per 10 min | one person hammering. Eight rather than five because check-then-send is two requests |
| `LIMIT_IP_AGENDA` | 10 per day | the same, for announcements |
| `LIMIT_GLOBAL_MINUTE` | 40 per minute | Diana as a whole, against the shared budget |
| `LIMIT_GLOBAL_DAY` | 90,000 per day | a soft version of Cloudflare's own hard wall at 100,000 |

The last one is honest about what it can and cannot see: it counts requests
that pass validation and actually go upstream, not every hit the Worker
receives, because counting those would burn KV's 1000-writes-a-day budget in
minutes during exactly the flood you would want it for. At 40 a minute the row
above it already keeps a day's accepted traffic near 57,600, so in normal
operation the daily one never fires. It is there for the day somebody raises
the per-minute limit without thinking about this file.

## Where the key is, and everything else that is a secret

In Cloudflare, as an encrypted secret named `WWFF_API_KEY`, and nowhere else.
Not in this repository, not in a GitHub Actions secret, not in the published
bundle. `worker/test/routing.mjs` proves the last of those.

What is **not** secret, and belongs in the repository: the KV namespace id in
`wrangler.toml` (a reference, useless without a Cloudflare token), the Worker's
address (it is in the app, unavoidably), and every limit above.

The full register of every credential in the project — where each lives, what
breaks when it expires, and how to replace it — belongs in `MAINTENANCE.md`.
