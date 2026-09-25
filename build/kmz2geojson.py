#!/usr/bin/env python3
"""
Diana — WWFF KMZ to GeoJSON pipeline.

Reads an official Google Earth release for one WWFF programme (ONFF, DLFF, …)
and produces the static data files the Diana PWA loads. One country per run, so
that a bad file for one of them cannot touch another one's data — hence the
per-country folder. <slug> below is the programme in lower case: onff, dlff.

Per country, in data/zones/:

    zones/<slug>.geojson    zone geometry, one MultiPolygon feature per reference
    zones/<slug>-index.json lightweight index (no geometry) for search, lists and
                            "nearest zones" without loading the full geometry file
    zones/<slug>-points.geojson  references that exist on the programme's list but
                            have no polygon in the KMZ, as single Point features
    zones/<slug>-activity.json   QSO count and last activation per reference

Shared by every country, in data/:

    data/countries.json     the manifest: which countries have boundaries, and which
                            files each one is made of. MERGED per run, never rewritten.
                            This is the only way the app learns a country exists —
                            and the only way build/site.sh knows what to publish
    data/meta.json          provenance: which source file, which release, what settings
    data/wwff-programs.json every WWFF programme in the directory mapped to its country
                            (worldwide) — lets the app's spots screen offer a "just this
                            country" filter without shipping a hand-kept list
    data/wwff-world.geojson EVERY active WWFF reference worldwide, this run's own
                            programme included, as bare Points — ref and name only,
                            never a boundary; this is the "other WWFF areas" layer.
                            Nothing is left out here on purpose: this file is shared
                            by every viewer, and each one has only ONE country's
                            boundaries loaded at a time — which one is a per-viewer
                            choice the app already makes correctly, dynamically
                            (worldFilteredData() in map.js). A build-time exclusion
                            can only ever be right for whichever country a build
                            happens to touch, not for whatever any given viewer
                            actually has loaded. See the comment at the write itself.
                            Positions are the directory's, except where that lies
                            more than 2 km outside a boundary Diana has (then a
                            point inside it, see _world_corrections()) or where
                            overrides.json places a point by hand
    data/wwff-activity.json QSO count for EVERY active WWFF reference worldwide,
                            every programme included, for a spot's or an
                            announced activation's reference: ref -> count,
                            nothing else. 0 means never activated (ATNO on the
                            spots screen). Published by build/site.sh alongside
                            wwff-world.geojson

Nothing is written to data/<slug>.geojson at the top level any more. Files by
those names may still be lying around from before the manifest; they are a
fallback for an old service worker, they are not kept up to date, and
build/site.sh publishes them only if they happen to exist.

It also writes a human-readable diff report against the previous index, which the
GitHub Action posts under the pull request and the /admin page renders in plain
language. See "Diana - Technisch plan" §2.

Usage
-----
    python build/kmz2geojson.py --kmz "source/ONFF 20260101.kmz"

Notes
-----
* The ONFF reference number is NOT stored in a data field. It lives in the name of
  the enclosing Document/Folder, as "ONFF-nnnn <name>". Names contain typos and
  duplicates, so we key everything on the number and never on the name.
* The KMZ embeds a Maidenhead grid layer (~32.700 placemarks) which we drop: a grid
  is cheaper to compute in the client than to ship.
* Attribute coverage is uneven (roughly 38% WDPA fields, 7% Flemish fields, 46%
  nothing at all), so every attribute is optional and callers must degrade
  gracefully.
* The ONFF index sheet lists ~965 references; the KMZ contains ~932 polygons. The
  remainder are real references with no boundary. They are emitted as Points (see
  --refs-csv) so they are visible on the map instead of silently absent, but a
  point is explicitly not a boundary: the app must not run "am I inside" on them.
"""

from __future__ import annotations

import argparse
import difflib
import gzip
import json
import math
import re
import sys
import unicodedata
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from lxml import etree
from pyproj import Geod
from shapely.geometry import MultiPolygon, Point, Polygon, mapping, shape
from shapely.ops import nearest_points, unary_union

KML_NS = "{http://www.opengis.net/kml/2.2}"
# Which programme this run is converting, and the pattern that finds its
# reference numbers in the KMZ. Both are set by main() from --program: Diana
# started as a Belgian app with ONFF baked in, and a second country must be a
# flag on a build rather than an edit to this file.
PROGRAM = "ONFF"
# The (?!\d) keeps a release date such as "ONFF 20260801.kmz" from reading as
# "ONFF-2026": without it \d{4} happily grabs the first four digits of an
# eight-digit date and calls that a reference. A real reference is never
# immediately followed by a fifth digit, so this costs nothing on real names.
REF_RE = re.compile(r"ONFF[- ]?(\d{4})(?!\d)")
# Every WWFF reference worldwide, e.g. ONFF-0104, GFF-0231, VKFF-1234.
FF_RE  = re.compile(r"\b[A-Z0-9]{1,3}FF-\d{3,5}\b")
GEOD = Geod(ellps="WGS84")

# Folders in the KMZ that are not ONFF zones.
SKIP_FOLDERS = {"Maidenhead grid by OH2ECG"}

# Extra thematic layers that sit alongside the provinces. Kept out of the main
# output for now; the MVP is ONFF only.
NON_PROVINCE_FOLDERS = {"National parks", "Natura2000", "Ramsar", "Antartica"}

SCRIPT_VERSION = "1.1.0"


# --------------------------------------------------------------------------- #
# KML reading
# --------------------------------------------------------------------------- #

def _name(el) -> str | None:
    node = el.find(KML_NS + "name")
    return node.text if node is not None and node.text else None


def _ring(linear_ring) -> list[tuple[float, float]]:
    """Parse a KML <LinearRing> into a list of (lon, lat) tuples."""
    text = linear_ring.find(KML_NS + "coordinates").text
    pts = []
    for chunk in text.split():
        parts = chunk.split(",")
        if len(parts) >= 2:
            pts.append((float(parts[0]), float(parts[1])))
    return pts


JUNK_NAMES = {"sql_statement", "naamloos plaatsmarkering", "untitled placemark", ""}


def _clean_name(raw: str) -> str:
    """Strip the reference prefix and any leftover file extension."""
    name = REF_RE.sub("", raw)
    name = re.sub(r"\.(kml|kmz|shp|gpx)$", "", name.strip(), flags=re.I)
    return name.strip(" -–—_")


def _looks_like_filename(name: str) -> bool:
    """'zwinduinen-en-polders' is an import filename, 'Zwinduinen en Polders' is a name."""
    return " " not in name and bool(re.search(r"[a-z0-9]-[a-z0-9]", name))


def pick_name(counts, ref: str) -> str:
    """
    Choose the best display name out of every spelling found in the KMZ.

    Many zones carry three or four variants (typos, capitalisation, and the name of
    the .kml file they were imported from). Preference order: a name that does not
    look like a filename, then the spelling that occurs most often, then the longest.
    """
    candidates = {}
    for raw, hits in counts.items():
        cleaned = _clean_name(raw)
        if cleaned.lower() in JUNK_NAMES:
            continue
        candidates[cleaned] = candidates.get(cleaned, 0) + hits
    if not candidates:
        return ref
    best = max(candidates, key=lambda c: (not _looks_like_filename(c), candidates[c], len(c)))
    if _looks_like_filename(best):
        best = _titlecase(best.replace("-", " ").replace("_", " "))
    return best


# Words that stay lowercase inside a name, in the three languages that occur.
SMALL_WORDS = {"de", "den", "der", "het", "van", "en", "op", "aan", "ter", "te", "'t",
               "du", "des", "la", "le", "les", "et", "aux", "sur", "sous", "of", "the"}


def _titlecase(name: str) -> str:
    """Capitalise a filename-derived name without shouting at the connecting words."""
    words = name.split()
    out = []
    for i, word in enumerate(words):
        if i > 0 and word.lower() in SMALL_WORDS:
            out.append(word.lower())
        else:
            out.append(word[:1].upper() + word[1:])
    return " ".join(out)


def _extended_data(placemark) -> dict[str, str]:
    """Return the SimpleData fields of a placemark, empty values dropped."""
    schema = placemark.find(".//" + KML_NS + "SchemaData")
    if schema is None:
        return {}
    out = {}
    for field in schema.findall(KML_NS + "SimpleData"):
        value = (field.text or "").strip()
        if value and value not in ("Not Reported", "Not Applicable"):
            out[field.get("name")] = value
    return out


def _ancestor_ref_candidates(placemark) -> list[tuple[str, str]]:
    """Every <PROG>-nnnn name found from the placemark itself up to the root,
    nearest first, consecutive repeats collapsed. Almost always this is one
    reference, sometimes repeated at several levels; _resolve_ref() decides
    what to do when it is not."""
    found: list[tuple[str, str]] = []
    node = placemark
    while node is not None:
        name = _name(node)
        if name:
            match = REF_RE.search(name)
            if match:
                ref = PROGRAM + "-" + match.group(1)
                raw = re.sub(r"\.kml$", "", name).strip()
                if not found or found[-1][0] != ref:
                    found.append((ref, raw))
        node = node.getparent()
    return found


