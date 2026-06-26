/**
 * server.cpp — C++ HTTP REST API server for Shanghai Metro Route Planning
 *
 * Wraps the metro_core library (Graph, StationManager, pathfinder, analysis)
 * as JSON API endpoints. Serves static frontend files from backend/static/.
 *
 * Dependencies (vendored, header-only):
 *   - cpp-httplib (third_party/cpp-httplib/httplib.h)
 *   - nlohmann/json (third_party/nlohmann/json.hpp)
 *
 * Build:
 *   cd cpp/build && cmake .. && cmake --build . --target metro_server
 *
 * Run:
 *   ./build/metro_server [--port 8080] [--data ../python/data]
 */

#include <algorithm>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <mutex>
#include <shared_mutex>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>

// Vendored third-party headers
#include "httplib.h"
#include "json.hpp"

// Metro core library headers
#include "metro/station.hpp"
#include "metro/graph.hpp"
#include "metro/pathfinder.hpp"
#include "metro/network_analysis.hpp"

namespace fs = std::filesystem;
using json = nlohmann::json;

// ============================================================================
// Global state (loaded once at startup, protected by shared_mutex)
// ============================================================================

static metro::Graph g_graph;
static metro::StationManager g_mgr;
static std::shared_mutex g_state_mutex;

// Shanghai Metro line colors (same as frontend)
static const std::unordered_map<std::string, std::string> LINE_COLORS = {
    {"1号线", "#E4002B"}, {"2号线", "#97D700"}, {"3号线", "#FCD600"},
    {"4号线", "#461D84"}, {"5号线", "#944D9B"}, {"6号线", "#D6006C"},
    {"7号线", "#ED6B06"}, {"8号线", "#0094D8"}, {"9号线", "#7AC8E1"},
    {"10号线", "#C6AFD4"}, {"11号线", "#841C21"}, {"12号线", "#007A60"},
    {"13号线", "#E77CA5"}, {"14号线", "#9D8B63"}, {"15号线", "#B2A680"},
    {"16号线", "#77D0C8"}, {"17号线", "#BB6414"}, {"18号线", "#C4984E"},
    {"浦江线", "#B5B5B6"}, {"市域机场线", "#4A90A4"},
};

// ============================================================================
// Data directory resolution (same logic as main.cpp)
// ============================================================================

static fs::path find_data_dir() {
    for (auto candidate : {"../python/data", "python/data", "data", "../data"}) {
        if (fs::exists(fs::path(candidate) / "Edge.csv")) {
            return fs::absolute(candidate);
        }
    }
    throw std::runtime_error("Cannot find data directory with Edge.csv");
}

static fs::path find_static_dir() {
    for (auto candidate : {"backend/static", "../backend/static", "cpp/backend/static", "../cpp/backend/static"}) {
        if (fs::exists(fs::path(candidate) / "index.html")) {
            return fs::absolute(candidate);
        }
    }
    // Fallback: relative to executable
    return fs::absolute("backend/static");
}

// ============================================================================
// JSON serialization helpers
// ============================================================================

static json station_to_json(const metro::Station& st) {
    return {
        {"id", st.id},
        {"name", st.name},
        {"line", st.line},
        {"status", st.status},
        {"is_open", st.is_open()},
    };
}

static json pathresult_to_json(const metro::PathResult& pr) {
    json j;
    j["valid"] = pr.valid;
    j["error"] = pr.error;
    j["station_ids"] = pr.station_ids;
    j["total_time"] = pr.total_time;
    j["transfer_count"] = pr.transfer_count;
    j["station_count"] = pr.station_count();

    // Enrich station_ids with names and lines
    json station_info = json::array();
    for (const auto& sid : pr.station_ids) {
        const auto* st = g_mgr.get(sid);
        if (st) {
            station_info.push_back({
                {"id", sid},
                {"name", st->name},
                {"line", st->line},
            });
        } else {
            station_info.push_back({
                {"id", sid},
                {"name", "?"},
                {"line", "?"},
            });
        }
    }
    j["stations"] = station_info;

    // Serialize transfer_at: vector<tuple<string,string,string>>
    json transfers = json::array();
    for (const auto& t : pr.transfer_at) {
        transfers.push_back({
            {"station_name", std::get<0>(t)},
            {"from_line", std::get<1>(t)},
            {"to_line", std::get<2>(t)},
        });
    }
    j["transfer_at"] = transfers;

    // line4_dirs: unordered_map<string, string>
    j["line4_dirs"] = pr.line4_dirs;

    return j;
}

