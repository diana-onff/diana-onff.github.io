# The website link per reference behind the "More info" line on the spot
# detail sheet: how the build reads the directory's website column, and what
# it writes to data/sites/.
#
#     python3 build/tests/test_sites.py
#
# No browser, no network. Part [1] feeds clean_website() the shapes the real
# WWFF directory actually has in that column (checked against the real export:
# some 64,000 filled-in cells, a third of them "-", plus bare "www." and bare
# "domain/path" addresses, two links glued together, and plain sentences). The
# app puts whatever comes out behind a tap, so the important half of this test
# is what must NOT come out: javascript:, data:, free text.
#
# Part [2] calls point_refs() directly. Part [3] runs the real build twice over
# a small made-up directory and checks that a programme which lost its last
# link also loses its file, and that a directory without any website column
# at all leaves the files that are there alone.
import json, pathlib, shutil, subprocess, sys, tempfile, zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "build"))
import kmz2geojson as kg  # noqa: E402  path insert above must run first

fails = []


def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)


print("\n[1] clean_website() on what the real directory writes")
cases = [
    ("http://valleivandezuidleie.be/leiemeersen-noord/", "http://valleivandezuidleie.be/leiemeersen-noord/"),
    ("https://www.natuurpunt.be/natuurgebied/fonteintjes", "https://www.natuurpunt.be/natuurgebied/fonteintjes"),
    ("www.hetleen.be./bos-en-arboretum/bos", "http://www.hetleen.be/bos-en-arboretum/bos"),   # ONFF-0115
    ("protectedplanet.net/555542723", "http://protectedplanet.net/555542723"),
    ("http://- https://azoresflorafauna.wixsite.com/azores", "https://azoresflorafauna.wixsite.com/azores"),
    ("http://-https://inpn.mnhn.fr/zone/znieff/110001", "https://inpn.mnhn.fr/zone/znieff/110001"),
    ("-https://inpn.mnhn.fr/zone/znieff/110001", "https://inpn.mnhn.fr/zone/znieff/110001"),
    ("http://\xa0https://inpn.mnhn.fr/zone/znieff/540003220", "https://inpn.mnhn.fr/zone/znieff/540003220"),
    ("http://a.example.org/x?Ap=34 ;  https://b.example.org/23", "http://a.example.org/x?Ap=34"),
    ("Reserve. Operation only with permission  http://www.societe.org.gg/reserves/",
     "http://www.societe.org.gg/reserves/"),
]
for raw, want in cases:
    got = kg.clean_website(raw)
    ok(got == want, f"{raw[:48]!r} -> {got!r}")

refused = ["", "-", "n/a", "None", "http://None", "http://", "http://ArdoisiÃ¨res Sainte-AdÃ¨le",  # ONFF-0287
           "NSG Steinbruchgelaende Hohenhagen", "Valencia Harbour/Portmagee Channel",
           "Rocky outcrop - No access", "e.g. St.Johns park",
           "javascript:alert(1)", "JaVaScRiPt:alert(1)", "data:text/html,<b>x</b>",
           "http://<script>.com", "http://ex\"ample.org/", "file:///C:/Users/x/a.pdf",
           "htpps://www.protectedplanet.net/555", "http://a.example.be\\@b.example.be/"]
for raw in refused:
    got = kg.clean_website(raw)
    ok(got is None, f"{raw[:48]!r} is no link ({got!r})")
ok(kg.clean_website(None) is None, "None is no link")


def row(ref, website="", status="active"):
    return {"program": ref.split("-")[0], "country": "X", "reference": ref, "name": ref,
            "status": status, "latitude": "50.5", "longitude": "4.5",
            "qsoCount": "5", "lastAct": "2024-01-01", "website": website}


def world_sites(rows, have=frozenset()):
    out = kg.point_refs(rows, [], False, ["ONFF"], set(have), {}, 5)
    return out[8], out[3], out[0]   # (world_sites, warnings, point features)


print("\n[2] point_refs(): every programme, with or without a boundary")
ws, warn, pts = world_sites([
    row("ONFF-0001", "http://www.een.be/"),          # has a boundary (in `have`)
    row("ONFF-0004", "http://www.antarcticstation.org/"),   # point only
    row("ONFF-0005", "-"),
    row("DLFF-0001", "www.eins.de"),
    row("VKFF-0010", "https://parks.example.au/10"),
    row("PAFF-0003", "http://deleted.example.nl/", status="deleted"),
    row("OZFF-0001", "javascript:alert(1)"),
], have={"ONFF-0001"})
ok(ws.get("ONFF-0001") == "http://www.een.be/", "a reference WITH a boundary gets its link (this was never read before)")
ok(ws.get("ONFF-0004") == "http://www.antarcticstation.org/", "a point-only reference too")
ok(ws.get("DLFF-0001") == "http://www.eins.de", "another programme, cleaned up")
ok(ws.get("VKFF-0010") == "https://parks.example.au/10", "a programme without boundaries at all")
ok("ONFF-0005" not in ws and "OZFF-0001" not in ws, "no '-', no javascript:")
ok("PAFF-0003" not in ws, "a deleted reference is left out")
p4 = next((f for f in pts if f["properties"]["ref"] == "ONFF-0004"), None)
ok(p4 is not None and p4["properties"].get("site") == "http://www.antarcticstation.org/",
   "the point file's own 'site' goes through the same cleaning")