def _norm_name(name: str) -> str:
    """Lower case, no reference prefix, no accents, no punctuation, so that
    'Kollintenbos' and 'Kollinten-bos.kml' compare as the same thing."""
    name = _clean_name(name)
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def _name_score(raw: str, official: str) -> float:
    """How well one KMZ-side name matches a reference's official WWFF-directory
    name. 1.0 when either is a plain substring of the other (short official
    names are common), otherwise plain string similarity."""
    a, b = _norm_name(raw), _norm_name(official)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def _resolve_ref(candidates: list[tuple[str, str]],
                  directory_names: dict[str, str]) -> tuple[str | None, str | None, str | None]:
    """Pick the reference for one placemark out of every <PROG>-nnnn name found
    among it and its ancestors.

    Normally there is exactly one, or none. When the names disagree, the
    nearest container is not automatically the correct one: real ONFF releases
    have both grouped several sub-areas under one broader outer label (where
    the closer, more specific name is right) and carried a plain typo in the
    innermost placemark's own number while an outer container had it right
    (see ONFF-0253/0254 and ONFF-0076/0079), and the two look identical from
    tree position alone. The tie is broken by the WWFF directory instead: whichever
    candidate's official name best matches the disagreeing name here wins.

    Returns (ref, raw_name, note). note is set only when there really was a
    disagreement to resolve, for the conversion report.
    """
    if not candidates:
        return None, None, None
    nearest_ref, nearest_raw = candidates[0]
    distinct = sorted({ref for ref, _ in candidates})
    if len(distinct) == 1 or not directory_names:
        return nearest_ref, nearest_raw, None

    best_ref, best_raw, best_score = nearest_ref, nearest_raw, -1.0
    for ref, raw in candidates:
        official = directory_names.get(ref)
        if not official:
            continue
        score = _name_score(raw, official)
        if score > best_score:
            best_ref, best_raw, best_score = ref, raw, score

    official = directory_names.get(best_ref)
    note = (f"one placemark's name disagreed between {', '.join(distinct)}; the WWFF "
            f"directory's name for {best_ref}" + (f" ('{official}')" if official else "") +
            " matched best, so it was used" +
            ("" if best_ref == nearest_ref else f" instead of the nearer {nearest_ref}"))
    return best_ref, best_raw, note


def _foreign_program(placemark) -> str | None:
    """Which OTHER programme the names around this placemark point at.

    Only asked when the reference for the programme being built was not found.
    Getting a whole file back with nothing in it is nearly always one mistake —
    the wrong country picked in the admin panel — and the file itself can say
    so, which beats "0 areas" as an explanation.
    """
    node = placemark
    while node is not None:
        name = _name(node)
        if name:
            match = FF_RE.search(name.upper())
            if match:
                return match.group(0).split("-")[0]
        node = node.getparent()
    return None


def _placemarks(container):
    """Yield (placemark, province, layer) for everything in the file that counts.

    Three shapes have turned up in real WWFF releases, and they do not agree
    with each other:

        ONFF   Document > Folder per province > Document per area > Placemark
        DLFF   Document > one Folder holding everything > Placemark per area
        OZFF   Folder   > Document per area > Placemark

    Diana read the first one and nothing else: it looked for <Document> at the
    root (Denmark has <Folder> there and the build stopped dead), and it looked
    for the areas inside folders one level down (Denmark has none, so even past
    that it would have written an empty country without complaining). Both are
    handled here, in one place, so that the rest of the conversion never has to
    know which shape it came from.
    """
    folders = [c for c in container
               if c.tag == KML_NS + "Folder" and _name(c) not in SKIP_FOLDERS]
    # A division into one is not a division. Germany ships the lot in a single
    # folder called "DLFF-Gebiete"; writing that into all 1326 areas as their
    # province would be worse than leaving the field empty, because it reads
    # like information.
    named = len(folders) > 1
    for folder in folders:
        name = _name(folder)
        layer = name if name in NON_PROVINCE_FOLDERS else None
        province = None if (layer or not named) else name
        for placemark in folder.iter(KML_NS + "Placemark"):
            yield placemark, province, layer
    # Areas sitting straight under the root container, with no grouping folder
    # around them at all — the Danish shape. There is no province to be had
    # here, only areas.
    for child in container:
        if child.tag in (KML_NS + "Document", KML_NS + "Placemark"):
            for placemark in child.iter(KML_NS + "Placemark"):
                yield placemark, None, None


def extract_kmz(kmz_path: Path, workdir: Path) -> Path:
    """Unpack doc.kml from the KMZ. Returns the path to the extracted KML."""
    workdir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(kmz_path) as archive:
        kml_names = [n for n in archive.namelist() if n.lower().endswith(".kml")]
        if not kml_names:
            raise SystemExit(f"No .kml found inside {kmz_path}")
        # Google Earth always names the main document doc.kml; fall back to the first.
        target = "doc.kml" if "doc.kml" in kml_names else kml_names[0]
        out = workdir / "doc.kml"
        out.write_bytes(archive.read(target))
    return out


# --------------------------------------------------------------------------- #
# Geometry
# --------------------------------------------------------------------------- #

def area_hectares(geom) -> float:
    """Geodesic area in hectares (WGS84), sign-independent."""
    area_m2, _ = GEOD.geometry_area_perimeter(geom)
    return round(abs(area_m2) / 10_000.0, 1)


def round_geometry(geom, decimals: int):
    """Round every coordinate. Five decimals is ~1 m, well under GPS accuracy."""
    def _round_coords(coords):
        return [(round(x, decimals), round(y, decimals)) for x, y in coords]

    polys = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
    out = []
    for poly in polys:
        shell = _round_coords(poly.exterior.coords)
        holes = [_round_coords(r.coords) for r in poly.interiors]
        try:
            rounded = Polygon(shell, holes)
        except Exception:
            continue
        if rounded.is_valid and not rounded.is_empty:
            out.append(rounded)
        else:
            fixed = rounded.buffer(0)
            if not fixed.is_empty:
                out.append(fixed)
    if not out:
        return None
    merged = unary_union(out)
    return merged if isinstance(merged, MultiPolygon) else MultiPolygon([merged])


# --------------------------------------------------------------------------- #
# Attribute mapping
# --------------------------------------------------------------------------- #

# The KMZ stores the managing authority as an abbreviation. Spelled out here so
# the app can show something a human recognises. Extend via overrides.json.
MANAGER_NAMES = {
    "ANB": "Agentschap Natuur & Bos",
    "DNF": "Département de la Nature et des Forêts",
    "NP": "Natuurpunt",
    "RNOB": "Natagora / RNOB",
}


def attributes_from(data: dict[str, str]) -> dict:
    """Normalise the two competing schemas in the KMZ into one flat dict."""
    out: dict[str, object] = {}

    # WDPA schema (uppercase) — about 38% of polygons.
    if data.get("DESIG_ENG") or data.get("DESIG"):
        out["desig"] = data.get("DESIG") or data.get("DESIG_ENG")
        out["desig_en"] = data.get("DESIG_ENG")
    if data.get("IUCN_CAT"):
        out["iucn"] = data["IUCN_CAT"]
    if data.get("MANG_AUTH"):
        code = data["MANG_AUTH"].strip()
        out["manager"] = MANAGER_NAMES.get(code, code)
        out["manager_code"] = code
    if data.get("STATUS_YR"):
        out["status_year"] = data["STATUS_YR"]
    if data.get("WDPA_PID"):
        out["wdpa_pid"] = data["WDPA_PID"]

    # Flemish schema (lowercase) — about 7%.
    if not out.get("desig") and data.get("desig"):
        out["desig"] = data["desig"]
    if not out.get("iucn") and data.get("iucn_cat"):
        out["iucn"] = data["iucn_cat"]
    if data.get("inspireid"):
        # "NatuurbeheerplanType4-NBP-AN-18-0007G" -> "NBP-AN-18-0007G"
        out["registration"] = data["inspireid"].split("-", 1)[-1] if "-" in data["inspireid"] else data["inspireid"]
        marker = "NBP-"
        if marker in data["inspireid"]:
            out["registration"] = data["inspireid"][data["inspireid"].index(marker):]
    if data.get("sub_loc") and not out.get("region"):
        out["region"] = data["sub_loc"]

    return out


# --------------------------------------------------------------------------- #
# Main conversion
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# The WWFF directory — the authoritative list of references
#
# https://wwff.co/wwff-data/wwff_directory.csv is regenerated daily and holds
# every WWFF reference worldwide (~68.000 rows, 190 programmes), each with a
# status, an official name, coordinates and an IARU locator. For Diana it does
# two jobs the KMZ cannot:
#
#   1. it says which references EXIST (the KMZ only says which have a boundary)
#   2. it gives a position for the ones that have no boundary yet
#
# The two sources are joined on the reference number, and a reference is only
# ever used once: if the KMZ has a polygon for it, that polygon wins and the
# directory row is used only to fill gaps and to cross-check. Otherwise it
# becomes a Point. That is what keeps duplicates out.
#
# Rows with status != active are skipped entirely — the directory keeps deleted
# references around, renamed to "DELETED AREA - …", and putting those on a map
# would be worse than leaving them off. So are null-island rows (0,0 / JJ00AA),
# which is how the directory marks "position unknown".
# --------------------------------------------------------------------------- #

WWFF_DIRECTORY = "https://wwff.co/wwff-data/wwff_directory.csv"

# The columns actually in wwff_directory.csv, in the order it publishes them:
#   reference, status, name, program, dxcc, state, county, continent, iota,
#   iaruLocator, latitude, longitude, IUCNcat, validFrom, validTo, notes,
#   lastMod, changeLog, reviewFlag, specialFlags, website, country, region,
#   dxccEnum, qsoCount, lastAct
# Read by name, never by position, so a new column in the middle is harmless.

# Region codes the directory uses for Belgium. A row can carry more than one
# ("OV,NP-SV" = East Flanders plus a national-park overlay); the first wins.
BE_REGIONS = {
    "AN": "Antwerpen", "LB": "Limburg", "OV": "Oost-Vlaanderen",
    "VB": "Vlaams-Brabant", "WV": "West-Vlaanderen", "BR": "Brussel",
    "BW": "Brabant Wallon", "HT": "Hainaut", "LG": "Liège",
    "LX": "Luxembourg", "NR": "Namur", "ANT": "Antarctica",
}

