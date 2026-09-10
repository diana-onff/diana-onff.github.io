# Deploying Diana

Diana runs on two GitHub repositories and one Cloudflare Worker, all on free
tiers. This document is the short orientation — what runs where, and why it's
split the way it is. It assumes the setup already exists; for building it
from nothing, see [docs/INSTALL.md](docs/INSTALL.md). For day-to-day
publishing, see [docs/ADMIN.md](docs/ADMIN.md). For every credential involved
and how to replace one, see [docs/MAINTENANCE.md](docs/MAINTENANCE.md).

---

## 1. First, the question that really matters

> "Downside: it's public. But the data shouldn't just be up for grabs, should it?"

There are two different things bundled in that question.

**The zone boundaries are public regardless.** Diana is a static web app:
every visitor's browser downloads `onff.geojson` to draw the map — that's how
a static map works, on any hosting, public repository or not. Publishing
Diana *as a web app* already means publishing the boundaries. They are
already public in practice today, in the ONFF blog's own embedded Google My
Maps.

**Making the *repository* public adds exactly one more thing: the original
KMZ file**, redistributed on a second channel outside ONFF's own
membership-gated groups.io. That file is largely a WDPA export (itself open
data), but distributing it is a courtesy question for ONFF's coordinator, not
a technical one — which is why this project keeps that one file out of the
public repository entirely, in a private repo of its own. See
[LICENSE](LICENSE) for the data-licensing terms this rests on.

---

## 2. What actually runs where

```
diana-onff/diana-onff.github.io   (public)    the app, data/, docs/, the two
                                                GitHub Actions workflows, and
                                                the Worker's source code
        │
        │  build-data.yml checks this repo out with SOURCE_TOKEN,
        │  read-only, to reach the KMZ
        ▼
diana-onff/diana-source            (private)   only the ONFF KMZ files, and
                                                an `incoming/` waiting room for
                                                an upload nobody has approved yet

diana-spotline (Cloudflare Worker)             holds WWFF_API_KEY; the only
                                                thing in the project that ever
                                                sees it — see SPOTLINE.md
```

This is Route 2 from the two options this project originally weighed — one
public repository, or a public/private split. The split was chosen because
the KMZ deserves the courtesy of staying off a second public channel; the
public repository still holds everything that makes the site work, including
the workflows and the Worker's code, so nothing about running or publishing
Diana needs access to the private repository directly — only the nightly
build's own token does.

Both repositories cost nothing on GitHub's free plan: unlimited private
repositories, and Actions minutes are unlimited on the *public* repo (the
private one has no workflow of its own — it only gets checked out by the
public repo's build). The Worker is free on Cloudflare's tier as well; see
[MAINTENANCE.md §8](docs/MAINTENANCE.md#8-limits-worth-watching) for the
actual ceilings and how far normal use sits below them.

---

## 3. Publishing a new release, day to day

This is now [docs/ADMIN.md §1](docs/ADMIN.md#1-publishing-a-new-onff-release)
in full — either a plain GitHub upload or Diana's own in-app Admin panel, both
ending at the same pull request and the same preview-then-merge review. It
isn't duplicated here to avoid the two documents drifting apart the way this
one drifted from reality before this rewrite.

---

## 4. Limits worth knowing when deploying

- **GitHub's web upload limit is 25 MiB per file.** The ONFF KMZ is around
  17 MB, so it fits; past 25 MiB it would need to go through git instead.
- **GitHub Pages: 1 GB site, and a soft limit of roughly 10 builds an hour.**
  Diana publishes a few megabytes, a handful of times a month.
- The full list, including the ones that matter for ongoing operation (KV
  writes, the shared WWFF budget, Actions minutes) is in
  [MAINTENANCE.md §8](docs/MAINTENANCE.md#8-limits-worth-watching) — kept
  there rather than here so there is one place to check, not two that can
  disagree.

---

## 5. If something isn't working

[docs/ADMIN.md §4 Troubleshooting](docs/ADMIN.md#4-troubleshooting) covers
the recurring failure modes: no `gh-pages` branch, a 403 on publish, the
wrong thing published, or a pull request that gets no diff report. Building
from zero and hitting a snag along the way is covered directly in
[docs/INSTALL.md](docs/INSTALL.md), step by step, with a checkpoint after
each one.
