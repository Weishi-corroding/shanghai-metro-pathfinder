"""
fetch_station_coords.py — Fetch real lat/lng for Shanghai Metro stations from OSM.

Queries the Overpass API once for all subway stations in Shanghai, then matches
them by station name (with a line-name fallback) against python/data/Station.csv.

Outputs:
  scripts/station_coords.json     — { "0101": {lat, lng, name, line}, ... }
  scripts/missing_coords.json     — stations we could not auto-match (for review)

The override file scripts/station_coords_override.json (if present) is merged in
last, so any hand-fixed entries win over the OSM result.

Usage:
    python scripts/fetch_station_coords.py            # uses cache if it exists
    python scripts/fetch_station_coords.py --refresh  # re-query Overpass
"""

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
STATION_CSV = ROOT / "python" / "data" / "Station.csv"
OUT_COORDS = ROOT / "scripts" / "station_coords.json"
OUT_MISSING = ROOT / "scripts" / "missing_coords.json"
OVERRIDE = ROOT / "scripts" / "station_coords_override.json"

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
]

# Bounding box for Shanghai metropolitan area (covers all metro lines incl. 11 Huaqiao, airports, etc.)
SHANGHAI_BBOX = "30.65,120.85,31.95,122.05"  # south,west,north,east

QUERY = f"""
[out:json][timeout:90];
(
  node["railway"="station"]["station"="subway"]({SHANGHAI_BBOX});
  node["railway"="station"]["subway"="yes"]({SHANGHAI_BBOX});
  node["railway"="stop"]["subway"="yes"]({SHANGHAI_BBOX});
  node["public_transport"="station"]["subway"="yes"]({SHANGHAI_BBOX});
);
out body;
"""

# Canonicalize a station name for fuzzy matching: trim spaces, normalize a few common variants.
def canon_name(name: str) -> str:
    if not name:
        return ""
    s = name.strip()
    # Strip parenthetical suffix: "迪士尼(乐园)" -> "迪士尼"; tolerate both half/full width parens
    s = re.sub(r"[（(].*?[）)]", "", s).strip()
    # Strip trailing "站"
    if s.endswith("站"):
        s = s[:-1]
    # Normalize middle dots: OSM uses U+30FB (・) while our CSV uses U+00B7 (·). Strip both.
    s = s.replace("・", "").replace("·", "").replace("·", "").replace("・", "")
    return s


def line_tag_match(osm_tags: dict, target_line: str) -> bool:
    """Best-effort check whether an OSM node's tags hint at the target line."""
    # target_line like "1号线", "市域机场线", "浦江线"
    hay = " ".join(
        osm_tags.get(k, "") for k in ("line", "ref", "name", "name:zh", "operator", "network", "route")
    )
    # Direct substring (e.g. "1号线" appears in "上海地铁1号线")
    if target_line in hay:
        return True
    # Match "Line 1" style on numeric lines
    m = re.match(r"^(\d+)号线$", target_line)
    if m:
        n = m.group(1)
        if re.search(rf"\bLine\s*{n}\b", hay, re.IGNORECASE):
            return True
        if re.search(rf"\b{n}号线\b", hay):
            return True
    return False


def fetch_overpass() -> list[dict]:
    """Try every endpoint with a polite User-Agent. Some endpoints reject curl-style
    or unbranded requests with 403/406; OSM asks all clients to identify themselves."""
    last_err = None
    headers = {
        "User-Agent": "shanghai-metro-pathfinder/1.0 (https://github.com/Weishi-corroding/shanghai-metro-pathfinder; educational)",
        "Accept": "application/json",
    }
    for url in OVERPASS_ENDPOINTS:
        try:
            print(f"  Querying {url} ...", flush=True)
            r = requests.post(url, data={"data": QUERY}, headers=headers, timeout=120)
            if r.status_code != 200:
                print(f"    HTTP {r.status_code}", flush=True)
                # Some servers return a useful body even on error
                snippet = r.text[:200] if r.text else ""
                if snippet:
                    print(f"    Body: {snippet}", flush=True)
                last_err = f"HTTP {r.status_code}"
                continue
            return r.json().get("elements", [])
        except Exception as e:
            print(f"    {e}", flush=True)
            last_err = str(e)
            continue
    raise RuntimeError(f"All Overpass endpoints failed: {last_err}")


