"""
generate_layout.py — Generate the metro map layout for the frontend.

Reads:
  python/data/Station.csv         (530 stations: id, name, line, status)
  python/data/Edge.csv            (1300 edges incl. transfer edges)
  scripts/station_coords.json     (real lat/lng for each station — produced by fetch_station_coords.py)

Outputs:
  cpp/backend/static/layout.json
    {
      "meta":    {...},
      "stations": { "<id>": {x, y, name, line, color, is_transfer, transfer_to[]} },
      "lines":    { "<line_name>": {
                      "name", "color", "station_count",
                      "station_ids":[...],
                      "segments":[ [a_id, b_id], ... ]    # real adjacency edges from Edge.csv (excludes "换乘")
                    } }
    }

Projection:
  Equirectangular (a.k.a. plate carrée) — for Shanghai's ~50km extent, the error
  from omitting Mercator is sub-pixel. lat -> y (north is up), lng -> x.
  We multiply lng-deltas by cos(mean_lat) so the displayed aspect ratio matches reality.

Usage:
    python scripts/generate_layout.py
"""

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "python" / "data"
STATION_CSV = DATA_DIR / "Station.csv"
EDGE_CSV = DATA_DIR / "Edge.csv"
COORDS_JSON = ROOT / "scripts" / "station_coords.json"
OUTPUT = ROOT / "cpp" / "backend" / "static" / "layout.json"

CANVAS_W = 1400
CANVAS_H = 900
PAD = 60

LINE_COLORS = {
    "1号线": "#E4002B", "2号线": "#97D700", "3号线": "#FCD600",
    "4号线": "#461D84", "5号线": "#944D9B", "6号线": "#D6006C",
    "7号线": "#ED6B06", "8号线": "#0094D8", "9号线": "#7AC8E1",
    "10号线": "#C6AFD4", "11号线": "#841C21", "12号线": "#007A60",
    "13号线": "#E77CA5", "14号线": "#9D8B63", "15号线": "#B2A680",
    "16号线": "#77D0C8", "17号线": "#BB6414", "18号线": "#C4984E",
    "浦江线": "#B5B5B6", "市域机场线": "#4A90A4",
}


def load_stations() -> list[dict]:
    rows = []
    with open(STATION_CSV, "r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append({
                "id": r["站点ID"],
                "name": r["站点名称"].strip(),
                "line": r["所属线路"].strip(),
                "status": r["运营状态"].strip(),
            })
    return rows


def load_edges() -> list[dict]:
    rows = []
    with open(EDGE_CSV, "r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append({
                "from": r["起点站ID"],
                "to": r["终点站ID"],
                "line": r["线路"].strip(),
            })
    return rows


def load_coords() -> dict[str, dict]:
    return json.loads(COORDS_JSON.read_text(encoding="utf-8"))


def find_transfer_groups(stations: list[dict]) -> dict[str, list[str]]:
    name_to_ids = defaultdict(list)
    for s in stations:
        name_to_ids[s["name"]].append(s["id"])
    return {name: ids for name, ids in name_to_ids.items() if len(ids) > 1}


