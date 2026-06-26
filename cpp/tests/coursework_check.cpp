/**
 * coursework_check.cpp — Verify all course design requirements (课设要求)
 * Mapped against 实验指导书 and Gemini_Report.md criteria.
 */
#include "metro/station.hpp"
#include "metro/graph.hpp"
#include "metro/pathfinder.hpp"
#include "metro/network_analysis.hpp"

#include <iostream>
#include <iomanip>
#include <string>
#include <set>
#include <vector>
#include <algorithm>

using namespace metro;

static int total = 0, passed = 0;

static void check(const std::string& req, bool cond, const std::string& note = "") {
    ++total;
    if (cond) ++passed;
    std::cout << "  [" << (cond ? "PASS" : "FAIL") << "] " << req;
    if (!note.empty()) std::cout << "  -- " << note;
    std::cout << "\n";
}

int main() {
    Graph graph;
    StationManager mgr;
    graph.load("../python/data/Edge.csv");
    mgr.load("../python/data/Station.csv");

    std::cout << "==============================================\n";
    std::cout << "  课程设计要求 Feature Verification\n";
    std::cout << "==============================================\n";
    std::cout << "Data: " << mgr.size() << " stations, "
              << graph.edge_count() << " edges\n\n";

    // ============================================================
    // 1. 数据集建设 (CSV Data — 10 pts)
    // ============================================================
    std::cout << "### 1. 数据集建设 (10 pts) ###\n";
    check("Station.csv: >= 500 stations", mgr.size() >= 500,
          std::to_string(mgr.size()) + " stations");
    check("Station.csv: >= 525 target (diff < 10)",
          std::abs((int)mgr.size() - 525) <= 10);
    check("Edge.csv: >= 1000 edges", graph.edge_count() >= 1000,
          std::to_string(graph.edge_count()) + " edges");
    check("Edge.csv: >= 1226 target (diff < 100)",
          std::abs((int)graph.edge_count() - 1226) <= 100);
    check("Station ID format: LLNN (4 chars)", [&]() {
        auto* s = mgr.get("0101");
        return s && s->id.size() == 4 && s->id >= "0101";
    }());
    check("Station fields present: name, line, status", [&]() {
        auto* s = mgr.get("0101");
        return s && !s->name.empty() && !s->line.empty()
               && !s->status.empty() && s->is_open();
    }());
    check("Status default is '开启' (open)", mgr.closed_stations().empty());

    // ============================================================
    // 2. 图拓扑结构构建 (Graph topology — 10 pts)
    // ============================================================
    std::cout << "\n### 2. 图拓扑结构构建 (10 pts) ###\n";
    {
        auto renmin = mgr.find_by_name("人民广场");
        check("Transfer station: multiple nodes (人民广场 >= 2)",
              renmin.size() >= 2, std::to_string(renmin.size()) + " nodes");
        check("Transfer lines differ (人民广场: L1, L2, L8)", [&]() {
            std::set<std::string> lines;
            for (auto* s : renmin) lines.insert(s->line);
            return lines.size() >= 2;
        }());
        // Check transfer edge
        bool has_xfer_edge = false;
        if (renmin.size() >= 2) {
            auto* e = graph.get_edge(renmin[0]->id, renmin[1]->id);
            has_xfer_edge = (e && e->is_transfer() && e->time == 5);
        }
        check("Transfer edge: line='换乘', time=5", has_xfer_edge);
    }
    check("Directed edges: both directions stored",
          graph.has_edge("0101", "0102") && graph.has_edge("0102", "0101"));
    check("Edge fields: from_id, to_id, line, direction, time", [&]() {
        auto* e = graph.get_edge("0101", "0102");
        return e && !e->from_id.empty() && !e->to_id.empty()
               && !e->line.empty() && e->time > 0;
    }());
    check("Node count matches station count",
          graph.node_count() == mgr.size());

    // ============================================================
    // 3. 路径规划算法 (15 pts)
    // ============================================================
    std::cout << "\n### 3. 路径规划算法 (15 pts) ###\n";
    {
        auto r = pathfinder::dijkstra_shortest_time("0101", "0113", graph, mgr);
        check("Dijkstra time: 莘庄->人民广场 reachable",
              r.valid && r.total_time == 29 && r.transfer_count == 0,
              "time=" + std::to_string(r.total_time));
    }
    {
        auto r = pathfinder::dijkstra_shortest_time("0113", "0210", graph, mgr);
        check("Dijkstra time: 人民广场(L1)->江苏路(L2) 1 transfer",
              r.valid && r.transfer_count == 1 && r.total_time == 12,
              "time=" + std::to_string(r.total_time)
              + " xfer=" + std::to_string(r.transfer_count));
    }
    {
        auto r = pathfinder::dijkstra_shortest_time("0101", "0101", graph, mgr);
        check("Dijkstra time: same start/end = 0",
              r.valid && r.total_time == 0 && r.station_count() == 1);
    }
    {
        auto r = pathfinder::dijkstra_min_transfers("0101", "0113", graph, mgr);
        check("Min transfers: 莘庄->人民广场 0 transfers",
              r.valid && r.transfer_count == 0,
              "time=" + std::to_string(r.total_time));
    }
    {
        auto r = pathfinder::dijkstra_min_transfers("0113", "0210", graph, mgr);
        check("Min transfers: 人民广场->江苏路 1 transfer",
              r.valid && r.transfer_count == 1,
              "time=" + std::to_string(r.total_time));
    }
    {
        auto rs = pathfinder::yen_k_shortest_time("0101", "0113", graph, mgr, 3);
        check("Yen KSP time: returns 3 paths", rs.size() == 3,
              std::to_string(rs.size()) + " paths");
        bool monotonic = true, all_valid = true;
        for (size_t i = 0; i < rs.size(); ++i) {
            if (!rs[i].valid) all_valid = false;
            if (i > 0 && rs[i].total_time < rs[i-1].total_time) monotonic = false;
        }
        check("Yen KSP time: all paths valid", all_valid);
        check("Yen KSP time: times non-decreasing", monotonic);
        check("Yen KSP time: paths distinct",
              rs[0].station_ids != rs[1].station_ids);
    }
    {
        auto rs = pathfinder::yen_k_min_transfers("0101", "0210", graph, mgr, 3);
        check("Yen KSP transfer: returns 3 paths", rs.size() == 3);
        bool all_valid = true;
        for (auto& r : rs) if (!r.valid) all_valid = false;
        check("Yen KSP transfer: all valid", all_valid);
    }

    // ============================================================
    // 4. 运营管理与状态维护 (15 pts)
    // ============================================================
    std::cout << "\n### 4. 运营管理与状态维护 (15 pts) ###\n";
    {
        auto s = mgr.find_by_name("漕宝路");
        const Station* caobao = nullptr;
        for (auto x : s) if (x->line == "1号线") { caobao = x; break; }

        if (caobao) {
            check("close_station() works",
                  mgr.close_station(caobao->id));
            check("closed_stations() returns closed",
                  mgr.closed_stations().size() == 1);
            check("open_station() restores",
                  mgr.open_station(caobao->id)
                  && mgr.closed_stations().empty());
            // Closed start rejected
            mgr.close_station(caobao->id);
            auto r4 = pathfinder::dijkstra_shortest_time(
                caobao->id, "0113", graph, mgr);
            check("Closed start rejected (time)",
                  !r4.valid && r4.error.find("起点") != std::string::npos);
            auto r5 = pathfinder::dijkstra_shortest_time(
                "0101", caobao->id, graph, mgr);
            check("Closed end rejected (time)",
                  !r5.valid && r5.error.find("终点") != std::string::npos);
            // Path avoids closed station
            auto guilin = mgr.find_by_name("桂林路");
            if (!guilin.empty()) {
                auto r6 = pathfinder::dijkstra_shortest_time(
                    "0101", guilin[0]->id, graph, mgr);
                bool avoids = r6.valid;
                for (auto& id : r6.station_ids) {
                    if (id == caobao->id) { avoids = false; break; }
                }
                check("Path avoids closed station (漕宝路 bypassed)", avoids);
            }
            mgr.open_station(caobao->id);
        }
    }
    {
        auto stats = mgr.batch_update_from_csv(
            "../python/data/update_station_status.csv");
        check("batch_update_from_csv: records updated",
              stats.updated > 0, std::to_string(stats.updated));
        mgr.restore_initial("../python/data/Station_init.csv");
    }
    check("restore_initial(): restores Station_init.csv",
          mgr.restore_initial("../python/data/Station_init.csv"));
    mgr.save("../python/data/Station.csv");

    // ============================================================
    // 5. 网络分析功能 (5 pts)
    // ============================================================
    std::cout << "\n### 5. 网络分析功能 (5 pts) ###\n";
    {
        auto caobao = mgr.find_by_name("漕宝路");
        const Station* s = nullptr;
        for (auto x : caobao) if (x->line == "1号线") { s = x; break; }
        if (s) {
            mgr.close_station(s->id);
            auto affected = analysis::affected_area(graph, mgr, s->id, 1);
            check("BFS affected_area: neighbors found",
                  !affected.empty(),
                  std::to_string(affected.size()) + " stations");
            auto affected2 = analysis::affected_area(graph, mgr, s->id, 2);
            check("BFS affected_area: depth=2 >= depth=1",
                  affected2.size() >= affected.size());

            auto comps = analysis::count_components(graph, mgr);
            check("DFS count_components: at least 1 component",
                  !comps.empty());
            check("DFS: largest component > 500 (network intact)",
                  comps[0].size() > 500,
                  "largest=" + std::to_string(comps[0].size()));

            mgr.open_station(s->id);
        }
    }

    // ============================================================
    // 6. 4号线内外圈标记
    // ============================================================
    std::cout << "\n### 6. 4号线 inner/outer ring ###\n";
    {
        auto it = mgr.line_index().find("4号线");
        if (it != mgr.line_index().end() && it->second.size() >= 4) {
            auto& ids = it->second;
            std::string src = ids[0];
            std::string dst = ids[ids.size() / 2];
            auto r = pathfinder::dijkstra_shortest_time(src, dst, graph, mgr);
            check("Line 4 direction markers populated",
                  r.valid && !r.line4_dirs.empty(),
                  std::to_string(r.line4_dirs.size()) + " markers");
            bool has_inner = false, has_outer = false;
            for (auto& [id, dir] : r.line4_dirs) {
                if (dir == "内圈") has_inner = true;
                if (dir == "外圈") has_outer = true;
            }
            check("Line 4 inner (内圈) or outer (外圈) present",
                  has_inner || has_outer);
        }
    }

    // ============================================================
    // 7. 模糊匹配 (Fuzzy search)
    // ============================================================
    std::cout << "\n### 7. 模糊匹配 (Fuzzy matching) ###\n";
    check("find_fuzzy('上海') >= 5 candidates",
          mgr.find_fuzzy("上海").size() >= 5,
          std::to_string(mgr.find_fuzzy("上海").size()));
    check("find_fuzzy('上海体') >= 2 candidates",
          mgr.find_fuzzy("上海体").size() >= 2);
    check("find_by_name exact match", [&]() {
        auto r = mgr.find_by_name("莘庄");
        return !r.empty() && r[0]->name == "莘庄";
    }());
    check("transfer_lines_for: 莘庄 has transfer to 5号线", [&]() {
        auto lines = mgr.transfer_lines_for("莘庄", "1号线");
        return std::find(lines.begin(), lines.end(), "5号线") != lines.end();
    }());

    // ============================================================
    // 8. 线路站点信息 (Line info — M2-5)
    // ============================================================
    std::cout << "\n### 8. 线路站点信息 (M2-5) ###\n";
    {
        auto line1 = mgr.stations_of_line("1号线");
        check("Line 1: 28 stations", line1.size() == 28);
        check("Line 1: first = 莘庄 (sorted by ID)",
              line1[0]->name == "莘庄");
        check("Line 1: last = 富锦路 (sorted by ID)",
              line1.back()->name == "富锦路");
    }
    {
        auto xfer = mgr.transfer_lines_for("漕宝路", "1号线");
        check("漕宝路: transfer to 12号线",
              std::find(xfer.begin(), xfer.end(), "12号线") != xfer.end());
    }

    // ============================================================
    // 9. 路径可视化 (Path visualization in format_path)
    // ============================================================
    std::cout << "\n### 9. 路径可视化 (format_path) ###\n";
    {
        auto r = pathfinder::dijkstra_shortest_time("0113", "0210", graph, mgr);
        std::string s = pathfinder::format_path(r, mgr, &graph);
        check("format_path contains transfer marker [换乘]",
              s.find("[换乘]") != std::string::npos);
        check("format_path contains total time (分钟)",
              s.find("分钟") != std::string::npos);
        check("format_path contains station count (途经)",
              s.find("途经") != std::string::npos);
    }

    // ============================================================
    // 10. 压力 / 边界测试 (Stress / boundary)
    // ============================================================
    std::cout << "\n### 10. 边界测试 (Edge cases) ###\n";
    check("Non-existent station: get('9999') = nullptr",
          mgr.get("9999") == nullptr);
    check("Empty keyword: find_fuzzy('') returns some results",
          mgr.find_fuzzy("").size() > 0);
    // Path with same start/end on min_transfer
    auto r0 = pathfinder::dijkstra_min_transfers("0101", "0101", graph, mgr);
    check("dijkstra_min_transfers same start/end",
          r0.valid && r0.total_time == 0 && r0.transfer_count == 0);
    // Path to station on same line (0 transfers expected)
    auto r1 = pathfinder::dijkstra_min_transfers("0101", "0128", graph, mgr);
    check("min_transfers on same line (0101->0128) = 0 transfers",
          r1.valid && r1.transfer_count == 0);

    // ============================================================
    // Summary
    // ============================================================
    std::cout << "\n==============================================\n";
    std::cout << "  Total: " << total << " | Passed: " << passed
              << " | Failed: " << (total - passed) << "\n";
    std::cout << "  Pass rate: " << std::fixed << std::setprecision(1)
              << (100.0 * passed / total) << "%\n";
    std::cout << "==============================================\n";

    return (total == passed) ? 0 : 1;
}