ok(not any("website" in w for w in warn), "no warning on an ordinary directory")

ws2, warn2, _ = world_sites([row("ONFF-0001"), row("DLFF-0001"), row("VKFF-0001")])
ok(ws2 == {}, "a directory with an empty website column everywhere yields nothing")
ok(any("no website links at all" in w for w in warn2), "and the report says why")


# ---------------------------------------------------------------- [3] build
def ring(lon, lat, d=0.01):
    pts = [(lon, lat), (lon + d, lat), (lon + d, lat + d), (lon, lat + d), (lon, lat)]
    return " ".join(f"{x},{y},0" for x, y in pts)


def kmz(path):
    kml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>ONFF release</name>'
           '<Folder><name>ONFF-0001 Gebied Een</name><Placemark><name>Gebied Een</name>'
           f'<Polygon><outerBoundaryIs><LinearRing><coordinates>{ring(4.35, 50.85)}</coordinates>'
           '</LinearRing></outerBoundaryIs></Polygon></Placemark></Folder></Document></kml>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("doc.kml", kml)


def directory(path, paff_site, with_column=True):
    """Over 5000 rows, or the build reads it as an outage rather than as data."""
    head = "program,country,reference,name,status,latitude,longitude,qsoCount,lastAct"
    head += ",website" if with_column else ""
    def r(prog, country, ref, lat, lon, site):
        base = f"{prog},{country},{ref},{ref},active,{lat},{lon},5,2024-01-01"
        return base + (f",{site}" if with_column else "")
    rows = [head,
            r("ONFF", "Belgium", "ONFF-0001", 50.85, 4.35, "http://www.een.be/"),
            r("PAFF", "Netherlands", "PAFF-0001", 52.1, 5.1, paff_site)]
    for i in range(3, 5200):
        rows.append(r("VKFF", "Australia", f"VKFF-{i:04d}", -33.5, 150.5,
                      "https://parks.example.au/10" if i == 10 else ""))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def bouw(repo):
    return subprocess.run([sys.executable, "build/kmz2geojson.py", "--kmz", "bron/ONFF 20260101.kmz",
                           "--refs-csv", "bron/dir.csv", "--out", "data", "--report", "report.md",
                           "--overrides", "overrides.json"], cwd=repo, capture_output=True, text=True)


print("\n[3] the files in data/sites/, over two builds")
with tempfile.TemporaryDirectory() as tmp:
    repo = pathlib.Path(tmp) / "diana"
    repo.mkdir()
    shutil.copytree(ROOT / "build", repo / "build")
    (repo / "data").mkdir()
    (repo / "bron").mkdir()
    (repo / "overrides.json").write_text("{}")
    kmz(repo / "bron" / "ONFF 20260101.kmz")
    sd = repo / "data" / "sites"

    directory(repo / "bron" / "dir.csv", "http://www.paff.example.nl/")
    r = bouw(repo)
    ok(r.returncode == 0, "first build succeeds" + ("" if r.returncode == 0 else ": " + r.stderr[-300:]))
    ok(sorted(p.name for p in sd.glob("*.json")) == ["onff.json", "paff.json", "vkff.json"],
       f"one file per programme with a link ({sorted(p.name for p in sd.glob('*.json'))})")
    body = (sd / "onff.json").read_text()
    ok("generated" not in body, "no timestamp in them, so a night without changes changes nothing")
    meta = json.loads((repo / "data" / "meta.json").read_text())
    ok(meta.get("world_site_refs") == 3, f"meta.json counts the links ({meta.get('world_site_refs')})")
    stamp = (sd / "onff.json").stat().st_mtime_ns

    directory(repo / "bron" / "dir.csv", "-")          # PAFF lost its only link
    r = bouw(repo)
    ok(r.returncode == 0, "second build succeeds")
    ok(not (sd / "paff.json").exists(), "a programme that lost its last link loses its file")
    ok((sd / "onff.json").stat().st_mtime_ns == stamp, "an unchanged file is not even rewritten")

    directory(repo / "bron" / "dir.csv", "-", with_column=False)   # column gone from the export
    r = bouw(repo)
    ok(r.returncode == 0, "a build over a directory without a website column still succeeds")
    ok((sd / "onff.json").is_file() and (sd / "vkff.json").is_file(),
       "and leaves the link files that are there alone")
    ok("no website links at all" in (repo / "report.md").read_text(encoding="utf-8"),
       "while the report says why")

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS: " + " | ".join(fails)))
sys.exit(1 if fails else 0)
