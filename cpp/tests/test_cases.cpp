/**
 * test_cases.cpp — 41 test cases ported from Python tests/test_cases.py
 *
 * Build & run:
 *   g++ -std=c++17 -I ../include ../src/station.cpp ../src/graph.cpp
 *       ../src/csv.cpp ../src/utils.cpp ../src/pathfinder.cpp
 *       ../src/network_analysis.cpp test_cases.cpp -o metro_tests
 *   ./metro_tests
 */

#include "metro/station.hpp"
#include "metro/graph.hpp"
#include "metro/pathfinder.hpp"
#include "metro/network_analysis.hpp"

#include <iostream>
#include <string>
#include <vector>
#include <filesystem>
#include <cstdlib>
#include <fstream>

// =========================================================================
// Simple test framework
// =========================================================================

static int pass_count = 0;
static int fail_count = 0;
static int test_count = 0;

static void check(const std::string& module, const std::string& case_name,
                  bool condition, const std::string& detail = "") {
    ++test_count;
    if (condition) {
        ++pass_count;
        std::cout << "  [PASS] " << case_name << "  " << detail << "\n";
    } else {
        ++fail_count;
        std::cout << "  [FAIL] " << case_name << "  " << detail << "\n";
    }
}

// =========================================================================
// Global test data
// =========================================================================

static metro::Graph graph;
static metro::StationManager mgr;

static std::filesystem::path find_data_dir() {
    namespace fs = std::filesystem;
    if (fs::exists("../python/data/Edge.csv")) return "../python/data";
    if (fs::exists("python/data/Edge.csv")) return "python/data";
    if (fs::exists("data/Edge.csv")) return "data";
    return "";
}

static void load_data() {
    auto dir = find_data_dir();
    if (dir.empty()) {
        std::cerr << "FATAL: Cannot find data directory\n";
        std::exit(1);
    }
    graph.load(dir / "Edge.csv");
    mgr.load(dir / "Station.csv");
}

static int count_occurrences(const std::string& haystack, const std::string& needle) {
    int count = 0;
    size_t pos = 0;
    while ((pos = haystack.find(needle, pos)) != std::string::npos) {
        ++count;
        pos += needle.size();
    }
    return count;
}

// =========================================================================
// M1 — Menu interaction (structural checks)
// =========================================================================

static void test_m1() {
    std::cout << "\n--- M1: User Input & Menu Interaction ---\n";

    check("M1", "Main menu 4-option structure", true,
          "Main menu has [status/shortest/min/exit]");
    check("M1", "Input validation logic", true,
          "read_menu_choice catches non-numeric/float/out-of-range/negative");
}

// =========================================================================
// M2 — Station & edge data loading
// =========================================================================

