# Install guide — setting up Diana from scratch

This is the procedure for standing Diana up somewhere new: a fresh GitHub
account, a hand-over to someone else entirely, or a second environment to
test changes in without touching the live site. It starts from nothing —
no organisation, no repository, no Worker — and ends with a working,
publicly reachable copy.

**Written for someone who has never used GitHub before.** Every step says
exactly where to click, what you should see if it worked, and what goes
wrong if you skip it. If you already know GitHub well, skim past the parts
that are obvious to you — they're here for the person who doesn't, not to
insult the person who does.

**Before you start:** this only covers the *how*. For *why* the project is
shaped the way it is (two repositories, a Cloudflare Worker, no server of
its own), read [ARCHITECTURE.md](ARCHITECTURE.md) and
[DEPLOY.md](../DEPLOY.md) first — it makes the steps below make sense
instead of feeling arbitrary.

**Try this on a throwaway copy first.** Do a full run-through in an
organisation and repositories you're willing to delete afterwards, with a
disposable token. That is the only real way to know this guide actually
works, and it costs nothing.

---

## 0. Create the organisation

1. On github.com, create a **new organisation** on the free plan. Use an
   email address that isn't tied to one person if you can — a shared
   mailbox, or a role account — so the project doesn't depend on one
   individual's GitHub login existing forever.
2. Immediately after creating it, go to **organisation Settings → Personal
   access tokens → Settings** and turn on **"Allow access via fine-grained
   personal access tokens."** This is easy to miss and only shows its effect
   much later: without it, the in-app Admin panel (which uses exactly this
   kind of token) simply cannot authenticate, with an error that doesn't
   mention this setting at all.

**Checkpoint:** the organisation exists, and fine-grained tokens are
allowed.

---

## 1. Create the two repositories