def load_csv_stations() -> list[dict]:
    rows = []
    with open(STATION_CSV, "r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append({
                "id": r["站点ID"],
                "name": r["站点名称"].strip(),
                "line": r["所属线路"].strip(),
            })
    return rows


def build_osm_index(elements: list[dict]) -> dict[str, list[dict]]:
    """Map canonical name -> list of OSM nodes."""
    idx: dict[str, list[dict]] = defaultdict(list)
    for el in elements:
        if el.get("type") != "node":
            continue
        tags = el.get("tags", {}) or {}
        # Prefer Chinese name fields
        name = tags.get("name") or tags.get("name:zh") or ""
        if not name:
            continue
        key = canon_name(name)
        if not key:
            continue
        idx[key].append({
            "lat": el["lat"],
            "lng": el["lon"],
            "tags": tags,
            "name": name,
        })
    return idx


def match_one(row: dict, idx: dict[str, list[dict]]) -> dict | None:
    key = canon_name(row["name"])
    candidates = idx.get(key, [])
    if not candidates:
        return None
    if len(candidates) == 1:
        c = candidates[0]
        return {"lat": c["lat"], "lng": c["lng"]}
    # Multiple candidates: prefer one matching the line tag
    for c in candidates:
        if line_tag_match(c["tags"], row["line"]):
            return {"lat": c["lat"], "lng": c["lng"]}
    # Otherwise fall back to centroid of all candidates (better than guessing one)
    lat = sum(c["lat"] for c in candidates) / len(candidates)
    lng = sum(c["lng"] for c in candidates) / len(candidates)
    return {"lat": lat, "lng": lng}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="Re-query Overpass even if cache exists")
    args = ap.parse_args()

    csv_rows = load_csv_stations()
    print(f"Loaded {len(csv_rows)} stations from Station.csv")

    raw_cache = ROOT / "scripts" / ".overpass_cache.json"
    if not args.refresh and raw_cache.exists():
        print(f"Using cached Overpass response: {raw_cache}")
        elements = json.loads(raw_cache.read_text(encoding="utf-8"))
    else:
        print("Fetching Shanghai subway stations from OSM Overpass ...")
        elements = fetch_overpass()
        raw_cache.write_text(json.dumps(elements, ensure_ascii=False), encoding="utf-8")
        print(f"  Got {len(elements)} OSM nodes; cached to {raw_cache.name}")

    idx = build_osm_index(elements)
    print(f"Indexed {len(idx)} unique station names from OSM")

    coords: dict[str, dict] = {}
    missing: list[dict] = []
    for row in csv_rows:
        m = match_one(row, idx)
        if m is None:
            missing.append(row)
        else:
            coords[row["id"]] = {
                "lat": round(m["lat"], 6),
                "lng": round(m["lng"], 6),
                "name": row["name"],
                "line": row["line"],
            }

    # Merge override file (manual fixes) — overrides win
    if OVERRIDE.exists():
        try:
            ov = json.loads(OVERRIDE.read_text(encoding="utf-8"))
            applied = 0
            for sid, val in ov.items():
                if not isinstance(val, dict) or "lat" not in val or "lng" not in val:
                    continue
                # Find the row to preserve name/line metadata if absent
                meta_row = next((r for r in csv_rows if r["id"] == sid), None)
                coords[sid] = {
                    "lat": float(val["lat"]),
                    "lng": float(val["lng"]),
                    "name": val.get("name") or (meta_row["name"] if meta_row else sid),
                    "line": val.get("line") or (meta_row["line"] if meta_row else ""),
                }
                # Remove from missing if it was there
                missing = [m for m in missing if m["id"] != sid]
                applied += 1
            print(f"Applied {applied} override entries from station_coords_override.json")
        except Exception as e:
            print(f"  WARNING: failed to read override file: {e}")

    OUT_COORDS.write_text(
        json.dumps(coords, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    OUT_MISSING.write_text(
        json.dumps(missing, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print(f"Matched : {len(coords)} / {len(csv_rows)}")
    print(f"Missing : {len(missing)}  -> {OUT_MISSING.name}")
    print(f"Output  : {OUT_COORDS.name}")
    if missing:
        print()
        print("Missing samples (first 10):")
        for m in missing[:10]:
            print(f"  {m['id']}  {m['name']:<12}  {m['line']}")
        print()
        print("To fix: add entries like this to scripts/station_coords_override.json:")
        print('  { "0101": {"lat": 31.1126, "lng": 121.3852}, ... }')


if __name__ == "__main__":
    sys.exit(main())
