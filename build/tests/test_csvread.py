# Reading the WWFF directory CSV: a doubled quote late in the file.
#
#     python3 build/tests/test_csvread.py
#
# No browser, no network. _read_rows() in kmz2geojson.py lets csv.Sniffer
# guess the file's layout from its first 4 KB. When no doubled quote ("")
# happens to occur in those 4 KB, the sniffer concludes the file does not use
# them, and every later row whose text contains one is split in the wrong
# places: all columns after it shift by one. In the real directory that hit
# ONFF-0103 Scheps, whose notes read 'Part "Bovenloop van de Grote Nete met
# Zammelsbroek, Langdonken en Goor" Natura 2000': Diana showed 209 QSOs and a
# last activation of "1059" (the real figures: 1059 QSOs, 2023-03-11), and the
# row's website ended up in the "country" column. Also CTFF-0564 and LYFF-0315,
# plus 38 names and 44 notes worldwide that kept a stray '""' at the end.
#
# The row below is ONFF-0103 exactly as the real export has it.
import sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kmz2geojson as kg  # noqa: E402  path insert above must run first

fails = []


def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)


HEADER = ("reference,status,name,program,dxcc,state,county,continent,iota,iaruLocator,latitude,longitude,"
          "IUCNcat,validFrom,validTo,notes,lastMod,changeLog,reviewFlag,specialFlags,website,country,"
          "region,dxccEnum,qsoCount,lastAct")
FILLER = ("ONFF-{n:04d},active,Gebied {n},ONFF,ON,ON,ON,EU,-,JO20AA,50.5,4.5,IV,0000-00-00,0000-00-00,"
          "-,2020-01-01,-,-,0,,Belgium,Belgium,209,12,2024-01-01")
SCHEPS = ('ONFF-0103,active,Scheps,ONFF,ON,ON,ON,EU,-,JO21OD,51.15245,5.17478,Natura2000,0000-00-00,'
          '0000-00-00,"Part ""Bovenloop van de Grote Nete met Zammelsbroek, Langdonken en Goor"" Natura 2000",'
          '"2023-08-23 by M0YMA - Updated","2023-08-23 by M0YMA - Updated: Locator<br>2017-03-09 by ON4BB - '
          'Updated: Website, IUCN category, Locator, Region, Notes<br>2016-09-03 by M0YMA - Updated: Lat/Lon",'
          '0,,https://www.natuurenbos.be/scheps,Belgium,Belgium,209,1059,2023-03-11')
QUOTED_NAME = ('DLFF-1365,active,"LSG ""Regnitzgrund""",DLFF,DL,DL,DL,EU,-,JN59AA,49.5,11.0,V,0000-00-00,'
               '0000-00-00,-,2020-01-01,-,-,0,,https://example.de/r,Germany,Germany,230,466,2026-03-13')

with tempfile.TemporaryDirectory() as tmp:
    print("\n[1] a doubled quote only after the first 4 KB")
    lines = [HEADER] + [FILLER.format(n=n) for n in range(1, 80)] + [SCHEPS, QUOTED_NAME]
    p = Path(tmp) / "dir.csv"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ok("\"\"" not in p.read_text(encoding="utf-8")[:4096], "(the first 4 KB really have no doubled quote)")
    rows = {r["reference"]: r for r in kg._read_rows(str(p))}
    s = rows.get("ONFF-0103", {})
    ok(s.get("qsoCount") == "1059", f"ONFF-0103 keeps its QSO count ({s.get('qsoCount')!r})")
    ok(s.get("lastAct") == "2023-03-11", f"and its last activation ({s.get('lastAct')!r})")
    ok(s.get("website") == "https://www.natuurenbos.be/scheps", f"and its website ({s.get('website')!r})")
    ok(s.get("notes", "").startswith('Part "Bovenloop') and s.get("notes", "").endswith('Goor" Natura 2000'),
       f"the notes read as written ({s.get('notes', '')[:40]!r}...)")
    ok(not any(k.startswith("col") for k in s), "and no extra column appeared")
    ok(rows.get("DLFF-1365", {}).get("name") == 'LSG "Regnitzgrund"',
       f"a quoted name keeps no stray quotes ({rows.get('DLFF-1365', {}).get('name')!r})")
    ok(rows.get("ONFF-0005", {}).get("qsoCount") == "12", "an ordinary row is read as before")

    print("\n[2] the same row at the top, inside the first 4 KB")
    lines = [HEADER, SCHEPS] + [FILLER.format(n=n) for n in range(1, 80)]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    s = {r["reference"]: r for r in kg._read_rows(str(p))}.get("ONFF-0103", {})
    ok(s.get("qsoCount") == "1059" and s.get("lastAct") == "2023-03-11", "still read correctly")

    print("\n[3] a semicolon file without any quotes is still recognised")
    p.write_text("reference;status;name;latitude;longitude\n"
                 + "\n".join(f"ONFF-{n:04d};active;Gebied {n};50.5;4.5" for n in range(1, 20)) + "\n",
                 encoding="utf-8")
    r = {x["reference"]: x for x in kg._read_rows(str(p))}.get("ONFF-0007", {})
    ok(r.get("name") == "Gebied 7" and r.get("latitude") == "50.5", f"columns as expected ({r})")

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS: " + " | ".join(fails)))
sys.exit(1 if fails else 0)
