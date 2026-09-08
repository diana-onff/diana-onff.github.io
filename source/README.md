# This directory is empty on purpose

The ONFF source KMZ is **not** in this public repository.

ONFF distributes that file through the BOS groups.io, behind membership. So it
has no business sitting on a public URL unasked. That is why it lives in a
separate, private repository of the same organisation, and the build fetches it
from there:

| Setting | Where | What |
|---|---|---|
| `SOURCE_REPO` | Settings → Secrets and variables → Actions → **Variables** | `diana-onff/diana-source` |
| `SOURCE_TOKEN` | Settings → Secrets and variables → Actions → **Secrets** | fine-grained token, only *Contents: read* on that repo |

If there is a `.kmz` in this directory after all, the build uses that — as a
safety net during a migration. `.gitignore` stops such a file from being
committed, so that only happens if someone deliberately forces it.

What is and stays public: `data/onff.geojson`. Those are the converted
boundaries, and that *is* the app. This setup protects the file, not the data
inside it.
