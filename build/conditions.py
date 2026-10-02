#!/usr/bin/env python3
"""Space weather for Diana's "Condities" tab, from NOAA SWPC only.

Run by .github/workflows/conditions.yml every hour. Writes one small file,
conditions.json, which that workflow puts on its own branch ("conditions"),
so the app itself is not republished every hour. The app reads it from there.

Source: the NOAA Space Weather Prediction Center (services.swpc.noaa.gov), a
service of the US government; its data is public. Nothing else is asked.

    noaa-planetary-k-index.json   the official planetary Kp per 3 hours: the
                                  number shown, as radio amateurs quote it
    planetary_k_index_1m.json     NOAA's running estimate per minute, shown
                                  small as "now (estimate)"
    daily-geomagnetic-indices.txt planetary A of the last full day, and the
                                  3-hourly Kp again, as a fallback
    daily-solar-indices.txt       10.7 cm solar flux (SFI) and sunspot number

Each value is read on its own. A source that is down or changed its format
leaves the value it would have given as it was in the previous file (passed in
with --previous), with its own time, so the app can say how old it is. Only
when there is nothing at all, now or before, does this exit with an error.

    python3 build/conditions.py --out conditions.json [--previous old.json]
    python3 build/conditions.py --out x.json --fixtures build/tests/conditions  (tests)
"""
import argparse, datetime as dt, json, os, re, sys, urllib.request

BASE = "https://services.swpc.noaa.gov/"
SOURCES = {
    "kp3h": BASE + "products/noaa-planetary-k-index.json",
    "kp1m": BASE + "json/planetary_k_index_1m.json",
    "dgd":  BASE + "text/daily-geomagnetic-indices.txt",
    "dsd":  BASE + "text/daily-solar-indices.txt",
}


