# User guide

Diana Fauna & Flora is a map for WWFF, World Wide Flora & Fauna: every WWFF
reference worldwide, the nature reserves of a country with their boundaries,
and the live spots and announced activations from WWFF Spotline on top. It
runs entirely in your browser, works offline with the last data it loaded,
and can be installed like a native app. This guide covers every screen, how
to install it, and, importantly, what it *doesn't* do.

Boundaries are loaded today for Belgium (ONFF), the Netherlands (PAFF),
Germany (DLFF) and Denmark (OZFF). Every other WWFF reference is on the map as
a point.

---

## 1. Supported platforms

Diana is a standard Progressive Web App (PWA): any reasonably modern browser
works, and no app-store install is required.

| Platform | Browser | Works? | Installable as an app? |
|---|---|---|---|
| Android | Chrome, Edge, Samsung Internet | Yes | Yes |
| iOS / iPadOS | Safari | Yes | Yes (via Share → Add to Home Screen) |
| iOS / iPadOS | Chrome, Firefox, etc. | Yes | No: iOS only allows PWA installation from Safari |
| Windows / macOS / Linux | Chrome, Edge, other Chromium browsers | Yes | Yes |
| Windows / macOS / Linux | Firefox, Safari | Yes | Browsing works fully; "install as app" isn't offered by these browsers |

GPS-based features ("am I inside this reserve", distances from you, the
reference filled in for you) need a device with a location sensor and
browser location permission. Without it everything else keeps working, and
Diana uses the locator from Settings as your position instead.

---

## 2. Installing Diana as an app

Installing wraps the same web app in its own icon and window; there is no
separate "app version" with different features.

**The short way: Settings → Install as an app.** Diana does it itself where the
browser allows it. On Android and on desktop Chrome/Edge you get an **Install
on this device** button that triggers the browser's own install prompt; a
one-time banner offers the same thing from the map screen (dismiss it once and
it stays dismissed; the Settings entry is always there).

Where a browser offers no install API, Diana shows the exact steps for *that*
browser instead of a button that would do nothing:

| Your browser | What Diana shows |
|---|---|
| Chrome / Edge (Android, Windows, macOS, Linux) | a working **Install** button |
| Safari on iPhone/iPad | Share **⬆︎** → **Add to Home Screen** |
| Chrome/Firefox/Edge on iPhone/iPad | a note that iOS only allows installing from Safari |
| Safari on macOS | **File ▸ Add to Dock** (Sonoma or newer) |
| Firefox on desktop | a note that Firefox cannot install web apps: bookmark it, or use Chrome/Edge |

