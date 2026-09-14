# The shapes a WWFF release actually comes in, and what happens to a file that
# is not one. No browser and no network:
#
#     python3 build/tests/test_kmlshapes.py
#
# Diana was built on one country's export and quietly took its layout for the
# law: <Document> at the root, a <Folder> per province one level down, the
# reference number in the name of something above the placemark. The first two
# real files from abroad both broke that assumption, each in its own way —
# Denmark opens with a <Folder> at the root (the build stopped on the spot) and
# Germany puts all 1326 areas in a single folder (which would have been written
# into every one of them as its province).
#
# So all three layouts are built here from scratch and put through the
# converter. The fourth case is the one that gets a person into trouble rather
# than the code: the wrong country picked when uploading. That must not produce
# an empty country — it must produce a sentence saying which country the file
# is actually for.
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


def vlak(naam, lon, lat):
    return (f"<Placemark><name>{naam}</name><Polygon><outerBoundaryIs><LinearRing>"
            f"<coordinates>{ring(lon, lat)}</coordinates>"
            f"</LinearRing></outerBoundaryIs></Polygon></Placemark>")


def kmz(path, kml):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("doc.kml", ('<?xml version="1.0" encoding="UTF-8"?>'
                               '<kml xmlns="http://www.opengis.net/kml/2.2">' + kml + "</kml>"))


def belgisch(path, program, per_provincie):
    """ONFF: a folder per province, a document per area inside it, and the
    number in the name of that document."""
    mappen = ""
    for provincie, gebieden in per_provincie.items():
        docs = "".join(f"<Document><name>{program}-{num} {naam}</name>{vlak(naam, lon, lat)}</Document>"
                       for num, naam, lon, lat in gebieden)
        mappen += f"<Folder><name>{provincie}</name>{docs}</Folder>"
    kmz(path, f"<Document><name>{program} release</name>{mappen}</Document>")


def duits(path, program, gebieden):
    """DLFF: one folder holding the lot, one placemark per area, the number in
    the name of the placemark itself."""
    pms = "".join(vlak(f"{program}-{num} {naam}", lon, lat) for num, naam, lon, lat in gebieden)
    kmz(path, f"<Document><name>{program}-Gebiete.kmz</name>"
              f"<Folder><name>{program}-Gebiete</name>{pms}</Folder></Document>")


def deens(path, program, gebieden):
    """OZFF: a <Folder> at the root instead of a <Document>, a document per area
    directly inside it, and no grouping level at all."""
    docs = "".join(f"<Document><name>{program}-{num} {naam}</name>{vlak(naam, lon, lat)}</Document>"
                   for num, naam, lon, lat in gebieden)
    kmz(path, f"<Folder><name>{program}</name>{docs}</Folder>")


