#include "metro/pathfinder.hpp"
#include "metro/graph.hpp"
#include "metro/station.hpp"

#include <queue>
#include <unordered_set>
#include <sstream>
#include <algorithm>
#include <iostream>

namespace metro::pathfinder {

// =========================================================================
// Internal constants
// =========================================================================

namespace {

constexpr const char* TRANSFER_LINE = "换乘";
constexpr const char* LINE4_INNER  = "内";   // counter-clockwise
constexpr const char* LINE4_OUTER  = "外";   // clockwise

// =========================================================================
// Weight types for priority queue (min-heap via reversed operator<)
// =========================================================================

struct TimeWeight {
    int time = 0;
    // Natural ordering (used for dist comparison): smaller = better
    bool operator<(const TimeWeight& o) const { return time < o.time; }
    bool operator>(const TimeWeight& o) const { return time > o.time; }
};

struct TransferWeight {
    int transfers = 0;
    int time = 0;
    // Natural ordering (used for dist comparison): smaller = better
    bool operator<(const TransferWeight& o) const {
        if (transfers != o.transfers) return transfers < o.transfers;
        return time < o.time;
    }
    bool operator>(const TransferWeight& o) const {
        if (transfers != o.transfers) return transfers > o.transfers;
        return time > o.time;
    }
};

// =========================================================================
// Predecessor info for path reconstruction
// =========================================================================

struct PredecessorInfo {
    std::string prev_id;
    // Store edge data by value (not pointer — the Edge from neighbors()
    // is a temporary that would dangle).
    std::string line;
    std::string direction;
    int time = 0;
    bool is_transfer = false;
};

// =========================================================================
// _path_key — unique string key for a station ID sequence
// =========================================================================

std::string path_key(const std::vector<std::string>& ids) {
    if (ids.empty()) return "";
    std::ostringstream oss;
    oss << ids[0];
    for (size_t i = 1; i < ids.size(); ++i) {
        oss << "->" << ids[i];
    }
    return oss.str();
}

// =========================================================================
// _path_total_time — sum edge times along a path
// =========================================================================

int path_total_time(const std::vector<std::string>& ids, const Graph& graph) {
    int total = 0;
    for (size_t i = 1; i < ids.size(); ++i) {
        const Edge* edge = graph.get_edge(ids[i - 1], ids[i]);
        if (edge) total += edge->time;
    }
    return total;
}

// =========================================================================
// _count_line_changes — count transfer events along a path
// =========================================================================

int count_line_changes(const std::vector<std::string>& ids, const Graph& graph) {
    if (ids.size() < 2) return 0;
    int changes = 0;
    std::string prev_line;
    for (size_t i = 1; i < ids.size(); ++i) {
        const Edge* edge = graph.get_edge(ids[i - 1], ids[i]);
        if (edge && !edge->is_transfer()) {
            if (!prev_line.empty() && prev_line != edge->line) {
                ++changes;
            }
            prev_line = edge->line;
        }
    }
    return changes;
}

// =========================================================================
// _rebuild_path — reconstruct PathResult from came_from map
// =========================================================================

PathResult rebuild_path(const std::string& end_id,
                         const std::unordered_map<std::string, PredecessorInfo>& came_from,
                         const Graph& graph,
                         const StationManager& mgr) {
    // 1. Walk backward from end to start
    std::vector<std::string> path_ids;
    std::unordered_set<std::string> seen;  // cycle detection
    std::string curr = end_id;
    while (true) {
        if (seen.count(curr)) break;  // cycle detected — break
        seen.insert(curr);
        path_ids.push_back(curr);
        auto it = came_from.find(curr);
        if (it == came_from.end()) break;
        curr = it->second.prev_id;
        if (curr.empty()) break;  // reached start node
    }
    std::reverse(path_ids.begin(), path_ids.end());

    PathResult result;
    result.station_ids = path_ids;

    // 2. Scan edges to compute total_time, transfer info, and line4 directions
    int total_time = 0;
    int transfer_edge_count = 0;
    // line_trace: (station_id, line, station_name) — ONE entry per *riding*
    // segment (transfer edges are excluded), plus a leading seed entry for the
    // origin station's nominal line.
    //
    // Transfer-counting semantics (settled 2026-07-01): a transfer at the ORIGIN
    // counts. Because line_trace is seeded with the origin's line, boarding a
    // DIFFERENT line than the origin node sits on (i.e. the path begins with a
    // transfer edge) is counted as a transfer. Example: 人民广场(1号线)→陆家嘴(2号线)
    // = 1 transfer. Riding your origin's own line first is free (seed == first
    // riding line → no change).
    //
    // A trailing transfer edge (arriving at another platform of the DESTINATION
    // station) is still NOT counted — you have already reached your destination
    // station, so walking to its other platform is not a ride change. That edge's
    // 5 minutes still count toward total_time.
    std::vector<std::tuple<std::string, std::string, std::string>> line_trace;

    // Seed with the origin station's nominal line so origin transfers are counted.
    if (!path_ids.empty()) {
        const Station* src_station = mgr.get(path_ids[0]);
        if (src_station) {
            line_trace.emplace_back(path_ids[0], src_station->line, src_station->name);
        }
    }

    for (size_t i = 1; i < path_ids.size(); ++i) {
        const Edge* edge = graph.get_edge(path_ids[i - 1], path_ids[i]);
        if (!edge) continue;
        total_time += edge->time;

        if (edge->is_transfer()) {
            ++transfer_edge_count;
        }

        if (!edge->is_transfer()) {
            const Station* station = mgr.get(path_ids[i - 1]);
            std::string sname = station ? station->name : "";
            line_trace.emplace_back(path_ids[i - 1], edge->line, sname);

            // 4号线 direction markers (keyed by TARGET station ID)
            if (edge->line.find("4号线") != std::string::npos && !edge->direction.empty()) {
                if (edge->direction.find(LINE4_INNER) != std::string::npos) {
                    result.line4_dirs[path_ids[i]] = "内圈";
                } else if (edge->direction.find(LINE4_OUTER) != std::string::npos) {
                    result.line4_dirs[path_ids[i]] = "外圈";
                }
            }
        }
    }

    result.total_time = total_time;
    result.transfer_edge_count = transfer_edge_count;

    // 3. Compute transfer count and transfer_at from line_trace
    int transfers = 0;
    if (line_trace.size() >= 2) {
        std::string current_line = std::get<1>(line_trace[0]);
        for (size_t j = 1; j < line_trace.size(); ++j) {
            if (std::get<1>(line_trace[j]) != current_line) {
                ++transfers;
                const auto& new_line = std::get<1>(line_trace[j]);
                const auto& sname = std::get<2>(line_trace[j]);
                // Avoid duplicate entries for the same station
                if (result.transfer_at.empty() ||
                    std::get<0>(result.transfer_at.back()) != sname) {
                    result.transfer_at.emplace_back(sname, current_line, new_line);
                }
                current_line = new_line;
            }
        }
    } else if (transfer_edge_count > 0 && path_ids.size() >= 2) {
        // Degenerate pure-transfer path: no riding edges at all (line_trace holds
        // only the seed). This is a same-station platform switch, e.g. 莘庄(1号线)
        // →莘庄(5号线). If the endpoints sit on different lines it is exactly one
        // transfer.
        const Station* src_station = mgr.get(path_ids.front());
        const Station* dst_station = mgr.get(path_ids.back());
        std::string src_line = src_station ? src_station->line : "";
        std::string dst_line = dst_station ? dst_station->line : "";
        if (!src_line.empty() && !dst_line.empty() && src_line != dst_line) {
            transfers = 1;
            std::string sname = src_station ? src_station->name : "";
            result.transfer_at.emplace_back(sname, src_line, dst_line);
        }
    }

    result.transfer_count = transfers;
    result.valid = true;
    return result;
}

// =========================================================================
// rebuild_path_from_ids — for Yen's algorithm: reconstruct from ID list
// =========================================================================

PathResult rebuild_path_from_ids(const std::vector<std::string>& path_ids,
                                  const Graph& graph,
                                  const StationManager& mgr) {
    // Build a minimal came_from map from consecutive IDs
    std::unordered_map<std::string, PredecessorInfo> came_from;
    for (size_t i = 1; i < path_ids.size(); ++i) {
        const Edge* edge = graph.get_edge(path_ids[i - 1], path_ids[i]);
        PredecessorInfo info;
        info.prev_id = path_ids[i - 1];
        if (edge) {
            info.line = edge->line;
            info.direction = edge->direction;
            info.time = edge->time;
            info.is_transfer = edge->is_transfer();
        }
        came_from[path_ids[i]] = info;
    }
    return rebuild_path(path_ids.back(), came_from, graph, mgr);
}

// =========================================================================
// Helper: build edge key for removal sets
// =========================================================================

std::string edge_removal_key(const std::string& from, const std::string& to) {
    return from + "->" + to;
}

// =========================================================================
// _dijkstra_with_removals — Dijkstra with blocked edges/nodes (time weight)
// =========================================================================

PathResult dijkstra_with_removals(
    const std::string& src_id, const std::string& dst_id,
    const Graph& graph, const StationManager& mgr,
    const std::unordered_set<std::string>& removed_edges_set,
    const std::unordered_set<std::string>& removed_nodes)
{
    std::unordered_map<std::string, int> dist;
    dist[src_id] = 0;

    std::unordered_map<std::string, PredecessorInfo> came_from;
    came_from[src_id] = {"", "", "", 0, false};

    std::priority_queue<std::pair<TimeWeight, std::string>,
                        std::vector<std::pair<TimeWeight, std::string>>,
                        std::greater<>> pq;
    pq.push({TimeWeight{0}, src_id});

    std::unordered_set<std::string> visited;

    while (!pq.empty()) {
        auto [w, u] = pq.top(); pq.pop();

        if (visited.count(u)) continue;
        if (removed_nodes.count(u)) continue;
        visited.insert(u);

        if (u == dst_id) {
            return rebuild_path(dst_id, came_from, graph, mgr);
        }

        for (const auto& edge : graph.neighbors(u, &mgr)) {
            const auto& v = edge.to_id;
            if (removed_edges_set.count(edge_removal_key(u, v))) continue;
            if (removed_nodes.count(v)) continue;

            int nd = w.time + edge.time;
            auto it = dist.find(v);
            if (it == dist.end() || nd < it->second) {
                dist[v] = nd;
                came_from[v] = {u, edge.line, edge.direction, edge.time, edge.is_transfer()};
                pq.push({TimeWeight{nd}, v});
            }
        }
    }

    return PathResult{};
}

// =========================================================================
// _min_transfer_with_removals — Dijkstra with removals (transfer weight)
// =========================================================================

PathResult min_transfer_with_removals(
    const std::string& src_id, const std::string& dst_id,
    const Graph& graph, const StationManager& mgr,
    const std::unordered_set<std::string>& removed_edges_set,
    const std::unordered_set<std::string>& removed_nodes)
{
    // dist: station_id → (transfers, time)
    std::unordered_map<std::string, TransferWeight> dist;
    dist[src_id] = {0, 0};

    std::unordered_map<std::string, PredecessorInfo> came_from;
    came_from[src_id] = {"", "", "", 0, false};

    std::priority_queue<std::pair<TransferWeight, std::string>,
                        std::vector<std::pair<TransferWeight, std::string>>,
                        std::greater<>> pq;
    pq.push({{0, 0}, src_id});

    std::unordered_set<std::string> visited;

    // Track which line reaches each node. Seed with the source station's actual
    // line so an origin transfer (path begins with a transfer edge onto another
    // line) is properly costed as +1. This keeps the algorithm consistent with
    // the display count in rebuild_path().
    std::unordered_map<std::string, std::string> node_line;
    {
        const Station* src_station = mgr.get(src_id);
        node_line[src_id] = src_station ? src_station->line : "";
    }

    while (!pq.empty()) {
        auto [w, u] = pq.top(); pq.pop();

        if (visited.count(u) || removed_nodes.count(u)) continue;
        visited.insert(u);

        if (u == dst_id) {
            return rebuild_path(dst_id, came_from, graph, mgr);
        }

        const auto& cur_line = node_line[u];

        for (const auto& edge : graph.neighbors(u, &mgr)) {
            const auto& v = edge.to_id;
            if (removed_edges_set.count(edge_removal_key(u, v))) continue;
            if (removed_nodes.count(v)) continue;

            int new_time = w.time + edge.time;
            int new_transfers = w.transfers;

            if (!edge.is_transfer() && !cur_line.empty() && edge.line != cur_line) {
                new_transfers = w.transfers + 1;
            }

            TransferWeight new_weight{new_transfers, new_time};

            // Determine the line that reaches v
            std::string v_line = edge.is_transfer() ? cur_line : edge.line;

            auto it = dist.find(v);
            if (it == dist.end() || new_weight < it->second) {
                if (!v_line.empty()) {
                    node_line[v] = v_line;
                }
                dist[v] = new_weight;
                came_from[v] = {u, edge.line, edge.direction, edge.time, edge.is_transfer()};
                pq.push({new_weight, v});
            }
        }
    }

    return PathResult{};
}

} // anonymous namespace

// =========================================================================
// PUBLIC API
// =========================================================================

// -------------------------------------------------------------------------
// M3-1: dijkstra_shortest_time
// -------------------------------------------------------------------------

PathResult dijkstra_shortest_time(const std::string& src_id,
                                   const std::string& dst_id,
                                   const Graph& graph,
                                   const StationManager& mgr) {
    // Same start/end
    if (src_id == dst_id) {
        PathResult r;
        r.station_ids = {src_id};
        r.total_time = 0;
        r.error = "起点和终点相同，无需进行路径规划。";
        return r;
    }

    // Check start/end are open
    const Station* src_s = mgr.get(src_id);
    const Station* dst_s = mgr.get(dst_id);
    if (src_s && !src_s->is_open()) {
        PathResult r;
        r.valid = false;
        r.error = "起点：" + src_s->name + "(" + src_s->line + ")已关闭，无法进行路径规划。";
        return r;
    }
    if (dst_s && !dst_s->is_open()) {
        PathResult r;
        r.valid = false;
        r.error = "终点：" + dst_s->name + "(" + dst_s->line + ")已关闭，无法进行路径规划。";
        return r;
    }

    std::unordered_map<std::string, int> dist;
    dist[src_id] = 0;

    std::unordered_map<std::string, PredecessorInfo> came_from;
    came_from[src_id] = {"", "", "", 0, false};

    std::priority_queue<std::pair<TimeWeight, std::string>,
                        std::vector<std::pair<TimeWeight, std::string>>,
                        std::greater<>> pq;
    pq.push({TimeWeight{0}, src_id});

    std::unordered_set<std::string> visited;

    while (!pq.empty()) {
        auto [w, u] = pq.top(); pq.pop();

        if (visited.count(u)) continue;
        visited.insert(u);

        if (u == dst_id) {
            return rebuild_path(dst_id, came_from, graph, mgr);
        }

        for (const auto& edge : graph.neighbors(u, &mgr)) {
            const auto& v = edge.to_id;
            int nd = w.time + edge.time;
            auto it = dist.find(v);
            if (it == dist.end() || nd < it->second) {
                dist[v] = nd;
                came_from[v] = {u, edge.line, edge.direction, edge.time, edge.is_transfer()};
                pq.push({TimeWeight{nd}, v});
            }
        }
    }

    PathResult r;
    r.valid = false;
    r.error = "未找到可达路径。";
    return r;
}

// -------------------------------------------------------------------------
// M3-2: yen_k_shortest_time
// -------------------------------------------------------------------------

std::vector<PathResult> yen_k_shortest_time(const std::string& src_id,
                                             const std::string& dst_id,
                                             const Graph& graph,
                                             const StationManager& mgr,
                                             int k) {
    // Same start/end
    if (src_id == dst_id) {
        PathResult p;
        p.station_ids = {src_id};
        p.total_time = 0;
        p.error = "起点和终点相同，无需进行路径规划。";
        return {p};
    }

    // Check start/end open
    const Station* src_s = mgr.get(src_id);
    const Station* dst_s = mgr.get(dst_id);
    if (src_s && !src_s->is_open()) {
        PathResult r;
        r.valid = false;
        r.error = "起点：" + src_s->name + "(" + src_s->line + ")已关闭，无法进行路径规划。";
        return {r};
    }
    if (dst_s && !dst_s->is_open()) {
        PathResult r;
        r.valid = false;
        r.error = "终点：" + dst_s->name + "(" + dst_s->line + ")已关闭，无法进行路径规划。";
        return {r};
    }

    // 1. Find first shortest path
    PathResult first = dijkstra_shortest_time(src_id, dst_id, graph, mgr);
    if (!first.valid || first.station_ids.empty()) {
        return {first};
    }

    std::vector<PathResult> a_paths = {first};
    // Candidates: (total_time, path_ids)
    std::priority_queue<
        std::pair<int, std::vector<std::string>>,
        std::vector<std::pair<int, std::vector<std::string>>>,
        std::greater<>
    > candidates;

    for (int ki = 1; ki < k; ++ki) {
        const auto& prev_path = a_paths[static_cast<size_t>(ki - 1)].station_ids;
        size_t n = prev_path.size();

        for (size_t i = 0; i + 1 < n; ++i) {
            const std::string& spur_node = prev_path[i];
            std::vector<std::string> root_path(prev_path.begin(), prev_path.begin() + i + 1);

            // Collect removed edges: edges on same root prefix from already-found paths
            std::unordered_set<std::string> removed_edges_set;
            for (const auto& ap : a_paths) {
                const auto& pp_ids = ap.station_ids;
                if (pp_ids.size() > i) {
                    bool same_prefix = true;
                    for (size_t j = 0; j <= i && j < pp_ids.size(); ++j) {
                        if (pp_ids[j] != root_path[j]) {
                            same_prefix = false;
                            break;
                        }
                    }
                    if (same_prefix && i + 1 < pp_ids.size()) {
                        removed_edges_set.insert(
                            edge_removal_key(pp_ids[i], pp_ids[i + 1]));
                    }
                }
            }

            // Remove root path nodes (except spur node)
            std::unordered_set<std::string> removed_nodes;
            for (size_t j = 0; j + 1 < root_path.size(); ++j) {
                if (root_path[j] != spur_node) {
                    removed_nodes.insert(root_path[j]);
                }
            }

            PathResult spur_path = dijkstra_with_removals(
                spur_node, dst_id, graph, mgr,
                removed_edges_set, removed_nodes);

            if (spur_path.valid && !spur_path.station_ids.empty()) {
                // Concatenate: root_path[:-1] + spur_path
                std::vector<std::string> total_path(
                    root_path.begin(), root_path.end() - 1);
                total_path.insert(total_path.end(),
                                  spur_path.station_ids.begin(),
                                  spur_path.station_ids.end());

                int total_t = path_total_time(total_path, graph);

                // Dedup check
                std::string pk = path_key(total_path);
                bool already_have = false;
                for (const auto& ap : a_paths) {
                    if (path_key(ap.station_ids) == pk) {
                        already_have = true;
                        break;
                    }
                }

                if (!already_have) {
                    candidates.push({total_t, total_path});
                }
            }
        }

        if (candidates.empty()) break;

        // Extract best candidate
        while (!candidates.empty()) {
            auto [best_time, best_path] = candidates.top(); candidates.pop();
            PathResult result = rebuild_path_from_ids(best_path, graph, mgr);
            if (result.valid) {
                a_paths.push_back(result);
                break;
            }
        }
    }

    return a_paths;
}

// -------------------------------------------------------------------------
// M4-1: dijkstra_min_transfers
// -------------------------------------------------------------------------

PathResult dijkstra_min_transfers(const std::string& src_id,
                                   const std::string& dst_id,
                                   const Graph& graph,
                                   const StationManager& mgr) {
    if (src_id == dst_id) {
        PathResult r;
        r.station_ids = {src_id};
        r.total_time = 0;
        r.error = "起点和终点相同，无需进行路径规划。";
        return r;
    }

    const Station* src_s = mgr.get(src_id);
    const Station* dst_s = mgr.get(dst_id);
    if (src_s && !src_s->is_open()) {
        PathResult r;
        r.valid = false;
        r.error = "起点：" + src_s->name + "(" + src_s->line + ")已关闭，无法进行路径规划。";
        return r;
    }
    if (dst_s && !dst_s->is_open()) {
        PathResult r;
        r.valid = false;
        r.error = "终点：" + dst_s->name + "(" + dst_s->line + ")已关闭，无法进行路径规划。";
        return r;
    }

    std::unordered_map<std::string, TransferWeight> dist;
    dist[src_id] = {0, 0};

    std::unordered_map<std::string, PredecessorInfo> came_from;
    came_from[src_id] = {"", "", "", 0, false};

    std::priority_queue<std::pair<TransferWeight, std::string>,
                        std::vector<std::pair<TransferWeight, std::string>>,
                        std::greater<>> pq;
    pq.push({{0, 0}, src_id});

    std::unordered_set<std::string> visited;

    // Track which line reaches each node. Seed with the source station's actual
    // line so an origin transfer is properly costed (see min_transfer_with_removals
    // for the full rationale — same rule here).
    std::unordered_map<std::string, std::string> node_line;
    {
        const Station* src_station = mgr.get(src_id);
        node_line[src_id] = src_station ? src_station->line : "";
    }

    while (!pq.empty()) {
        auto [w, u] = pq.top(); pq.pop();

        if (visited.count(u)) continue;
        visited.insert(u);

        if (u == dst_id) {
            return rebuild_path(dst_id, came_from, graph, mgr);
        }

        const auto& cur_line = node_line[u];

        for (const auto& edge : graph.neighbors(u, &mgr)) {
            const auto& v = edge.to_id;
            int new_time = w.time + edge.time;
            int new_transfers = w.transfers;

            if (!edge.is_transfer() && !cur_line.empty() && edge.line != cur_line) {
                new_transfers = w.transfers + 1;
            }

            TransferWeight new_weight{new_transfers, new_time};

            std::string v_line = edge.is_transfer() ? cur_line : edge.line;

            auto it = dist.find(v);
            if (it == dist.end() || new_weight < it->second) {
                if (!v_line.empty()) {
                    node_line[v] = v_line;
                }
                dist[v] = new_weight;
                came_from[v] = {u, edge.line, edge.direction, edge.time, edge.is_transfer()};
                pq.push({new_weight, v});
            }
        }
    }

    PathResult r;
    r.valid = false;
    r.error = "未找到可达路径。";
    return r;
}

// -------------------------------------------------------------------------
// M4-2: yen_k_min_transfers
// -------------------------------------------------------------------------

std::vector<PathResult> yen_k_min_transfers(const std::string& src_id,
                                             const std::string& dst_id,
                                             const Graph& graph,
                                             const StationManager& mgr,
                                             int k) {
    if (src_id == dst_id) {
        PathResult p;
        p.station_ids = {src_id};
        p.total_time = 0;
        p.error = "起点和终点相同，无需进行路径规划。";
        return {p};
    }

    const Station* src_s = mgr.get(src_id);
    const Station* dst_s = mgr.get(dst_id);
    if (src_s && !src_s->is_open()) {
        PathResult r;
        r.valid = false;
        r.error = "起点：" + src_s->name + "(" + src_s->line + ")已关闭，无法进行路径规划。";
        return {r};
    }
    if (dst_s && !dst_s->is_open()) {
        PathResult r;
        r.valid = false;
        r.error = "终点：" + dst_s->name + "(" + dst_s->line + ")已关闭，无法进行路径规划。";
        return {r};
    }

    PathResult first = dijkstra_min_transfers(src_id, dst_id, graph, mgr);
    if (!first.valid || first.station_ids.empty()) {
        return {first};
    }

    std::vector<PathResult> a_paths = {first};
    // Candidates: ((transfers, time), path_ids)
    using Candidate = std::pair<TransferWeight, std::vector<std::string>>;
    auto cmp = [](const Candidate& a, const Candidate& b) {
        return b.first < a.first;  // want min-heap behavior
    };
    std::priority_queue<Candidate, std::vector<Candidate>, decltype(cmp)> candidates(cmp);

    for (int ki = 1; ki < k; ++ki) {
        const auto& prev_path = a_paths[static_cast<size_t>(ki - 1)].station_ids;
        size_t n = prev_path.size();

        for (size_t i = 0; i + 1 < n; ++i) {
            const std::string& spur_node = prev_path[i];
            std::vector<std::string> root_path(
                prev_path.begin(), prev_path.begin() + i + 1);

            std::unordered_set<std::string> removed_edges_set;
            for (const auto& ap : a_paths) {
                const auto& pp_ids = ap.station_ids;
                if (pp_ids.size() > i) {
                    bool same_prefix = true;
                    for (size_t j = 0; j <= i && j < pp_ids.size(); ++j) {
                        if (pp_ids[j] != root_path[j]) {
                            same_prefix = false;
                            break;
                        }
                    }
                    if (same_prefix && i + 1 < pp_ids.size()) {
                        removed_edges_set.insert(
                            edge_removal_key(pp_ids[i], pp_ids[i + 1]));
                    }
                }
            }

            std::unordered_set<std::string> removed_nodes;
            for (size_t j = 0; j + 1 < root_path.size(); ++j) {
                if (root_path[j] != spur_node) {
                    removed_nodes.insert(root_path[j]);
                }
            }

            PathResult spur_result = min_transfer_with_removals(
                spur_node, dst_id, graph, mgr,
                removed_edges_set, removed_nodes);

            if (spur_result.valid && !spur_result.station_ids.empty()) {
                std::vector<std::string> total_path(
                    root_path.begin(), root_path.end() - 1);
                total_path.insert(total_path.end(),
                                  spur_result.station_ids.begin(),
                                  spur_result.station_ids.end());

                int total_t = path_total_time(total_path, graph);
                int total_x = count_line_changes(total_path, graph);

                std::string pk = path_key(total_path);
                bool already_have = false;
                for (const auto& ap : a_paths) {
                    if (path_key(ap.station_ids) == pk) {
                        already_have = true;
                        break;
                    }
                }

                if (!already_have) {
                    candidates.push({{total_x, total_t}, total_path});
                }
            }
        }

        if (candidates.empty()) break;

        while (!candidates.empty()) {
            auto [best_w, best_path] = candidates.top(); candidates.pop();
            PathResult result = rebuild_path_from_ids(best_path, graph, mgr);
            if (result.valid) {
                a_paths.push_back(result);
                break;
            }
        }
    }

    return a_paths;
}

// -------------------------------------------------------------------------
// format_path — console visualization
// -------------------------------------------------------------------------

std::string format_path(const PathResult& result,
                        const StationManager& mgr,
                        const Graph* graph) {
    if (!result.valid) {
        return "[错误] " + result.error;
    }

    std::ostringstream out;

    // Same start/end
    if (result.station_ids.size() == 1) {
        const Station* station = mgr.get(result.station_ids[0]);
        std::string name = station ? station->name : result.station_ids[0];
        out << name << "（起终点相同）\n";
        out << "总耗时: 0 分钟 | 换乘: 0 次";
        return out.str();
    }

    // Build visualized path string
    std::ostringstream path_str;
    int station_count = 0;
    bool prev_emitted_xfer = false;

    for (size_t i = 0; i < result.station_ids.size(); ++i) {
        const Station* station = mgr.get(result.station_ids[i]);

        bool incoming_transfer = false;
        if (i > 0 && graph) {
            const Edge* edge = graph->get_edge(
                result.station_ids[i - 1], result.station_ids[i]);
            incoming_transfer = edge && edge->is_transfer();
        }

        if (incoming_transfer) {
            if (!prev_emitted_xfer) {
                path_str << " --[换乘]-- ";
                prev_emitted_xfer = true;
            }
            // Intermediate transfer-platform nodes are the same physical station
            // and will be shown by the following riding edge. If this is the
            // destination node, keep its station name so the path does not end
            // with a bare transfer marker.
            if (i + 1 != result.station_ids.size()) continue;
        }

        if (station_count > 0 && !prev_emitted_xfer) {
            path_str << " -> ";
        }

        if (!station) {
            path_str << "[?" << result.station_ids[i] << "?]";
            ++station_count;
            prev_emitted_xfer = false;
            continue;
        }

        std::string line_tag = "(" + station->line + ")";

        // 4号线 direction marker
        auto l4_it = result.line4_dirs.find(station->id);
        if (l4_it != result.line4_dirs.end()) {
            line_tag = "(" + station->line + l4_it->second + ")";
        }

        path_str << station->name << line_tag;
        ++station_count;
        prev_emitted_xfer = false;
    }

    out << path_str.str() << "\n\n";
    out << "途经 " << result.station_count() << " 站 | 总耗时: "
        << result.total_time << " 分钟 | 换乘: "
        << result.transfer_count << " 次";

    if (!result.transfer_at.empty()) {
        out << "\n换乘点:";
        for (const auto& [t_name, f_line, t_line] : result.transfer_at) {
            out << "\n  · " << t_name << " (" << f_line << " -> " << t_line << ")";
        }
    }

    return out.str();
}

} // namespace metro::pathfinder