Once installed, that card reads "✓ Diana is installed on this device", Diana
opens in its own window without browser chrome, and the service worker (see
[ARCHITECTURE.md §4](ARCHITECTURE.md#4-offline-behaviour-service-worker))
keeps the map and reference data available even with no signal: handy on
activation, where connectivity is exactly what you won't have.

---

## 2.1 Starting up

Diana opens on a start screen (the activation drawing, a radio signal running
across it, a progress line and the version number) while it reads the
reference data and prepares the map. It leaves by itself the moment the map is
actually drawn, and after nine seconds regardless, because being stuck on a
start screen is worse than a bare map. Embedded in someone else's page
(`?embed=1`) it does not appear at all.

## 2.2 The first time: welcome screen, setup wizard and tour

On a device that has never opened Diana, two short things come first.

**The welcome screen** asks two questions and preselects neither:

- **Allow precise location.** Diana uses your GPS to show which reserve you are
  in and which references are nearby. The position is used only on the screen
  in front of you and is never sent to a server. Diana does not ask the browser
  for your position before this screen is answered.
- **Anonymous statistics**: "Yes, I'll help" or "No, rather not". Nothing is
  counted unless you say yes; either way Diana works exactly the same.

**The setup wizard** follows straight on. It starts in English and lets you pick
any of the eight languages on the first step. Then: your station (callsign,
portable callsign, locator, or take it from GPS), your country, your five
quick words for a spot's remark, and the band list for announcements (all
bands or HF only). Every answer is saved into Settings as you go, so stopping
halfway loses nothing. The last step says that everything stays in the browser
of this device, and that clearing the browser data (history, cookies and site
data) or removing the app starts Diana again at the welcome screen.

**The tour** comes after that, if you want it: Diana opens each screen in turn
with a short card explaining what you see. Skip it whenever you like.

Already using Diana? You do not get the wizard automatically. Start it
yourself from **Settings → Run the setup wizard again**; it begins from your
current settings.

---

## 3. The screens

Bottom navigation, left to right: **Map**, **Spots**, **Spot**, **Agenda**,
**Field info**, **Rules**, **Settings**. Coordinators of the Diana team also
see **Admin**.

### Map (◈)

The main screen. At the top: **⌕** search by name or reference number
(every WWFF reference worldwide; the loaded country's results come first, and
a bare number such as `0012` looks only in your own country), **◐** map style (Liberty, Positron, Bright, Dark), and **≡** layers and
language. Tap **Map** in the bottom bar at any time to centre the map on your
own position again; the zoom stays as it is.

**The country you chose in Settings is shown in detail**: every reserve with
its boundary, in green. **Every other WWFF reference in the world** is a blue
point; points close together form a numbered circle that splits apart as you
zoom in (tap it to zoom into it). From zoom 11 each dot is labelled with its
reference. Travelling? Pick the country you visit in Settings; if Diana has
boundaries for it, its reserves appear in full.

**Tap anything to get its panel.** Every panel shows only what is actually
known, never an empty box:

- **A reserve with a boundary** (green): reference, region, name, and whatever
  the area file carries (area in hectares, managed by, designation, IUCN
  category, designated since), the QSO count and last activation from the WWFF
  directory, the locator, the CQ zone, ITU zone and ITU region, and **More
  info**, the reserve's website when the WWFF directory has one. The boundary
  of the selected reserve turns orange.
- **A reference of your country without a boundary** (a dashed ring with an
  amber dot): the same panel without the area figures, and a note that Diana
  cannot tell whether you are inside it, because the marker is only an
  approximate location.
- **A blue dot from another country**: reference, country and name, locator
  and zones, **From you** (bearing and distance), QSOs or **ATNO** in red when
  it was never activated, and More info. When Diana has the boundaries of that
  country but has not loaded them, the panel says so and offers **Show
  <country> in detail**: one tap does the same as picking that country in
  Settings, and the reserve opens again, now with its own boundary. Your spots
  filter is left alone.

Under every panel: **Spot yourself here** and **Announce an activation**.
Both open their form with the reference already filled in.

Panels at the bottom of the screen close by **swiping them down**, or with ×.
On a phone only one bottom panel is visible at a time.

**Am I inside the reserve?** A card at the bottom of the map answers that from
your GPS: inside a reference, inside several at once (when references overlap),
or outside, with the nearest one and its distance. Inside, it also gives the
distance to the nearest boundary.

Finding your position takes a few seconds on purpose. A phone that has just
woken its GPS answers from wifi and cell masts first, and that position can be
hundreds of metres out. So Diana keeps listening while the accuracy improves,
shows what it has so far ("Sharpening the fix… ±380 m"), and only answers the
inside-or-outside question once the fix is good enough, or after twelve
seconds with the sharpest one it got. If that one is still coarse, the answer
says so rather than sounding certain.

Indoors there is a second trap. A wifi position often arrives within a second
claiming twenty metres: that is how accurate the wifi database believes itself
to be, not how accurate this answer is. Diana therefore answers on that fix
straight away, but **keeps listening for the rest of the twelve seconds** and
revises the answer as more readings arrive. Ordinary wobble of a few metres
changes nothing; the marker does not dance.

Every verdict ends with how good the position was ("position ±40 m"), and when
that margin is more than about ten metres, a dashed ring is drawn around the
marker at exactly that radius. A tight ring means satellites; a ring covering
the whole block means the answer came off a wifi network.

Some phones state an accuracy they cannot honour. So Diana keeps the readings
of the last three-quarters of a minute and judges them against each other. A
single wild reading is outvoted and no longer shown. If the readings as a group
contradict each other, the margin becomes the spread you are actually seeing
and the verdict says "readings contradict each other". Walking is not scatter:
what you could have covered on foot between two readings is subtracted first.
When a fix stays worse than about 75 m, a banner suggests checking whether the
site may use your precise location.

**Spots are always on the map.** A green icon with an antenna for each station
on the air now, pulsing, with the callsign, frequency and mode next to it, and a
**dotted green line** from you to it. A spot older than 30 minutes is shown
faded. An announced activation is a white dot with an orange ring and an
**orange dashed line**, labelled with the callsign and time. The lines can be
switched off under ≡ (**Lines to the spots**); the choice is remembered.
**⤢ Fit all spots** re-frames the map to everything shown, your own position
included.

The layers menu (≡) also switches the reference areas, the reference numbers,
the references without a boundary, the spots and the other WWFF areas on and
off, and holds the language buttons.

### Spots (((·)))

**Spots & agenda**, refreshed every 30 seconds, with two tabs:

- **On air**: who is active right now. Each line holds the callsign, the QSO
  count of the reference or **ATNO** in red when it was never activated, the
  frequency, mode and reference, how many minutes ago it was spotted, and the
  bearing and distance from you.
- **Agenda**: every announced activation, with reference, bands and modes, and
  date and time in UTC. One that is running now has an orange dot and "live
  until …"; upcoming ones are grey with their date. **+ Announce** goes to the
  form.

Under the tabs you choose between **your country** and **Worldwide**; the
choice is remembered and kept in step with the same control in Settings. The
country button follows your country setting, which Diana takes from your
callsign until you pick one (PA… offers PAFF, DL… DLFF, ON… ONFF).

Tap a line to open it on the map, zoomed in, with a sheet showing frequency and
mode (or band and mode), the reserve, the locator there and yours, the remark,
the QSO count, More info and a compass with the bearing. **← Back to Spots**,
or Android's back button, returns to the list; × or swiping down closes only
the sheet and keeps the map.

### Spot (✚)

Spot yourself on WWFF Spotline, so hunters can find you. When you are standing
inside a reserve, or came from a panel, the reference is already filled in and
the screen says where it came from. Your callsigns come from Settings. Not
active yet, just planning ahead? The link at the top goes to **Agenda**
instead.

Validation mirrors Spotline's own rules (callsign format, frequency range, a
100-character remark limit), and a band plan check warns if your mode doesn't
match the segment your frequency falls in. The reference is checked against
Diana's own data, so it answers instantly and without a network. The **quick
words** under the remark add your own words (set in Settings) with one tap.

