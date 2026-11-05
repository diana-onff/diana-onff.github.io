# The last activation per reference for every programme (since 2.2.5):
# data/lastact/<prog>.json, written from the directory's lastAct column.
#
#     python3 build/tests/test_lastact.py
#
# No browser, no network. Part [1] calls point_refs() directly: a plausible
# date is kept (first ten characters), the year 1059 the real directory has is
# dropped, an empty cell gives nothing. Part [2] runs the real build over a
# small made-up directory, the same way test_sites.py does: one file per
# programme, no timestamp in them, and a directory without the lastAct column
# leaves the files that are there alone.
import json, pathlib, shutil, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "build"))
import kmz2geojson as kg  # noqa: E402

fails = []


def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)


def row(ref, last, status="active"):
    return {"program": ref.split("-")[0], "country": "X", "reference": ref, "name": ref, "status": status,
            "latitude": "50.0", "longitude": "4.0", "qsoCount": "5" if last else "", "lastAct": last, "website": ""}


print("\n[1] point_refs(): which dates are kept")
out = kg.point_refs([row("EAFF-0001", "2025-03-14"), row("EAFF-0002", "1059-01-01"),
                     row("EAFF-0003", ""), row("VKFF-0010", "2019-07-02 00:00:00"),
                     row("EAFF-0004", "2024-01-01", status="deleted")], [], False, ["ONFF"], set(), {}, 5)
last = out[9]
ok(last.get("EAFF-0001") == "2025-03-14", f"a real date is kept ({last.get('EAFF-0001')})")
ok("EAFF-0002" not in last, "the year 1059 is dropped")
ok("EAFF-0003" not in last, "an empty cell gives no date")
ok(last.get("VKFF-0010") == "2019-07-02", "a date with a time keeps the date only")
ok("EAFF-0004" not in last, "a deleted reference is left out")
ok(len(out) == 10 and isinstance(out[8], dict), "the earlier return values are where they were")

# ---------------------------------------------------------------- [2] build
import zipfile  # noqa: E402


def kmz(path):
    """One area, ONFF-0001, the same as in test_sites.py."""
    ring = " ".join(f"{x},{y},0" for x, y in [(4.35, 50.85), (4.36, 50.85), (4.36, 50.86), (4.35, 50.86), (4.35, 50.85)])
    kml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>ONFF release</name>'
           '<Folder><name>ONFF-0001 Gebied Een</name><Placemark><name>Gebied Een</name>'
           f'<Polygon><outerBoundaryIs><LinearRing><coordinates>{ring}</coordinates>'
           '</LinearRing></outerBoundaryIs></Polygon></Placemark></Folder></Document></kml>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("doc.kml", kml)


def directory(path, with_column=True):
    head = "program,country,reference,name,status,latitude,longitude,qsoCount" + (",lastAct" if with_column else "")
    def r(prog, ref, lat, lon, d):
        return f"{prog},X,{ref},{ref},active,{lat},{lon},5" + (f",{d}" if with_column else "")
    rows = [head, r("ONFF", "ONFF-0001", 50.85, 4.35, "2024-05-01"), r("EAFF", "EAFF-0001", 41.9, 2.8, "2025-03-14")]
    for i in range(3, 5200):
        rows.append(r("VKFF", f"VKFF-{i:04d}", -33.5, 150.5, "2023-01-0%d" % (1 + i % 9)))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def bouw(repo):
    return subprocess.run([sys.executable, "build/kmz2geojson.py", "--kmz", "bron/ONFF 20260101.kmz",
                           "--refs-csv", "bron/dir.csv", "--out", "data", "--report", "report.md",
                           "--overrides", "overrides.json"], cwd=repo, capture_output=True, text=True)


print("\n[2] the files in data/lastact/")
with tempfile.TemporaryDirectory() as tmp:
    repo = pathlib.Path(tmp) / "diana"
    repo.mkdir()
    shutil.copytree(ROOT / "build", repo / "build")
    (repo / "data").mkdir(); (repo / "bron").mkdir()
    (repo / "overrides.json").write_text("{}")
    kmz(repo / "bron" / "ONFF 20260101.kmz")
    ld = repo / "data" / "lastact"
    directory(repo / "bron" / "dir.csv")
    r = bouw(repo)
    ok(r.returncode == 0, "the build succeeds" + ("" if r.returncode == 0 else ": " + r.stderr[-300:]))
    names = sorted(p.name for p in ld.glob("*.json"))
    ok(names == ["eaff.json", "onff.json", "vkff.json"], f"one file per programme ({names})")
    ea = json.loads((ld / "eaff.json").read_text())
    ok(ea == {"refs": {"EAFF-0001": "2025-03-14"}}, f"EAFF-0001 with its date, nothing else ({ea})")
    ok("generated" not in (ld / "onff.json").read_text(), "no timestamp, so a quiet night changes nothing")
    stamp = (ld / "eaff.json").stat().st_mtime_ns
    directory(repo / "bron" / "dir.csv", with_column=False)
    r = bouw(repo)
    ok(r.returncode == 0, "a directory without the lastAct column still builds")
    ok((ld / "eaff.json").stat().st_mtime_ns == stamp, "and leaves the date files alone")
    ok("no activation dates at all" in (repo / "report.md").read_text(encoding="utf-8"), "while the report says why")

    site = subprocess.run(["bash", "build/site.sh", str(pathlib.Path(tmp) / "site")], cwd=repo, capture_output=True, text=True)
    ok((pathlib.Path(tmp) / "site" / "data" / "lastact" / "eaff.json").is_file() or site.returncode != 0,
       "site.sh publishes data/lastact/" + ("" if site.returncode == 0 else f" (site.sh stopped: {site.stderr[-120:]})"))

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS: " + " | ".join(fails)))
sys.exit(1 if fails else 0)