# "51.2345, 4.5678" in one cell — only used for a CSV that has no lat/lon columns.
PAIR_RE = re.compile(r"(-?\d{1,3}[.,]\d+)\s*[,;/|]\s*(-?\d{1,3}[.,]\d+)")

# Rough envelope of Belgium, used only to tell latitude from longitude apart in
# that fallback. Named columns are trusted as-is — ONFF-0004 sits in Antarctica.
BE_LAT = (49.0, 52.0)
BE_LON = (2.0, 7.0)


MOJIBAKE_HINTS = ("Ã", "â€", "Â", "Å", "Ð")


def _demojibake(text: str) -> str:
    """Repair text that was UTF-8, got read as Windows-1252, and re-saved as UTF-8.

    The WWFF directory hands us some 437 names double-encoded: "Vallée de
    l'Ecaillon" arrives as "VallÃ©e de lâ€™Ecaillon". That is not a misread on
    our side — those characters really are in the file that way — but we do
    display it, so we repair it here, in one place, for every field.

    The reversal is only valid if it comes out exactly right: if the way back
    fails, or does not yield valid UTF-8, then the text was already fine
    (Portuguese "Âncora", Spanish "Ávila") and we leave it alone.
    """
    if not text or not any(hint in text for hint in MOJIBAKE_HINTS):
        return text

    # Per contiguous run of non-ASCII, not over the whole text in one go. The
    # directory also hands us half-mangled names: in "Vallée de lâ€™EscriÃ¨re"
    # the first é is already fine and the rest is not. Over the whole string the
    # way back then fails on that good é, and everything stays broken.
    def repair(match: re.Match) -> str:
        run = match.group(0)
        raw = bytearray()
        for ch in run:
            try:
                raw += ch.encode("cp1252")
            except UnicodeEncodeError:
                if ord(ch) > 0xFF:              # can never have come from one byte
                    return run
                raw.append(ord(ch))             # cp1252 has no 0x81/0x8D/0x9D
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return run                          # was already fine (Portuguese "Âncora")

    return re.sub(r"[^\x00-\x7f]+", repair, text)


def _read_rows(source: str, timeout: int = 120) -> list[dict[str, str]]:
    """Read a CSV from a local path or a URL into a list of dicts."""
    import csv
    import io

    if re.match(r"^https?://", source):
        import urllib.request
        req = urllib.request.Request(source, headers={"User-Agent": "Diana/1.0 (ONFF map build)"})
        with urllib.request.urlopen(req, timeout=timeout) as fh:
            text = fh.read().decode("utf-8", "replace")
    else:
        text = Path(source).read_text(encoding="utf-8", errors="replace")

    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(text), dialect))
    if not rows:
        return []

    # The header is not always the first line — a hand-made sheet often starts
    # with a title row. The header is the row above the first ONFF/xxFF number.
    first_data = next((i for i, row in enumerate(rows[:12])
                       if any(REF_RE.search(cell or "") or FF_RE.search(cell or "") for cell in row)), 1)
    header_at = max(first_data - 1, 0)
    header = [(c or "").strip() for c in rows[header_at]]
    seen: dict[str, int] = {}
    for i, name in enumerate(header):
        key = name or f"col{i}"
        if key in seen:
            seen[key] += 1
            key = f"{key}_{seen[key]}"
        else:
            seen[key] = 0
        header[i] = key

    out = []
    for row in rows[header_at + 1:]:
        if not any((c or "").strip() for c in row):
            continue
        out.append({header[i] if i < len(header) else f"col{i}": _demojibake((row[i] or "").strip())
                    for i in range(len(row))})
    return out


def _to_float(raw: str) -> float | None:
    raw = (raw or "").strip().replace("°", "")
    if not raw:
        return None
    try:
        value = float(raw.replace(",", ".")) if raw.count(",") <= 1 else None
    except ValueError:
        return None
    # float() also accepts "nan" and "inf". Neither is a coordinate or a QSO
    # count, and int(nan) raises: one such cell anywhere in the worldwide
    # directory would otherwise stop the build for every country.
    return value if value is not None and math.isfinite(value) else None


def _orient(a: float, b: float) -> tuple[float, float] | None:
    """Given two numbers from one cell, return (lat, lon) if we can tell which is which."""
    if BE_LAT[0] <= a <= BE_LAT[1] and BE_LON[0] <= b <= BE_LON[1]:
        return a, b
    if BE_LAT[0] <= b <= BE_LAT[1] and BE_LON[0] <= a <= BE_LON[1]:
        return b, a
    return None


def _row_value(row: dict[str, str], *words: str) -> str | None:
    for key, value in row.items():
        if value and value not in ("-", "n/a") and any(w in key.lower() for w in words):
            return value.strip()
    return None


# How the directory writes "position unknown": null island, both as a coordinate
# and as a locator. JJ00AA converts neatly to (0.02, 0.04) — so it has to be
# caught here, before the conversion, or it slips straight through the zero check.
NULL_LOCATOR = {"JJ00AA", "JJ00", "AA00AA", "AA00"}

# Lower bound for "this really is the WWFF directory". The real list has some
# 68.000 rows; a truncated download does not come anywhere near that.
MIN_DIRECTORY_ROWS = 5000

# What a WWFF reference looks like, worldwide: a programme code that already ends
# in "FF", a dash, a number. Strict enough to keep the stray header line in the
# export ("REFERENCE") out.
WORLD_REF_RE = re.compile(r"^[A-Z0-9]{1,5}FF-\d+$")


def locator_to_latlon(loc: str) -> tuple[float, float] | None:
    """Maidenhead locator to the centre of its square. The directory always has
    one, so it is the backstop when latitude/longitude are empty."""
    # The directory contains locators with junk around them ("-GJ01PN", "IO91GN-",
    # "IO75 HT") and a handful of extended locators of 8 characters. All of them
    # are perfectly usable once you strip the non-alphanumeric characters and cut
    # to six — throwing them away would make the backstop needlessly brittle.
    loc = re.sub(r"[^A-Za-z0-9]", "", loc or "").upper()[:6]
    if loc in NULL_LOCATOR:
        return None
    if not re.fullmatch(r"[A-R]{2}[0-9]{2}([A-X]{2})?", loc):
        return None
    lon = (ord(loc[0]) - 65) * 20 - 180
    lat = (ord(loc[1]) - 65) * 10 - 90
    lon += int(loc[2]) * 2
    lat += int(loc[3]) * 1
    if len(loc) >= 6:
        lon += (ord(loc[4]) - 65) * (2 / 24) + (2 / 48)
        lat += (ord(loc[5]) - 65) * (1 / 24) + (1 / 48)
    else:
        lon += 1
        lat += 0.5
    return lat, lon


def _row_latlon(row: dict[str, str]) -> tuple[float, float] | None:
    """Position for one row: the named columns first, then the locator, then a
    coordinate pair squeezed into a single cell. Null island counts as absent."""
    lat = _to_float(row.get("latitude") or "")
    lon = _to_float(row.get("longitude") or "")
    if lat is None or lon is None:                       # other CSV shapes
        for key, value in row.items():
            k = key.lower()
            if not value:
                continue
            if lat is None and "lat" in k:
                lat = _to_float(value)
            elif lon is None and ("lon" in k or "lng" in k):
                lon = _to_float(value)
    # Three ways the directory hands us an unusable coordinate, and all three slip
    # through a naive check:
    #   · out of range     — latitude −1000, longitude −787 (a mangled export)
    #   · swapped          — latitude 144, longitude −36 (lat/lon transposed)
    #   · half null island — one of the two exactly 0, the other genuine
    # In all three cases we fall through to the locator, which nearly always does
    # have it right. Note the 'or' in the zero check: with 'and' a half-zeroed
    # coordinate gets through, and that drops a Northern Irish area 500 km out
    # into the North Sea.
    if lat is not None and lon is not None:
        if abs(lat) > 90 and abs(lon) <= 90:
            lat, lon = lon, lat                          # clearly transposed
        if abs(lat) <= 90 and abs(lon) <= 180 and not (abs(lat) < 0.1 or abs(lon) < 0.1):
            return lat, lon

    ll = locator_to_latlon(row.get("iaruLocator") or _row_value(row, "locator", "grid") or "")
    if ll and not (abs(ll[0]) < 0.1 or abs(ll[1]) < 0.1):
        return ll

    for key, value in row.items():
        if not value or not any(w in key.lower() for w in ("coord", "gps", "positi")):
            continue
        m = PAIR_RE.search(value)
        if m:
            a, b = _to_float(m.group(1)), _to_float(m.group(2))
            if a is not None and b is not None:
                return _orient(a, b) or (a, b)
    return None


def _province(row: dict[str, str]) -> str | None:
    code = (row.get("region") or "").split(",")[0].strip()
    return BE_REGIONS.get(code)


def _read_directory_rows(source: str | None) -> tuple[list[dict[str, str]], list[str], bool]:
    """Read the WWFF directory once, up front, so both convert() (to break a
    reference tie) and point_refs() (for the points themselves) work from the
    same rows instead of two separate downloads.

    Returns (rows, warnings, read_failed). Never raises: a directory that has
    moved, or a runner without network, must not break a data build, so the
    caller degrades to whatever it can do without it.
    """
    warnings: list[str] = []
    rows: list[dict[str, str]] = []
    read_failed = False
    if source:
        try:
            rows = _read_rows(source)
        except Exception as exc:                      # noqa: BLE001 (any failure here is non-fatal)
            warnings.append(f"WWFF directory not read ({type(exc).__name__}): "
                            f"used only the manual points from overrides.json")
            read_failed = True
        else:
            # A truncated download produces no error at all: you simply get fewer
            # rows. Without this check we would write out a half file that looks
            # perfectly healthy. The real directory has ~68.000 rows; anything
            # under a few thousand is never the real list.
            if len(rows) < MIN_DIRECTORY_ROWS:
                warnings.append(f"WWFF directory looks incomplete: {len(rows)} rows read, "
                                f"at least {MIN_DIRECTORY_ROWS} expected, ignored")
                rows = []
                read_failed = True
    return rows, warnings, read_failed


