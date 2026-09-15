# What actually gets published, without a browser.
#
#     python3 build/tests/test_site.py
#
# Every other test in this folder reads data/ straight off the disk, or serves
# the repository itself over http. None of them ever ran build/site.sh — and
# that is precisely where Diana broke: the conversion wrote data/countries.json
# and data/zones/ correctly, the manifest was merged correctly, the files landed
# on main correctly, and site.sh then published neither of them, because it
# still listed the Belgium-only filenames from before the manifest existed. The
# app found no manifest, fell back to "assume Belgium", and Germany could not be
# selected however often it was rebuilt. 481 checks were green throughout.
#
# So this file runs the real script over a real conversion of two made-up
# countries, and looks at what comes out the other end. The central check reads
# the manifest and demands every file it names — not a list of filenames, which
# is the thing that went stale in the first place.
#
# Everything here is made up on the spot: a KMZ is a zip with a KML in it, and
# the WWFF directory is a CSV. No network, no real data.
import json, pathlib, re, shutil, subprocess, sys, tempfile, zipfile

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
    """Fewer than 5000 rows is treated as an outage rather than as data, so the
    filler below is not padding: without it this exercises the wrong branch."""
    rows = ["program,country,reference,name,status,latitude,longitude,qsoCount,lastAct,IUCNcat,website,iaruLocator",
            "ONFF,Belgium,ONFF-0001,Gebied Een,active,50.85,4.35,120,2025-06-01,IV,,JO20",
            "ONFF,Belgium,ONFF-0002,Gebied Twee,active,50.90,4.40,80,2024-05-02,IV,,JO20",
            "ONFF,Belgium,ONFF-0003,Gebied Zonder Grens,active,50.95,4.45,10,2023-04-03,IV,,JO20",
            "DLFF,Federal Republic Of Germany,DLFF-0001,Gebiet Eins,active,51.10,7.10,55,2025-07-07,II,,JO31",
            "DLFF,Federal Republic Of Germany,DLFF-0002,Gebiet Ohne Grenze,active,51.20,7.20,5,2022-01-01,II,,JO31"]
    for i in range(3, 2600):
        rows.append(f"VKFF,Australia,VKFF-{i:04d},Park {i},active,"
                    f"-{33 + i % 5}.{i % 90:02d},{150 + i % 4}.{i % 80:02d},{i % 300},2023-02-02,II,,QF56")
    for i in range(3, 2600):
        rows.append(f"KFF,United States,KFF-{i:04d},Park {i},active,"
                    f"{38 + i % 5}.{i % 90:02d},-{90 + i % 4}.{i % 80:02d},{i % 300},2024-02-02,II,,EM48")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")

def bouw(repo, kmz_name, program=None):
    """One country, straight into this fake repository's own data/ folder —
    exactly as the workflow does it."""
    cmd = [sys.executable, "build/kmz2geojson.py", "--kmz", f"bron/{kmz_name}",
           "--refs-csv", "bron/dir.csv", "--out", "data",
           "--report", "report.md", "--overrides", "overrides.json"]
    if program:
        cmd += ["--program", program]
    return subprocess.run(cmd, cwd=repo, capture_output=True, text=True)

def publiceer(repo, out="_site"):
    return subprocess.run(["bash", "build/site.sh", out], cwd=repo,
                          capture_output=True, text=True)

