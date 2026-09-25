# Wrong WWFF-directory positions, and what Diana puts in the world file instead.
#
#     python3 build/tests/test_worldpos.py
#
# No browser, no network: kmz2geojson.py is run for real, on made-up KMZs and a
# made-up directory, into a throwaway repository.
#
# The real case: the WWFF directory gives ONFF-0850 Helschot the exact
# coordinates of ONFF-0849 Tommelen, 41 km away, and four more ONFF references
# copy a neighbour the same way (DLFF and PAFF have their own). Diana's
# boundaries are right, so the worldwide points file, which Nearby > Info,
# other viewers' points layer and agenda pins all read, should use a point
# inside the boundary for those. Only for those: a directory position inside or
# just off its boundary is left alone. And because every country's build
# rewrites that one shared file, a correction made while building one country
# must survive the next build of another: the file has had exactly that kind
# of build-order bug before.
import json, pathlib, shutil, subprocess, sys, tempfile, zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
fails = []


def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)


def ring(lon, lat, d=0.01):
    pts = [(lon, lat), (lon + d, lat), (lon + d, lat + d), (lon, lat + d), (lon, lat)]
    return " ".join(f"{x},{y},0" for x, y in pts)


def kmz(path, program, entries):
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
    """At least 5000 rows, or the build treats it as an outage."""
    rows = ["program,country,reference,name,status,latitude,longitude,qsoCount,lastAct",
            # inside its own boundary (4.35..4.36, 50.85..50.86): left alone
            "ONFF,Belgium,ONFF-0001,Tommelen,active,50.855,4.355,10,2025-01-01",
            # boundary 25 km away, directory copies ONFF-0001 exactly
            "ONFF,Belgium,ONFF-0002,Helschot,active,50.855,4.355,20,2025-01-01",
            # just off its boundary (a few hundred metres): rounding, left alone
            "ONFF,Belgium,ONFF-0005,Rand,active,50.705,4.2064,5,2025-01-01",
            # no boundary at all: the directory's position is all there is
            "ONFF,Belgium,ONFF-0003,Zonder Grens,active,51.2,4.9,3,2024-01-01",
            # no boundary, placed by hand in overrides.json
            "ONFF,Belgium,ONFF-0004,Met Override,active,51.3,5.0,1,2024-01-01",
            "DLFF,Germany,DLFF-0001,Eins,active,51.105,7.105,7,2025-01-01",
            # German one copying its neighbour, boundary 45 km away
            "DLFF,Germany,DLFF-0002,Zwei,active,51.105,7.105,8,2025-01-01"]
    for i in range(3, 5200):
        rows.append(f"VKFF,Australia,VKFF-{i:04d},Park {i},active,-33.{i % 90:02d},150.{i % 80:02d},{i % 300},2023-02-02")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def bouw(repo, kmz_name, program, *extra):
    cmd = [sys.executable, "build/kmz2geojson.py", "--kmz", f"bron/{kmz_name}", "--program", program,
           "--refs-csv", "bron/dir.csv", "--out", "data", "--report", "report.md",
           "--overrides", "overrides.json", *extra]
    return subprocess.run(cmd, cwd=repo, capture_output=True, text=True)


def world(repo):
    doc = json.loads((repo / "data" / "wwff-world.geojson").read_text())
    return {f["properties"]["ref"]: f["geometry"]["coordinates"] for f in doc["features"]}


def inside(xy, lon, lat, d=0.01):
    return lon <= xy[0] <= lon + d and lat <= xy[1] <= lat + d


