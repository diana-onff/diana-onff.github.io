# The worldwide QSO counts behind the spots screen's QSO figure and ATNO tag.
#
#     python3 build/tests/test_worldactivity.py
#
# No browser, no network: point_refs() from kmz2geojson.py is called directly
# on a handful of hand-written directory rows. What it guards is how the real
# WWFF directory says "never activated": not with a 0, but with an EMPTY count
# and an empty last-activation date. A first version of this feature read
# only literal zeros and would never have shown a single ATNO. And the
# reverse risk: a directory with no counts at all (a renamed or dropped
# column in some future export) must not turn every reference on earth into
# an ATNO.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kmz2geojson as kg  # noqa: E402  path insert above must run first

fails = []


def ok(c, m):
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        fails.append(m)


def row(ref, status="active", q="", last=""):
    return {"program": ref.split("-")[0], "country": "X", "reference": ref, "name": ref,
            "status": status, "latitude": "50.5", "longitude": "4.5",
            "qsoCount": q, "lastAct": last}


def world_activity(rows):
    out = kg.point_refs(rows, [], False, ["ONFF"], set(), {}, 5)
    return out[7], out[3]      # (world_activity, warnings)


print("\n[1] the four cases the real directory has")
wa, warn = world_activity([
    row("ONFF-0001", q="3675", last="2026-03-05"),   # activated, counted
    row("ONFF-0962"),                                  # never activated: empty count, empty date
    row("PAFF-0002", last="2025-05-05"),               # activated, count missing
    row("PAFF-0003", status="deleted", q="12"),        # not an active reference
    row("VKFF-0010", q="10", last="2024-01-01"),       # another programme entirely
    row("DLFF-0001", q="0", last="2024-01-01"),        # a literal 0 WITH a date: activated
    row("DLFF-0002", q="0"),                           # a literal 0, no date: never activated
    row("DLFF-0003", q="nan"),                         # garbage: must not stop the build
])
ok(wa.get("ONFF-0001") == 3675, f"a counted reference keeps its count ({wa.get('ONFF-0001')})")
ok(wa.get("ONFF-0962") == 0, f"empty count and no date is 0, i.e. ATNO ({wa.get('ONFF-0962')!r})")
ok("PAFF-0002" not in wa, "a date but no count is left out, not a false ATNO")
ok("PAFF-0003" not in wa, "a deleted reference is left out")
ok(wa.get("VKFF-0010") == 10, "every programme is in it, not only the one being built")
ok("DLFF-0001" not in wa, "a literal 0 with a date is left out too, the same way the app reads it")
ok(wa.get("DLFF-0002") == 0, "a literal 0 without a date is ATNO")
ok(wa.get("DLFF-0003") == 0, "a count of 'nan' is read as no count (no crash, and no date, so 0)")
ok(all(isinstance(v, int) for v in wa.values()), "only the count per reference, nothing else")
ok(not any("QSO counts" in w for w in warn), "and no warning on an ordinary directory")

print("\n[2] a directory with no counts at all is not read as 'everything is an ATNO'")
wa2, warn2 = world_activity([row("ONFF-0001"), row("ONFF-0002"), row("PAFF-0001")])
ok(wa2 == {}, f"nothing written ({wa2})")
ok(any("no QSO counts at all" in w for w in warn2), "and the report says why")

print("\n" + ("ALL OK" if not fails else f"{len(fails)} PROBLEMS: " + " | ".join(fails)))
sys.exit(1 if fails else 0)
