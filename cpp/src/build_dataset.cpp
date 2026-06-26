#include "metro/build_dataset.hpp"
#include "metro/csv.hpp"

#include <iostream>
#include <algorithm>
#include <map>
#include <set>
#include <sstream>
#include <iomanip>

namespace metro::build {

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const std::vector<int> ALL_LINES = []() {
    std::vector<int> v;
    for (int i = 1; i <= 18; ++i) v.push_back(i);
    v.push_back(41);
    v.push_back(51);
    return v;
}();

const std::unordered_map<int, std::string> LINE_NAMES = {
    {1, "1号线"}, {2, "2号线"}, {3, "3号线"}, {4, "4号线"},
    {5, "5号线"}, {6, "6号线"}, {7, "7号线"}, {8, "8号线"},
    {9, "9号线"}, {10, "10号线"}, {11, "11号线"}, {12, "12号线"},
    {13, "13号线"}, {14, "14号线"}, {15, "15号线"}, {16, "16号线"},
    {17, "17号线"}, {18, "18号线"}, {41, "浦江线"}, {51, "市域机场线"},
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

std::string line_str(int line_num) {
    auto it = LINE_NAMES.find(line_num);
    return (it != LINE_NAMES.end()) ? it->second : (std::to_string(line_num) + "号线");
}

std::string clean_name(const std::string& name) {
    // Strip leading/trailing whitespace
    auto start = name.find_first_not_of(" \t\r\n");
    if (start == std::string::npos) return "";
    auto end = name.find_last_not_of(" \t\r\n");
    return name.substr(start, end - start + 1);
}

// ---------------------------------------------------------------------------
// Station record (internal, map-based like Python)
// ---------------------------------------------------------------------------

using StationDict = std::unordered_map<std::string, std::string>;
using EdgeDict = std::unordered_map<std::string, std::string>;

// ---------------------------------------------------------------------------
// 1. Build stations from line-XX.csv files
// ---------------------------------------------------------------------------

static std::pair<std::vector<StationDict>, std::map<std::pair<int, std::string>, std::string>>
build_stations(const std::filesystem::path& raw_dir) {
    std::vector<StationDict> stations;
    // name_index: (line_num, station_name) → station_id
    std::map<std::pair<int, std::string>, std::string> name_index;

    for (int line_num : ALL_LINES) {
        std::ostringstream fname;
        fname << "line-" << std::setw(2) << std::setfill('0') << line_num << ".csv";
        auto path = raw_dir / fname.str();

        if (!std::filesystem::exists(path)) {
            std::cerr << "[WARN] Missing file: " << path.string() << "\n";
            continue;
        }

        csv::Reader reader(path);
        std::set<std::string> seen_names;
        int seq = 1;

        for (const auto& row : reader.read_all()) {
            auto it = row.find("station_name");
            if (it == row.end()) continue;
            std::string name = clean_name(it->second);

            if (seen_names.count(name)) continue;
            seen_names.insert(name);

            // Station ID: LLNN format
            std::ostringstream sid;
            sid << std::setw(2) << std::setfill('0') << line_num
                << std::setw(2) << std::setfill('0') << seq;

            StationDict s;
            s["station_id"]   = sid.str();
            s["station_name"] = name;
            s["line"]         = line_str(line_num);
            s["line_num"]     = std::to_string(line_num);
            s["status"]       = "开启";
            stations.push_back(s);

            name_index[{line_num, name}] = sid.str();
            ++seq;
        }
    }

    return {stations, name_index};
}

// ---------------------------------------------------------------------------
// 2. Build interval edges from fltime-XX.csv files
// ---------------------------------------------------------------------------

static std::vector<EdgeDict> build_interval_edges(
    const std::filesystem::path& raw_dir,
    const std::map<std::pair<int, std::string>, std::string>& name_index)
{
    std::vector<EdgeDict> edges;
    std::vector<std::string> missing;

    for (int line_num : ALL_LINES) {
        std::ostringstream fname;
        fname << "fltime-" << std::setw(2) << std::setfill('0') << line_num << ".csv";
        auto path = raw_dir / fname.str();

        if (!std::filesystem::exists(path)) {
            std::cerr << "[WARN] Missing file: " << path.string() << "\n";
            continue;
        }

        csv::Reader reader(path);
        for (const auto& row : reader.read_all()) {
            auto from_it = row.find("from_station");
            auto to_it = row.find("to_station");
            auto dir_it = row.find("direction");
            auto time_it = row.find("interval_min");
            if (from_it == row.end() || to_it == row.end() || time_it == row.end()) continue;

            std::string from_name = clean_name(from_it->second);
            std::string to_name = clean_name(to_it->second);
            std::string direction = dir_it != row.end() ? dir_it->second : "";
            int time_min = std::stoi(time_it->second);

            auto f_it = name_index.find({line_num, from_name});
            auto t_it = name_index.find({line_num, to_name});

            if (f_it == name_index.end() || t_it == name_index.end()) {
                missing.push_back("L" + std::to_string(line_num) + " " +
                                  from_name + " -> " + to_name);
                continue;
            }

            EdgeDict e;
            e["from_id"]  = f_it->second;
            e["to_id"]    = t_it->second;
            e["line"]     = line_str(line_num);
            e["direction"] = direction;
            e["time"]     = std::to_string(time_min);
            edges.push_back(e);
        }
    }

    if (!missing.empty()) {
        std::cerr << "[WARN] Lookup failures: " << missing.size() << " edges\n";
        for (size_t i = 0; i < missing.size() && i < 5; ++i) {
            std::cerr << "    " << missing[i] << "\n";
        }
        if (missing.size() > 5) {
            std::cerr << "    ... and " << (missing.size() - 5) << " more\n";
        }
    }

    return edges;
}

// ---------------------------------------------------------------------------
// 2.5 Fill missing adjacent edges
// ---------------------------------------------------------------------------

static std::vector<EdgeDict> fill_missing_adjacent_edges(
    const std::vector<StationDict>& stations,
    const std::vector<EdgeDict>& edges)
{
    // Build line-ordered station lists
    std::map<int, std::vector<StationDict>> line_order;
    for (const auto& s : stations) {
        int ln = std::stoi(s.at("line_num"));
        line_order[ln].push_back(s);
    }
    for (auto& [ln, stns] : line_order) {
        std::sort(stns.begin(), stns.end(),
                  [](const auto& a, const auto& b) {
                      return a.at("station_id") < b.at("station_id");
                  });
    }

    // Existing edges set
    std::set<std::pair<std::string, std::string>> existing;
    for (const auto& e : edges) {
        existing.insert(std::make_pair(e.at("from_id"), e.at("to_id")));
    }

    // Reverse edge time lookup
    std::map<std::pair<std::string, std::string>, int> rev_time;
    for (const auto& e : edges) {
        rev_time[{e.at("to_id"), e.at("from_id")}] = std::stoi(e.at("time"));
    }

    std::vector<EdgeDict> filled(edges.begin(), edges.end());
    int added = 0;

    for (const auto& [ln, stns] : line_order) {
        std::string line_name = stns[0].at("line");

        for (size_t i = 0; i + 1 < stns.size(); ++i) {
            const auto& a = stns[i].at("station_id");
            const auto& b = stns[i + 1].at("station_id");

            // Try using reverse edge time
            const std::pair<std::string, std::string> pairs1[] = {
                std::make_pair(a, b), std::make_pair(b, a)};
            for (const auto& [fwd, rev] : pairs1) {
                if (existing.count(std::make_pair(fwd, rev))) continue;

                auto rit = rev_time.find({fwd, rev});
                if (rit != rev_time.end()) {
                    EdgeDict e;
                    e["from_id"]  = fwd;
                    e["to_id"]    = rev;
                    e["line"]     = line_name;
                    e["direction"] = "";
                    e["time"]     = std::to_string(rit->second);
                    filled.push_back(e);
                    existing.insert(std::make_pair(fwd, rev));
                    ++added;
                }
            }

            // If both directions still missing (Y-branch forks), use default 3 min
            if (!existing.count(std::make_pair(a, b)) && !existing.count(std::make_pair(b, a))) {
                const std::pair<std::string, std::string> pairs2[] = {
                    std::make_pair(a, b), std::make_pair(b, a)};
                for (const auto& [fwd, rev] : pairs2) {
                    EdgeDict e;
                    e["from_id"]  = fwd;
                    e["to_id"]    = rev;
                    e["line"]     = line_name;
                    e["direction"] = "";
                    e["time"]     = "3";
                    filled.push_back(e);
                    existing.insert(std::make_pair(fwd, rev));
                    ++added;
                }
            }
        }
    }

    if (added) {
        std::cout << "[补全] Added " << added << " missing adjacent edges\n";
    }
    return filled;
}

// ---------------------------------------------------------------------------
// 2.6 Remove loop closure pseudo-edges
// ---------------------------------------------------------------------------

static std::vector<EdgeDict> remove_loop_closure_edges(
    const std::vector<EdgeDict>& edges,
    const std::vector<StationDict>& stations)
{
    // Build ID → (name, line) map
    std::unordered_map<std::string, std::pair<std::string, std::string>> info;
    for (const auto& s : stations) {
        info[s.at("station_id")] = {s.at("station_name"), s.at("line")};
    }

    int removed = 0;
    std::vector<EdgeDict> filtered;

    for (const auto& e : edges) {
        if (e.at("line") == "换乘") {
            filtered.push_back(e);
            continue;
        }

        auto f_it = info.find(e.at("from_id"));
        auto t_it = info.find(e.at("to_id"));

        if (f_it != info.end() && t_it != info.end()) {
            // Same name + same line → ring closure pseudo-edge
            if (f_it->second.first == t_it->second.first &&
                f_it->second.second == t_it->second.second) {
                ++removed;
                continue;
            }
        }
        filtered.push_back(e);
    }

    if (removed) {
        std::cout << "[过滤] Removed " << removed << " loop closure pseudo-edges\n";
    }
    return filtered;
}

// ---------------------------------------------------------------------------
// 3. Build transfer edges
// ---------------------------------------------------------------------------

static std::vector<EdgeDict> build_transfer_edges(const std::vector<StationDict>& stations) {
    // name → list of station IDs
    std::unordered_map<std::string, std::vector<std::string>> name_to_ids;
    for (const auto& s : stations) {
        name_to_ids[s.at("station_name")].push_back(s.at("station_id"));
    }

    std::vector<EdgeDict> edges;
    for (const auto& [name, ids] : name_to_ids) {
        if (ids.size() < 2) continue;

        // All ordered pairs (bidirectional)
        for (const auto& i : ids) {
            for (const auto& j : ids) {
                if (i == j) continue;
                EdgeDict e;
                e["from_id"]  = i;
                e["to_id"]    = j;
                e["line"]     = "换乘";
                e["direction"] = "";
                e["time"]     = std::to_string(TRANSFER_TIME);
                edges.push_back(e);
            }
        }
    }

    return edges;
}

// ---------------------------------------------------------------------------
// 4. Write CSV outputs
// ---------------------------------------------------------------------------

static void write_station_csv(const std::vector<StationDict>& stations,
                              const std::filesystem::path& path) {
    csv::Writer writer(path, true);
    writer.write_header({"站点ID", "站点名称", "所属线路", "运营状态"});

    for (const auto& s : stations) {
        writer.write_row({
            s.at("station_id"),
            s.at("station_name"),
            s.at("line"),
            s.at("status")
        });
    }
}

static void write_edge_csv(const std::vector<EdgeDict>& edges,
                           const std::filesystem::path& path) {
    csv::Writer writer(path, true);
    writer.write_header({"起点站ID", "终点站ID", "线路", "运行方向", "通行时间"});

    for (const auto& e : edges) {
        writer.write_row({
            e.at("from_id"),
            e.at("to_id"),
            e.at("line"),
            e.at("direction"),
            e.at("time")
        });
    }
}

static void write_update_status_example(const std::filesystem::path& path) {
    csv::Writer writer(path, true);
    writer.write_header({"站点名称", "所属线路", "运营状态"});
    writer.write_row({"漕宝路", "1号线", "关闭"});
    writer.write_row({"陆家嘴", "2号线", "关闭"});
    writer.write_row({"萧塘", "5号线", "开启"});
}

// ---------------------------------------------------------------------------
// Main pipeline
// ---------------------------------------------------------------------------

bool build_all(const std::filesystem::path& raw_dir,
               const std::filesystem::path& out_dir) {
    try {
        std::filesystem::create_directories(out_dir);

        std::cout << std::string(56, '=') << "\n";
        std::cout << " build_dataset — Build canonical dataset\n";
        std::cout << std::string(56, '=') << "\n";

        // 1. Build stations
        auto [stations, name_index] = build_stations(raw_dir);
        std::cout << "\n[1/3] Stations built: " << stations.size() << " stations\n";

        // Per-line stats
        std::map<int, int> by_line;
        for (const auto& s : stations) {
            by_line[std::stoi(s.at("line_num"))]++;
        }
        for (int ln : ALL_LINES) {
            auto it = by_line.find(ln);
            int count = (it != by_line.end()) ? it->second : 0;
            std::cout << "      " << line_str(ln) << "(L" << ln << "): "
                      << count << " stations\n";
        }

        // Transfer station count
        std::map<std::string, int> name_count;
        for (const auto& s : stations) {
            name_count[s.at("station_name")]++;
        }
        int transfer_count = 0;
        for (const auto& [name, cnt] : name_count) {
            if (cnt >= 2) ++transfer_count;
        }
        std::cout << "\n      Transfer stations (cross-line): " << transfer_count << "\n";

        // 2. Build edges
        auto interval_edges = build_interval_edges(raw_dir, name_index);
        std::cout << "\n[2/3] Interval edges built: " << interval_edges.size() << "\n";

        auto filled_edges = fill_missing_adjacent_edges(stations, interval_edges);
        std::cout << "      After filling: " << filled_edges.size() << " interval edges\n";

        filled_edges = remove_loop_closure_edges(filled_edges, stations);

        auto transfer_edges = build_transfer_edges(stations);
        std::cout << "      Transfer edges built: " << transfer_edges.size() << "\n";

        std::vector<EdgeDict> all_edges = filled_edges;
        all_edges.insert(all_edges.end(), transfer_edges.begin(), transfer_edges.end());
        std::cout << "      Total edges: " << all_edges.size() << "\n";

        // 3. Write output
        auto station_csv = out_dir / "Station.csv";
        auto station_init_csv = out_dir / "Station_init.csv";
        auto edge_csv = out_dir / "Edge.csv";
        auto update_csv = out_dir / "update_station_status.csv";

        write_station_csv(stations, station_csv);
        write_station_csv(stations, station_init_csv);
        write_edge_csv(all_edges, edge_csv);
        write_update_status_example(update_csv);

        std::cout << "\n[3/3] Files written:\n";
        std::cout << "      " << station_csv.string() << "\n";
        std::cout << "      " << station_init_csv.string() << "\n";
        std::cout << "      " << edge_csv.string() << "\n";
        std::cout << "      " << update_csv.string() << "\n";

        // Benchmark check
        std::cout << "\n=== Benchmark comparison ===\n";
        std::cout << "  Stations: " << stations.size() << "  (target: 525)\n";
        std::cout << "  Edges:    " << all_edges.size() << "  (target: 1226)\n";

        if (std::abs(static_cast<int>(stations.size()) - 525) > 5 ||
            std::abs(static_cast<int>(all_edges.size()) - 1226) > 50) {
            std::cout << "  [WARN] Data scale deviates from benchmark — check raw data\n";
        } else {
            std::cout << "  [OK] Data scale matches expectations\n";
        }

        return true;

    } catch (const std::exception& e) {
        std::cerr << "[FATAL] " << e.what() << "\n";
        return false;
    }
}

// =========================================================================
// Entry point for standalone build_dataset executable
// =========================================================================

} // namespace metro::build

// When built as standalone executable:
#ifndef BUILD_DATASET_AS_LIBRARY
int main() {
    namespace fs = std::filesystem;

    // Resolve paths — data lives under python/ directory
    fs::path raw_dir = "../python/metro_data";
    fs::path out_dir = "../python/data";

    // Try alternative locations
    if (!fs::exists(raw_dir)) {
        raw_dir = "metro_data";
        out_dir = "data";
    }
    if (!fs::exists(raw_dir) && fs::exists("python/metro_data")) {
        raw_dir = "python/metro_data";
        out_dir = "python/data";
    }

    return metro::build::build_all(raw_dir, out_dir) ? 0 : 1;
}
#endif
