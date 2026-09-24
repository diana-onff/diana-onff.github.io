#!/usr/bin/env python3
"""
Diana: CQ zone, ITU zone and ITU region polygons for the Info tab.

Writes one compact file, web/geo/radio-zones.json, that the app loads the first
time someone opens Nearby > Info. It is reference data that changes perhaps
once a decade, so this is NOT part of the nightly build: run it by hand when a
source changes, and commit the output.

Sources (all free to bundle, see LICENSE part 3):

  CQ and ITU zones   HB9HIL/hamradio-zones-geojson, MIT licence.
                     git clone --depth 1 https://github.com/HB9HIL/hamradio-zones-geojson
  ITU regions        Built here from the definitions of lines A, B and C in the
                     ITU Radio Regulations, Article 5 (a treaty text: facts, not
                     a work anyone owns), plus the country exceptions it names.
  Country borders    Natural Earth, admin-0 countries 1:50m, public domain. Only
                     needed for those exceptions (the CIS countries, Mongolia,
                     Turkey, Ukraine are Region 1 wherever they are; Iran is
                     Region 3 wherever it is).
                     git clone --depth 1 --filter=blob:none --sparse \
                       https://github.com/nvkelso/natural-earth-vector
                     git sparse-checkout set --no-cone /geojson/ne_50m_admin_0_countries.geojson

Usage:

  python3 build/radiozones.py \
      --zones  /path/to/hamradio-zones-geojson \
      --countries /path/to/ne_50m_admin_0_countries.geojson \
      [--out web/geo/radio-zones.json]

How the file is shaped, and why:

  * Every polygon is simplified (Douglas-Peucker, 0.03 degree, about 3 km) and
    rounded to 3 decimals (about 100 m). The zone lines in the source are not
    survey-grade to begin with, and the app says "near a boundary" whenever
    your position or its margin could fall on either side; see radiogeo.js.
  * Longitudes are NOT folded into -180..180. Zones and regions that cross the
    date line are drawn in a continuous longitude range (the source zones run
    from about -205 to +192), so a lookup tries lon, lon+360 and lon-360.
    Folding would cut polygons in two for no gain.
  * Each polygon carries its bounding box, so a lookup skips almost all of
    them with four comparisons.
"""
import argparse, datetime, json, math, pathlib, subprocess, sys

from shapely.geometry import shape, mapping, Polygon, MultiPolygon, box
from shapely.ops import unary_union
from shapely.validation import make_valid

SIMPLIFY_DEG = 0.03
DECIMALS = 3

# ---------- ITU Radio Regulations, Article 5, lines A, B and C ----------
# (lat, lon) waypoints; consecutive waypoints are joined by a great circle arc
# unless both lie on the same meridian or the same parallel, where the text
# says "along" (a meridian is a great circle anyway; a parallel is not).
BERING = -(168 + 58 / 60 + 49.4 / 3600)   # international boundary at 65 deg 30' N
TROPIC = 23 + 26 / 60                      # Tropic of Cancer, as used in the text

LINE_A = [(90, 40), (40, 40), ("arc", TROPIC, 60), (-90, 60)]
LINE_B = [(90, -10), (72, -10), ("arc", 40, -50), ("arc", -10, -20), (-90, -20)]
# Line C, drawn west of the date line (165 E written as -195), so that it is
# one continuous line from pole to pole in this longitude range.
LINE_C = [(90, BERING), (65.5, BERING), ("arc", 50, -195), ("arc", 10, -170),
          ("par", 10, -120), (-90, -120)]

# Region 1 wherever they are, per Article 5 (ISO 3166 alpha-3 as Natural Earth
# carries it in ADM0_A3).
REGION1_COUNTRIES = {"ARM", "AZE", "GEO", "KAZ", "MNG", "UZB", "KGZ", "RUS",
                     "TJK", "TKM", "TUR", "UKR"}
REGION3_COUNTRIES = {"IRN"}
# "...and the area to the north of Russia which lies between lines A and C".
# Between those lines, everything north of 60 N is Russia or the sea north of
# it, so a plain latitude cut says exactly that.
ARCTIC_NORTH_OF_RUSSIA = box(-400, 60, 400, 90)
# Enclosed water surrounded by Region 1 countries, which the line rule alone
# would hand to Region 3 because it lies just east of line A. A hand box,
# stated as such: see radiogeo.js for how "near a boundary" covers the rest.
REGION1_WATER = [box(46.5, 36.5, 55.0, 47.3),   # Caspian Sea
                 box(40.0, 40.9, 42.0, 47.4)]   # eastern Black Sea


def gc_points(lat1, lon1, lat2, lon2, n=90):
    """Points along the great circle arc between two positions, longitudes kept
    continuous with lon1 (no jump at the date line)."""
    r = math.radians
    p1 = [math.cos(r(lat1)) * math.cos(r(lon1)), math.cos(r(lat1)) * math.sin(r(lon1)), math.sin(r(lat1))]
    p2 = [math.cos(r(lat2)) * math.cos(r(lon2)), math.cos(r(lat2)) * math.sin(r(lon2)), math.sin(r(lat2))]
    dot = max(-1.0, min(1.0, sum(a * b for a, b in zip(p1, p2))))
    om = math.acos(dot)
    out, prev = [], lon1
    for i in range(n + 1):
        t = i / n
        if om < 1e-12:
            v = p1
        else:
            s1, s2 = math.sin((1 - t) * om) / math.sin(om), math.sin(t * om) / math.sin(om)
            v = [s1 * a + s2 * b for a, b in zip(p1, p2)]
        lat = math.degrees(math.atan2(v[2], math.hypot(v[0], v[1])))
        lon = math.degrees(math.atan2(v[1], v[0]))
        while lon - prev > 180: lon -= 360
        while lon - prev < -180: lon += 360
        prev = lon
        out.append((lon, lat))
    return out


