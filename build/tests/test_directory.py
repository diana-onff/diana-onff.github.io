"""What the build step does with a rickety WWFF directory.

No browser needed: this runs kmz2geojson.py itself, with a real KMZ and a real
CSV. The three things guarded here have each gone wrong in production, or could
have:

  1. coordinates that are out of range, transposed or half zero — those ended up
     as a dot in the middle of the ocean
  2. a truncated or unreachable directory that quietly wrote out a half file
     which looked perfectly healthy
  3. --strict, which the nightly run relies on to commit nothing

Running:  python3 build/tests/test_directory.py [path/to/wwff_directory.csv]
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "build" / "kmz2geojson.py"
fails = []


def ok(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


def build(out: Path, csv: str, strict: bool = False):
    kmz = sorted((ROOT / "source").glob("*.kmz"))
    if not kmz:
        print("No KMZ in source/ — test skipped.")
        sys.exit(0)
    args = [sys.executable, str(SCRIPT), "--kmz", str(kmz[-1]), "--out", str(out),
            "--report", str(out / "report.md"), "--refs-csv", csv,
            "--overrides", str(ROOT / "overrides.json")]
    if strict:
        args.append("--strict")
    return subprocess.run(args, capture_output=True, text=True, cwd=ROOT)


def find_csv() -> str | None:
    if len(sys.argv) > 1:
        return sys.argv[1]
    for base in (Path("/root/.claude/uploads"), Path("/tmp")):
        if base.exists():
            hits = sorted(base.rglob("*wwff_directory.csv"))
            if hits:
                return str(hits[-1])
    return None


CSV = find_csv()
if not CSV:
    print("No local wwff_directory.csv found — pass the path as an argument.")
    sys.exit(0)

work = Path(tempfile.mkdtemp(prefix="diana-dirtest-"))
good = work / "good"

print("\n[1] ordinary build against the real directory")
r = build(good, CSV)
ok(r.returncode == 0, f"exit code 0 (got {r.returncode})")
world = json.loads((good / "wwff-world.geojson").read_text())["features"]
ok(len(world) > 50000, f"{len(world)} world points written")

print("\n[2] not a single impossible coordinate")
out_of_range = [f["properties"]["ref"] for f in world
                if not (-90 <= f["geometry"]["coordinates"][1] <= 90
                        and -180 <= f["geometry"]["coordinates"][0] <= 180)]
ok(not out_of_range, f"everything within range (out of range: {out_of_range[:5]})")

half_zero = [f["properties"]["ref"] for f in world
             if abs(f["geometry"]["coordinates"][0]) < 0.001
             or abs(f["geometry"]["coordinates"][1]) < 0.001]
ok(not half_zero, f"no half-zero positions (found: {half_zero[:5]})")

junk = [f["properties"]["ref"] for f in world if not f["properties"]["ref"][:1].isalnum()
        or "FF-" not in f["properties"]["ref"]]
ok(not junk, f"no junk rows as a reference (found: {junk[:5]})")

print("\n[3] the two layers do not leak into each other")
onff_in_world = [f["properties"]["ref"] for f in world if f["properties"]["ref"].startswith("ONFF")]
ok(not onff_in_world, "no ONFF in the world layer")
pts = json.loads((good / "onff-points.geojson").read_text())["features"]
ok(all(f["properties"]["ref"].startswith("ONFF") for f in pts),
   "only ONFF in the boundary-less points layer")

print("\n[4] ONFF-0004 is in Antarctica and that is as it should be")
antarctic = [f["geometry"]["coordinates"] for f in pts if f["properties"]["ref"] == "ONFF-0004"]
ok(bool(antarctic) and antarctic[0][1] < -60,
   f"Princess Elisabeth base in the southern hemisphere ({antarctic})")

print("\n[5] unreachable directory: --strict stops, without writing anything")
before = (good / "wwff-world.geojson").read_bytes()
r = build(good, "https://example.invalid/weg.csv", strict=True)
ok(r.returncode == 1, f"exit code 1 (got {r.returncode})")
ok((good / "wwff-world.geojson").read_bytes() == before, "world file left untouched")

print("\n[6] a truncated directory is spotted by the drop against the previous build")
trunc = work / "trunc.csv"
raw = Path(CSV).read_bytes()
trunc.write_bytes(raw[: len(raw) // 5])
r = build(good, str(trunc), strict=True)
ok(r.returncode == 1, f"exit code 1 on a truncated CSV (got {r.returncode})")
ok((good / "wwff-world.geojson").read_bytes() == before, "world file still untouched")

print("\n[7] without --strict the points from the previous build stay put")
r = build(good, "https://example.invalid/weg.csv")
ok(r.returncode == 0, f"exit code 0 without --strict (got {r.returncode})")
idx = json.loads((good / "onff-index.json").read_text())
ok(idx["point_count"] == len(pts),
   f"{idx['point_count']} points kept instead of wiped (was {len(pts)})")
ok(len(json.loads((good / "onff-points.geojson").read_text())["features"]) == len(pts),
   "onff-points.geojson not written empty")

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS: " + " | ".join(fails)))
sys.exit(1 if fails else 0)