def _directory_name_lookup(rows: list[dict[str, str]], program: str) -> dict[str, str]:
    """ref -> official WWFF-directory name, for one programme.

    Used only to break a tie when the KMZ's own names disagree on which
    reference something is (_resolve_ref()); the polygons themselves are never
    sourced from here.
    """
    out: dict[str, str] = {}
    for row in rows:
        ref = (row.get("reference") or _row_value(row, "ref", "onff", "nummer") or "").strip().upper()
        if not ref:
            head = " ".join(list(row.values())[:4])
            m = REF_RE.search(head)
            ref = f"{program}-{m.group(1)}" if m else ""
        if not ref or not ref.startswith(program):
            continue
        name = (row.get("name") or _row_value(row, "name", "naam", "nom") or "").strip()
        if name:
            out[ref] = name
    return out


def _point_inside_other_polygon_warnings(geojson: dict, pt_features: list[dict]) -> list[str]:
    """A reference marked as having no polygon of its own, whose WWFF-directory
    position nonetheless falls inside another reference's finished boundary,
    is usually not "no polygon" at all: it is the other reference's KMZ
    placemark carrying the wrong number (see ONFF-0253/0254). Flags it instead
    of silently drawing a marker on top of somebody else's polygon.
    """
    polys = []
    for feat in geojson["features"]:
        try:
            polys.append((feat["properties"]["ref"], shape(feat["geometry"])))
        except Exception:                              # noqa: BLE001 (a bad geometry is not this check's job)
            continue
    warnings: list[str] = []
    for pt in pt_features:
        ref = pt["properties"]["ref"]
        lon, lat = pt["geometry"]["coordinates"]
        point = Point(lon, lat)
        for other_ref, poly in polys:
            if other_ref == ref:
                continue
            try:
                inside = poly.contains(point)
            except Exception:                          # noqa: BLE001 (same)
                continue
            if inside:
                warnings.append(
                    f"{ref} has no polygon of its own, but its position from the WWFF "
                    f"directory falls inside {other_ref}'s boundary: likely a reference "
                    f"mixed up somewhere in the source KMZ, worth checking")
                break
    return warnings


def _world_corrections(out_dir: Path, program: str, index_doc: dict,
                       points: list[dict]) -> dict[str, list[float]]:
    """ref -> [lon, lat] to use in wwff-world.geojson instead of the WWFF
    directory's position, for every country Diana has boundaries for, not only
    the one this run builds.

    Two kinds, both decided when their own country was built and stored in
    that country's index file: a reference whose directory position lies more
    than 2 km outside its own boundary (index entry "world", a point inside
    the boundary; see _position_mismatches()), and a position set by hand in
    overrides.json for a reference without a boundary. Everything else keeps
    the directory's position, including the many that sit a few metres off an
    edge: that is rounding, not an error, and moving thousands of points for it
    would only make every build's diff noisy.

    Read from every country's index file on disk, plus this run's fresh index
    and points (the points are not in index_doc yet at this stage) instead of
    its stale ones: a world file corrected only for whichever country
    was built last would lose the others' corrections at the next build, which
    is exactly the build-order bug this file has already had once.
    """
    pos: dict[str, list[float]] = {}

    def take(doc: dict) -> None:
        for r in doc.get("refs") or []:
            if r.get("ref") and isinstance(r.get("world"), list) and len(r["world"]) == 2:
                pos[r["ref"]] = [round(r["world"][0], 4), round(r["world"][1], 4)]
        for r in doc.get("points") or []:
            if r.get("src") == "overrides" and r.get("placed") and r.get("lat") is not None:
                pos[r["ref"]] = [round(r["lon"], 4), round(r["lat"], 4)]

    own = f"{program.lower()}-index.json"
    for path in sorted((out_dir / "zones").glob("*-index.json")):
        if path.name == own:
            continue
        try:
            take(json.loads(path.read_text(encoding="utf-8")))
        except Exception:                              # noqa: BLE001 (a broken file is simply not used)
            continue
    take({"refs": index_doc.get("refs") or [], "points": points})
    return pos


def _position_mismatches(geojson: dict, index_doc: dict, dir_pos: dict[str, tuple[float, float]],
                         limit_m: float = 2000) -> list[dict]:
    """References of this run whose WWFF-directory position lies more than
    `limit_m` outside their own boundary. Real cases, all in the directory, not
    in the KMZ: ONFF-0850 Helschot carries the exact coordinates of ONFF-0849
    Tommelen, 41 km away, and four more ONFF references copy a neighbour the
    same way. Listed in the report, with the neighbour when the coordinates are
    an exact copy and a point inside the boundary, so the list can go to WWFF
    for the root fix; wwff-world.geojson already uses the boundary instead.
    """
    same_spot: dict[tuple[float, float], list[str]] = defaultdict(list)
    for ref, xy in dir_pos.items():
        same_spot[tuple(xy)].append(ref)
    inside = {r["ref"]: (r.get("lat"), r.get("lon"), r.get("name")) for r in index_doc.get("refs") or []}
    out = []
    for feat in geojson.get("features") or []:
        ref = feat["properties"]["ref"]
        xy = dir_pos.get(ref)
        if not xy:
            continue
        try:
            poly = shape(feat["geometry"])
            point = Point(xy)
            if poly.contains(point):
                continue
            near = nearest_points(poly, point)[0]
            _, _, metres = GEOD.inv(xy[0], xy[1], near.x, near.y)
        except Exception:                              # noqa: BLE001 (a bad geometry is not this check's job)
            continue
        if metres <= limit_m:
            continue
        lat, lon, name = inside.get(ref, (None, None, None))
        out.append({"ref": ref, "name": name or feat["properties"].get("name") or ref,
                    "km": round(metres / 1000, 1),
                    "same_as": sorted(r for r in same_spot[tuple(xy)] if r != ref),
                    "directory": [xy[1], xy[0]], "inside": [lat, lon]})
    out.sort(key=lambda m: -m["km"])
    return out


