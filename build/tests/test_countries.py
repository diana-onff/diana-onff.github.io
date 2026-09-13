# The per-country build, without a browser.
#
#     python3 build/tests/test_countries.py
#
# Diana began as a Belgian app: one KMZ, one set of files, ONFF written into
# the script in fifteen places. A second country must be a folder in the source
# repo and a flag on a build, not an edit to the code — and, above all, a build
# for one country must be unable to touch another country's data. That last
# rule is what this file is really about. It builds two miniature countries and
# checks that each one keeps its own files, that the manifest grows instead of
# being overwritten, and that a reference with a boundary stops appearing as a
# bare point in the worldwide layer.
#
# Everything here is made up on the spot: a KMZ is a zip with a KML in it, and
# the WWFF directory is a CSV. No network, no real data.
import json, pathlib, subprocess, sys, tempfile, zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "build" / "kmz2geojson.py"
fails = []

def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)

def ring(lon, lat, d=0.01):
    pts = [(lon, lat), (lon + d, lat), (lon + d, lat + d), (lon, lat + d), (lon, lat)]
    return " ".join(f"{x},{y},0" for x, y in pts)

def kmz(path, program, entries):
    """A minimal Google Earth export shaped the way the ONFF one is: the
    reference number lives in the name of the enclosing folder, not in a field."""
    folders = "".join(f"""
      <Folder><name>{program}-{num} {name}</name>
        <Placemark><name>{name}</name><Polygon><outerBoundaryIs><LinearRing>
          <coordinates>{ring(lon, lat)}</coordinates>
        </LinearRing></outerBoundaryIs></Polygon></Placemark>
      </Folder>""" for num, name, lon, lat in entries)
    kml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
           f'<name>{program} release</name>{folders}</Document></kml>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("doc.kml", kml)

def directory(path):
    """The script refuses a directory that looks truncated — fewer than 5000
    rows is treated as an outage, not as data. So the filler is not padding:
    without it this test would exercise the wrong branch."""
    rows = ["program,country,reference,name,status,latitude,longitude,qsoCount,lastAct,IUCNcat,website,iaruLocator",
            "ONFF,Belgium,ONFF-0001,Gebied Een,active,50.85,4.35,120,2025-06-01,IV,,JO20",
            "ONFF,Belgium,ONFF-0002,Gebied Twee,active,50.90,4.40,80,2024-05-02,IV,,JO20",
            "ONFF,Belgium,ONFF-0003,Gebied Zonder Grens,active,50.95,4.45,10,2023-04-03,IV,,JO20",
            "PAFF,Netherlands,PAFF-0001,Park Een,active,52.10,5.10,55,2025-07-07,II,,JO22",
            "PAFF,Netherlands,PAFF-0002,Park Zonder Grens,active,52.20,5.20,5,2022-01-01,II,,JO22"]
    for i in range(1, 2600):
        rows.append(f"DLFF,Federal Republic Of Germany,DLFF-{i:04d},Gebiet {i},active,"
                    f"{51 + i % 3}.{i % 90:02d},{7 + i % 4}.{i % 80:02d},{i % 400},2024-03-03,IV,,JO30")
    for i in range(1, 2600):
        rows.append(f"VKFF,Australia,VKFF-{i:04d},Park {i},active,"
                    f"-{33 + i % 5}.{i % 90:02d},{150 + i % 4}.{i % 80:02d},{i % 300},2023-02-02,II,,QF56")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")

def build(work, out, kmz_name, program=None):
    cmd = [sys.executable, str(SCRIPT), "--kmz", str(work / kmz_name),
           "--refs-csv", str(work / "dir.csv"), "--out", str(out),
           "--report", str(out / "report.md"), "--overrides", str(work / "overrides.json")]
    if program:
        cmd += ["--program", program]
    return subprocess.run(cmd, capture_output=True, text=True)

def refs(path):
    return [f["properties"]["ref"] for f in json.loads(path.read_text())["features"]]

