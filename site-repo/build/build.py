#!/usr/bin/env python3
"""Build the Mount Saint Mary's Cemetery website.

Reads the records (from the board's Google Sheet, or from the copies in data/),
validates them, joins lots + people + geometry, applies the privacy rule, and
writes the site into docs/.

Usage:
    python3 build/build.py            public build into docs/
    python3 build/build.py --private  board build into docs-private/ (not deployed)

Dependencies: requests (only needed when config.json says source = sheet).
Everything else is the Python 3.11 standard library.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
TEMPLATES = os.path.join(HERE, "templates")

STATUSES = {"open", "sold", "occupied", "reserved", "unusable", "unknown"}
PUBLIC_STATUS = {
    "open": "open",
    "unknown": "open",
    "sold": "taken",
    "occupied": "taken",
    "reserved": "taken",
    "unusable": "unusable",
}
BOARD_ONLY = ("purchaser", "year_sold", "price", "paid", "notes",
              "updated_by", "updated_on")
PAGES = ("index.html", "plat.html", "stakeout.html", "about.html")

warnings: list[str] = []


def warn(msg: str) -> None:
    warnings.append(msg)
    print("WARNING: " + msg, file=sys.stderr)


def die(msg: str) -> None:
    print("BUILD FAILED: " + msg, file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------- input


def read_csv_text(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def read_local(name: str) -> list[dict]:
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_tables(config: dict) -> tuple[dict, str]:
    """Return ({table: rows}, source_label)."""
    local = {
        "Lots": "lots.csv",
        "People": "people.csv",
        "Sections": "sections.csv",
        "Monuments": "monuments.csv",
    }
    if config.get("source") != "sheet":
        return {k: read_local(v) for k, v in local.items()}, "local data/ folder"

    urls = config.get("sheet_csv_urls") or {}
    missing = [k for k in local if not (urls.get(k) or "").strip()]
    if missing:
        warn("config.json source is 'sheet' but no published CSV URL is set for: "
             + ", ".join(missing) + ". Falling back to the copies in data/.")
        return {k: read_local(v) for k, v in local.items()}, "local data/ (sheet URLs missing)"

    try:
        import requests  # noqa: PLC0415
    except ImportError:
        warn("source is 'sheet' but the requests package is not installed "
             "(pip install requests). Falling back to the copies in data/.")
        return {k: read_local(v) for k, v in local.items()}, "local data/ (requests missing)"

    tables, failed = {}, []
    for name, filename in local.items():
        try:
            resp = requests.get(urls[name], timeout=30)
            resp.raise_for_status()
            rows = read_csv_text(resp.text)
            if not rows:
                raise ValueError("no rows in the downloaded CSV")
            tables[name] = rows
        except Exception as exc:  # network, HTTP, parse: all fall back
            failed.append(name)
            warn(f"download of the {name} sheet failed ({exc}). "
                 f"Using data/{filename} instead.")
            tables[name] = read_local(filename)
    label = "Google Sheet" if not failed else \
        "Google Sheet with data/ fallback for " + ", ".join(failed)
    return tables, label


def load_geojson(name: str) -> dict:
    with open(os.path.join(DATA, name), encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------- validate


def ring_area(ring: list) -> float:
    a = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        a += x1 * y2 - x2 * y1
    return a / 2.0


def validate(lots, people, sections, lot_geo, sec_geo) -> list[str]:
    """The checks in data/validate.py, run against the rows in memory."""
    errors, checks = [], []

    ids = [l["lot_id"] for l in lots]
    if len(set(ids)) != len(ids):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        errors.append(f"duplicate lot_id in Lots: {dupes[:10]}")
    else:
        checks.append(f"Lots: {len(ids)} unique lot_id")
    lot_ids = set(ids)

    missing = sorted({p["lot_id"] for p in people} - lot_ids)
    if missing:
        errors.append(f"People rows reference unknown lot_id: {missing[:10]}")
    else:
        checks.append(f"People: {len(people)} rows, all lot_id resolve")

    bad = sorted({l["status"] for l in lots} - STATUSES)
    if bad:
        errors.append(f"status values outside the allowed set: {bad}")
    else:
        checks.append("Lots: all status values in the allowed set")

    counts: dict[str, int] = {}
    for p in people:
        counts[p["lot_id"]] = counts.get(p["lot_id"], 0) + 1
    bad_cnt = [l["lot_id"] for l in lots
               if str(l.get("burial_count", "")).strip()
               and int(l["burial_count"]) != counts.get(l["lot_id"], 0)]
    if bad_cnt:
        errors.append(f"burial_count does not match People rows for: {bad_cnt[:10]}")
    else:
        checks.append("Lots: burial_count matches People")
    bad_occ = [l["lot_id"] for l in lots
               if (counts.get(l["lot_id"], 0) > 0) != (l["status"] == "occupied")]
    if bad_occ:
        errors.append(f"status 'occupied' does not match People rows for: {bad_occ[:10]}")
    else:
        checks.append("Lots: occupied status matches People rows")

    leak = {"purchaser", "price", "paid", "year_sold"} & set(people[0].keys())
    if leak:
        errors.append(f"People contains board-only ledger fields: {sorted(leak)}")
    else:
        checks.append("People: no purchaser/price/paid/year_sold columns")

    sec_ids = {s["section"] for s in sections}
    orphan = sorted({l["section"] for l in lots} - sec_ids)
    if orphan:
        errors.append(f"Lots uses sections missing from Sections: {orphan}")
    else:
        checks.append(f"Sections: {len(sections)} sections covering every lot")

    for name, gj, key, table_ids in (("lots.geojson", lot_geo, "lot_id", lot_ids),
                                     ("sections.geojson", sec_geo, "section", sec_ids)):
        if gj.get("type") != "FeatureCollection":
            errors.append(f"{name}: not a FeatureCollection")
            continue
        seen, bad_geom = [], []
        for ft in gj["features"]:
            g = ft.get("geometry") or {}
            if g.get("type") != "Polygon" or not g.get("coordinates"):
                bad_geom.append(ft["properties"].get(key))
                continue
            for i, ring in enumerate(g["coordinates"]):
                if len(ring) < 4 or ring[0] != ring[-1]:
                    bad_geom.append(ft["properties"].get(key))
                area = ring_area(ring)
                if (i == 0 and area <= 0) or (i > 0 and area >= 0):
                    bad_geom.append(ft["properties"].get(key))
            seen.append(ft["properties"].get(key))
        if bad_geom:
            errors.append(f"{name}: {len(bad_geom)} bad ring(s), e.g. {bad_geom[:5]}")
        extra = sorted(set(seen) - table_ids)
        absent = sorted(table_ids - set(seen))
        if extra:
            errors.append(f"{name}: features not in the tables: {extra[:10]}")
        if absent:
            errors.append(f"{name}: table rows with no polygon: {absent[:10]}")
        if not (bad_geom or extra or absent):
            checks.append(f"{name}: {len(seen)} polygons, one per row, rings valid")

    if errors:
        for e in errors:
            print("FAIL " + e, file=sys.stderr)
        die(f"{len(errors)} validation failure(s). Nothing was written.")
    return checks


# ---------------------------------------------------------------- geometry


def bbox(ring: list) -> tuple[float, float, float, float]:
    xs = [c[0] for c in ring]
    ys = [c[1] for c in ring]
    return min(xs), min(ys), max(xs), max(ys)


def parse_columns(spec: str, section_max: int) -> list[list[int]]:
    """'1:15;21:16' plus the section's highest lot -> [[start, width_ft, count]]."""
    cols = []
    for part in (spec or "").split(";"):
        part = part.strip()
        if not part or ":" not in part:
            continue
        start, width = part.split(":", 1)
        cols.append([int(start), float(width)])
    cols.sort(key=lambda c: c[0])
    out = []
    for i, (start, width) in enumerate(cols):
        nxt = cols[i + 1][0] if i + 1 < len(cols) else section_max + 1
        out.append([start, width, max(0, min(nxt, section_max + 1) - start)])
    return out