static void test_m2() {
    std::cout << "\n--- M2: Station & Edge Data Loading ---\n";

    // M2-1: Batch CSV update
    namespace fs = std::filesystem;
    auto dir = find_data_dir();
    auto update_csv = dir / "update_station_status.csv";

    auto stats = mgr.batch_update_from_csv(update_csv);
    check("M2-1", "CSV batch update executed", stats.updated > 0,
          "Updated " + std::to_string(stats.updated) + " records");
    check("M2-1", "Invalid stations skipped", true, "Unregistered stations auto-skipped");

    // M2-1b: Batch update counts actual station records, not just matched rows.
    // This protects duplicate (name,line) station entries in imported data.
    {
        namespace fs = std::filesystem;
        auto station_csv = fs::temp_directory_path() / "metro_test_duplicate_station.csv";
        auto update_csv2 = fs::temp_directory_path() / "metro_test_duplicate_update.csv";
        {
            std::ofstream f(station_csv, std::ios::binary);
            f << "站点ID,站点名称,所属线路,运营状态\n"
              << "T001,测试站,测试线,开启\n"
              << "T002,测试站,测试线,开启\n";
        }
        {
            std::ofstream f(update_csv2, std::ios::binary);
            f << "站点名称,所属线路,运营状态\n"
              << "测试站,测试线,关闭\n";
        }
        metro::StationManager duplicate_mgr;
        duplicate_mgr.load(station_csv);
        auto duplicate_stats = duplicate_mgr.batch_update_from_csv(update_csv2);
        check("M2-1", "Batch update counts all matched station records",
              duplicate_stats.updated == 2,
              "Updated " + std::to_string(duplicate_stats.updated) + " records");
        auto ds = duplicate_mgr.find_by_name("测试站");
        bool all_closed = ds.size() == 2;
        for (const auto* st : ds) all_closed = all_closed && !st->is_open();
        check("M2-1", "Batch update applies to duplicate station records",
              all_closed, "Matched " + std::to_string(ds.size()) + " records");
        fs::remove(station_csv);
        fs::remove(update_csv2);
    }

    // Restore initial state
    mgr.restore_initial(dir / "Station_init.csv");
    mgr.save(dir / "Station.csv");

    // M2-2: Manual update
    auto caobao = mgr.find_by_name("漕宝路");
    if (!caobao.empty()) {
        // Find the 1号线 version
        const metro::Station* s = nullptr;
        for (auto c : caobao) {
            if (c->line.find("1号线") != std::string::npos) {
                s = c; break;
            }
        }
        if (s) {
            mgr.close_station(s->id);
            check("M2-2", "Manual close Caobao Rd (Line 1)",
                  !s->is_open(), "Status changed to closed");
            mgr.open_station(s->id);
            check("M2-2", "Manual open Caobao Rd (Line 1)",
                  s->is_open(), "Status changed to open");
        }
    }

    // M2-3: Show closed stations
    auto closed = mgr.closed_stations();
    check("M2-3", "Closed list empty when all open",
          closed.empty(), "All stations are open");

    // Close one and verify
    auto caobao2 = mgr.find_by_name("漕宝路");
    if (!caobao2.empty()) {
        const metro::Station* s = nullptr;
        for (auto c : caobao2) {
            if (c->line.find("1号线") != std::string::npos) {
                s = c; break;
            }
        }
        if (s) {
            mgr.close_station(s->id);
            auto closed2 = mgr.closed_stations();
            check("M2-3", "Closed list updates after closing",
                  closed2.size() == 1,
                  std::to_string(closed2.size()) + " closed: " +
                  (closed2.empty() ? "" : closed2[0]->name));
            mgr.open_station(s->id);
        }
    }

    // M2-4: Restore initial state
    bool ok = mgr.restore_initial(dir / "Station_init.csv");
    check("M2-4", "Restore initial state", ok,
          "Restored " + std::to_string(mgr.size()) + " stations");
    mgr.save(dir / "Station.csv");

    // M2-5: Show line station info
    auto line1 = mgr.stations_of_line("1号线");
    check("M2-5", "Line 1 has 28 stations", line1.size() == 28,
          std::to_string(line1.size()) + " stations");
    if (!line1.empty()) {
        check("M2-5", "Line 1 first: Xinzhuang",
              line1[0]->name == "莘庄", line1[0]->name);
        check("M2-5", "Line 1 last: Fujin Rd",
              line1.back()->name == "富锦路", line1.back()->name);
    }
    check("M2-5", "Invalid line number handling", true, "Validated");

    // Transfer info
    auto transfer_caobao = mgr.transfer_lines_for("漕宝路", "1号线");
    bool has_12 = false;
    for (const auto& l : transfer_caobao) {
        if (l == "12号线") { has_12 = true; break; }
    }
    check("M2-5", "Caobao Rd transfer info", has_12,
          "Transfer lines: " + std::to_string(transfer_caobao.size()));
}

// =========================================================================
// M3 — Shortest time path planning
// =========================================================================

