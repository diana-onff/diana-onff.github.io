# This directory is empty on purpose

The source KMZ files of the countries are **not** in this public repository.

ONFF, for one, distributes its file through the BOS groups.io, behind
membership, and other programmes have their own channels. So these files have
no business sitting on a public URL unasked. That is why they live in a
separate, private repository of the same organisation, and the build fetches
them from there (`source/<PROG>/` per country, `incoming/` for an upload that is
still waiting for review):

| Setting | Where | What |
|---|---|---|
| `SOURCE_REPO` | Settings → Secrets and variables → Actions → **Variables** | `diana-onff/diana-source` |
| `SOURCE_TOKEN` | Settings → Secrets and variables → Actions → **Secrets** | fine-grained token, only *Contents: read* on that repo |

If there is a `.kmz` in this directory after all, the build uses that — as a
safety net during a migration. `.gitignore` stops such a file from being
committed, so that only happens if someone deliberately forces it.

What is and stays public: `data/zones/<prog>.geojson`. Those are the
converted boundaries, and that *is* the app. This setup protects the files,
not the data inside them.
