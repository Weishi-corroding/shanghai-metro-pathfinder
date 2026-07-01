# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository structure

```
python/                        # Python implementation (original)
├── src/                       # graph, station, pathfinder, menu, network_analysis, utils, build_dataset
├── metro_api.py               # Shanghai Metro official API client wrapper
├── fetch_all.py               # One-shot: fetches all 20 lines from the API → metro_data/
└── request_metro.py           # Direct API query utility (standalone)

cpp/                           # C++17 implementation (feature-complete rewrite)
├── include/metro/             # Headers: station, graph, csv, pathfinder, network_analysis, menu, utils, build_dataset
├── src/                       # Corresponding .cpp files (~3,100 lines total; pathfinder.cpp ~840 lines)
├── backend/                   # HTTP REST API server (wraps metro_core for the web UI)
│   ├── server.cpp             # ~620 lines: httplib + nlohmann/json, 16 JSON endpoints + static file mount
│   └── static/                # Minimal map-free UI: index.html, app.js (REST client), tailwind.js (vendored); legacy/ holds the archived D3.js map UI
├── third_party/               # Vendored single-header libs (committed): cpp-httplib/, nlohmann/
├── CMakeLists.txt             # Builds metro_core static library + 5 targets: app, server, tests, coursework_check, build_dataset
├── build_server.sh            # Static-link script for portable metro_server_s.exe (no MinGW DLLs needed)
└── tests/
    ├── test_cases.cpp         # 41 tests (M1-M4 + extended) — mirrors python/tests/test_cases.py
    └── coursework_check.cpp   # 53 requirements checks mapped to 课设要求 scoring criteria

cpp_CLI/                       # C++17 minimal-viable CLI variant (~1,670 lines)
├── include/                   # Headers: csv, station, graph, pathfinder (4 files, ~240 lines)
├── src/                       # Implementation: csv, station, graph, pathfinder, main (5 files, ~1,430 lines)
├── CMakeLists.txt             # Single target — metro_cli
├── build.sh                   # Alternative: single g++ command, no CMake needed
└── README.md                  # Self-contained build/run guide + cpp/ comparison table

scripts/
├── fetch_station_coords.py    # One-shot: Overpass API → station_coords.json (530 lat/lng pairs); use --refresh to re-query
├── station_coords.json        # Committed cache of real geographic coordinates per station ID
├── station_coords_override.json # Manual fallback coords for stations OSM didn't have (~9 entries)
├── .overpass_cache.json       # Raw OSM response cache (1 MB, committed to avoid re-querying)
└── generate_layout.py         # Reads station_coords.json + Edge.csv → equirectangular projection → layout.json

data/                           # NOT a separate dir — canonical CSVs live under python/data/ (shared with cpp/ and cpp_CLI/)
metro_data/                     # NOT a separate dir — raw API CSVs live under python/metro_data/
```

All three implementations (`python/`, `cpp/`, `cpp_CLI/`) share the same `python/data/` directory. Only `cpp/build_dataset` and `python/-m src.build_dataset` can regenerate it from `python/metro_data/`; `cpp_CLI/` is read-only against that data.

## Root Directory

```
D:\Code\metro (repo root)
├── .claude/              # Claude Code session state & plans (commit-safe to gitignore)
│   ├── worktrees/        # Isolated git worktrees (e.g., for PPT generation)
│   └── settings.local.json
├── .git/                 # Git repository
├── .gitignore
├── .vscode/              # VS Code configs
├── cpp/                  # Feature-complete C++ impl (see above)
├── cpp_CLI/              # Minimal C++ CLI
├── docs/                 # Empty directory (docs placeholder)
├── metroView.jpg         # Full-page D3 UI screenshot — use for docs/presentations
├── python/               # Python impl
├── scripts/              # Layout, coordinate fetching, utilities
└── CLAUDE.md             # This file
```

**Important**: No top-level `CMakeLists.txt` exists. CMake build directories must be under `cpp/` or `cpp_CLI/`.

## Commands

### Python (run from `python/`)

```bash
cd python
python fetch_all.py                   # Fetch raw data from Shanghai Metro official API → metro_data/
python -m src.build_dataset          # Build Station.csv / Edge.csv from raw API data
python main.py                        # Interactive console app
python -m tests.test_cases           # 41 tests (M1-M4 modules + extended)
```

### C++ (run from repo root or `cpp/`)

**CMake (recommended)** — builds `metro_core` static library, then all targets:

```bash
cd cpp && mkdir -p build && cd build
cmake .. && cmake --build .
ctest --output-on_failure            # Run 41 tests
```

CMake targets: `metro_app` (console), `metro_server` (web), `metro_tests` (tests), `build_dataset` (data pipeline), `coursework_check` (grading).

**Running specific tests**: Run `metro_tests.exe` with a pattern to filter test names. Pass no arguments to run all 41 tests. On Windows use the `.exe` suffix.

**Manual build** — no CMake required (g++ MinGW-w64 or MSVC):

```bash
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

### cpp_CLI (run from repo root or `cpp_CLI/`)

Self-contained minimal CLI variant. Reuses `python/data/` (no build_dataset of its own). Build with either CMake or a single g++ invocation:

```bash
# Option A — CMake
cd cpp_CLI && mkdir -p build && cd build
cmake .. && cmake --build .

# Option B — bash script (single g++ call, static-linked)
cd cpp_CLI && ./build.sh

# Option C — direct g++ one-liner (MinGW-w64 or clang++)
cd cpp_CLI
g++ -std=c++17 -O2 -Wall -I include \
    src/csv.cpp src/station.cpp src/graph.cpp src/pathfinder.cpp src/main.cpp \
    -o build/metro_cli.exe

# Run (data dir auto-detected; --data overrides)
./build/metro_cli                                    # tries ../python/data, python/data, etc.
./build/metro_cli --data D:/Code/metro/python/data   # explicit
```

No tests in this variant — it's intended as a minimal independently-deliverable artifact for the course's "上机代码实现 60 分" criteria. For algorithm regression testing use `cpp/`'s 41-test suite.

### Web server (run from `cpp/`)

```bash
# CMake — adds the metro_server target alongside metro_app/metro_tests
cd cpp && mkdir -p build && cd build
cmake .. && cmake --build . --target metro_server

# Or use the static-link bash script (produces a portable .exe on Windows)
cd cpp && ./build_server.sh    # links statically, no MinGW DLLs needed at runtime

# Run (port and data dir are optional; defaults: 8080, ../python/data)
# IMPORTANT: use metro_server_s.exe (static-linked, no DLL deps) — the smaller metro_server.exe
# is dynamic-linked and fails with exit 127 on Windows without MinGW DLLs on PATH.
cd cpp/build
./metro_server_s.exe --data ../python/data --port 8080
# Then open http://localhost:8080

# Windows cmd/powershell (run from repo root):
cpp\build\metro_server_s.exe --data python\data --port 8080

# Or use the convenience batch file (edit hardcoded paths first):
cpp\run_server.bat

# Regenerate the geographic layout (two steps — rerun only when station topology changes):
python scripts/fetch_station_coords.py          # Step 1: fetch lat/lng (uses cache; add --refresh to re-query OSM)
python scripts/generate_layout.py               # Step 2: project to SVG coords → writes cpp/backend/static/layout.json

