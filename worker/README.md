# Diana — Spotline proxy

A Cloudflare Worker that sits between the Diana app and the WWFF Spotline API.

## Why this exists

WWFF issues one API key per application and asks that it be kept server-side.
Diana is a static page on GitHub Pages, so there is no server to keep it on:
anything the page can read, every visitor can read. This Worker is that missing
server, and it is the only thing in the project that ever sees the key.

Forwarding is the least interesting thing it does. Its value is in what it
refuses:

| Refused here | Why it matters |
|---|---|
| Unknown fields | The payload is built field by field, never copied. Nothing invented by a caller reaches WWFF. |
| Bad callsigns, frequencies, modes, references | A typo costs nothing from the shared WWFF budget if it is caught here. |
| More than a handful of spots per IP | One person cannot spend the budget. |
| More than ~40 requests a minute in total | Diana as a whole cannot spend it either — and that budget is shared with every other Spotline client. |
| Everything, when the switch is off | One KV key stops the service in seconds, without a deploy. |

The key travels in one direction only: to WWFF, in the `X-API-Key` header, over
HTTPS. It is never in a response, a log line, a KV value or an error message —
and `worker/test/routing.mjs` asserts each of those.

## Endpoints

| Method | Path | What it does |
|---|---|---|
| `POST` | `/spot` | Validates and forwards to `POST {WWFF_BASE}/api/spots/add` |
| `POST` | `/agenda` | Validates and forwards to `POST {WWFF_BASE}/api/agenda/store` |
| `GET` | `/status` | Version, upstream, and whether the switch is on. Costs nothing, needs no key. |
| `OPTIONS` | any | CORS preflight, answered before any counter is touched |

Add `"dryrun": true` to a spot or agenda body and Spotline validates without
storing. Use it for everything until you are sure.

## Setting it up

Prerequisite: a Cloudflare account and `wrangler login`. See `CLOUDFLARE.md`.

**1. Create the KV namespace** — it holds the counters and the kill switch:

```
cd worker
npx wrangler kv namespace create DIANA_KV
```

Paste the `id` it prints into `wrangler.toml`, replacing `VUL_HIER_HET_ID_IN`.
Wrangler shows it as a JSON snippet; this file is TOML, so copy only the id
string itself, not the whole block.

That id belongs in the repository. It is a reference, not a key: without a token
for this Cloudflare account it does nothing. Committing it is what lets the next
person — or you on another machine — deploy without hunting for it. What must
never be committed is `.dev.vars`, the file `wrangler dev` writes local secrets
into in plain text; `.gitignore` already blocks it.

**2. Deploy:**

```
npx wrangler deploy
```

It will tell you the address, something like
`https://diana-spotline.diana-onff.workers.dev`.

**3. Put the key in.** This is the one step nobody else can do for you:

```
npx wrangler secret put WWFF_API_KEY
```

It asks for the value in the terminal, encrypts it, and never shows it again —
not in the dashboard, not through wrangler, not through the API. The code reads
it as `env.WWFF_API_KEY` while it runs. To replace it later (after a rotation,
for instance), run the same command again.

**4. Check:**

```
curl https://diana-spotline.diana-onff.workers.dev/status
npx wrangler secret list      # shows the NAME, never the value
```

## Testing

Two suites run under plain node — no Cloudflare, no key, no network:

```
node worker/test/validation.mjs   # what may and may not become a payload
node worker/test/routing.mjs      # CORS, the kill switch, rate limiting, and
                                  # that the key does not leak
```

Against the live development host, with `dryrun` so nothing is stored:

```
bash worker/test/curl.sh https://diana-spotline.diana-onff.workers.dev
```

## Operating it

**Switching everything off**, within seconds, without a deploy:

```
npx wrangler kv key put --binding DIANA_KV switch off --remote
```

The Worker then answers every request with a 503 and an explanation the app can
show. Back on:

```
npx wrangler kv key delete --binding DIANA_KV switch --remote
```

**Moving from the test host to production** is one line in `wrangler.toml`:
change `WWFF_BASE` and deploy. Do that only once the rate limiting has been
tested against the development host, because it is the one thing that cannot be
tried out safely afterwards.

**Watching it:**

```
npx wrangler tail
```

You will see event names and counts. Nothing else is logged: no callsigns, no
positions, no remarks. If you ever want to add one of those to debug something,
reproduce it with a `dryrun` instead.

## Limits, and why these numbers

WWFF's own ceiling is roughly 100 requests a minute and 1000 an hour per key,
shared with every other Spotline client. Diana's limits sit far below that on
purpose: hitting our own ceiling inconveniences one user, while emptying WWFF's
is everybody's outage.

Cloudflare's free tier gives 100,000 KV reads and **1000 KV writes** a day. The
writes are the tight one, so only requests that pass validation and are actually
going upstream write anything — a preflight, a rejected form or a blocked origin
costs nothing. Two writes per accepted request means roughly 500 spots a day
before KV becomes the limit, which is far more than this service will ever see.

The counters are read-then-write without a lock, so two requests in the same
millisecond can lose one increment. That is accepted: being off by one costs one
spot too many, and the alternative — a Durable Object — is a different pricing
tier for a counter that only has to be roughly right.