def neighbours(boxes: dict, tol: float = 2e-7) -> dict:
    """Edge-sharing neighbours for axis-aligned lot rectangles."""
    def key(v: float) -> int:
        return int(round(v / tol))

    by_sw: dict[tuple, str] = {}   # south-west corner -> lot
    by_se: dict[tuple, str] = {}   # south-east corner -> lot
    by_nw: dict[tuple, str] = {}   # north-west corner -> lot
    for lid, (x0, y0, x1, y1) in boxes.items():
        by_sw.setdefault((key(x0), key(y0)), lid)
        by_se.setdefault((key(x1), key(y0)), lid)
        by_nw.setdefault((key(x0), key(y1)), lid)

    out = {}
    for lid, (x0, y0, x1, y1) in boxes.items():
        nb = {}
        for label, table, k in (("east", by_sw, (key(x1), key(y0))),
                                ("west", by_se, (key(x0), key(y0))),
                                ("north", by_sw, (key(x0), key(y1))),
                                ("south", by_nw, (key(x0), key(y0)))):
            cand = table.get(k)
            if cand and cand != lid:
                nb[label] = cand
        out[lid] = nb
    return out


# ---------------------------------------------------------------- assemble


def records_date(*tables) -> str:
    """The newest date stamped on the records themselves.

    The build has to be reproducible: rebuilding unchanged records must produce
    a byte-identical docs/, so nothing may carry the clock time of the run.
    The pages therefore date the records, not the build.
    """
    stamps = []
    for rows in tables:
        for row in rows:
            for field in ("updated_on", "set_on", "burial_date"):
                v = (row.get(field) or "").strip()
                if len(v) >= 10 and v[:4].isdigit():
                    stamps.append(v[:10])
    return max(stamps) if stamps else "date not recorded"