with tempfile.TemporaryDirectory() as tmp:
    work = pathlib.Path(tmp)
    out = work / "data"
    out.mkdir()
    (work / "overrides.json").write_text("{}")
    directory(work / "dir.csv")
    kmz(work / "ONFF 20260101.kmz", "ONFF",
        [("0001", "Gebied Een", 4.35, 50.85), ("0002", "Gebied Twee", 4.40, 50.90)])
    kmz(work / "PAFF 20260201.kmz", "PAFF", [("0001", "Park Een", 5.10, 52.10)])

    print("\n[1] a country lands in its own files")
    r = build(work, out, "ONFF 20260101.kmz")
    ok(r.returncode == 0, f"the ONFF build succeeds{'' if r.returncode == 0 else ': ' + r.stderr[-300:]}")
    ok((out / "zones" / "onff.geojson").exists(), "data/zones/onff.geojson")
    ok((out / "zones" / "onff-points.geojson").exists(), "data/zones/onff-points.geojson")
    ok((out / "zones" / "onff-activity.json").exists(), "data/zones/onff-activity.json")
    ok(refs(out / "zones" / "onff.geojson") == ["ONFF-0001", "ONFF-0002"], "with the two boundaries in it")

    print("\n[2] the manifest says what is on board")
    man = json.loads((out / "countries.json").read_text())
    entry = man["countries"][0]
    ok([c["program"] for c in man["countries"]] == ["ONFF"], "one country listed")
    ok(entry["country"] == "Belgium", f"with its name from the directory ({entry['country']})")
    ok(entry["refs"] == 2 and entry["points"] == 1,
       f"and its counts ({entry['refs']} boundaries, {entry['points']} points)")
    ok(entry["files"]["zones"] == "zones/onff.geojson", "and where its files are")

    print("\n[3] building a second country leaves the first one alone")
    before = (out / "zones" / "onff.geojson").read_bytes()
    r = build(work, out, "PAFF 20260201.kmz", "PAFF")
    ok(r.returncode == 0, f"the PAFF build succeeds{'' if r.returncode == 0 else ': ' + r.stderr[-300:]}")
    ok((out / "zones" / "onff.geojson").read_bytes() == before, "onff.geojson is untouched, byte for byte")
    ok(refs(out / "zones" / "paff.geojson") == ["PAFF-0001"], "and paff.geojson holds only the Dutch one")

    man = json.loads((out / "countries.json").read_text())
    ok([c["program"] for c in man["countries"]] == ["ONFF", "PAFF"],
       "the manifest gained a country instead of being replaced")

    print("\n[4] a reference with a boundary is not also a bare point")
    world = json.loads((out / "wwff-world.geojson").read_text())
    progs = {f["properties"]["ref"].split("-")[0] for f in world["features"]}
    ok("ONFF" not in progs and "PAFF" not in progs,
       f"neither country is in the worldwide points layer ({sorted(progs)})")
    ok("DLFF" in progs, "while a country without boundaries still is")

    print("\n[5] a rebuild of the first country does not drop the second")
    kmz(work / "ONFF 20260301.kmz", "ONFF",
        [("0001", "Gebied Een", 4.35, 50.85), ("0002", "Gebied Twee", 4.40, 50.90),
         ("0004", "Gebied Vier", 4.50, 50.95)])
    r = build(work, out, "ONFF 20260301.kmz")
    ok(r.returncode == 0, "the second ONFF build succeeds")
    ok(len(refs(out / "zones" / "onff.geojson")) == 3, "Belgium now has three boundaries")
    ok(refs(out / "zones" / "paff.geojson") == ["PAFF-0001"], "and the Netherlands is still there")
    man = json.loads((out / "countries.json").read_text())
    ok([c["program"] for c in man["countries"]] == ["ONFF", "PAFF"], "both still in the manifest")
    onff = next(c for c in man["countries"] if c["program"] == "ONFF")
    ok(onff["source_file"] == "ONFF 20260301.kmz", "with Belgium's entry pointing at the new release")

    print("\n[6] a programme code that is not one is refused")
    r = build(work, out, "ONFF 20260301.kmz", "Belgium")
    ok(r.returncode != 0, "--program Belgium stops the build")
    ok("WWFF programme code" in (r.stderr + r.stdout), "and says why")

    print("\n[7] a broken manifest is not fatal")
    (out / "countries.json").write_text("{ this is not json")
    r = build(work, out, "ONFF 20260301.kmz")
    ok(r.returncode == 0, "the build still runs")
    man = json.loads((out / "countries.json").read_text())
    ok([c["program"] for c in man["countries"]] == ["ONFF"],
       "and writes a fresh manifest holding the country it just built")
    ok("could not read" in r.stderr, "having said out loud what it lost")

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS"))
sys.exit(1 if fails else 0)