with tempfile.TemporaryDirectory() as tmp:
    repo = pathlib.Path(tmp) / "diana"
    repo.mkdir()
    # A repository like the real one, minus its history: the app, the build, and
    # a source/ folder that must not be published.
    shutil.copytree(ROOT / "web", repo / "web")
    shutil.copytree(ROOT / "build", repo / "build")
    (repo / "data").mkdir()
    (repo / "bron").mkdir()
    (repo / "source").mkdir()
    (repo / "source" / "geheim.kmz").write_bytes(b"not for the public")
    (repo / "overrides.json").write_text("{}")
    directory(repo / "bron" / "dir.csv")
    kmz(repo / "bron" / "ONFF 20260101.kmz", "ONFF",
        [("0001", "Gebied Een", 4.35, 50.85), ("0002", "Gebied Twee", 4.40, 50.90)])
    kmz(repo / "bron" / "DLFF 20260601.kmz", "DLFF",
        [("0001", "Gebiet Eins", 7.10, 51.10)])

    print("\n[1] two countries, converted one after the other")
    r = bouw(repo, "ONFF 20260101.kmz")
    ok(r.returncode == 0, f"the ONFF build succeeds{'' if r.returncode == 0 else ': ' + r.stderr[-300:]}")
    r = bouw(repo, "DLFF 20260601.kmz", "DLFF")
    ok(r.returncode == 0, f"the DLFF build succeeds{'' if r.returncode == 0 else ': ' + r.stderr[-300:]}")
    manifest = json.loads((repo / "data" / "countries.json").read_text())
    ok([c["program"] for c in manifest["countries"]] == ["DLFF", "ONFF"],
       "and the manifest holds both")

    print("\n[2] the site is assembled")
    r = publiceer(repo)
    ok(r.returncode == 0, f"site.sh succeeds{'' if r.returncode == 0 else ': ' + r.stderr[-400:]}")
    site = repo / "_site"
    ok((site / "index.html").is_file(), "index.html is there")
    ok((site / "js" / "core.js").is_file(), "and the app's own files")

    print("\n[3] the manifest reaches the site at all")
    # Without this one file the app cannot know that any country other than
    # Belgium exists: loadCountries() falls back to the pre-manifest layout and
    # every other country silently stops being selectable. This was the bug.
    er_is_een = (site / "data" / "countries.json").is_file()
    ok(er_is_een, "data/countries.json is published")
    # Without it there is nothing left to check against, and a traceback says
    # far less than the rest of these lines would — so carry on with an empty
    # one and let every check below fail on its own terms.
    gepubliceerd = json.loads((site / "data" / "countries.json").read_text()) if er_is_een else {"countries": []}
    ok([c["program"] for c in gepubliceerd["countries"]] == ["DLFF", "ONFF"],
       "with both countries still in it")

    print("\n[4] every file the manifest promises is really there")
    # Against the manifest, deliberately, and not against a list of names in
    # this test: a list here would go stale the same way the one in site.sh did.
    for land in gepubliceerd["countries"]:
        for soort, pad in (land.get("files") or {}).items():
            doel = site / "data" / pad
            ok(doel.is_file(), f"{land['program']} {soort}: data/{pad}")
            if doel.is_file() and pad.endswith(".geojson"):
                ok(bool(json.loads(doel.read_text()).get("features")),
                   f"  and it has something in it")

    print("\n[5] the second country is on the published map, not just in the manifest")
    dlff = site / "data" / "zones" / "dlff.geojson"
    duits = json.loads(dlff.read_text()) if dlff.is_file() else {"features": []}
    ok([f["properties"]["ref"] for f in duits["features"]] == ["DLFF-0001"],
       "zones/dlff.geojson holds the German boundary")
    wf = site / "data" / "wwff-world.geojson"
    wereld = json.loads(wf.read_text()) if wf.is_file() else {"features": []}
    progs = {f["properties"]["ref"].split("-")[0] for f in wereld["features"]}
    ok("VKFF" in progs, "and the worldwide points layer is published too")
    # DLFF was built last, ONFF before it — both have boundaries, and both must
    # still be in this shared file. Leaving out "whichever one was built most
    # recently" is exactly the bug that made a country vanish for every viewer
    # who did not happen to have that one loaded.
    ok("DLFF" in progs, "the country just built is in it too, not only ONFF")
    ok("ONFF" in progs, "and so is the one built before it")

    print("\n[6] source/ stays private")
    ok(not (site / "source").exists(), "no source/ folder in the published site")
    ok(not any(p.suffix == ".kmz" for p in site.rglob("*")), "and no KMZ anywhere in it")

    print("\n[7] the version stamp is filled in")
    core = (site / "js" / "core.js").read_text()
    ok("__DIANA_BUILD__" not in core, "the placeholder is gone from js/")
    ok("'dev'" not in core.split("BUILD_TXT")[0].split("const BUILD")[-1],
       "and BUILD is a real value")
    # The service worker gets a cache name per build, so that a new release
    # clears the previous one out by itself instead of waiting for a cache to
    # expire. It must have been rewritten, and to something other than what
    # stands in the repository.
    naam = lambda tekst: (re.search(r"const VERSION\s*=\s*'([^']*)'", tekst) or [None, None])[1]
    in_repo = naam((ROOT / "web" / "sw.js").read_text())
    gepubliceerd_naam = naam((site / "sw.js").read_text())
    ok(bool(gepubliceerd_naam), f"the service worker has a cache name ({gepubliceerd_naam})")
    ok(gepubliceerd_naam != in_repo, f"and it is this build's, not the repository's ({in_repo})")

    print("\n[8] a promise the build cannot keep stops the publication")
    # A manifest entry whose file is missing is a 404 in the field, at the worst
    # possible moment, and says nothing until then. Better to fail here.
    (repo / "data" / "zones" / "dlff.geojson").unlink()
    r = publiceer(repo, "_site2")
    ok(r.returncode != 0, "site.sh refuses to publish")
    ok("zones/dlff.geojson" in (r.stderr + r.stdout), "and names the file it is missing")

    print("\n[9] a data set from before the manifest still publishes")
    # The other direction: nothing about the old layout may have become
    # mandatory. An old-style data folder has no manifest and no zones/.
    oud = pathlib.Path(tmp) / "diana-oud"
    oud.mkdir()
    shutil.copytree(ROOT / "web", oud / "web")
    shutil.copytree(ROOT / "build", oud / "build")
    (oud / "data").mkdir()
    (oud / "data" / "onff.geojson").write_text('{"type":"FeatureCollection","features":[]}')
    (oud / "data" / "onff-index.json").write_text('{"refs":[]}')
    (oud / "data" / "meta.json").write_text('{"release":"2026-01-01"}')
    r = publiceer(oud)
    ok(r.returncode == 0, f"site.sh succeeds without a manifest{'' if r.returncode == 0 else ': ' + r.stderr[-300:]}")
    ok((oud / "_site" / "data" / "onff.geojson").is_file(), "and publishes the old filenames")
    ok("no data/countries.json" in r.stderr, "having said out loud what it did not find")

    print("\n[10] and a data set that has moved on entirely still publishes")
    # The mirror image: once the stale pre-manifest files are deleted from the
    # repository, nothing here may insist on them. They used to be copied
    # unconditionally, so deleting them would have broken every deploy.
    for naam in ("onff.geojson", "onff-index.json", "onff-points.geojson", "onff-activity.json"):
        pad = repo / "data" / naam
        if pad.exists():
            pad.unlink()
    # put the file back that step [8] removed on purpose
    bouw(repo, "DLFF 20260601.kmz", "DLFF")
    r = publiceer(repo, "_site3")
    ok(r.returncode == 0, f"site.sh succeeds with the new layout only{'' if r.returncode == 0 else ': ' + r.stderr[-300:]}")
    ok((repo / "_site3" / "data" / "zones" / "onff.geojson").is_file(), "Belgium still published")
    ok((repo / "_site3" / "data" / "zones" / "dlff.geojson").is_file(), "Germany with it")

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS"))
sys.exit(1 if fails else 0)