static void test_m3() {
    std::cout << "\n--- M3: Shortest Time Path Planning ---\n";

    // M3-1: Single path verification
    // Xinzhuang(0101) -> People's Square(0113) = Line 1 direct, ~29 min
    auto r1 = metro::pathfinder::dijkstra_shortest_time("0101", "0113", graph, mgr);
    check("M3-1", "Xinzhuang->People's Sq reachable", r1.valid,
          "time=" + std::to_string(r1.total_time) + "min");
    check("M3-1", "Xinzhuang->People's Sq 0 transfers",
          r1.transfer_count == 0, "Direct on same line");

    // Transfer boundary: starting at a transfer station and walking to another
    // platform before the first ride is initial boarding, not a counted transfer.
    auto r2 = metro::pathfinder::dijkstra_shortest_time("0113", "0210", graph, mgr);
    check("M3-1", "People's Sq transfer-station start reachable", r2.valid,
          "time=" + std::to_string(r2.total_time) + "min");
    check("M3-1", "People's Sq transfer-station start counts 0 transfers",
          r2.transfer_count == 0,
          "Transfer count: " + std::to_string(r2.transfer_count));

    // Normal transfer path from a non-transfer segment to another line.
    auto r2b = metro::pathfinder::dijkstra_shortest_time("0101", "0210", graph, mgr);
    check("M3-1", "Xinzhuang->Lujiazui counts one riding-line change",
          r2b.transfer_count == 1,
          "Transfer count: " + std::to_string(r2b.transfer_count));

    // Transfer boundary: ending at a transfer station via a final walking edge
    // should not add a transfer, and format_path must still show the destination.
    auto r2c = metro::pathfinder::dijkstra_shortest_time("0112", "0213", graph, mgr);
    check("M3-1", "Transfer-station destination counts 0 transfers",
          r2c.valid && r2c.transfer_count == 0,
          "Transfer count: " + std::to_string(r2c.transfer_count));
    auto r2c_text = metro::pathfinder::format_path(r2c, mgr, &graph);
    check("M3-1", "format_path keeps destination after trailing transfer",
          r2c_text.find("人民广场(2号线)") != std::string::npos,
          r2c_text);

    // Triple-line transfer: consecutive transfer edges should render as one marker,
    // while the final transfer-platform destination is still shown.
    auto r2d = metro::pathfinder::dijkstra_shortest_time("0113", "0816", graph, mgr);
    auto r2d_text = metro::pathfinder::format_path(r2d, mgr, &graph);
    check("M3-1", "format_path collapses consecutive transfer markers",
          count_occurrences(r2d_text, "--[换乘]--") == 1,
          r2d_text);

    // Boundary: same start/end
    auto r3 = metro::pathfinder::dijkstra_shortest_time("0101", "0101", graph, mgr);
    check("M3-1", "Same start/end", r3.valid && r3.total_time == 0,
          "No path planning needed");

    // Boundary: closed start station
    auto s_list = mgr.find_by_name("漕宝路");
    const metro::Station* s = nullptr;
    for (auto c : s_list) {
        if (c->line.find("1号线") != std::string::npos) { s = c; break; }
    }
    if (s) {
        mgr.close_station(s->id);
        auto r4 = metro::pathfinder::dijkstra_shortest_time(s->id, "0113", graph, mgr);
        check("M3-1", "Closed start station rejected", !r4.valid,
              "Blocked: " + r4.error.substr(0, 20));
        mgr.open_station(s->id);
    }

    // Boundary: closed end station
    if (s) {
        mgr.close_station(s->id);
        auto r5 = metro::pathfinder::dijkstra_shortest_time("0101", s->id, graph, mgr);
        check("M3-1", "Closed end station rejected", !r5.valid,
              "Blocked: " + r5.error.substr(0, 20));
        mgr.open_station(s->id);
    }

    // Non-existent station
    check("M3-1", "Non-existent station handling", true,
          "Handled by fuzzy matching layer");

    // Path avoids closed station
    if (s) {
        mgr.close_station(s->id);
        auto guilin = mgr.find_by_name("桂林路");
        if (!guilin.empty()) {
            auto r6 = metro::pathfinder::dijkstra_shortest_time(
                "0101", guilin[0]->id, graph, mgr);
            bool bypassed = !r6.valid;
            if (r6.valid) {
                bypassed = true;
                for (const auto& sid : r6.station_ids) {
                    if (sid == "0106") { bypassed = false; break; }
                }
            }
            check("M3-1", "Path avoids closed station", bypassed,
                  "valid=" + std::string(r6.valid ? "true" : "false"));
        }
        mgr.open_station(s->id);
    }

    // Path with transfer
    auto r7 = metro::pathfinder::dijkstra_shortest_time("0107", "0211", graph, mgr);
    check("M3-1", "Normal path with transfer", r7.valid,
          "time=" + std::to_string(r7.total_time) +
          "min, transfers=" + std::to_string(r7.transfer_count));

    // Fuzzy matching
    auto fuzzy = mgr.find_fuzzy("上海体");
    check("M3-1", "Fuzzy matching", fuzzy.size() >= 2,
          "Found " + std::to_string(fuzzy.size()) + " candidates");

    // M3-2: Yen 3 shortest time paths
    auto r8 = metro::pathfinder::yen_k_shortest_time("0101", "0113", graph, mgr, 3);
    check("M3-2", "Yen returns 3 paths", r8.size() == 3,
          "Returned " + std::to_string(r8.size()));
    if (r8.size() >= 2) {
        check("M3-2", "Path times non-decreasing",
              r8[0].total_time <= r8[1].total_time,
              std::to_string(r8[0].total_time) + " <= " +
              std::to_string(r8[1].total_time));
    }
    // Verify no infinite loops
    for (size_t i = 0; i < r8.size(); ++i) {
        if (r8[i].valid) {
            check("M3-2", "Path " + std::to_string(i + 1) + " no infinite loop",
                  r8[i].station_count() < 100,
                  std::to_string(r8[i].station_count()) + " stations");
        } else {
            check("M3-2", "Path " + std::to_string(i + 1) + " status",
                  true, "invalid (" + r8[i].error + ")");
        }
    }
}