**Two buttons, in this order.** *Check* asks Spotline whether the spot is
acceptable without placing it, and tells you what they said. Only then does
*Send* open. Change anything afterwards and Send closes again: the approval was
for the spot you had, not the one you have now. Two presses rather than one,
because every request comes out of a budget shared with every other Spotline
user.

When a spot goes out you get a real confirmation with its number. Press twice
on a bad connection and Diana says the spot was already there instead of
showing an error. If Spotline refuses something, you get their own
explanation.

**If sending isn't working at all**, Diana offers *Send the old way*: the spot
goes straight to Spotline's own form in a new tab. You see their answer
yourself, but Diana can't confirm anything for you. That way out appears only
when the normal route fails.

### Agenda (▤): announce an activation

Tell people about an activation before it happens. Three doors in: **Agenda**
in the bottom bar, the link at the top of **Spot**, or **+ Announce** on the
Agenda tab of the Spots screen; **Announce an activation** under a map panel
opens it with that reference filled in.

The fields: the activator's callsign, your own callsign (someone else can
announce on an activator's behalf), the WWFF reference, start and end time in
**your own local time** (Diana converts to UTC before it leaves your device),
and optionally the bands, the modes and a remark. Bands and modes are both
multiple choice: an announcement covers an afternoon, so entries read
"40m, 20m, 17m · CW, SSB". Whether the band row offers every band from 160m to
23cm or only 80, 40, 30, 20, 15 and 10m is a choice in Settings.

**The PIN is the only way to edit or cancel this announcement later, on
Spotline's own site; Diana cannot do that for you.** Lose it and there is no
recovery, so Diana keeps a list of everything you announced from this device
(reference, date, PIN) under the form, with ✕ to remove a line. That list lives
only on this device; see §Limitations.

The screen won't let you pick a date more than a month out, or an end before
the start, the same rules Spotline applies. Diana itself allows 16
announcements a day from one device, to protect the shared Spotline budget from
a runaway script; ordinary use stays well under it. Beyond that it works like
spotting: *Check* first, then *Send*. There is no "old way" for an
announcement; if the Worker can't be reached, try again.

