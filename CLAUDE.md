# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository structure

```
python/                        # Python implementation (original)
└── src/                       # graph, station, pathfinder, menu, network_analysis, utils, build_dataset

cpp/                           # C++17 implementation (feature-complete rewrite)
├── include/metro/             # Headers: station, graph, csv, pathfinder, network_analysis, menu, utils, build_dataset
├── src/                       # Corresponding .cpp files (~2500 lines with pathfinder.cpp at ~840 lines)
└── tests/
    ├── test_cases.cpp         # 41 tests (M1-M4 + extended) — mirrors python/tests/test_cases.py
    └── coursework_check.cpp   # 53 requirements checks mapped to 课设要求 scoring criteria

data/                           # NOT a separate dir — canonical CSVs live under python/data/ (shared with cpp/)
metro_data/                     # NOT a separate dir — raw API CSVs live under python/metro_data/
```

Both implementations share the same `python/data/` and `python/metro_data/` directories. The C++ `build_dataset` reads from `python/metro_data/` and writes to `python/data/`.

## Commands

### Python (run from `python/`)

```bash
cd python
python -m src.build_dataset          # Build Station.csv / Edge.csv from raw API data
python main.py                        # Interactive console app
python -m tests.test_cases           # 41 tests
```

### C++ (run from repo root or `cpp/`)

```bash
# Manual build — no CMake required (g++ MinGW-w64 or MSVC)
cd cpp
mkdir -p build

# Compile all objects
g++ -std=c++17 -Wall -I include -c src/station.cpp -o build/station.o
g++ -std=c++17 -Wall -I include -c src/graph.cpp -o build/graph.o
g++ -std=c++17 -Wall -I include -c src/csv.cpp -o build/csv.o
g++ -std=c++17 -Wall -I include -c src/pathfinder.cpp -o build/pathfinder.o
g++ -std=c++17 -Wall -I include -c src/network_analysis.cpp -o build/network_analysis.o
g++ -std=c++17 -Wall -I include -c src/utils.cpp -o build/utils.o
g++ -std=c++17 -Wall -I include -c src/menu.cpp -o build/menu.o
g++ -std=c++17 -Wall -I include -c src/main.cpp -o build/main.o

# Link metro_app (interactive console)
g++ -std=c++17 build/station.o build/graph.o build/csv.o build/pathfinder.o build/network_analysis.o build/utils.o build/menu.o build/main.o -o build/metro_app.exe

# Link build_dataset (data pipeline)
g++ -std=c++17 -Wall -I include -c src/build_dataset.cpp -o build/build_dataset.o
g++ -std=c++17 build/station.o build/graph.o build/csv.o build/build_dataset.o -o build/build_dataset.exe

# Build and run tests
g++ -std=c++17 -Wall -I include src/station.cpp src/graph.cpp src/csv.cpp src/utils.cpp src/pathfinder.cpp src/network_analysis.cpp tests/test_cases.cpp -o build/metro_tests.exe
./build/metro_tests.exe

# Build and run coursework requirements check (53 checks)
g++ -std=c++17 -Wall -I include src/station.cpp src/graph.cpp src/csv.cpp src/pathfinder.cpp src/network_analysis.cpp tests/coursework_check.cpp -o build/coursework_check.exe
./build/coursework_check.exe
```

Or use CMake (if installed):

```bash
cd cpp && mkdir build && cd build
cmake .. && cmake --build .
ctest --output-on-failure
```

## Project overview

Shanghai Metro Route Planning & Operations Management System (上海地铁路径规划与运营管理系统) — university data structures course design (东华大学, due 2026-07-01). Two implementations: Python (original) and C++17 (complete rewrite). Dijkstra + Yen's K-Shortest Paths over 20 metro lines (~530 stations, ~1300 edges).

## Architecture (common to both implementations)

### Data pipeline

1. **Raw API data** → `python/metro_data/line-XX.csv` (station listings) + `fltime-XX.csv` (interval times) for 20 lines
2. **Build canonical CSVs** → `data/Station.csv` (站点ID, 站点名称, 所属线路, 运营状态), `data/Edge.csv` (起点站ID, 终点站ID, 线路, 运行方向, 通行时间), `data/Station_init.csv`, `data/update_station_status.csv`

### Module dependency graph

```
main / main.cpp
  ├── graph       (adjacency list — no deps on other project modules)
  ├── station     (station registry + status management — no deps)
  └── menu
        ├── pathfinder     → graph, station
        ├── network_analysis → graph, station
        └── utils          → station
```

### Key design decisions