def point_refs(rows: list[dict[str, str]], read_warnings: list[str], read_failed: bool,
               programs: list[str], have: set[str], overrides: dict, decimals: int):
    """Join the WWFF directory with the polygons we already have.

    Returns (features, index_entries, activity, warnings, stats). `rows` is
    whatever _read_directory_rows() returned; this function never reads the
    directory itself.
    """
    warnings: list[str] = list(read_warnings)
    stats = {"listed": 0, "deleted": 0, "nonwwff": 0, "orphan_polygons": [], "renamed": []}
    stats["rows"] = len(rows)

    wanted = tuple(p.strip().upper() for p in programs if p.strip())
    listed: dict[str, dict] = {}
    activity: dict[str, dict] = {}
    seen: set[str] = set()          # every active reference from the directory

    # Programme → country, over the ENTIRE directory (not limited to --program):
    # the map itself stays ONFF-only, but the spots screen wants to filter by
    # country worldwide, and needs a name per WWFF programme to do that. One tally
    # per country per programme; the most frequent country wins (almost always
    # that is the only one, bar a few spelling variants).
    programs_seen: dict[str, Counter] = {}
    program_code_re = re.compile(r"^[A-Z0-9]{1,5}FF$")
    for row in rows:
        prog = (row.get("program") or "").strip().upper()
        country = (row.get("country") or "").strip()
        # The odd stray header line here and there in the export yields "PROGRAM"/
        # "country" as values; a real programme always ends in "FF".
        if program_code_re.match(prog) and country and country not in ("-", "n/a"):
            programs_seen.setdefault(prog, Counter())[country] += 1

    for row in rows:
        ref = (row.get("reference") or _row_value(row, "ref", "onff", "nummer") or "").strip().upper()
        if not ref:
            # Scan only the first few cells. Searching the whole row means
            # searching 'notes' and 'changeLog' too, and a row from another
            # country that happens to mention an ONFF number would then come in
            # as an ONFF area.
            head = " ".join(list(row.values())[:4])
            m = REF_RE.search(head)
            ref = f"ONFF-{m.group(1)}" if m else ""
        if not ref or (wanted and not ref.startswith(wanted)):
            continue

        status = (row.get("status") or "active").strip().lower()
        if status and status != "active":
            # 'deleted' really has been struck off; 'national' is an existing area
            # that does not (yet) count as a WWFF reference. We draw neither, but
            # lumping them together lets the report claim that areas were deleted
            # when they were not.
            stats["deleted" if status == "deleted" else "nonwwff"] += 1
            # A deleted reference that we do still draw is a genuine signal.
            if ref in have:
                warnings.append(f"{ref} is listed as '{status}' in the WWFF directory but still has "
                                f"a polygon in the KMZ — needs checking")
            continue

        stats["listed"] += 1
        seen.add(ref)
        name = row.get("name") or _row_value(row, "name", "naam", "nom")
        q = _to_float(row.get("qsoCount") or "")
        last = (row.get("lastAct") or "").strip()
        if ref in have:
            # Cross-check and activity only — the polygon stays authoritative.
            if q is not None or last:
                activity[ref] = {"q": int(q or 0), "last": last or None}
            continue

        listed[ref] = {
            "name": name,
            "prov": _province(row),
            "iucn": (row.get("IUCNcat") or "").strip() or None,
            "site": (row.get("website") or "").strip() or None,
            "loc": (row.get("iaruLocator") or "").strip().upper() or None,
            "latlon": _row_latlon(row),
            "src": "wwff",
        }
        if q is not None or last:
            activity[ref] = {"q": int(q or 0), "last": last or None}

    # A polygon with no row in the directory. Compare against every reference we
    # saw — not against the activity table, because a reference without a QSO
    # count is not in there and is therefore not yet unknown.
    if rows and stats["listed"]:
        stats["orphan_polygons"] = sorted(have - seen)

    # overrides.json may place or move a point, and always wins.
    for ref, ov in overrides.items():
        if ref in have or not isinstance(ov, dict) or "point" not in ov:
            continue
        listed.setdefault(ref, {"name": None, "prov": None, "iucn": None,
                                "site": None, "loc": None, "latlon": None})
        try:
            lon, lat = float(ov["point"][0]), float(ov["point"][1])
            listed[ref]["latlon"] = (lat, lon)
            listed[ref]["src"] = "overrides"
        except (TypeError, ValueError, IndexError):
            warnings.append(f"{ref}: overrides.json 'point' is not a [lon, lat]")

    features, entries, unplaced = [], [], []
    for ref in sorted(listed):
        info = listed[ref]
        ov = overrides.get(ref) if isinstance(overrides.get(ref), dict) else {}
        props = {
            "ref": ref,
            "name": (ov or {}).get("name") or info.get("name") or ref,
            "prov": (ov or {}).get("province") or info.get("prov"),
            "iucn": info.get("iucn"),
            "loc": info.get("loc"),
            "site": info.get("site"),
            "nopoly": True,
            "src": info.get("src"),
        }
        props = {k: v for k, v in props.items() if v not in (None, "", "n/a", "-")}
        if not info.get("latlon"):
            unplaced.append(ref)
            entries.append({**props, "placed": False})
            continue
        lat, lon = (round(v, decimals) for v in info["latlon"])
        features.append({"type": "Feature", "properties": props,
                         "geometry": {"type": "Point", "coordinates": [lon, lat]}})
        entries.append({**props, "lat": lat, "lon": lon, "placed": True})

    if unplaced:
        warnings.append(f"{len(unplaced)} references with no polygon and no usable position: "
                        + ", ".join(unplaced[:12]) + ("…" if len(unplaced) > 12 else "")
                        + " — can be placed with \"point\": [lon, lat] in overrides.json")
    if stats["orphan_polygons"]:
        warnings.append(f"{len(stats['orphan_polygons'])} polygons are not in the WWFF directory: "
                        + ", ".join(stats["orphan_polygons"][:12])
                        + ("…" if len(stats["orphan_polygons"]) > 12 else ""))
    programs_map = {prog: counter.most_common(1)[0][0]
                    for prog, counter in programs_seen.items() if counter}
    stats["read_failed"] = read_failed

    # Every active reference worldwide, as a bare point: no country name, no
    # province, no IUCN — only what it takes to put a dot down, because this runs
    # to tens of thousands of features soon enough. Never a boundary: this file
    # carries no polygons for anyone. A small share (~1%) has no position; those
    # are skipped, never invented.
    #
    # This USED to leave out --program — the country this very run is building —
    # on the reasoning that it already has a boundary, so it should not also be a
    # dot. That was true only because Diana used to have exactly one loadable
    # country, which was therefore always both "what this run just built" and
    # "what every viewer has loaded". Once a second country got boundaries the two
    # came apart: this file is shared by every viewer, and each one loads only
    # ONE country of their own choosing, not necessarily whichever one a build
    # happened to touch most recently. Leaving out --program here meant that
    # whichever country was rebuilt LAST simply vanished from this file for
    # EVERYONE, including a viewer who had a completely different country loaded
    # and needed exactly that one as a dot. It reappeared the moment some other
    # country's build ran — a bug that moved around depending on build order, not
    # a change in what anyone was looking at.
    #
    # So: everything goes in here now, this run's own programme included. Leaving
    # the right one out is a per-viewer decision — only the browser knows which
    # single country a given visitor actually has loaded — and the app already
    # makes that decision correctly, dynamically, per viewer: see
    # worldFilteredData() in map.js.
    world_features = []
    # QSO count per reference, worldwide, every programme included, same
    # reasoning as world_features just above: a spot or an announced activation
    # can be for any country, not only the one this run happens to be building,
    # and the app already picks the right one per viewer dynamically. Unlike
    # the per-programme `activity` table above, a reference lands in here
    # whether or not it also has a polygon, since a spot needs no boundary.
    #
    # Every ACTIVE reference is written, including the ones the directory has
    # no count for at all: that empty count is how the directory says "never
    # activated" (it never writes a literal 0; checked against the real file,
    # where ONFF's 21 never-activated references, mostly the newest ones, have
    # an empty qsoCount AND an empty lastAct). Written here as 0, which is what
    # the spots screen turns into ATNO. The one case left out is a missing or
    # zero count WITH a last activation date: that reference has been
    # activated, so 0 would be a false ATNO (the app reads the per-country
    # table the same way, see qsoCountAnywhere() in map-data.js).
    #
    # Only the count, no date: the spots screen uses nothing else, and at some
    # 65,000 references the date alone would more than double the file.
    world_activity: dict[str, int] = {}
    counts_seen = 0
    for row in rows:
        ref = (row.get("reference") or "").strip().upper()
        if not ref:
            continue
        # The same stray header line as above yields ref "REFERENCE" with an empty
        # status. Reading an empty status here as 'active' would put that line on
        # the map as an area; hence no default value, and the same shape test as
        # in the programme table.
        if not WORLD_REF_RE.match(ref):
            continue
        status = (row.get("status") or "").strip().lower()
        if status != "active":
            continue
        q = _to_float(row.get("qsoCount") or "")
        last = (row.get("lastAct") or "").strip()
        if q is not None:
            counts_seen += 1
        if q:
            world_activity[ref] = int(q)
        elif not last:
            world_activity[ref] = 0
        latlon = _row_latlon(row)
        if not latlon:
            continue
        lat, lon = (round(v, 4) for v in latlon)
        world_features.append({
            "type": "Feature",
            "properties": {"ref": ref, "name": (row.get("name") or "").strip()},
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
        })

    # "No count" reads as "never activated" only because the real directory
    # does have a count for every reference that has been. A directory with no
    # counts at all (the column renamed or dropped in some future export) would
    # turn every reference on earth into an ATNO. So: not written at all then,
    # the previous file stays, and the report says why.
    if world_activity and not counts_seen:
        warnings.append("WWFF directory has no QSO counts at all (qsoCount column missing or "
                        "empty): wwff-activity.json not rewritten, rather than calling every "
                        "reference an ATNO")
        world_activity = {}

    return features, entries, activity, warnings, stats, programs_map, world_features, world_activity


def convert(kml_path: Path, tolerance: float, decimals: int, overrides: dict,
            directory_names: dict[str, str] | None = None) -> tuple[dict, dict, dict]:
    tree = etree.parse(str(kml_path))
    # Google Earth writes the outermost container as either a <Document> or a
    # <Folder>, depending on how the person who made the file organised it, and
    # both are valid KML. Belgium and Germany have a Document, Denmark has a
    # Folder. Neither is a reason to refuse a file.
    root = tree.getroot()
    document = root.find(KML_NS + "Document")
    if document is None:
        document = root.find(KML_NS + "Folder")
    if document is None:
        raise SystemExit("KML has neither a <Document> nor a <Folder> at its root — "
                         "this does not look like a Google Earth export")

    release = None
    desc = document.find(KML_NS + "description")
    if desc is not None and desc.text:
        m = re.search(r"(\d{4}-\d{2}-\d{2})", desc.text)
        if m:
            release = m.group(1)

    polygons: dict[str, list[Polygon]] = defaultdict(list)
    meta: dict[str, dict] = {}
    warnings: list[str] = []
    skipped_no_ref = 0
    # What the file turned out to hold, whether or not any of it was usable.
    # A conversion that produces nothing has to be able to say why, and "why"
    # is nearly always one of: no areas in it, or areas belonging to another
    # country. Both are visible from here and nowhere else.
    seen_polygons = 0
    foreign: Counter = Counter()
    stray_names: list[str] = []
    directory_names = directory_names or {}

    for placemark, province, layer in _placemarks(document):
        kml_polys = placemark.findall(".//" + KML_NS + "Polygon")
        if not kml_polys:
            continue
        seen_polygons += 1
        candidates = _ancestor_ref_candidates(placemark)
        ref, raw_name, note = _resolve_ref(candidates, directory_names)
        if note:
            warnings.append(note)
        if not ref:
            skipped_no_ref += 1
            other = _foreign_program(placemark)
            if other:
                foreign[other] += 1
            if len(stray_names) < 3:
                name = _name(placemark)
                if name:
                    stray_names.append(name)
            continue

        for kml_poly in kml_polys:
            outer = kml_poly.find(".//" + KML_NS + "outerBoundaryIs/" + KML_NS + "LinearRing")
            if outer is None:
                continue
            shell = _ring(outer)
            if len(shell) < 4:
                continue
            holes = []
            for inner in kml_poly.findall(".//" + KML_NS + "innerBoundaryIs/" + KML_NS + "LinearRing"):
                ring = _ring(inner)
                if len(ring) >= 4:
                    holes.append(ring)
            try:
                poly = Polygon(shell, holes)
            except Exception:
                warnings.append(f"{ref}: unreadable polygon skipped")
                continue
            if not poly.is_valid:
                poly = poly.buffer(0)
            if poly.is_empty:
                continue
            polygons[ref].append(poly)

        entry = meta.setdefault(ref, {"names": Counter(), "province": province, "layer": layer})
        if raw_name:
            entry["names"][raw_name] += 1
        if entry["province"] is None and province:
            entry["province"] = province
        attrs = attributes_from(_extended_data(placemark))
        for key, value in attrs.items():
            entry.setdefault(key, value)

    if skipped_no_ref:
        note = f"{skipped_no_ref} polygons with no recognisable {PROGRAM} number skipped"
        if foreign:
            note += (" — they carry " +
                     ", ".join(f"{p} ({n}×)" for p, n in foreign.most_common(3)) +
                     " instead")
        warnings.append(note)

    features = []
    index = []
    for ref in sorted(polygons):
        merged = unary_union(polygons[ref])
        simplified = merged.simplify(tolerance, preserve_topology=True)
        if simplified.is_empty:
            warnings.append(f"{ref}: geometry vanished on simplification, raw version used")
            simplified = merged
        geom = round_geometry(simplified, decimals)
        if geom is None:
            warnings.append(f"{ref}: no usable geometry after rounding — skipped")
            continue

        entry = meta.get(ref, {})
        override = overrides.get(ref, {})

        name = override.get("name") or pick_name(entry.get("names") or Counter(), ref)

        props = {
            "ref": ref,
            "name": name,
            "prov": override.get("province", entry.get("province")),
        }
        for key in ("desig", "iucn", "manager", "registration", "status_year", "layer", "region"):
            value = override.get(key, entry.get(key))
            if value:
                props[key] = value

        area = area_hectares(geom)
        props["area_ha"] = area
        centroid = geom.representative_point()
        bounds = geom.bounds

        features.append({"type": "Feature", "properties": props, "geometry": mapping(geom)})
        index.append({
            **props,
            "lat": round(centroid.y, 5),
            "lon": round(centroid.x, 5),
            "bbox": [round(v, 5) for v in bounds],
            "parts": len(geom.geoms),
        })

    geojson = {"type": "FeatureCollection", "features": features}
    index_doc = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "release": release,
        "count": len(index),
        "refs": index,
    }
    stats = {
        "release": release,
        "zones": len(index),
        "polygons": sum(len(v) for v in polygons.values()),
        "warnings": warnings,
        # For the format check in main(): what was in the file, as opposed to
        # what could be used from it.
        "seen_polygons": seen_polygons,
        "no_ref": skipped_no_ref,
        "foreign": dict(foreign),
        "stray_names": stray_names,
    }
    return geojson, index_doc, stats