### Field info (◎)

What is around you, in three tabs; Diana remembers which one you had open. It
needs your position: a GPS fix, otherwise the locator from Settings (and it
says which).

- **Areas**: the WWFF references around you, within the distance you chose in
  Settings (10, 25, 50 or 100 km), with distance and bearing, the QSO count and
  the last activation. Sort by **Distance**, **Last active** or **QSO count**;
  the last two put the neglected references first. Up to a hundred lines, with
  "Show more". Tap a line to open it on the map. References from other
  countries are in the list too, across the border for instance, and for a
  country without boundaries in Diana they are the whole list. For those,
  Diana knows the QSO count (or ATNO) but not the date of the last activation,
  so they come last when you sort on Last active.
- **Location**: where you are in radio terms. UTC and local time with the time
  zone, your Maidenhead locator in six and eight characters, your position in
  decimal degrees and in degrees, minutes and seconds with its accuracy, your
  CQ zone, ITU zone and ITU region, and the nearest WWFF references anywhere in
  the world. The zone lines come from a public dataset simplified to about 3 km,
  so near a boundary the tile names the neighbouring zone too. Worked out on
  the phone, so it works offline.
- **Conditions**: the space weather and what it means for each band. A dial
  with the Kp index (the official 3-hourly value from NOAA, with the estimate
  of the last minutes beside it), the solar flux (SFI), the A index and the
  sunspot number. Under it, per band (80, 40, 20, 15 and 10 m), a colour bar
  over morning, midday, afternoon, evening and night, worked out from sunrise
  and sunset at your position, with a marker for now and a word: good, fair or
  poor. A minor storm (Kp 5 and 6) only lowers 20, 15 and 10 m; only a strong
  one (Kp 7 or more) lowers 80 and 40 m too. Kp is a worldwide value, not a
  measurement at your position. The figures are fetched twice an hour; the tab
  says how old they are and warns when they are more than eight hours old. It
  is an indication, not a promise.

The QSO counts and last activations come from the WWFF directory, refreshed
every night. Where the directory has nothing on a reference, the screen says so
rather than calling it "never activated".

### Rules (☰)

Two tabs:

- **Rules**: a selection from the official WWFF rules (3.5, 3.6, 4.4, 4.7, 6.8,
  6.9 and 6.11) in your language, grouped by subject, with an example of the
  right name for your log file and links to the full rules. They are WWFF
  rules, so they hold for ONFF too.
- **Band plan**: per band where you may transmit, with the CW, digital and SSB
  segments drawn as a bar, the FT8 frequency marked, and the WWFF preferred
  frequencies highlighted.

### Settings (⚙)

- **Your station**: callsign, portable callsign (e.g. `ON3VZ/P`) and
  Maidenhead locator, with **Take from GPS** and a line saying how good the last
  position was. There is no setting for where the map opens: it always opens
  where you are, falling back to your locator, then your callsign's country.
- **Your country**: one choice for which country's boundaries Diana loads and
  which spots your country button stands for. A line under it says what Diana
  has for that country: how many areas with boundaries, or points only.
  Changing it takes effect immediately. **Show** (your country or Worldwide) is
  the separate spots filter, kept in step with the Spots screen; choosing a
  country never changes it.
- **Quick words on a spot**: five words you can tap onto a spot's remark.
- **Field info**: how far around you the Areas tab looks.
- **Announce**: all bands or HF only.
- **Language**: one of the eight, or "Follow the browser".
- **Privacy**: the Privacy page (what stays on the device, which outside
  services Diana talks to and why), your statistics choice, and a button that
  clears everything Diana stored on this device.
- **Install as an app**, see §2.
- At the bottom: the version and data line, **Check for updates**, **What's
  new** (the release notes, newest first) and **Run the setup wizard again**.

Everything here stays in the browser of this device; see §Limitations.

### Admin (⛭, hidden)

For the Diana team only: uploading a country's area file and generating embed
codes. Hidden until `?admin=1` is used or the Diana logo is tapped five times,
and useless without a GitHub token. Regional coordinators do not use it: they
send their KMZ to the team, see [ADMIN.md](ADMIN.md).

---

## 4. Languages