# Also writes octilinear.json (schematic diagram layout):
# cpp/backend/static/octilinear.json
```

## Project overview

Shanghai Metro Route Planning & Operations Management System (上海地铁路径规划与运营管理系统) — university data structures course design (东华大学, due 2026-07-01). **Three** implementations sharing one canonical dataset (`python/data/`):

| Variant | Lines | Purpose |
|---|---|---|
| `python/` | ~3,165 | Original; owns the API fetch pipeline (`fetch_all.py`) |
| `cpp/` | ~3,108 | Feature-complete C++ rewrite + HTTP server + D3.js web UI |
| `cpp_CLI/` | ~1,670 | Minimal-viable C++ CLI; same M1–M4 functionality as `cpp/` but no server / no build_dataset / no tests |

All three implement Dijkstra + Yen's K-Shortest Paths over 20 metro lines (~530 physical stations, ~800 graph nodes after transfer splitting, ~1,300 directed edges). When asked to fix a path-planning bug, fix it in **all** the variants that contain that code path — they drift silently otherwise.

## Architecture (common to all three implementations)

### Data pipeline (three stages)

1. **Fetch** (Python only): `metro_api.py` + `fetch_all.py` hits the official Shanghai Metro mobile API (`m.shmetro.com`) → `python/metro_data/line-XX.csv` (station listings) + `fltime-XX.csv` (interval times) for 20 lines.
2. **Build** (both implementations): `build_dataset` reads raw CSVs, assigns station IDs, splits transfer stations into separate nodes, creates transfer edges (time=5, line="换乘"), fills missing adjacent edges, removes ring-closure pseudo-edges → `python/data/Station.csv`, `Edge.csv`, `Station_init.csv`, `update_station_status.csv`.
3. **Visualize**: `scripts/fetch_station_coords.py` (OSM Overpass API for lat/lng) → `scripts/generate_layout.py` (equirectangular projection to SVG coords) → `cpp/backend/static/layout.json`.

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

- **Transfer node splitting**: Same-name stations split by line (e.g., 人民广场 → 3 nodes: 0113/1号线, 0213/2号线, 0816/8号线). Transfer edges (time=5, line="换乘") connect same-name nodes bidirectionally. This is the critical design choice — the graph has ~800 nodes for ~530 physical stations.
- **Station ID format**: `LLNN` = 2-digit line number + 2-digit sequence within line. e.g., `0101` = 1号线 #1 (莘庄). This format is hard-coded in test suites.
- **Directed edges**: Both directions of each segment are separate edges (up/down travel times may differ).
- **Edge filling**: `fill_missing_adjacent_edges()` patches fltime gaps — mirrors reverse-direction time or inserts default 3min for Y-branch forks (lines 5/10/11).
- **Ring closure removal**: `remove_loop_closure_edges()` detects edges between same-name same-line stations (e.g., Line 4's 0401↔0426 pseudo-edge) and removes them.

### Algorithms

- **Shortest time (M3)**: `dijkstra_shortest_time()` — priority-queue Dijkstra, transfer penalty in edge weights
- **K-shortest time (M3)**: `yen_k_shortest_time(k=3)` — spur-path with edge/node removal, path dedup
- **Min transfers (M4)**: `dijkstra_min_transfers()` — tuple weight `(transfer_count, total_time)` with lexicographic comparison
- **K-min transfers (M4)**: `yen_k_min_transfers(k=3)` — same spur-path algorithm, using TransferWeight
- **Station closure**: `Graph.neighbors(id, station_mgr)` filters closed target stations; transfer edges never blocked
- **Line 4 loop**: Direction tags (内圈/外圈) stored per edge in Edge.csv, recorded in `PathResult::line4_dirs` map
- **Network analysis**: BFS `affected_area()` (K-order neighbor), DFS `count_components()` (connected components)

### Important quirks (C++ specific — CRITICAL)

1. **Weight comparison MUST NOT be reversed**: `TimeWeight` and `TransferWeight` use natural `operator<` (smaller = better). Priority queues use `std::greater<>` for min-heap. Reversing this was the root cause of a path-optimality bug.

2. **PredecessorInfo stores by value, NOT pointer**: The Edge from `Graph::neighbors()` is returned by value (temporary vector). Storing `const Edge*` would dangle.

3. **rebuild_path() must handle two failure modes**: (a) start node has `prev_id = ""`, break when `curr.empty()`; (b) cycle detection via `std::unordered_set<std::string> seen` prevents infinite loops.

4. **UTF-8 BOM**: All CSV files use `utf-8-sig` encoding. C++ `csv::Writer` writes BOM by default; `csv::Reader::skip_bom()` detects and skips `\xEF\xBB\xBF`. Required for Chinese Excel compatibility.

5. **Terminal encoding**: Windows pre-Win10 terminals use GBK. C++ `main.cpp` calls `SetConsoleOutputCP(CP_UTF8)` on startup. Status messages use ASCII-safe `[OK]`/`[错误]` markers.

6. **`Station_init.csv`**: Pristine copy created by `build_dataset`, used by `StationManager.restore_initial()`. Must re-run `build_dataset` to regenerate after station changes.

7. **Trailing spaces**: Station names from the API may have trailing whitespace; `clean_name()` strips them.

8. **Data directory resolution**: Tries 4 paths (`../python/data`, `python/data`, `data`, `../data`). Always run from repo root or `cpp/` directory.

## C++ specific design decisions

### STL container choices

| Abstraction | C++ Type |
|---|---|
| Dict/map | `std::unordered_map<std::string, T>` |
| List/sequence | `std::vector<T>` |
| Set (visited) | `std::unordered_set<std::string>` |
| Priority queue (min-heap) | `std::priority_queue<T, vector<T>, std::greater<>>` |
| BFS queue | `std::queue<std::pair<std::string, int>>` |

### CSV handling

Self-contained lightweight parser in `csv.hpp/cpp` (~170 lines). Handles UTF-8 BOM detection/skipping, BOM writing, quoted fields (escaped `""`), Windows CRLF line endings.

### No external dependencies

The C++ implementation uses only the C++17 standard library. **No Catch2, no gtest** — tests use a minimal custom framework with `check()` macros. This ensures build-anywhere simplicity.

The `metro_server` target adds two vendored single-header libraries under `cpp/third_party/` (`cpp-httplib/httplib.h`, `nlohmann/json.hpp`) — both header-only with no runtime dependencies. Windows build links statically (`-static` + `-lws2_32`) so the resulting `.exe` runs without MinGW DLLs on PATH.

## cpp_CLI vs cpp/ — what diverged

`cpp_CLI/` is structurally similar but **not** a subset of `cpp/`. The C++ rewrite work that improved the minimal version surfaced bugs in `cpp/` that were NOT back-ported (`cpp_CLI/`'s decisions are listed first):

| Concern | cpp_CLI behavior | cpp/ behavior |
|---|---|---|
| Trailing transfer counts as transfer | No (rider semantics: walking to dst platform isn't a ride) | No (same) |
| Initial transfer counts as transfer | No — `line_trace` is not seeded with the start's nominal line, so boarding the first line at a transfer-station origin is not a transfer (fixed 2026-06-30) | **Yes** (fixed 2026-07-01) — `rebuild_path` seeds `line_trace` with the origin station's line, so a rider starting at a specific platform of a transfer station and switching lines is counted as one transfer. `dijkstra_min_transfers` seeds `node_line[src]` with the same line so the cost function agrees. |
| Same-station pure transfer (莘庄1↔莘庄5) | 0 transfers (path is one transfer edge, no riding segments) | **1** transfer — degenerate branch in `rebuild_path` returns 1 when the path has no riding edges and `src_line != dst_line` (fixed 2026-07-01) |
| Physical station count (途经N站) | Format renders each node, so terminal transfer platform double-counts | **Deduped** — `PathResult::station_count()` returns `station_ids.size() - transfer_edge_count`, and `format_path` prints that value. 莘庄→莘庄 shows 途经 1 站 (fixed 2026-07-01) |
| `format()` shows terminal node reached via transfer | Yes (special-case at `i+1==size`) | Yes (same — `prev_emitted_xfer` + `i+1==size` keeps the destination name; fixed 2026-06-30) |
| Consecutive `--[换乘]--` markers | Collapsed to one | Collapsed to one (fixed 2026-06-30) |
| `Graph::neighbors()` API | Returns `const vector<Edge>&` (no copy) | Returns `vector<Edge>` (copies on every Dijkstra relaxation) |
| Closed-station filter | Inline in pathfinder (`target_open`) | Inside `Graph::neighbors()` itself |
| `pick_station` rejects closed stations | Yes, when `require_open=true` (path-planning callers pass true) | Lets closed stations through, fails later in `guard()` |
| Batch update counter | Per-station (handles duplicate name+line correctly) | Per-station (fixed 2026-06-30; previously per-row) |
| Yen K-best | Single template function `yen_k<>()` | Two ~50-line copy-paste blocks |
| `BatchStats::errors` | Populated with per-row diagnostics | Populated similarly (no regression) |

**Transfer-counting semantics (cpp/, settled 2026-07-01)**: transfer count reflects the rider standing on a specific platform. Boarding a *different* line than your origin node sits on is a transfer (the origin platform switch counts). Walking to another platform of the *destination* station is NOT counted — you've already arrived. A pure same-station transfer (e.g. 莘庄1号线→莘庄5号线) is 1 transfer, 5 分钟, 途经 1 站. Examples: 人民广场(1号线)→陆家嘴(2号线) = 1 transfer (must walk to 2号线 platform first); 莘庄→陆家嘴 = 1 transfer (mid-trip line change at 上海体育馆 or similar); 一大会址·黄陂南路(1号线)→人民广场(2号线) = 0 transfers (rode line 1 to destination, arrived at 人民广场 physical station; the trailing transfer edge to the 2号线 platform is 5 min but not a counted ride change). Enforced in `rebuild_path()` by seeding `line_trace` with the origin's line and adding a degenerate branch for pure-transfer paths, plus in `dijkstra_min_transfers` / `min_transfer_with_removals` by seeding `node_line[src]` with the origin's line.

**cpp_CLI/ still uses the pre-2026-07-01 semantics** (initial transfer free, same-station transfer = 0). The two variants intentionally diverge on this point — see the table row above.

**When fixing a path-planning bug**: check whether it manifests in both variants. The shared algorithms (Dijkstra/Yen) live in different files (`cpp/src/pathfinder.cpp` vs `cpp_CLI/src/pathfinder.cpp`) with no shared header — bugs MUST be fixed in both places independently.

## Web backend (cpp/backend/)

`server.cpp` is a thin HTTP/JSON wrapper over `metro_core` — it does no algorithmic work of its own; every route delegates to existing `pathfinder::*`, `analysis::*`, and `StationManager` calls.

### Global state + thread safety

```cpp
static metro::Graph g_graph;
static metro::StationManager g_mgr;
static std::shared_mutex g_state_mutex;
```

- Read routes (pathfinding, queries, analysis) take `std::shared_lock` — many can run concurrently.
- Write routes (station close/open, batch CSV upload, restore) take `std::unique_lock` — exclusive.
- The pathfinder functions accept `const Graph&` / `const StationManager&`, so they are naturally safe under shared_lock. `StationManager::set_status()` mutates and requires unique_lock.

### Routes (16 endpoints)

| Group | Routes |
|---|---|
| Data queries | `GET /api/stations`, `/api/stations/search?q=`, `/api/stations/<id>`, `/api/lines`, `/api/graph/summary`, `/api/layout`, `/api/health` |
| Route planning | `POST /api/route/shortest-time`, `/api/route/k-shortest-time`, `/api/route/min-transfers`, `/api/route/k-min-transfers` |
| Station mgmt | `POST /api/stations/<id>/close`, `/api/stations/<id>/open`, `/api/stations/batch-update` (multipart), `/api/stations/restore` |
| Analysis | `POST /api/analysis/affected-area`, `GET /api/analysis/components` |

Static files (`backend/static/`) are mounted at `/` via `svr.set_mount_point()`.

### Frontend (cpp/backend/static/)

The active UI is a **minimal, map-free** single page (rebuilt 2026-06-30). The original D3.js geographic-map / octilinear UI was archived to `backend/static/legacy/` (still served at `/legacy/…`); it is no longer linked from the live page.

- **`index.html`** — Light "card" theme, top-bar tabs (路径规划 / 运营管理 / 网络分析), stat badges. No SVG map.
- **`app.js`** (~480 lines) — Vanilla JS, **no D3, no map rendering**. Pure REST client over the 16 endpoints:
  - Route planning (shortest-time / min-transfers, 1 or 3 paths) → results as vertical-timeline cards with line-color badges and 换乘 markers
  - Station management (filter by line/status/name, toggle open/close, batch CSV upload, restore all)
  - Network analysis (affected-area BFS chips, connected-components DFS list)
  - Reusable debounced station-search dropdown backed by `/api/stations/search`
- **`tailwind.js`** (~451 KB) — Vendored Tailwind Play CDN compiler. JITs utility classes in-browser (incl. dynamically-rendered ones via MutationObserver), so the page works **fully offline** like the rest of the project. Line colors come from `/api/lines` at runtime and are applied via inline styles.
- **`legacy/`** — Archived original frontend: `app.js` (~1,464 lines, D3.js map), `labeler.js` (D3-Labeler SA fork), `layout.json` (equirectangular projection), `octilinear*.json` (8-direction schematic), `d3.v7.min.js`, old `index.html` / `style.css`. Restore by copying back to the static root if the map UI is needed again.
- **Layout regeneration** (only relevant to the legacy map UI): `scripts/generate_layout.py` writes `layout.json` / `octilinear.json` to the static root — move them into `legacy/` (or update the script's output path) if regenerated.
- **`LINE_COLORS`** still lives in `server.cpp`, `generate_layout.py`, and `build_dataset.hpp` (via `LINE_NAMES`). The live `app.js` no longer hard-codes them — it reads `/api/lines`, so the front-of-house copy is gone (3 places remain to sync, not 4).

## Testing

Both implementations have identical test coverage (41 cases across M1-M4 modules + extended):

- **M1**: Menu structure, input validation
- **M2**: CSV batch update, manual status toggle, closed-listing, restore, line info, transfer detection
- **M3**: Dijkstra shortest time (reachability, transfer count, edge cases), Yen K-shortest (count, monotonicity, no loops)
- **M4**: Dijkstra min transfers, Yen K-min transfers, boundary cases
- **Extended**: `affected_area()` BFS, `count_components()` DFS

The additional `coursework_check.cpp` maps 53 checks directly to the 课设要求 scoring matrix (数据集建设 10pts, 图拓扑 10pts, 路径算法 15pts, 运营管理 15pts, 网络分析 5pts, 可视化等).

Acceptance criteria: ≥95% pass rate on the 41-test suite, 100% on core path-planning functionality.