# --------------------------------------------------------------------------- #
# Does this file hold what we were told it holds?
#
# A conversion that yields nothing used to be indistinguishable from a country
# that happens to have no areas: the build wrote an empty file and the output
# check further down the line said "0 zones" without ever saying why. The one
# mistake that actually happens is picking the wrong country when uploading,
# and that is exactly the case the file itself can explain — so it does, here,
# before anything is written and before the WWFF directory is even fetched.
# --------------------------------------------------------------------------- #

def _an(code: str) -> str:
    """"an ONFF number", "a DLFF number". Read aloud, a programme code starts
    with the name of its first letter, not with the letter — so the article
    follows the sound of that name. Small thing; it is a message people read."""
    return "an" if code[:1].upper() in "AEFHILMNORSX" else "a"


def format_complaint(stats: dict, program: str, source: str) -> str | None:
    """The reason this file cannot be read as `program`, or None if it can."""
    if stats["zones"]:
        return None

    seen = stats.get("seen_polygons") or 0
    if not seen:
        return (f"{source} holds no areas at all: not one placemark with a boundary in "
                f"it. A WWFF release is a Google Earth export with the areas as "
                f"polygons — a file of waypoints or an empty map will not do.")

    foreign = stats.get("foreign") or {}
    lead = (f"{source} holds {seen} areas, and not one of them carries "
            f"{_an(program)} {program} number.")
    if foreign:
        top = sorted(foreign.items(), key=lambda kv: -kv[1])
        named = ", ".join(f"{prog} ({n}×)" for prog, n in top[:3])
        return (f"{lead} They carry {named}. This file is for another country than "
                f"the one it was sent as — pick {top[0][0]} instead of {program}, or "
                f"send the {program} release.")
    examples = stats.get("stray_names") or []
    shown = "; ".join(f'"{n}"' for n in examples[:3])
    return (f"{lead} The number has to stand in the name of the area itself or of a "
            f"folder around it, as \"{program}-0001 Name\"."
            + (f" The names in this file look like: {shown}." if shown else ""))


# --------------------------------------------------------------------------- #
# Diff report
# --------------------------------------------------------------------------- #

def diff_report(new_index: dict, prev_path: Path, stats: dict, source_name: str) -> str:
    new_by_ref = {r["ref"]: r for r in new_index["refs"]}
    lines: list[str] = []

    if not prev_path.exists():
        lines.append(f"## Diana — first dataset from `{source_name}`")
        lines.append("")
        lines.append(f"**{len(new_by_ref)} areas** read in. There is no previous version to compare against yet.")
    else:
        prev = json.loads(prev_path.read_text(encoding="utf-8"))
        prev_by_ref = {r["ref"]: r for r in prev.get("refs", [])}

        added = sorted(set(new_by_ref) - set(prev_by_ref))
        removed = sorted(set(prev_by_ref) - set(new_by_ref))
        changed = []
        for ref in sorted(set(new_by_ref) & set(prev_by_ref)):
            old, cur = prev_by_ref[ref], new_by_ref[ref]
            old_area = old.get("area_ha") or 0
            new_area = cur.get("area_ha") or 0
            if old_area and abs(new_area - old_area) / old_area > 0.01:
                changed.append((ref, cur.get("name"), old_area, new_area))

        delta = len(new_by_ref) - len(prev_by_ref)
        sign = f"+{delta}" if delta > 0 else str(delta)
        lines.append(f"## Diana — new dataset from `{source_name}`")
        lines.append("")
        lines.append(
            f"**{len(new_by_ref)} areas** (was {len(prev_by_ref)}, {sign}) · "
            f"**{len(added)} new** · **{len(removed)} gone** · "
            f"**{len(changed)} boundary changed**"
        )
        lines.append("")

        if added:
            lines.append(f"<details><summary>{len(added)} new areas</summary>")
            lines.append("")
            for ref in added:
                r = new_by_ref[ref]
                lines.append(f"- `{ref}` {r.get('name')} — {r.get('prov') or 'province unknown'}, {r.get('area_ha')} ha")
            lines.append("")
            lines.append("</details>")
            lines.append("")

        if removed:
            lines.append(f"<details><summary>{len(removed)} areas gone — needs checking</summary>")
            lines.append("")
            for ref in removed:
                r = prev_by_ref[ref]
                lines.append(f"- `{ref}` {r.get('name')} — was in the previous release, not any more")
            lines.append("")
            lines.append("</details>")
            lines.append("")

        if changed:
            lines.append(f"<details><summary>{len(changed)} changed boundaries (more than 1% difference in area)</summary>")
            lines.append("")
            for ref, name, old_area, new_area in changed:
                pct = (new_area - old_area) / old_area * 100
                lines.append(f"- `{ref}` {name}: {old_area} ha → {new_area} ha ({pct:+.1f}%)")
            lines.append("")
            lines.append("</details>")
            lines.append("")

    d = stats.get("directory") or {}
    placed = stats.get("points", 0)
    unplaced = stats.get("points_unplaced", 0)
    if d.get("listed") or placed or unplaced:
        lines.append("")
        lines.append("### Cross-check against the WWFF directory")
        lines.append("")
        lines.append(f"**{d.get('listed', 0)} active references** in the directory · "
                     f"**{len(new_by_ref)} with a boundary** from the KMZ · "
                     f"**{placed} as a point** on the map"
                     + (f" · **{unplaced} without a position**" if unplaced else "")
                     + (f" · {d.get('deleted', 0)} deleted (not shown)" if d.get("deleted") else "")
                     + (f" · {d.get('nonwwff', 0)} non-WWFF (not shown)" if d.get("nonwwff") else ""))
        lines.append("")
        lines.append("Every reference appears only once: if there is a polygon in the KMZ, "
                     "that one wins and the directory row is used only to check against.")
        if unplaced:
            lines.append("")
            lines.append("References without a position are in the list but not on the map. "
                         "You can set a coordinate in `overrides.json`: "
                         "`\"ONFF-0123\": { \"point\": [4.47, 50.85] }` (longitude, latitude).")

    mismatch = stats.get("position_mismatch") or []
    if mismatch:
        lines.append("")
        lines.append(f"<details><summary>📍 {len(mismatch)} references whose WWFF-directory position "
                     f"lies more than 2 km outside their own boundary</summary>")
        lines.append("")
        lines.append("Diana puts these at a point inside the boundary instead (worldwide points, "
                     "Nearby > Info, agenda pins), so the dot matches the area on the map. Where the "
                     "directory copies a neighbour's exact coordinates the directory is wrong and this "
                     "list can go to WWFF as it is; for the others it is worth a look which of the two "
                     "is wrong, the directory or the boundary in the KMZ. Coordinates are latitude, "
                     "longitude.")
        lines.append("")
        for m in mismatch:
            copy = (f"; the directory gives it the exact coordinates of "
                    + ", ".join(f"`{r}`" for r in m["same_as"]) if m["same_as"] else "")
            inside = (f", a point inside the boundary is {m['inside'][0]:.4f}, {m['inside'][1]:.4f}"
                      if m["inside"][0] is not None else "")
            lines.append(f"- `{m['ref']}` {m['name']}: {m['km']} km outside its boundary{copy} "
                         f"(directory {m['directory'][0]:.4f}, {m['directory'][1]:.4f}{inside})")
        lines.append("")
        lines.append("</details>")

    if stats["warnings"]:
        lines.append("")
        lines.append(f"<details><summary>⚠️ {len(stats['warnings'])} warnings</summary>")
        lines.append("")
        for warning in stats["warnings"]:
            lines.append(f"- {warning}")
        lines.append("")
        lines.append("</details>")

    lines.append("")
    lines.append(f"<sub>Release {stats['release'] or 'unknown'} · {stats['polygons']} source polygons · generated by kmz2geojson {SCRIPT_VERSION}</sub>")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #

