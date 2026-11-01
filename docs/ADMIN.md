# Administrator guide

Everything a Diana administrator needs: publishing a new area file (KMZ) for
a country, using the in-app Admin panel, and what to do when something
doesn't work. For the one-time repository setup, see [INSTALL.md](INSTALL.md):
this document assumes that's already done and focuses on the recurring,
day-to-day tasks. For every credential involved, the GitHub security
settings, and how to replace a credential, see [MAINTENANCE.md](MAINTENANCE.md).

---

## 1. Publishing a new release for a country

### Where the file comes from

Regional coordinators do **not** upload anything themselves. They e-mail the
official KMZ of their programme to **wwffmembers@gmail.com**, formatted as
described in the KMZ format guide
([kmz-guide.pdf](https://diana-onff.github.io/kmz-guide.pdf), published with
the site from `web/kmz-guide.pdf`). Someone of the Diana team then uploads it.
That keeps the number of people with a token small: today only the
administrators of the `diana-onff` organisation have one.

For ONFF itself the file is the `ONFF_YYYYMMDD.kmz` that the BOS publishes on
groups.io.

### The normal way: the in-app Admin panel

Upload the file through Diana's own Admin panel (§2). It puts the KMZ in the
waiting room `incoming/<country>/` of the private source repo, starts the
conversion, and opens a pull request in the public repo with a diff report
and a preview of the map. Look at the preview, then **Publish** (merge) or
**Reject**. Publishing *is* going live; nothing else to do.

### Fallback: GitHub's own web interface

Only for the team, and only when the Admin panel cannot be used. Uploading
straight to `source/<country>/` in the private repo skips the waiting room:
there is **no pull request, no diff report and no preview**, and the next
data build (at the latest the nightly one) publishes whatever is in that file.

1. In `diana-onff/diana-source`, open `source/<country>/` → **Add file →
   Upload files** → drag the file in → **Commit changes** on `main`.
2. In the public repo: **Actions → Build map data → Run workflow** (branch
   `main`, leave the branch field empty) to publish it now instead of tonight.
3. Check the live site afterwards. If it is wrong, delete the new file from
   `source/<country>/` (the previous release is the newest again) and run the
   workflow once more.

Through the Admin panel, a **removed zone is real information, not an
error** (programmes do retire reference numbers), so it is always shown in
the diff report, never silently applied without you seeing it first.

---

## 2. The in-app Admin panel

### Getting to it

The Admin screen is hidden by default — not for security (see the token
warning below), but so it isn't a source of confusion for ordinary
visitors. Two ways to reveal it:

- open the app with `?admin=1` in the URL, or
- click the Diana logo/wordmark **five times in a row**.

Either one adds an "Admin" entry to the bottom navigation. Once you have
saved a repository in the panel, Diana remembers it on that device and shows
Admin on every start, until you clear the app's data in the browser.

### Connecting to a repository

Diana works with **two** repositories, because the source KMZ and the
published app do not belong in the same place:

| Field | What goes in it |
|---|---|
| App repo (public) | `owner/repo`, e.g. `diana-onff/diana-onff.github.io` — the app, the data and the workflows |
| Source repo (private) | e.g. `diana-onff/diana-source` — the KMZ files of every country, and nothing else |
| Main branch | usually `main`, and the same name in both |
| Staging folder | where an uploaded file waits for approval — `incoming/`. The country you pick becomes a folder inside it |
| Access token | a GitHub **fine-grained personal access token** |
| "Remember the token on this device" | unticked by default; when ticked, the token is stored encrypted with a passphrase, see below |

Leave the source repo empty and everything goes to the app repo. That is
the arrangement from before the two-repository split; it still works, but
it puts the KMZ in a public repository.

Click **Test the connection** before uploading anything. It checks **both**
repositories and reports the current commit on each, and warns you if the
token cannot write to one of them — better to find that out now than
halfway through sending twenty megabytes.

**Creating the token**, if you don't have one yet: on GitHub, go to
Settings → Developer settings → Personal access tokens → Fine-grained
tokens → Generate new token, and scope it as narrowly as possible:

- **Resource owner:** the organisation, not your personal account. If the
  organisation does not appear in that list, you are not (yet) a *member*
  of it; see the troubleshooting note below.
- **Repository access:** "Only select repositories", and select **both** —
  the public app repo and the private source repo. Never "All repositories".
- **Permissions:** click **Add permissions**, choose **Repository**, and set
  Contents — Read and write, Pull requests — Read and write, Actions — Read
  and write. Actions is what lets the panel start the conversion; without it
  the upload succeeds and then nothing happens. (GitHub has moved this
  behind the "Add permissions" button; older screenshots that show the
  three permissions directly on the page are the same setting, just on an
  earlier version of this screen.)
- **Expiration:** as short as you're willing to renew — a token that
  expires in 90 days is safer than one that doesn't expire at all.

Note that a fine-grained token applies the same permission set to every
repository you select. This token can therefore write to the public repo as
well. That is acceptable for the administrator's own token — you own both
repositories anyway — but it is the reason this token is not the one stored
as a secret in the repository. That one (`SOURCE_TOKEN`, used by the build)
is read-only, and stays read-only.

**"This token cannot write to this repository"**, even though it looks set
up exactly as above: a token can never do more than the person who made
it, so check these in order:

1. **Your own access on both repos.** On github.com, open each repository →
   **Settings → Collaborators and teams**, and check your role there. Being
   a *member* of the organisation is not enough by itself: by default that
   only grants **Read**. You need **Write**, added explicitly on each repo:
   see [MAINTENANCE.md §4](MAINTENANCE.md#4-adding-a-new-content-administrator).
2. **A token waiting for approval.** Some organisations require an owner to
   approve new fine-grained tokens before they can write anything. Check
   **organisation Settings → Personal access tokens → Pending requests**:
   if the token is sitting there, it behaves as read-only until someone
   with Owner rights approves it.
3. **Resource owner and repository selection on the token itself.** Open
   the token on GitHub and confirm it says the organisation (not your
   personal account) and lists both repositories, see the two bullets
   above.

### Uploading a file

Pick the file, then **Upload and convert**. Diana shows the nine steps this
actually takes, each ticking off as it completes:

0. Choosing the country the file is for — see below
1. Reading the base branch (of the source repo)
2. Reading the file, in your browser, before sending
3. Sending the file to GitHub as a blob
4. Updating the tree
5. Creating the commit
6. Writing to the staging folder — `incoming/<country>/` on `main` of the source repo
7. Starting the conversion in the app repo
8. Waiting for the conversion (a minute or two; the counter tells you where it is)
9. Opening the pull request

If a step fails, that step turns red with GitHub's own error message next to
it and the upload button becomes usable again, so you can fix the problem —
usually the token — and retry. Nothing is left half-done, because each step
only starts once the previous one has actually succeeded.

Steps 8 and 9 survive you closing the app: the branch is built on GitHub
regardless, and the next time you open the Admin panel Diana notices the
unfinished upload and opens the pull request then.

**Why you have to pick a country.** A KMZ does not say which programme it
belongs to. The ONFF export carries its reference numbers in the names of its
folders, and nothing says a German or Dutch export does the same — so the only
reliable way to know is to be told. The panel therefore offers every WWFF
programme, with the ones Diana already has boundaries for at the top, and
sends nothing until you have chosen. There is deliberately no preselection: a
wrong guess here would put one country's release in another country's folder,
on top of the file that was already there.

The country becomes a folder: the upload lands in `incoming/<country>/`, and
publishing moves it to `source/<country>/`. Each country's newest file is
converted on its own, so a release for one country can never affect another's
data — see
[ARCHITECTURE.md §2.1b](ARCHITECTURE.md#21b-one-country-per-file-and-a-manifest-over-them).
(A file left over from before this existed, lying loose in `incoming/` or
`source/`, is still read — as ONFF.)

**The file is read before it is sent.** As soon as a file and a country are
both chosen, the panel opens the KMZ on your own device and looks at what is
in it. A line appears under the file:

| | |
|---|---|
| `✓ OZFF — 20+ references found in this file.` | as expected; send it |
| `The areas in this file are DLFF, not OZFF …` | the wrong country was picked. The send button stays shut: the file itself proves the answer, and sending it would put a German release in the Danish folder |
| `No reference number was found anywhere …` | nothing recognisable in it. Sending is still allowed — this may equally be the check's fault, and the conversion will look again properly |
| `Could not check the file here …` | an unreadable zip, or a browser that cannot unpack one. Sending is allowed; nothing has been proven either way |

Only the second line stops you, because it is the only one that is certain.
For a large file the check takes a moment — it is reading the whole thing —
and the send button stays shut until it has finished. If the wrong country
slips past all this anyway, the conversion on GitHub refuses the file with the
same explanation, writes nothing, and leaves the previous data alone.

**Why `incoming/` and not `source/` directly.** The nightly build always
picks the newest KMZ in `source/`. If an uploaded file went straight there,
then rejecting the change would achieve nothing — the next night's build
would quietly use that same file anyway and commit the result itself, going
around the very review this panel exists for. `incoming/` is a waiting room
that the nightly build never looks at. A file only becomes a source once you
have published it.

**What publishing does.** Merging the pull request takes the new data live.
Diana then moves the KMZ from `incoming/<country>/` to `source/<country>/`,
using your own token — the file itself is not re-uploaded, only the tree
entry is rewritten, so this is a handful of small API calls rather than
another twenty megabytes. Rejecting closes the pull request, deletes the
branch, and removes the file from the staging folder.

If you close the app in the seconds between merging and the move, the file
stays in `incoming/`. That is untidy but harmless: nothing reads that folder
on its own. The next time you open the Admin panel, Diana finishes the move.

### Remembering the token: encrypted, with a passphrase

Since v2.2.2 "Remember the token on this device" never stores the token
itself:

1. Fill in the token and tick **Remember the token on this device**.
2. Two fields appear. Type a passphrase of **at least 10 characters**, twice,
   and tap **Remember encrypted**. A few words work best, for example
   `groene specht in het bos`; a short PIN would be guessed in minutes by
   someone who copied the stored data.
3. On the device only the encrypted token is stored (AES-GCM, with a key made
   from your passphrase with PBKDF2-SHA256, 600,000 rounds, all the browser's
   own Web Crypto).
4. Next time you open the Admin panel, the token field is shut and Diana asks
   for the passphrase: type it and tap **Unlock** (or Enter). The token is
   then in memory for that tab only; reloading asks again.
5. A pending upload waits while the panel is locked ("An upload is pending.
   Unlock the token above to follow it up."). After unlocking it is followed
   up exactly as before.
6. **Forgot the passphrase?** Tap **Enter the token again**. The encrypted
   copy is deleted and you paste your token as on the first day. Nothing else
   is lost.
7. **New token?** Paste it over the old one: the stored copy is deleted at
   once and Diana asks for a passphrase again.
8. Untick **Remember** to delete the stored copy.

A token that an older version had stored in plain text is taken off the
device the first time 2.2.2 starts. It stays usable for that one session,
and the panel asks you to choose a passphrase or to untick remember.

There is no limit on wrong attempts: in a browser that would be easy to wipe,
so it would protect nothing. The length of the passphrase is the protection.

### A plain warning about the token

Even encrypted, a remembered token is only as safe as the device and the
passphrase. And while the panel is unlocked, the token is in the page's
memory, readable by any script that runs on that page. This is exactly why:

- the checkbox is **off by default**: the token is only kept in memory for
  that browser tab unless you explicitly ask Diana to remember it
- the token should be fine-grained, limited to the two Diana repositories
  (the public app repo and the private source repo), with only Contents,
  Pull requests and Actions, nothing broader
- never paste the token anywhere else: not in a chat, not in an e-mail, not
  in a file in a repository. GitHub's push protection blocks a token in a
  commit, but not in a message
- give it a short expiration and renew it rather than issuing one that
  never expires
- never tick "remember" on a shared or public computer
- a lost device: delete the token on github.com (your profile picture →
  **Settings → Developer settings → Personal access tokens → Fine-grained
  tokens** → the token → **Delete**) and make a new one

An alternative that needs no passphrase in Diana at all: leave remember
unticked and keep the token in your password manager, then fill it in from
there each time.

### Generating an embed snippet

The same Admin panel has an embed-code generator: fill in a province or
region, a language, and whether the "other WWFF areas" layer should be on,
and it produces a ready-to-paste `<iframe>`:

```html
<iframe src="https://diana-onff.github.io/?embed=1&prov=antwerpen&lang=en&world=1"
        width="100%" height="600" style="border:0"
        loading="lazy" allow="geolocation"></iframe>
```

- The **other WWFF areas** (the blue dots) are off inside an embed unless
  `world=1` is in the address; the checkbox adds it.
- The **spots** are on in every embed. Untick "Spots on by default" and the
  code gets `spots=0`, which hides them (since v2.2.2; older snippets made
  with the box unticked still show spots, add `&spots=0` to those by hand).

`?embed=1` hides Diana's own navigation and header so the map fits cleanly
into someone else's page layout: see
[USER_GUIDE.md §5](USER_GUIDE.md#5-embedding-diana-on-another-page) for the
full parameter reference.

---

## 3. Where the data comes from — and what you actually have to do

Diana joins two sources, and they need different amounts of work from you:

| Source | How it arrives | What you do |
|---|---|---|
| **WWFF directory** (`wwff.co/wwff-data/wwff_directory.csv`): which references exist, their official names, coordinates, QSO counts | **fetched automatically on every data build**, including a build every night at 02:17 UTC. It is regenerated daily at WWFF's end | nothing, normally, see below |
| **A country's KMZ**: the actual boundaries | **the team uploads it**, by hand, when a coordinator sends a new release | upload → check the preview → publish (§1) |

So a new *reference* (a park added to WWFF), a renamed one, a retired one, or
updated QSO counts appear by themselves: a scheduled build runs every night
at 02:17 UTC, for every country, against whatever KMZ is already in
`source/<country>/`. Most nights this changes little and the run ends
quietly. (GitHub may start a scheduled run late on a busy night; that is
normal.)

When the directory *did* change and the build produced good output, that
nightly run **commits straight to `main` by itself** — no pull request, no
waiting for you to click merge. This is a deliberate exception to the
"a human always looks first" rule that governs KMZ uploads: it only ever
touches which references exist, their name, position, or QSO stats — never a
boundary, which still only ever comes from a KMZ you upload by hand — and
only commits when the build hit no errors and every output file actually has
content. If the WWFF directory is unreachable, or the build produces an empty
or missing output file, the run stops **without committing anything**, and
instead opens (or comments on an already-open) GitHub issue labelled
`diana-nachtelijke-build`, so a broken night is a notification you see, not a
silent gap. GitHub notifies whoever watches the repository the same way it
does for any other new issue — as a repository owner you watch your own
repositories by default, so this reaches you as a website notification and,
if you've turned on email for Issues under github.com → Settings →
Notifications, as an email too. A new *boundary*, on the other hand, only
ever appears when you upload a new KMZ — the nightly run never touches
boundaries, and never opens a PR of its own when it succeeds.

If you want the directory refreshed sooner than the next scheduled run, use
**Actions → Build map data → Run workflow** (branch `main`, leave the
branch field empty): same result, no upload needed, and no need to wait for
the night.

You can also point the build at a **CSV of your own** instead of the live URL —
set a repository variable `ONFF_REFS_CSV` (Settings → Secrets and variables →
Actions → Variables) to a URL or to a path inside the repository. Use that if
WWFF ever moves the file, or to test a change before it is live. Nothing about
the upload flow changes; it is the same build either way.

## 3.1 A reference with no boundary

Not every active reference has a polygon in its country's KMZ. Diana draws
those as a dashed ring with an amber dot at an approximate position instead of
hiding them, but it can only do that if it knows where they are.

Each data build reports the state in the diff report, per country, for
example:

> **948 active references** in the directory · **947 with a boundary** from the
> KMZ · **1 as a point** on the map · 16 deleted (not shown)

A reference the directory has no position for at all would be searchable but
appear nowhere on the map. To place one, add a coordinate to `overrides.json`:

```json
"ONFF-0123": {
  "point": [4.4700, 50.8500],
  "_why": "no boundary in the KMZ; point set on the reserve entrance"
}
```

The order is `[longitude, latitude]` — GeoJSON order, so the smaller number
usually comes first in Western Europe. A point set here always wins over the
directory's own coordinate, and survives every future release, because the key
is the reference number. A pull request on `overrides.json` re-runs the build
and shows the result in a preview.

Diana never invents a position: a reference with no coordinate from either
source stays off the map deliberately, because a wrong pin in a nature reserve
is worse than no pin.

---

## 4. Troubleshooting

### No `gh-pages` branch appears

That branch is created *by the workflow*, not by hand. Work through this in
order:

1. **Is `.github/` actually in the repository?** By far the most common
   cause: Windows Explorer hides folders that start with a dot, so
   drag-and-dropping extracted files into GitHub's uploader silently leaves
   `.github/` behind. Check on github.com whether
   `.github/workflows/pages.yml` exists. If not, add it with **Add file →
   Create new file**, type the full path as the filename (GitHub creates
   the folders for you), and paste the contents in.
2. **Check the Actions tab.** No runs at all → the workflow file isn't
   there, or your default branch isn't named `main`/`master`. A red run →
   open it and read the failed step.
3. **Red at the "Publiceren"/publish step, with a 403 or "permission
   denied"?** Settings → Actions → General → Workflow permissions → *Read
   and write permissions* → Save, then re-run the workflow with **Run
   workflow** in the Actions tab.
4. **Still nothing?** Actions → the Pages workflow → **Run workflow**
   manually. This creates `gh-pages` without needing a push at all.

Only once `gh-pages` exists can you select it under Settings → Pages.

### The published site shows the wrong thing, or `source/*.kmz` is exposed

This means GitHub's own built-in "pages-build-deployment" ran instead of the
custom `pages.yml` — almost always because `.github/` was missing (see
above), so Settings → Pages was left on "Deploy from a branch: main /
(root)", which publishes the **entire repository root**, KMZ included. Fix:
add the workflow file properly (via "Create new file", not drag-and-drop),
let it run once, then repoint Settings → Pages to the `gh-pages` branch.

### A new country is published, but the app only offers Belgium

The conversion and the publication are two separate things, and this is the
gap between them. Check in this order:

1. **Is the country in the data?** Open `data/countries.json` on `main`. If
   your country is not in there, the conversion never landed — look at the
   pull request, not at the site.
2. **Did it reach the site?** Open `https://<your-site>/data/countries.json`
   in a browser. A 404, or a file without your country in it, means the
   publication is behind: Actions → *Publish to GitHub Pages* → **Run
   workflow**. `build/site.sh` decides what gets published, and it refuses to
   publish at all if the manifest names a file it cannot find — so a green run
   here means the country really is online.
3. **Is your phone still on the old version?** Close the app fully and reopen
   it. Everything under `data/` is fetched network-first, so one reopen with a
   signal is enough.

Up to v1.17.0 step 2 was permanently broken: `site.sh` still published the
Belgium-only filenames from before Diana had a manifest, so `countries.json`
and `data/zones/` never went online and no second country could be selected,
no matter how often it was rebuilt.

### A pull request doesn't get a diff report or preview link

- **From the Admin panel:** the diff report is in the pull request's own
  description (below the `---`), not in a comment, and the panel shows it on
  its "Pending upload" card. The preview link comes from *Publish to GitHub
  Pages* once *Build map data* has finished; tap **Refresh** on the card.
- **A hand-made pull request:** check that it actually touches
  `source/**.kmz`, `overrides.json`, or `build/**`; those are the only paths
  `build-data.yml` watches. A PR that only touches, say, `docs/` gets a
  preview but no data rebuild, by design.

### Where to see that an upload went wrong

1. In the Admin panel: the step that failed turns red with GitHub's own
   message next to it, and the "Pending upload" card marks a failed workflow
   with ✗.
2. On github.com, in the **public** repo: **Actions**. A red run of *Build
   map data* or *Publish to GitHub Pages*: open it and read the failed step.
3. A failing nightly run opens an issue labelled `diana-nachtelijke-build`
   under **Issues**.

The private source repo has no workflows: its Actions tab stays empty, that
is normal.

### Files left in the waiting room

A file in `incoming/` that no longer belongs to a pull request (for example
after a merge or a close on github.com) is listed on the Admin panel's
**Clean up the staging folder** card, with **Move to source/** and **Delete**.
Removing it by hand on github.com is just as good: delete the file, not the
folder `incoming/` itself (an empty folder disappears from GitHub by itself
anyway). Nothing reads `incoming/` on its own, so a forgotten file is untidy,
never harmful.

---

## 5. What is public and what is not

The app repository is public, and publishing Diana as a web app necessarily
publishes the zone boundaries: every visitor's browser downloads the
converted `data/zones/<prog>.geojson`. The **source KMZ files** are another
matter: they live only in the private `diana-source` repository and are never
published by `build/site.sh`. Keep it that way unless a programme's
coordinator agrees otherwise; see
[DEPLOY.md §1](../DEPLOY.md#1-first-the-question-that-really-matters) and the data-licensing terms in
[LICENSE](../LICENSE).