with tempfile.TemporaryDirectory() as tmp:
    repo = pathlib.Path(tmp) / "diana"
    repo.mkdir()
    shutil.copytree(ROOT / "build", repo / "build")
    (repo / "data").mkdir()
    (repo / "bron").mkdir()
    (repo / "overrides.json").write_text(json.dumps({"zones": {"ONFF-0004": {"point": [5.5, 51.5]}}}))
    directory(repo / "bron" / "dir.csv")
    kmz(repo / "bron" / "onff.kmz", "ONFF", [("0001", "Tommelen", 4.35, 50.85),
                                              ("0002", "Helschot", 4.60, 51.00),
                                              ("0005", "Rand", 4.21, 50.70)])
    kmz(repo / "bron" / "dlff.kmz", "DLFF", [("0001", "Eins", 7.10, 51.10),
                                              ("0002", "Zwei", 7.70, 51.30)])

    print("\n[1] building Belgium")
    r = bouw(repo, "onff.kmz", "ONFF")
    ok(r.returncode == 0, "the ONFF build succeeds" + ("" if r.returncode == 0 else ": " + r.stderr[-300:]))
    w = world(repo)
    ok(inside(w["ONFF-0002"], 4.60, 51.00), f"ONFF-0002 moved inside its own boundary ({w['ONFF-0002']})")
    ok(w["ONFF-0001"] == [4.355, 50.855], f"ONFF-0001, already inside, keeps the directory's position ({w['ONFF-0001']})")
    ok(w["ONFF-0005"] == [4.2064, 50.705], f"ONFF-0005, a few hundred metres off its edge, is left alone ({w['ONFF-0005']})")
    ok(w["ONFF-0003"] == [4.9, 51.2], f"ONFF-0003, no boundary, keeps the directory's position ({w['ONFF-0003']})")
    ok(w["ONFF-0004"] == [5.5, 51.5], f"ONFF-0004, placed in overrides.json, is at that position ({w['ONFF-0004']})")
    report = (repo / "report.md").read_text()
    ok("`ONFF-0002` Helschot" in report and "exact coordinates of `ONFF-0001`" in report,
       "the report lists ONFF-0002 as a copy of ONFF-0001's coordinates")
    block = report.split("📍")[1].split("</details>")[0] if "📍" in report else ""
    listed = [l.split("`")[1] for l in block.splitlines() if l.startswith("- `")]
    ok(listed == ["ONFF-0002"], f"and lists nothing else ({listed})")
    idx = json.loads((repo / "data" / "zones" / "onff-index.json").read_text())
    marked = [e["ref"] for e in idx["refs"] if e.get("world")]
    ok(marked == ["ONFF-0002"], f"the decision is stored in Belgium's own index ({marked})")

    print("\n[2] building Germany afterwards, which rewrites the shared world file")
    r = bouw(repo, "dlff.kmz", "DLFF")
    ok(r.returncode == 0, "the DLFF build succeeds" + ("" if r.returncode == 0 else ": " + r.stderr[-300:]))
    w = world(repo)
    ok(inside(w["DLFF-0002"], 7.70, 51.30), f"DLFF-0002 moved inside its own boundary ({w['DLFF-0002']})")
    ok(inside(w["ONFF-0002"], 4.60, 51.00), f"and Belgium's correction survived ({w['ONFF-0002']})")
    ok(w["ONFF-0004"] == [5.5, 51.5], "and so did Belgium's hand-placed point")

    print("\n[3] Belgium rebuilt without the directory, then Germany again")
    r = bouw(repo, "onff.kmz", "ONFF", "--no-refs")
    ok(r.returncode == 0, "the ONFF build without the directory succeeds" + ("" if r.returncode == 0 else ": " + r.stderr[-300:]))
    idx = json.loads((repo / "data" / "zones" / "onff-index.json").read_text())
    ok([e["ref"] for e in idx["refs"] if e.get("world")] == ["ONFF-0002"],
       "with nothing to compare against, it keeps what the previous build decided")
    r = bouw(repo, "dlff.kmz", "DLFF")
    w = world(repo)
    ok(inside(w["ONFF-0002"], 4.60, 51.00), f"so the next German build still applies it ({w['ONFF-0002']})")

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS: " + " | ".join(fails)))
sys.exit(1 if fails else 0)
