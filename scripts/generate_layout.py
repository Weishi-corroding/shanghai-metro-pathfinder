"""
generate_layout.py — Generate station layout coordinates for metro map.

Reads Station.csv and Edge.csv, produces a topology-based schematic layout.
Each metro line is a horizontal row. Transfer stations (same name, different
lines) are snapped to a shared position.

Output: cpp/backend/static/layout.json

Usage:
    python scripts/generate_layout.py
"""

import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "python" / "data"
STATION_CSV = DATA_DIR / "Station.csv"
EDGE_CSV = DATA_DIR / "Edge.csv"
OUTPUT = ROOT / "cpp" / "backend" / "static" / "layout.json"

LINE_COLORS = {
    "1号线": "#E4002B", "2号线": "#97D700", "3号线": "#FCD600",
    "4号线": "#461D84", "5号线": "#944D9B", "6号线": "#D6006C",
    "7号线": "#ED6B06", "8号线": "#0094D8", "9号线": "#7AC8E1",
    "10号线": "#C6AFD4", "11号线": "#841C21", "12号线": "#007A60",
    "13号线": "#E77CA5", "14号线": "#9D8B63", "15号线": "#B2A680",
    "16号线": "#77D0C8", "17号线": "#BB6414", "18号线": "#C4984E",
    "浦江线": "#B5B5B6", "市域机场线": "#4A90A4",
}

# Line ordering: roughly north-to-south, west-to-east to minimize crossovers
LINE_ORDER = [
    "17号线", "11号线", "7号线", "10号线",
    "1号线", "3号线", "15号线",
    "2号线", "13号线", "14号线",
    "9号线", "12号线", "4号线",
    "6号线", "8号线", "18号线",
    "5号线", "16号线", "浦江线", "市域机场线",
]


def parse_sequence(station_id: str) -> int:
    return int(station_id[2:])


def load_stations(path: Path) -> list[dict]:
    stations = []
    with open(path, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            stations.append({
                "id": row["站点ID"],
                "name": row["站点名称"],
                "line": row["所属线路"],
                "status": row["运营状态"],
            })
    return stations


def group_by_line(stations: list[dict]) -> dict[str, list[dict]]:
    groups = defaultdict(list)
    for s in stations:
        groups[s["line"]].append(s)
    for line in groups:
        groups[line].sort(key=lambda s: parse_sequence(s["id"]))
    return dict(groups)


def find_transfer_groups(stations: list[dict]) -> dict[str, list[str]]:
    name_to_ids = defaultdict(list)
    for s in stations:
        name_to_ids[s["name"]].append(s["id"])
    return {name: ids for name, ids in name_to_ids.items() if len(ids) > 1}


def generate_layout(stations: list[dict]) -> dict:
    line_groups = group_by_line(stations)
    transfer_groups = find_transfer_groups(stations)

    active_lines = [l for l in LINE_ORDER if l in line_groups]
    for line in line_groups:
        if line not in active_lines:
            active_lines.append(line)

    Y_SPACING = 80
    X_SPACING = 56
    PAD_LEFT = 60
    PAD_TOP = 60

    line_y = {}
    for i, line_name in enumerate(active_lines):
        line_y[line_name] = PAD_TOP + i * Y_SPACING

    # Step 1: initial positions along each line
    layout = {}
    for line_name, sts in line_groups.items():
        base_y = line_y.get(line_name, PAD_TOP)
        for st in sts:
            seq = parse_sequence(st["id"])
            x = PAD_LEFT + seq * X_SPACING
            layout[st["id"]] = {
                "x": x,
                "y": base_y,
                "name": st["name"],
                "line": st["line"],
                "color": LINE_COLORS.get(line_name, "#666666"),
            }

    # Step 2: snap transfer stations to shared positions
    for name, ids in transfer_groups.items():
        valid = [i for i in ids if i in layout]
        if len(valid) < 2:
            continue
        avg_x = sum(layout[i]["x"] for i in valid) / len(valid)
        avg_y = sum(layout[i]["y"] for i in valid) / len(valid)

        offsets = [(0, 0)]
        if len(valid) == 2:
            offsets = [(-5, 0), (5, 0)]
        elif len(valid) == 3:
            offsets = [(-6, -3), (6, -3), (0, 5)]
        elif len(valid) >= 4:
            offsets = [(-7, -5), (7, -5), (-7, 5), (7, 5)]

        for j, sid in enumerate(valid):
            off = offsets[min(j, len(offsets) - 1)]
            layout[sid]["x"] = round(avg_x + off[0], 1)
            layout[sid]["y"] = round(avg_y + off[1], 1)
            layout[sid]["is_transfer"] = True

    # Set transfer info
    for name, ids in transfer_groups.items():
        for sid in ids:
            if sid in layout:
                layout[sid]["is_transfer"] = True
                layout[sid]["transfer_to"] = list(set(
                    layout[i]["line"] for i in ids if i in layout and i != sid
                ))

    return layout


def main():
    print(f"Loading stations from {STATION_CSV}...")
    stations = load_stations(STATION_CSV)
    print(f"  Loaded {len(stations)} stations")

    line_groups = group_by_line(stations)
    transfer_groups = find_transfer_groups(stations)

    print("Generating layout...")
    layout = generate_layout(stations)

    output_data = {
        "meta": {
            "total_stations": len(stations),
            "total_lines": len(line_groups),
            "transfer_stations": len(transfer_groups),
            "description": "Shanghai Metro schematic layout",
        },
        "stations": layout,
        "lines": {
            name: {
                "name": name,
                "color": LINE_COLORS.get(name, "#666666"),
                "station_ids": [s["id"] for s in sts],
                "station_count": len(sts),
            }
            for name, sts in line_groups.items()
        },
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    print(f"Writing to {OUTPUT}...")
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"Done! {len(layout)} stations across {len(line_groups)} lines.")
    print(f"  Transfer groups: {len(transfer_groups)}")


if __name__ == "__main__":
    main()