// ============================================================================
// Route handler helpers
// ============================================================================

// Shared lock for read-only operations (pathfinding, queries)
static auto read_lock() { return std::shared_lock(g_state_mutex); }
// Unique lock for write operations (status changes)
static auto write_lock() { return std::unique_lock(g_state_mutex); }

// Parse JSON body, return empty json on failure
static json parse_body(const httplib::Request& req, httplib::Response& res) {
    if (req.body.empty()) {
        res.status = 400;
        res.set_content(R"({"error":"Empty request body"})", "application/json");
        return {};
    }
    try {
        return json::parse(req.body);
    } catch (const json::parse_error& e) {
        res.status = 400;
        res.set_content(json{{"error", std::string("JSON parse error: ") + e.what()}}.dump(),
                        "application/json");
        return {};
    }
}

// Send JSON response
static void send_json(httplib::Response& res, const json& j, int status = 200) {
    res.status = status;
    res.set_content(j.dump(), "application/json");
}

// ============================================================================
// API: Data queries
// ============================================================================

static void handle_get_stations(const httplib::Request& req, httplib::Response& res) {
    auto lock = read_lock();
    json arr = json::array();
    for (const auto& st : g_mgr.all_stations()) {
        arr.push_back(station_to_json(*st));
    }
    send_json(res, arr);
}

static void handle_get_station(const httplib::Request& req, httplib::Response& res) {
    auto lock = read_lock();
    std::string id = req.matches[1];  // from path param /api/stations/<id>
    const auto* st = g_mgr.get(id);
    if (!st) {
        send_json(res, {{"error", "Station not found: " + id}}, 404);
        return;
    }
    json j = station_to_json(*st);
    j["transfer_to"] = g_mgr.transfer_lines_for(st->name, st->line);
    send_json(res, j);
}

static void handle_search_stations(const httplib::Request& req, httplib::Response& res) {
    auto lock = read_lock();
    std::string q;
    if (req.has_param("q")) {
        q = req.get_param_value("q");
    }
    if (q.empty()) {
        send_json(res, json::array());
        return;
    }
    auto results = g_mgr.find_fuzzy(q);
    json arr = json::array();
    for (const auto* st : results) {
        arr.push_back(station_to_json(*st));
    }
    send_json(res, arr);
}

static void handle_get_lines(const httplib::Request& /*req*/, httplib::Response& res) {
    auto lock = read_lock();
    json arr = json::array();
    // Get all unique lines from stations
    std::unordered_map<std::string, int> line_counts;
    for (const auto& st : g_mgr.all_stations()) {
        line_counts[st->line]++;
    }
    for (const auto& [line, count] : line_counts) {
        auto it = LINE_COLORS.find(line);
        arr.push_back({
            {"name", line},
            {"color", it != LINE_COLORS.end() ? it->second : "#666666"},
            {"station_count", count},
        });
    }
    send_json(res, arr);
}

static void handle_get_line_stations(const httplib::Request& req, httplib::Response& res) {
    auto lock = read_lock();
    std::string line_name = req.matches[1];
    auto sts = g_mgr.stations_of_line(line_name);
    json arr = json::array();
    for (const auto* st : sts) {
        json j = station_to_json(*st);
        j["transfer_to"] = g_mgr.transfer_lines_for(st->name, st->line);
        arr.push_back(j);
    }
    send_json(res, arr);
}

static void handle_graph_summary(const httplib::Request& /*req*/, httplib::Response& res) {
    auto lock = read_lock();
    // Count transfer edges
    int transfer_count = 0;
    for (const auto& [id, edges] : g_graph.adj()) {
        for (const auto& e : edges) {
            if (e.is_transfer()) transfer_count++;
        }
    }
    send_json(res, {
        {"node_count", g_graph.node_count()},
        {"edge_count", g_graph.edge_count()},
        {"transfer_edge_count", transfer_count},
        {"station_count", g_mgr.size()},
        {"closed_count", g_mgr.closed_stations().size()},
    });
}