def build(work, out, bestand, program):
    """--no-refs on purpose: this is about reading the KML, and the WWFF
    directory would only add a download and a second reason to fail."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--kmz", str(work / bestand), "--program", program,
         "--no-refs", "--out", str(out), "--report", str(work / "report.md"),
         "--overrides", str(work / "overrides.json"), "--workdir", str(work / "werk")],
        capture_output=True, text=True)


def index(out, program):
    return json.loads((out / "zones" / f"{program.lower()}-index.json").read_text())["refs"]


with tempfile.TemporaryDirectory() as tmp:
    work = pathlib.Path(tmp)
    out = work / "data"
    out.mkdir()
    (work / "overrides.json").write_text("{}")

    print("\n[1] the Belgian shape: folders one level down are provinces")
    belgisch(work / "be.kmz", "ONFF", {
        "Antwerpen": [("0001", "Gebied Een", 4.35, 51.20), ("0002", "Gebied Twee", 4.40, 51.25)],
        "Limburg": [("0003", "Gebied Drie", 5.35, 51.00)]})
    r = build(work, out, "be.kmz", "ONFF")
    ok(r.returncode == 0, f"it converts{'' if r.returncode == 0 else ': ' + r.stderr[-300:]}")
    be = index(out, "ONFF")
    ok(len(be) == 3, f"all three areas are in ({len(be)})")
    ok({z["ref"]: z.get("prov") for z in be} ==
       {"ONFF-0001": "Antwerpen", "ONFF-0002": "Antwerpen", "ONFF-0003": "Limburg"},
       "and each one carries its province")

    print("\n[2] the German shape: everything in one folder, so no province")
    duits(work / "de.kmz", "DLFF", [("0001", "Bayerischer Wald", 13.20, 48.95),
                                    ("0002", "Berchtesgaden", 12.95, 47.55),
                                    ("0003", "Eifel", 6.40, 50.55)])
    r = build(work, out, "de.kmz", "DLFF")
    ok(r.returncode == 0, f"it converts{'' if r.returncode == 0 else ': ' + r.stderr[-300:]}")
    de = index(out, "DLFF")
    ok(len(de) == 3, f"all three areas are in ({len(de)})")
    ok(all(z.get("prov") is None for z in de),
       "and the name of that one folder is not written in as a province")
    ok([z["name"] for z in de] == ["Bayerischer Wald", "Berchtesgaden", "Eifel"],
       "the names are the areas' own, with the number stripped off")

    print("\n[3] the Danish shape: a <Folder> at the root, areas straight inside")
    deens(work / "dk.kmz", "OZFF", [("0001", "Læsø", 11.00, 57.28),
                                    ("0002", "Mols Bjerge", 10.55, 56.23)])
    r = build(work, out, "dk.kmz", "OZFF")
    ok(r.returncode == 0, f"it converts{'' if r.returncode == 0 else ': ' + r.stderr[-300:]}")
    dk = index(out, "OZFF")
    ok(len(dk) == 2, f"both areas are in ({len(dk)})")
    ok([z["name"] for z in dk] == ["Læsø", "Mols Bjerge"], "with their names intact")

    print("\n[4] three countries, three shapes, all still there afterwards")
    man = json.loads((out / "countries.json").read_text())
    ok([c["program"] for c in man["countries"]] == ["DLFF", "ONFF", "OZFF"],
       "the manifest holds all three")
    ok(len(index(out, "ONFF")) == 3, "and Belgium survived the two builds after it")

    print("\n[5] the wrong country picked: refused, and it says which one it is")
    r = build(work, out, "de.kmz", "OZFF")
    melding = r.stderr + r.stdout
    ok(r.returncode != 0, "the build stops")
    ok("DLFF" in melding, "it names the country the file is really for")
    ok("OZFF" in melding, "and the one it was sent as")
    ok(len(index(out, "OZFF")) == 2, "Denmark's own data is untouched")
    ok("could not be read as OZFF" in (work / "report.md").read_text(),
       "and the reason is in the report, not only in a log")

    print("\n[6] areas without a number: refused, with an example of what is there")
    kmz(work / "geennummer.kmz",
        f"<Document><name>zonder</name><Folder><name>Gebieden</name>"
        f"{vlak('Reserve Noord', 4.1, 50.1)}{vlak('Reserve Zuid', 4.2, 50.2)}"
        f"</Folder></Document>")
    r = build(work, out, "geennummer.kmz", "ONFF")
    melding = r.stderr + r.stdout
    ok(r.returncode != 0, "the build stops")
    ok("Reserve Noord" in melding, "it quotes a name from the file, so you can see what it is")
    ok(len(index(out, "ONFF")) == 3, "Belgium's data is untouched")

    print("\n[7] a file with no areas in it at all")
    kmz(work / "leeg.kmz", "<Document><name>leeg</name>"
                           "<Placemark><name>Een punt</name><Point>"
                           "<coordinates>4.3,50.8,0</coordinates></Point></Placemark></Document>")
    r = build(work, out, "leeg.kmz", "ONFF")
    ok(r.returncode != 0, "the build stops")
    ok("no areas at all" in (r.stderr + r.stdout), "and says the file holds no boundaries")

    print("\n[8] a file that is not a KML at all")
    kmz(work / "onzin.kmz", "<Document><name>onzin</name></Document>")
    r = build(work, out, "onzin.kmz", "ONFF")
    ok(r.returncode != 0, "the build stops rather than writing an empty country")

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS"))
sys.exit(1 if fails else 0)