def utc_iso(t):
    return t.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(name, fixtures=None):
    if fixtures:
        with open(os.path.join(fixtures, os.path.basename(SOURCES[name])), encoding="utf-8") as f:
            return f.read()
    req = urllib.request.Request(SOURCES[name], headers={"User-Agent": "Diana (diana-onff.github.io)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def num(s):
    try:
        v = float(s)
    except (TypeError, ValueError):
        return None
    return v if v >= 0 else None          # NOAA writes -1 for "not available"


NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def data_lines(text):
    """The rows of an SWPC text product as lists of numbers (strings), header
    lines (':' and '#') left out. Read as numbers rather than split on spaces:
    the columns are fixed width, and a missing value (-1) can run into its
    neighbour ("2 1-1-1"), which a split on spaces would read as one field."""
    for line in text.splitlines():
        s = line.strip()
        if not s or s[0] in ":#":
            continue
        parts = NUMBER.findall(s)
        if len(parts) >= 4 and all(p.isdigit() for p in parts[:3]):
            yield parts


def day_of(parts):
    return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"


KP1M_MAX_AGE = dt.timedelta(hours=6)     # older than this, the minute file is stuck
KP3H_MAX_AGE = dt.timedelta(hours=12)    # and the 3-hourly one


def when_of(tag):
    """An SWPC time tag ('2026-10-02 12:00:00.000' or '2026-10-02T12:00:00') as UTC."""
    t = str(tag).strip().replace(" ", "T").rstrip("Z")
    return dt.datetime.fromisoformat(t[:19]).replace(tzinfo=dt.timezone.utc)


def parse_kp3h(text, now=None):
    """The newest official 3-hourly planetary Kp: {'value', 'time'}, where time
    is the END of its three hours. The file has been a list of lists with a
    header row ([["time_tag","Kp",...], ["2026-10-02 12:00:00.000","1.33",...]])
    and SWPC has been moving products to lists of objects; both are read."""
    rows = json.loads(text)
    recs = []
    if rows and isinstance(rows[0], list):
        head = [str(h).lower() for h in rows[0]]
        it, ik = head.index("time_tag"), head.index("kp")
        recs = [(r[it], r[ik]) for r in rows[1:] if isinstance(r, list) and len(r) > max(it, ik)]
    else:
        for r in rows:
            if isinstance(r, dict):
                k = r.get("Kp", r.get("kp", r.get("kp_index")))
                recs.append((r.get("time_tag"), k))
    best = None
    for tag, k in recs:
        v = num(k)
        if tag and v is not None and v <= 9:
            w = when_of(tag)
            if best is None or w > best[0]:
                best = (w, v)
    if not best:
        return None
    end = best[0] + dt.timedelta(hours=3)
    if now and now - end > KP3H_MAX_AGE:
        raise ValueError(f"newest 3-hourly value ends {utc_iso(end)}")
    return {"value": round(best[1], 2), "time": utc_iso(end)}


def parse_kp1m(text, now=None):
    """Newest minute value: {'value': Kp, 'time': ISO}. Prefers the decimal estimate."""
    best = None
    for rec in json.loads(text):
        if not isinstance(rec, dict):
            continue
        t = rec.get("time_tag")
        v = num(rec.get("estimated_kp"))
        if v is None:
            v = num(rec.get("kp_index"))
        if t and v is not None and v <= 9 and (best is None or t > best[0]):
            best = (t, v)
    if not best:
        return None
    t = best[0] if best[0].endswith("Z") else best[0] + "Z"
    when = dt.datetime.fromisoformat(t.replace("Z", "+00:00"))
    if now and now - when > KP1M_MAX_AGE:
        raise ValueError(f"newest minute value is from {t}")
    return {"value": round(best[1], 2), "time": t}


def parse_dgd(text):
    """Planetary A of the newest complete day, and the newest 3-hourly planetary Kp.

    A row: date (3), Fredericksburg A + 8 K, College A + 8 K, planetary A + 8 Kp."""
    a = kp = None
    for p in data_lines(text):
        if len(p) < 30:
            continue
        pa = num(p[21])
        kps = [num(x) for x in p[22:30]]
        if pa is not None and all(k is not None for k in kps):
            a = {"value": int(round(pa)), "date": day_of(p)}
        for i, k in enumerate(kps):
            if k is not None and k <= 9:
                end = when_of(day_of(p) + "T00:00:00") + dt.timedelta(hours=3 * (i + 1))
                kp = {"value": round(k, 2), "time": utc_iso(end)}       # the end of its three hours
    return a, kp


def parse_dsd(text):
    """10.7 cm flux and sunspot number of the newest day that has them."""
    sfi = ssn = None
    for p in data_lines(text):
        f, s = num(p[3]), (num(p[4]) if len(p) > 4 else None)
        if f is not None and f > 0:
            sfi = {"value": int(round(f)), "date": day_of(p)}
        if s is not None:
            ssn = {"value": int(round(s)), "date": day_of(p)}
    return sfi, ssn


def build(fixtures=None, previous=None, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    prev = previous if isinstance(previous, dict) else {}
    out = {"source": "NOAA SWPC", "updated": utc_iso(now)}
    got = {}
    problems = []

    def attempt(name, fn):
        try:
            return fn(fetch(name, fixtures))
        except Exception as e:                       # one source failing stops nothing
            problems.append(f"{name}: {e}")
            return None

    kp3h = attempt("kp3h", lambda text: parse_kp3h(text, now))
    kp_now = attempt("kp1m", lambda text: parse_kp1m(text, now))
    dgd = attempt("dgd", parse_dgd) or (None, None)
    dsd = attempt("dsd", parse_dsd) or (None, None)
    # The official 3-hourly Kp first; the same from the daily file; the minute
    # estimate only when neither is there.
    got["kp"] = kp3h or dgd[1] or kp_now
    got["kp_now"] = kp_now
    got["a"], got["sfi"], got["ssn"] = dgd[0], dsd[0], dsd[1]
    for k in ("kp", "kp_now", "a", "sfi", "ssn"):
        v = got[k] or prev.get(k)
        if v:
            out[k] = v
        if not got[k]:
            problems.append(f"{k}: kept from the previous file" if prev.get(k) else f"{k}: missing")
    if not any(k in out for k in ("kp", "a", "sfi", "ssn")):
        raise SystemExit("no space weather at all: " + "; ".join(problems))
    return out, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--previous")
    ap.add_argument("--fixtures")
    args = ap.parse_args()
    prev = None
    if args.previous and os.path.exists(args.previous):
        try:
            with open(args.previous, encoding="utf-8") as f:
                prev = json.load(f)
        except ValueError:
            prev = None
    out, problems = build(args.fixtures, prev)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
        f.write("\n")
    print(json.dumps(out))
    for p in problems:
        print("note:", p, file=sys.stderr)


if __name__ == "__main__":
    main()