Diana is available in English, Dutch, French, German, Danish, Italian,
Spanish and Portuguese. Set yours in **Settings → Language**, in the layers
menu (≡) on the map, or on the first step of the setup wizard. Language is
chosen, in order: the `?lang=` URL parameter, then your saved setting,
otherwise **English**. Your browser's language is used only if you explicitly
pick **Follow the browser**. Switching language re-renders every screen
immediately. Reserve names are never translated: they are official names and
belong in activation logs exactly as published. The release notes ("What's
new") are in Dutch and English.

---

## 5. Embedding Diana on another page

Diana can be dropped into any web page as an iframe: a club site, a blog,
anything that accepts HTML.

```html
<iframe src="https://diana-onff.github.io/?embed=1&prov=antwerpen&lang=en"
        width="100%" height="600" style="border:0"
        loading="lazy" allow="geolocation"></iframe>
```

| Parameter | Effect |
|---|---|
| `?embed=1` | hides Diana's own navigation and header, so it fits inside someone else's page |
| `?lang=en\|nl\|fr\|de\|da\|it\|es\|pt` | forces a language |
| `?ref=ONFF-0104` | opens directly zoomed to one reference |
| `?prov=antwerpen` | zooms to a region of the loaded country |
| `?spots=0` | hides the live spots, which are on by default, in an embed too |
| `?world=1` | shows the other WWFF areas, which are off by default in an embed |
| `?admin=1` | reveals the Admin panel (not meaningful in an embed) |

In an embed the worldwide points stay off unless `?world=1` is present, so an
iframe already published somewhere does not suddenly start downloading them.
The welcome screen and the start screen do not appear in an embed.

The Admin panel includes a small form that builds this snippet for you, see
[ADMIN.md §Generating an embed snippet](ADMIN.md#generating-an-embed-snippet).

---

## 6. Limitations

**Everything is stored on this one device, in this one browser; nothing
syncs.** Your callsigns, locator, country, quick words, language, statistics
choice, the PINs of announcements you made and (if you ticked it) a remembered
Admin token (encrypted) all live in that browser's local storage. Open Diana on your phone
and then on your laptop, and you set it up again on the laptop: Diana has no
account system to tie the two together. Clearing the browser's site data,
using a private window, or removing the installed app clears these settings,
and Diana starts again at the welcome screen.

**Live data depends on a third party Diana doesn't control.** Spots and the
agenda come from WWFF Spotline (see
[ARCHITECTURE.md §2.3](ARCHITECTURE.md#23-wwff-spotline-live-spots-agenda-self-spotting)).
If it is unavailable, the Spots screen says so rather than showing stale data
silently. The band conditions come from NOAA, and the tab says how old they
are. Everything else ships with the release.

**Boundaries exist only where an area file was supplied.** Today that is
Belgium, the Netherlands, Germany and Denmark. Elsewhere every reference is
there as a point, at the position the WWFF directory gives, and Diana cannot
tell whether you are inside it. Within those four countries a handful of
references also have no polygon (overseas areas of the Netherlands, for
instance) and are shown as a dashed ring. Which references exist comes from the
WWFF directory and refreshes by itself every night; the boundaries come from a
file the Diana team publishes, so a brand-new reserve can appear as a point
first and gain its outline later.

**Not every reserve has full details.** Many reserves have no attributes
beyond a name and reference number; that is a gap in the source data, not
something the app is hiding.

**Data usage terms.** The boundaries and activation figures shown in Diana come
from the WWFF programmes, WDPA, government sources and WWFF Spotline, and remain
their owners' data. Diana's *code* is source-available under the PolyForm
Noncommercial License (personal, hobby and noncommercial use only), and the
*data and content* may not be freely redistributed or reused elsewhere without
permission either. See [LICENSE](../LICENSE).

**Privacy.** Settings has its own Privacy page: what stays on the device, which
outside services Diana talks to and why, the anonymous-statistics choice
(asked once, never on by default, and without cookies), and a button that
clears everything Diana has stored on that device. Spotting yourself sends
your callsign, frequency, mode and reference to WWFF Spotline, never your
position.

**Precise location.** Diana always asks the browser for the most precise
position it can give, but whether a site gets the exact position or a
deliberately blurred one is the phone's or browser's setting, not Diana's.
When a fix stays wider than about 75 m, the welcome screen and the Privacy
page show the steps to switch precise location on for that phone (Android,
iPhone with Safari, iPhone with another browser, or a computer).