def project(coords: dict[str, dict]) -> dict[str, tuple[float, float]]:
    """Equirectangular projection of (lat, lng) -> (x, y) in canvas pixels.

    Returns dict id -> (x, y). The mapping preserves true aspect ratio
    and centers the network in the canvas.
    """
    lats = [c["lat"] for c in coords.values()]
    lngs = [c["lng"] for c in coords.values()]
    lat_min, lat_max = min(lats), max(lats)
    lng_min, lng_max = min(lngs), max(lngs)
    mean_lat_rad = math.radians((lat_min + lat_max) / 2.0)
    cos_lat = math.cos(mean_lat_rad)

    # Geographic span in "equivalent degrees" — multiply lng by cos(lat) so 1° lng visually equals 1° lat near Shanghai.
    width_deg = (lng_max - lng_min) * cos_lat
    height_deg = (lat_max - lat_min)
    if width_deg == 0 or height_deg == 0:
        raise RuntimeError("Degenerate coordinates")

    avail_w = CANVAS_W - 2 * PAD
    avail_h = CANVAS_H - 2 * PAD
    scale = min(avail_w / width_deg, avail_h / height_deg)

    # Center the projected box inside the canvas
    used_w = width_deg * scale
    used_h = height_deg * scale
    off_x = (CANVAS_W - used_w) / 2.0
    off_y = (CANVAS_H - used_h) / 2.0

    result = {}
    for sid, c in coords.items():
        x = off_x + (c["lng"] - lng_min) * cos_lat * scale
        y = off_y + (lat_max - c["lat"]) * scale  # invert: north => top
        result[sid] = (round(x, 1), round(y, 1))
    return result


def extract_segments(edges: list[dict], line_name: str) -> list[list[str]]:
    """Return [[id_a, id_b], ...] of unique track segments belonging to line_name.

    Excludes transfer edges (line == "换乘"). Each undirected pair appears once.
    """
    seen = set()
    out = []
    for e in edges:
        if e["line"] != line_name:
            continue
        if e["line"] == "换乘":  # double-safety
            continue
        a, b = e["from"], e["to"]
        key = tuple(sorted([a, b]))
        if key in seen:
            continue
        seen.add(key)
        out.append([a, b])
    return out


def compute_parallel_offsets(
    all_segments: dict[str, list[list[str]]],
    coords: dict[str, tuple[float, float]],
    gap: float = 4.5,
) -> dict[str, list[list]]:
    """Assign a perpendicular-screen-pixel offset to every segment.

    When N ≥ 2 lines share the same geographic corridor (same endpoint coords,
    e.g. near transfer stations), each line gets a different offset so they render
    side-by-side rather than on top of each other.  Keyed by rounded coordinates
    since transfer stations with different IDs share the same (x, y) after snapping.

    Returns {line_name: [[id_a, id_b, offset], ...]}.
    """
    from collections import defaultdict

    def _coord_key(a: str, b: str) -> tuple:
        """Return a stable key for the segment's geographic location.
        Round to 0.5 px to catch segments that are visually identical."""
        ax, ay = coords[a] if a in coords else (0.0, 0.0)
        bx, by = coords[b] if b in coords else (0.0, 0.0)
        # Sort so (A,B) and (B,A) produce the same key
        if (ax, ay) <= (bx, by):
            return (round(ax * 2) / 2, round(ay * 2) / 2, round(bx * 2) / 2, round(by * 2) / 2)
        else:
            return (round(bx * 2) / 2, round(by * 2) / 2, round(ax * 2) / 2, round(ay * 2) / 2)

    edge_index: dict[tuple, list[tuple[str, list[str]]]] = defaultdict(list)
    for ln, segs in all_segments.items():
        for seg in segs:
            key = _coord_key(seg[0], seg[1])
            edge_index[key].append((ln, seg))

    result: dict[str, list[list]] = {ln: [] for ln in all_segments}

    for key, entries in edge_index.items():
        n = len(entries)
        if n == 1:
            ln, seg = entries[0]
            result[ln].append([seg[0], seg[1], 0.0])
        else:
            for i, (ln, seg) in enumerate(entries):
                offset = round(gap * (i - (n - 1) / 2.0), 1)
                result[ln].append([seg[0], seg[1], offset])

    return result