- **Transfer node splitting**: Same-name stations split by line (e.g., 人民广场 → 3 nodes: 0113/1号线, 0213/2号线, 0816/8号线). Transfer edges (time=5, line="换乘") connect same-name nodes bidirectionally.
- **Station ID format**: `LLNN` = 2-digit line number + 2-digit sequence. e.g., `0101` = 1号线 #1 (莘庄).
- **Directed edges**: Both directions of each segment are separate edges (up/down travel times may differ).
- **Edge filling**: `fill_missing_adjacent_edges()` patches fltime gaps — mirrors reverse-direction time or inserts default 3min for Y-branch forks (lines 5/10/11).
- **Ring closure removal**: `remove_loop_closure_edges()` detects edges between same-name same-line stations (e.g., Line 4's 0401↔0426 pseudo-edge) and removes them.

### Algorithms

- **Shortest time (M3)**: `dijkstra_shortest_time()` — priority-queue Dijkstra, transfer penalty in edge weights
- **K-shortest time (M3)**: `yen_k_shortest_time(k=3)` — spur-path with edge/node removal, path dedup
- **Min transfers (M4)**: `dijkstra_min_transfers()` — tuple weight `(transfer_count, total_time)` with lexicographic comparison
- **Station closure**: `Graph.neighbors(id, station_mgr)` filters closed target stations
- **Line 4 loop**: Direction tags (内圈/外圈) via `line4_dirs` map keyed by station ID
- **Network analysis**: BFS `affected_area()` (K-order neighbor), DFS `count_components()` (connected components)

### Important quirks

- **UTF-8 BOM**: All CSV files use `utf-8-sig` encoding. The C++ `csv::Writer` writes BOM by default; `csv::Reader::skip_bom()` detects and skips `\xEF\xBB\xBF`.
- **Terminal encoding**: Windows pre-Win10 terminals use GBK. Both implementations use ASCII-safe `[OK]`/`[错误]` markers for status. The C++ `main.cpp` calls `SetConsoleOutputCP(CP_UTF8)` on startup.
- **`Station_init.csv`**: Pristine copy created by `build_dataset`, used by `StationManager.restore_initial()`. Must re-run `build_dataset` to regenerate after station changes.
- **Trailing spaces**: Station names from the API may have trailing whitespace; `clean_name()` strips them.

## C++ specific design decisions

### STL container choices

| Abstraction | C++ Type |
|---|---|
| Dict/map | `std::unordered_map<std::string, T>` |
| List/sequence | `std::vector<T>` |
| Set (visited) | `std::unordered_set<std::string>` |
| Priority queue (min-heap) | `std::priority_queue<T, vector<T>, std::greater<>>` |
| BFS queue | `std::queue<std::pair<std::string, int>>` |

### Weight comparison design (critical)

The `TimeWeight` and `TransferWeight` structs use natural `operator<` (smaller = better). Priority queues are declared with `std::greater<>` to achieve min-heap behavior. The same `operator<` is used for dist-map relaxation (`new_weight < dist[v]`). **Do not** reverse the comparison (e.g., `return time > o.time`) — this was the root cause of a path-optimality bug.

### Path reconstruction (rebuild_path)

The `rebuild_path()` function walks backward through `came_from` (a predecessor map). Two pitfalls were fixed:
1. **Empty prev_id**: The start node has `prev_id = ""`. The backward walk must break when `curr.empty()` is true.
2. **Came_from cycles**: Cycle detection via `std::unordered_set<std::string> seen` prevents infinite loops in case of inconsistent predecessor updates.

### PredecessorInfo — store by value, not pointer

`PredecessorInfo` stores edge data (`line`, `direction`, `time`, `is_transfer`) by value, NOT as `const Edge*`. The Edge from `Graph::neighbors()` is returned by value (temporary vector); storing a pointer to it would dangle.

### CSV handling

Self-contained lightweight parser in `csv.hpp/cpp` (~170 lines). Handles:
- UTF-8 BOM detection and skipping on read
- BOM writing on write (Excel compatibility)
- Basic quoted field support (escaped `""`)
- Windows CRLF line endings

### Data file location

Both `main.cpp` and `build_dataset.cpp` resolve paths relative to the working directory. They search multiple locations (e.g., `../python/data/`, `python/data/`, `data/`) to find `Edge.csv` and `Station.csv`.

### No external dependencies

The C++ implementation uses only the C++17 standard library. Catch2 is not bundled — tests use a minimal custom framework with `check()` macros. This ensures build-anywhere simplicity.

## Testing

Both implementations have identical test coverage (41 cases across M1-M4 modules + extended):

- **M1**: Menu structure, input validation
- **M2**: CSV batch update, manual status toggle, closed-listing, restore, line info, transfer detection
- **M3**: Dijkstra shortest time (reachability, transfer count, edge cases), Yen K-shortest (count, monotonicity, no loops)
- **M4**: Dijkstra min transfers, Yen K-min transfers, boundary cases
- **Extended**: `affected_area()` BFS, `count_components()` DFS

The additional `coursework_check.cpp` maps 53 checks directly to the 课设要求 scoring matrix (数据集建设 10pts, 图拓扑 10pts, 路径算法 15pts, 运营管理 15pts, 网络分析 5pts, 可视化等).

Acceptance criteria: ≥95% pass rate on the 41-test suite, 100% on core path-planning functionality.
