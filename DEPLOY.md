# Putting Diana online — everything inside GitHub

No Cloudflare, no external service. One repo, GitHub Pages, and one administrator who
uploads. This document is also honest about what becomes public in the process and
what does not.

---

## 1. First, the question that really matters

> "Downside: it's public. But the data shouldn't just be up for grabs, should it?"

There are three different things in that question, and only one of them is a real
choice.

### The zone boundaries become public either way

Diana is a static web app. Every visitor's browser **downloads `onff.geojson`** —
that is how the map works. Anyone who can open the app can save that file. That holds
on GitHub Pages, on Cloudflare, on any hosting whatsoever, and whether the repo is
public or private.

In other words: **publishing the app *is* publishing the boundaries.** If ONFF does
not want that, then Diana cannot exist as a public web app — it would become a closed
app behind a login, and that is an entirely different project.

For reassurance: those boundaries are already public in practice. The ONFF blogspot
shows them province by province in embedded Google My Maps, without a login.

### Making the repo public adds exactly one thing

Namely the **original KMZ file**, as a file, redistributed through a second channel.
ONFF distributes it through the BOS groups.io, behind membership. It is not secret
data — it is largely a WDPA export, and WDPA is itself an open dataset — but it *is*
Luk's work, distributed through his channel.

**So this is not a technical question but a question of courtesy, and it is Luk's to
answer.**

What you can put to him, in one sentence: *"Diana is going open source on GitHub. That
means the zone boundaries go online as a data file — they have to, otherwise the map
does not work. May the source KMZ go with it, or do we keep that out of the public
repo?"*

### And then there are two routes

| | If Luk agrees | If Luk would rather not |
|---|---|---|
| Setup | **one public repo** | **two repos**: private for the source, public for the site |
| KMZ | sits in `source/`, public | stays in the private repo |
| Complexity | low | one extra repo and one token |
| Cost | €0 | €0 (2,000 free Action minutes a month is plenty) |

Route 1 is worked out in full below. Route 2 is in §5.

---

## 2. Route 1 — one public repo (recommended if Luk agrees)

### Setting up, once

1. Create a **public** repo on GitHub in the `diana-onff` organisation, named
   `diana-onff.github.io`.
2. Put everything from `diana-repo.zip` into it, plus `ONFF 20260101.kmz` in `source/`.
3. Repo settings → **Pages** → Source: **Deploy from a branch** → branch `gh-pages`,
   folder `/ (root)`. (That branch does not exist yet; it is created on the first
   push. So set this up after the first workflow has run.)
4. Invite the administrator as a **collaborator** with the *Write* role. That is all
   he needs to upload and to merge.

Your site is then at `https://diana-onff.github.io/`.

### What happens automatically

| When | What |
|---|---|
| pull request with a new KMZ | `build-data.yml` converts it and pastes the diff report underneath |
| the same pull request | `pages.yml` publishes a **preview** at `.../preview/pr-12/` and posts that link underneath |
| merge to `main` | the live site is updated |
| pull request closed | the preview is cleaned up |

That preview is deliberate. GitHub Pages does not offer it out of the box — which is
why `pages.yml` publishes to a `gh-pages` branch instead of going through the standard
Pages action. This lets the administrator **look at the real map with the new data
before he merges**, and that is the only check there is.

### What does not go online

`build/site.sh` assembles the folder to be published out of `web/` and the three data
files, and deliberately leaves `source/` out of it. So the KMZ is in the repo tree
(because the Action reads it), but it is not served as part of the website.

---

## 3. What the administrator does

The full procedure, without a single command:

1. Get the new `ONFF_YYYYMMDD.kmz` from the BOS groups.io.
2. On github.com go to `source/` → **Add file → Upload files** → drag the file in →
   at the bottom **Create a new branch for this commit** → **Propose changes**.
3. Wait a few minutes. Two comments appear under the pull request: the diff report and
   the preview link.
4. Open the preview and look at the map.
5. Does it look right? **Merge.** That is publishing.
6. Does it not? Close the pull request. Or, if it has already been merged: **Revert**
   on the merge commit, and the previous version is back.

One administrator is enough. If you want more later, that is a matter of adding a
collaborator.

---

## 4. Limits worth knowing

- **File size in the browser: 25 MiB.** The KMZ is 17 MB, so it fits. If it ever grows
  past 25 MiB, it will have to go through git instead of the web interface.
- **Pages site: 1 GB maximum, and a soft limit of 10 builds per hour.** We are at some
  5 MB per publication and a handful of builds per month.
- **Actions on a public repo are free and unlimited.**
- **The repo history keeps every KMZ forever.** At roughly 17 MB per release and a
  couple of releases a year, it will be years before that runs into anything.

---

## 5. Route 2 — two repos, if the KMZ may not be public

Also entirely inside GitHub.

```
diana-onff/diana-source          (private)  source/ build/ overrides.json  + the conversion Action
      │  pushes data/ and web/ after a merge to
      ▼
diana-onff/diana-onff.github.io  (public)   the site + the data   → GitHub Pages
```

- The administrator uploads in the **private** repo. Everything he sees — the report,
  the approval — stays there.
- A fine-grained token with write access to the public repo only sits as a secret in
  the private repo; the Action uses it to push the built site through.
- Private Actions minutes: 2,000 free per month, and one conversion takes about a
  minute.
- What you give up: the preview URL then lives in the public repo, while the approval
  happens in the private one. Workable, but less straightforward than route 1.

Do not start here. Start with the question to Luk.

---

## 6. If no `gh-pages` appears

That branch is created by the workflow. If it is not there, the workflow has not run
or has got stuck. Work through this, in this order:

**a. Is the `.github` folder actually in the repo?**
This is by far the most common cause. Windows Explorer hides folders that start with a
dot, so anyone who drags the unpacked files into the GitHub web uploader leaves
`.github/` behind without noticing — and then there is no workflow at all. Check on
github.com whether you can see `.github/workflows/pages.yml`. If not: create the file
with **Add file → Create new file**, type `.github/workflows/pages.yml` as the name
(GitHub creates the folders for you) and paste the contents in.

**b. Is there anything in the Actions tab?**
- *No runs at all* → the workflow is not there, or it is on a branch other than
  `main`. Check what your main branch is called.
- *A red run* → open it and read the failed step.

**c. Red at "Publish", with a 403 or "permission denied"?**
Then the token permission setting is still read-only. Settings → Actions → General →
**Workflow permissions** → *Read and write permissions* → Save. After that, run the
workflow again with **Run workflow** in the Actions tab.

**d. Still nothing?**
The workflow also has a manual button. Actions → "Publish to GitHub Pages" → **Run
workflow**. That creates `gh-pages` without you having to push anything.

Only once `gh-pages` exists does it appear in the menu at Settings → Pages.

---

## 7. The very first time

1. **First** set Settings → Actions → General → Workflow permissions to *Read and
   write*.
2. Create the repo, put everything in it, KMZ in `source/` — and check that `.github/`
   came along.
3. Actions → "Publish to GitHub Pages" → **Run workflow**. Now `gh-pages` exists.
4. Settings → Pages → branch `gh-pages`, folder `/ (root)` → Save.
5. Make one pull request (a small change in `overrides.json`, for instance) and check
   that you get two comments: the report and the preview link.
6. **Open the live site and see whether the spots and the heatmap load.** That answers
   the last open question from the plan in ten seconds: will we ever need a proxy, or
   not?

That last step is also the cheapest test in the whole project.
