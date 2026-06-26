# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository structure

```
python/                        # Python implementation (data structures course design)
├── main.py                    # Entry point
├── metro_api.py               # SH Metro API client
├── fetch_all.py               # Batch data fetcher
├── src/                       # Core modules
│   ├── build_dataset.py       # Raw CSV → canonical datasets
│   ├── graph.py               # Adjacency list graph
│   ├── station.py             # Station entity + status management
│   ├── pathfinder.py          # Dijkstra, Yen K-shortest, min-transfers
│   ├── network_analysis.py    # BFS affected area, DFS components
│   ├── menu.py                # Multi-level console UI
│   └── utils.py               # Input validation, fuzzy matching
├── tests/
│   └── test_cases.py          # 41 tests (M1-M4 + extended)
├── data/                      # Canonical CSVs (Station.csv, Edge.csv, ...)
├── metro_data/                # Raw API data (line-XX.csv, fltime-XX.csv)
└── 课设要求/                   # Course design requirements & templates
```

## Commands

All commands run from the `python/` directory:

```bash
cd python

# Build canonical datasets from raw API data
python -m src.build_dataset

# Run the interactive console application
python main.py

# Run the full test suite (41 test cases)
python -m tests.test_cases
```

## Project overview

Shanghai Metro Route Planning & Operations Management System (上海地铁路径规划与运营管理系统) — a university data structures course design project (东华大学, due 2026-07-01). 5-person team, Python, Dijkstra + Yen's K-Shortest Paths over a 20-line metro network (530 stations, 1300 edges).

## Architecture

### Data pipeline (two-stage)

1. **Fetch**: `metro_api.py` → `fetch_all.py` → `metro_data/line-XX.csv` + `metro_data/fltime-XX.csv` (20 lines)
2. **Build**: `src/build_dataset.py` reads raw CSVs → outputs `data/Station.csv`, `data/Edge.csv`, `data/Station_init.csv`, `data/update_station_status.csv`

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

### Key design decisions

- **Transfer node splitting**: Same-name stations split by line (e.g., 人民广场 → 3 nodes: 0113/1号线, 0213/2号线, 0816/8号线). Transfer edges (time=5, line="换乘") connect same-name nodes bidirectionally.
- **Station ID format**: `LLNN` = 2-digit line number + 2-digit sequence. e.g., `0101` = 1号线 #1 (莘庄).
- **Directed edges**: Both directions of each segment are separate edges (up/down travel times may differ).
- **Edge filling**: `fill_missing_adjacent_edges()` patches fltime gaps — mirrors reverse-direction time or inserts default 3min for Y-branch forks (lines 5/10/11).

### Algorithms

- **Shortest time (M3)**: `dijkstra_shortest_time()` — heapq Dijkstra, transfer penalty in edge weights
- **K-shortest time (M3)**: `yen_k_shortest_time(k=3)` — spur-path with edge/node removal, path dedup
- **Min transfers (M4)**: `dijkstra_min_transfers()` — tuple weight `(transfer_count, total_time)`
- **Station closure**: `Graph.neighbors(id, station_mgr)` filters closed target stations
- **Line 4 loop**: Direction tags (内圈/外圈) via `line4_dirs` dict keyed by station ID

### Important quirks

- **UTF-8 BOM**: All CSV files use `utf-8-sig` encoding (Windows Excel compatibility).
- **Terminal encoding**: Windows GBK terminals garble Chinese. Use ASCII-safe `[OK]`/`[错误]` markers instead of emoji.
- **`data/Station_init.csv`**: Pristine copy created by `build_dataset.py`, used by `StationManager.restore_initial()` (M2-4). Re-run `build_dataset.py` to regenerate after station changes.
- **Trailing spaces**: Station names from the API may have trailing whitespace; `clean_name()` in `build_dataset.py` strips them.
