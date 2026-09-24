# Which reference number wins when the KMZ's own names disagree about it.
#
#     python3 build/tests/test_kmzrefs.py
#
# A field report: two adjacent ONFF areas, 0253 and 0254, showed one polygon
# for both and a bare marker for the other, and clicking either one landed on
# the wrong name. The KMZ itself turned out to carry the typo: within one
# area's own little group of containers, the placemark's own <name> had the
# wrong number while a container one level up had it right. The reverse also
# happens for real, in the other direction: a broad grouping label one or two
# levels further up (covering several sub-areas at once) disagreeing with an
# already-correct nearest name, which must NOT be allowed to overrule it.
#
# Both shapes look identical from tree position alone, so the tie is broken by
# the WWFF directory's own name for each candidate instead (_resolve_ref() in
# kmz2geojson.py). This is offline and does not touch the network: the
# "directory" here is a small hand-written dict, not a download.
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kmz2geojson as kg  # noqa: E402  path insert above must run first

fails = []


def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)


kg.PROGRAM = "ONFF"
kg.REF_RE = __import__("re").compile(r"ONFF[- ]?(\d{4})(?!\d)")

print("\n[1] name scoring: identical and prefix-stripped names score highest, unrelated ones score low")
ok(kg._name_score("Kollintenbos", "Kollintenbos") == 1.0, "identical names score 1.0")
ok(kg._name_score("ONFF-0254 Kollintenbos", "Kollintenbos") == 1.0,
   "the reference prefix does not lower the score, it is stripped first")
low = kg._name_score("Kollintenbos", "Bos van Aa")
ok(low < 0.4, f"an unrelated name scores low ({low})")

print("\n[2] REF_RE: a release filename is not read as a reference, a real one still is")
ok(kg.REF_RE.search("ONFF 20260801.kmz") is None,
   "'ONFF 20260801.kmz' is not mistaken for ONFF-2026")
m = kg.REF_RE.search("ONFF-0253 Bos van Aa")
ok(bool(m) and m.group(1) == "0253", "a real reference in a name is still found")

print("\n[3] _resolve_ref: a typo in the placemark's own number, an ancestor has it right")
directory = {"ONFF-0253": "Bos van Aa", "ONFF-0254": "Kollintenbos"}
candidates = [("ONFF-0253", "Kollintenbos"), ("ONFF-0254", "Kollintenbos")]  # nearest first
ref, raw, note = kg._resolve_ref(candidates, directory)
ok(ref == "ONFF-0254", f"resolved to ONFF-0254, the one the directory actually calls 'Kollintenbos' (got {ref})")
ok(bool(note) and "ONFF-0253" in note and "ONFF-0254" in note,
   f"the disagreement is written down for the report ({note})")

print("\n[4] _resolve_ref: a broad grouping label further up must not overrule a correct nearest name")
directory2 = {"ONFF-0100": "Vallei van de Grote Nete", "ONFF-0101": "Teunenberg"}
candidates2 = [("ONFF-0101", "Teunenberg"), ("ONFF-0100", "Vallei van de Grote Nete")]
ref2, raw2, note2 = kg._resolve_ref(candidates2, directory2)
ok(ref2 == "ONFF-0101", f"the nearer, already-correct ONFF-0101 wins on an even match (got {ref2})")

print("\n[5] _resolve_ref: no directory at all falls back to the nearest name, exactly as before")
ref3, raw3, note3 = kg._resolve_ref(candidates, {})
ok(ref3 == "ONFF-0253" and note3 is None,
   f"without a directory the nearest name wins and nothing is logged (got {ref3}, {note3})")

print("\n[6] end to end through convert(): the typo is corrected, not just the scoring function")
kml = ('<?xml version="1.0" encoding="UTF-8"?>'
       '<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>ONFF release</name>'
       '<Folder><name>Antwerpen</name>'
       '<Document><name>ONFF-0254 Kollintenbos</name>'
       '<Placemark><name>ONFF-0253 Kollintenbos</name><Polygon><outerBoundaryIs><LinearRing>'
       '<coordinates>4.40,51.20,0 4.41,51.20,0 4.41,51.21,0 4.40,51.21,0 4.40,51.20,0</coordinates>'
       '</LinearRing></outerBoundaryIs></Polygon></Placemark></Document>'
       '<Document><name>ONFF-0253 Bos van Aa</name>'
       '<Placemark><name>ONFF-0253 Bos van Aa</name><Polygon><outerBoundaryIs><LinearRing>'
       '<coordinates>4.30,51.10,0 4.31,51.10,0 4.31,51.11,0 4.30,51.11,0 4.30,51.10,0</coordinates>'
       '</LinearRing></outerBoundaryIs></Polygon></Placemark></Document>'
       '</Folder></Document></kml>')
work = Path(tempfile.mkdtemp(prefix="diana-kmzrefs-"))
kml_path = work / "doc.kml"
kml_path.write_text(kml, encoding="utf-8")
geojson, index_doc, stats = kg.convert(kml_path, tolerance=0.00005, decimals=5, overrides={},
                                        directory_names=directory)
refs = {f["properties"]["ref"] for f in geojson["features"]}
ok(refs == {"ONFF-0253", "ONFF-0254"}, f"both references end up with their own polygon ({refs})")
names = {f["properties"]["ref"]: f["properties"]["name"] for f in geojson["features"]}
ok(names.get("ONFF-0254") == "Kollintenbos", f"ONFF-0254 carries its own name ({names.get('ONFF-0254')})")
ok(names.get("ONFF-0253") == "Bos van Aa",
   f"ONFF-0253 keeps its own, unrelated polygon and name ({names.get('ONFF-0253')})")
ok(any("ONFF-0253" in w and "ONFF-0254" in w for w in stats["warnings"]),
   "the mixup is written into the conversion report")

print("\n[7] convert() without a directory: unchanged, nearest name still wins, nothing to compare against")
geojson2, _, stats2 = kg.convert(kml_path, tolerance=0.00005, decimals=5, overrides={}, directory_names=None)
refs2 = {f["properties"]["ref"] for f in geojson2["features"]}
ok(refs2 == {"ONFF-0253"},
   f"both placemarks are read as ONFF-0253 (the nearest name each time), same as before this fix ({refs2})")

print("\n[8] the geometric safety net: a point-only reference sitting inside someone else's polygon")
fake_geojson = {"features": [
    {"type": "Feature", "properties": {"ref": "ONFF-0001"},
     "geometry": {"type": "Polygon",
                  "coordinates": [[[4.0, 51.0], [4.2, 51.0], [4.2, 51.2], [4.0, 51.2], [4.0, 51.0]]]}},
]}
inside_pt = [{"properties": {"ref": "ONFF-0002"}, "geometry": {"type": "Point", "coordinates": [4.1, 51.1]}}]
outside_pt = [{"properties": {"ref": "ONFF-0004"}, "geometry": {"type": "Point", "coordinates": [10.0, -75.0]}}]
w_in = kg._point_inside_other_polygon_warnings(fake_geojson, inside_pt)
w_out = kg._point_inside_other_polygon_warnings(fake_geojson, outside_pt)
ok(len(w_in) == 1 and "ONFF-0002" in w_in[0] and "ONFF-0001" in w_in[0],
   f"a point-only reference inside another polygon is flagged ({w_in})")
ok(len(w_out) == 0, f"a genuinely point-only reference far away, like ONFF-0004 in Antarctica, stays quiet ({w_out})")

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS: " + " | ".join(fails)))
sys.exit(1 if fails else 0)