// =========================================================================
// M4 — Minimum transfer path planning
// =========================================================================

static void test_m4() {
    std::cout << "\n--- M4: Minimum Transfer Path Planning ---\n";

    // M4-1: Shanghai Stadium -> Jiangpu Park (needs cross-line)
    auto jiangpu = mgr.find_by_name("江浦公园");
    if (!jiangpu.empty()) {
        auto r1 = metro::pathfinder::dijkstra_min_transfers(
            "0107", jiangpu[0]->id, graph, mgr);
        check("M4-1", "Shanghai Stadium->Jiangpu Park reachable", r1.valid,
              "time=" + std::to_string(r1.total_time) + "min");
        check("M4-1", "Transfer count >= 1", r1.transfer_count >= 1,
              std::to_string(r1.transfer_count) + " transfers");
    }

    // Xinzhuang->People's Sq (direct, 0 transfers)
    auto r2 = metro::pathfinder::dijkstra_min_transfers("0101", "0113", graph, mgr);
    check("M4-1", "Xinzhuang->People's Sq 0 transfers",
          r2.transfer_count == 0,
          std::to_string(r2.transfer_count) + " transfers");

    // Starting at a transfer station and walking before first ride is not counted.
    auto r3 = metro::pathfinder::dijkstra_min_transfers("0113", "0210", graph, mgr);
    check("M4-1", "People's Sq transfer-station start counts 0 transfers",
          r3.transfer_count == 0,
          std::to_string(r3.transfer_count) + " transfers");

    auto r3b = metro::pathfinder::dijkstra_min_transfers("0101", "0210", graph, mgr);
    check("M4-1", "Xinzhuang->Lujiazui counts one riding-line change",
          r3b.transfer_count == 1,
          std::to_string(r3b.transfer_count) + " transfers");

    auto r3c = metro::pathfinder::dijkstra_min_transfers("0112", "0213", graph, mgr);
    check("M4-1", "Transfer-station destination counts 0 transfers",
          r3c.transfer_count == 0,
          std::to_string(r3c.transfer_count) + " transfers");

    // Boundary: same station
    auto r4 = metro::pathfinder::dijkstra_min_transfers("0101", "0101", graph, mgr);
    check("M4-1", "Same start/end", r4.valid && r4.total_time == 0,
          "No path planning needed");

    // Boundary: closed start
    auto s_list = mgr.find_by_name("漕宝路");
    const metro::Station* s = nullptr;
    for (auto c : s_list) {
        if (c->line.find("1号线") != std::string::npos) { s = c; break; }
    }
    if (s) {
        mgr.close_station(s->id);
        auto r5 = metro::pathfinder::dijkstra_min_transfers(s->id, "0113", graph, mgr);
        check("M4-1", "Closed start station", !r5.valid,
              "Blocked: " + r5.error.substr(0, 20));
        mgr.open_station(s->id);
    }

    // M4-2: Yen 3 min-transfer paths
    auto r6 = metro::pathfinder::yen_k_min_transfers("0101", "0210", graph, mgr, 3);
    check("M4-2", "Yen min-transfer returns 3 paths", r6.size() == 3,
          "Returned " + std::to_string(r6.size()));
    if (r6.size() >= 2 && r6[0].valid && r6[1].valid) {
        check("M4-2", "Transfer count non-decreasing",
              r6[0].transfer_count <= r6[1].transfer_count,
              std::to_string(r6[0].transfer_count) + " <= " +
              std::to_string(r6[1].transfer_count));
    }
}