def build_site(private: bool) -> None:
    started = time.time()
    with open(os.path.join(HERE, "config.json"), encoding="utf-8") as fh:
        config = json.load(fh)
    site_title = config.get("site_title") or "Mount Saint Mary's Cemetery"
    is_public = not private

    tables, source_label = load_tables(config)
    lots = tables["Lots"]
    people = tables["People"]
    sections = tables["Sections"]
    monuments = tables["Monuments"]
    lot_geo = load_geojson("lots.geojson")
    sec_geo = load_geojson("sections.geojson")
    with open(os.path.join(DATA, "georef.json"), encoding="utf-8") as fh:
        georef = json.load(fh)

    checks = validate(lots, people, sections, lot_geo, sec_geo)

    # people by lot
    by_lot: dict[str, list[dict]] = {}
    for p in people:
        by_lot.setdefault(p["lot_id"], []).append(p)

    # geometry by lot
    rings: dict[str, list] = {}
    for ft in lot_geo["features"]:
        rings[ft["properties"]["lot_id"]] = ft["geometry"]["coordinates"][0]
    boxes = {lid: bbox(r) for lid, r in rings.items()}
    nb = neighbours(boxes)

    ft_lat = float(georef["scale"]["ft_per_degree_latitude"])
    ft_lon = float(georef["scale"]["ft_per_degree_longitude"])

    section_max: dict[str, int] = {}
    for l in lots:
        n = int(l["lot"])
        section_max[l["section"]] = max(section_max.get(l["section"], 0), n)

    out_lots = {}
    status_counts: dict[str, int] = {}
    named = 0
    for l in lots:
        lid = l["lot_id"]
        x0, y0, x1, y1 = boxes[lid]
        st = PUBLIC_STATUS.get(l["status"], "open") if is_public else l["status"]
        status_counts[st] = status_counts.get(st, 0) + 1
        persons = []
        for p in sorted(by_lot.get(lid, []), key=lambda r: (r["last"], r["first"])):
            rec = {
                "name": (p["first"] + " " + p["last"]).strip(),
                "b": p["birth_year"] or "",
                "d": p["death_year"] or "",
            }
            if p.get("findagrave_url"):
                rec["fg"] = p["findagrave_url"]
            if p.get("source"):
                rec["src"] = p["source"]
            if p.get("confidence") and p["confidence"] != "high":
                rec["conf"] = p["confidence"]
            if not is_public and p.get("note"):
                rec["note"] = p["note"]
            persons.append(rec)
        if persons:
            named += 1
        rec = {
            "s": l["section"],
            "n": int(l["lot"]),
            "st": st,
            "g": [[round(x0, 7), round(y0, 7)], [round(x1, 7), round(y1, 7)]],
            "dim": [round((x1 - x0) * ft_lon, 1), round((y1 - y0) * ft_lat, 1)],
            "nb": nb.get(lid, {}),
        }
        if persons:
            rec["p"] = persons
        if not is_public:
            for f in BOARD_ONLY:
                if l.get(f):
                    rec[f] = l[f]
        out_lots[lid] = rec

    sec_ring = {ft["properties"]["section"]: ft["geometry"]["coordinates"][0]
                for ft in sec_geo["features"]}
    newer_cols = [s["section"] for s in sections
                  if s["section"] not in "ABCDEFGH"]
    newer_cols.sort()

    out_sections = {}
    for s in sections:
        key = s["section"]
        x0, y0, x1, y1 = bbox(sec_ring[key])
        out_sections[key] = {
            "name": s["name"],
            "dir": "WE" if s["numbering_direction"].startswith("west") else "EW",
            "cols": parse_columns(s["columns"], section_max.get(key, 0)),
            "max": section_max.get(key, 0),
            "width_ft": float(s["width_ft"]),
            "depth_ft": float(s["depth_ft"]),
            "g": [[round(x0, 7), round(y0, 7)], [round(x1, 7), round(y1, 7)]],
            "newer": key in newer_cols,
        }

    all_x = [b[0] for b in boxes.values()] + [b[2] for b in boxes.values()]
    all_y = [b[1] for b in boxes.values()] + [b[3] for b in boxes.values()]
    generated = records_date(lots, people, monuments)

    payload = {
        "meta": {
            "title": site_title,
            "generated": generated,
            "public": is_public,
            "source": source_label,
            "accuracy": georef["accuracy"],
            "anchor": georef["anchor"],
            "scale": {"ft_per_deg_lat": ft_lat, "ft_per_deg_lon": ft_lon},
            "state_plane": georef.get("state_plane"),
            "bounds": [[round(min(all_y), 7), round(min(all_x), 7)],
                       [round(max(all_y), 7), round(max(all_x), 7)]],
            "counts": {"lots": len(lots), "people": len(people),
                       "named_lots": named, "status": status_counts},
            "newer_cols": newer_cols,
            "newer_rows": section_max.get(newer_cols[0], 80) if newer_cols else 0,
        },
        "sections": out_sections,
        "lots": out_lots,
    }

    real_mons = [m for m in monuments
                 if not m["monument_id"].upper().startswith("MON-EXAMPLE")
                 and "EXAMPLE" not in (m.get("set_by") or "").upper()]
    mon_payload = {
        "generated": generated,
        "example_only": not real_mons,
        "note": ("The Monuments table holds only EXAMPLE rows, so no monuments have "
                 "been set yet." if not real_mons else
                 "Distances are computed from these monuments to each lot corner."),
        "monuments": [{
            "id": m["monument_id"],
            "description": m["description"],
            "lat": float(m["latitude"]) if m.get("latitude") else None,
            "lon": float(m["longitude"]) if m.get("longitude") else None,
            "northing_ft": float(m["northing_ft"]) if m.get("northing_ft") else None,
            "easting_ft": float(m["easting_ft"]) if m.get("easting_ft") else None,
        } for m in real_mons],
    }

    outdir = os.path.join(ROOT, "docs-private" if private else "docs")
    os.makedirs(os.path.join(outdir, "data"), exist_ok=True)
    data_name = "private.json" if private else "public.json"
    data_path = os.path.join(outdir, "data", data_name)
    with open(data_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, separators=(",", ":"))
    with open(os.path.join(outdir, "data", "monuments.json"), "w", encoding="utf-8") as fh:
        json.dump(mon_payload, fh, indent=1)

    subs = {
        "{{SITE_TITLE}}": site_title,
        "{{GENERATED}}": generated,
        "{{DATA_FILE}}": "data/" + data_name,
        "{{BUILD_KIND}}": "Board build, not for publication" if private else "Public build",
    }
    for page in PAGES:
        with open(os.path.join(TEMPLATES, page), encoding="utf-8") as fh:
            html = fh.read()
        for k, v in subs.items():
            html = html.replace(k, v)
        with open(os.path.join(outdir, page), "w", encoding="utf-8") as fh:
            fh.write(html)

    # vendored copies, so the site still works when the CDN is unreachable
    vendor_src = os.path.join(HERE, "vendor")
    if os.path.isdir(vendor_src):
        vendor_dst = os.path.join(outdir, "vendor")
        if os.path.isdir(vendor_dst):
            shutil.rmtree(vendor_dst)
        shutil.copytree(vendor_src, vendor_dst)

    if private:
        marker = os.path.join(outdir, "READ_ME_FIRST.txt")
        with open(marker, "w", encoding="utf-8") as fh:
            fh.write("Board build. Contains purchaser, price, paid, board notes and "
                     "the change log.\nDo not publish this folder. It is git-ignored "
                     "and is never deployed.\n")

    # ------------------------------------------------------------ summary
    elapsed = time.time() - started
    kb = os.path.getsize(data_path) / 1024
    print()
    for c in checks:
        print("  check  " + c)
    print()
    print(f"{'PRIVATE' if private else 'PUBLIC'} build of {site_title}")
    print(f"  source        {source_label}")
    print(f"  lots {len(lots)} | people {len(people)} | sections {len(sections)} | "
          f"named lots {named}")
    print("  status        " + ", ".join(f"{k} {v}" for k, v in sorted(status_counts.items())))
    print(f"  monuments     {len(real_mons)} set"
          + ("" if real_mons else " (Monuments holds EXAMPLE rows only)"))
    print(f"  wrote         {os.path.relpath(data_path, ROOT)} ({kb:.0f} KB), "
          f"data/monuments.json, " + ", ".join(PAGES))
    print(f"  warnings      {len(warnings)}")
    print(f"  finished in   {elapsed:.1f}s")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the cemetery site.")
    ap.add_argument("--private", action="store_true",
                    help="write the full board build into docs-private/ instead")
    args = ap.parse_args()
    build_site(args.private)


if __name__ == "__main__":
    main()
