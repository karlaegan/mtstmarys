#!/usr/bin/env python3
"""Validate the canonical cemetery tables and their GeoJSON.

Usage: python3 data/validate.py     (exits non-zero and prints FAIL lines on error)
"""
import csv, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
STATUSES = {"open", "sold", "occupied", "reserved", "unusable", "unknown"}
BANNED_IN_PEOPLE = {"purchaser", "price", "paid", "year_sold"}
errors, checks = [], []


def load(name):
    with open(os.path.join(HERE, name), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def ok(msg):
    checks.append(msg)


def fail(msg):
    errors.append(msg)


lots = load("lots.csv")
people = load("people.csv")
sections = load("sections.csv")

# 1. unique lot_id
ids = [l["lot_id"] for l in lots]
dupes = {i for i in ids if ids.count(i) > 1} if len(set(ids)) != len(ids) else set()
if dupes:
    fail(f"duplicate lot_id in lots.csv: {sorted(dupes)[:10]}")
else:
    ok(f"lots.csv: {len(ids)} unique lot_id")

lot_ids = set(ids)

# 2. every people.lot_id exists in lots
missing = sorted({p["lot_id"] for p in people} - lot_ids)
if missing:
    fail(f"people.csv references lot_id not in lots.csv: {missing[:10]}")
else:
    ok(f"people.csv: {len(people)} rows, all lot_id resolve")

# 3. status values
bad = sorted({l["status"] for l in lots} - STATUSES)
if bad:
    fail(f"lots.csv has status values outside the allowed set: {bad}")
else:
    ok("lots.csv: all status values in the allowed set")

# 3b. status rules and burial_count consistency
counts = {}
for p in people:
    counts[p["lot_id"]] = counts.get(p["lot_id"], 0) + 1
bad_cnt = [l["lot_id"] for l in lots if int(l["burial_count"]) != counts.get(l["lot_id"], 0)]
bad_occ = [l["lot_id"] for l in lots
           if (counts.get(l["lot_id"], 0) > 0) != (l["status"] == "occupied")]
if bad_cnt:
    fail(f"burial_count does not match people rows for: {bad_cnt[:10]}")
else:
    ok("lots.csv: burial_count matches people.csv")
if bad_occ:
    fail(f"status 'occupied' does not match presence of people rows for: {bad_occ[:10]}")
else:
    ok("lots.csv: occupied status matches people rows")

# 4. no purchaser / price fields in people.csv
leak = BANNED_IN_PEOPLE & set(people[0].keys())
if leak:
    fail(f"people.csv contains board-only ledger fields: {sorted(leak)}")
else:
    ok("people.csv: no purchaser/price/paid/year_sold columns")

# 5. sections cover every lot's section
sec_ids = {s["section"] for s in sections}
orphan = sorted({l["section"] for l in lots} - sec_ids)
if orphan:
    fail(f"lots.csv uses sections missing from sections.csv: {orphan}")
else:
    ok(f"sections.csv: {len(sections)} sections, covering every lot")


def ring_area(ring):
    """Signed area (shoelace); positive = counterclockwise = correct exterior."""
    a = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        a += x1 * y2 - x2 * y1
    return a / 2.0


def check_geojson(name, key):
    path = os.path.join(HERE, name)
    try:
        gj = json.load(open(path, encoding="utf-8"))
    except Exception as exc:
        fail(f"{name}: not valid JSON ({exc})")
        return None
    if gj.get("type") != "FeatureCollection":
        fail(f"{name}: not a FeatureCollection")
        return None
    seen, bad_ring, bad_wind, bad_geom = [], [], [], []
    for ft in gj["features"]:
        g = ft.get("geometry") or {}
        if g.get("type") != "Polygon" or not g.get("coordinates"):
            bad_geom.append(ft["properties"].get(key))
            continue
        for i, ring in enumerate(g["coordinates"]):
            if len(ring) < 4 or ring[0] != ring[-1]:
                bad_ring.append(ft["properties"].get(key))
            area = ring_area(ring)
            # exterior ring CCW (positive), interior rings CW (negative)
            if (i == 0 and area <= 0) or (i > 0 and area >= 0):
                bad_wind.append(ft["properties"].get(key))
        seen.append(ft["properties"].get(key))
    for label, lst in (("non-polygon geometry", bad_geom), ("unclosed ring", bad_ring),
                       ("ring violating the right-hand rule", bad_wind)):
        if lst:
            fail(f"{name}: {len(lst)} feature(s) with {label}, e.g. {lst[:5]}")
    if not (bad_geom or bad_ring or bad_wind):
        ok(f"{name}: {len(seen)} polygon features, valid JSON, closed rings, "
           "right-hand rule")
    return seen


lot_feat = check_geojson("lots.geojson", "lot_id")
if lot_feat is not None:
    extra = sorted(set(lot_feat) - lot_ids)
    absent = sorted(lot_ids - set(lot_feat))
    if extra:
        fail(f"lots.geojson has lot_id not in lots.csv: {extra[:10]}")
    if absent:
        fail(f"lots.csv rows with no polygon in lots.geojson: {absent[:10]}")
    if not extra and not absent:
        ok("lots.geojson: one polygon per lot, matching lots.csv exactly")
    if len(lot_feat) != len(set(lot_feat)):
        fail("lots.geojson: duplicate lot_id features")

sec_feat = check_geojson("sections.geojson", "section")
if sec_feat is not None:
    if sorted(set(sec_feat)) != sorted(sec_ids):
        fail("sections.geojson does not match sections.csv one-for-one")
    else:
        ok("sections.geojson: one polygon per section, matching sections.csv")

# 6. supporting files exist
for f in ("georef.json", "README.md", "import_report.md", "monuments.csv",
          "changes.csv"):
    if not os.path.exists(os.path.join(HERE, f)):
        fail(f"missing file: {f}")
try:
    json.load(open(os.path.join(HERE, "georef.json"), encoding="utf-8"))
    ok("georef.json: valid JSON")
except Exception as exc:
    fail(f"georef.json: {exc}")

for c in checks:
    print("PASS", c)
for e in errors:
    print("FAIL", e)
print(("\nAll %d checks passed." % len(checks)) if not errors
      else "\n%d FAILURE(S)." % len(errors))
sys.exit(1 if errors else 0)