def build_layout(stations: list[dict], edges: list[dict], coords: dict[str, dict]) -> dict:
    # Project geographic coords to canvas pixels
    xy = project(coords)

    # Snap transfer groups (same-name stations) to their geographic centroid so
    # the cluster renders as a single point — visually distinguishable by the
    # larger r=8 ring drawn by the frontend.
    transfer_groups = find_transfer_groups(stations)
    for name, ids in transfer_groups.items():
        present = [i for i in ids if i in xy]
        if len(present) < 2:
            continue
        cx = sum(xy[i][0] for i in present) / len(present)
        cy = sum(xy[i][1] for i in present) / len(present)
        for sid in present:
            xy[sid] = (round(cx, 1), round(cy, 1))

    transfer_id_set = {i for ids in transfer_groups.values() for i in ids}
    transfer_to_map = {}
    for name, ids in transfer_groups.items():
        lines = {next((s["line"] for s in stations if s["id"] == i), None) for i in ids}
        for sid in ids:
            self_line = next((s["line"] for s in stations if s["id"] == sid), None)
            transfer_to_map[sid] = sorted(l for l in lines if l and l != self_line)

    # Build per-station record
    station_records = {}
    for s in stations:
        sid = s["id"]
        if sid not in xy:
            continue  # should not happen — fetch script guarantees coverage
        rec = {
            "x": xy[sid][0],
            "y": xy[sid][1],
            "name": s["name"],
            "line": s["line"],
            "color": LINE_COLORS.get(s["line"], "#666666"),
        }
        if sid in transfer_id_set:
            rec["is_transfer"] = True
            rec["transfer_to"] = transfer_to_map.get(sid, [])
        station_records[sid] = rec

    # Group lines for output, including real adjacency segments
    line_groups: dict[str, list[dict]] = defaultdict(list)
    for s in stations:
        line_groups[s["line"]].append(s)

    # Step 1: extract raw segments per line (no offsets yet)
    raw_segments: dict[str, list[list]] = {}
    for line_name in line_groups:
        raw_segments[line_name] = extract_segments(edges, line_name)

    # Step 2: compute parallel offsets for shared corridors (keyed by coords, not IDs,
    # because transfer stations share the same (x,y) but have different IDs per line).
    offset_segments = compute_parallel_offsets(raw_segments, xy)

    line_output = {}
    for line_name, sts in line_groups.items():
        line_output[line_name] = {
            "name": line_name,
            "color": LINE_COLORS.get(line_name, "#666666"),
            "station_count": len(sts),
            "station_ids": [s["id"] for s in sts],
            "segments": offset_segments[line_name],
        }

    return {
        "meta": {
            "total_stations": len(stations),
            "total_lines": len(line_groups),
            "transfer_stations": len(transfer_groups),
            "canvas_width": CANVAS_W,
            "canvas_height": CANVAS_H,
            "description": "Shanghai Metro geographic layout (equirectangular projection)",
        },
        "stations": station_records,
        "lines": line_output,
    }


def main():
    print(f"Loading stations from {STATION_CSV.name} ...")
    stations = load_stations()
    print(f"  {len(stations)} stations")

    print(f"Loading edges from {EDGE_CSV.name} ...")
    edges = load_edges()
    print(f"  {len(edges)} edges (incl. transfers)")

    print(f"Loading coords from {COORDS_JSON.name} ...")
    coords = load_coords()
    print(f"  {len(coords)} geo coords")

    missing_coords = [s["id"] for s in stations if s["id"] not in coords]
    if missing_coords:
        print(f"  WARNING: {len(missing_coords)} stations lack coordinates: {missing_coords[:5]}{' ...' if len(missing_coords)>5 else ''}")
        print(f"  These stations will be dropped from the layout. Run fetch_station_coords.py to fix.")

    print("Building layout ...")
    layout = build_layout(stations, edges, coords)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(layout, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print(f"Wrote {OUTPUT}")
    print(f"  {len(layout['stations'])} stations across {len(layout['lines'])} lines")
    print(f"  Segments per line:")
    for name, info in sorted(layout["lines"].items(), key=lambda kv: -info_seg(kv[1])):
        print(f"    {name:>10}  {len(info['segments']):>4} segments  ({info['station_count']} stations)")


def info_seg(info):
    return len(info["segments"])


if __name__ == "__main__":
    main()
