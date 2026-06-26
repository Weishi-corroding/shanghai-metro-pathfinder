# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Shanghai Metro Route Planning & Operations Management System (上海地铁路径规划与运营管理系统) — a university data structures course design project (东华大学, due 2026-07-01). 5-person team, Python, Dijkstra + Yen's K-Shortest Paths over a 20-line metro network.

## Commands

```bash
# Build the canonical datasets from raw API data (one-time or after re-fetch)
python -m src.build_dataset

# Run the interactive console application
python main.py

# Run the full test suite (41 test cases, M1-M4 + extended)
python -m tests.test_cases
```

## Architecture

### Data pipeline (two-stage)

1. **Fetch**: `metro_api.py` → `fetch_all.py` → `metro_data/line-XX.csv` + `metro_data/fltime-XX.csv` (raw API data, 20 lines)
2. **Build**: `src/build_dataset.py` reads raw CSVs → outputs `data/Station.csv`, `data/Edge.csv`, `data/Station_init.csv`, `data/update_station_status.csv`

The app loads from `data/` CSVs at runtime — raw `metro_data/` files are not read at runtime.

### Key design decisions

- **Transfer node splitting**: Same-name stations split by line (e.g., 人民广场 → 3 nodes: 0113/1号线, 0213/2号线, 0816/8号线). Transfer edges (time=5, line="换乘") connect same-name nodes bidirectionally. This makes Dijkstra naturally account for transfer cost.
- **Station ID format**: `LLNN` = 2-digit line number + 2-digit sequence within line. e.g., `0101` = 1号线 station #1 (莘庄).
- **Directed edges**: Both directions of each line segment are separate edges (up/down travel times may differ).
- **Edge filling**: `fill_missing_adjacent_edges()` in `build_dataset.py` patches gaps in the fltime data — mirrors reverse-direction time for single-missing edges, or inserts default 3min for both-direction-missing (Y-branch forks on lines 5/10/11).

### Module dependency graph

```
main.py
  ├── src/graph.py          (no deps on other src modules)
  ├── src/station.py        (no deps on other src modules)
  └── src/menu.py
        ├── src/pathfinder.py → graph, station
        ├── src/network_analysis.py → graph, station
        └── src/utils.py → station
```

`graph.py` and `station.py` are independent foundations. `pathfinder.py` and `network_analysis.py` consume both. `menu.py` orchestrates everything for the console UI.

### Algorithm details

- **Shortest time (M3)**: `dijkstra_shortest_time()` — standard Dijkstra with heapq, transfer penalty embedded in edge weights (transfer edges = 5min)
- **K-shortest time (M3)**: `yen_k_shortest_time(k=3)` — spur-path strategy, removes edges/nodes from prior paths to force deviation, deduplicates by path key
- **Min transfers (M4)**: `dijkstra_min_transfers()` — tuple weight `(transfer_count, total_time)`, Python's tuple comparison naturally prioritizes transfers first
- **Station closure filtering**: `Graph.neighbors(station_id, station_mgr)` filters out edges whose target station is closed. All pathfinding algorithms pass `station_mgr` through.
- **Path reconstruction**: `_rebuild_path()` traces back through `came_from` dict, then scans consecutive edges to detect line changes (transfer points) by comparing non-transfer edge line fields

### CSV schemas

**Station.csv / Station_init.csv**: `站点ID, 站点名称, 所属线路, 运营状态` (530 rows, status: 开启/关闭)

**Edge.csv**: `起点站ID, 终点站ID, 线路, 运行方向, 通行时间` (1300 rows, line="换乘" for transfer edges)

**update_station_status.csv**: `站点名称, 所属线路, 运营状态` — example batch-update file (station name + line form a composite key)

## Important quirks

- **UTF-8 BOM**: All CSV files use `utf-8-sig` encoding (required for Excel compatibility on Windows). Always read/write with `encoding="utf-8-sig"`.
- **Terminal encoding**: Windows terminals may use GBK and fail on Unicode symbols. Use ASCII-safe markers like `[OK]` and `[错误]` instead of emoji.
- **Line 4 loop**: 26 stations on a circular line, direction field contains "全程（内）"/"全程（外）" for inner/outer loop marking. `format_path()` appends 内圈/外圈 tags when detected, but the algorithm often finds faster non-loop paths, so this feature is rarely triggered in practice.
- **Trailing spaces in station names**: 6 stations in the raw API data had trailing whitespace. `build_dataset.py`'s `clean_name()` strips these.
- **`data/Station_init.csv`**: A pristine copy of Station.csv created during `build_dataset.py`. Used by `StationManager.restore_initial()` (M2-4). If you modify the station set, re-run `build_dataset.py` to regenerate it.
