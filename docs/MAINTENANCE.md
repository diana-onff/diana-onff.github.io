# Maintenance & security guide

Every credential in the project, where it lives, what breaks if it expires or
disappears, and how to replace it — written for whoever ends up keeping Diana
running, including a future version of the person reading this now. If you
inherit this project and read only one document, make it this one.

This is not a security audit. It is the opposite: a plain list of what is
sensitive, what isn't, and exactly what to click, so that a routine token
renewal never turns into an evening of guessing.

---

## 1. Two kinds of "administrator" — work out which one you need

Diana has no accounts and no login of its own (see
[ARCHITECTURE.md §3](ARCHITECTURE.md#3-whats-stored-where-and-what-never-leaves-the-device)).
"Administrator" always means a GitHub identity with the right repository
access, and there are two clearly different jobs hiding behind that one word:

| | **Content administrator** | **Technical maintainer** |
|---|---|---|
| Does | Publishes new ONFF releases: uploads a KMZ, looks at the preview, merges or rejects | Everything a content administrator does, **plus** touching secrets, redeploying the Worker, changing repository settings |
| Needs | GitHub **Write** access to both repositories, and their own fine-grained token (§4) | The above, **plus** GitHub **Admin/Owner** rights on both repositories, and access to the project's Cloudflare account |
| Cannot do | Read or change any secret, redeploy the Worker, change branch protection or Actions settings | — |
| How many, realistically | As many as you trust to publish | One or two — every extra person here is someone who could print `WWFF_API_KEY` in a workflow log or drain the Cloudflare account |

Most people who help with Diana only ever need to be a content administrator.
Keep the second circle small on purpose: §5 covers what it actually takes to
add one.

---

## 2. The credential register

Everything in this table is sensitive. Nothing outside it is (§6 says what
that "everything else" actually is, on purpose — treating a non-secret as one
makes handover harder, not safer).

| Credential | What it protects | Where it lives | Who can read the value | Expires? | What breaks if it's gone |
|---|---|---|---|---|---|
| `SOURCE_TOKEN` | Read access to the private `diana-source` repo | GitHub Actions **secret**, in the **public** repo (`diana-onff/diana-onff.github.io` → Settings → Secrets and variables → Actions → Secrets) | Nobody, once saved — GitHub secrets are write-only from that point on | Yes, if you gave it one when you created it (recommended) | The nightly build can't fetch the KMZ, falls back to `source/` in the public repo (empty, normally), and prints a `::warning::` in the Actions log. The site itself keeps working — this only stops *new* data from arriving |
| `WWFF_API_KEY` | The whole point of the Worker — WWFF's API key | Cloudflare Worker **secret** (`wrangler secret put`), scoped to the `diana-spotline` Worker only | Nobody — Cloudflare encrypts it on entry; not the dashboard, not `wrangler`, not the API | No built-in expiry; WWFF can revoke or ask you to rotate it | Self-spotting and announcing stop working (`401` from the Worker); the map, the zone data and reading spots are unaffected — they never used this key |
| An administrator's GitHub token | Write access to both repositories, from inside Diana's Admin panel | The browser's own memory for that tab, or `localStorage` on that one device if "remember" was ticked | That one person, on that one device | Whatever you set when creating it — 90 days is a sane default | That one person can no longer upload through the Admin panel until they make a new one. Nothing else is affected, and nobody else's token is touched |
| Cloudflare account login (`wrangler login`) | The ability to deploy the Worker or change its secrets/settings | Whoever's machine ran `wrangler login`; Cloudflare's own session | That person | Cloudflare sessions expire on their own after inactivity; re-run `wrangler login` | You can't deploy or rotate `WWFF_API_KEY` until someone logs in again — the Worker itself keeps running regardless |

Two credentials that sound like secrets but are handled entirely by GitHub
and are not something you manage by hand: the built-in `GITHUB_TOKEN` every
workflow run gets automatically (scoped to that run, expires when it ends),
and GitHub Pages' own deployment mechanism. Neither is configured anywhere in
this repository.

---

## 3. Replacing each one

### 3.1 `SOURCE_TOKEN`

1. On github.com, go to your own account → **Settings → Developer settings →
   Personal access tokens → Fine-grained tokens → Generate new token.**
2. **Resource owner:** the `diana-onff` organisation.
3. **Repository access:** "Only select repositories" → `diana-source`. Not
   the public repo — this token has no business there.
4. **Permissions:** **Contents: Read-only.** Nothing else. If a screen offers
   more, that's a sign you picked the wrong token type.
5. **Expiration:** pick one — 90 days is reasonable — and set a personal
   reminder for a few days before it lapses (see §7).
6. Generate it, copy the value **immediately** (GitHub shows it exactly
   once).
7. Go to the **public** repo → **Settings → Secrets and variables → Actions →
   Secrets** tab → find `SOURCE_TOKEN` → **Update** → paste the new value.
8. Verify: **Actions → "Build ONFF data" → Run workflow**, leave the branch
   field empty, run it. Open the run and check the "Determine the source
   directory" step — it should say `Source: private repo diana-onff/diana-source`
   with **no** `::warning::` line above it.

### 3.2 `WWFF_API_KEY`

This one needs a machine with `wrangler` installed and logged in to the
project's Cloudflare account (§3.4).

```
cd worker
npx wrangler secret put WWFF_API_KEY
```

Paste the new key when prompted. That's the entire rotation — there is
nothing to update in the repository, because the code only ever refers to
`env.WWFF_API_KEY`, never the value itself.

Verify:

```
curl https://diana-spotline.diana-onff.workers.dev/status
```

then send one real self-spot with `"dryrun": true` from the app (or with
`worker/test/curl.sh`) and confirm it comes back accepted, not `401`.

**When to do this without being asked:** if the key has ever travelled
somewhere it shouldn't have — pasted into an email, a chat, a screenshot —
treat it as compromised and ask WWFF for a fresh one rather than waiting for
something to go wrong. WWFF can also revoke a key on their end at any time;
that shows up here as every spot suddenly failing with `401`, and the fix is
the same three lines above with the new value they issue.

### 3.3 An administrator's own GitHub token

There is no central rotation — each administrator manages their own. When
theirs is about to expire, or already has:

1. They create a new fine-grained token exactly as described in
   [ADMIN.md — Creating the token](ADMIN.md#connecting-to-a-repository).
2. They open Diana's Admin panel and paste it in over the old one.
3. If "remember" was ticked, the old value in `localStorage` is simply
   overwritten — no separate step to "delete" the expired one.

Nobody else needs to do anything. One administrator's expired token has zero
effect on any other administrator, or on the site.

### 3.4 Cloudflare access (`wrangler login`)

```
npx wrangler login
```

opens a browser tab to approve the connection. This is per-machine, per-person
— it is not a value stored anywhere in the repository, so there is nothing to
"update", only to redo when a session has expired or on a new machine.
`wrangler whoami` confirms which account you're currently authenticated as.

---

## 4. Adding a new content administrator

1. **Give them repository access.** On both `diana-onff/diana-onff.github.io`
   and `diana-onff/diana-source`: Settings → Collaborators and teams → **Add
   people** → their GitHub username → role **Write**. Write is enough to
   upload, open pull requests, and merge; it is not enough to change
   repository settings or read secrets.
2. **Have them create their own token**, following
   [ADMIN.md's instructions](ADMIN.md#connecting-to-a-repository) exactly —
   fine-grained, scoped to both repositories, Contents + Pull requests +
   Actions read/write, short expiration. Never hand someone your own token;
   each administrator has their own, so that removing one person later never
   means rotating anyone else's.
3. **They open Diana** with `?admin=1` (or tap the logo five times), fill in
   both repository names and their token, and press **Test the connection**
   before uploading anything for real.
4. Tell them plainly: don't tick "remember the token on this device" on a
   shared or public computer. See [ADMIN.md's token warning](ADMIN.md#a-plain-warning-about-the-token)
   for why.

If their token mysteriously fails to authenticate even though it looks right,
check the one organisation-wide setting this all depends on: **organisation
Settings → Personal access tokens → Settings → allow access via fine-grained
personal access tokens.** This is normally set once, for the whole
organisation, and never touched again — but it's exactly the kind of setting
that produces a confusing error for the one person who joins after everyone
forgot it exists.

**Removing a content administrator:** remove them as a collaborator on both
repositories. Their token stops being useful the moment they lose repository
access — there is no separate token to revoke.

---

## 5. Adding a new technical maintainer

Only do this for someone who genuinely needs to touch secrets or redeploy —
not for someone who just publishes releases (§4 is enough for that).

1. Everything in §4, plus:
2. **GitHub:** give them the **Admin** role (not just Write) on both
   repositories, or make them an **organisation Owner** if they'll be
   managing settings and other people's access too.
3. **Cloudflare:** either invite them as a member on the project's Cloudflare
   account (Cloudflare dashboard → Manage account → Members), or — simpler,
   and what this project has done so far — treat the Worker as something
   anyone with the code and their *own* Cloudflare account can redeploy from
   scratch (see [worker/README.md](../worker/README.md#setting-it-up)) rather
   than sharing one account. Either is fine; pick the one that matches how
   much you trust this person with the account as a whole, not just the
   Worker.
4. **Locally:** `npm install -g wrangler`, then `wrangler login` on their own
   machine.

---

## 6. What is *not* a secret

Worth writing down on purpose, because the instinct to protect everything
makes a handover harder, not safer:

| Not a secret | Why | Where it lives |
|---|---|---|
| The KV namespace id in `worker/wrangler.toml` | A reference, not a credential — useless to anyone without a Cloudflare token for this account | Committed in the repository |
| The Worker's address (`diana-spotline.diana-onff.workers.dev`) | It has to be, since the app itself calls it from every visitor's browser | `web/js/self-spot.js`, `WORKER` constant |
| The repository variable `ONFF_REFS_CSV` (if set) | It's a URL or file path, not a credential | Settings → Secrets and variables → Actions → **Variables**, public repo |
| The repository variable `SOURCE_REPO` | The *name* of the private repo, not access to it — the access is `SOURCE_TOKEN` | Same place |
| Every rate limit in `worker/wrangler.toml` | Configuration, and arguably more useful to a would-be abuser if it were *hidden* and untested | Committed, `[vars]` block |
| The Worker's entire source code | The key is the secret, never the code that uses it — see [SPOTLINE.md](SPOTLINE.md) | `worker/src/index.js`, public |

---

## 7. Things that go stale quietly

A checklist worth reading every few months, because none of these announce
themselves the way an expired password does:

- **Token expiration dates.** Keep your own note of what you've issued and
  when it lapses — GitHub doesn't remind you, and Diana can't either, since
  it never sees the token's expiry date, only whether a call succeeded.
  A simple personal calendar reminder a week before each one expires is
  enough.

  | Token | Issued | Expires | Reminder set? |
  |---|---|---|---|
  | `SOURCE_TOKEN` | _fill in_ | _fill in_ | |
  | (your own admin-panel token) | _fill in_ | _fill in_ | |

- **GitHub disables an inactive scheduled workflow after 60 days.** If the
  repository sees no activity at all for two months, the nightly `01:00 UTC`
  build quietly stops running — GitHub emails the repository owner when this
  happens, and re-enabling it is one click on **Actions → "Build ONFF data" →
  "Enable workflow"**. On an active project this practically never triggers,
  but a quiet period (a slow winter, an admin on leave) can be enough.
- **The nightly build can fail without anyone noticing unless someone reads
  GitHub's notifications.** See §10.
- **The WWFF directory CSV can move or change shape** without warning — it's
  someone else's file, not an API with a deprecation notice. `--strict`
  (used by the nightly run) refuses to build on a truncated or unreachable
  copy rather than publishing bad data; see §10 for what that failure looks
  like.

---

## 8. Limits worth watching

None of these are close to being hit in ordinary use, which is exactly why
they're easy to forget about until the one week they matter:

| Limit | Value | What happens at the ceiling |
|---|---|---|
| Cloudflare KV writes | 1,000/day, free tier | The rate-limit counters themselves start failing to write — see `worker/README.md`'s "Limits, and why these numbers" section for how far normal traffic sits below this |
| GitHub Actions minutes | Unlimited on the **public** repo; 2,000/month free on the **private** one | The private repo (`diana-source`) barely uses any — it holds no workflow of its own, it's only ever *checked out by* the public repo's workflow |
| GitHub Pages | 1 GB site, soft limit ~10 builds/hour | Diana publishes a few megabytes per release, a handful of times a month — nowhere close |
| GitHub web upload | 25 MiB per file | The ONFF KMZ is ~17 MB; if it ever grows past 25 MiB it has to go through git instead of drag-and-drop |
| WWFF's own API budget | ~100 requests/minute, ~1000/hour, shared with every Spotline client | Diana's own `LIMIT_GLOBAL_MINUTE` (40/min) stays comfortably under this on purpose — see [SPOTLINE.md](SPOTLINE.md#the-limits-and-where-the-numbers-come-from) |
| Cloudflare Workers free tier | 100,000 requests/day | `LIMIT_GLOBAL_DAY` (90,000) is a deliberately softer version of this same wall — see `worker/README.md` |

---

## 9. The kill switch

For when something needs to stop *now* — reported abuse, a request from
WWFF, a suspected key compromise — without waiting for a deploy:

```
npx wrangler kv key put --binding DIANA_KV switch off --remote
```

Every request to the Worker then gets a clean `503` that the app already
knows how to explain to a user, and self-spotting falls back to the old
form-post route automatically. Turn it back on with:

```
npx wrangler kv key delete --binding DIANA_KV switch --remote
```

This needs the same `wrangler login` access as §3.2 and §3.4 — nothing more.
Test it once, deliberately, before you ever need it for real (flip it off,
confirm the app shows the fallback, flip it back on) — see
`worker/README.md`'s "Operating it" section.

---

## 10. When the nightly build fails

A failed or skipped nightly run (WWFF's directory unreachable, or the output
looked truncated) opens — or comments on — a GitHub issue labelled
`diana-nachtelijke-build` in the **public** repo, rather than failing
silently. As the repository's owner you're watching it by default, so this
arrives as a GitHub notification and, if you've turned on email for Issues
under github.com → Settings → Notifications, as an email too.

Most of these are transient — WWFF's own directory file was briefly
unreachable, and the next scheduled run the following night succeeds on its
own. Only chase it yourself if it repeats for more than a night or two: use
**Actions → "Build ONFF data" → Run workflow** to retry immediately rather
than waiting for 01:00 UTC.

---

## 11. Moving the whole project

Changing GitHub accounts, handing the project to someone else entirely, or
just wanting a second environment to test in — none of this is a rewrite.
[docs/INSTALL.md](INSTALL.md) is the from-scratch procedure, written for
exactly this situation. The Worker in particular is, deliberately, fully
disposable: the code lives in the repository, and `wrangler deploy` puts a
working copy anywhere in one command — the only thing a move costs is a new
address in one constant (`WORKER` in `web/js/self-spot.js`) and a new
`WWFF_API_KEY`.