def line_points(spec):
    """A line as a list of (lon, lat), north to south."""
    pts = [(spec[0][1], spec[0][0])]
    for step in spec[1:]:
        lat0, lon0 = pts[-1][1], pts[-1][0]
        if step[0] == "arc":
            _, lat, lon = step
            pts += gc_points(lat0, lon0, lat, lon)[1:]
        elif step[0] == "par":
            _, lat, lon = step
            pts.append((lon, lat))
        else:
            lat, lon = step
            pts.append((lon, lat))
    return pts


def between(west, east):
    """The area east of line `west` and west of line `east` (both north to south)."""
    ring = west + list(reversed(east))
    return make_valid(Polygon(ring))


def shifted(g, dx):
    from shapely import affinity
    return affinity.translate(g, xoff=dx)


def with_copies(g):
    return unary_union([g, shifted(g, -360), shifted(g, 360)])


def polygons_only(g):
    g = make_valid(g)
    if isinstance(g, Polygon):
        return MultiPolygon([g])
    if isinstance(g, MultiPolygon):
        return g
    parts = [p for p in getattr(g, "geoms", []) if isinstance(p, (Polygon, MultiPolygon))]
    flat = []
    for p in parts:
        flat += list(p.geoms) if isinstance(p, MultiPolygon) else [p]
    return MultiPolygon(flat)


def compact(g):
    g = polygons_only(g.simplify(SIMPLIFY_DEG, preserve_topology=True))
    polys = []
    for p in g.geoms:
        if p.area < 1e-6:
            continue
        rings = [[[round(x, DECIMALS), round(y, DECIMALS)] for x, y in p.exterior.coords]]
        rings += [[[round(x, DECIMALS), round(y, DECIMALS)] for x, y in h.coords] for h in p.interiors]
        polys.append(rings)
    minx, miny, maxx, maxy = g.bounds
    return {"b": [round(minx, DECIMALS), round(miny, DECIMALS), round(maxx, DECIMALS), round(maxy, DECIMALS)],
            "c": polys}


def git_head(path):
    try:
        return subprocess.check_output(["git", "-C", str(path), "log", "-1", "--format=%H %cs"], text=True).strip()
    except Exception:
        return "unknown"


def regions(countries_path):
    a, b, c = line_points(LINE_A), line_points(LINE_B), line_points(LINE_C)
    c_east = [(lon + 360, lat) for lon, lat in c]
    r1 = between(b, a)            # east of B, west of A
    r2 = between(c, b)            # east of C, west of B
    r3 = between(a, c_east)       # east of A, west of C (one turn further east)

    nat = json.loads(pathlib.Path(countries_path).read_text(encoding="utf-8"))
    def pick(codes):
        found = {}
        for f in nat["features"]:
            code = f["properties"].get("ADM0_A3")
            if code in codes:
                found[code] = make_valid(shape(f["geometry"]))
        missing = codes - set(found)
        if missing:
            sys.exit(f"radiozones: not in the country file: {sorted(missing)}")
        return with_copies(unary_union(list(found.values())))
    r1c, r3c = pick(REGION1_COUNTRIES), pick(REGION3_COUNTRIES)
    water = with_copies(unary_union(REGION1_WATER))

    to_r1 = unary_union([r1c, (r3.intersection(ARCTIC_NORTH_OF_RUSSIA)), water.difference(r3c)])
    R1 = unary_union([r1.difference(r3c), (r2.union(r3)).intersection(to_r1)])
    R2 = r2.difference(to_r1)
    R3 = unary_union([r3.difference(to_r1), r1.intersection(r3c)])
    return {1: R1, 2: R2, 3: R3}


def zones(path, key):
    d = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    out = {}
    for f in d["features"]:
        n = int(f["properties"][f"{key}_zone_number"])
        g = make_valid(shape(f["geometry"]))
        out[n] = unary_union([out[n], g]) if n in out else g
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zones", required=True, help="checkout of HB9HIL/hamradio-zones-geojson")
    ap.add_argument("--countries", required=True, help="Natural Earth ne_50m_admin_0_countries.geojson")
    ap.add_argument("--out", default="web/geo/radio-zones.json")
    args = ap.parse_args()

    zp = pathlib.Path(args.zones)
    cq = zones(zp / "cqzones.geojson", "cq")
    itu = zones(zp / "ituzones.geojson", "itu")
    reg = regions(args.countries)
    if len(cq) != 40:
        sys.exit(f"radiozones: expected 40 CQ zones, got {len(cq)}")
    if len(itu) != 90:
        sys.exit(f"radiozones: expected 90 ITU zones, got {len(itu)}")

    doc = {
        "v": 1,
        "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": {
            "zones": {"name": "HB9HIL/hamradio-zones-geojson", "licence": "MIT",
                      "copyright": "Copyright (c) 2024 HB9HIL", "commit": git_head(zp)},
            "regions": {"name": "ITU Radio Regulations, Article 5 (lines A, B, C)"},
            "countries": {"name": "Natural Earth admin-0 1:50m", "licence": "public domain"},
        },
        "cq":     [dict(n=n, **compact(g)) for n, g in sorted(cq.items())],
        "itu":    [dict(n=n, **compact(g)) for n, g in sorted(itu.items())],
        "region": [dict(n=n, **compact(g)) for n, g in sorted(reg.items())],
    }
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
    print(f"radiozones: wrote {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