static void handle_get_layout(const httplib::Request& /*req*/, httplib::Response& res) {
    // layout.json is served as a static file — mount point handles this
    // But we provide an API endpoint that reads and returns it
    auto static_dir = find_static_dir();
    auto layout_path = static_dir / "layout.json";
    if (!fs::exists(layout_path)) {
        send_json(res, {{"error", "layout.json not found. Run scripts/generate_layout.py first."}}, 404);
        return;
    }
    std::ifstream f(layout_path);
    std::string content((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
    res.set_content(content, "application/json");
}

// ============================================================================
// API: Route planning
// ============================================================================

static void handle_shortest_time(const httplib::Request& req, httplib::Response& res) {
    auto body = parse_body(req, res);
    if (body.empty()) return;
    std::string src = body.value("src_id", "");
    std::string dst = body.value("dst_id", "");
    if (src.empty() || dst.empty()) {
        send_json(res, {{"valid", false}, {"error", "Missing src_id or dst_id"}}, 400);
        return;
    }
    auto lock = read_lock();
    auto result = metro::pathfinder::dijkstra_shortest_time(src, dst, g_graph, g_mgr);
    send_json(res, pathresult_to_json(result));
}

static void handle_k_shortest_time(const httplib::Request& req, httplib::Response& res) {
    auto body = parse_body(req, res);
    if (body.empty()) return;
    std::string src = body.value("src_id", "");
    std::string dst = body.value("dst_id", "");
    int k = body.value("k", 3);
    if (src.empty() || dst.empty()) {
        send_json(res, {{"error", "Missing src_id or dst_id"}}, 400);
        return;
    }
    auto lock = read_lock();
    auto results = metro::pathfinder::yen_k_shortest_time(src, dst, g_graph, g_mgr, k);
    json arr = json::array();
    for (const auto& r : results) {
        arr.push_back(pathresult_to_json(r));
    }
    send_json(res, arr);
}

static void handle_min_transfers(const httplib::Request& req, httplib::Response& res) {
    auto body = parse_body(req, res);
    if (body.empty()) return;
    std::string src = body.value("src_id", "");
    std::string dst = body.value("dst_id", "");
    if (src.empty() || dst.empty()) {
        send_json(res, {{"valid", false}, {"error", "Missing src_id or dst_id"}}, 400);
        return;
    }
    auto lock = read_lock();
    auto result = metro::pathfinder::dijkstra_min_transfers(src, dst, g_graph, g_mgr);
    send_json(res, pathresult_to_json(result));
}

static void handle_k_min_transfers(const httplib::Request& req, httplib::Response& res) {
    auto body = parse_body(req, res);
    if (body.empty()) return;
    std::string src = body.value("src_id", "");
    std::string dst = body.value("dst_id", "");
    int k = body.value("k", 3);
    if (src.empty() || dst.empty()) {
        send_json(res, {{"error", "Missing src_id or dst_id"}}, 400);
        return;
    }
    auto lock = read_lock();
    auto results = metro::pathfinder::yen_k_min_transfers(src, dst, g_graph, g_mgr, k);
    json arr = json::array();
    for (const auto& r : results) {
        arr.push_back(pathresult_to_json(r));
    }
    send_json(res, arr);
}

// ============================================================================
// API: Station management
// ============================================================================

static fs::path g_data_dir;  // Set at startup

static void handle_close_station(const httplib::Request& req, httplib::Response& res) {
    std::string id = req.matches[1];
    auto lock = write_lock();
    const auto* st = g_mgr.get(id);
    if (!st) {
        send_json(res, {{"error", "Station not found: " + id}}, 404);
        return;
    }
    g_mgr.close_station(id);
    g_mgr.save(g_data_dir / "Station.csv");
    send_json(res, station_to_json(*g_mgr.get(id)));
}

static void handle_open_station(const httplib::Request& req, httplib::Response& res) {
    std::string id = req.matches[1];
    auto lock = write_lock();
    const auto* st = g_mgr.get(id);
    if (!st) {
        send_json(res, {{"error", "Station not found: " + id}}, 404);
        return;
    }
    g_mgr.open_station(id);
    g_mgr.save(g_data_dir / "Station.csv");
    send_json(res, station_to_json(*g_mgr.get(id)));
}

static void handle_batch_update(const httplib::Request& req, httplib::Response& res) {
    // Check for multipart file upload
    auto it = req.files.find("file");
    if (it == req.files.end()) {
        send_json(res, {{"error", "No file uploaded. Use multipart/form-data with field name 'file'."}}, 400);
        return;
    }

    const auto& file = it->second;
    auto temp_path = g_data_dir / "_temp_update.csv";

    {
        std::ofstream ofs(temp_path, std::ios::binary);
        ofs.write(file.content.data(), file.content.size());
    }

    auto lock = write_lock();
    auto stats = g_mgr.batch_update_from_csv(temp_path);
    g_mgr.save(g_data_dir / "Station.csv");

    // Clean up temp file
    std::error_code ec;
    fs::remove(temp_path, ec);

    send_json(res, {
        {"updated", stats.updated},
        {"not_found", stats.not_found},
        {"invalid", stats.invalid},
        {"errors", stats.errors},
    });
}

static void handle_restore(const httplib::Request& /*req*/, httplib::Response& res) {
    auto lock = write_lock();
    auto init_path = g_data_dir / "Station_init.csv";
    bool ok = g_mgr.restore_initial(init_path);
    if (ok) {
        g_mgr.save(g_data_dir / "Station.csv");
    }
    send_json(res, {
        {"success", ok},
        {"closed_count", g_mgr.closed_stations().size()},
    });
}

// ============================================================================
// API: Network analysis
// ============================================================================

static void handle_affected_area(const httplib::Request& req, httplib::Response& res) {
    auto body = parse_body(req, res);
    if (body.empty()) return;
    std::string station_id = body.value("station_id", "");
    int max_depth = body.value("max_depth", 2);
    if (station_id.empty()) {
        send_json(res, {{"error", "Missing station_id"}}, 400);
        return;
    }
    auto lock = read_lock();
    auto affected = metro::analysis::affected_area(g_graph, g_mgr, station_id, max_depth);

    json arr = json::array();
    for (const auto& sid : affected) {
        const auto* st = g_mgr.get(sid);
        if (st) {
            arr.push_back(station_to_json(*st));
        } else {
            arr.push_back({{"id", sid}, {"name", "?"}, {"line", "?"}});
        }
    }

    send_json(res, {
        {"center_station_id", station_id},
        {"max_depth", max_depth},
        {"affected_count", affected.size()},
        {"affected_stations", arr},
    });
}

static void handle_components(const httplib::Request& /*req*/, httplib::Response& res) {
    auto lock = read_lock();
    auto components = metro::analysis::count_components(g_graph, g_mgr);

    json comps = json::array();
    for (size_t i = 0; i < components.size(); i++) {
        json stations = json::array();
        for (const auto& sid : components[i]) {
            const auto* st = g_mgr.get(sid);
            if (st) {
                stations.push_back(station_to_json(*st));
            } else {
                stations.push_back({{"id", sid}, {"name", "?"}, {"line", "?"}});
            }
        }
        comps.push_back({
            {"index", i},
            {"size", components[i].size()},
            {"stations", stations},
        });
    }

    int total = 0;
    for (const auto& c : components) total += static_cast<int>(c.size());

    send_json(res, {
        {"component_count", components.size()},
        {"total_stations", total},
        {"components", comps},
    });
}

// ============================================================================
// CORS middleware (for development)
// ============================================================================

static void add_cors(httplib::Response& res) {
    res.set_header("Access-Control-Allow-Origin", "*");
    res.set_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    res.set_header("Access-Control-Allow-Headers", "Content-Type");
}

// ============================================================================
// Main
// ============================================================================

int main(int argc, char* argv[]) {
    // Parse CLI arguments
    int port = 8080;
    std::string data_dir_arg;

    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--port" && i + 1 < argc) {
            port = std::stoi(argv[++i]);
        } else if (arg == "--data" && i + 1 < argc) {
            data_dir_arg = argv[++i];
        } else if (arg == "--help" || arg == "-h") {
            std::cout << "Usage: metro_server [--port PORT] [--data DATA_DIR]\n"
                      << "  --port PORT     Listen port (default: 8080)\n"
                      << "  --data DATA_DIR Path to directory with Station.csv and Edge.csv\n"
                      << "  --help          Show this help\n";
            return 0;
        }
    }

    // Resolve data directory
    try {
        if (!data_dir_arg.empty()) {
            g_data_dir = fs::absolute(data_dir_arg);
        } else {
            g_data_dir = find_data_dir();
        }
    } catch (const std::exception& e) {
        std::cerr << "[FATAL] " << e.what() << std::endl;
        return 1;
    }

    std::cout << "============================================================\n";
    std::cout << "  Shanghai Metro Route Planning — C++ Web Server\n";
    std::cout << "============================================================\n";
    std::cout << "Data directory: " << g_data_dir.string() << "\n";

    // Load graph and stations
    try {
        g_graph.load(g_data_dir / "Edge.csv");
        g_mgr.load(g_data_dir / "Station.csv");
    } catch (const std::exception& e) {
        std::cerr << "[FATAL] Failed to load data: " << e.what() << std::endl;
        return 1;
    }

    std::cout << "[OK] Graph: " << g_graph.node_count() << " nodes, "
              << g_graph.edge_count() << " edges\n";
    std::cout << "[OK] Stations: " << g_mgr.size() << " loaded ("
              << g_mgr.closed_stations().size() << " closed)\n";

    // Resolve static directory
    auto static_dir = find_static_dir();
    std::cout << "Static files: " << static_dir.string() << "\n";

    // --- Setup HTTP server ---
    httplib::Server svr;

    // Static file serving
    if (!fs::exists(static_dir / "index.html")) {
        std::cerr << "[WARN] index.html not found in " << static_dir.string()
                  << " — create frontend files in backend/static/\n";
    }
    svr.set_mount_point("/", static_dir.string());

    // CORS preflight handler
    svr.Options(R"(/api/.*)", [](const httplib::Request&, httplib::Response& res) {
        add_cors(res);
        res.status = 204;
    });

    // --- Register API routes ---

    // Data queries
    svr.Get("/api/stations", [](auto& req, auto& res) { add_cors(res); handle_get_stations(req, res); });
    svr.Get(R"(/api/stations/search)", [](auto& req, auto& res) { add_cors(res); handle_search_stations(req, res); });
    svr.Get(R"(/api/stations/([^/]+))", [](auto& req, auto& res) { add_cors(res); handle_get_station(req, res); });
    svr.Get("/api/lines", [](auto& req, auto& res) { add_cors(res); handle_get_lines(req, res); });
    svr.Get(R"(/api/lines/(.+))", [](auto& req, auto& res) { add_cors(res); handle_get_line_stations(req, res); });
    svr.Get("/api/graph/summary", [](auto& req, auto& res) { add_cors(res); handle_graph_summary(req, res); });
    svr.Get("/api/layout", [](auto& req, auto& res) { add_cors(res); handle_get_layout(req, res); });

    // Route planning
    svr.Post("/api/route/shortest-time", [](auto& req, auto& res) { add_cors(res); handle_shortest_time(req, res); });
    svr.Post("/api/route/k-shortest-time", [](auto& req, auto& res) { add_cors(res); handle_k_shortest_time(req, res); });
    svr.Post("/api/route/min-transfers", [](auto& req, auto& res) { add_cors(res); handle_min_transfers(req, res); });
    svr.Post("/api/route/k-min-transfers", [](auto& req, auto& res) { add_cors(res); handle_k_min_transfers(req, res); });

    // Station management
    svr.Post(R"(/api/stations/([^/]+)/close)", [](auto& req, auto& res) { add_cors(res); handle_close_station(req, res); });
    svr.Post(R"(/api/stations/([^/]+)/open)", [](auto& req, auto& res) { add_cors(res); handle_open_station(req, res); });
    svr.Post("/api/stations/batch-update", [](auto& req, auto& res) { add_cors(res); handle_batch_update(req, res); });
    svr.Post("/api/stations/restore", [](auto& req, auto& res) { add_cors(res); handle_restore(req, res); });

    // Network analysis
    svr.Post("/api/analysis/affected-area", [](auto& req, auto& res) { add_cors(res); handle_affected_area(req, res); });
    svr.Get("/api/analysis/components", [](auto& req, auto& res) { add_cors(res); handle_components(req, res); });

    // Health check
    svr.Get("/api/health", [](const httplib::Request&, httplib::Response& res) {
        res.set_content(R"({"status":"ok"})", "application/json");
    });

    // --- Start server ---
    std::cout << "\n  Open http://localhost:" << port << " in your browser\n\n";

    svr.listen("0.0.0.0", port);

    return 0;
}