| Repository | Visibility | Contains |
|---|---|---|
| `<your-org>/<your-org>.github.io` | **Public** | the app, the data, the workflows, the documentation, the Worker's code |
| `<your-org>/diana-source` (name doesn't matter, but be consistent) | **Private** | only the KMZ files, one folder per country: `source/ONFF/`, `source/PAFF/` … (and `incoming/`, the waiting room the Admin panel creates) |

The public repository's name matters more than it looks: only a repository
named **exactly** `<organisation>.github.io` publishes at
`https://<organisation>.github.io/` with no extra path segment. Any other
name publishes at `https://<organisation>.github.io/<repo-name>/` instead —
which still works, but every link, embed snippet and the Worker's allowed
origins would need that extra segment too. Decide this before copying any
files in.

Copy this project's contents into the two repositories as the table above
splits them — everything except `source/**.kmz` into the public one, and
only the KMZ files into the private one. **The `.github/` folder is the one
thing people lose without noticing**: Windows Explorer hides folders whose
name starts with a dot, so dragging an extracted zip into GitHub's web
uploader silently leaves it behind, and then there is no workflow at all.
Check on github.com afterwards that `.github/workflows/build-data.yml`,
`.github/workflows/pages.yml` and `.github/workflows/conditions.yml`
genuinely exist in the public repository. If
they don't, add them with **Add file → Create new file**, type the full
path (`.github/workflows/pages.yml`) as the file name — GitHub creates the
folders for you — and paste the contents in.

**Checkpoint:** both repositories exist, with the right visibility, and
`.github/workflows/` is visibly present in the public one.

---

## 2. Settings you must set before the first run

In the **public** repository: **Settings → Actions → General → Workflow
permissions → "Read and write permissions" → Save.**

Do this *before* running anything. Without it, every workflow fails the
same way: a `403 permission denied` when it tries to push — the nightly build
can't commit to `main`, `pages.yml` can't push to `gh-pages`, and
`conditions.yml` can't write its `conditions` branch. It's the single most
common reason a fresh install doesn't work.

On the same page, under **Fork pull request workflows from outside
collaborators**, choose **Require approval for all external contributors**.

Then connect the private repository, so the build can read the KMZ:

1. Create a fine-grained token: your account → **Settings → Developer
   settings → Personal access tokens → Fine-grained tokens → Generate new
   token**. Resource owner: the organisation. Repository access: only
   `diana-source`. Permissions: **Contents: Read-only**, nothing else.
   Expiration: 90 days or less (see [MAINTENANCE.md §3.1](MAINTENANCE.md#31-source_token)).
2. Public repository → **Settings → Secrets and variables → Actions →
   Secrets → New repository secret**: name `SOURCE_TOKEN`, value the token.
3. Same page, tab **Variables → New repository variable**: name
   `SOURCE_REPO`, value `<your-org>/diana-source`.

**Checkpoint:** Workflow permissions is set to Read and write, fork pull
requests need approval, and `SOURCE_TOKEN` and `SOURCE_REPO` are listed.

---

## 3. The first Pages build

The `gh-pages` branch that GitHub Pages serves from does not exist yet — it
is created *by the workflow*, not by you. In the public repository:
**Actions → "Publish to GitHub Pages" → Run workflow → Run workflow**
(leave the branch field empty).

Wait for it to finish (green check). This creates the `gh-pages` branch for
the first time.

**Checkpoint:** a `gh-pages` branch now exists in the repository (visible in
the branch dropdown).

---

## 4. Point Pages at it

**Settings → Pages → Source: "Deploy from a branch" → Branch: `gh-pages`,
folder `/ (root)` → Save.**

Only once `gh-pages` exists (step 3) does it appear as a choice here — if
you don't see it, step 3 didn't finish successfully.

**Checkpoint:** `https://<your-org>.github.io/` loads something (the site
will still be missing its data — that's step 5).

---

## 5. Build the data for the first time

Put one KMZ file in `source/<PROG>/` in the **private** repository, for
example `source/ONFF/ONFF_20260101.kmz` (a normal file upload on github.com
is fine for this first one — later releases go through the review flow in
[ADMIN.md](ADMIN.md#1-publishing-a-new-release-for-a-country)), then, in the
public repository: **Actions → "Build map data" → Run workflow** (leave the
branch field empty — that field is only for the Admin panel's own upload
flow).

Read the run's summary. You should see a line like:

> **932 zones** (was 0, +932) · **932 new** · **0 removed** · **0 boundary
> changed**

and, further down, how many references came from the WWFF directory versus
the KMZ. The step "Determine the source directory" should say `Source:
private repo <your-org>/diana-source (directory source/)`. If it warns that it
fell back on `source/` in this repo, `SOURCE_TOKEN` or `SOURCE_REPO` is wrong
(step 2); if it finds no KMZ at all, the file didn't land in
`source/<PROG>/`, or landed with the wrong extension.

**Checkpoint:** the workflow succeeds, `data/*.json` files appear in the
repository, and reloading the site now shows the map with zones on it.

---

## 6. Optional: pointing at a different WWFF directory

Only needed if WWFF ever moves `wwff_directory.csv`, or you want to test
against your own copy: set a repository variable **`ONFF_REFS_CSV`**
(Settings → Secrets and variables → Actions → **Variables**) to a URL or a
path inside the repository. Leave it unset otherwise — the default already
points at the live file.

---

## 7. The administrator's own token

This is the token you'll use personally, day to day, through Diana's own
Admin panel. Full instructions — exact scopes, why each one, expiration —
are in [ADMIN.md → Creating the token](ADMIN.md#connecting-to-a-repository).
Follow those, then come back here.

**Checkpoint:** in Diana (`?admin=1`), you can fill in both repository
names and this token, and **"Test the connection"** reports success against
both repositories.

---

## 8. Branch protection and the other security settings

Public repository → **Settings → Rules → Rulesets → New ruleset → New branch
ruleset**. Name it (`main`), set **Enforcement status: Active**, under
**Target branches → Add target → Include default branch**, and turn on:

- **Block force pushes** — yes
- **Restrict deletions** — yes
- **Require a pull request before merging** — **no.** This one is
  counter-intuitive: turning it on would also block the nightly build's own
  direct commit to `main` (see
  [DEVELOPER.md §3](DEVELOPER.md#3-the-three-github-actions-workflows)), which
  is deliberately not a pull request. Leave it off, and rely on the
  KMZ-upload review flow (§9 below, or ADMIN.md) for the changes that
  genuinely need a human to look first.

**Checkpoint:** a direct push of a small, harmless commit succeeds; a force
push is refused.

Then set the rest of the list in
[MAINTENANCE.md §6a](MAINTENANCE.md#6a-the-github-security-settings):
two-factor authentication required for the organisation (secure methods
only), Secret Protection and Push protection on the public repository, and a
second owner.

---

## 9. The Worker (Cloudflare)

This is the piece that lets Diana send spots and announcements to WWFF
without shipping an API key to every visitor's browser. Full detail is in
[worker/README.md](../worker/README.md); the ordered version for a first
setup:

1. Create a free Cloudflare account, then `npm install -g wrangler` and
   `wrangler login` (opens a browser tab to approve it).
2. `cd worker && npx wrangler kv namespace create DIANA_KV`, then paste the
   `id` it prints into `worker/wrangler.toml`'s `[[kv_namespaces]]` block —
   only the id string, not the whole JSON snippet wrangler shows you.
3. `npx wrangler deploy`. It prints the Worker's address, something like
   `https://diana-spotline.<your-account>.workers.dev`.
4. `npx wrangler secret put WWFF_API_KEY` — paste the key WWFF issued you
   when prompted. See [MAINTENANCE.md §3.2](MAINTENANCE.md#32-wwff_api_key)
   if you don't have one yet.
5. In `worker/wrangler.toml`, set `ALLOWED_ORIGINS` to your public site's
   real address (`https://<your-org>.github.io`), and confirm `WWFF_BASE`
   points at `https://spots-dev.cuf.fi` (test) or `https://spots.wwff.co`
   (production) as appropriate. Re-deploy after any change here.
6. Verify: `curl https://diana-spotline.<your-account>.workers.dev/status`
   returns JSON, and `npx wrangler secret list` shows `WWFF_API_KEY` by
   name only, never its value.

**Checkpoint:** the `/status` endpoint answers, and a `dryrun` spot sent
through it comes back accepted.

---

## 10. Point the app at your Worker

One constant: `WORKER` at the top of `web/js/self-spot.js`. Change it to the
address from step 9, commit, and let `pages.yml` publish it. `agenda.js`
reads the same constant — there is only one place to change.

Two more addresses point at the original organisation and need the same
treatment on a copy elsewhere: `COND_URL` at the top of
`web/js/conditions.js` (the `conditions` branch of *your* public repo), and
the default repository names in the Admin panel, which each administrator
fills in anyway.

**Checkpoint:** self-spotting and announcing an activation both work from
the published site, not just from the Worker's own `/status` endpoint.

---

## 11. Checking the whole thing end to end

- The live site shows zones, and searching for a reference works.
- Live spots and the agenda appear on the Spots screen (confirms
  `spots.wwff.co`'s static files are reachable — they always have been, no
  Worker involved in reading them).
- Field info → Areas lists references with distances and QSO counts
  (confirms `data/zones/<prog>-activity.json` was built and shipped; without
  it the distances still appear but every reference reads as having no
  figures).
- Field info → Conditions shows numbers less than an hour old (confirms
  `conditions.yml` runs and `COND_URL` points at your repo; run **Actions →
  Space weather → Run workflow** once to start it).
- Self-spotting and announcing an activation both complete with a real
  confirmation (confirms the Worker, step 9-10).
- Opening the Admin panel, testing the connection, and doing one real
  upload-and-publish cycle end to end (confirms step 7, and the whole
  review flow in [ADMIN.md](ADMIN.md#2-the-in-app-admin-panel)).

**This install guide is not finished until you've done this list yourself,
on the environment you just built.** A procedure nobody has actually run is
a wish list, not a guide — and running it once is how you find the three
things that don't quite match what's written here.

---

## 12. If something doesn't work

Don't re-derive this from scratch — the two most common failure classes
already have a written diagnosis:

- **No `gh-pages` branch, a 403 on publish, or the wrong thing gets
  published** → [ADMIN.md §4 Troubleshooting](ADMIN.md#4-troubleshooting).
- **A pull request doesn't get a diff report or a preview link** → same
  section — check the PR actually touches `source/**.kmz`, `overrides.json`,
  or `build/**`.
- **A credential doesn't work, or you're not sure which one to touch** →
  [MAINTENANCE.md](MAINTENANCE.md)'s credential register.

If none of those cover it, the honest next step is to add what you found
here, so the next person doesn't repeat the same evening you just had.