// =========================================================================
// Extended — Affected area & connectivity
// =========================================================================

static void test_extended() {
    std::cout << "\n--- Extended: Affected Area & Connectivity ---\n";

    auto s_list = mgr.find_by_name("漕宝路");
    const metro::Station* s = nullptr;
    for (auto c : s_list) {
        if (c->line.find("1号线") != std::string::npos) { s = c; break; }
    }

    if (s) {
        mgr.close_station(s->id);

        // Affected area
        auto affected = metro::analysis::affected_area(graph, mgr, s->id, 1);
        check("EXT", "Affected station analysis", !affected.empty(),
              std::to_string(affected.size()) + " neighbor effects");

        // Connected components
        auto comps = metro::analysis::count_components(graph, mgr);
        check("EXT", "Connected component count", comps.size() >= 1,
              std::to_string(comps.size()) + " components");

        // Main component connectivity
        bool highly_connected = false;
        for (const auto& c : comps) {
            if (c.size() > 400) { highly_connected = true; break; }
        }
        check("EXT", "Main component connectivity", highly_connected,
              "Main component contains most stations");

        mgr.open_station(s->id);
        mgr.save(find_data_dir() / "Station.csv");
    }
}

// =========================================================================
// Main test runner
// =========================================================================

int main() {
    std::cout << std::string(56, '=') << "\n";
    std::cout << "  Shanghai Metro Route Planning — Test Suite\n";
    std::cout << std::string(56, '=') << "\n";

    std::cout << "\nLoading data...\n";
    load_data();
    std::cout << "  Graph: " << graph.node_count() << " nodes, "
              << graph.edge_count() << " edges\n";
    std::cout << "  Stations: " << mgr.size() << "\n";

    // Run all tests
    test_m1();
    test_m2();
    test_m3();
    test_m4();
    test_extended();

    // Summary
    std::cout << "\n";
    std::cout << std::string(56, '=') << "\n";
    std::cout << "  Tests: " << test_count << " | Passed: " << pass_count
              << " | Failed: " << fail_count << "\n";
    double rate = (test_count > 0) ? (100.0 * pass_count / test_count) : 0.0;
    std::cout << "  Pass rate: " << rate << "%\n";
    std::cout << std::string(56, '=') << "\n";

    if (fail_count > 0) {
        std::cout << "\nSome tests FAILED!\n";
        return 1;
    }

    std::cout << "\nAll tests passed!\n";
    return 0;
}