def main() -> int:
    parser = argparse.ArgumentParser(description="Convert an ONFF KMZ release into Diana's data files.")
    parser.add_argument("--kmz", required=True, type=Path, help="path to ONFF_YYYYMMDD.kmz")
    parser.add_argument("--out", type=Path, default=Path("data"), help="output directory (default: data)")
    parser.add_argument("--overrides", type=Path, default=Path("overrides.json"))
    parser.add_argument("--report", type=Path, default=Path("report.md"))
    parser.add_argument("--tolerance", type=float, default=0.00005,
                        help="simplification tolerance in degrees (default 0.00005 = ~5 m)")
    parser.add_argument("--decimals", type=int, default=5)
    parser.add_argument("--gzip", action="store_true", help="also write a .gz, to check the delivered size")
    parser.add_argument("--workdir", type=Path, default=Path(".kmz-work"))
    parser.add_argument("--refs-csv", default=WWFF_DIRECTORY,
                        help="the WWFF directory (URL or local path). It decides which "
                             "references exist; the ones without a polygon in the KMZ become "
                             f"Point features. Default: {WWFF_DIRECTORY}")
    parser.add_argument("--program", default="ONFF",
                        help="the WWFF programme this KMZ belongs to (default ONFF). It "
                             "decides which references are read from the directory, how "
                             "they are recognised in the KMZ, and what the output files "
                             "are called: data/zones/<program>.geojson and friends. One "
                             "country per run — that is what keeps a bad file for one "
                             "country from touching another country's data.")
    parser.add_argument("--no-refs", action="store_true",
                        help="skip the directory entirely (offline builds)")
    parser.add_argument("--strict", action="store_true",
                        help="stop with exit code 1 if the WWFF directory is unreachable or "
                             "incomplete, instead of carrying on with less data. "
                             "For unattended runs that are allowed to commit by themselves.")
    args = parser.parse_args()

    # One country per run. Everything downstream — which references are read
    # from the directory, how they are recognised in the KMZ, what the files are
    # called — hangs off this.
    global PROGRAM, REF_RE
    PROGRAM = args.program.strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{1,3}FF", PROGRAM):
        print(f"--program {PROGRAM!r} does not look like a WWFF programme code "
              f"(ONFF, PAFF, DLFF, …)", file=sys.stderr)
        return 2
    REF_RE = re.compile(PROGRAM + r"[- ]?(\d{4})(?!\d)")

    if not args.kmz.exists():
        raise SystemExit(f"KMZ not found: {args.kmz}")

    overrides = {}
    if args.overrides.exists():
        raw = json.loads(args.overrides.read_text(encoding="utf-8"))
        overrides = raw.get("zones", raw)

    # Read the WWFF directory before the KMZ itself: convert() needs its names
    # to break a tie when the KMZ's own names disagree on a reference number
    # (see _resolve_ref()). A directory that cannot be read at all just means
    # no names to break a tie with, so convert() then falls back to the nearest
    # name, as it always did.
    print("→ WWFF directory", file=sys.stderr)
    dir_rows, dir_warnings, dir_read_failed = _read_directory_rows(
        None if args.no_refs else args.refs_csv)
    directory_names = _directory_name_lookup(dir_rows, PROGRAM)

    print(f"→ unpacking {args.kmz.name}", file=sys.stderr)
    kml_path = extract_kmz(args.kmz, args.workdir)

    print("→ parsing and converting", file=sys.stderr)
    geojson, index_doc, stats = convert(kml_path, args.tolerance, args.decimals, overrides,
                                        directory_names)

    # Stop here if the file cannot be read as this country, before anything is
    # written. Writing an empty country would take the real one off the map;
    # saying nothing would leave whoever sent the file guessing. So: nothing
    # written, and a reason.
    complaint = format_complaint(stats, PROGRAM, args.kmz.name)
    if complaint:
        args.report.write_text(
            f"## Diana — `{args.kmz.name}` could not be read as {PROGRAM}\n\n"
            f"{complaint}\n\n"
            f"Nothing has been changed. The data that was already there is untouched.\n",
            encoding="utf-8")
        print(f"✗ {complaint}", file=sys.stderr)
        return 2

    # The <description> in the KML is the official release date, but ONFF does
    # forget to update it now and then: the August 2026 release still carries
    # 2026-01-01 in there. The filename (ONFF YYYYMMDD.kmz) is always right, so
    # that one wins, and the description stays the fallback for a file with no date.
    naam_datum = re.search(r"(20\d{2})[-_ ]?(\d{2})[-_ ]?(\d{2})", args.kmz.stem)
    if naam_datum:
        uit_naam = "-".join(naam_datum.groups())
        if stats["release"] and stats["release"] != uit_naam:
            stats["warnings"].append(
                f"release date in the KML ({stats['release']}) differs from the filename "
                f"({uit_naam}) — the filename was used")
        stats["release"] = uit_naam

    have = {r["ref"] for r in index_doc["refs"]}
    programs = [PROGRAM]
    pt_features, pt_entries, activity, pt_warnings, pt_stats, programs_map, world_features, world_activity = point_refs(
        dir_rows, dir_warnings, dir_read_failed, programs, have, overrides, args.decimals)
    stats["warnings"].extend(pt_warnings)
    stats["warnings"].extend(_point_inside_other_polygon_warnings(geojson, pt_features))

    # The worldwide points layer takes each position from the WWFF directory,
    # and for a reference with a boundary that position is sometimes plainly
    # wrong: more than 2 km outside the boundary, often an exact copy of a
    # neighbour's coordinates (see _position_mismatches()). Diana knows better
    # there, so those, and only those, get a point inside their boundary in the
    # world file: Nearby > Info's nearest references, other viewers' points
    # layer and agenda pins all read it. The decision is stored in this
    # country's index ("world"), so a later build of another country, which
    # rewrites the shared world file, still applies it (_world_corrections()).
    if world_features:
        dir_pos = {f["properties"]["ref"]: tuple(f["geometry"]["coordinates"]) for f in world_features}
        stats["position_mismatch"] = _position_mismatches(geojson, index_doc, dir_pos)
        wrong = {m["ref"] for m in stats["position_mismatch"]}
        for entry in index_doc["refs"]:
            if entry["ref"] in wrong:
                entry["world"] = [entry["lon"], entry["lat"]]
    else:
        # No directory this time (unreachable, or --no-refs): nothing to compare
        # against, so keep what the previous build of this country decided.
        # Dropping it would let the next build of any other country put the
        # wrong positions back into the shared world file.
        try:
            earlier = json.loads((args.out / "zones" / f"{PROGRAM.lower()}-index.json")
                                 .read_text(encoding="utf-8"))
        except Exception:                              # noqa: BLE001 (no previous build, nothing to keep)
            earlier = {}
        kept = {r["ref"]: r["world"] for r in earlier.get("refs") or [] if r.get("world")}
        for entry in index_doc["refs"]:
            if entry["ref"] in kept:
                entry["world"] = kept[entry["ref"]]
    corrections = _world_corrections(args.out, PROGRAM, index_doc, pt_entries)
    moved = 0
    for feat in world_features:
        better = corrections.get(feat["properties"]["ref"])
        if better and better != feat["geometry"]["coordinates"]:
            feat["geometry"]["coordinates"] = better
            moved += 1
    stats["world_moved"] = moved

    args.out.mkdir(parents=True, exist_ok=True)
    zones_dir = args.out / "zones"
    zones_dir.mkdir(parents=True, exist_ok=True)
    slug = PROGRAM.lower()
    index_path = zones_dir / f"{slug}-index.json"

    # The directory is the most fragile of the three sources: one 503 and we have
    # no points at all left. That is no reason to throw the previous build away.
    #
    # Under --strict (the nightly run, where nobody is watching) we simply stop
    # here: writing nothing is always better than quietly pushing stripped-down
    # data through to main. Without --strict there is someone looking at a pull
    # request, and we keep the points from the previous build instead of wiping
    # them — otherwise a reachability problem writes itself into the history as a
    # data change.
    directory_failed = bool(pt_stats.get("read_failed"))

    # A truncated download gives no error at all — you simply get fewer rows, and
    # a fixed lower bound catches that badly: 20% of the file is still 14.000
    # rows. So we calibrate against the previous build: if the row count drops
    # sharply, something is wrong with the source, not with WWFF.
    meta_path = args.out / "meta.json"
    previous_meta: dict = {}
    if meta_path.exists():
        try:
            previous_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:                              # noqa: BLE001 — corrupt is just "no previous"
            previous_meta = {}
    try:
        previous_rows = int(previous_meta.get("directory_rows") or 0)
    except (TypeError, ValueError):
        previous_rows = 0
    rows_now = pt_stats.get("rows") or 0
    if not directory_failed and previous_rows and rows_now < previous_rows * 0.8:
        directory_failed = True
        stats["warnings"].append(
            f"WWFF directory looks truncated: {rows_now} rows against {previous_rows} "
            f"the previous build (−{100 - round(rows_now / previous_rows * 100)}%) — ignored")

    if directory_failed:
        if args.strict:
            print("✗ WWFF directory unreachable or incomplete — nothing written (--strict)",
                  file=sys.stderr)
            for warning in pt_warnings + stats["warnings"][-1:]:
                print("  " + warning, file=sys.stderr)
            return 1
        previous = {}
        if index_path.exists():
            try:
                previous = json.loads(index_path.read_text(encoding="utf-8"))
            except Exception:                          # noqa: BLE001 — corrupt is just "no previous"
                previous = {}
        if previous.get("points"):
            pt_entries = previous["points"]
            stats["warnings"].append(
                f"directory unreachable — the {len(pt_entries)} points from the previous build "
                f"are kept; onff-points.geojson has not been rewritten")

    stats["points"] = len(pt_features)
    stats["points_unplaced"] = sum(1 for e in pt_entries if not e.get("placed"))
    stats["directory"] = pt_stats
    stats["activity"] = len(activity)
    index_doc["points"] = pt_entries
    index_doc["point_count"] = len(pt_entries)

    print("→ writing diff report", file=sys.stderr)
    report = diff_report(index_doc, index_path, stats, args.kmz.name)
    args.report.write_text(report + "\n", encoding="utf-8")

    geojson_path = zones_dir / f"{slug}.geojson"
    geojson_path.write_text(json.dumps(geojson, separators=(",", ":")), encoding="utf-8")
    if args.gzip:
        # Only for a local size check: in production the hosting compresses itself.
        with gzip.open(str(geojson_path) + ".gz", "wb", compresslevel=9) as fh:
            fh.write(geojson_path.read_bytes())
    index_path.write_text(json.dumps(index_doc, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")

    # Written even when empty, so the app's fetch is a clean 200 rather than a 404
    # — but NOT if the directory was unreachable: then "empty" is not an outcome
    # but an outage, and we would overwrite a good file with an empty one.
    if not directory_failed:
        (zones_dir / f"{slug}-points.geojson").write_text(
            json.dumps({"type": "FeatureCollection",
                        "generated": index_doc["generated"],
                        "features": pt_features}, separators=(",", ":"), ensure_ascii=False),
            encoding="utf-8")

    # Activity per reference from the WWFF directory: number of QSOs and the date
    # of the last activation. Small file, and the only source the app has for
    # those figures — the Nearby screen and the area panel both read it.
    if activity and not directory_failed:
        (zones_dir / f"{slug}-activity.json").write_text(
            json.dumps({"generated": index_doc["generated"],
                        "source": "wwff_directory.csv",
                        "refs": activity}, separators=(",", ":")), encoding="utf-8")

    # Worldwide programme → country list, for the spots filter in the app
    # (Settings: one country / worldwide). Independent of --program: that only
    # decides which references this run turns into boundaries.
    if programs_map and not directory_failed:
        (args.out / "wwff-programs.json").write_text(
            json.dumps({"generated": index_doc["generated"],
                        "programs": [{"program": p, "country": c}
                                     for p, c in sorted(programs_map.items(),
                                                         key=lambda kv: kv[1])]},
                       separators=(",", ":"), ensure_ascii=False), encoding="utf-8")

    # ---------------------------------------------------------- the manifest
    # data/countries.json is what the app reads to know which countries it has
    # boundaries for. It is MERGED, never rewritten: a build for one country
    # updates its own entry and leaves every other country's alone. That is the
    # whole point of building per country — a bad file for Germany must not be
    # able to take Belgium off the map.
    manifest_path = args.out / "countries.json"
    entries = {}
    if manifest_path.exists():
        try:
            old = json.loads(manifest_path.read_text(encoding="utf-8"))
            for entry in old.get("countries") or []:
                if entry.get("program"):
                    entries[entry["program"]] = entry
        except (ValueError, OSError) as exc:
            print(f"  ! could not read the existing {manifest_path.name} ({exc}) — "
                  f"it will be written fresh, with only {PROGRAM} in it", file=sys.stderr)

    files = {"zones": f"zones/{slug}.geojson"}
    if (zones_dir / f"{slug}-points.geojson").exists():
        files["points"] = f"zones/{slug}-points.geojson"
    if (zones_dir / f"{slug}-activity.json").exists():
        files["activity"] = f"zones/{slug}-activity.json"

    entries[PROGRAM] = {
        "program": PROGRAM,
        # The directory knows the country name; without it the app falls back to
        # showing the programme code, which is no disaster.
        "country": programs_map.get(PROGRAM) or entries.get(PROGRAM, {}).get("country") or PROGRAM,
        "refs": stats["zones"],
        "points": len(pt_features),
        "release": stats["release"],
        "source_file": args.kmz.name,
        "generated": index_doc["generated"],
        "bytes": geojson_path.stat().st_size,
        "files": files,
    }
    manifest_path.write_text(json.dumps(
        {"generated": index_doc["generated"],
         "countries": [entries[k] for k in sorted(entries)]},
        indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"→ {manifest_path.name}: {', '.join(sorted(entries))}", file=sys.stderr)

    # The "other WWFF areas" layer: every active reference worldwide, as a bare
    # point — including references whose programme already has a boundary
    # elsewhere. This file is shared by every viewer, and each one only ever has
    # ONE country's boundaries loaded at a time: their own. The app itself
    # already leaves that one country's points out, dynamically, per viewer (see
    # worldFilteredData() in map.js) — so this file has to keep everyone else's
    # points in, always, or nobody could ever see them.
    #
    # This used to also strip out every country already in the manifest, not
    # just the one being built (point_refs() above already leaves out --program
    # for this run). That was harmless as long as Diana only ever had boundaries
    # for one country: ONFF was always the one loaded, so ONFF being permanently
    # gone from here made no difference. The moment a second country got
    # boundaries, that stopped being true — whichever of the two was NOT the
    # viewer's own home country had nowhere left to appear at all: no boundary,
    # because it was not the one loaded, and no point, because it was stripped
    # out here for everyone. So nothing beyond point_refs()'s own-programme
    # filter happens here any more.
    #
    # Only written if the directory could genuinely be read (otherwise this
    # would overwrite an empty or wildly outdated file with something that looks
    # emptier still); otherwise the previous version simply stays put.
    if world_features and not directory_failed:
        (args.out / "wwff-world.geojson").write_text(
            json.dumps({"type": "FeatureCollection",
                        "generated": index_doc["generated"],
                        "features": world_features}, separators=(",", ":"), ensure_ascii=False),
            encoding="utf-8")

    # Same reasoning, same guard: the QSO count per reference, worldwide, for
    # the spots screen (qsoCountAnywhere() in map-data.js). Kept separate from
    # wwff-world.geojson: a spot needs no boundary and no position either,
    # only a number, so this file has no geometry in it at all. build/site.sh
    # has to publish it by name, like every other shared file.
    if world_activity and not directory_failed:
        (args.out / "wwff-activity.json").write_text(
            json.dumps({"generated": index_doc["generated"], "refs": world_activity},
                       separators=(",", ":")), encoding="utf-8")

    # If the directory was unreachable, all of these counts are zero — but the
    # corresponding files were deliberately not rewritten above. Writing zeros out
    # would make meta.json lie about what is on disk, and worse: it would wipe the
    # calibration value by which the next build spots that the directory came in
    # truncated. So we keep the previous figures.
    def vorige(sleutel, nu):
        return previous_meta.get(sleutel, nu) if directory_failed else nu

    (args.out / "meta.json").write_text(json.dumps({
        "source_file": args.kmz.name,
        "release": stats["release"],
        "generated": index_doc["generated"],
        "zones": stats["zones"],
        "directory_failed": directory_failed or None,
        "directory_listed": vorige("directory_listed", pt_stats.get("listed")),
        "directory_deleted": vorige("directory_deleted", pt_stats.get("deleted")),
        # The total number of rows read — the calibration value against which the
        # next build notices that the directory came in truncated.
        "directory_rows": vorige("directory_rows", pt_stats.get("rows")),
        "directory_nonwwff": vorige("directory_nonwwff", pt_stats.get("nonwwff")),
        "points_no_polygon": vorige("points_no_polygon", stats["points"]),
        "points_unplaced": vorige("points_unplaced", stats["points_unplaced"]),
        "activity_refs": vorige("activity_refs", len(activity)),
        "world_points": vorige("world_points", len(world_features)),
        # Only a count of what is actually on disk: when wwff-activity.json was
        # not rewritten (directory failed, or the no-counts guard fired), the
        # previous file is still there, and so is its figure.
        "world_activity_refs": (len(world_activity) if world_activity and not directory_failed
                                else previous_meta.get("world_activity_refs", 0)),
        "source_polygons": stats["polygons"],
        "tolerance_deg": args.tolerance,
        "decimals": args.decimals,
        "script_version": SCRIPT_VERSION,
    }, indent=2), encoding="utf-8")

    size = geojson_path.stat().st_size / 1e6
    note = ""
    if args.gzip:
        note = f" ({Path(str(geojson_path) + '.gz').stat().st_size / 1e6:.2f} MB gzipped)"
    pts = ""
    if stats["points"] or stats["points_unplaced"]:
        pts = f" · {stats['points']} points without a polygon"
        if stats["points_unplaced"]:
            pts += f" (+{stats['points_unplaced']} without a coordinate)"
    world_note = f" · {len(world_features)} worldwide WWFF points" if world_features else ""
    if stats.get("world_moved"):
        world_note += f" ({stats['world_moved']} moved off a wrong directory position)"
    print(f"✓ {stats['zones']} zones · {size:.2f} MB{note}{pts}{world_note}", file=sys.stderr)
    if stats["warnings"]:
        print(f"⚠ {len(stats['warnings'])} warnings — see {args.report}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
